"""The rot report: index rows naming something this machine cannot run.

Invoked as `howto tools unresolved`. Its own module rather than a verb in
`howto.tools`, because it reads the whole index and `howto.index` already
imports `howto.tools` — the other direction would close a cycle.

Three sections, because "this entry is wrong", "you do not have this here" and
"this was never for this machine" are different facts, and only the first is
anyone's to fix.
"""

import json
from collections.abc import Callable
from typing import Annotated

import typer
from rich.text import Text

from howto import index
from howto.render import console


def cmd_unresolved(as_json: bool) -> int:
    """List rows naming something this machine cannot run."""
    verdict = index.classify()
    if as_json:
        print(json.dumps(index.unresolved_rows(verdict.dead), indent=2))
        return 0
    if not verdict.dead and not verdict.absent and not verdict.foreign:
        console.print('[green]✓[/] Every indexed row names something runnable.')
        return 0

    if verdict.dead:
        console.rule('[cyan]Rows naming nothing runnable', align='left')
        print_index_rows(verdict.dead, 'yellow')
        console.print(f'\n  {len(verdict.dead)} rows name something not on PATH, nor a function, alias or forgit shortcut.')
        console.print('  No `requires:` accounts for them, so either the entry is stale or it needs one.')

    # A separate section, not a footnote on the one above. These are correct
    # entries for software this box does not have, so counting them alongside
    # rot is what trains you to stop reading the number.
    if verdict.absent:
        console.print()
        console.rule('[cyan]Rows needing something this machine lacks', align='left')
        print_index_rows(verdict.absent, 'cyan', note=lambda entry: f'needs {entry.requires}')
        console.print(f'\n  {len(verdict.absent)} rows are fine and their prerequisite is not installed here.')

    # Last and dimmest. These need nothing from you on this box, and the only
    # reason to print them at all is so a row that vanished from the two sections
    # above can be found rather than assumed deleted.
    if verdict.foreign:
        console.print()
        console.rule('[cyan]Rows this machine never declared', align='left')
        print_index_rows(verdict.foreign, 'bright_black', note=foreign_note)
        console.print(f'\n  {len(verdict.foreign)} rows belong to another machine, whose manifest declares them.')
        console.print('  Nothing to repair here.')
    return 0


def foreign_note(entry: index.Entry) -> str:
    """Why a row is another machine's, in the terms its own entry used."""
    return f'needs {entry.requires}' if entry.requires else f'installed via {entry.installed_via}'


def print_index_rows(entries: list[index.Entry], style: str, note: Callable[[index.Entry], str] | None = None) -> None:
    width = max(len(entry.name) for entry in entries)
    for entry in entries:
        line = Text('  ')
        line.append(entry.name.ljust(width), style=style)
        line.append(f'  {note(entry) if note else entry.invocation}')
        console.print(line, no_wrap=True, overflow='ellipsis')


def unresolved_command(
    as_json: Annotated[bool, typer.Option('--json', help='Output the rows naming nothing runnable as JSON to stdout.')] = False,
) -> None:
    """Rows naming something this machine cannot run."""
    raise typer.Exit(cmd_unresolved(as_json))
