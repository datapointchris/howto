"""The library checkout — cards, Labs and the tool registry — and keeping it current.

The library is authored far more often than howto is released, so it does not
ship inside howto. It is a git checkout under `$XDG_DATA_HOME/terminal-library/`,
which means writing a card and having a card are the same act on every machine
— the tldr model, where pages live upstream and the client fetches them.

Not `howto update`: that verb is reserved for a tool updating *itself*. The
library and the binary are two different things to bring up to date, and giving
them one word would make "did you update?" an ambiguous question.

howto clones it on first use, so a new machine needs no setup step that can be
forgotten — which is the whole reason the remote is named here rather than left
to the checkout. `sync` afterwards asks git where it came from, so a fork or a
moved remote keeps working without this constant being right forever.

The clone happens once; the pull happens on every run, detached and never waited
on. A tool that *waited* on the network every command would be one you stopped
running, but nothing here waits: the command returns at its own speed and the
cards are current by the next one, which is what makes `sync` a verb nobody has
to remember.

The outcome of the last background pull is cache, not state. It is one line,
rebuilt by the next pull, and losing it costs one warning that the next run
would have printed anyway.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from rich.text import Text

from howto.editor import open_in_editor
from howto.paths import cache_dir
from howto.paths import library_dir
from howto.paths import library_source
from howto.render import console
from howto.render import error_console

LIBRARY_DIR = library_dir()

# The subdirectories `edit` looks in, in the order it looks.
EDITABLE = ('cards', 'labs')

SYNC_LOG = cache_dir() / 'library-sync.log'
SYNC_LOCK = SYNC_LOG.with_name(SYNC_LOG.name + '.lock')

# Long enough that no real pull is mistaken for a dead one, short enough that a
# machine killed mid-pull is syncing again the same session.
STALE_LOCK_SECONDS = 5 * 60

# Commands another program drives, where "once per run" is not once per command:
# an fzf preview pane redraws on every keystroke. Everything else is a person
# typing, which is exactly when a pull is free.
MACHINE_DRIVEN = frozenset({'__preview', '__render'})

# Asking what a command does is not asking howto to do anything. A help screen
# reads no cards, so a pull started for one is work nobody asked for.
HELP_FLAGS = frozenset({'--help', '-h'})

# Where the library comes from on a machine that has none yet. Overridable so a
# fork, a mirror, or a test can point somewhere else without patching code.
LIBRARY_REMOTE = os.environ.get('HOWTO_LIBRARY_REMOTE') or 'https://github.com/datapointchris/terminal-library.git'


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=False)


def is_checkout(path: Path) -> bool:
    return (path / '.git').exists()


def remote_url(path: Path) -> str:
    result = git('remote', 'get-url', 'origin', cwd=path)
    return result.stdout.strip() if result.returncode == 0 else ''


def ensure_cloned() -> bool:
    """Clone the library on a machine that has none. True if it is there now.

    Called on every invocation, so the common path is one `exists()` and no
    process spawn. A failure is a warning rather than an error: the shell
    collections — functions, aliases, keys — need no library, and refusing to
    search them because a clone failed would be the tail wagging the dog.
    """
    if is_checkout(LIBRARY_DIR):
        return True
    if LIBRARY_DIR.exists() and any(LIBRARY_DIR.iterdir()):
        # Something is already there that git did not put there. Adopting it
        # would mean deciding whose files win, which is not howto's call.
        return False
    error_console.print(Text(f'Fetching the library into {LIBRARY_DIR}…'), soft_wrap=True)
    LIBRARY_DIR.parent.mkdir(parents=True, exist_ok=True)
    result = git('clone', '--quiet', LIBRARY_REMOTE, str(LIBRARY_DIR))
    if result.returncode != 0:
        error_console.print(Text(f'  could not clone {LIBRARY_REMOTE}:'), soft_wrap=True)
        error_console.print(Text(f'  {(result.stderr or result.stdout).strip().splitlines()[0]}'), soft_wrap=True)
        return False
    return True


def record_sync() -> None:
    """Mark the library as synced now, with no failure outstanding."""
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    SYNC_LOG.write_text('')


def worth_a_pull(argv: list[str]) -> bool:
    """Whether this invocation is one where fetching the library earns its cost.

    Two ways it does not: another program is driving, so "once per run" is not
    once per command; or the line asks for help, which reads no cards at all.
    """
    return MACHINE_DRIVEN.isdisjoint(argv) and HELP_FLAGS.isdisjoint(argv)


def claim_sync() -> bool:
    """True if no pull is already in flight, having claimed the right to start one.

    An atomic mkdir rather than a flag file anyone checks then writes: two howto
    commands started together would both find it absent and both pull, and the
    loser dies on git's own index.lock with a message that reads like a real
    failure of the remote.
    """
    try:
        SYNC_LOCK.mkdir(parents=True)
        return True
    except FileExistsError:
        pass
    try:
        held_for = time.time() - SYNC_LOCK.stat().st_mtime
    except OSError:
        return False
    if held_for < STALE_LOCK_SECONDS:
        return False
    # A pull killed mid-flight leaves the lock behind, and without this nothing
    # would ever sync again on this machine.
    try:
        SYNC_LOCK.rmdir()
        SYNC_LOCK.mkdir()
    except OSError:
        return False
    return True


def report_last_sync_failure() -> None:
    """Say that the last background pull failed, since nothing else can.

    A detached pull has nowhere to print. Cards that quietly stopped updating
    read as cards that stopped changing, and the reader concludes there is
    nothing new.
    """
    try:
        last = SYNC_LOG.read_text().strip()
    except OSError:
        return
    if not last:
        return
    error_console.print(Text(f'The library last failed to sync: {last.splitlines()[0]}'), soft_wrap=True)
    error_console.print(Text('  retry with howto library sync', style='cyan'), soft_wrap=True)


def autosync(argv: list[str] | None = None) -> bool:
    """Pull the library on every run, in the background. True if a pull started.

    Detached and never waited on: the cards are current by the time you read one
    without anything having waited for the network, and a pull against a dead
    route costs the command nothing.
    """
    if not is_checkout(LIBRARY_DIR):
        return False
    report_last_sync_failure()
    if not worth_a_pull(sys.argv if argv is None else argv):
        return False
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not claim_sync():
        return False
    # The log is the only channel a detached child has: it keeps git's stderr on
    # failure and is emptied on success, so "non-empty" means "the last pull
    # failed" without this having to wait around for an exit status.
    #
    # `--ff-only` is what makes this safe to point at a checkout cards are
    # authored in. It refuses rather than merging, and git declines to overwrite
    # a modified file, so an unfinished card is never the price of a sync.
    subprocess.Popen(
        [
            'sh',
            '-c',
            'git pull --ff-only --quiet 2>"$1" && : >"$1"; rmdir "$2"',
            'sh',
            str(SYNC_LOG),
            str(SYNC_LOCK),
        ],
        cwd=LIBRARY_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


def explain_missing() -> int:
    """Say there is no checkout, and print the clone to run by hand.

    The command names `LIBRARY_REMOTE`, the remote the clone on first run uses,
    so running it by hand repeats that clone and nothing else.
    `$HOWTO_LIBRARY_REMOTE` points both at a fork or a mirror.
    """
    # soft_wrap: a path rich has wrapped mid-way is a path you cannot copy, and
    # the whole point of this message is the command underneath it.
    error_console.print(Text(f'No library checkout at {LIBRARY_DIR}.'), soft_wrap=True)
    error_console.print('howto clones it on first run; if that failed, do it by hand:')
    error_console.print(Text(f'  git clone {LIBRARY_REMOTE} {LIBRARY_DIR}', style='cyan'), soft_wrap=True)
    return 1


def cmd_sync() -> int:
    """Fast-forward the library checkout."""
    if not is_checkout(LIBRARY_DIR):
        return explain_missing()
    result = git('pull', '--ff-only', cwd=LIBRARY_DIR)
    if result.returncode != 0:
        error_console.print(Text(f'git pull failed in {LIBRARY_DIR}:'))
        error_console.print(Text(f'  {(result.stderr or result.stdout).strip().splitlines()[0]}'))
        return 1
    # Doing it by hand clears a past failure that would otherwise keep being
    # reported at a problem the person just fixed.
    record_sync()
    console.print(Text.from_markup('[green]✓[/] ') + Text(result.stdout.strip() or 'Already up to date.'))
    return 0


def cmd_status() -> int:
    """Where the library is, where it came from, and whether it is dirty.

    Authoring happens in this checkout, so "have I committed the card I wrote"
    is a question with a real answer that is otherwise a `cd` away.
    """
    if not is_checkout(LIBRARY_DIR):
        return explain_missing()
    console.print(Text(f'path    {LIBRARY_DIR}  (from {library_source()})'), soft_wrap=True)
    console.print(Text(f'remote  {remote_url(LIBRARY_DIR) or "(none)"}'), soft_wrap=True)
    dirty = git('status', '--porcelain', cwd=LIBRARY_DIR).stdout.strip()
    if not dirty:
        console.print(Text.from_markup('[green]✓[/] nothing uncommitted'))
        return 0
    console.print(Text(f'{len(dirty.splitlines())} uncommitted change(s)', style='yellow'))
    for line in dirty.splitlines():
        console.print(Text(f'  {line}'), no_wrap=True, overflow='ellipsis')
    return 0


def cmd_path() -> int:
    """The checkout path, for scripting. One line, nothing else."""
    print(LIBRARY_DIR)
    return 0


def cmd_edit(what: str) -> int:
    for subdir in EDITABLE:
        candidate = LIBRARY_DIR / subdir / f'{what.removesuffix(".md")}.md'
        if candidate.exists():
            open_in_editor(candidate)
            return 0
    error_console.print(Text(f'No card or Lab named {what!r} under {LIBRARY_DIR}.'))
    return 1


LIBRARY_HELP = """The library checkout: cards, Labs and the tool registry.

