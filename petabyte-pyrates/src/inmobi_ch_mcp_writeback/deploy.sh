#!/usr/bin/env bash
# Deploy ClickHouse writeback MCP on Lambda (Streamable HTTP + Function URL).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$(cd "$(dirname "$0")" && pwd)"
REGION="${AWS_REGION:-ap-south-1}"
PROFILE="${AWS_PROFILE:-clickathon}"
FUNCTION_NAME="${FUNCTION_NAME:-inmobi-ch-mcp-writeback}"
ROLE_NAME="${ROLE_NAME:-inmobi-rca-ch-bridge-role}"

export AWS_PROFILE="$PROFILE"
export AWS_DEFAULT_REGION="$REGION"

if [[ -f "$ROOT/.env" ]]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^CLICKHOUSE_(HOST|USER|PASSWORD)= ]] && export "$line"
  done < "$ROOT/.env"
fi

: "${CLICKHOUSE_HOST:?Set CLICKHOUSE_HOST in .env}"

MCP_TOKEN_FILE="$PKG/.mcp_auth_token"
if [[ -f "$MCP_TOKEN_FILE" && -z "${MCP_AUTH_TOKEN:-}" ]]; then
  MCP_AUTH_TOKEN=$(cat "$MCP_TOKEN_FILE")
else
  MCP_AUTH_TOKEN="${MCP_AUTH_TOKEN:-$(openssl rand -hex 24)}"
fi
echo "$MCP_AUTH_TOKEN" > "$MCP_TOKEN_FILE"
chmod 600 "$MCP_TOKEN_FILE"

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)

echo "==> Packaging Lambda"
ZIP="/tmp/inmobi-ch-mcp-writeback.zip"
rm -f "$ZIP"
(cd "$PKG" && zip -q "$ZIP" handler.py)

ENV_VARS="MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN,CLICKHOUSE_HOST=$CLICKHOUSE_HOST,CLICKHOUSE_USER=${CLICKHOUSE_USER:-default},CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD"

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
    --timeout 60 \
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
echo "MCP writeback Lambda deployed"
echo "  URL:     $FUNC_URL"
echo "  Token:   $MCP_AUTH_TOKEN  ($PKG/.mcp_auth_token)"
echo "  Tool:    close_anomaly_investigation"
echo "=========================================="
echo ""
echo "Attach in ClickHouse Agent Builder → MCP servers:"
echo "  URL: $FUNC_URL"
echo "  Auth: Bearer token = value in $PKG/.mcp_auth_token"
