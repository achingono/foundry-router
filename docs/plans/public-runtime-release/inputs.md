# Public runtime release inputs

| Input | Source | Owner |
| --- | --- | --- |
| Public baseline | Existing remote main branch | Release preparer |
| Reviewed runtime and focused tests | Committed source objects | Runtime owner |
| Generic deployment guard | Reviewed workflow | Release preparer |
| Export plan | Independently reviewed before implementation | Separate reviewer |

Source objects are exported from committed files; unrelated working-tree edits are excluded. Environment-specific records are not publication inputs.
