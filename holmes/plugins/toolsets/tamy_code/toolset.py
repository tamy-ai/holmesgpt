"""Read-only tools over a clone of the Tamy product code (`tamy.code.reader` holds the rules).

The clone lives in CODE_ROOT (default /app/code) and the entrypoint keeps it on `main`, the
branch that runs in production. Nothing here writes, runs or reaches the network.
"""

from __future__ import annotations

import os
from pathlib import Path
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
from tamy.code import reader
from tamy.code.budget import Budget

CODE_CALLS_PER_CONVERSATION = int(os.environ.get("CODE_CALLS_PER_CONVERSATION", "8"))
_budget = Budget(limit=CODE_CALLS_PER_CONVERSATION, window_s=900)
OUT_OF_BUDGET = (
    "Orçamento de leitura de código acabou nesta conversa. Pare de buscar e responda agora com o que "
    "já leu, citando arquivo:linha só do que você leu, e diga o que ficou sem conferir."
)


def _root() -> Path:
    return Path(os.environ.get("CODE_ROOT", "/app/code"))


def _result(params: dict, run, context: ToolInvokeContext | None = None) -> StructuredToolResult:
    key = str(((context.request_context or {}) if context else {}).get("conversation_id") or "all")
    if not _budget.spend(key):
        return StructuredToolResult(status=StructuredToolResultStatus.ERROR, error=OUT_OF_BUDGET, params=params)
    try:
        data = run()
    except reader.CodeError as error:
        return StructuredToolResult(status=StructuredToolResultStatus.ERROR, error=str(error), params=params)
    return StructuredToolResult(status=StructuredToolResultStatus.SUCCESS, data=data, params=params)


class ReadFile(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tamy_code_read",
            description="Read a file of the Tamy code (branch main, what runs in production), with line numbers.",
            parameters={
                "path": ToolParameter(description="Path from the repository root", type="string", required=True),
                "start": ToolParameter(description="First line, default 1", type="integer", required=False),
                "end": ToolParameter(description="Last line, at most 400 lines per call", type="integer", required=False),
            },
        )

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        return _result(
            params,
            lambda: reader.read_file(
                _root(), str(params["path"]), int(params.get("start") or 1), int(params["end"]) if params.get("end") else None
            ),
            context,
        )

    def get_parameterized_one_liner(self, params: dict) -> str:
        return f"Code: read {params.get('path', '')}"


class ListDir(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tamy_code_list",
            description="List a folder of the Tamy code. Empty path is the repository root.",
            parameters={"path": ToolParameter(description="Folder path", type="string", required=False)},
        )

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        return _result(params, lambda: reader.list_dir(_root(), str(params.get("path") or "")), context)

    def get_parameterized_one_liner(self, params: dict) -> str:
        return f"Code: list {params.get('path', '') or '/'}"


class SearchCode(Tool):
    def __init__(self) -> None:
        super().__init__(
            name="tamy_code_search",
            description="Search the Tamy code with a regular expression (git grep). Returns file:line: text.",
            parameters={
                "pattern": ToolParameter(description="Regular expression, for example 'def total_sales'", type="string", required=True),
                "path": ToolParameter(description="Folder to search, default the whole repository", type="string", required=False),
            },
        )

    def _invoke(self, params: dict, context: ToolInvokeContext) -> StructuredToolResult:
        return _result(params, lambda: reader.search(_root(), str(params["pattern"]), str(params.get("path") or "")), context)

    def get_parameterized_one_liner(self, params: dict) -> str:
        return f"Code: search {params.get('pattern', '')}"


class TamyCodeToolset(Toolset):
    def __init__(self) -> None:
        super().__init__(
            name="tamy/code",
            description="Read the Tamy product code to point at the cause of a bug",
            icon_url="https://platform.robusta.dev/demos/github.svg",
            prerequisites=[CallablePrerequisite(callable=self.prerequisites_callable)],
            tools=[ReadFile(), ListDir(), SearchCode()],
            tags=[ToolsetTag.CORE],
            enabled=False,
        )

    def prerequisites_callable(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        if not (_root() / ".git").exists():
            return False, f"No code clone in {_root()}"
        return True, ""
