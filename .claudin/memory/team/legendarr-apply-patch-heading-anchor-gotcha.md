---
name: legendarr-apply-patch-heading-anchor-gotcha
description: apply_patch can reject a hunk whose trailing context runs past a markdown heading, even when the context is byte-identical to the file
type: reference
---

Inserting a new bullet just before a `##` heading in `ROADMAP.md` via `apply_patch`, anchored
on the heading itself (`@@ ## 0.21.0 — Resilience`) with trailing context that continued past
the insertion point through a blank line into the *next* `##` heading, failed twice in a row
with "none of the N line(s) below appear at or after line X" — even though the context was
confirmed byte-for-byte identical to the file (checked with `od -c`, em-dash bytes and all).
Re-anchoring on `@@ <verbatim bullet line right before the insertion>` and dropping the
trailing blank-line+next-heading context entirely (a pure insertion, no context needed after
it) applied cleanly on the first try.

**Why:** saves re-verifying byte content (encoding, whitespace) when `apply_patch` rejects a
hunk that looks correct — trailing context spanning into an unrelated heading is the more
likely culprit than an encoding mismatch.

**How to apply:** when inserting a line just before a markdown heading via `apply_patch`,
anchor on the nearest real content line above the insertion point and omit trailing context
that would span into the next heading — don't spend multiple retries re-checking bytes first.
