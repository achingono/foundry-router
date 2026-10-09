# Signature text Risks

| Risk | Mitigation |
| --- | --- |
| Lost reasoning continuity | Explicitstatelesstextonly,tools/continuationreject |
| Unrecognized provider output silentlylost | Exactwrapper/type/sizeonly,unknownreject |
| Genericproviderloosening | Identitydefaulthooks,Googlespecializationtests |
| Budgetreset/ambiguousretry | Newbaseline/sameledgerlock,phasecasesanddurablehalts |
