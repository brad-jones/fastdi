---
name: execute-plan
description: Read an implementation plan from ./docs/plans/ and implement it — writing/editing ./src/fastdi and ./tests — iterating until every spec's test suite and the root test suite pass. Use this after plan-implementation has produced a plan and the user wants it built. Do not use this to write a plan yourself; that's plan-implementation's job.
---

# execute-plan

This skill implements a plan that `plan-implementation` already wrote. It is the only skill of the three that edits
`./src/fastdi`.

## 1. Pick the plan

If the user names a plan, use it. Otherwise, list `./docs/plans/*.md` and use the most recent one with
`status: draft` or `status: in-progress` in its frontmatter. If none exists, stop and say so — don't improvise a plan
inline; that's a different skill.

Read the plan in full, plus every spec it references under `./specs/` (their `README.md`, `main.py`, and tests) and
the current state of `./src/fastdi` and `./tests/`.

## 2. Implement

Set the plan's frontmatter to `status: in-progress` before starting.

Work through the plan's `./src/fastdi` changes in the order it lists them (it's already ordered to avoid forward
dependencies). Write real implementation code — no stubs, no `NotImplementedError` placeholders left behind, no
`# TODO` deferrals for anything the plan describes as in-scope. If, while implementing, you find the plan is wrong or
incomplete about something concrete (a signature that doesn't actually work, a missing case), fix it in the code and
note the deviation in the plan file rather than silently diverging — don't stop to regenerate the whole plan for a
small correction.

Then add the test cases the plan lists under `./tests/`.

## 3. Verify

Run, in order, fixing forward until each is clean:

1. `uv run pytest specs` — every spec's own suite.
2. `uv run pytest tests` — the root framework suite.
3. `uv run ruff check .`
4. `uv run pyright`

A plan is not done until all four are clean. If a spec's test still fails after implementing what the plan describes,
that's either an implementation bug (fix it) or a sign the plan itself was incomplete (update `./src/fastdi` further
and note it in the plan) — don't mark the plan done with a failing spec suite.

## 4. Close out

Set the plan's frontmatter to `status: done` (add a `completed: <date>` field) once all four checks pass. Tell the
user which plan was executed, what changed under `./src/fastdi`, and confirm the verification commands are clean.
