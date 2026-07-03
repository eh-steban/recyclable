export const meta = {
  name: 'review-gate',
  description:
    'Project review gate: test-auditor + code-reviewer + adversarial-reviewer fan out over a diff, every finding is adversarially refuted (killing false positives), then comment-reviewer runs last on the final state.',
  whenToUse:
    'Before marking a diff done. Pass the diff range + worktree in args. Returns only findings that survived refutation, grouped by severity, plus the comment-review pass.',
  phases: [
    { title: 'Preflight', detail: 'sensor agent confirms the diff is non-empty; empty diff fails the gate loud' },
    { title: 'Review', detail: 'test-auditor + code-reviewer + adversarial-reviewer in parallel over the diff' },
    { title: 'Verify', detail: 'independent skeptic refutes each finding; syntax/runtime/version claims checked against the real interpreter' },
    { title: 'Comment', detail: 'comment-reviewer against the final diff, last' },
  ],
}

// ---------------------------------------------------------------------------
// args: { range?: string, worktree?: string, paths?: string[] }
//   range    -- git revision range to review, e.g. "main..HEAD" or "abc123..def456"
//   worktree -- absolute path to the repo/worktree the reviewers run git in
//   paths    -- optional path filters (defaults to the whole diff)
// ---------------------------------------------------------------------------
const range = (args && args.range) || 'main...HEAD'
const worktree = (args && args.worktree) || '.'
const paths = args && args.paths && args.paths.length ? args.paths.join(' ') : ''

// Embed the exact diff command so agents cannot fall back to `git diff` with no
// range in the wrong cwd (the failure mode that made a prior run review an
// empty diff and still report success).
const diffCmd = `git -C ${worktree} diff ${range}${paths ? ' -- ' + paths : ''}`

const target =
  `Worktree: ${worktree}\n` +
  `Diff under review: \`${diffCmd}\`\n` +
  `Run that exact command to read the diff under review. ` +
  `Backend tests/type-checks run in the container (docker compose exec -T app-backend ...), not on the host.`

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'title', 'file', 'line', 'claim', 'suggested_fix'],
        properties: {
          severity: { type: 'string', enum: ['blocking', 'should-fix', 'nit'] },
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'string', description: 'e.g. "84" or "84-90" or "n/a"' },
          claim: { type: 'string', description: 'The precise, falsifiable assertion.' },
          suggested_fix: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'reason', 'verification_method'],
  properties: {
    verdict: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
    reason: { type: 'string' },
    verification_method: {
      type: 'string',
      description: 'How you checked -- e.g. "ran the construct in the container", "read the file", "grepped invariants.md".',
    },
  },
}

const COMMENT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'line', 'issue', 'recommendation'],
        properties: {
          file: { type: 'string' },
          line: { type: 'string' },
          issue: { type: 'string' },
          recommendation: { type: 'string' },
        },
      },
    },
  },
}

const PREFLIGHT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['files_changed', 'branch', 'summary'],
  properties: {
    files_changed: { type: 'integer', description: 'Count of files in the diff; 0 if the diff is empty.' },
    branch: { type: 'string' },
    summary: { type: 'string', description: 'One line, e.g. "40 files changed, 4195 insertions".' },
  },
}

// Each review dimension maps to the project agent that owns it.
const DIMENSIONS = [
  {
    key: 'tests',
    agentType: 'test-auditor',
    instruction:
      'Audit the test coverage of the diff: missing error/edge paths, invariant coverage, tests that overstate or falsely claim coverage, stale tests. Verify any invariant ID you cite actually exists in private/invariants.md.',
  },
  {
    key: 'correctness',
    agentType: 'code-reviewer',
    instruction:
      'Review for correctness bugs, security vulnerabilities, and convention violations. Verify any rule/invariant you cite exists.',
  },
  {
    key: 'adversarial',
    agentType: 'adversarial-reviewer',
    instruction:
      'Attack assumptions and invariants: auth/data boundaries, injection at ingestion time, races, LLM grounding/refusal bypass, and operational failure modes.',
  },
]

