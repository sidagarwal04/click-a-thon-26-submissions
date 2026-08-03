# Model x retrieval-mode bake-off

Spec `06_unseen`, 3 fixed questions, identical data. Scored deterministically -- no LLM judge. `grounding.py` decides whether an asserted number appears in the query results the answer cites.

**Read `Figures cited` and `…of which grounded` together.** Groundedness on its own is a *precision* measure, and precision rewards saying less: a model citing one correct figure scores the same 100% as one citing seven. On the first run of this harness the deterministic `mock` stub -- placeholder prose by construction -- scored "100% grounded", identical to Sonnet. Volume is what separates them.

| Model | RAG | Schema-valid | Figures cited | …of which grounded | Ungrounded | DISPUTED handled | Context chars | Output tokens | Latency (s) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cli:claude-sonnet-5 | on | 3 | 5 | 5/5 | 0 | 1/1 | 25776 | 1660 | 33.4 |  |
| cli:claude-sonnet-5 | off | 3 | 7 | 7/7 | 0 | 1/1 | 53095 | 2433 | 43.0 |  |
| openai:gpt-oss:120b | on | 3 | 1 | 1/1 | 0 | 1/1 | 25776 | 705 | 11.1 |  |
| openai:gpt-oss:120b | off | 3 | 1 | 1/1 | 0 | 1/1 | 53095 | 748 | 11.9 |  |
| openai:gpt-oss:20b | on | 3 | 1 | 1/1 | 0 | 1/1 | 25776 | 896 | 15.3 |  |
| openai:gpt-oss:20b | off | 3 | 1 | 1/1 | 0 | 1/1 | 53095 | 550 | 14.3 |  |
| mock:mock | on | 3 | 2 | 2/2 | 0 | 1/1 | 25776 | 67 | 1.6 |  |
| mock:mock | off | 3 | 1 | 1/1 | 0 | 1/1 | 53095 | 71 | 1.4 |  |

Questions asked:

1. What is the coupon apply rate from coupon_field_shown to coupon_applied?
2. Which device_type has the worst checkout_with_coupon rate?
3. What is our conversion rate?
