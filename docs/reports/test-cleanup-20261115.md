# Test cleanup — 15 Nov 2026

Starting commit `9aad6d30c4b4c368ac293c4b7d09aaa99be54402`; clean worktree. Inventoried tracked test files (~6,028 lines), scanned source reads, mock-only cases and test names, and reviewed candidates; this was not a line-by-line audit.

Removed five literal workflow/source checks from `tests/test_deps_jobs.py` (44 lines): `test_upgrade_script_is_uv_lock_upgrade`, `test_dependabot_stops_per_package_prs`, `test_weekly_batch_workflow_tests_then_merges`, `test_automerge_covers_dependabot_and_weekly_branch`, and `test_agentic_workflow_is_capped_and_separate`. They checked substrings rather than executing GitHub configuration or enforcing successful checks before merge. Workflow operation and configuration validity are not equivalently covered and remain unverified. Retained actual offline suggestion cap, prompt, no-key, existing-issue, and single-issue behavior; bot routing, token, send and access tests were preserved.

Project-environment pytest initially failed to import botspot via shared conftest. This pure module does not need it: `UV_OFFLINE=1 uv run --no-sync pytest --noconftest -q tests/test_deps_jobs.py` — 5 passed. `git diff --check` passed. No provider, network, bot send, manual commit or push.
