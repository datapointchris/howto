"""The picker's line format and where a pick ends up.

fzf is never launched. It needs a TTY, so a test that spawned it would hang on
the picker rather than fail; `run_fzf` is stubbed with the row a human would have
landed on, which is the only part of the interaction that matters here.

What is asserted hardest is the split between the two terminal acts. `find` hands
its pick to the composite renderer and `choose` prints one line to stdout, and a
`$(howto choose)` that captured a rule, a color or a second line would put that
on the command line verbatim.
"""

import os
import shlex
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from howto import find
from howto import index
from howto.cli import app as cli_app

runner = CliRunner()

ENTRIES = [
    index.Entry(source='tool', name='ripgrep', invocation='rg [pattern] [path]', description='Ultra-fast recursive grep'),
    index.Entry(source='alias', name='ll', invocation='ll', description='List files', command='eza -l'),
]


@pytest.fixture
def picks(monkeypatch):
    """Answer the picker with one canned row, and record how it was called."""
    calls = {}

    def choose(row: str | None):
        def stub(lines, query, header):
            calls.update(lines=lines, query=query, header=header)
            return row

        monkeypatch.setattr(find, 'run_fzf', stub)
        return calls

    monkeypatch.setattr(index, 'build_index', lambda sources=None: list(ENTRIES))
    return choose


def test_a_row_carries_its_invocation_past_fzf():
    """`--with-nth=1` hides field four, so it costs nothing to send it through
    and saves resolving the name a second time on the other side."""
    fields = find.index_lines(ENTRIES)[0].split('\t')

    assert fields[0] == ENTRIES[0].display()
    assert fields[1:] == ['tool', 'ripgrep', 'rg [pattern] [path]']
    assert '--with-nth=1' in find.FZF_COMMON


def test_choosing_prints_the_invocation_and_nothing_else(picks, capsys):
    """The row is `ripgrep` and the answer is `rg`: a registry key is a package
    name as often as a command, and printing the name would put something you
    cannot type on the line."""
    picks(find.index_lines(ENTRIES)[0])

    assert find.cmd_choose('', None) == 0

    captured = capsys.readouterr()
    assert captured.out == 'rg [pattern] [path]\n'
    assert captured.err == ''


def test_backing_out_of_the_picker_is_not_an_error(picks, capsys):
    picks('')

    assert find.cmd_choose('', None) == 0
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('command', [find.cmd_choose, find.cmd_find])
def test_a_missing_picker_is_a_failure_rather_than_a_cancelled_pick(monkeypatch, capsys, command):
    """`choose` is read back through `$(...)`, where exit status is the only
    signal the caller gets."""
    monkeypatch.setattr(index, 'build_index', lambda sources=None: list(ENTRIES))
    monkeypatch.setattr(find.shutil, 'which', lambda binary: None)

    assert command('', None) == 1

    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'fzf is not installed' in captured.err


def fzf_exiting(directory: Path, code: int, said: str) -> None:
    """Put an `fzf` on PATH that prints `said` to stderr and exits `code`, as the real one does without a terminal."""
    stub = directory / 'fzf'
    stub.write_text(f'#!/bin/sh\ncat > /dev/null\nprintf %s {shlex.quote(said)} >&2\nexit {code}\n')
    stub.chmod(0o755)


def test_a_picker_that_cannot_run_is_a_failure_that_says_why(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(index, 'build_index', lambda sources=None: list(ENTRIES))
    fzf_exiting(tmp_path, 2, 'inappropriate ioctl for device')
    monkeypatch.setenv('PATH', f'{tmp_path}{os.pathsep}{os.environ["PATH"]}')

    assert find.cmd_choose('', None) == 1

    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'inappropriate ioctl for device' in captured.err
    assert 'howto list --json' in captured.err


@pytest.mark.parametrize('code', [1, 130])
def test_no_match_and_esc_are_still_a_pick_of_nothing(tmp_path, monkeypatch, capsys, code):
    monkeypatch.setattr(index, 'build_index', lambda sources=None: list(ENTRIES))
    fzf_exiting(tmp_path, code, '')
    monkeypatch.setenv('PATH', f'{tmp_path}{os.pathsep}{os.environ["PATH"]}')

    assert find.cmd_find('', None) == 0
    assert capsys.readouterr().err == ''


def test_list_through_a_pipe_keeps_every_row_whole(monkeypatch):
    """A row cut to the terminal width drops the tags at its end, which are what
    a `howto list | rg` is searching for."""
    entry = index.Entry(
        source='tool',
        name='ripgrep',
        invocation='rg [pattern] [path]',
        description='Ultra-fast recursive grep that respects gitignore by default',
        tags=('search', 'gitignore-aware'),
    )
    monkeypatch.setattr(index, 'build_index', lambda sources=None: [entry])

    result = runner.invoke(cli_app, ['list'])

    assert result.exit_code == 0
    assert len(entry.display()) > 80
    assert result.output == entry.display() + '\n'


def test_finding_opens_the_composite_for_the_name_picked(monkeypatch, picks):
    picks(find.index_lines(ENTRIES)[1])
    shown = []
    monkeypatch.setattr(find, 'cmd_show', lambda subject: shown.append(subject) or 0)

    assert find.cmd_find('', None) == 0
    assert shown == ['ll']


def test_the_preview_builds_only_the_collection_it_was_given(monkeypatch):
    """It runs once per keystroke, and building every collection to render one
    row asks zsh for its keymaps each time. That subprocess is an interactive
    shell, which takes the terminal from the picker that spawned it."""
    asked = []

    def record(sources=None):
        asked.append(sources)
        return list(ENTRIES)

    monkeypatch.setattr(index, 'build_index', record)

    with pytest.raises(typer.Exit):
        find.preview_command('alias', 'll')

    assert asked == [['alias']]


def test_an_empty_index_says_how_to_fill_it(monkeypatch, capsys):
    monkeypatch.setattr(index, 'build_index', lambda sources=None: [])

    assert find.cmd_choose('', None) == 1
    assert 'howto library sync' in capsys.readouterr().err


def test_an_unknown_source_is_a_usage_error():
    result = runner.invoke(cli_app, ['find', '--source', 'nonsense'])

    assert result.exit_code == 2
    assert 'nonsense' in result.output
