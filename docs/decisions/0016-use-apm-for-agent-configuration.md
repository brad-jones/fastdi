---
status: accepted
date: 2026-08-29
---

# Use apm to manage AI agent configuration across providers

## Context and Problem Statement

[ADR-0006](0006-use-xcaffold-for-agent-configuration.md) adopted xcaffold to compile a single source tree of agent
configuration into provider-specific output directories. Since then,
[Microsoft's Agent Package Manager (apm)](https://microsoft.github.io/apm/) has emerged and gained industry traction as
a package manager for agent harness configuration — not just a compiler. How should we manage our AI agent configuration
going forward?

## Considered Options

- apm — a package manager for agent harness configuration (`apm.yml`, `apm.lock.yaml`) that compiles a shared `.apm/`
  source tree into provider-specific output directories, and can install shareable packages of skills, instructions, and
  agents from a registry
- xcaffold — a deterministic agent configuration compiler that compiles a shared `xcaf/` source tree into
  provider-specific output directories, with no package management or registry capability
- Maintain per-provider configuration files manually (e.g. `.claude/`, `.github/copilot-instructions.md`, `.gemini/`)

## Decision Outcome

Chosen option: "apm", because it does everything xcaffold did (compiling a single source tree to provider-specific
output) while also functioning as a true package manager — letting us pull in and share reusable skills, instructions,
and agents (see `apm_modules/`) rather than only compiling our own local source tree. This aligns with where the
industry is heading for agent harness tooling.

### Consequences

- Good, because agent skills, rules, and context are still defined once (now in `.apm/`) and applied consistently across
  all providers.
- Good, because we can install and share reusable agent configuration packages via `apm_modules/` instead of
  hand-authoring or copy-pasting everything ourselves.
- Good, because adopting a new agent provider still requires only running `apm install` / `apm compile` rather than
  manually authoring new configuration files.
- Bad, because apm is an additional tool in the chain that contributors need to understand and run when changing agent
  configuration.
- Bad, because provider-specific output directories (`.claude/`, `.cursor/`, `AGENTS.md`, etc.) must not be edited
  directly, which may be unintuitive for contributors unfamiliar with the workflow.
- Neutral, because xcaffold's compilation model is still preferred in isolation; if xcaffold gains package management /
  registry capabilities in the future, we may revisit this decision.
