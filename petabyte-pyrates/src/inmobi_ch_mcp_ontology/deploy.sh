#!/usr/bin/env bash
# Deploy InMobi ontology MCP on Lambda (Streamable HTTP + Function URL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$(cd "$(dirname "$0")" && pwd)"
ONTOLOGY_YAML="$ROOT/config/glossary_ontology.yaml"
REGION="${AWS_REGION:-ap-south-1}"
PROFILE="${AWS_PROFILE:-clickathon}"
FUNCTION_NAME="${FUNCTION_NAME:-inmobi-ch-mcp-ontology}"
ROLE_NAME="${ROLE_NAME:-inmobi-rca-ch-bridge-role}"

export AWS_PROFILE="$PROFILE"
export AWS_DEFAULT_REGION="$REGION"

: "${ONTOLOGY_YAML:?Missing $ONTOLOGY_YAML}"

MCP_TOKEN_FILE="$PKG/.mcp_auth_token"
if [[ -f "$MCP_TOKEN_FILE" && -z "${MCP_AUTH_TOKEN:-}" ]]; then
  MCP_AUTH_TOKEN=$(cat "$MCP_TOKEN_FILE")
else
  MCP_AUTH_TOKEN="${MCP_AUTH_TOKEN:-$(openssl rand -hex 24)}"
fi
echo "$MCP_AUTH_TOKEN" > "$MCP_TOKEN_FILE"
chmod 600 "$MCP_TOKEN_FILE"

echo "==> Building ontology.json from glossary_ontology.yaml"
(cd "$ROOT" && uv run python - <<'PY'
import json
from pathlib import Path

from inmobi_ontology.loader import load_ontology

root = Path.cwd()
out = root / "src/inmobi_ch_mcp_ontology/ontology.json"
ontology = load_ontology(root / "config/glossary_ontology.yaml")
out.write_text(json.dumps(ontology.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} bytes)")
PY
)

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)

echo "==> Packaging Lambda"
ZIP="/tmp/inmobi-ch-mcp-ontology.zip"
rm -f "$ZIP"
(cd "$PKG" && zip -q "$ZIP" handler.py ontology.json)

ENV_VARS="MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN"

echo "==> Deploying Lambda $FUNCTION_NAME"
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNCTION_NAME" --zip-file "fileb://$ZIP"
  aws lambda wait function-updated --function-name "$FUNCTION_NAME"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment "Variables={$ENV_VARS}" \
    --vpc-config SubnetIds=[],SecurityGroupIds=[]
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler handler.handler \
    --timeout 30 \
    --memory-size 256 \
    --zip-file "fileb://$ZIP" \
    --environment "Variables={$ENV_VARS}"
fi

aws lambda wait function-active-v2 --function-name "$FUNCTION_NAME" 2>/dev/null || \
  aws lambda wait function-active --function-name "$FUNCTION_NAME"

echo "==> Creating public Function URL"
aws lambda create-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --auth-type NONE \
  --invoke-mode BUFFERED 2>/dev/null || \
aws lambda update-function-url-config \
  --function-name "$FUNCTION_NAME" \
  --auth-type NONE \
  --invoke-mode BUFFERED

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --statement-id public-function-url 2>/dev/null || true

aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --action lambda:InvokeFunction \
  --principal "*" \
  --statement-id FunctionURLAllowPublicInvoke 2>/dev/null || true

FUNC_URL=$(aws lambda get-function-url-config --function-name "$FUNCTION_NAME" --query FunctionUrl --output text)
FUNC_URL="${FUNC_URL%/}"
echo "$FUNC_URL" > "$PKG/.mcp_url"

echo ""
echo "=========================================="
echo "Ontology MCP Lambda deployed"
echo "  URL:     $FUNC_URL"
echo "  Token:   $MCP_AUTH_TOKEN  ($PKG/.mcp_auth_token)"
echo "  Tool:    get_ontology"
echo "=========================================="
echo ""
echo "Attach in ClickHouse Agent Builder → MCP servers:"
echo "  URL: $FUNC_URL"
echo "  Auth: Bearer token = value in $PKG/.mcp_auth_token"
