---
name: legendarr-scheduled-retry-e2e-flaky-in-ci
description: test_end_to_end_a_real_one_off_jobs_failure_gets_a_backed_off_follow_up intermittently fails on GitHub Actions, not locally
type: project
---

`src/backend/tests/scheduling/test_scheduled_retry.py::test_end_to_end_a_real_one_off_jobs_failure_gets_a_backed_off_follow_up`
uses a real `BackgroundScheduler` thread and polls `scheduler.get_job(...)` for up to 2.5s
(`for _ in range(50): ... time.sleep(0.05)`) waiting for the backed-off retry job to land in
the jobstore. Confirmed flaky on GitHub Actions (PR #93, run 33287675209, job
99193618688, 2026-08-30): failed with `assert job is not None` after the full suite took
158s on that runner (vs ~71s locally), while 10 back-to-back local runs of just this test
all passed in ~0.07s each. Root cause looks like CI-runner contention pushing past the
2.5s poll window, not a real scheduling bug — unrelated to whatever PR happened to be
running when it triggered.

**Why:** seeing this test fail in CI for an unrelated PR isn't a signal that PR broke
scheduling — don't chase it as a regression in the diff.

**How to apply:** if this exact test fails in CI and the PR doesn't touch
`scheduling/scheduled_retry.py` or `scheduling/retry.py`, just `gh run rerun <run-id>
--failed` and move on. If it starts failing repeatedly, the fix is to raise the poll
budget in the test (e.g. more/longer iterations) rather than treat it as a product bug.
