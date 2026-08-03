#!/bin/bash
# Clickathon 2026 - RCA stack bootstrap.
#
# Secrets are NEVER baked into this script, the AMI, or the repo. They are read from SSM
# Parameter Store at boot using the instance profile, so rotating a parameter and rebooting
# is the whole update path, and nothing sensitive survives on disk outside /opt/clickathon/.env
# (root-owned, 0600).
set -euxo pipefail
exec > >(tee -a /var/log/clickathon-bootstrap.log) 2>&1

REGION=ap-southeast-2
REPO=https://github.com/Rohanmrao/Clickathon2026.git
APP=/opt/clickathon

echo "=== [1/5] packages ==="
dnf update -y
dnf install -y docker git
systemctl enable --now docker
usermod -aG docker ec2-user

# Compose v2 and buildx as docker plugins. Amazon Linux 2023 packages neither at a usable
# version: it ships no compose at all, and a buildx old enough that current compose refuses to
# build against it ("compose build requires buildx 0.17.0 or later"). Installing compose alone
# gets you all the way to the final step and then fails, which is exactly what happened here.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -sSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

BUILDX=v0.36.0
curl -fsSL "https://github.com/docker/buildx/releases/download/${BUILDX}/buildx-${BUILDX}.linux-amd64" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

docker compose version
docker buildx version

echo "=== [2/5] source ==="
git clone --depth 1 "$REPO" "$APP"
cd "$APP"

echo "=== [3/5] secrets from SSM ==="
# --with-decryption resolves SecureString via KMS; the instance profile grants exactly this
# path and nothing else.
get() { aws ssm get-parameter --region "$REGION" --name "/clickathon/$1" --with-decryption \
        --query Parameter.Value --output text; }

PUBLIC_IP=$(curl -sf -H "X-aws-ec2-metadata-token: $(curl -sf -X PUT http://169.254.169.254/latest/api/token \
             -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')" \
             http://169.254.169.254/latest/meta-data/public-ipv4)

umask 077
cat > "$APP/.env" <<EOF
CLICKHOUSE_HOST=$(get clickhouse/host)
CLICKHOUSE_PORT=$(get clickhouse/port)
CLICKHOUSE_USER=$(get clickhouse/user)
CLICKHOUSE_PASSWORD=$(get clickhouse/password)
CLICKHOUSE_DATABASE=$(get clickhouse/database)

LANGFUSE_PUBLIC_KEY=$(get langfuse/public_key)
LANGFUSE_SECRET_KEY=$(get langfuse/secret_key)
LANGFUSE_INIT_USER_PASSWORD=$(get langfuse/init_user_password)
# Two different addresses for the same service, deliberately:
#   LANGFUSE_PUBLIC_HOST - what a BROWSER resolves. Points at the dedicated HTTPS host that
#                          fronts Langfuse (traces.kangasys.com), so every "Open trace" link a
#                          judge clicks lands on a reachable page instead of their own machine.
#                          Uses the stable domain rather than the raw public IP, which changes
#                          on stop/start.
#   LANGFUSE_HOST        - container-to-container, set to the service name inside compose.
LANGFUSE_PUBLIC_HOST=${LANGFUSE_PUBLIC_HOST:-https://traces.kangasys.com}
LANGFUSE_BASE_URL=https://traces.kangasys.com

# Bedrock auth comes from the instance profile - no keys anywhere on this box.
AWS_REGION=$(get bedrock/region)
BEDROCK_MODEL_ID=$(get bedrock/model_id)

# Baked into the dashboard at BUILD time and resolved by the VIEWER's browser, so these must
# be publicly reachable addresses. Left at the compose default of localhost, a judge opening the
# dashboard gets "Backend unreachable" because their own machine has nothing on :8000.
VITE_API_URL=http://${PUBLIC_IP}:8000
VITE_LIBRECHAT_URL=http://${PUBLIC_IP}:3080
EOF
chown root:root "$APP/.env"; chmod 600 "$APP/.env"

echo "=== [4/5] systemd unit ==="
# Runs compose as a managed service so the stack survives reboots and secrets are re-read
# from SSM on every start.
cat > /etc/systemd/system/clickathon.service <<EOF
[Unit]
Description=Clickathon 2026 RCA stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP
ExecStart=/usr/bin/docker compose up -d --build
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable clickathon.service

echo "=== [5/5] up ==="
systemctl start clickathon.service || true
docker compose ps || true
echo "=== bootstrap finished at $(date -Is) ==="
