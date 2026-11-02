"""Isolation from the machine running the suite.

The zsh lens asks the live shell for its keymaps. Left alone, the zsh rows would
depend on whoever runs the suite, and on CI they read empty without anything
failing.

The library's sync log is pointed at the test's own directory.
"""

import pytest

from howto import index
from howto import library


@pytest.fixture(autouse=True)
def isolated_zsh_keymap(monkeypatch):
    """Answer the zsh lens with an empty keymap unless a test supplies its own.

    The cache is cleared before the stub goes in: the stub replaces the cached
    function outright, so there is nothing left to clear on the way out.
    """
    index.zsh_bindkeys.cache_clear()
    monkeypatch.setattr(index, 'zsh_bindkeys', lambda interactive: '')


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(library, 'SYNC_LOG', tmp_path / 'cache' / 'library-sync.log')
    monkeypatch.setattr(library, 'SYNC_LOCK', tmp_path / 'cache' / 'library-sync.log.lock')
