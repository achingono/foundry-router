# Codex Project Agents

## Status: Implemented (definitions installed; runtime launch unverified)

The installed [agent definitions](../../.codex/agents/) implement
[AGENTS.md](../../AGENTS.md)'s handoffs as agent instructions. All six reviewed definitions
are installed under `.codex/agents/`. The requested
`.codes/agents/coder.toml` is interpreted as `.codex/agents/coder.toml`.

| Role | Responsibility | Handoff |
| --- | --- | --- |
| planner | Delegate direct plan authoring to OpenCode Muse Spark | Independent plan review |
| reviewer | Approve plan in an independent session; contextual review after checks | Verdict and actionable findings |
| coder | Compatibility alias for developer OpenCode build delegation | Candidate plus focused results |
| verifier | Full applicable checks, 80% code coverage, lint/format/types, conditional Docker/SonarQube | Actual results and missing gates |
| orchestrator | Sequence handoffs, remediation and evidence; enforce one writer by coordination | Final exit-criteria report |
| developer | Delegate approved implementation/tests/docs to OpenCode Muse Spark | Candidate plus focused results |

## Model Assignments

Assignments checked against the local Codex catalog and [official model guidance](https://developers.openai.com/codex/models) on October 12, 2026.

| Agent | Model | Reasoning effort | Rationale |
| --- | --- | --- | --- |
| planner | Sol wrapper → `opencode/muse-spark-1.3` | Sol low; no Muse variant pinned | Muse writes plan documents through foundry-planner |
| developer / coder | Sol wrapper → `opencode/muse-spark-1.3` | Sol low; no Muse variant pinned | Muse implements approved scope through build |
| orchestrator | `gpt-6.1-sol` | medium | Multi-step coordination and gate decisions |
| reviewer | `gpt-6-astra` | low | Reserve frontier capability for concurrency, credit integrity and trust-boundary review |
| verifier | `gpt-6-luna` | high | Lower-cost execution of defined checks and evidence capture |

Sol low settings coordinate CLI calls; Sol medium coordinates the full workflow. Muse
uses its configured provider defaults; no unsupported reasoning flag is invented.
OpenCode model listing confirms selection only, not successful inference or free pricing.
The Codex credit table below applies to wrapper/reviewer/verifier usage, not Muse billing.

The remaining Codex effort settings follow [custom-agent guidance](https://developers.openai.com/codex/multi-agent): Luna high and Astra low are recommended starting points. Sol medium balances coordination cost and depth. These are workload judgments, not measured repository benchmarks.

[Standard Codex credit rates](https://developers.openai.com/codex/pricing#token-rates) per million tokens, checked October 12, 2026:

| Model | Input | Cached input | Output |
| --- | --- | --- | --- |
| GPT-6.1 Sol | 50 | 2.5 | 250 |
| GPT-6 Astra | 250 | 25 | 1,250 |
| GPT-6 Luna | 2.5 | 0.25 | 12.5 |

Astra's uncached input/output rates are 5× Sol's; Luna's are 1/20th. Actual cost depends on token use, reasoning and inherited speed tier. Fast/Ultrafast can increase purchased-credit rates. These credit rates do not predict included subscription allowances; API-key billing follows separate API pricing. Catalog listing does not establish successful inference or provider entitlement.

See [model assignment evidence](../plans/codex-agent-models/evidence.md). Model overrides are fixed in role files; revisit them if availability or pricing changes.

## OpenCode Delegation

OpenCode v2.0.26 is installed. Its local `run --help` is authoritative when website
flags differ. [Planner](../../.codex/agents/planner.toml) uses the project
[foundry-planner](../../.opencode/agents/foundry-planner.md) OpenCode primary agent.
Muse reads blank templates and writes completed plans directly under the assigned
`docs/plans/<task>/` folder. Sol does not persist a returned text plan on Muse's behalf.

The custom agent configures deny-default tools, read/search access, and edits under
`docs/plans/**`; shell/subagent/browser access is denied. The task restricts writes
further to its assigned folder, checked through the resulting diff. `opencode debug
agents` confirms the agent/model/permission configuration loads. Actual Muse edits and
runtime permission enforcement remain unverified. If permissions do not match a path,
report the blocker rather than switching planning to unrestricted build mode.

Use the repository root as execution workdir. Set `task_file` to an absolute temporary
Markdown file with the task, AGENTS.md obligations, relevant references, assigned plan
folder or independently approved plan/verdict paths, ownership and acceptance criteria;
set `task_title` to a short nonsecret title. Quote arguments as shown:

```bash
opencode run --standalone --model opencode/muse-spark-1.3 --agent foundry-planner --format json --file "$task_file" --title "$task_title" "Write the plan documents directly in the assigned docs/plans folder; return file paths and unresolved decisions."
opencode run --standalone --model opencode/muse-spark-1.3 --agent build --format json --file "$task_file" --title "$task_title" "Implement only the attached independently approved scope with tests and documentation; report actual results."
```

Developer is the preferred build delegate; coder has identical delegation obligations.
Only one OpenCode build writer runs at a time. Neither wrapper implements the same
scope concurrently under Sol. Omit `--auto`; do not add unsupported v2.0.26 `--dir` or
`--variant` flags. Workdir selects the repository, and `--standalone` uses a private
server. Fresh tasks omit continuation/server flags. Scoped remediation may explicitly
resume a recorded `--session` after termination and approval/ownership revalidation.

Capture JSON/stdout/stderr locally and check error events, process exit and actual files;
exit zero alone does not prove success. Confirm process termination before retry or
writer handoff after failures/hangs. No silent model substitution or auto-restart.
Minimize nonsecret task context and commit only redacted evidence. OpenCode can retain
session/tool content in its own local data even when capture files are temporary.
Independent review and verification remain separate from Muse's claimed success.

See [OpenCode workflow evidence](../plans/opencode-workflow-agents/evidence.md).

## Invocation

Start a fresh Codex session in this repository and request:

> Use the orchestrator agent to implement <concrete scope> through the AGENTS.md workflow.
> Delegate plan authoring to planner through OpenCode, a fresh reviewer for plan approval,
> developer through OpenCode for coding, verifier, and a fresh
> reviewer for final deep review. Record evidence and resolve required findings.

The installed Codex CLI 0.162.1 loader supports discovered role TOML files with nonempty
`name`, `description`, and `developer_instructions`. Each definition sets `model` and `model_reasoning_effort` explicitly. Permission and
speed/service-tier settings continue to inherit from the invoking session. No permission
bypass, feature flag or duplicate registration is supplied. Actual discovery and launch
remain unverified; local prompt inspection did not expose a role roster, and TOML
parsing alone does not establish runtime use.
If the runtime cannot select named roles, supply the corresponding instructions and
assigned model/effort to separate subagent sessions where delegation tools support them.
If model overrides are unavailable, disclose that fallback sessions use inherited settings.

Role files provide instructions; they do not automatically launch agents or mechanically
block implementation. The coordinator must wait for each dependent gate and record
verdicts. Use a reviewer session that did not author the reviewed plan or code. Material
plan amendments need independent approval; fixes need affected checks and independent
re-review of Critical/Major findings. Keep one source/test writer; evidence updates must
also have explicit ownership. The verifier reports failures rather than patching code.

Missing required tools or unavailable scans remain outstanding gates. An absent
SonarQube script is recorded as not applicable, never a scan pass. Pure configuration
and documentation changes can justify runtime-test/coverage/Docker exclusions in their
plan evidence. Live Azure/provider tests require explicit scope; local verification uses
mocks/emulators. Production remains memory-backed with one replica until remaining gates
pass. No deployment or live acceptance follows from agent installation.

See [plan and evidence](../plans/codex-workflow-agents/evidence.md) and
[testing](testing.md) for exact validation scope.
