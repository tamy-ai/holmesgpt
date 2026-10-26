"""The Jira Cloud REST client. One definition for CI and for Tamy Chamados.

CI runs `scripts/jira_sync.py` with a bare `python3` and no installed package,
so this module imports the standard library only. Keep it that way.

`move_to_status` lives here too: CI moves tickets on merge and deploy. The
ADF builders live here because CI and Tamy Chamados both write Jira text.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import cast

JIRA_SITE_URL = "https://tamy-ai.atlassian.net"
DEFAULT_PROJECT_KEY = "TA"

# A search that matches more than this is a broken JQL, not a big queue.
DEFAULT_SEARCH_MAX_PAGES = 20
SEARCH_PAGE_SIZE = 100

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class MultipartFile:
    """One file for `POST /issue/{key}/attachments`."""

    filename: str
    content: bytes
    content_type: str


JsonBody = dict[str, object] | list[object] | None
Body = JsonBody | MultipartFile
Transport = Callable[[str, str, Body], tuple[int, object]]
AdfNode = dict[str, object]


class JiraError(Exception):
    """A Jira call failed or Jira is not in the expected state.

    `status` is the HTTP status when Jira answered with one."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class JiraConfigError(JiraError):
    """Jira answered, but the project's setup does not allow the call (a
    missing issue type, a field the create screen lacks). Another try will
    not help; the message, in Portuguese, names what to change."""


class JiraUnreachableError(JiraError):
    """No answer from Jira. A write may or may not have happened."""


def basic_auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _check_scheme(base_url: str) -> None:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS:
        return
    raise JiraError(f"JIRA_BASE_URL precisa começar com https://: {base_url}")


def multipart_body(file: MultipartFile) -> tuple[bytes, str]:
    """(body, content type) of a form with one file field, as Jira expects."""
    boundary = uuid.uuid4().hex
    safe_name = file.filename.replace('"', "'").replace("\r", " ").replace("\n", " ")
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
        f"Content-Type: {file.content_type}\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + file.content + tail, f"multipart/form-data; boundary={boundary}"


