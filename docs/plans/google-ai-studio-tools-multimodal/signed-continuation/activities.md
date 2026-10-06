# Signed continuation activities

1. Independently review [design](design.md) and the extension API decision before runtime edits.
2. Implement secret configuration/readiness and nonpublic caller scope; preserve unrelated auth.
3. Implement bounded canonical history projection and Fernet envelope codec with rotation/bindings.
4. Prepare owned immutable continuation facts at API intake; enforce pool history policy and pin
   candidate routing before reservations, including otherwise healthy unsigned alternatives.
5. Implement native exact Part association and ordered replay; native nonstream upstream for signed public streaming; final item extensions
   appear only after complete valid provider turn/usage. No complete calls with missing required state.
6. Exercise exact client nonstream/stream/replay plus tampering/caller/config/rotation/restart/expiry,
   redaction, cancellation, repeated independent billing and pinned-backend failure cases.
7. Measure bounded maximum-state work, run full quality/Docker/deep review and update canonical docs.
8. Run bounded live exact-model cases only when model configuration is supplied and local gates pass.
