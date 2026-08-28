---
name: legendarr-playwright-mcp-numeric-param-schema-bug
description: Playwright MCP tools intermittently fail schema validation — number/boolean params fail per-field, and a session's first call(s) can fail with a schema-compile error regardless of param shape; retry once then fall back to browser_run_code_unsafe
type: feedback
---

When a Playwright MCP tool call fails with a schema error like "data/width must be number" or
"data/static must be boolean" even though the argument passed genuinely is a number/boolean,
don't keep re-issuing the identical call — it's a client-side schema-validation glitch in the MCP
bridge, not a mistake in the arguments. Confirmed 2026-08-26: `browser_resize({width: 390, height:
844})` failed the same way 3 times in a row and never recovered; `browser_wait_for({time: 1})`,
`browser_network_requests({static: false})` and `browser_console_messages({all: true})` each hit
the same error at least once but succeeded on a retry. Confirmed again 2026-08-27:
`browser_handle_dialog({accept: true})` failed 3 times in a row with "data/accept must be boolean"
against a genuine `confirm()` dialog and never recovered.

**Why:** the failure is spurious, not a real argument problem — after 3 identical failures the
harness itself warns that repeating the call unchanged will fail the same way, and burning turns
on a tool call that structurally can't succeed wastes the session. `browser_resize` and
`browser_handle_dialog` in particular have been observed to never recover no matter how many
times they're retried.

**How to apply:** retry an affected call at most once. If it fails again, switch to
`mcp__playwright__browser_run_code_unsafe` and do the same thing with raw Playwright code instead
— e.g. `page.setViewportSize({width, height})` in place of `browser_resize`, or
`page.waitForTimeout(ms)` in place of `browser_wait_for`. That tool takes a single code-string
parameter, so it isn't subject to the same per-field schema validation as the others.
`browser_handle_dialog` needs a different shape of fallback than the others because it only acts
on an *already-open* dialog: register the handler *before* the action that opens it, in the same
script — `page.once('dialog', d => d.accept()); await page.getByRole('button', {name:
'...'}).click();` — rather than clicking first and trying to handle the dialog reactively
afterward, which does not reliably resolve it once the native dialog is already blocking.

Confirmed 2026-08-28: a different symptom of the same underlying flakiness — `Failed to compile
JSON schema for validation: Error: no schema with key or ref
"https://json-schema.org/draft/2020-12/schema"` on the *first* call of a fresh session, hitting
`browser_navigate` (single string param), `browser_snapshot` (no required params), and
`browser_take_screenshot` (has a boolean `fullPage`) alike — so this one isn't specific to
number/boolean fields, just an early-session glitch. A plain retry of the identical call fixed it
every time, no `browser_run_code_unsafe` fallback needed for this particular error shape.