def urllib_transport(
    base_url: str, authorization: str, timeout_s: float = 30
) -> Transport:
    _check_scheme(base_url)

    def send(method: str, path: str, body: Body) -> tuple[int, object]:
        headers = {"Authorization": authorization, "Accept": "application/json"}
        data: bytes | None
        if isinstance(body, MultipartFile):
            data, headers["Content-Type"] = multipart_body(body)
            # Jira refuses an upload without it (XSRF check).
            headers["X-Atlassian-Token"] = "no-check"
        else:
            data = None if body is None else json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(  # noqa: S310 - scheme checked above
            base_url.rstrip("/") + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
                return response.status, _json_or_none(response.read())
        except urllib.error.HTTPError as error:
            return error.code, _json_or_none(error.read())
        except (urllib.error.URLError, TimeoutError) as error:
            reason = error.reason if isinstance(error, urllib.error.URLError) else error
            raise JiraUnreachableError(
                f"o Jira não respondeu em {base_url}: {reason}"
            ) from error

    return send


def json_object(value: object) -> dict[str, object]:
    """A JSON object from Jira, or {} for anything else."""
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def json_objects(value: object) -> list[dict[str, object]]:
    """The JSON objects of a JSON array from Jira; anything else is dropped."""
    items = cast(list[object], value) if isinstance(value, list) else []
    return [json_object(item) for item in items if isinstance(item, dict)]


def _json_or_none(raw: bytes) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode(errors="replace")[:500]


def adf_text(text: str) -> AdfNode:
    return {"type": "text", "text": text}


def adf_link(label: str, url: str) -> AdfNode:
    return {
        "type": "text",
        "text": label,
        "marks": [{"type": "link", "attrs": {"href": url}}],
    }


def adf_doc(paragraphs: Sequence[Sequence[AdfNode]]) -> AdfNode:
    """An Atlassian Document: one paragraph per sequence of inline nodes."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": list(nodes)} for nodes in paragraphs
        ],
    }


def adf_heading(text: str, level: int = 3) -> AdfNode:
    return {"type": "heading", "attrs": {"level": level}, "content": [adf_text(text)]}


def adf_paragraph(nodes: Sequence[AdfNode]) -> AdfNode:
    return {"type": "paragraph", "content": list(nodes)}


def _adf_list(kind: str, items: Sequence[Sequence[AdfNode]]) -> AdfNode:
    return {
        "type": kind,
        "content": [
            {"type": "listItem", "content": [adf_paragraph(nodes)]} for nodes in items
        ],
    }


def adf_bullets(items: Sequence[Sequence[AdfNode]]) -> AdfNode:
    return _adf_list("bulletList", items)


def adf_ordered(items: Sequence[Sequence[AdfNode]]) -> AdfNode:
    return _adf_list("orderedList", items)


def adf_blocks(blocks: Sequence[AdfNode]) -> AdfNode:
    """An Atlassian Document from block nodes (headings, paragraphs, lists)."""
    return {"type": "doc", "version": 1, "content": list(blocks)}


class JiraClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        token: str,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url
        self._send = transport or urllib_transport(
            base_url, basic_auth_header(email, token)
        )
        self._field_ids: dict[str, str] | None = None

    def request(self, method: str, path: str, body: Body = None) -> object:
        status, payload = self._send(method, path, body)
        if 200 <= status < 300:
            return payload
        raise JiraError(
            f"o Jira recusou {method} {path}: HTTP {status} "
            f"{json.dumps(payload, ensure_ascii=False)[:500]}",
            status=status,
        )

    def get_issue(self, key: str, fields: Iterable[str]) -> dict[str, object]:
        query = urllib.parse.urlencode({"fields": ",".join(fields)})
        status, payload = self._send("GET", f"/rest/api/3/issue/{key}?{query}", None)
        if status == 404:
            raise JiraError(
                f"o ticket {key} não existe no Jira, ou a conta do CI não o enxerga"
            )
        if not 200 <= status < 300 or not isinstance(payload, dict):
            raise JiraError(
                f"o Jira recusou a leitura de {key}: HTTP {status} {payload}"
            )
        return json_object(json_object(payload).get("fields"))

    def issue_status(self, key: str) -> str | None:
        """The status of one issue; None only when Jira answers 404 (gone, or out
        of the account's sight). Any other failure raises."""
        status, payload = self._send(
            "GET", f"/rest/api/3/issue/{key}?fields=status", None
        )
        if status == 404:
            return None
        if not 200 <= status < 300 or not isinstance(payload, dict):
            raise JiraError(
                f"o Jira recusou a leitura de {key}: HTTP {status}", status=status
            )
        name = status_name(json_object(json_object(payload).get("fields")))
        if not name:
            raise JiraError(f"o Jira devolveu {key} sem situação")
        return name

    def field_id(self, name: str) -> str:
        if self._field_ids is None:
            fields = self.request("GET", "/rest/api/3/field")
            if not isinstance(fields, list):
                raise JiraError(
                    f"o Jira devolveu a lista de campos fora do formato: {fields!r:.200}"
                )
            self._field_ids = {
                str(field["name"]): str(field["id"])
                for field in json_objects(fields)
                if "name" in field and "id" in field
            }
        if name not in self._field_ids:
            raise JiraError(f"o campo '{name}' não existe no Jira")
        return self._field_ids[name]

    def create_issue(self, fields: dict[str, object]) -> str:
        payload = self.request("POST", "/rest/api/3/issue", {"fields": fields})
        key = payload.get("key") if isinstance(payload, dict) else None
        if not isinstance(key, str) or not key:
            raise JiraError(
                f"o Jira criou o ticket mas não devolveu a chave: {payload}"
            )
        return key

    def add_attachment(self, key: str, file: MultipartFile) -> None:
        self.request("POST", f"/rest/api/3/issue/{key}/attachments", file)

    def add_remote_link(self, key: str, url: str, title: str) -> None:
        self.request(
            "POST",
            f"/rest/api/3/issue/{key}/remotelink",
            {"object": {"url": url, "title": title}},
        )

    def add_label(self, key: str, label: str) -> None:
        self.request(
            "PUT",
            f"/rest/api/3/issue/{key}",
            {"update": {"labels": [{"add": label}]}},
        )

    def add_comment(self, key: str, body: AdfNode) -> None:
        self.request("POST", f"/rest/api/3/issue/{key}/comment", {"body": body})

    def _paged_values(
        self, path: str, *, key: str = "values"
    ) -> list[dict[str, object]]:
        """Every `key` item of a startAt/total paged GET, up to a page cap. Jira names the
        list per endpoint: `values` for most, `issueTypes` and `fields` for createmeta."""
        values: list[dict[str, object]] = []
        start = 0
        for _ in range(DEFAULT_SEARCH_MAX_PAGES):
            separator = "&" if "?" in path else "?"
            payload = self.request("GET", f"{path}{separator}startAt={start}")
            if not isinstance(payload, dict):
                raise JiraError(
                    f"o Jira devolveu {path} fora do formato: {payload!r:.200}"
                )
            page = json_objects(json_object(payload).get(key))
            values.extend(page)
            total = json_object(payload).get("total")
            start += len(page)
            if not page or not isinstance(total, int) or start >= total:
                return values
        raise JiraError(
            f"{path} passou de {DEFAULT_SEARCH_MAX_PAGES} páginas; leitura cortada"
        )

    def create_fields(self, project_key: str, issue_type: str) -> frozenset[str]:
        """The fields the create screen of one issue type accepts (createmeta).
        Jira refuses a create that sends a field outside this set."""
        base = f"/rest/api/3/issue/createmeta/{project_key}/issuetypes"
        type_id = next(
            (
                str(item.get("id"))
                for item in self._paged_values(base, key="issueTypes")
                if item.get("name") == issue_type
            ),
            None,
        )
        if type_id is None:
            raise JiraConfigError(
                f"o projeto {project_key} não tem o tipo de ticket {issue_type}"
            )
        return frozenset(
            field_id
            for item in self._paged_values(f"{base}/{type_id}", key="fields")
            if isinstance(field_id := item.get("fieldId"), str)
        )

    def search(
        self,
        jql: str,
        *,
        fields: Iterable[str],
        expand: str | None = None,
        max_pages: int = DEFAULT_SEARCH_MAX_PAGES,
    ) -> list[dict[str, object]]:
        """Every issue the JQL matches, following `nextPageToken`.

        Raises when a page is not a JSON object, or when the result needs more
        than `max_pages` pages: a partial or unreadable list would read as
        "nothing else matched".
        """
        body: dict[str, object] = {
            "jql": jql,
            "fields": list(fields),
            "maxResults": SEARCH_PAGE_SIZE,
        }
        if expand:
            body["expand"] = expand
        issues: list[dict[str, object]] = []
        for _ in range(max_pages):
            page = self.request("POST", "/rest/api/3/search/jql", body)
            if not isinstance(page, dict):
                raise JiraError(
                    f"a busca do Jira devolveu algo que não é JSON: {page!r:.200}"
                )
            issues.extend(json_objects(page.get("issues")))
            token = page.get("nextPageToken")
            if page.get("isLast") or not token:
                return issues
            body = {**body, "nextPageToken": token}
        raise JiraError(f"a busca '{jql}' passou de {max_pages} páginas; confira a JQL")


def status_name(fields: dict[str, object]) -> str:
    return str(json_object(fields.get("status")).get("name", ""))


def move_to_status(client: JiraClient, key: str, status: str) -> bool:
    """Transition `key` to `status`. Returns False when it is already there.

    The transition is found by the status it leads to, then by its own name:
    in TA the transition "Feito" leads to the status "Em Dev".
    """
    current = status_name(client.get_issue(key, ("status",)))
    if current == status:
        return False
    payload = client.request("GET", f"/rest/api/3/issue/{key}/transitions")
    options = json_objects(json_object(payload).get("transitions"))

    def target(transition: dict[str, object]) -> object:
        return json_object(transition.get("to")).get("name")

    chosen = next((t for t in options if target(t) == status), None) or next(
        (t for t in options if t.get("name") == status), None
    )
    if chosen is None:
        names = ", ".join(f"{t.get('name')} -> {target(t)}" for t in options)
        raise JiraError(
            f"{key} está em '{current}' e nenhuma transição leva a '{status}'. "
            f"Transições disponíveis: {names or 'nenhuma'}"
        )
    client.request(
        "POST",
        f"/rest/api/3/issue/{key}/transitions",
        {"transition": {"id": str(chosen["id"])}},
    )
    return True
