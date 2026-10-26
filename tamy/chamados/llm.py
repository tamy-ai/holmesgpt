"""One JSON answer from Gemini on Vertex AI, in our own GCP project.

The classifier and the checklist reader ask the same thing: a system prompt, a prompt, one
JSON object back, temperature 0, under a time cap. Credentials are the service account of
`GOOGLE_APPLICATION_CREDENTIALS`; the project is `VERTEX_PROJECT`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_MODEL = "gemini-3.1-flash-lite"
VERTEX_LOCATION = "global"
VERTEX_URL = (
    "https://aiplatform.googleapis.com/v1/projects/{project}/locations/"
    "{location}/publishers/google/models/{model}:generateContent"
)

_credentials: Any = None


def object_json(text: str) -> str:
    """From the first brace to the last, or "". It skips a markdown fence and a lead-in
    sentence; what comes out must still be valid JSON and fit the caller's shape."""
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else ""


def _token() -> str:
    global _credentials  # noqa: PLW0603 -- one cached credential per process
    import google.auth  # noqa: PLC0415 -- only the services that call the model need it
    import google.auth.transport.requests  # noqa: PLC0415

    if _credentials is None:
        _credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _credentials.valid:
        _credentials.refresh(google.auth.transport.requests.Request())
    return str(_credentials.token)


def invoke_json(
    system: str,
    prompt: str,
    *,
    timeout_s: float,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    """The model's text. Raises on a model error or on a timeout."""
    url = VERTEX_URL.format(
        project=os.environ["VERTEX_PROJECT"],
        location=VERTEX_LOCATION,
        model=model or os.environ.get("CHAMADOS_MODEL", DEFAULT_MODEL),
    )
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            **({"maxOutputTokens": max_tokens} if max_tokens else {}),
        },
    }
    request = urllib.request.Request(  # noqa: S310 -- fixed https template
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Vertex respondeu HTTP {error.code}") from None
    parts = ((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts", [])
    return "".join(str(p.get("text", "")) for p in parts if not p.get("thought"))
