# Table write metadata exit criteria

- Passed: independent review, exact metadata boundary, ETag/no-mutation regressions,
  actual SDK wire check, strict Azurite settlement/recovery, full coverage >=80%,
  lint/format/types, Docker runtime imports and contextual review.
- Open: cloud synthetic write acceptance and corrected isolated inference/settlement.
- Preserved: old failed/ambiguous request ledger; no replay or balance reset.
