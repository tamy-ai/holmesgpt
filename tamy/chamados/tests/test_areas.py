"""Where a problem lives: the channel the person used and the screen or feature.

Both come from a closed list. A Jira label made of free text splits one problem
into twenty spellings, and a code pointer made of free text points nowhere.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tamy.chamados.areas import (
    AREAS,
    Channel,
    area_by_slug,
    area_label,
    channel_label,
    clean_area,
    clean_channel,
)

# The code the areas point to lives in the Tamy Consultant, not in this repository. Set
# `TAMY_CONSULTANT_PATH` to a checkout of it to check that every pointer still exists.
_CONSULTANT = os.environ.get("TAMY_CONSULTANT_PATH")
REPO_ROOT = Path(_CONSULTANT) if _CONSULTANT else None


def test_the_slugs_are_unique_and_safe_for_a_jira_label() -> None:
    slugs = [area.slug for area in AREAS]

    assert len(slugs) == len(set(slugs))
    assert all(
        slug.replace("-", "").isalnum() and slug == slug.lower() for slug in slugs
    )


@pytest.mark.parametrize("area", AREAS, ids=lambda area: area.slug)
def test_every_code_pointer_exists_in_the_repository(area) -> None:  # type: ignore[no-untyped-def]
    """A pointer to a file that moved sends the developer to nothing."""
    if REPO_ROOT is None:
        pytest.skip("TAMY_CONSULTANT_PATH is not set")
    for path in area.code_paths:
        assert (REPO_ROOT / path).exists(), f"{area.slug}: {path}"


def test_only_the_catch_all_area_has_no_code_pointer() -> None:
    assert [a.slug for a in AREAS if not a.code_paths] == ["outro"]


def test_every_area_names_a_dashboard_that_exists() -> None:
    uids = {
        "tamy-api-performance",
        "tamy-chat-performance",
        "tamy-background-performance",
    }

    assert {area.dashboard_uid for area in AREAS} <= uids


def test_the_classifier_values_are_cleaned_to_the_closed_lists() -> None:
    assert clean_area(" Dre ") == "dre"
    assert clean_area("tela do dre, com R$ 9") is None
    assert clean_area(None) is None
    assert clean_channel("WhatsApp") is Channel.WHATSAPP
    assert clean_channel("celular") is None
    assert clean_channel(3) is None


def test_the_words_the_team_reads() -> None:
    assert area_label("dre") == "DRE"
    assert channel_label(Channel.APP) == "App no celular"
    assert area_by_slug("nao-existe") is None
