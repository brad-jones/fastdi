---
status: accepted
date: 2026-07-03
decision-makers: Brad Jones
---

# Use SOPS with Age for secret management

## Context and Problem Statement

Projects need a way to manage secrets (API keys, tokens, credentials) that is simple, vendor-neutral, and keeps secrets
co-located with the code that uses them. Developers should not be blocked because they are unsure where secret values
are stored or how to access them.

## Decision Drivers

- Secrets should live alongside the code that consumes them, reducing confusion about where values are stored
- The solution must be vendor-neutral to avoid cloud-provider lock-in and slow login processes
- Onboarding new developers should require fetching at most one external secret
- The encryption workflow must be simple enough for daily use without ceremony

## Considered Options

- SOPS with Age encryption
- HashiCorp Vault
- Cloud-provider KMS (AWS KMS, GCP KMS, Azure Key Vault)
- Git-crypt

## Decision Outcome

Chosen option: "SOPS with Age encryption", because it keeps encrypted secrets in the repository next to the code that
uses them, requires no external infrastructure, and stays completely vendor-neutral. A single Age private key is the
only secret a new developer needs to obtain from an external source.

### Consequences

- Good, because secrets are versioned alongside code — diffs show when secrets change.
- Good, because no external service is required to decrypt; only the Age private key is needed.
- Good, because Age is fast, simple, and has no login flow or token expiry to manage.
- Good, because SOPS supports partial encryption, keeping file structure readable while values stay encrypted.
- Bad, because the private key must be shared out-of-band (e.g., via a team password manager like 1Password or
  LastPass).
- Bad, because key rotation requires re-encrypting all secrets and distributing a new key.

## More Information

The private key (`.sops.age.key`) should be shared via the team's existing password manager. That is the only secret a
new developer needs to fetch from an external system — once they have it, they can read all repo secrets.

SOPS supports multiple keys per file, so each developer could have their own Age keypair. The Age backend also supports
SSH keys, making a multi-key setup feasible. However, this repo intentionally keeps things simple with a single shared
key. More complex multi-key configurations are left as an exercise for the reader.

Wrapper script: [`scripts/sops.py`](../../scripts/sops.py) provides `get`, `set`, and `rm` convenience commands for a
simple key-value interface over the encrypted secrets file.
