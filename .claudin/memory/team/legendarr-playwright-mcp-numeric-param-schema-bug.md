---
name: legendarr-playwright-mcp-numeric-param-schema-bug
description: Playwright MCP tools with number/boolean params (browser_resize, browser_wait_for, browser_network_requests, browser_console_messages) intermittently fail schema validation even with correctly-typed arguments — retry once then fall back to browser_run_code_unsafe
type: feedback
---

When a Playwright MCP tool call fails with a schema error like "data/width must be number" or
"data/static must be boolean" even though the argument passed genuinely is a number/boolean,
don't keep re-issuing the identical call — it's a client-side schema-validation glitch in the MCP
bridge, not a mistake in the arguments. Confirmed 2026-08-26: `browser_resize({width: 390, height:
844})` failed the same way 3 times in a row and never recovered; `browser_wait_for({time: 1})`,
`browser_network_requests({static: false})` and `browser_console_messages({all: true})` each hit
the same error at least once but succeeded on a retry.

**Why:** the failure is spurious, not a real argument problem — after 3 identical failures the
harness itself warns that repeating the call unchanged will fail the same way, and burning turns
on a tool call that structurally can't succeed wastes the session. `browser_resize` in particular
never recovered no matter how many times it was retried.

**How to apply:** retry an affected call at most once. If it fails again, switch to
`mcp__playwright__browser_run_code_unsafe` and do the same thing with raw Playwright code instead
— e.g. `page.setViewportSize({width, height})` in place of `browser_resize`, or
`page.waitForTimeout(ms)` in place of `browser_wait_for`. That tool takes a single code-string
parameter, so it isn't subject to the same per-field schema validation as the others.