// Preflight: refuse to review an empty or mis-targeted diff. The script has no
// shell access, so a sensor agent runs the diff command and reports the file
// count; an empty diff throws (fail loud) instead of silently "passing" -- the
// failure mode a prior run hit when it reviewed the wrong tree.
phase('Preflight')
const preflight = await agent(
  `Run this exact command and report what it shows:\n\`${diffCmd} --stat\`\n` +
    `Also run \`git -C ${worktree} rev-parse --abbrev-ref HEAD\` for the branch name.\n` +
    `Report files_changed (the integer count of changed files, 0 if none), the branch, ` +
    `and a one-line summary. This guards that the review targets a real, non-empty diff.`,
  { label: 'preflight:diff-sensor', phase: 'Preflight', schema: PREFLIGHT_SCHEMA },
)
if (!preflight || !preflight.files_changed || preflight.files_changed < 1) {
  throw new Error(
    `review-gate preflight FAILED: \`${diffCmd}\` is empty ` +
      `(files_changed=${preflight ? preflight.files_changed : 'null'}). ` +
      `Refusing to review an empty diff -- check the range/worktree args.`,
  )
}
log(`Preflight: ${preflight.summary} on ${preflight.branch} -- non-empty, proceeding.`)

phase('Review')

// Pipeline: each dimension's findings flow straight into refutation as soon as
// that reviewer returns -- no barrier, so a fast reviewer's findings verify
// while a slow reviewer is still working.
const reviewed = await pipeline(
  DIMENSIONS,
  (d) =>
    agent(`${d.instruction}\n\n${target}\n\nReturn structured findings, each with a concrete path:line and a precise falsifiable claim. Empty findings are valid -- do not pad.`, {
      label: `review:${d.key}`,
      phase: 'Review',
      schema: FINDINGS_SCHEMA,
      agentType: d.agentType,
    }),
  (review, d) =>
    parallel(
      ((review && review.findings) || []).map((f) => () =>
        agent(
          `You are an adversarial verifier. A reviewer produced the finding below; your job is to REFUTE it.\n\n` +
            `Severity: ${f.severity}\nTitle: ${f.title}\nLocation: ${f.file}:${f.line}\nClaim: ${f.claim}\nSuggested fix: ${f.suggested_fix}\n\n${target}\n\n` +
            `RULES:\n` +
            `- If the claim asserts anything about language syntax, runtime behavior, a stdlib/library API, or a version-specific feature, VERIFY it empirically against the actual interpreter/tooling (run it in the container). Do NOT reason from memory. A reviewer asserting it -- even two reviewers -- is not verification.\n` +
            `- If the claim cites a rule/invariant/spec ID, confirm that ID exists and says what is claimed.\n` +
            `- Default your verdict to "refuted" unless you can independently confirm the finding is both real and material.\n` +
            `Report your verdict and exactly how you checked.`,
          { label: `verify:${d.key}:${f.file}`, phase: 'Verify', schema: VERDICT_SCHEMA },
        ).then((v) => ({ ...f, dimension: d.key, verdict: v })),
      ),
    ),
)

const findings = reviewed.flat().filter(Boolean)
const confirmed = findings.filter((f) => f.verdict && f.verdict.verdict === 'confirmed')
const refuted = findings.filter((f) => f.verdict && f.verdict.verdict === 'refuted')
const uncertain = findings.filter((f) => f.verdict && f.verdict.verdict === 'uncertain')

log(`Review: ${findings.length} raw findings -> ${confirmed.length} confirmed, ${uncertain.length} uncertain, ${refuted.length} refuted`)

// Comment-reviewer runs LAST, against the same (final) diff -- per the project
// review-gate order. It is not adversarially verified; its output is advisory.
phase('Comment')
const commentReview = await agent(
  `Audit comments and docstrings in the diff for (a) knowledge that belongs in a higher tier (mental model / learnings / spec) rather than inline, and (b) redundant comments that merely restate the code. Recommend deletion over trimming when a comment only echoes a spec/section.\n\n${target}\n\nReturn findings with path:line.`,
  { label: 'comment-reviewer', phase: 'Comment', schema: COMMENT_SCHEMA, agentType: 'comment-reviewer' },
)

const bySeverity = (sev) => confirmed.filter((f) => f.severity === sev)

return {
  summary: {
    raw_findings: findings.length,
    confirmed: confirmed.length,
    uncertain: uncertain.length,
    refuted: refuted.length,
    blocking_confirmed: bySeverity('blocking').length,
    comment_findings: (commentReview && commentReview.findings && commentReview.findings.length) || 0,
  },
  confirmed,
  uncertain, // surface these -- a human decides; "uncertain" is not "safe"
  refuted: refuted.map((f) => ({
    title: f.title,
    where: `${f.file}:${f.line}`,
    why_refuted: f.verdict && f.verdict.reason,
  })),
  comment_review: commentReview,
}
