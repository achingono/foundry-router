# Isolated Ingress Watchdog Activities

## Step-By-Step Activities

1. Freeze the rejected continuation packet. Do not add approval, dispatch case 3, patch ingress, restart, or reuse its evidence as approval for a different topology.
2. Treat the independent gateway with a local expiring lease as the design candidate. Reject runner `finally`, shell traps, timer jobs, and ARM polling as sole fail-closed controls.
3. Independently validate the cloud ingress boundary: dedicated private ACA environment, VNet route reachability, gateway ingress restriction, direct-origin isolation, and TLS/SSE/cancellation behavior. Do not substitute a shared environment based on bypass testing.
4. Threat-model runner death, delayed/replayed renewals, clock uncertainty, VM/gateway failure, lease replay, concurrent closure/dispatch, ARM outage, network partition, retries/failover, and in-flight paid request ambiguity. Specify safe outcomes and evidence for each.
5. Produce a complete cost/operations/network delta and exact trust/permission matrix. Gateway receives no Azure resource write role; runner/supervisor cannot exec, resolve app/provider secrets, mutate infrastructure, or directly call the provider. Independently operated evidence and restart workflows must be feasible without granting those capabilities to the runner.
6. Obtain an independent design review. Resolve all Critical/Major findings before implementation planning.
7. The operator has approved implementation, Azure validation/deployment, and execution stages in principle. Prepare and independently review the exact implementation, disposable-environment infrastructure, and execution packets; stage approval does not replace those gates.
8. After any implementation, require focused fault-injection tests, security review, Azure ingress verification, and an exact new four-case G1 packet and separately approved aggregate budget before paid acceptance. Bind each case to one durable dispatch, zero retries/failover, and independent settlement/continuity; require distinct pre- and post-restart DENY evidence.

## Review Focus

- Does access to the ACA origin become impossible from the executor except through the gateway?
- Can ACA ingress logs distinguish the configured ingress denial from an application-generated 403, with request correlation and complete diagnostics?
- Does the proxy itself enforce monotonic lease expiry on every request and fail closed after restart?
- Can runner death leave forwarding enabled beyond the explicitly approved TTL?
- Can an in-flight renewal or blocked ledger insert reopen or start forwarding after closure/expiry?
- Do runner identity and egress controls prevent exec, secret, and direct-provider bypass while independently preserving G1 diagnostics?
- Do four new, ordered, single-attempt cases fit the approved aggregate budget and preserve exact financial continuity?
- Is the sole-writer baseline freshly rechecked immediately before every case, after slot consumption and with no intervening remote operation or wait before forwarding?
- Are active streams and already-dispatched provider requests treated as ambiguous rather than retried?
- Can the gateway alter app config, table state, credits, model settings, or production resources?
- Does an Azure control-plane outage become a clear blocked state, not false success?
- Are cost, gateway endpoint lifecycle, dedicated-environment networking, and operational ownership acceptable?
