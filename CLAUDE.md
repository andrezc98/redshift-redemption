# CLAUDE.md — Redshift Redemption (RA3 vs RG, medido)

## Verify every API against current docs, every task, every agent
Redshift RG is months old (launch 2026-05-12, rg.large/12xlarge 2026-07). Do NOT
rely on training memory for node types, Terraform provider arguments, Data API
fields, system-view columns or prices. Before writing or changing any code or
config: official docs / Terraform registry / GitHub releases of the day, pin
what you verify, cite it in README. Every dispatched subagent gets this
instruction verbatim.

## AWS is the Morris Labs POC account only (since 2026-10-05)
The default credentials on this machine belong to a client. Every script that
touches AWS calls `require_sandbox()` first (AWS_PROFILE must contain
"sandbox" or be in `LAB_PROFILES`; the lab profile is `morrislabs-poc` (SSO),
region pinned to us-east-1). Terraform for `infra/` runs only through the
manually dispatched `.github/workflows/infra.yml` (OIDC role `rr-gha` from
`infra/bootstrap/`); dispatching apply/destroy needs the speaker's go, like
restoring snapshots, resizing clusters or starting a benchmark scenario.
Clusters are PAUSED or DELETED between lab sessions; verify with
`aws redshift describe-clusters` before leaving them unattended. The runner
never runs terraform.

## Budget
Core lab estimate: USD 40–45 at 100 GB (spec §6). An AWS Budget alert at USD 80 exists
before the first `apply`. `results/prices.md` is the only price source; fill it
from the Price List API on the lab day.

## Language
Code, tests, commits: English. Everything the audience sees (slides, README,
result comments): neutral Spanish, no voseo.

## Deliverable boundary
Spec: `docs/superpowers/specs/2026-09-24-redshift-redemption-design.md`.
Plan: `docs/superpowers/plans/2026-09-24-redshift-redemption.md`.
The speaker owns the official Google Slides template; we hand over
`slides/contenido.md` and image assets only.

## Framing rule
Verify, don't attack: AWS claims are promises we test (where they hold, where
they depend on the workload), never "marketing vs truth". No Snowflake numbers
of our own, ever. AWS's "4.2x vs other warehouses" claim is out of scope.

## Sibling repos (read-only precedents, do not modify)
- `../kcd/kcd-argentina-2026-brainstorm-recap.md` §12: the submitted abstract
  and the original lab spec. Its "no third-party RG benchmarks" line is
  outdated (tombola 2026-06-22, Southwest); never repeat it on a slide.
- `../armed-and-dangerous/`: runner/test/results conventions.
- `../rompe-tu-agente/`: `require_sandbox()` and `demo/sanitize-check.sh`,
  copied verbatim.

## Sanitization
No account IDs, sensitive ARNs, cluster endpoints or credentials in anything
committed. Run `demo/sanitize-check.sh` before committing any result; it must
print `sanitize-check: clean`.
