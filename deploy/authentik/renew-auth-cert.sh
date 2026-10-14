#!/bin/sh
# Renew auth.atz.vn and copy the certificate files into the nginx volume.
set -eu
certbot renew --cert-name auth.atz.vn --quiet
src=/etc/letsencrypt/live/auth.atz.vn
dst=/var/lib/docker/volumes/n8n_letsencrypt/_data/live/auth.atz.vn
mkdir -p "$dst"
cp -L "$src/cert.pem" "$src/chain.pem" "$src/fullchain.pem" "$src/privkey.pem" "$dst/"
chmod 644 "$dst/cert.pem" "$dst/chain.pem" "$dst/fullchain.pem"
chmod 600 "$dst/privkey.pem"
docker exec nginx-reverse-proxy nginx -t
docker exec nginx-reverse-proxy nginx -s reload
echo "auth.atz.vn certificate copied and nginx reloaded"
