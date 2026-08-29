---
status: accepted
date: 2026-06-01
---

# Use cocogitto for conventional commits and automated releases

## Context and Problem Statement

We follow the Conventional Commits standard and need tooling to enforce commit message format, determine semantic
version bumps automatically, and generate changelogs. What tool should we standardise on for this release workflow?

## Considered Options

- [cocogitto](https://github.com/cocogitto/cocogitto)
- [release-please](https://github.com/googleapis/release-please)
- [semantic-release](https://github.com/semantic-release/semantic-release)

## Decision Outcome

Chosen option: "cocogitto", because it is a self-contained binary that is language-agnostic and does not rely on pull
requests or a Node.js runtime to perform releases — meeting our simplicity and portability decision drivers.

### Consequences

- Good, because cocogitto ships as a single binary with no runtime dependencies, making it easy to install via pixi.
- Good, because releases are performed directly from the CLI rather than through a PR-based workflow, reducing friction.
- Good, because changelog generation and version bumping are driven purely from the local commit history.
- Bad, because cocogitto is less widely known than semantic-release, so new contributors may need to learn it.
