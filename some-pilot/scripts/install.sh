#!/usr/bin/env bash
set -euo pipefail
if [[ $(id -u) -ne 0 ]]; then
  echo "Run on the new Ubuntu 24.04 server as root after SSH fingerprint verification." >&2
  exit 2
fi
apt-get update
apt-get upgrade -y
apt-get install -y ca-certificates curl git ufw unattended-upgrades python3 python3-venv
if ! id deploy >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" deploy
fi
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
if [[ -f /root/.ssh/authorized_keys && ! -f /home/deploy/.ssh/authorized_keys ]]; then
  install -m 600 -o deploy -g deploy /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
fi
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
ARCH=$(dpkg --print-architecture)
printf '%s\n' "Types: deb" "URIs: https://download.docker.com/linux/ubuntu" "Suites: $VERSION_CODENAME" "Components: stable" "Architectures: $ARCH" "Signed-By: /etc/apt/keyrings/docker.asc" > /etc/apt/sources.list.d/docker.sources
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
docker run --rm hello-world
docker compose version
install -d -m 700 /opt/some/secrets
install -d -o 10001 -g 10001 /opt/some/data /opt/some/models
install -d -o deploy -g deploy /opt/some/app
ufw default deny incoming
ufw default allow outgoing
if [[ -n "${ADMIN_IP:-}" ]]; then
  ufw allow from "$ADMIN_IP" to any port 22 proto tcp
  echo "Review rules, then enable with: ufw enable" >&2
else
  echo "ADMIN_IP not supplied; SSH rule and ufw enable intentionally not applied." >&2
fi
printf '%s\n' "Next: open a NEW deploy SSH session and verify sudo before disabling root/password login." "Create /opt/some/secrets/app.env securely with chmod 600; never paste keys in chat." "Deploy from /opt/some/app with scripts/deploy.sh."
