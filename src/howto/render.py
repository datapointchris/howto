"""howto's shared consoles, the document every --json read prints, and whether anyone can be asked a question.

Lines carrying content from the library are built as `Text` rather than markup
strings — `Text.append` does not parse `[...]`, so a bracket in a description
cannot be swallowed as a style tag.
"""

import json
import sys

from rich.console import Console

# The version every schema under `schemas/` pins with `const`. A shape change to
# one document gives that document a version of its own.
SCHEMA_VERSION = 1

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


def print_json_rows(key: str, rows: list[dict]) -> None:
    """A --json read's document: its rows under `key`, beside `schema_version`.

    Plain print, never the console, because a Console soft-wraps at terminal
    width and would put newlines inside JSON strings.
    """
    print(json.dumps({'schema_version': SCHEMA_VERSION, key: rows}, indent=2))


def set_no_input(value: bool) -> None:
    global no_input
    no_input = value


def can_prompt() -> bool:
    """Whether the user can be asked anything: --no-input never allows it, and
    otherwise stdin has to be a terminal.

    A prompt written to a stdin that never closes leaves the caller with no
    output and no exit code."""
    return not no_input and sys.stdin.isatty()
