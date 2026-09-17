"""Test Prime - a greeting module with paranoid input handling.

The public API is re-exported here so callers never need to import from
``test_prime.main`` directly::

    from test_prime import greeting, SecurityError
"""

from .main import (
    DEFAULT_NAME,
    GREETING_PREFIX,
    InvalidNameError,
    MalformedUnicodeError,
    NameTooLongError,
    SecurityError,
    UnsafeCharacterError,
    greeting,
)

__all__ = [
    "DEFAULT_NAME",
    "GREETING_PREFIX",
    "InvalidNameError",
    "MalformedUnicodeError",
    "NameTooLongError",
    "SecurityError",
    "UnsafeCharacterError",
    "greeting",
]

#: PEP 440 version. Kept in sync with ``pyproject.toml`` by hand for the
#: 0.x series; switch to ``importlib.metadata.version`` once the package
#: is published.
__version__ = "0.0.1"
