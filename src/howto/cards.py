"""The reference cards — what to run once you have decided what to do.

Invoked as `howto cards`. A card is one markdown file: a named procedure
carried through several tools in order, or one tool's commands and keybindings
collected in one place.

The cards directory sits in the library checkout that `howto library sync`
pulls, so `new` writes the file the reader reads — one path, resolved once,
rather than a symlink followed backwards to wherever the content is authored.

Searching cards is `howto find --source card`, not a verb here. A card is one
row in the federated index alongside tools, aliases and tmux keys, and
scoping that index is a filter rather than a second search.
"""

import random
from typing import Annotated

import typer
from rich.text import Text

from howto.editor import open_in_editor
from howto.markdown import first_heading
from howto.markdown import render_body
from howto.markdown import slugify
from howto.markdown import split_frontmatter
from howto.paths import library_dir
from howto.render import console
from howto.render import error_console

CARDS_DIR = library_dir() / 'cards'

TEMPLATE = """\
---
tags: []
---

# {title}

"""


def load_cards() -> dict:
    """{card_id: {title, tags, path}} for every card markdown file."""
    cards: dict[str, dict] = {}
    if not CARDS_DIR.exists():
        return cards
    for path in sorted(CARDS_DIR.glob('*.md')):
        meta, body = split_frontmatter(path.read_text())
        cards[path.stem] = {
            'title': first_heading(body) or path.stem,
            'tags': meta.get('tags') or [],
            'path': path,
        }
    return cards


def warn_no_cards() -> int:
    console.print(Text(f'No cards yet in {CARDS_DIR}.'))
    console.print('Create your first with [cyan]howto cards new <name>[/].')
    return 0


def unknown_card(card_id: str) -> int:
    error_console.print(Text(f'No card {card_id!r}.'))
    hint = Text('See what is available with ')
    hint.append('howto cards list', style='cyan')
    hint.append(', or search across everything with ')
    hint.append(f'howto find {card_id}', style='cyan')
    error_console.print(hint)
    return 1


def cmd_list() -> int:
    cards = load_cards()
    if not cards:
        return warn_no_cards()
    console.rule('[cyan]Cards', align='left')
    width = max(len(name) for name in cards)
    for name, card in cards.items():
        line = Text('  ')
        line.append(name.ljust(width), style='green')
        line.append(f'  {card["title"]}')
        console.print(line, no_wrap=True, overflow='ellipsis')
    console.print(f'\n  {len(cards)} cards · [cyan]howto cards show <name>[/]')
    return 0


def cmd_show(card_id: str) -> int:
    # `.md` is accepted because the filename is what a tab-completion offers.
    card_id = card_id.removesuffix('.md')
    cards = load_cards()
    if card_id not in cards:
        return unknown_card(card_id)
    render_body(cards[card_id]['path'])
    return 0


def cmd_render_preview(card_id: str) -> int:
    cards = load_cards()
    if card_id not in cards:
        return 1
    render_body(cards[card_id]['path'], for_preview=True)
    return 0


def cmd_random() -> int:
    cards = load_cards()
    if not cards:
        return warn_no_cards()
    render_body(cards[random.choice(list(cards))]['path'])
    return 0


def cmd_new(name: str) -> int:
    slug = slugify(name)
    if not slug:
        error_console.print('A card needs a name with at least one letter or digit.')
        return 2
    target = CARDS_DIR / f'{slug}.md'
    if target.exists():
        error_console.print(Text(f'Card already exists: {target}'))
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATE.format(title=name))
    console.print(Text.from_markup('[green]✓[/] Created ') + Text(str(target)))
    open_in_editor(target)
    return 0


app = typer.Typer(name='cards', no_args_is_help=True, help='The reference cards.')


@app.command('list')
def list_command() -> None:
    """Every card and what it covers."""
    raise typer.Exit(cmd_list())


@app.command('show')
def show_command(card_id: Annotated[str, typer.Argument(help='The card to render.')]) -> None:
    """Render one card."""
    raise typer.Exit(cmd_show(card_id))


@app.command('new')
def new_command(name: Annotated[list[str], typer.Argument(help='The new card name.')]) -> None:
    """Create a card in the library and open it in $EDITOR."""
    raise typer.Exit(cmd_new(' '.join(name)))


@app.command('random')
def random_command() -> None:
    """Render a card at random."""
    raise typer.Exit(cmd_random())


@app.command('__render', hidden=True)
def render_command(card_id: Annotated[str, typer.Argument()]) -> None:
    """Render one card body, for an fzf preview pane."""
    raise typer.Exit(cmd_render_preview(card_id))
