"""Search the federated index, then hand you off to whoever owns the answer.

`howto find` is one motion: fuzzy-match a line, press Enter, get how to use that
thing, assembled from every collection that has it. `howto show` is that same
composite when you already know the name, and it is a command rather than a
picker callback because knowing the name is the common case.

`howto choose` is the same picker ending somewhere else: it prints the row's
invocation and nothing else, so the thing you pointed at can be run rather than
only read. Landing it on the prompt is the shell's half — see `howto.shell` —
and has to be, because the line editor belongs to the parent process this one
cannot reach into.

fzf is shelled out to rather than reimplemented. It is already the picker
everywhere else on a terminal, and a Python reimplementation would be a worse
one that also had to be maintained.

Nothing here renders a subject itself. Each lens hands off to whatever owns it —
`howto.tools` for anything out of the registry or the shell files, `howto.cards`
for a card — because a second renderer is a second thing to keep in step with
the first.
"""

import json
import shutil
import subprocess
from typing import Annotated

import typer
from rich.text import Text

from howto import cards
from howto import index
from howto import tools
from howto.render import console
from howto.render import error_console

FZF_FAILED = 2

FZF_COMMON = [
    '--delimiter=\t',
    '--with-nth=1',
    '--tiebreak=begin,length',
    '--no-hscroll',
    '--preview-window=right:62%',
]

# What fzf runs per highlighted row, given the row's collection and name.
PREVIEW = 'howto __preview {2} {3}'

# The header is the only thing on screen naming which picker you are in, so it
# is named here rather than quoted at the call site — two commands share one
# picker, and a copy-paste header is the drift that makes them indistinguishable.
FIND_HEADER = 'Enter shows how to use it'
CHOOSE_HEADER = 'Enter puts it on your command line'


def run_fzf(lines: list[str], query: str, header: str) -> str | None:
    """Pick one line with fzf: the row, '' when the pick was canceled, None when fzf is missing or failed.

    Canceling and having no picker are different answers and every caller has
    to tell them apart. `choose` is read back through `$(...)`, where exit status
    is the caller's only signal — a missing binary reported as success is an
    empty command line with no explanation of why.

    fzf exits 1 for no match and 130 for Esc, both a pick of nothing. It exits 2
    when it cannot run at all, as with no terminal to draw on, and prints why to
    the stderr captured here.
    """
    if not shutil.which('fzf'):
        error_console.print('fzf is not installed on this machine.')
        print_without_a_picker()
        return None
    command = [
        'fzf',
        *FZF_COMMON,
        f'--query={query}',
        '--prompt=howto ❯ ',
        f'--preview={PREVIEW}',
        f'--header={header}',
    ]
    result = subprocess.run(command, input='\n'.join(lines), text=True, capture_output=True, check=False)
    if result.returncode == FZF_FAILED:
        said = result.stderr.strip().splitlines()
        error_console.print(f'fzf could not run: {said[0] if said else f"exited {result.returncode}"}')
        print_without_a_picker()
        return None
    return result.stdout.strip()


def print_without_a_picker() -> None:
    error_console.print('Without a picker, [cyan]howto show <name>[/] shows one thing and [cyan]howto list --json[/] lists all of them.')


def index_lines(entries: list[index.Entry]) -> list[str]:
    """`display <TAB> source <TAB> name <TAB> invocation` — field one is shown and searched.

    The invocation rides along rather than being looked up again after the pick.
    `--with-nth=1` means fzf neither displays nor matches it, and re-resolving a
    name through a second `build_index()` is a second answer that can disagree
    with the row the human actually pointed at.
    """
    return [f'{entry.display()}\t{entry.source}\t{entry.name}\t{entry.invocation}' for entry in entries]


def explain_empty_index() -> int:
    error_console.print('Nothing indexed. Fetch the library with [cyan]howto library sync[/].')
    return 1


