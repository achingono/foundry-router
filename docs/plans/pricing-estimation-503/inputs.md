# Pricing-estimation 503 inputs

Status: Planned. User requests investigation and resolution of production Terra High failures from ChatGPT Desktop.

- Live production pricing for gpt-6.1-terra is USD/M 2.5 input, 0.1 cached input, 7.5 output; readiness passes. Bounded logs show successful and rejected Terra requests in the same process with healthy candidates. Exact supplied request ID was outside the retained sample; no request bodies are logged.
- Reproduction: synthetic 2,010,078-byte Responses body is below default 2,097,152-byte intake but estimate_request_cost returns None due to independent 2,000,000-character/serialized-byte bounds. Tools force serialization and may amplify wire length with inserted whitespace.
- Owning code: credit.py and routing/__init__.py; request intake common.py and bounded JSON parser. Existing tests: test_credit.py and test_main.py.
- Production is memory/one, current deployed image verified read-only; restart requires fresh drained account seeds. Other untracked responses-request-limit plan is independent and remains untouched.
