#!/bin/sh
# Create /opt/authentik secrets once, then start the stack. Prints no secret values.
set -eu
umask 077
unset HISTFILE
base=/opt/authentik
mkdir -p "$base/secrets" "$base/data" "$base/custom-templates" "$base/blueprints"
if [ ! -s "$base/.env" ]; then
  pg=$(openssl rand -base64 24 | tr -d '\n')
  secret=$(openssl rand -base64 48 | tr -d '\n')
  admin=$(openssl rand -base64 24 | tr -d '\n')
  token=$(openssl rand -base64 32 | tr -d '\n')
  cat > "$base/.env" <<EOF
PG_DB=authentik
PG_USER=authentik
PG_PASS=${pg}
AUTHENTIK_SECRET_KEY=${secret}
AUTHENTIK_TAG=2026.8.3
AUTHENTIK_BOOTSTRAP_EMAIL=admin@atz.vn
AUTHENTIK_BOOTSTRAP_PASSWORD=${admin}
AUTHENTIK_BOOTSTRAP_TOKEN=${token}
EOF
  printf '%s\n' "$admin" > "$base/secrets/akadmin.password"
  printf '%s\n' "$token" > "$base/secrets/bootstrap.token"
fi
chmod 600 "$base/.env" "$base/secrets/"*
echo "env-ready"
cd "$base"
docker compose pull
docker compose up -d
echo "compose-started"
