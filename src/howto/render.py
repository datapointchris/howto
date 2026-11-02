"""howto's shared consoles, and whether anyone can be asked a question.

Lines carrying content from the library are built as `Text` rather than markup
strings — `Text.append` does not parse `[...]`, so a bracket in a description
cannot be swallowed as a style tag.
"""

import sys

from rich.console import Console

# highlight=False: rich's automatic highlighter colors anything that looks like
# a number, path or URL, which turns a card id into a surprise.
console = Console(highlight=False)

# Everything that is not data. stdout carries the answer a caller parses; a
# diagnostic written there turns `howto list --json` into a broken parse.
error_console = Console(stderr=True, highlight=False)

# Bound to the persistent --no-input flag by the root callback, which runs on
# every invocation and rewrites it, so an in-process run never inherits the
# last one's value.
no_input = False


def set_no_input(value: bool) -> None:
    global no_input
    no_input = value


def can_prompt() -> bool:
    """Whether the user can be asked anything: --no-input never allows it, and
    otherwise stdin has to be a terminal.

    A prompt written to a stdin that never closes leaves the caller with no
    output and no exit code."""
    return not no_input and sys.stdin.isatty()
