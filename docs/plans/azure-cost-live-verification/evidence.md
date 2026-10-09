# Cost live Evidence

Local provider verified at `47fd4b9`. Read-only live acceptance attempted below.

The fixed verifier reads the gitignored operator mapping, discovers actual account IDs with
two bounded CLI subprocesses, then performs one isolated provider refresh. Account names
come from the operator mapping; safe credit-group labels are separate. It never applies
ceilings or changes deployments/roles. Thirteen focused tests passed, covering mismatched
membership, invalid policy, independent account names, clamped ceiling labels and subprocess
cap/timeout cleanup. Independent contextual review cleared all Critical/Major findings after
correcting the account-name assumption. Ruff lint/format and strict mypy passed. A full-suite
attempt encountered a sandbox restriction binding the local OTLP receiver; the approved rerun
passed: 1,842 tests, 3 skipped, 18 deselected, 89.73% coverage. No Docker rebuild is required
for this read-only script; runtime is unchanged. SonarQube script is absent.

## Read-only live attempt

Verifier implementation committed as `56d1fa1`. The authorized single invocation completed
in 5.27 seconds with unverified result (local-only `results.json`), no accepted group ceilings and
`balance_applied: false`. Its deliberately redacted category combines metadata, identity and
billing unavailability; the saved result cannot establish the failing boundary or permission
cause. No repeated billing refresh was dispatched. The live scope/permission/query acceptance
gate remains open. No deployment, role or router estimate was changed.

## Diagnostic preparation

Independent amendment review cleared one additional bounded refresh, with fixed redacted
failure categories and an immutable started/result pair. The runner refuses replay after
interruption. Original results remain untouched. Twenty diagnostic/acceptance tests passed;
Ruff lint/format and strict mypy passed. Independent contextual implementation review found
no Critical/Major issues. Fresh metadata preflight passed for both groups without billing calls.
Full suite: 1,867 passed, 3 skipped, 18 deselected; coverage 89.73%. Runtime/image are unchanged.

## Single diagnostic refresh

Implementation committed as `1f135cd`. Diagnostic result (local-only `diagnostic-results.json`) records
the provider boundary and fixed `schema` rejection category after 4.101 seconds, with no
accepted ceilings and no balance application. Started marker (local-only `diagnostic-started.json`)
prevents repeat execution. The original result remains unchanged. This narrows the observed
failure to provider response validation; it does not identify a particular invalid column,
row, currency or completeness condition. Permission status remains unverified, and validation
was not loosened. Any further response-shape diagnosis needs its own reviewed finite scope.
