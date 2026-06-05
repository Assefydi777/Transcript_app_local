#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Usage: $0 DOMAIN EMAIL"
  exit 1
fi

systemctl stop nginx || true
certbot certonly --standalone -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive
cat >/opt/transcript-app/nginx/nginx.conf <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}
server {
    listen 443 ssl;
    server_name $DOMAIN;
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    client_max_body_size 2G;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    location / {
        proxy_pass http://app:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF
(crontab -l 2>/dev/null | grep -v 'certbot renew'; echo '0 3 * * * certbot renew --quiet') | crontab -
cd /opt/transcript-app
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx

