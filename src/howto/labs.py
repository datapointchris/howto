"""Hands-on practice Labs. Invoked as `howto labs`.

A Lab is a single markdown file under the Labs dir that teaches a tool the way a
senior engineer walks a junior through it: what to do, what to expect, why it
works, alternatives. Any environment setup is a copy-pasteable code block inside
the Lab — you run it yourself in a second pane and work through the steps at your
own keyboard. Nothing is graded; the point is the reps.

A Lab carries no schedule, and howto records nothing about when you practiced
one. Keeping a practice schedule is a different tool's job.

There is one Labs directory, not a source and an installed copy. It sits in the
library checkout that `howto library sync` pulls, so authoring writes straight to
the file the reader reads — which is why nothing here resolves a second path or
links one into the other.
"""

import random
import subprocess
from typing import Annotated

import typer
from rich.text import Text

from howto import tools
from howto.editor import open_in_editor
from howto.markdown import first_heading
from howto.markdown import render_body
from howto.markdown import slugify
from howto.markdown import split_frontmatter
from howto.paths import library_dir
from howto.render import can_prompt
from howto.render import console
from howto.render import error_console
from howto.render import print_json_rows

LABS_DIR = library_dir() / 'labs'

# A flashcard session stays short — the research says a few minutes / <=5 new/day
# beats long cramming — so a session samples at most this many cards.
FLASH_SESSION = 10

TEMPLATE = """\
---
tags: []
---

# {title}

> One line: what this Lab drills and when you'd reach for it.

## Setup

Copy this into your other pane to stage a scratch dir to play in:

```bash
LAB=$(mktemp -d) && cd "$LAB"
# ... create fixture files here ...
```

## Steps

1. **Do the thing.** `some command`
   - Expect: what you should see.
   - Why: the reason it works.
   - Alternative: another way to reach the same result.
"""


def load_labs() -> dict:
    """{lab_id: {title, tags, path}} for every Lab markdown file."""
    deck: dict[str, dict] = {}
    if not LABS_DIR.exists():
        return deck
    for path in sorted(LABS_DIR.glob('*.md')):
        meta, body = split_frontmatter(path.read_text())
        lab_id = path.stem
        deck[lab_id] = {
            'title': first_heading(body) or lab_id,
            'tags': meta.get('tags') or [],
            'path': path,
        }
    return deck


def deck_rows() -> list[dict]:
    """Every Lab as its id, title and tags, in id order."""
    return [{'id': lab_id, 'title': meta['title'], 'tags': meta['tags']} for lab_id, meta in load_labs().items()]


def render_row(row: dict) -> None:
    line = Text('  ')
    line.append(row['id'], style='yellow')
    line.append(f'  {row["title"]}')
    console.print(line)
    if row['tags']:
        tags = Text('      ')
        tags.append(f'#{" #".join(row["tags"])}', style='cyan')
        console.print(tags)


def cmd_show(lab_id: str) -> int:
    labs = load_labs()
    if lab_id not in labs:
        return unknown_lab(lab_id)
    render_body(labs[lab_id]['path'], for_preview=False)
    return 0


def cmd_render_preview(lab_id: str) -> int:
    labs = load_labs()
    if lab_id not in labs:
        return 1
    render_body(labs[lab_id]['path'], for_preview=True)
    return 0


def bounded(rows: list[dict], limit: int | None) -> list[dict]:
    """The first `limit` rows, or all of them when no limit was asked for."""
    return rows[:limit] if limit else rows


def more_line(shown: int, total: int, browse: str) -> None:
    """Say what the limit held back, and name the command that shows it."""
    if shown < total:
        console.print(f'  +{total - shown} more  ·  [cyan]{browse}[/]')


