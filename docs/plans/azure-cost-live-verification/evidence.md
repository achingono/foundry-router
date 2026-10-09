# Cost live Evidence

Local provider verified at `47fd4b9`. Read-only live acceptance not yet executed.

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
