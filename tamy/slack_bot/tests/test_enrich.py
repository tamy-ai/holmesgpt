"""Files of the Slack thread and the links to where a developer looks first (TA-1315)."""

from __future__ import annotations

from typing import Any

from tamy.chamados.jira_rest import MultipartFile
from tamy.slack_bot.enrich import EnrichResult, Links, attach_files, describe, enrich_ticket, files_of, links_for

THREAD_LABEL = "slack-C1-1.0"


def _file(name: str = "print.png", mimetype: str = "image/png", size: int = 1000) -> dict[str, Any]:
    return {"name": name, "mimetype": mimetype, "size": size, "url_private_download": f"https://files.slack.test/{name}"}


def test_files_of_the_people_in_the_thread_are_collected() -> None:
    messages = [
        {"user": "U1", "text": "bug", "files": [_file("a.png"), _file("b.pdf", "application/pdf")]},
        {"user": "U2", "text": "oi"},
    ]

    assert [f.name for f in files_of(messages)] == ["a.png", "b.pdf"]


def test_a_file_of_the_bot_a_huge_file_and_an_odd_type_are_left_out() -> None:
    messages = [
        {"bot_id": "B1", "files": [_file("bot.png")]},
        {"user": "U1", "files": [_file("big.png", size=50_000_000), _file("run.exe", "application/x-msdownload"), _file("ok.csv", "text/csv")]},
    ]

    assert [f.name for f in files_of(messages)] == ["ok.csv"]


def test_at_most_ten_files() -> None:
    messages = [{"user": "U1", "files": [_file(f"f{n}.png") for n in range(15)]}]

    assert len(files_of(messages)) == 10


class FakeJira:
    def __init__(self, labels: list[str]) -> None:
        self.labels, self.attached, self.links = labels, [], []

    def issue_labels(self, key: str) -> list[str]:
        return self.labels

    def add_attachment(self, key: str, file: MultipartFile) -> None:
        self.attached.append((key, file.filename, file.content))

    def add_remote_link(self, key: str, url: str, title: str) -> None:
        self.links.append((key, url, title))


def test_attach_counts_what_went_in_and_what_failed_and_never_raises() -> None:
    files = files_of([{"user": "U1", "files": [_file("a.png"), _file("b.png")]}])

    def download(url: str) -> bytes:
        if url.endswith("b.png"):
            raise OSError("boom")
        return b"bytes"

    jira = FakeJira([THREAD_LABEL])

    assert attach_files(files, download, jira, "TA-1") == (1, 1)
    assert jira.attached == [("TA-1", "a.png", b"bytes")]


def test_the_links_point_to_the_dashboard_of_the_area_the_logs_and_the_traces() -> None:
    links = links_for("vendas", Links(grafana="https://g.test", langfuse="https://l.test", langfuse_project="p1"))

    urls = [url for _, url in links]
    assert any(u.startswith("https://g.test/d/") for u in urls)
    assert any("explore" in u and "loki" in u.lower() for u in urls)
    assert "https://l.test/project/p1/traces" in urls


def test_an_unknown_area_still_gets_logs_and_traces_and_no_made_up_dashboard() -> None:
    links = links_for("area-que-nao-existe", Links(grafana="https://g.test", langfuse="https://l.test", langfuse_project="p1"))

    assert not any("/d/" in url for _, url in links)
    assert len(links) >= 2


def test_nothing_is_attached_to_a_ticket_of_another_thread() -> None:
    jira = FakeJira(["slack-C9-9.9"])
    messages = [{"user": "U1", "files": [_file("a.png")]}]

    result = enrich_ticket("TA-1", "C1", "1.0", messages, lambda url: b"x", jira, "vendas", Links("https://g", "https://l", "p"))

    assert result.skipped and jira.attached == [] and jira.links == []


def test_the_ticket_of_the_thread_gets_its_files_and_links() -> None:
    jira = FakeJira([THREAD_LABEL])
    messages = [{"user": "U1", "files": [_file("a.png")]}]

    result = enrich_ticket("TA-1", "C1", "1.0", messages, lambda url: b"x", jira, "vendas", Links("https://g", "https://l", "p"))

    assert (result.attached, result.failed) == (1, 0)
    assert len(jira.attached) == 1 and len(jira.links) >= 2


def test_the_thread_is_told_what_went_in_and_what_did_not() -> None:
    assert describe(EnrichResult(attached=2, links=3)) == "Anexei 2 arquivos e 3 links ao chamado."
    assert describe(EnrichResult(attached=1, links=3)) == "Anexei 1 arquivo e 3 links ao chamado."
    assert "não consegui anexar 1" in describe(EnrichResult(attached=1, failed=1, links=2))
    assert describe(EnrichResult(links=2)) == "Deixei 2 links no chamado."
    assert describe(EnrichResult(skipped=True)) == ""
