#!/bin/sh
set -eu
umask 077
unset HISTFILE
base=/opt/authelia
mkdir -p "$base/config" "$base/secrets"
install -m 644 "$base/configuration.yml" "$base/config/configuration.yml"
chmod 755 "$base/redis-entrypoint.sh" "$base/acme-auth.sh" "$base/acme-cleanup.sh" "$base/renew-auth-cert.sh"

gen() {
  if [ ! -s "$1" ]; then
    openssl rand -base64 32 | tr -d '\n' > "$1"
  fi
  chmod 600 "$1"
}
gen "$base/secrets/admin.password"
gen "$base/secrets/session_secret"
gen "$base/secrets/storage_encryption_key"
gen "$base/secrets/jwt_secret"
gen "$base/secrets/redis_password"

docker pull authelia/authelia:4.38.19 >/tmp/authelia-pull.log
uid=$(docker run --rm --entrypoint id authelia/authelia:4.38.19 -u)
gid=$(docker run --rm --entrypoint id authelia/authelia:4.38.19 -g)
echo "authelia-uid=$uid authelia-gid=$gid"

if [ ! -s "$base/config/users_database.yml" ]; then
  docker run --rm -v "$base/secrets:/secrets:ro" authelia/authelia:4.38.19 \
    authelia crypto hash generate argon2 --password "$(cat "$base/secrets/admin.password")" \
    > "$base/secrets/admin.hash"
  digest=$(awk 'match($0, /\$argon2id\$[^[:space:]]+/) { print substr($0, RSTART, RLENGTH); exit }' "$base/secrets/admin.hash")
  if [ -z "$digest" ]; then
    echo "hash-missing"
    exit 1
  fi
  cat > "$base/config/users_database.yml" <<EOF
---
users:
  admin:
    disabled: false
    displayname: Admin
    email: admin@atz.vn
    password: "$digest"
    groups:
      - admins
EOF
  rm -f "$base/secrets/admin.hash"
  echo "users-written ${#digest}"
fi
chmod 600 "$base/config/users_database.yml"
chown "$uid:$gid" "$base/config" "$base/config/configuration.yml" "$base/config/users_database.yml"
chown "$uid:$gid" "$base/secrets" "$base/secrets/"*
chmod 755 "$base/config" "$base/secrets"
echo "secrets-ready"