def cmd_list(as_json: bool = False, limit: int | None = None) -> int:
    # An empty deck is an empty list, not the prose hint: --json must always be
    # parsable.
    if as_json:
        print_json_rows('labs', bounded(deck_rows(), limit))
        return 0
    deck = deck_rows()
    if not deck:
        return warn_no_labs()
    console.rule('[cyan]Labs — full deck', align='left')
    shown = bounded(deck, limit)
    for row in shown:
        render_row(row)
    console.print()
    more_line(len(shown), len(deck), 'howto labs list')
    console.print('Practice one:  [cyan]howto labs show <id>[/]   ·   choose interactively:  [cyan]howto labs choose[/]')
    return 0


def cmd_pick() -> int:
    labs = load_labs()
    if not labs:
        return warn_no_labs()
    rows = '\n'.join(f'{lab_id}\t{meta["title"]}' for lab_id, meta in sorted(labs.items()))
    try:
        result = subprocess.run(
            [
                'fzf',
                '--delimiter=\t',
                '--with-nth=2',
                '--prompt=lab ❯ ',
                '--preview',
                'howto labs __render {1}',
                '--preview-window=right:62%',
            ],
            input=rows,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        error_console.print('fzf not found. Use [cyan]howto labs list[/] then [cyan]howto labs show <id>[/].')
        return 1
    selected = result.stdout.strip()
    if not selected:
        return 0
    return cmd_show(selected.split('\t', 1)[0])


def cmd_new(name: str) -> int:
    slug = slugify(name)
    if not slug:
        error_console.print('A Lab needs a name with at least one letter or digit.')
        return 2
    target = LABS_DIR / f'{slug}.md'
    if target.exists():
        error_console.print(Text(f'Lab already exists: {target}'))
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(TEMPLATE.format(title=name))
    console.print(Text.from_markup('[green]✓[/] Created ') + Text(str(target)))
    open_in_editor(target)
    return 0


def cmd_edit(lab_id: str) -> int:
    path = LABS_DIR / f'{lab_id}.md'
    if not path.exists():
        return unknown_lab(lab_id)
    open_in_editor(path)
    return 0


def unknown_lab(lab_id: str) -> int:
    error_console.print(Text(f'No Lab {lab_id!r}.'))
    hint = Text('See what is available with ')
    hint.append('howto labs list', style='cyan')
    hint.append(', or create it with ')
    hint.append(f'howto labs new {lab_id}', style='cyan')
    error_console.print(hint)
    return 1


def warn_no_labs() -> int:
    console.print(Text(f'No Labs yet in {LABS_DIR}.'))
    console.print('Create your first with [cyan]howto labs new <name>[/].')
    return 0


def load_flashcards(subject: str | None = None) -> list[dict]:
    """Recall cards from the registry: prompt = an example's description, answer =
    its command. Zero authoring — every tool's examples become a deck.

    A subject filters to one tool by name or by tag membership.

    The registry backs this deck (recall the command from an example's
    description). `howto.tools` owns it; this only reads it.
    """
    cards = []
    for name, tool in tools.load_registry().items():
        tool = tool or {}
        if subject and name != subject and subject not in (tool.get('tags') or []):
            continue
        for example in tool.get('examples') or []:
            example = example or {}
            cmd = example.get('cmd')
            desc = example.get('desc')
            if cmd and desc:
                cards.append({'tool': name, 'prompt': desc, 'answer': cmd})
    return cards


def cmd_flash(subject: str | None = None) -> int:
    """A quick recall pass: show a description, you recall the command, reveal,
    self-mark. Ephemeral (no schedule) — the daily warm-up next to the Labs."""
    cards = load_flashcards(subject)
    if not cards:
        message = f'No examples to drill for {subject!r}.' if subject else f'No registry examples found at {tools.REGISTRY}.'
        console.print(Text(message))
        return 0
    if not can_prompt():
        error_console.print('flash is answered card by card, and this run has nobody to answer it.')
        return 1
    random.shuffle(cards)
    cards = cards[:FLASH_SESSION]
    console.rule('[cyan]Flashcards — recall the command', align='left')
    correct = 0
    answered = 0
    for i, card in enumerate(cards, 1):
        # Text, not markup: a tool name sits inside square brackets here, which
        # rich would otherwise read as a style tag and swallow.
        counter = Text('  ')
        counter.append(f'{i}/{len(cards)}', style='yellow')
        counter.append(f'  [{card["tool"]}]')
        console.print(counter)
        console.print(Text(f'  {card["prompt"]}'))
        try:
            if console.input('  [cyan]Enter to reveal · q to quit ❯ [/]').strip().lower() == 'q':
                break
            answer = Text('  ')
            answer.append(f'$ {card["answer"]}', style='green')
            console.print(answer)
            got = console.input(r'  got it? \[y/N] ❯ ').strip().lower()
        except EOFError:
            break
        answered += 1
        if got == 'y':
            correct += 1
        console.print()
    if answered:
        console.print(f'[green]✓[/] Recalled {correct}/{answered}.')
    return 0


LABS_HELP = """Hands-on practice Labs.

Examples:

```text
howto labs choose              pick a Lab to work through in another pane
howto labs list                every Lab, with its title and tags
howto labs show git-stash      one Lab, to read beside your practice pane
howto labs flash git           a recall drill on the git examples
```
"""

app = typer.Typer(name='labs', no_args_is_help=True, help=LABS_HELP)


LimitOption = Annotated[int | None, typer.Option('--limit', '-n', help='Show at most this many, then say how many are left.')]


@app.command('list')
def list_command(
    as_json: Annotated[bool, typer.Option('--json', help='Output as JSON to stdout.')] = False,
    limit: LimitOption = None,
) -> None:
    """Every Lab, with its title and tags.

    Examples:

    ```text
    howto labs list                find a Lab by its title or tags
    howto labs list -n 5           the first five, and how many are left
    howto labs list --json         id, title and tags for another program
    ```
    """
    raise typer.Exit(cmd_list(as_json, limit))


@app.command('show')
def show_command(lab_id: Annotated[str, typer.Argument(help='The Lab to open.')]) -> None:
    """Open a Lab to read while you work in another pane.

    Examples:

    ```text
    howto labs show git-stash      practice shelving work in progress
    ```
    """
    raise typer.Exit(cmd_show(lab_id))


@app.command('choose')
def choose_command() -> None:
    """Choose a Lab interactively (fzf).

    Examples:

    ```text
    howto labs choose              browse Labs with a preview, open your pick
    ```
    """
    raise typer.Exit(cmd_pick())


@app.command('flash')
def flash_command(
    subject: Annotated[str | None, typer.Argument(help='One tool or tag; omit to drill everything.')] = None,
) -> None:
    """Quick recall drill from tool examples.

    Examples:

    ```text
    howto labs flash git           recall git commands before a day of git work
    howto labs flash               a drill across every tool's examples
    ```
    """
    raise typer.Exit(cmd_flash(subject))


@app.command('new')
def new_command(name: Annotated[list[str], typer.Argument(help='The new Lab name.')]) -> None:
    """Scaffold a new Lab and open it in $EDITOR.

    Examples:

    ```text
    howto labs new git worktrees   create labs/git-worktrees.md and edit it
    ```
    """
    raise typer.Exit(cmd_new(' '.join(name)))


@app.command('edit')
def edit_command(lab_id: Annotated[str, typer.Argument(help='The Lab to edit.')]) -> None:
    """Edit an existing Lab in $EDITOR.

    Examples:

    ```text
    howto labs edit git-stash      fix a step in a Lab you just worked through
    ```
    """
    raise typer.Exit(cmd_edit(lab_id))


@app.command('__render', hidden=True)
def render_command(lab_id: Annotated[str, typer.Argument()]) -> None:
    """Render one Lab body, for the fzf preview pane in `pick`."""
    raise typer.Exit(cmd_render_preview(lab_id))
