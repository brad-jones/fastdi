---
description: task lint must report zero warnings as well as zero errors; an unavoidable one needs an approved spec
  change or a justified inline suppression.
---

# Lint Must Report Zero Warnings, Not Just Exit Zero

## Rule

`task lint`'s combined output must show zero warnings, not only zero errors, for every file a plan touches. A run that
exits `0` while reporting `0 errors, N warnings` is not clean. A warning that can only be removed by changing a spec's
documented public API, or by suppressing it inline, is not resolved by leaving it in place — it must go through one of
the two paths in **Exceptions**.

## Why

`task lint`'s own exit code doesn't fail on a pyright warning, so a warning left in place is invisible to every check
except a human actually reading the output — exactly the kind of thing that accumulates silently across many
`execute-plan` runs. Most warnings point at a real design smell (a `TypeVar` that binds nothing, a type wider or
narrower than intended); requiring them to be resolved, not merely noted, keeps that debt from building up. Routing an
unavoidable one through the user before touching a spec keeps `./specs` — the framework's single source of truth for
its public API — from drifting by fiat during an unattended run.

## Scope

Applies to `./src/fastdi` and `./tests` (the default): every file `execute-plan` writes or edits. This rule governs
whether a lint run counts as clean, not the linter configuration itself — it doesn't require making `Taskfile.yaml`'s
`lint` task fail its own exit code on a warning. Compliance is a manual read of `task lint`'s output, the same way
`public-api-requires-docstrings` is manually reviewed rather than linted for.

## Overrides

Sharpens `execute-plan`'s own verification bar, which currently treats `task lint`'s exit code alone as sufficient for
"clean." It also carves a narrow, explicitly-approved exception into `execute-plan`'s and `plan-implementation`'s
standing rule against ever touching `./specs`: normally a spec problem is reported and left for the user to run
`create-spec` themselves, but here the spec change is small enough (the fix for a lint warning, nothing else) that this
rule permits doing it inline, gated on live approval in the same conversation. It grants no broader license to edit
specs, and doesn't touch `create-spec`'s status as the only route to authoring a spec from scratch.

## Examples

Non-compliant — the warning is implemented faithfully and only noted in the plan's Deviations, without ever asking
whether the spec itself could change:

```python
@overload
def add_singleton[T](self, instance: T, /) -> Self: ...
```

`pyright` reports: `warning: TypeVar "T" appears only once in generic function signature (reportInvalidTypeVarUse)`.

Compliant — after presenting this exact diff to the user and receiving approval, `specs/singleton-scope/README.md` and
every plan quoting the old signature are updated to match, and the implementation follows:

```python
@overload
def add_singleton(self, instance: object, /) -> Self: ...
```

## Exceptions

1. **Spec-caused warning.** When the only fix is a change to a spec's documented public API: stop, show the user the
   smallest spec diff that removes the warning and the warning text it removes, and proceed only once they approve it
   in that same conversation. Update every `./docs/plans/*.md` that quotes the old signature to match, so the plan and
   the spec never disagree about what was implemented. This covers only the text causing the warning — not a license
   to revise the rest of that spec, or any other, while there.
2. **Inline suppression.** Permitted only when neither a code change nor a spec change removes the warning — the
   warning is intrinsic to what the tool or the language can express, not a stylistic tradeoff that was easier to
   suppress. Record the tool's exact warning text and why no alternative exists in the plan's Deviations section, next
   to the suppression.

No other way of leaving a warning in place is compliant — not a Deviations note alone, not silence.