def cmd_find(term: str, sources: list[str] | None) -> int:
    entries = index.build_index(sources)
    if not entries:
        return explain_empty_index()
    selected = run_fzf(index_lines(entries), term, FIND_HEADER)
    if selected is None:
        return 1
    if not selected:
        return 0
    return cmd_show(selected.split('\t')[2])


def cmd_choose(term: str, sources: list[str] | None) -> int:
    """The same pick, ending on the command line instead of in a card.

    `find` answers "tell me about this" and `choose` answers "give me this to
    run" — two terminal acts over one picker, so neither has to be a mode of the
    other. Plain `print` rather than the console: this string is the answer a
    caller reads back through `$(...)`, and a style code or a wrap in it would
    land on the prompt verbatim.
    """
    entries = index.build_index(sources)
    if not entries:
        return explain_empty_index()
    selected = run_fzf(index_lines(entries), term, CHOOSE_HEADER)
    if selected is None:
        return 1
    if not selected:
        return 0
    print(selected.split('\t')[3])
    return 0


def lens_sources(subject: str, sources: list[str] | None = None) -> dict[str, index.Entry]:
    """Every indexed row whose name is this subject, keyed by collection.

    `howto show` wants all of them, which is the composite. A preview already
    knows which collection its row came from, and narrowing to it is the
    difference between reading one file and asking zsh for its keymaps.
    """
    return {entry.source: entry for entry in index.build_index(sources) if entry.name == subject}


def render_section(title: str, style: str) -> None:
    console.print()
    console.print(Text(title, style=style))


def delegate(command: list[str]) -> bool:
    """Run another tool's own renderer. False when the tool is not installed."""
    try:
        subprocess.run(command, check=False)
    except FileNotFoundError:
        return False
    return True


def cmd_show(subject: str) -> int:
    """How to use one tool or command, from every collection in the library that has it.

    Assembled in a fixed order so the same subject reads the same way every
    time, and each section names the collection it came from — a composite that
    hides its sources is one you cannot go and correct.
    """
    found = lens_sources(subject)
    if not found:
        error_console.print(Text(f'Nothing known about {subject!r} in any collection.'))
        error_console.print(f'Collections searched: {", ".join(index.LENSES)}')
        hint = Text('Search for it with ')
        hint.append(f'howto find {subject}', style='cyan')
        hint.append(', or list every name with ')
        hint.append('howto list', style='cyan')
        error_console.print(hint)
        return 1

    console.rule(f'[cyan]{subject}', align='left')
    console.print(Text(f'Found in: {", ".join(sorted(found))}', style='blue'))

    if 'tool' in found:
        entry = found['tool']
        render_section(f'registry — {entry.invocation}', 'yellow')
        tools.render_tool(subject, tools.load_registry().get(subject) or {}, heading=False)
        # A heading is a promise that something follows it. tldr answers for
        # itself when it has no page, so absence of the binary is the one case
        # that would leave the promise unkept.
        if shutil.which('tldr'):
            render_section('tldr — common examples', 'blue')
            delegate(['tldr', tools.invocation_head(entry.invocation)])
    if 'card' in found:
        render_section('card — your reference card', 'cyan')
        # Flushed first because bat writes straight to the terminal, and the
        # heading above must land before the card it introduces.
        console.file.flush()
        cards.cmd_show(subject)
    for source in ('func', 'alias', 'git', 'forgit', 'zsh', 'tmux'):
        if source in found:
            console.print()
            render_lens_card(found[source])
    return 0


def render_lens_card(entry: index.Entry) -> None:
    """The card shape belonging to whichever shell collection this row came from.

    The fallback is the shape for a row that is not a command — a tmux keybinding
    is a key, so there is nothing for a `↳` line to carry.
    """
    if entry.source == 'func':
        tools.render_function(entry.name, entry.description, entry.body)
    elif entry.source == 'alias':
        tools.render_alias(entry.name, entry.command, entry.description)
    elif entry.source == 'git':
        tools.render_git_alias(entry.name, entry.command)
    elif entry.source == 'forgit':
        tools.render_forgit(entry.name, entry.command)
    elif entry.source == 'zsh':
        tools.render_zsh_key(entry.name, entry.command, entry.description)
    else:
        tools.card_title(entry.invocation, entry.source)
        tools.card_detail(entry.description, brief=False)


