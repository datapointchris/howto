"""howto's command tree.

Every node prints help when given no arguments, and a usage error exits 2 —
both from typer rather than hand-rolled here. Each subcommand module owns its
own `app`; this file only assembles them.
"""

import sys
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Any

import typer
from typer.core import TyperGroup

from howto import cards
from howto import find
from howto import labs
from howto import library
from howto import shell
from howto import tool_version
from howto import tools
from howto.render import set_no_input

if TYPE_CHECKING:
    import pyselfupdate

TAGLINE = 'How do I do this: reference cards, Labs, a tool registry, and your shell, searched as one.'

# The first-run hint shares the tagline's paragraph because typer dims every
# paragraph after the first, and markdown wraps it to the terminal. The examples
# sit in a fenced text block, as every command's do: typer dedents the text after
# the first paragraph, so an indented block would become a paragraph.
ROOT_HELP = f"""{TAGLINE}
The first run clones the library, and **howto library status** says where.

Examples:

```text
howto find stash             search everything, and open what you pick
howto show bat               all that is known about one name
howto choose                 pick a command and print it, ready to run
howto cards show git-rebase  one reference card
howto labs choose            a Lab to work through in another pane
```
"""


class RootGroup(TyperGroup):
    """The root group, which says where an option a command refused is accepted.

    `--no-input` belongs to the root, so `howto labs flash --no-input` is refused
    by `flash`. click's "No such option" alone sends the reader to `--help` to
    find where the option goes, so the refusal names the placement that works.
    """

    def invoke(self, ctx: Any) -> Any:
        try:
            return super().invoke(ctx)
        except Exception as failure:
            name_accepted_placements(failure)
            raise


def accepted_placements(failure: Any) -> list[str]:
    """The refused command line with the option moved onto each group above it that declares it.

    click's `NoSuchOption` is recognized by its `option_name` and `possibilities`
    rather than by class, because typer vendors click under a private module.
    Its `ctx` is the command that refused, and its parents are the groups above.
    """
    option = getattr(failure, 'option_name', None)
    refusing = getattr(failure, 'ctx', None)
    if not option or not hasattr(failure, 'possibilities') or refusing is None:
        return []
    chain: list[Any] = []
    while refusing is not None:
        chain.insert(0, refusing)
        refusing = refusing.parent
    names = [context.info_name or '' for context in chain]
    return [
        ' '.join([*names[: depth + 1], option, *names[depth + 1 :]])
        for depth, context in enumerate(chain[:-1])
        if any(option in getattr(param, 'opts', ()) for param in context.command.params)
    ]


def name_accepted_placements(failure: Any) -> None:
    """Append the placements that work to a refused option's message."""
    placements = accepted_placements(failure)
    if placements:
        listed = ' or '.join(f"'{placement}'" for placement in placements)
        failure.message = f'{failure.message}. It goes before the command: {listed}.'
        failure.possibilities = None


app = typer.Typer(name='howto', cls=RootGroup, no_args_is_help=True, help=ROOT_HELP, rich_markup_mode='markdown')


def update_config() -> 'pyselfupdate.Config':
    """What `howto update` installs and what the daily notice compares against.

    Notify-only: one check per 24h, one line to stderr, and `howto update` is the
    only thing that writes anything. The notice and the command share this one
    config so they cannot advertise a release the command then refuses.

    pyselfupdate is imported here and in the two places that call this, rather
    than at the top, because it loads its HTTP and install stack with it, and
    most runs, the fzf preview's included, never check for a release.
    """
    # 348ms → 218ms on `howto __preview alias ll`, 2026-11-15
    import pyselfupdate

    return pyselfupdate.Config(tool='howto', owner='datapointchris')


def update_command(
    check_only: Annotated[bool, typer.Option('--check', help='Report whether an update is available without installing it')] = False,
    skip_changelog: Annotated[bool, typer.Option('--no-changelog', help='Do not list the commits between versions')] = False,
) -> None:
    """Update howto to the latest release.

    Examples:

    ```text
    howto update                 install the newest and list its commits
    howto update --check         only report whether a newer one exists
    howto update --no-changelog  install it without listing its commits
    ```
    """
    # 348ms → 218ms on `howto __preview alias ll`, 2026-11-15
    from pyselfupdate.typercmd import run_update

    run_update(update_config(), check_only=check_only, skip_changelog=skip_changelog)


app.command('find')(find.find_command)
app.command('show')(find.show_command)
app.command('choose')(find.choose_command)
app.command('list')(find.list_command)
app.command('update')(update_command)

# What the fzf preview pane calls, not what you type.
app.command('__preview', hidden=True)(find.preview_command)

app.add_typer(cards.app, name='cards')
app.add_typer(tools.app, name='tools')
app.add_typer(labs.app, name='labs')
app.add_typer(library.app, name='library')
app.add_typer(shell.app, name='shell')


def version_callback(asked: bool) -> None:
    """`howto --version`, in the one line every CLI here answers it with."""
    if not asked:
        return
    print(f'howto {tool_version()}')
    raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option('--version', '-V', callback=version_callback, is_eager=True, help='Show the installed version and exit.'),
    ] = None,
    no_input: Annotated[
        bool,
        typer.Option('--no-input', help='Never prompt; fail naming the flag that would have answered.'),
    ] = False,
) -> None:
    """Root callback, hosting the app-level options.

    The library clone happens here so a new machine needs no setup step anyone
    has to remember. It is one `exists()` once the checkout is there.

    Keeping it current is the same argument on every later run — the pull is
    detached, so a command costs the same whether or not one was due. `library`
    is exempt: its own subcommands report on the checkout, and a pull racing them
    would have `status` describe a tree being rewritten underneath it.
    """
    set_no_input(no_input)
    # A help screen reads no cards, so neither the clone nor the pull belongs on
    # one. Typer runs this callback before answering a subcommand's --help. The
    # update notice is skipped on the same runs: nobody reads a line on stderr
    # from a help screen or from the preview fzf runs on every keystroke.
    if not library.worth_a_pull(sys.argv):
        return
    library.ensure_cloned()
    if ctx.invoked_subcommand != 'library':
        library.autosync()

    # `update` runs its own check, so notifying too would ask the releases API
    # twice for one command.
    if ctx.invoked_subcommand != 'update':
        # 348ms → 218ms on `howto __preview alias ll`, 2026-11-15
        from pyselfupdate import notify

        notify(update_config())


def main() -> None:
    app()
