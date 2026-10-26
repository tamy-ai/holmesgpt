import subprocess
from pathlib import Path

import pytest

from tamy.code.reader import CodeError, list_dir, read_file, search


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "dre.py").write_text("def dre():\n    return 1\n\n# CMV aqui\n")
    (tmp_path / ".env").write_text("SECRET=1\n")
    (tmp_path / "chave.pem").write_text("-----BEGIN-----\n")
    (tmp_path / "outside.txt").write_text("fora")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], check=True
    )
    return tmp_path


def test_a_file_is_read_with_line_numbers(repo: Path) -> None:
    text = read_file(repo, "backend/dre.py")
    assert "1: def dre():" in text and "4: # CMV aqui" in text


def test_a_range_of_lines_can_be_asked_for(repo: Path) -> None:
    text = read_file(repo, "backend/dre.py", start=2, end=2)
    assert "2:     return 1" in text and "def dre" not in text


@pytest.mark.parametrize("path", ["../outside.txt", "/etc/passwd", "backend/../../x", ".git/config"])
def test_a_path_outside_the_code_is_refused(repo: Path, path: str) -> None:
    with pytest.raises(CodeError):
        read_file(repo, path)


@pytest.mark.parametrize("path", [".env", "chave.pem"])
def test_a_secret_file_is_refused_even_inside_the_repo(repo: Path, path: str) -> None:
    with pytest.raises(CodeError):
        read_file(repo, path)


def test_a_symlink_that_leaves_the_repo_is_refused(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    outside = tmp_path_factory.mktemp("o") / "s.txt"
    outside.write_text("segredo")
    (repo / "link.txt").symlink_to(outside)
    with pytest.raises(CodeError):
        read_file(repo, "link.txt")


def test_a_directory_lists_its_entries_and_hides_secrets(repo: Path) -> None:
    names = list_dir(repo, "")
    assert "backend/" in names and ".env" not in names and "chave.pem" not in names and ".git" not in names


def test_search_finds_lines_with_file_and_number(repo: Path) -> None:
    hits = search(repo, "CMV")
    assert "backend/dre.py:4:" in hits


def test_search_never_returns_a_secret_file(repo: Path) -> None:
    assert ".env" not in search(repo, "SECRET")


def test_a_search_pattern_cannot_become_a_git_option(repo: Path) -> None:
    result = search(repo, "--open-files-in-pager=touch /tmp/x")
    assert "no matches" in result.lower() or result == ""
