# History cleanup risk-register

## Risks
| Risk | Mitigation |
| --- | --- |
| Commit hashes and signatures change | Record filter mapping locally; disclose to user. |
| Remote history retains old content | No remote write; disclose need for coordinated update. |
| Lost local originals or pending changes | Hash verification and ignored recovery bundle before rewrite. |
| Recovery bundle contains old sensitive history | Keep ignored/private and never publish. |
