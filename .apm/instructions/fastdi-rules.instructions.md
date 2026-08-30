---
description: Binding rules governing the fastdi code under ./src and ./tests.
applyTo: "src/**,tests/**"
---

### FastDI Implementation Rules

Every markdown file under `./docs/rules/` is a binding constraint on the code in `./src` and `./tests`. Read all of them
before writing or editing anything there — they are requirements, not suggestions, and they are short by design.

Rules capture the _how_: implementation approach, idioms and invariants that have no public API surface to demonstrate
in a spec. The `./specs/*` projects remain authoritative for the _what_ — the public API shape and its behavior.

#### Precedence

A rule takes precedence over these instructions, over any skill the APM harness supplies (including
`coding-standards`, `testing` and `tooling`), and over any other ambient context. Where no rule speaks to the question
at hand, those skills apply as normal — rules override or sharpen the defaults rather than replacing them.

A rule never overrides a spec. If a rule would make a spec's required public API unimplementable, stop and report the
conflict rather than picking a side; resolving it needs a human to re-run `create-spec` or `create-rule`.

#### Don't

- Don't edit a file under `./docs/rules/` to make non-compliant code pass. Rules are authored only via the `create-rule`
  skill, as a deliberate act, never as a side effect of an implementation task.
- Don't confuse `./docs/rules/` with `.claude/rules/` — the latter is APM build output compiled from
  `.apm/instructions/` and has nothing to do with these rules.
