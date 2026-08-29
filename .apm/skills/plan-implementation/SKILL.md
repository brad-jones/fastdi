---
name: plan-implementation
description: Read every spec under ./specs/ plus the current state of ./src/fastdi, and write a markdown implementation plan under ./docs/plans/ describing the diff needed to satisfy the specs. Use this after a spec has been created or changed and before writing any framework code. Writes a plan only — never edits ./src/fastdi or ./tests directly.
---

# plan-implementation

This skill turns the spec-driven source of truth (`./specs/*`) into a concrete, reviewable plan for changing
`./src/fastdi`. It produces a markdown document, nothing else. Actually writing the code is `execute-plan`'s job.

## 1. Gather the full picture

Read, in full:

- Every `./specs/<name>/README.md`, `main.py`, and test suite under `./specs/<name>/tests/`. The README is the
  authoritative description of behavior; `main.py` and the tests show it concretely — cross-check them against the
  README for drift (a spec that's been hand-edited inconsistently is a defect to flag in the plan, not silently
  resolve).
- The current contents of `./src/fastdi` (every module, however small).
- The current contents of `./tests/` (root framework-level suite), so the plan doesn't propose tests that already
  exist.
- Existing plans under `./docs/plans/` whose frontmatter isn't `status: done` — an in-flight plan for the same area
  should be updated/superseded, not duplicated.

## 2. Work out the diff

For each spec, determine what's missing or wrong in `./src/fastdi` for that spec's `main.py` and tests to pass:
new modules, classes, functions, or changes to existing ones. Note the dependency order across specs where one spec's
implementation is a prerequisite for another's (e.g. basic registration/resolution before scoped lifetimes).

Then look past the specs to `./src/fastdi`'s own internal correctness and coverage: identify unit-level behavior that
none of the specs exercise directly but that the implementation still needs to get right — error paths, boundary
conditions, invariants an internal helper must uphold. These become the additional tests you plan for `./tests/`
(spec suites cover the public API end-to-end; `./tests/` covers what they don't reach).

## 3. Write the plan

Create `./docs/plans/NNNN-<slug>.md`, numbered sequentially like the ADRs in `./docs/decisions/` (check the highest
existing number under `./docs/plans/` and increment). Frontmatter:

```markdown
---
status: draft
date: <today, YYYY-MM-DD>
specs: [<name>, <name>, ...]
---
```

Body structure:

- **Context** — which spec(s) this plan satisfies, and why now (new spec, changed spec, or filling a coverage gap).
- **`./src/fastdi` changes** — concrete, file-by-file: what module to add/change, its public shape (classes,
  functions, signatures), and the behavior it must implement. Reference the spec section that requires each piece.
  Order this list so implementation can proceed top-to-bottom without hitting forward dependencies.
- **`./tests/` additions** — what new test files/cases to add under `./tests/` and what each one covers, per step 2's
  gap analysis. Name specific scenarios, not just "add tests for X."
- **Verification** — the exact commands `execute-plan` should end on: `uv run pytest specs`, `uv run pytest tests`,
  `uv run ruff check .`, `uv run pyright`.

Keep it scannable: a reader should be able to tell what's changing without reading every spec themselves.

## 4. Stop here

Do not modify `./src/fastdi` or `./tests/`. Do not invoke `execute-plan` yourself. Tell the user the plan's path and a
one-line summary of what it covers.
