# Rules

Each `./docs/rules/<slug>.md` is a binding constraint on the fastdi code an LLM writes under `./src` and `./tests`.
Rules capture the **how** — the implementation approach, idioms and invariants we insist on — for requirements that
have no public API surface to demonstrate.

## How a rule differs from everything else in this repo

| Artifact              | Answers                                     | Scope                                   |
| --------------------- | ------------------------------------------- | --------------------------------------- |
| `./specs/*`           | _What_ the public API is and how it behaves | The `fastdi` package's API surface      |
| `./docs/rules/*`      | _How_ that API must be implemented          | LLM-authored code in `./src`, `./tests` |
| `./docs/decisions/*`  | _Why_ we chose one option over others, once | The repo and its tooling                |
| `.apm/instructions/*` | How to work in this repo at all             | Everything, every agent                 |

## Precedence

A rule beats the workspace instructions, any APM skill (including `coding-standards`, `testing` and `tooling`), and any
other context the agent harness supplies. Where a rule is silent, those skills still apply as normal — rules exist to
override or sharpen the defaults, not to replace them.

Rules do **not** override a spec. Specs remain authoritative for the public API; if a rule would make a spec's required
API unimplementable, that is a conflict for a human to resolve, not something an agent may silently pick a side on.

## Authoring

Use the `create-rule` skill. `plan-implementation` and `execute-plan` read rules but must never edit them.
