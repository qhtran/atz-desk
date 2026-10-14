#!/bin/sh
set -eu
docker exec nginx-reverse-proxy mkdir -p /var/www/html/.well-known/acme-challenge
printf '%s' "$CERTBOT_VALIDATION" | docker exec -i nginx-reverse-proxy tee "/var/www/html/.well-known/acme-challenge/$CERTBOT_TOKEN" >/dev/null
