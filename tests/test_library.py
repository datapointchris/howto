"""The library checkout: the first-run clone, the background pull, and the verbs over it."""

import subprocess
import time

import pytest

from howto import library


def git_in(cwd, *args):
    subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', *args], cwd=cwd, check=True)


def upstream_with_a_card(tmp_path):
    upstream = tmp_path / 'upstream'
    upstream.mkdir()
    subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=upstream, check=True)
    (upstream / 'cards').mkdir()
    (upstream / 'cards' / 'a-card.md').write_text('# A Card\n')
    git_in(upstream, 'add', '-A')
    git_in(upstream, 'commit', '-qm', 'seed')
    return upstream


def test_a_missing_checkout_says_what_to_clone(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(library, 'LIBRARY_DIR', tmp_path / 'absent')

    assert library.cmd_status() == 1

    err = capsys.readouterr().err
    assert 'git clone' in err
    assert str(tmp_path / 'absent') in err


def test_status_reports_uncommitted_work(tmp_path, monkeypatch, capsys):
    """Authoring happens in the checkout, so "did I commit that card" is a real
    question with an answer that is otherwise a `cd` away."""
    monkeypatch.setattr(library, 'LIBRARY_DIR', tmp_path)
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    (tmp_path / 'cards').mkdir()
    (tmp_path / 'cards' / 'new-card.md').write_text('# New Card\n')

    assert library.cmd_status() == 0

    out = capsys.readouterr().out
    assert 'uncommitted' in out
    assert 'cards/' in out


def test_the_library_is_cloned_on_first_use_and_only_then(tmp_path, monkeypatch):
    target = tmp_path / 'library'
    monkeypatch.setattr(library, 'LIBRARY_DIR', target)
    monkeypatch.setattr(library, 'LIBRARY_REMOTE', str(upstream_with_a_card(tmp_path)))

    assert library.ensure_cloned() is True
    assert (target / 'cards' / 'a-card.md').exists()

    monkeypatch.setattr(library, 'LIBRARY_REMOTE', 'file:///nowhere-that-exists')
    assert library.ensure_cloned() is True


def test_a_non_empty_directory_is_left_alone(tmp_path, monkeypatch):
    """Files git did not put there are not howto's to adopt or overwrite."""
    target = tmp_path / 'library'
    target.mkdir()
    (target / 'mine.md').write_text('# Mine\n')
    monkeypatch.setattr(library, 'LIBRARY_DIR', target)

    assert library.ensure_cloned() is False
    assert (target / 'mine.md').exists()


def test_a_failed_clone_warns_rather_than_stopping_the_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(library, 'LIBRARY_DIR', tmp_path / 'library')
    monkeypatch.setattr(library, 'LIBRARY_REMOTE', str(tmp_path / 'not-a-repo'))

    assert library.ensure_cloned() is False
    assert 'could not clone' in capsys.readouterr().err


def settled(predicate, seconds=10.0):
    """Wait for the detached pull, which by design is never waited on."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def synced(tmp_path, monkeypatch):
    """An upstream and a checkout of it."""
    upstream = upstream_with_a_card(tmp_path)
    checkout = tmp_path / 'library'
    subprocess.run(['git', 'clone', '-q', str(upstream), str(checkout)], check=True)
    monkeypatch.setattr(library, 'LIBRARY_DIR', checkout)
    return upstream, checkout


def test_a_card_written_upstream_arrives_without_anyone_running_sync(synced, capsys):
    upstream, checkout = synced
    (upstream / 'cards' / 'later.md').write_text('# Later\n')
    git_in(upstream, 'add', '-A')
    git_in(upstream, 'commit', '-qm', 'a second card')

    assert library.autosync() is True
    assert settled(lambda: (checkout / 'cards' / 'later.md').exists())
    assert settled(lambda: not library.SYNC_LOCK.exists())

    assert library.autosync() is True
    assert capsys.readouterr().err == ''


def test_a_pull_already_in_flight_is_not_started_twice_unless_its_lock_is_stale(synced, monkeypatch):
    """Two runs at once would otherwise collide on git's index.lock. A pull
    killed mid-flight leaves the lock behind, and must not stop syncing forever."""
    library.SYNC_LOCK.mkdir(parents=True)

    assert library.autosync() is False

    monkeypatch.setattr(library, 'STALE_LOCK_SECONDS', 0)
    assert library.autosync() is True


def test_a_preview_or_a_help_screen_does_not_pull(synced):
    """A preview redraws on every keystroke. Typer runs the root callback before
    answering any --help, so without this every help screen starts a pull."""
    for argv in (
        ['howto', '__preview', 'card', 'a-card'],
        ['howto', 'labs', '__render', 'a-lab'],
        ['howto', '--help'],
        ['howto', 'cards', 'show', '-h'],
    ):
        assert library.autosync(argv=argv) is False, argv

    assert library.autosync(argv=['howto', 'find']) is True


def test_an_unfinished_card_is_not_the_price_of_a_background_sync(synced):
    """`--ff-only` is what makes this safe to point at a checkout you author in."""
    upstream, checkout = synced
    (upstream / 'cards' / 'a-card.md').write_text('# A Card, upstream\n')
    git_in(upstream, 'add', '-A')
    git_in(upstream, 'commit', '-qm', 'upstream edit')

    mine = checkout / 'cards' / 'a-card.md'
    mine.write_text('# A Card, half written\n')

    assert library.autosync() is True
    assert settled(lambda: library.SYNC_LOG.exists() and library.SYNC_LOG.read_text().strip())
    assert mine.read_text() == '# A Card, half written\n'


def test_a_background_failure_is_reported_until_a_sync_by_hand_clears_it(synced, capsys):
    library.SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    library.SYNC_LOG.write_text('fatal: could not read from remote repository\n')

    library.report_last_sync_failure()
    err = capsys.readouterr().err
    assert 'last failed to sync' in err
    assert 'howto library sync' in err

    assert library.cmd_sync() == 0
    library.report_last_sync_failure()
    assert 'last failed to sync' not in capsys.readouterr().err
