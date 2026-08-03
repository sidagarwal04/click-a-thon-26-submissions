# Self-improving agent loop

Prompt-ops for the concurrency agents: ground truth from ClickHouse, experiments
against the live agent, and automatic prompt publishing when a challenger wins.

Runs standalone on your machine — a separate Python env from the containers.

```
langfuse/
├── langfuse_client.py          # LF client, ClickHouse, agent HTTP, role LLMs
├── evals/
│   ├── ground_truth.py         # correct answers computed from ClickHouse
│   ├── correctness.py          # deterministic evaluators (no LLM)
│   ├── llm_judge.py            # subjective axes only
│   └── seed_datasets.py        # questions + ground truth -> Langfuse datasets
├── experiments/
│   ├── run_experiment.py       # runs against the LIVE agent endpoint
│   └── auto_improve.py         # compare runs -> rewrite -> publish
└── scripts/run_pipeline.sh
```

## What makes this different from generic prompt-ops

**Correctness is measured, not judged.** Concurrency has a right answer: the
peak IS a number and it DID occur at a specific minute. `ground_truth.py`
computes both from ClickHouse at seed time, and `correctness.py` checks the
agent's answer against them with no LLM involved. The judge is left to score
only what no query can settle — groundedness, concision, actionability, clarity.

That distinction matters. Asking a model to grade a number it cannot verify
produces confident noise, and a loop optimising against that noise drifts
toward answers that read well and are wrong.

**Experiments hit the live agent.** `run_experiment.py` POSTs to lc-agent's
OpenAI-compatible endpoint, so each run exercises the real MCP tools, the real
Langfuse-served prompt, and the supervisor's real routing. A prompt that scores
well here works in the product.

**The loop actually closes.** lc-agent fetches prompts by the `production`
label and caches its graph keyed on prompt version. When `auto_improve.py`
publishes, live agent behaviour changes within the cache TTL — no rebuild, no
restart.

**Correctness is a gate, not a term.** In the blended score, deterministic
correctness is weighted double, and `auto_improve.py` refuses to publish at all
if correctness regressed — however much the prose improved.

## Setup

```bash
pip install -r langfuse/requirements.txt
```

Publish lc-agent's port so the pipeline can reach it. In `docker-compose.yml`:

```yaml
  lc-agent:
    ports:
      - "3002:3002"
```

Add to `.env`:

```dotenv
AGENT_BASE_URL=http://localhost:3002/v1

# Judge needs reliable JSON — do not use a free tier here, malformed JSON
# silently zeroes your scores.
JUDGE_PROVIDER=openrouter
JUDGE_MODEL=openai/gpt-oss-120b

IMPROVER_PROVIDER=openrouter
IMPROVER_MODEL=openai/gpt-oss-120b
```

`CH_HOST_BARE`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `AGENT_API_KEY` and
the Langfuse keys are already there from the main setup.

## Run it

```bash
# everything: seed + baseline across all three datasets
bash langfuse/scripts/run_pipeline.sh baseline-v1

# or step by step
python langfuse/evals/seed_datasets.py
python langfuse/experiments/run_experiment.py \
    --dataset liv-concurrency-evals --run-name baseline-v1

# deterministic scores only — fast, free, no judge tokens
python langfuse/experiments/run_experiment.py \
    --dataset liv-traps --run-name traps-v1 --no-judge

# edit the prompt in the Langfuse UI, then run a challenger
python langfuse/experiments/run_experiment.py \
    --dataset liv-concurrency-evals --run-name v2

# compare and publish the winner
python langfuse/experiments/auto_improve.py \
    --prompt liv-concurrency-agent --dataset liv-concurrency-evals \
    --baseline baseline-v1 --challenger v2
```

## The datasets

| Dataset | Items | Scored on |
|---|---|---|
| `liv-concurrency-evals` | peak, average, filtered slices, peak users | `numeric_accuracy`, `reports_moment` |
| `liv-segment-evals` | platform/country/title comparisons | `numeric_accuracy`, `reports_moment` |
| `liv-traps` | false-premise questions | `rule_compliance` |

`liv-traps` is small and matters most. It is the only set that tests whether the
correctness rules in `CLICKHOUSE_TOOL_HINT` are doing real work or just sitting
in the context window being ignored. An agent that answers "the combined total
peak is 4,812" has failed in a way no other dataset detects.

## Evaluators

**Deterministic** (`correctness.py`, no LLM, free):

- `numeric_accuracy` — the true peak value appears in the answer, tolerant of
  separators and 2% rounding
- `reports_moment` — a time is stated. The most common failure is a correct
  number with no minute attached, which discards the fact that a peak is a moment
- `rule_compliance` — trap questions were refused rather than answered

**Judged** (`llm_judge.py`, 0–10): groundedness, conciseness, actionability,
clarity.

## Improving the agents vs improving prompts

`--prompt` takes an agent prompt name (`liv-router-agent`,
`liv-concurrency-agent`, `liv-segment-agent`, `liv-capacity-agent`) — the same
ones `lc-agent/push_agent_prompts.py` publishes. There is deliberately no
second prompt family here: one set of prompts, evaluated and improved in place.

Schema and the three correctness rules stay in `lc-agent/config.py` as
`CLICKHOUSE_TOOL_HINT`, and `IMPROVE_SYSTEM` explicitly forbids the improver
from adding them to the prompt. Two sources of truth for the same rules would
drift, and a rewrite could quietly weaken the one thing keeping the SQL correct.