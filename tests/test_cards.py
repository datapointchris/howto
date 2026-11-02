"""Card loading and authoring.

Rendering is bat's and is not asserted here; what matters is which file gets
picked and where a new one lands.
"""

from pathlib import Path

import pytest

from howto import cards

FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'cards'


@pytest.fixture(autouse=True)
def fixture_cards(monkeypatch):
    monkeypatch.setattr(cards, 'CARDS_DIR', FIXTURE_DIR)


def test_load_cards_reads_title_and_tags_and_needs_no_front_matter():
    loaded = cards.load_cards()

    assert set(loaded) == {'tmux-commands', 'no-frontmatter'}
    assert loaded['tmux-commands']['title'] == 'tmux Commands'
    assert loaded['tmux-commands']['tags'] == ['tmux', 'terminal']
    assert loaded['no-frontmatter']['title'] == 'A Card Without Frontmatter'
    assert loaded['no-frontmatter']['tags'] == []


def test_show_accepts_the_filename_a_completion_offers(monkeypatch):
    rendered = []
    monkeypatch.setattr(cards, 'render_body', lambda path, **kwargs: rendered.append(path))

    assert cards.cmd_show('tmux-commands.md') == 0

    assert rendered == [FIXTURE_DIR / 'tmux-commands.md']


def test_an_unknown_card_points_at_the_federated_search(capsys):
    assert cards.cmd_show('nope') == 1

    err = capsys.readouterr().err
    assert 'howto cards list' in err
    assert 'howto find nope' in err


def test_new_writes_into_the_cards_directory_and_never_overwrites(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cards, 'CARDS_DIR', tmp_path)
    monkeypatch.setattr(cards, 'open_in_editor', lambda path: None)

    assert cards.cmd_new('Review And Merge A PR') == 0
    assert (tmp_path / 'review-and-merge-a-pr.md').exists()
    assert 'review-and-merge-a-pr' in cards.load_cards()

    assert cards.cmd_new('Review And Merge A PR') == 1
    assert 'already exists' in capsys.readouterr().err


def test_an_empty_directory_is_not_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cards, 'CARDS_DIR', tmp_path)

    assert cards.cmd_list() == 0
    assert 'howto cards new' in capsys.readouterr().out
