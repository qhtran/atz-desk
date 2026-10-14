#!/bin/sh
set -eu
docker exec nginx-reverse-proxy rm -f "/var/www/html/.well-known/acme-challenge/$CERTBOT_TOKEN"
