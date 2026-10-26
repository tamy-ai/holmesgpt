#!/bin/sh
# Writes the GCP service account JSON from the env to a file, then starts the server.
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  printf '%s' "$GOOGLE_CREDENTIALS_JSON" > /tmp/gcp.json
  export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp.json
fi
exec python -u server.py
