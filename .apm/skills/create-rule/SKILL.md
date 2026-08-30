---
name: create-rule
description: Write or refine a markdown rule under ./docs/rules from a short English description of a constraint on how FastDI's code should be written. Use this whenever asked to add, draft, tighten or amend a rule, or to record a requirement about the "how" of ./src/fastdi and ./tests that has no public API surface to demo in a spec. Never touches ./specs, ./src/fastdi or ./tests.
---

# create-rule

FastDI is built spec-first: `./specs/*` describes _what_ the public API is. Rules under `./docs/rules/` describe _how_
that API must be implemented — the idioms, invariants and approaches we insist on for requirements with no public API
surface to demonstrate. `plan-implementation` reads every rule alongside every spec, and `execute-plan` implements
under both. This skill's only job is producing (or refining) a rule file. It must never write or edit anything under
`./specs`, `./src/fastdi`, or `./tests`.

Rules are binding. A rule takes precedence over the workspace instructions, over any APM-supplied skill (including
`coding-standards`, `testing` and `tooling`), and over any other ambient context. Where a rule is silent those skills
still apply — a rule exists to override or sharpen a default, not to restate it. A rule never overrides a spec: specs
own the public API, and a rule that would make a specified API unimplementable is a conflict for the user to resolve.

That authority is exactly why the bar for writing one is high. Work through step 2 before creating a file.

## 1. Understand the request

