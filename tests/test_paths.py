"""XDG resolution and the library's three rungs.

The empty-string case is the one worth holding: the module reads
``os.environ.get(VAR) or default`` rather than ``os.environ.get(VAR, default)``,
because a variable exported as empty is the shape a partially-initialized shell
produces, and the two-argument form would resolve every path to the root.
"""

from pathlib import Path

import pytest

from howto import paths

RESOLVERS = [
    ('XDG_CONFIG_HOME', paths.xdg_config_home, Path('.config')),
    ('XDG_DATA_HOME', paths.xdg_data_home, Path('.local/share')),
    ('XDG_CACHE_HOME', paths.xdg_cache_home, Path('.cache')),
]


@pytest.mark.parametrize(('var', 'resolve', 'default'), RESOLVERS)
def test_an_xdg_variable_wins_unless_unset_or_empty(monkeypatch, tmp_path, var, resolve, default):
    monkeypatch.setenv(var, str(tmp_path / 'elsewhere'))
    assert resolve() == tmp_path / 'elsewhere'
    monkeypatch.setenv(var, '')
    assert resolve() == Path.home() / default
    monkeypatch.delenv(var)
    assert resolve() == Path.home() / default


@pytest.fixture
def config_home(monkeypatch, tmp_path):
    monkeypatch.delenv('HOWTO_LIBRARY_DIR', raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    (tmp_path / 'config' / 'howto').mkdir(parents=True)
    return tmp_path / 'config' / 'howto' / 'config.toml'


# Asserted rung by rung, each winning over every rung below it. Every rung yields
# a path, so a reordering is invisible to a test that only checks one came back.
def test_each_rung_beats_the_ones_below_it(monkeypatch, tmp_path, config_home):
    assert paths.library_dir() == tmp_path / 'data' / 'terminal-library'
    assert paths.library_source() == 'default'

    config_home.write_text('library_dir = "~/elsewhere/library"\n')
    assert paths.library_dir() == Path.home() / 'elsewhere' / 'library'
    assert paths.library_source() == str(config_home)

    monkeypatch.setenv('HOWTO_LIBRARY_DIR', '/from/the/shell')
    assert paths.library_dir() == Path('/from/the/shell')
    assert paths.library_source() == '$HOWTO_LIBRARY_DIR'

    monkeypatch.setenv('HOWTO_LIBRARY_DIR', '')
    assert paths.library_dir() == Path.home() / 'elsewhere' / 'library'


def test_malformed_config_falls_through_rather_than_breaking_the_run(tmp_path, config_home):
    config_home.write_text('library_dir = [this is not toml\n')
    assert paths.library_dir() == tmp_path / 'data' / 'terminal-library'
