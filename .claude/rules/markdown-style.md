---
paths:
  - "**/*.md"
  - "**/*.markdown"
---

# Markdown Style Guide

Adapted from Google's markdown styleguide. Primary sources:

- [Google styleguide -- philosophy][src-philosophy]
- [Google styleguide -- markdown style rules][src-style]
- [Gitiles markdown spec -- renderer behavior][src-gitiles]

[src-philosophy]: https://google.github.io/styleguide/docguide/philosophy.html
[src-style]: https://google.github.io/styleguide/docguide/style.html
<!-- markdownlint-disable-next-line MD013 -->
[src-gitiles]: https://gerrit.googlesource.com/gitiles/+/HEAD/Documentation/markdown.md

Snapshot date: 2026-05-01

---

## Project deltas

These two rules override or refine the Google defaults.
They are listed first because they contradict common assumptions.

### Em-dashes: blanket ban everywhere

Em-dashes (`—`) are **banned in all contexts** -- prose, `.md` files,
commit messages, PR titles, everything.

Use `--` (double-hyphen) instead.

Reason: the em-dash byte sequence (`<E2><80><94>`) renders as mojibake in
some terminals and git diff views depending on locale. This project switches
machines; portability wins.

### Line wrapping: semantic wrap at ~80 columns; orphan wraps banned

Wrapping at approximately 80 columns is acceptable -- and often preferred
for reviewability -- provided the wrap falls at a semantic boundary:
a sentence end, a clause boundary, after a comma, or before a long
parenthetical.

**Banned:** orphan wraps, where a break leaves only 1-3 words alone on the
next line with no semantic reason for the break. These break reading flow
without aiding it.

Good:

```text
The assistant returns a cited answer whenever the knowledge base contains
a matching rule for the queried jurisdiction and material combination.
```

Bad (orphan wrap):

```text
The assistant returns a cited answer whenever the knowledge base contains a
matching rule for the
queried jurisdiction and material combination.
```

Also banned: mid-phrase wraps that cut apart a noun phrase, a verb and its
object, or a preposition and its object.

---

## General rules

### Headings

Use ATX-style headings (`#`, `##`, `###`) -- not Setext underlines.
One blank line before and after each heading.

```markdown
## Correct

Not this
--------
```

Each document has exactly one H1 (`#`). It is the document title.
Do not use H1 inside the body for section headings.

Capitalize headings as you would a sentence (first word + proper nouns),
not in Title Case.

### Document layout

A well-formed document follows this order:

1. Title (`# ...`)
2. Short intro paragraph -- what this document is and who it is for
3. `[TOC]` if the document is long enough to warrant navigation
4. Topic sections
5. "See also" section for links to related docs (optional)

Not every document needs all of these. Apply judgment.
A two-section rules file does not need a TOC.

### Lists

Use `-` for unordered lists. Use `1.` for every item in ordered lists
when the list is long or may be edited frequently -- renderers handle
the actual numbering ("lazy numbering"). Reserve explicit sequential
numbers only for short, stable ordered lists where the numbers themselves
carry meaning.

Nest with four-space indentation. Avoid nesting deeper than two levels;
restructure the content instead.

### Links

For short, readable URLs: inline links are fine -- `[text](url)`.

For long or repeated URLs: use reference-style links to keep prose
readable.

```markdown
See the [Denver rules page][denver-rules] for details.

[denver-rules]: https://example.com/very/long/path/that/would/clutter
```

**Inline links that force short lines: prefer reference-style.** When an
inline link's URL is long enough that wrapping around it leaves
neighboring lines noticeably short of the 80-column cap (e.g. under
~60 columns), convert it to a reference-style link. The wrap is only
useful when it falls at a semantic boundary in continuous prose; if the
URL itself is what is forcing the break, the result reads as a stutter
of half-empty lines and harms readability more than a single longer
line would.

Bad (wrapping forced by URL length, leaves a 33-col orphan):

```markdown
This repo uses [pre-commit](https://pre-commit.com) to run
[gitleaks](https://github.com/gitleaks/gitleaks) (secret scanner) on
every commit.
```

Good (reference-style; prose flows at full width):

```markdown
This repo uses [pre-commit][pre-commit] to run [gitleaks][gitleaks]
(secret scanner) on every commit.

[pre-commit]: https://pre-commit.com
[gitleaks]: https://github.com/gitleaks/gitleaks
```

### Product names and capitalization

Preserve the capitalization of product and project names exactly as they
style themselves: `Next.js`, `Postgres`, `Neon`, `Railway`, `Vercel`,
`Claude`. Do not normalize to all-caps or all-lowercase.

---

## Code blocks

Always use fenced code blocks (triple backtick). Always declare the
language tag.

````markdown
```python
result = retriever.query(jurisdiction="denver", material="cardboard")
```
````

Do not use indented code blocks. Do not leave the language tag blank.

**Nesting code in lists:** indent the fence by four spaces to align with
the list item content, not the bullet.

```markdown
- Run the ingestion job:

    ```bash
    python -m app.cli ingest --source <url>
    ```
```

**Line length in code blocks:** the 80-column cap applies to code lines
where the language permits breaking. Use line-continuation characters
(`\` in bash/Python, `...` in YAML multi-line strings) to stay under the
cap when reasonable.

**Conflict with Google's guidance:** Google's styleguide does not exempt
code blocks from the line-length rule but acknowledges that some command
strings and import paths are unavoidably long. This project follows the
same pragmatic position: prefer short lines; do not break a line just to
hit 80 columns if the break harms readability or requires a continuation
character the reader would find surprising. Long lines inside code fences
are a linter warning, not a hard error.

**Escaping newlines in shell examples:** when a shell command is broken
across lines for readability, use `\` at the end of each continued line.
The last line carries no trailing `\`.

```bash
docker build \
  --tag recyclable-frontend:local \
  --file frontend/Dockerfile \
  .
```

---

## Tables

Use tables only for short, narrow, genuinely tabular data. Every
table must have a header row and a separator row. The 80-column
soft cap applies to table rows -- if a row would exceed it, the
data does not belong in a table; use sub-headings or bullet lists
with bold labels instead.

**Alignment syntax:**

| Syntax | Meaning |
| :----- | :------ |
| `:---` | Left-align (default) |
| `---:` | Right-align |
| `:---:` | Center-align |

---

## Images

Per the Gitiles markdown spec:

- Always include alt text: `![descriptive alt text](path/to/image.png)`.
- Images do not render in plain-text contexts (terminals, git log,
  patch emails). Do not use an image to convey information that
  prose cannot convey -- use images only for diagrams or screenshots
  that supplement prose, never replace it.
- Prefer reference-style image syntax for long paths:
  `![alt text][img-id]` with `[img-id]: path` at the bottom.
- Keep image files in an `assets/` or `images/` subdirectory alongside
  the document, not scattered at the repo root.

---

## Renderer notes

The Gitiles markdown spec documents a behavior shared by most modern
renderers: line breaks within a paragraph are ignored by the parser.
A newline in source is treated as a space, not a `<br>`. This is what
makes semantic wrapping safe -- the rendered output is unaffected by
where you break source lines within a paragraph.

Explicit `<br>` tags or double-space line endings are the only way to
force an in-paragraph break. Avoid both in prose; use them only in
tables or other contexts where layout demands it.
