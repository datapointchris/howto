"""XDG base-directory resolution, defined here once so every part of howto agrees
on where the library, the config and the cache live.

The library is a git checkout under the data dir, which ``howto library sync``
keeps current. The one optional config file sits under the config dir. Anything
a recompute can rebuild goes under the cache dir. howto writes no state, so the
state dir is never resolved here.

The library is a path howto does not own, so it resolves in three rungs:
``$HOWTO_LIBRARY_DIR``, then ``library_dir`` in config.toml, then a default.
Each rung answers a different question — the variable is this shell, the config
is this machine, the default is every machine that says nothing.
"""

import os
import tomllib
from pathlib import Path
from typing import Any

LIBRARY_DIR_ENV = 'HOWTO_LIBRARY_DIR'


def xdg_config_home() -> Path:
    """`$XDG_CONFIG_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')


def xdg_data_home() -> Path:
    """`$XDG_DATA_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')


def xdg_cache_home() -> Path:
    """`$XDG_CACHE_HOME`, or its spec default when unset or empty."""
    return Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')


def cache_dir() -> Path:
    """Where howto keeps what it can rebuild: the last sync's outcome, the machine manifest."""
    return xdg_cache_home() / 'howto'


def config_path() -> Path:
    """howto's own config file. Optional — howto runs on defaults alone."""
    return xdg_config_home() / 'howto' / 'config.toml'


def load_config() -> dict[str, Any]:
    """Parse config.toml, answering {} for every way it can fail.

    Optional by design: a machine keeping the library where howto expects it
    should not have to hold a file saying so. Erroring here would break exactly
    that machine, so an unreadable or malformed file falls through to the default.
    """
    try:
        return tomllib.loads(config_path().read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def resolve_path(env_var: str, key: str, default: Path, config: dict[str, Any] | None = None) -> Path:
    """Resolve a shared path: $env_var, then the config key, then the default.

    ``or`` rather than a two-argument get: a variable exported as empty is what a
    partially-initialized shell produces, and taking that as an answer resolves
    the path to the root.
    """
    config = load_config() if config is None else config
    value = os.environ.get(env_var) or config.get(key)
    return Path(value).expanduser() if value else default


def setting_source(env_var: str, key: str, config: dict[str, Any] | None = None) -> str:
    """Which layer supplied a setting.

    Travels with the value because the value alone does not explain itself: an
    empty library is usually a config that was never read, not a wrong path.
    Kept in step with resolve_path by hand.
    """
    config = load_config() if config is None else config
    if os.environ.get(env_var):
        return f'${env_var}'
    if config.get(key):
        return str(config_path())
    return 'default'


def library_dir() -> Path:
    """The library checkout: the cards, the Labs and the tool registry.

    Resolved here once, and every reader reaches into a subdirectory of this
    rather than resolving its own. An override per reader would let two readers
    answer from two checkouts.

    The rungs are what let a second checkout be a pointer rather than a clone. A
    machine that authors cards points one rung at the checkout it commits from,
    so writing a card and reading it are one file.
    """
    return resolve_path(LIBRARY_DIR_ENV, 'library_dir', xdg_data_home() / 'terminal-library')


def library_source() -> str:
    """Which layer named the checkout, for the commands that report it."""
    return setting_source(LIBRARY_DIR_ENV, 'library_dir')
