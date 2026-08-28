---
name: legendarr-resilience-constants-hardcoded
description: Circuit breaker + scheduled-retry backoff thresholds are hardcoded module constants, not Settings/config.yaml fields, unlike every other per-job retry/interval knob
type: project
---

Confirmed 2026-08-28 while implementing ROADMAP 0.21.0's second item (scheduled-job
retry backoff, `scheduling/scheduled_retry.py`): unlike every other per-job knob
(`*_retry_attempts`, `*_retry_delay_seconds`, `*_max_instances`, `*_coalesce`,
`*_interval_minutes` — all `Settings`/`AppConfigFile` fields, editable from the Settings
UI), both 0.21.0 "Resilience" features deliberately hardcode their thresholds as plain
module constants with no config surface at all:
- `circuit_breaker.py`'s `FAILURE_THRESHOLD = 3` / `COOLDOWN_SECONDS = 300.0` (PR #75)
- `scheduled_retry.py`'s `MAX_SCHEDULE_RETRIES = 3` / `BACKOFF_SCHEDULE` = `[2min, 5min,
  15min]` (added in the same session as this memory)

Verified by grepping `src/web` for references to each — zero hits both times, confirming
this is deliberate, not an oversight left over from either PR.

**Why:** these are internal backoff/circuit-breaker policy for provider and job
resilience, not user-facing tuning — the same category of decision as picking the retry
count baked into `with_retry`, not a per-environment setting.

**How to apply:** when adding a similar internal resilience threshold (backoff delays,
failure thresholds, cooldowns) for a future roadmap item, default to a hardcoded module
constant like these two rather than a new `Settings`/`config.yaml` field — don't assume
every new numeric knob needs to be user-configurable just because most job-scheduling
knobs are (see [[legendarr-scheduling-job-conventions]] for those). This does NOT extend
to genuinely user-facing operational settings, e.g. retention counts/days for the
0.22.0 "Maintenance & backup" item — those are real user tuning, not internal policy.
