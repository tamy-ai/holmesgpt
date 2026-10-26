#!/bin/sh
# Writes the GCP service account JSON from the env to a file, keeps a read-only clone of the
# product code (branch main) in CODE_ROOT, then starts the server.
if [ -n "$GOOGLE_CREDENTIALS_JSON" ]; then
  printf '%s' "$GOOGLE_CREDENTIALS_JSON" > /tmp/gcp.json
  export GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcp.json
fi

CODE_ROOT="${CODE_ROOT:-/app/code}"
export CODE_ROOT
if [ -n "$GITHUB_READ_TOKEN" ] && [ -n "$CODE_REPO" ]; then
  AUTH="Authorization: Basic $(printf 'x-access-token:%s' "$GITHUB_READ_TOKEN" | base64 | tr -d '\n')"
  sync_code() {
    if [ -d "$CODE_ROOT/.git" ]; then
      git -C "$CODE_ROOT" -c http.extraHeader="$AUTH" fetch -q --depth 1 origin main \
        && git -C "$CODE_ROOT" reset -q --hard FETCH_HEAD
    else
      git -c http.extraHeader="$AUTH" clone -q --depth 1 --branch main "$CODE_REPO" "$CODE_ROOT"
    fi
  }
  (
    sync_code || echo "code clone failed"
    while true; do sleep 1800; sync_code || echo "code sync failed"; done
  ) &
fi
exec python -u server.py
