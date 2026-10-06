# Settings identity risks

| Risk | Control |
| --- | --- |
| Retain old configuration secrets longer | One existing Settings reference only; replaced on successful sync/reset, no logs/serialization |
| In-place same-object edits still skipped | Preserve existing singleton immutability expectation; membership comparison unchanged; in-place reload not introduced |
| Failed merge falsely advances cache | Assign only on complete success as before |
