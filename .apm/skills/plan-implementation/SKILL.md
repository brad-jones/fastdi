---
name: plan-implementation
description: Read every spec under ./specs/ and every rule under ./docs/rules/, plus the current state of ./src/fastdi, and write a markdown implementation plan under ./docs/plans/ describing the diff needed to satisfy them. Use this after a spec or rule has been created or changed and before writing any framework code. Writes a plan only — never edits ./specs/, ./docs/rules/, ./src/fastdi, or ./tests directly.
---

# plan-implementation

This skill turns the spec-driven source of truth (`./specs/*`) and the rules that constrain how it's built
(`./docs/rules/*`) into a concrete, reviewable plan for changing `./src/fastdi`. It produces a markdown document,
nothing else. Actually writing the code is `execute-plan`'s job.

## 1. Gather the full picture

Read, in full:

- Every `./specs/<name>/README.md`, `main.py`, and test suite under `./specs/<name>/tests/`. The README is the
  authoritative description of behavior; `main.py` and the tests show it concretely — cross-check them against the
  README for drift (a spec that's been hand-edited inconsistently is a defect to flag in the plan, not silently
  resolve).
- Every `./docs/rules/*.md`. These are binding constraints on the code you're about to plan, not suggestions: a rule
  takes precedence over the workspace instructions and over any APM-supplied skill (`coding-standards`, `testing`,
  `tooling`) it contradicts. Where the rules are silent, those skills still apply as normal.
- The current contents of `./src/fastdi` (every module, however small).
- The current contents of `./tests/` (root framework-level suite), so the plan doesn't propose tests that already
  exist.
- Existing plans under `./docs/plans/` whose `status:` is `draft`, `in-progress` or `blocked` (see the status
  lifecycle in step 3). Those are the only in-flight ones; `done` and `superseded` plans are history and can be
  skipped. An in-flight plan covering the same area should be superseded (see step 3) rather than silently
  duplicated.

## 2. Work out the diff

For each spec, determine what's missing or wrong in `./src/fastdi` for that spec's `main.py` and tests to pass:
new modules, classes, functions, or changes to existing ones. Note the dependency order across specs where one spec's
implementation is a prerequisite for another's (e.g. basic registration/resolution before scoped lifetimes).

If step 1's cross-check turned up drift _within_ a single spec — its README, `main.py` and tests describing genuinely
contradictory behavior, such that there's no single design that satisfies all three — stop and report it to the user
instead of writing a plan. You can't edit specs, and neither can `execute-plan`, so a plan built on a contradictory
spec has nowhere to go: the spec needs another `create-spec` pass first. Say which spec, which files disagree, and how.
Drift that's merely a _gap_ (the tests don't cover something the README describes, or vice versa) isn't a blocker —
note it in the plan and design for what the README says, since the README is authoritative.

Where two specs imply overlapping or conflicting API shapes, reconcile them into one coherent design — don't produce a
plan that would make one spec pass at the expense of another silently regressing. If specs genuinely conflict (not
just overlap), say so explicitly in the plan rather than picking a side unstated.

Now constrain that design by the rules. Specs govern the _what_ — the public API and its observable behavior — and
rules govern the _how_, so in the normal case they compose: the spec says a capability exists, and the rules narrow the
set of acceptable implementations of it. Apply them to the `./tests/` additions too, not just `./src/fastdi`; a rule
about how code is written usually has something to say about how it's tested. Where a rule rules out the obvious
approach, plan the compliant one and say why in the plan, so `execute-plan` doesn't "fix" it back.

If a rule and a spec genuinely can't both be satisfied — the rule forbids the only way to deliver an API the spec
requires — stop and report it to the user instead of writing a plan, exactly as with a contradictory spec. Name the
rule, the spec requirement, and why they can't coexist. You may not edit either, and neither may `execute-plan`, so
either the rule needs narrowing via `create-rule` or the spec needs another `create-spec` pass. That's the user's call.
A rule never wins by default just because rules outrank skills; that precedence is over ambient guidance, not over the
specs.

