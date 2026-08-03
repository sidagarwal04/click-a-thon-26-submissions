# AWS Bedrock Setup (Backend Narrator)

How to get the **backend → AWS Bedrock** connection working on your machine.
The narrator (`backend/narrator/narrate.py`) turns an Evidence Bundle into prose by calling
Bedrock's `converse` API. It authenticates through the **standard AWS credential chain** — there
is **no LLM API key** in `.env`.

## Mental model (read this first)

| Thing | Where it lives | Who sets it |
|---|---|---|
| Region + model (`ap-southeast-2` / `deepseek.v3.2`) | `backend/config.json` (tracked) | Already correct — shared in the repo |
| AWS credentials | `~/.aws/` on your machine (or env vars) | **You** — per person, never committed |

- The backend runs **on the host** (your venv), so it *can* read `~/.aws`. That's why it works
  where LibreChat-in-Docker can't.
- Bedrock **model access** is account-level; **credentials** are per-person. Both must be right.

## Steps

### 1. Configure AWS credentials
```bash
aws configure
```
Enter your **Access Key ID**, **Secret Access Key**, and set the default region to
**`ap-southeast-2`** (must match `config.json`). This writes `~/.aws/credentials` + `~/.aws/config`.

> Alternative (no CLI): export `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION=ap-southeast-2`.
> If using AWS SSO / Identity Center: `aws configure sso` then `aws sso login`.

Get your credentials from the account owner. You need an IAM identity with at least:
`bedrock:InvokeModel`, `bedrock:Converse` (and optionally `bedrock:ListFoundationModels`).

### 2. Confirm Bedrock model access
`deepseek.v3.2` must be enabled in **`ap-southeast-2`**.
- **Shared team account:** if the owner already enabled it, you're covered — skip this.
- **Your own account:** Bedrock console → **Model access** → enable **DeepSeek V3.2**.

### 3. Set up the backend virtual environment (once)
```bash
cd backend
python -m venv .venv

# Windows:
.venv/Scripts/python -m pip install clickhouse-connect fastapi "uvicorn[standard]" pydantic python-dotenv pandas langfuse jsonschema boto3 pytest

# macOS / Linux:
.venv/bin/python     -m pip install clickhouse-connect fastapi "uvicorn[standard]" pydantic python-dotenv pandas langfuse jsonschema boto3 pytest
```

### 4. Verify the backend ↔ Bedrock connection
Runs through the backend's own config, so it proves the real code path:
```bash
cd backend

# Windows (use .venv/bin/python on macOS/Linux):
.venv/Scripts/python -c "from config import BEDROCK; import boto3; c=boto3.client('bedrock-runtime', region_name=BEDROCK['region']); print('Bedrock OK ->', c.converse(modelId=BEDROCK['model_id'], messages=[{'role':'user','content':[{'text':'say OK'}]}], inferenceConfig={'maxTokens':10})['output']['message']['content'][0]['text'])"
```
A printed reply means backend → Bedrock is live.

## Error decoder

| Error | Cause | Fix |
|---|---|---|
| `UnrecognizedClientException` / `NoCredentialsError` | Credentials missing or wrong | Step 1 |
| `AccessDeniedException` | Model access not granted, or missing IAM permission | Step 2 (+ IAM) |
| `ExpiredToken` | SSO session expired | `aws sso login` |
| `ValidationException: ... model ... not found` | Wrong region | Region must be `ap-southeast-2` |

## Notes

- **Region/model overrides (optional):** set `AWS_REGION` or `BEDROCK_MODEL_ID` in `.env` to override
  `config.json`. Normally you don't need to.
- **This is for the backend narrator only.** LibreChat is a separate app and is *not* wired to
  Bedrock; it doesn't need to be for the RCA system.
- **Never commit credentials.** `.env` and `~/.aws` stay off git. The repo goes public.
