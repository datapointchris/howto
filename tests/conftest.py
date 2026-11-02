"""Isolation from the machine running the suite.

The zsh lens asks the live shell for its keymaps, and the rot report asks this
box's package manifest what it declares. Left alone, a fixture row's bucket and
the zsh rows would depend on whoever runs the suite, and on CI both read empty
without anything failing.

The cache dir is pointed at the test's own directory, because the library's
sync log and the manifest cache both write there.
"""

import pytest

from howto import index
from howto import library
from howto import machine


@pytest.fixture(autouse=True)
def isolated_zsh_keymap(monkeypatch):
    """Answer the zsh lens with an empty keymap unless a test supplies its own.

    The cache is cleared before the stub goes in: the stub replaces the cached
    function outright, so there is nothing left to clear on the way out.
    """
    index.zsh_bindkeys.cache_clear()
    monkeypatch.setattr(index, 'zsh_bindkeys', lambda interactive: '')


@pytest.fixture(autouse=True)
def unknown_machine_manifest(monkeypatch):
    """Answer the manifest with `UNKNOWN` unless a test declares its own.

    `UNKNOWN` is what a box that cannot be asked reports, and every caller
    already falls back to judging rows by PATH there.
    """
    machine.declaration.cache_clear()
    monkeypatch.setattr(machine, 'declaration', lambda: machine.UNKNOWN)


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(machine, 'CACHE_DIR', tmp_path / 'cache')
    monkeypatch.setattr(machine, 'MANIFEST_CACHE', tmp_path / 'cache' / 'machine-manifest.json')
    monkeypatch.setattr(library, 'SYNC_LOG', tmp_path / 'cache' / 'library-sync.log')
    monkeypatch.setattr(library, 'SYNC_LOCK', tmp_path / 'cache' / 'library-sync.log.lock')
