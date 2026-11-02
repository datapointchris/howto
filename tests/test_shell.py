"""The generated shell blocks.

The assertion that earns its place is `zsh -n`: a generated script that does not
parse breaks at shell startup on every machine at once, rather than where it was
written.
"""

import re
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from howto import shell
from howto.cli import app as cli_app

runner = CliRunner()
needs_zsh = pytest.mark.skipif(not shutil.which('zsh'), reason='zsh is not installed')


@needs_zsh
@pytest.mark.parametrize('generate', [shell.zsh_completion, shell.zsh_widgets])
def test_the_generated_zsh_parses(generate):
    result = subprocess.run(['zsh', '-n'], input=generate(), text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_the_completion_offers_no_command_the_cli_does_not_have():
    """A hand-written list drifts from the command tree unless something joins them."""
    script = shell.zsh_completion()
    offered = set(re.findall(r"^\s+'([a-z-]+):", script, re.M))
    registered = {command.name for command in cli_app.registered_commands}
    registered |= {group.name for group in cli_app.registered_groups}
    assert offered <= registered, f'completion offers {sorted(offered - registered)}'

    groups = {group.name: group.typer_instance for group in cli_app.registered_groups}
    for name, row in re.findall(r'^\s+(\w+)\) sub=\((.*)\) ;;$', script, re.M):
        verbs = set(re.findall(r"'([a-z-]+):", row))
        typer_app = groups[name]
        known = {command.name for command in typer_app.registered_commands} | {g.name for g in typer_app.registered_groups}
        assert verbs <= known, f'{name} completion offers {sorted(verbs - known)}'


def test_completion_never_calls_howto_on_tab():
    """A Tab must not wait on a Python start; ids are globbed from the library."""
    script = shell.zsh_completion()
    assert '$(howto' not in script
    assert '(*.md' in script or '/*.md' in script


def test_the_widget_is_defined_before_it_is_registered_and_binds_no_key():
    """The rc binds a key to this name, and that bind is silent when the widget
    is missing. howto cannot see the keymap, so it never binds one itself."""
    block = shell.zsh_widgets()

    assert block.index('howto-choose-widget()') < block.index('zle -N howto-choose-widget')
    assert [line for line in block.splitlines() if line.strip().startswith('bindkey')] == []
    assert 'zle reset-prompt' in block
    assert 'print -z' in block.split('howto-choose-next()')[1]


@pytest.mark.parametrize('verb', ['widgets', 'completion'])
def test_an_unsupported_shell_is_a_usage_error(verb):
    result = runner.invoke(cli_app, ['shell', verb, 'fish'])

    assert result.exit_code == 2
    assert 'zsh' in result.output
