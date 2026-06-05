#!/usr/bin/env bash
set -euo pipefail

apt-get update
apt-get install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx ufw fail2ban htop git rsync

if ! id deploy >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" deploy
fi
usermod -aG docker deploy
cat >/etc/sudoers.d/deploy-docker <<'EOF'
deploy ALL=(root) NOPASSWD: /usr/bin/docker, /usr/bin/docker compose
EOF
chmod 0440 /etc/sudoers.d/deploy-docker

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

cat >/etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban docker

grep -q '^vm.swappiness=10' /etc/sysctl.conf || echo 'vm.swappiness=10' >>/etc/sysctl.conf
grep -q '^vm.vfs_cache_pressure=50' /etc/sysctl.conf || echo 'vm.vfs_cache_pressure=50' >>/etc/sysctl.conf
sysctl -p

mkdir -p /opt/transcript-app
chown -R deploy:deploy /opt/transcript-app

echo "Server setup complete. Create /opt/transcript-app/.env.prod as deploy, then run scripts/deploy/deploy.sh SERVER."

