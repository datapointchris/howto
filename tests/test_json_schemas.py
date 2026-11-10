"""Each --json read, run over the committed fixture library, validated against its file under `schemas/`."""

import json
from pathlib import Path
from typing import Any

import pytest
import typer
from jsonschema import Draft7Validator
from typer.testing import CliRunner

from howto import cards
from howto import index
from howto import labs
from howto import tools
from howto.cli import app

SCHEMAS = Path(__file__).resolve().parents[1] / 'schemas'
FIXTURES = Path(__file__).resolve().parent / 'fixtures'

runner = CliRunner()

# The command each schema describes, and the key its rows sit under.
READS = {
    'list': (['list'], 'rows'),
    'tools-list': (['tools', 'list'], 'tools'),
    'tools-categories-list': (['tools', 'categories', 'list'], 'categories'),
    'labs-list': (['labs', 'list'], 'labs'),
    'cards-list': (['cards', 'list'], 'cards'),
}


@pytest.fixture(autouse=True)
def fixture_library(monkeypatch):
    """The fixture library, with the index cut to the collections it holds rather than this box's shell."""
    monkeypatch.setattr(tools, 'REGISTRY', FIXTURES / 'labs-registry.yml')
    monkeypatch.setattr(cards, 'CARDS_DIR', FIXTURES / 'cards')
    monkeypatch.setattr(index, 'CARDS_DIR', FIXTURES / 'cards')
    monkeypatch.setattr(labs, 'LABS_DIR', FIXTURES / 'labs')
    monkeypatch.setattr(index, 'LENSES', {'tool': index.index_tools, 'card': index.index_cards})


@pytest.mark.parametrize('schema', sorted(READS))
def test_the_document_matches_its_published_schema(schema):
    command, key = READS[schema]
    published = json.loads((SCHEMAS / f'{schema}.schema.json').read_text())
    Draft7Validator.check_schema(published)

    result = runner.invoke(app, [*command, '--json'])

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document[key], 'an empty array matches any row shape, so the fixture has to fill it'
    Draft7Validator(published).validate(document)


def commands_taking_json(command: Any, path: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    found = {path} if any('--json' in getattr(param, 'opts', ()) for param in command.params) else set()
    for name, child in getattr(command, 'commands', {}).items():
        found |= commands_taking_json(child, (*path, name))
    return found


def test_every_json_read_has_a_schema_and_every_schema_a_read():
    assert commands_taking_json(typer.main.get_command(app)) == {tuple(command) for command, _ in READS.values()}
    assert {path.name.removesuffix('.schema.json') for path in SCHEMAS.glob('*.schema.json')} == set(READS)
