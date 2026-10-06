# Signed continuation exit criteria

- [x] Independent design/API decision review before runtime edits.
- [x] Local canonical bounded authenticated encryption; exact scope/config/backend/history binding.
- [x] Synthetic missing/dropped/malformed state fails before reservation even with healthy alternatives.
- [x] Synthetic native ordered text/call Part signatures retained without merging or caller reconstruction.
- [x] Actual OpenAI2.8.1 synthetic HTTP nonstream/stream/tool replay retains extension with reviewed helper serializer.
- [x] Synthetic HTTP expiry/key overlap/revocation/client rotation/config change and fresh runtime-object replay pass.
- [x] Actual fresh-process restart replay passes on local3.14 and Linux3.12; container/TCP restart unverified.
- [x] Synthetic pinned unavailable backends preserve429/503; no project/provider/surface failover.
- [ ] Repeated valid requests authenticate/reserve/settle independently; cancellation/redaction pass.
- [ ] Maximum-state resource, coverage>=80%, full checks/Docker/deep review/docs pass.
- [ ] Exact operator model/native signature/live usage evidence passes before profile enablement.
