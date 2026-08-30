---
name: execute-plan
description: Read an implementation plan from ./docs/plans/ and implement it — writing/editing ./src/fastdi and ./tests — iterating until the test suites of the specs that plan covers, plus the root test suite, pass. Use this after plan-implementation has produced a plan and the user wants it built. Do not use this to write a plan yourself; that's plan-implementation's job.
---

# execute-plan

This skill implements a plan that `plan-implementation` already wrote. It is the only skill of the three that edits
`./src/fastdi`.

## 1. Pick the plan

If the user names a plan, use it — but if its `status:` is `done` or `superseded`, say so and confirm before touching
anything. Otherwise, list `./docs/plans/*.md` with `status: draft` or `status: in-progress` in their frontmatter
(`in-progress` means an earlier run was interrupted; resume it rather than starting fresh). A `blocked` plan is only
ever executed when the user names it explicitly, since something about it needed a human. If there isn't exactly one
candidate, ask the user which to execute — don't silently guess by recency. If none exists, stop and say so — don't
improvise a plan inline; that's a different skill.

Read the plan in full, plus every spec it references under `./specs/` (their `README.md`, `main.py`, and tests) and
the current state of `./src/fastdi` and `./tests/`.

If the plan flags an unresolved contradiction — between two specs, or within one spec's README/`main.py`/tests — don't
execute it. Set it to `status: blocked`, note why, and tell the user the spec needs another `create-spec` pass. Neither
this skill nor `plan-implementation` may edit specs, so implementing around a known contradiction just bakes in a
guess.

## 2. Implement

Set the plan's frontmatter to `status: in-progress` before starting.

Work through the plan's `./src/fastdi` changes in the order it lists them (it's already ordered to avoid forward
dependencies). Write real implementation code — no stubs, no `NotImplementedError` placeholders left behind, no
`# TODO` deferrals for anything the plan describes as in-scope. If, while implementing, you find the plan is wrong or
incomplete about something concrete (a signature that doesn't actually work, a missing case), fix it in the code and
append a note to the plan's **Deviations** section rather than silently diverging — append only; don't rewrite the rest
of the plan, and don't stop to regenerate the whole thing for a small correction. Keep changes scoped to what the plan
actually calls for; if something's missing that you need to proceed, make the smallest faithful extension consistent
with the plan's intent rather than inventing unrelated API surface.

If executing the plan reveals a spec is genuinely infeasible — not just hard, but unimplementable as written — stop
and report clearly (which spec, which requirement, why) rather than pushing through with a different, easier API than
the one specified. Don't adjust the spec yourself: close out per step 4 as `blocked` and tell the user the spec needs
another `create-spec` pass, followed by a fresh `plan-implementation` run.

Then add the test cases the plan lists under `./tests/`.

## 3. Verify

Run, in order, fixing forward until each is clean:

1. `task fmt` — auto-format the code.
2. `task lint` — runs `dprint check`, `ruff check`, and `pyright` together.
3. `task test` — every spec's own suite plus the root framework suite.

Plus anything extra the plan's own **Verification** section calls for.

`task test` is repo-wide, but this plan is not: only the specs listed in its `specs:` frontmatter are yours to make
pass. A spec outside that list which was already failing before you started is expected — it's waiting on a plan of its
own. So the bar for done is: `task fmt` and `task lint` clean, the root suite clean, and the suites of this plan's
specs clean. Report any out-of-scope spec failures you observed rather than fixing them here; if you _caused_ one (it
passed before your changes and doesn't now), that's a regression and it is yours to fix.

A plan is not done until that bar is met. If one of this plan's spec tests still fails after implementing what the plan
describes, that's either an implementation bug (fix it) or a sign the plan itself was incomplete (update
`./src/fastdi` further and note it under **Deviations**) — don't mark the plan done with a failing in-scope spec suite.

## 4. Close out

Once the step 3 bar is met, set the plan's frontmatter to `status: done` and fill in `completed: <today, YYYY-MM-DD>`.
Tell the user which plan was executed, what changed under `./src/fastdi`, which verification commands are clean, and
any deviations you appended.

If you hit a genuine blocker per step 1 or step 2, stop there instead: set `status: blocked`, record what's blocking
and what you'd already implemented in the plan's **Deviations** section, leave `completed:` empty, and report it. Don't
leave a stopped plan sitting at `in-progress` — that makes it look like an interrupted run that the next invocation
should just resume.
