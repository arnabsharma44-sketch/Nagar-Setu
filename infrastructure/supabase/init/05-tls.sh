#!/usr/bin/env bash
# Enable TLS on the local Supabase-shaped instance and refuse plaintext TCP.
#
# Runs inside the postgres container after initdb, before the entrypoint restarts
# the server for real. Writing postgresql.conf / pg_hba.conf here is therefore
# picked up by that final start. The certificate lives inside PGDATA so file
# ownership and 0600 permissions satisfy PostgreSQL's key checks.
set -euo pipefail

CERT_DIR="$PGDATA/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.crt" \
  -subj "/CN=supabase-local-db" >/dev/null 2>&1
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

cat >> "$PGDATA/postgresql.conf" <<EOF
# --- local Supabase-shaped TLS ---
ssl = on
ssl_cert_file = '$CERT_DIR/server.crt'
ssl_key_file = '$CERT_DIR/server.key'
EOF

# Plaintext TCP is rejected, exactly like a managed instance that only serves TLS.
# Local socket stays trusted so pg_isready and in-container psql keep working.
cat > "$PGDATA/pg_hba.conf" <<'EOF'
local   all all                  trust
hostssl all all 0.0.0.0/0        scram-sha-256
hostssl all all ::/0             scram-sha-256
hostnossl all all 0.0.0.0/0      reject
hostnossl all all ::/0           reject
EOF

echo "supabase-shape: TLS enabled, non-TLS TCP rejected"
