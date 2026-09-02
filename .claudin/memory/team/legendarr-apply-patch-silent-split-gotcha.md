---
name: legendarr-apply-patch-silent-split-gotcha
description: Read(offset, limit) that stops before EOF can look like "end of file" — anchoring an apply_patch append there can silently insert into the middle of an existing function
type: reference
---

Read a test file with `offset=390, limit=34` (showing lines 390-423) to check what its last
test function looked like before appending new tests after it. Line 423 (`assert
result.skipped_reason == "no_upgrade_found"`) looked like the final line — no truncation
notice was shown, since a range read that doesn't hit a size cap doesn't warn the caller it
stopped short of EOF. The file actually had one more line, `assert provider.download_calls
== []`, that belonged to the same test. Anchoring `apply_patch`'s insertion on line 423 as
the file's tail applied cleanly (no rejection) but landed five new test functions *between*
that test's two assert lines, splitting it in half — invisible until the suite ran, where it
surfaced as an unrelated-looking `NameError: name 'provider' is not defined` deep inside a
newly added, otherwise-correct test.

**Why:** `apply_patch` only validates that a hunk's context matches somewhere in the file —
it has no notion of "this hunk claims to be at EOF but isn't," so a hunk anchored on a line
that isn't actually the last one applies successfully while corrupting whatever follows it.
Related but distinct from [[legendarr-apply-patch-heading-anchor-gotcha]] (that one is an
explicit *rejection*; this one is a *silent* wrong-location apply).

**How to apply:** before appending new content "at the end of a file" via `apply_patch`,
read with a limit large enough to comfortably overshoot the expected end (or re-read without
`limit` once near the tail) so the actual last line is confirmed, not just the last line a
bounded range happened to return. After such a patch, a quick `git diff` context check (are
the lines right after the insertion point still contiguous with what came before it in the
original function?) catches this before running tests.
