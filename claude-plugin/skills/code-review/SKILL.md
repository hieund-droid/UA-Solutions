---
name: code-review
description: Review pending changes for quality — naming, clarity, likely bugs, test coverage, Apero conventions. Lighter than /security-review. Use for a second opinion before requesting human review.
---

# /code-review

Diff = `git diff main...HEAD`. Read `CLAUDE.md` + the project's stack addendum. Read files around the diff — never review hunks in isolation.

## Check

1. **Naming** — descriptive, full words, no made-up abbreviations.
2. **Clarity** — happy path obvious; errors at edges; comments only for the *why*, not the *what*.
3. **Likely bugs** — off-by-one; null-deref after conditional assign; un-awaited promises; input mutation; float for money; local time without TZ.
4. **Tests** — each new function has a test that would fail without it; bug fix has a regression test; tests don't mock the thing under test.
5. **Convention drift** — wrong package manager; layout renamed; new deps without justification.
6. **Scope creep** — does the PR match its title, or has it grown? Flag for splitting.

## Output

```
CODE REVIEW — <branch> vs main

MUST FIX
  - file:line — finding
CONSIDER
  - file:line — finding
NICE
  - what's good
```

## Don't

- Don't repeat what `/security-review` catches.
- Don't bikeshed prettier/eslint output — those are deterministic.
- Don't recommend big refactors inside a small PR.