Examples:

```text
howto library status           where it is, and anything uncommitted
howto library sync             pull the latest cards, Labs and registry now
howto library edit git-rebase  open a card or Lab in $EDITOR by its id
cd "$(howto library path)"     go to the checkout to commit what you wrote
```
"""

app = typer.Typer(name='library', no_args_is_help=True, help=LIBRARY_HELP)


@app.command('sync')
def sync_command() -> None:
    """Fetch the latest cards, Labs and registry.

    Examples:

    ```text
    howto library sync             pick up a card written on another machine
    ```
    """
    raise typer.Exit(cmd_sync())


@app.command('status')
def status_command() -> None:
    """Where the library lives and whether anything is uncommitted.

    Examples:

    ```text
    howto library status           check for cards written but not yet committed
    ```
    """
    raise typer.Exit(cmd_status())


@app.command('path')
def path_command() -> None:
    """Print the library checkout path.

    Examples:

    ```text
    cd "$(howto library path)"     go to the checkout to commit or push
    ```
    """
    raise typer.Exit(cmd_path())


@app.command('edit')
def edit_command(
    what: Annotated[str, typer.Argument(help='A card or Lab id.')],
) -> None:
    """Open a card or Lab in $EDITOR, wherever it lives.

    Examples:

    ```text
    howto library edit git-rebase  edit a card without knowing its directory
    howto library edit git-stash   the same for a Lab
    ```
    """
    raise typer.Exit(cmd_edit(what))
