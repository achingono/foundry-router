# Table write metadata exit criteria

- Passed: independent review, exact metadata boundary, ETag/no-mutation regressions,
  actual SDK wire check, strict Azurite settlement/recovery, full coverage >=80%,
  lint/format/types, Docker runtime imports and contextual review.
- Passed: corrected isolated image binding and both fresh live streaming settlement cases.
- Open: direct synthetic probe (exec transport 404), original nonstream/restart acceptance.
- Preserved: old failed/ambiguous request ledger; no replay or balance reset.