Read the constraint the user described. If it's vague on something that changes what the rule actually forbids or
requires (`"avoid reflection"` — all reflection, or only in the resolution hot path? `"keep modules small"` — by what
measure, and what happens when one isn't?), ask. A rule nobody can apply consistently is worse than no rule: it gets
interpreted differently on every run, and the inconsistency looks like a bug in the framework.

If a rule for this constraint already exists under `./docs/rules/`, treat the request as a refinement — read that file
and edit it in place rather than adding a near-duplicate. See step 5.

## 2. Triage: is this actually a rule?

`./docs/rules/` is one of four places a requirement can live in this repo, and putting one in the wrong place is the
most common failure here. Check each of these before writing anything, and redirect rather than proceeding:

- **Does it have a public API surface a user would call?** Then it's a spec, not a rule — the "what", not the "how".
  "Registrations should support an async factory" is a spec. Redirect to `create-spec`. If the request is a mix
  (a new API _and_ a constraint on building it), split it: propose the spec to `create-spec` and keep only the
  constraint here.
- **Does it govern anything outside `./src/fastdi` and `./tests`?** Repo tooling, git workflow, `pixi`, `task`, CI,
  commit messages, how to run things — that's ambient workspace guidance and belongs in
  `.apm/instructions/*.instructions.md`, where it reaches every agent in every directory. Rules are scoped to the
  framework code and its tests on purpose; widening them dilutes them.
- **Is it a one-time choice between weighed alternatives?** "Use `dataclasses` over `attrs`", "target 3.14+" — that's a
  decision with context and consequences. Use the `adr` skill and write it to `./docs/decisions/`. A rule may _cite_ an
  ADR as its rationale, but the two aren't interchangeable: an ADR records why we chose something once, a rule binds
  every future change.
- **Does an APM skill already say this?** `coding-standards`, `testing` and `tooling` are already in force. Restating
  one of them as a rule adds maintenance and buries the rules that actually matter. Only write the rule if it
  **overrides** that guidance (we deliberately do the opposite here) or **sharpens** it into something specific and
  checkable (the skill says "prefer composition"; the rule says exactly which seam in the container must stay
  composable and why). If it does neither, say so and write nothing.
- **Is it objectively checkable?** A reviewer — human or LLM — has to be able to look at a diff and say yes or no
  without a judgement call. "Write clean code", "be performant", "keep it simple" are not rules; they're vibes, and
  they'll be cited to justify contradictory changes. Push for the falsifiable version: what specifically must be true,
  or must never appear, in the code?
- **Does it conflict with an existing rule?** Two rules that pull in opposite directions will deadlock
  `plan-implementation`, which has no authority to pick between them. Resolve it by editing the existing rule so the
  two are consistent, and tell the user what you changed — don't add a second rule and leave the contradiction for a
  later run to hit.
- **Would it make an existing spec unimplementable?** Read the specs it touches before writing. If the rule forbids the
  only way to deliver something a spec requires, stop and tell the user, naming the spec and the requirement. Either
  the rule needs narrowing or the spec needs another `create-spec` pass — that's the user's call, not yours.

## 3. Write the rule file

One rule per file, at `./docs/rules/<slug>.md`. The slug is kebab-case and names the constraint itself, so the
directory listing reads as a list of rules: `no-import-time-side-effects.md`, `resolution-path-allocates-nothing.md`.
Not numbered — rules are living constraints cited by name, unlike `./docs/decisions` and `./docs/plans`, which are
dated history.

Frontmatter:

```markdown
---
description: <one line: what this forbids or requires, in plain terms>
  applies-to: [<paths>]
---
```

`applies-to:` is optional and defaults to all of `./src/fastdi` and `./tests`. Include it only to _narrow_ the scope
(`applies-to: [src/fastdi]` for something that shouldn't constrain test code), never to widen it beyond those two
trees — that's what `.apm/instructions/` is for.

Body, in this order:

- **`# <Title>`** — the rule as a short imperative sentence. A reader who only sees the heading should already know
  what to do.
- **Rule** — one or two sentences stating precisely what must or must not happen. This is the normative text; every
  other section is context. Write it so a diff can be checked against it.
- **Why** — the rationale. This is what lets a future reader (or `plan-implementation`) tell whether an unforeseen
  situation falls inside the rule's intent or outside it, so don't skip it even when the reason feels obvious.
- **Scope** — where it applies, and — just as importantly — what it deliberately doesn't cover, so nobody stretches it
  into territory it was never meant to govern.
- **Overrides** — name the guidance this supersedes (a specific `coding-standards`/`testing`/`tooling` rule, a
  workspace instruction), or say "nothing — sharpens the default" when it only makes existing guidance concrete.
  Without this, an agent hitting the conflict has to guess which wins.
- **Examples** — a compliant and a non-compliant snippet, when code makes it clearer than prose. Keep them minimal and
  drawn from FastDI's own domain. Omit the section entirely if the rule is plain enough without it; a padded example is
  worse than none.
- **Exceptions** — the circumstances under which the rule may be broken, and what the implementer must do about it
  (typically: note it in the plan's **Deviations** section). If there are none, say "none" explicitly — an absent
  section reads as an oversight, and someone will assume they've found a gap.

Keep the whole file short. A rule that runs to several pages is either several rules, or an ADR wearing a rule's
clothes.

## 4. Don't write the enforcement

State the constraint; don't specify how `./src/fastdi` should be structured to satisfy it, and don't sketch the code.
That's `plan-implementation`'s job, and pre-empting it in a rule freezes one particular design into a document meant to
outlive every design. If you find yourself describing modules and signatures, you've written a plan — cut it back to
the constraint.

## 5. Make it re-runnable

This skill is invoked repeatedly on the same rule as it's refined. When `./docs/rules/<slug>.md` already exists, treat
the invocation as "update this rule," editing it in place and preserving refinements that are still valid. If a
refinement materially changes what the rule permits, mention it to the user when you hand back: code already written
under the old wording may no longer comply, and that's a `plan-implementation` run they may want to schedule.

## 6. Verify

From the repo root:

1. `task fmt` — formats the markdown.
2. `task lint` — must be clean before you hand back.

Nothing else. A rule is not a `uv` workspace member, so there's no `uv sync`. Don't run `task test`: a new rule can't
make a passing suite fail on its own, and if it means existing code is now non-compliant, that's a
`plan-implementation` and `execute-plan` cycle, not a test failure to chase here.

## 7. Review the rule as a whole

Before handing back, check:

- Does step 2 still hold — is this genuinely a rule, rather than a spec, an ADR or a workspace instruction that ended
  up here because it was easier?
- Could a reviewer look at a diff and decide compliance without a judgement call?
- Does it override or sharpen existing guidance, rather than restating it?
- Is it consistent with every other file in `./docs/rules/` and implementable alongside every spec?

Iterate with the user until yes to all four.

## 8. Stop here

Do not write or modify anything under `./specs`, `./src/fastdi`, or `./tests`. Do not run `plan-implementation` or
`execute-plan` yourself. Tell the user which rule was created or updated, what it constrains, and — if step 2 surfaced
a redirect, an overlap with an existing rule, or a tension with a spec — what you flagged and how it was resolved.
