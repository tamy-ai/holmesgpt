import pytest

from tamy.chamados import cli


@pytest.fixture(autouse=True)
def _forget_created_tickets() -> None:
    """The process remembers what it created by Slack thread; each test starts clean."""
    cli.forget_created()