TermArgument = Annotated[list[str] | None, typer.Argument(help='What to search for.')]

LensOption = Annotated[
    list[str] | None,
    typer.Option('--source', help=f'Limit to one collection (repeatable): {", ".join(index.LENSES)}'),
]


def lenses(source: list[str] | None) -> list[str] | None:
    """The `--source` list, or a usage error naming what it could have been."""
    unknown = [name for name in source or [] if name not in index.LENSES]
    if unknown:
        raise typer.BadParameter(f'unknown source(s) {", ".join(unknown)}; choose from {", ".join(index.LENSES)}')
    return source


def find_command(term: TermArgument = None, source: LensOption = None) -> None:
    """Search everything and open all that is known about the one you pick.

    Examples:

    ```text
    howto find stash               search everything, and open what you pick
    howto find --source card git   only the cards that mention git
    howto find                     browse every row, starting from nothing
    ```
    """
    raise typer.Exit(cmd_find(' '.join(term or []), lenses(source)))


def choose_command(term: TermArgument = None, source: LensOption = None) -> None:
    """Pick one thing and print what you would type to run it — read, never opened.

    `$(howto choose)` in any shell. `howto shell widgets zsh` emits the zsh half
    that lands the pick on the line editor instead of on stdout.

    Examples:

    ```text
    howto choose                   pick a command and print it, ready to run
    howto choose --source alias    only your aliases
    $(howto choose docker)         run the docker command you pick
    ```
    """
    raise typer.Exit(cmd_choose(' '.join(term or []), lenses(source)))


def show_command(subject: Annotated[str, typer.Argument(help='The name of a tool, card, function, alias or key.')]) -> None:
    """How to use one tool or command, from every collection that has it.

    Examples:

    ```text
    howto show bat                 every collection's entry for bat, on one page
    howto show git-rebase          a card, found by its id
    ```
    """
    raise typer.Exit(cmd_show(subject))


def preview_command(source: Annotated[str, typer.Argument()], name: Annotated[str, typer.Argument()]) -> None:
    """Render one row for the fzf preview pane.

    Runs once per keystroke, so it builds the one collection fzf named rather
    than the whole index. A source fzf could not have produced renders nothing:
    the preview pane is not where a usage error is worth printing.
    """
    if source == 'tool':
        tools.render_tool(name, tools.load_registry().get(name) or {})
        raise typer.Exit(0)
    if source == 'card':
        raise typer.Exit(cards.cmd_render_preview(name))
    if source in index.LENSES and (entry := lens_sources(name, [source]).get(source)):
        render_lens_card(entry)
    raise typer.Exit(0)


def list_command(
    as_json: Annotated[bool, typer.Option('--json', help='Output as JSON to stdout.')] = False,
) -> None:
    """Every indexed row, as the picker sees it.

    A terminal gets one line per row, cut to its width so the list scans. A
    pipe gets every row whole, because fzf matches the whole line, and the tags
    at its end are the first thing a cut drops.

    Examples:

    ```text
    howto list                     everything the picker searches, one row each
    howto list | rg docker         the rows that mention docker, tags included
    howto list --json              source, name, invocation, description per row
    ```
    """
    entries = index.build_index()
    if as_json:
        print(
            json.dumps(
                [{'source': e.source, 'name': e.name, 'invocation': e.invocation, 'description': e.description} for e in entries],
                indent=2,
            )
        )
        raise typer.Exit(0)
    if not console.is_terminal:
        for entry in entries:
            print(entry.display())
        raise typer.Exit(0)
    for entry in entries:
        console.print(Text(entry.display()), no_wrap=True, overflow='ellipsis')
    raise typer.Exit(0)
