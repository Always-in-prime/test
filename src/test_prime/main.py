"""Greeting module with robust name formatting functionality.

This module provides a single public entry point, :func:`greeting`, which
turns an arbitrary user-supplied name into a clean, human-readable greeting.
It handles whitespace normalisation, title-casing of hyphenated and
apostrophised names, ``None`` input, and invalid (non-string) input.
"""

from __future__ import annotations

import logging
import re
from typing import Final

logger = logging.getLogger(__name__)


# --- Constants ---------------------------------------------------------------

DEFAULT_NAME: Final[str] = "Stranger"
GREETING_TEMPLATE: Final[str] = "Hello, {name}"
EMPTY_NAME_GREETING: Final[str] = f"Hello, {DEFAULT_NAME}!"
PROMPT: Final[str] = "What is your name?\n>>> "

# Matches one or more Unicode whitespace characters (spaces, tabs,
# newlines, non-breaking spaces, etc.).
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+", re.UNICODE)

# A name token: one or more letters, optionally joined by a hyphen or
# an apostrophe (straight ' or typographic ’). Digits and underscores are
# excluded so they never become part of a capitalised token.
_NAME_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*", re.UNICODE
)

# Splits a token on its separators. The capturing group keeps the
# separators in the resulting list so they can be re-joined untouched.
_TOKEN_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"(['\u2019-])")

# Characters that must be preserved verbatim between capitalised parts.
_SEPARATORS: Final[frozenset[str]] = frozenset({"'", "\u2019", "-"})


# --- Errors ------------------------------------------------------------------

class InvalidNameError(TypeError):
    """Raised when a name argument is neither a string nor ``None``.

    Subclasses :class:`TypeError` so callers that already catch ``TypeError``
    for bad argument types continue to work.
    """


# --- Helpers -----------------------------------------------------------------

def _normalize_whitespace(value: str) -> str:
    """Collapse all whitespace runs into single spaces and trim the ends.

    Args:
        value: Raw input string that may contain spaces, tabs, newlines,
            or Unicode whitespace such as non-breaking spaces.

    Returns:
        The input with every whitespace run replaced by a single space
        and with leading/trailing whitespace removed.

    Examples:
        >>> _normalize_whitespace("  jane\\t\\ndoe  ")
        'jane doe'
    """
    return _WHITESPACE_RE.sub(" ", value).strip()


def _capitalize_token(token: str) -> str:
    """Capitalize each sub-part of a name token.

    Sub-parts are separated by hyphens or apostrophes. Each part is
    capitalised independently while the separators are preserved as-is.
    This yields ``O'Neil`` from ``o'neil`` and ``Mary-Jane`` from
    ``mary-jane``.

    Args:
        token: A single name token produced by :data:`_NAME_TOKEN_RE`.
            It is assumed to contain no whitespace.

    Returns:
        The token in title case, with separators preserved verbatim.

    Examples:
        >>> _capitalize_token("o'neil")
        "O'Neil"
        >>> _capitalize_token("mary-jane")
        'Mary-Jane'
    """
    parts = _TOKEN_SPLIT_RE.split(token)
    return "".join(
        part
        if part in _SEPARATORS
        else part[:1].upper() + part[1:].lower()
        for part in parts
        if part
    )


def _to_display_name(value: str) -> str:
    """Format a whitespace-normalised name for display.

    Every name token (letters possibly joined by ``-`` or ``'``) is
    capitalised; anything else — digits, punctuation, stray characters —
    is left untouched.

    Args:
        value: Whitespace-normalised input string.

    Returns:
        The value with each name token converted to title case.

    Examples:
        >>> _to_display_name("jane doe")
        'Jane Doe'
        >>> _to_display_name("o'brien-smith")
        "O'Brien-Smith"
    """
    return _NAME_TOKEN_RE.sub(lambda m: _capitalize_token(m.group(0)), value)


# --- Public API --------------------------------------------------------------

def greeting(name: str | None) -> str:
    """Generate a personalized greeting message.

    Args:
        name: The name to greet. May contain leading/trailing whitespace,
            tabs or newlines, and any mix of letter case. ``None`` is
            treated as an empty name and yields the fallback greeting.

    Returns:
        A formatted greeting string. Returns ``"Hello, Stranger!"`` when
        ``name`` is ``None``, empty, or whitespace-only.

    Raises:
        InvalidNameError: If ``name`` is neither ``str`` nor ``None``.

    Examples:
        >>> greeting("alex")
        'Hello, Alex'
        >>> greeting("  ")
        'Hello, Stranger!'
        >>> greeting("jANE dOE")
        'Hello, Jane Doe'
        >>> greeting("o'neil")
        "Hello, O'Neil"
        >>> greeting("mary-jane")
        'Hello, Mary-Jane'
        >>> greeting(None)
        'Hello, Stranger!'
    """
    # Fast path: explicit None means "use the default greeting".
    if name is None:
        logger.debug("greeting() received None; using default greeting")
        return EMPTY_NAME_GREETING

    # Reject any non-string input with a clear, typed error.
    if not isinstance(name, str):
        raise InvalidNameError(
            f"name must be str or None, got {type(name).__name__!r}"
        )

    # Collapse tabs, newlines, and repeated spaces into single spaces.
    normalized = _normalize_whitespace(name)
    if not normalized:
        logger.debug("greeting() received blank name; using default greeting")
        return EMPTY_NAME_GREETING

    # Title-case each name token, honouring hyphens and apostrophes.
    formatted = _to_display_name(normalized)
    logger.debug("greeting(): %r -> %r", name, formatted)
    return GREETING_TEMPLATE.format(name=formatted)


# --- CLI ---------------------------------------------------------------------

def main() -> None:
    """Run the interactive greeting prompt.

    Reads a name from standard input, prints the formatted greeting to
    standard output, and exits with status ``1`` on invalid input or
    ``KeyboardInterrupt`` (Ctrl+C).
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        user_input = input(PROMPT)
        print(greeting(user_input))
    except (InvalidNameError, KeyboardInterrupt) as exc:
        logger.error("Failed to greet user: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
