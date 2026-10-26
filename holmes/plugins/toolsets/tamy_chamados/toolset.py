"""Tamy tickets as a native Holmes toolset (tamy-consultant decision 0752).

The model picks the fields, the code in `tamy.chamados` decides: checklist, deadline, labels,
description, one ticket per Slack thread, no duplicate. Three tools:

- `tamy_preview_ticket` and `tamy_find_similar_tickets` only read;
- `tamy_create_ticket` writes to Jira, and ALWAYS asks for the click of who asked
  (`approval_required_tools`), whatever the config says.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

from holmes.core.tools import (
    CallablePrerequisite,
    StructuredToolResult,
    StructuredToolResultStatus,
    Tool,
    ToolInvokeContext,
    ToolParameter,
    Toolset,
    ToolsetTag,
)
from tamy.chamados import cli
from tamy.chamados.jira_rest import JIRA_SITE_URL, JiraClient

_PARAMS: Dict[str, ToolParameter] = {
    "ticket_type": ToolParameter(
        description="bug, incident, improvement, feature, support, access, question or task",
        type="string",
        required=True,
    ),
    "priority": ToolParameter(description="P0, P1, P2 or P3", type="string", required=True),
    "summary": ToolParameter(
        description="Title: 'Area: what is wrong or asked', one line, in Portuguese",
        type="string",
        required=True,
    ),
    "answers_json": ToolParameter(
        description=(
            "JSON object with the checklist answers by question id, in Portuguese "
            "(see the skill of the type). Example: {\"bug_client\": \"Martita, loja 3\"}"
        ),
        type="string",
        required=True,
    ),
    "client": ToolParameter(description="The client named, as written", type="string", required=False),
    "area": ToolParameter(description="Area slug (see skill chamado-regras)", type="string", required=False),
    "channel": ToolParameter(description="web, app or whatsapp", type="string", required=False),
    "thread_ref": ToolParameter(
        description="Slack channel and thread, as CHANNEL-TS (e.g. C0123-1700000000.0001)",
        type="string",
        required=False,
    ),
    "requester": ToolParameter(description="Who asked, first name", type="string", required=False),
    "thread_url": ToolParameter(description="Link to the Slack thread", type="string", required=False),
    "priority_reason": ToolParameter(
        description="One sentence: the fact that decided the priority", type="string", required=False
    ),
    "acceptance": ToolParameter(
        description="Acceptance criteria of the case, one per line, 'Dado..., quando..., então...'",
        type="string",
        required=False,
    ),
}


def _item(params: dict) -> cli.TicketInput:
    try:
        answers = json.loads(params.get("answers_json") or "{}")
    except json.JSONDecodeError:
        answers = {}
    return cli.TicketInput(
        ticket_type=str(params.get("ticket_type", "")),
        priority=str(params.get("priority", "")),
        summary=str(params.get("summary", "")),
        client=str(params.get("client", "")),
        answers=answers if isinstance(answers, dict) else {},
        area=str(params.get("area", "")),
        channel=str(params.get("channel", "")),
        thread_ref=str(params.get("thread_ref", "")),
        requester=str(params.get("requester", "")),
        thread_url=str(params.get("thread_url", "")),
        priority_reason=str(params.get("priority_reason", "")),
        acceptance=str(params.get("acceptance", "")),
        not_a_duplicate=str(params.get("not_a_duplicate", "")).lower() == "true",
    )


def _ok(data: str, params: dict) -> StructuredToolResult:
    return StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=data, params=params)


class PreviewTicket(Tool):
    toolset: "TamyChamadosToolset" = None  # type: ignore

    def __init__(self, toolset: "TamyChamadosToolset"):
        super().__init__(
            name="tamy_preview_ticket",
            description=(
                "Dry run of a Tamy ticket: says what is missing from the checklist and shows the "
                "deadline, labels and description that would be created. Writes nothing. Call it "
                "before tamy_create_ticket."
            ),
            parameters=dict(_PARAMS),
        )
        self.toolset = toolset

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        return _ok(cli.preview(_item(params)).to_json(), params)

    def get_parameterized_one_liner(self, params: dict) -> str:
        return f"Tamy: preview ticket {params.get('summary', '')}"


class FindSimilar(Tool):
    toolset: "TamyChamadosToolset" = None  # type: ignore

    def __init__(self, toolset: "TamyChamadosToolset"):
        super().__init__(
            name="tamy_find_similar_tickets",
            description="Open tickets of the last 60 days whose text shares the words of a title.",
            parameters={"summary": ToolParameter(description="The title", type="string", required=True)},
        )
        self.toolset = toolset

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        found = cli.similar(str(params.get("summary", "")), self.toolset.client())
        return _ok(json.dumps(found, ensure_ascii=False), params)

    def get_parameterized_one_liner(self, params: dict) -> str:
        return f"Tamy: similar tickets to {params.get('summary', '')}"


class CreateTicket(Tool):
    toolset: "TamyChamadosToolset" = None  # type: ignore

    def __init__(self, toolset: "TamyChamadosToolset"):
        parameters = dict(_PARAMS)
        parameters["not_a_duplicate"] = ToolParameter(
            description="true only after the person saw the similar tickets and said it is different",
            type="boolean",
            required=False,
        )
        super().__init__(
            name="tamy_create_ticket",
            description=(
                "Create the ticket in Jira. Refuses when the checklist is incomplete, when the Slack "
                "thread already has a ticket, or when a similar open ticket exists. Needs the "
                "person's approval."
            ),
            parameters=parameters,
        )
        self.toolset = toolset

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        result = cli.create(_item(params), self.toolset.client())
        payload = json.loads(result.to_json())
        if result.key:
            payload["url"] = f"{JIRA_SITE_URL}/browse/{result.key}"
        return _ok(json.dumps(payload, ensure_ascii=False), params)

    def get_parameterized_one_liner(self, params: dict) -> str:
        return f"Tamy: create ticket {params.get('summary', '')}"


class TamyChamadosToolset(Toolset):
    def __init__(self) -> None:
        super().__init__(
            name="tamy/chamados",
            description="Create Tamy tickets in Jira with the team's rules",
            icon_url="https://platform.robusta.dev/demos/jira.svg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[PreviewTicket(self), FindSimilar(self), CreateTicket(self)],
            tags=[ToolsetTag.CORE],
            enabled=False,
            # The write tool never runs without a click, whatever the config says.
            approval_required_tools=["tamy_create_ticket"],
        )
        self._client: JiraClient | None = None

    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        missing = [k for k in ("JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_GATEWAY_URL") if not os.environ.get(k)]
        if missing:
            return False, f"Missing environment variables: {', '.join(missing)}"
        return True, ""

    def client(self) -> JiraClient:
        if self._client is None:
            self._client = JiraClient(
                os.environ["JIRA_GATEWAY_URL"], os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"]
            )
        return self._client
