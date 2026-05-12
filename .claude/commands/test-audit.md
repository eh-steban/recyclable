Run a comprehensive test suite audit using the test-auditor subagent.

Scan all test files across all services and report:

1. Coverage gaps (components/endpoints/functions with no tests)
2. Missing error path tests
3. Stale or skipped tests
4. Pattern compliance issues
5. Prioritized action list

Use the test-auditor agent for this work. Output should be actionable --
each gap should specify what to test and estimated effort.

Recommended cadence: monthly, or before any major release.
