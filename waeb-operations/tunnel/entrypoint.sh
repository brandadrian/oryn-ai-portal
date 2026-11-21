#!/bin/sh
set -e
# ssh refuses keys with open permissions, so copy the read-only mounted key.
cp /keys/id_key /tmp/id_key && chmod 600 /tmp/id_key

exec autossh -M 0 -N \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/keys/known_hosts \
  -o IdentitiesOnly=yes -i /tmp/id_key \
  -p "${SSH_PORT:-22}" \
  -L "0.0.0.0:3100:127.0.0.1:${LOKI_REMOTE_PORT:-3100}" \
  -L "0.0.0.0:3306:${MYSQL_REMOTE_HOST:-127.0.0.1}:${MYSQL_REMOTE_PORT:-3306}" \
  -L "0.0.0.0:9090:127.0.0.1:${PROMETHEUS_REMOTE_PORT:-9090}" \
  "${SSH_USER}@${SSH_HOST}"