Then look past the specs to `./src/fastdi`'s own internal correctness and coverage: identify unit-level behavior that
none of the specs exercise directly but that the implementation still needs to get right — error paths, boundary
conditions, invariants an internal helper must uphold. These become the additional tests you plan for `./tests/`
(spec suites cover the public API end-to-end; `./tests/` covers what they don't reach).

## 3. Write the plan

Create `./docs/plans/NNNN-<slug>.md`, zero-padded to four digits. Take the highest number already under
`./docs/plans/` and add one; if the directory is empty (only `.gitkeep`), start at `0001`.

Frontmatter:

```markdown
---
status: draft
date: <today, YYYY-MM-DD>
completed:
specs: [<name>, <name>, ...]
rules: [<slug>, <slug>, ...]
---
```

`specs:` must list every spec this plan is responsible for making pass — `execute-plan` uses exactly that list to
decide which spec suites gate completion, so a spec left off it won't be verified.

`rules:` lists the rules that materially shaped this plan, by slug, and may be empty. Unlike `specs:` it is provenance
rather than a filter: `execute-plan` reads every rule under `./docs/rules/` regardless of what's listed here, so
omitting one doesn't excuse the implementation from it.

`status:` is the shared lifecycle both this skill and `execute-plan` read and write. It is the only vocabulary
allowed:

| Status        | Meaning                                              | Set by                       |
| ------------- | ---------------------------------------------------- | ---------------------------- |
| `draft`       | Written, not started.                                | this skill, at creation      |
| `in-progress` | Being implemented right now, or an interrupted run.  | `execute-plan`, on starting  |
| `done`        | Implemented and verified; `completed:` is filled in. | `execute-plan`, on finishing |
| `blocked`     | Started, then stopped on something needing a human.  | `execute-plan`, on a blocker |
| `superseded`  | Replaced by a later plan; never to be executed.      | this skill                   |

Leave `completed:` empty at creation; `execute-plan` fills it with the date when it moves the plan to `done`.

Body structure:

- **Context** — which spec(s) this plan satisfies, and why now (new spec, changed spec, changed rule, or filling a
  coverage gap).
- **Current state** — what already exists in `./src/fastdi` relevant to this plan.
- **Rules applied** — each rule that constrained the design, and the specific decision it drove. Omit the section only
  when no rule bore on this plan at all. This is what stops a later reader (or `execute-plan`) from mistaking a
  rule-mandated detour for an arbitrary one and undoing it.
- **`./src/fastdi` changes** — concrete, file-by-file: what module to add/change, its public shape (classes,
  functions, signatures), and the behavior it must implement. Reference the spec section that requires each piece.
  Order this list so implementation can proceed top-to-bottom without hitting forward dependencies.
- **`./tests/` additions** — what new test files/cases to add under `./tests/` and what each one covers, per step 2's
  gap analysis. Name specific scenarios, not just "add tests for X."
- **Verification** — anything `execute-plan` needs to check _beyond_ its own standard `task fmt` / `task lint` /
  `task test` sequence (an example to run by hand, a specific scenario to eyeball). If there's nothing plan-specific,
  say "standard verification only" — don't restate the command list, so a Taskfile change doesn't strand old plans.
- **Deviations** — left empty ("none yet") for `execute-plan` to append to when the implementation has to diverge from
  what's written above.

Never overwrite or delete an existing plan file, and never edit one that's `in-progress` — that's `execute-plan`'s
working copy. If this plan supersedes an earlier `draft` or `blocked` one, say so in the new plan's text and set the
old plan's `status:` to `superseded`. If the plan you'd be superseding is `in-progress`, stop and ask the user first:
something may be mid-implementation against it.

Keep it scannable: a reader should be able to tell what's changing without reading every spec themselves.

## 4. Stop here

Do not modify `./src/fastdi`, `./tests/`, `./specs/`, or `./docs/rules/`. Do not invoke `execute-plan` yourself. Tell
the user the plan's path and a one-line summary of what it covers.
