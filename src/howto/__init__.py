"""howto — search, index and show reference material, and keep no state."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version


def tool_version() -> str:
    """This build's version, or 'unknown' from a checkout that was never installed.

    Read from the installed distribution, whose build took the version from the
    release tag, so no copy here can drift behind it.
    """
    try:
        return installed_version('howto')
    except PackageNotFoundError:
        return 'unknown'


__version__ = tool_version()
