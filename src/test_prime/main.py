"""Greeting module with paranoid, defense-in-depth name formatting.

Security model
--------------
Untrusted input flows through a strict allowlist pipeline; any deviation
raises a typed :class:`SecurityError` and the raw value is never echoed
back to the caller or written to logs:

1. Type check       - ``str`` or ``None`` only.
2. Size guard       - bounded character count and UTF-8 byte length,
                      enforced both before and after NFC normalisation.
3. Unicode hygiene  - NFC normalisation; lone surrogates and
                      unencodable input are rejected before anything
                      else touches them.
4. Char allowlist   - Unicode letters (``L*``) and combining marks
                      (``M*``), the six ASCII whitespace characters, and
                      a fixed set of separators. This rejects ANSI
                      escapes, C0/C1 controls, bidi overrides, zero-width
                      characters, private-use areas, surrogates, and
                      non-ASCII whitespace such as NBSP (U+00A0), which
                      is a known homoglyph-smuggling vector.
5. Whitespace fold  - linear-time ``re`` over ASCII whitespace only.
6. Title-casing     - linear-time ``re`` only.
7. Output guard     - result is re-checked against the same allowlist
                      and length cap before being returned.

Non-goals (explicitly *not* protected against here): timing side
channels, DoS against the caller, and the host environment's terminal
emulator.
"""

from __future__ import annotations

import contextlib
import logging
import re
import sys
import unicodedata
from typing import Final

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger(f"{__name__}.audit")

__all__ = [
    "InvalidNameError",
    "MalformedUnicodeError",
    "NameTooLongError",
    "SecurityError",
    "UnsafeCharacterError",
    "greeting",
    "main",
]


# --- Security limits ---------------------------------------------------------
#
# Hard-coded on purpose: any limit that can be overridden by the
# environment is itself an attack surface.

MAX_INPUT_CHARS: Final[int] = 256
MAX_INPUT_BYTES: Final[int] = 1024
# Worst-case title-casing expansion is 3x (e.g. U+FB03 "ﬃ" -> "FFI"),
# plus room for the fixed greeting prefix and suffix.
MAX_OUTPUT_CHARS: Final[int] = MAX_INPUT_CHARS * 3 + 64


# --- Constants ---------------------------------------------------------------

DEFAULT_NAME: Final[str] = "Stranger"
GREETING_PREFIX: Final[str] = "Hello, "
EMPTY_NAME_SUFFIX: Final[str] = "!"
PROMPT: Final[str] = "What is your name?\n>>> "

# Allowlisted Unicode general categories. ``L*`` covers every letter
# script (Latin, Cyrillic, Greek, Han, Arabic, ...); ``M*`` covers
# combining marks that survive NFC (needed for Indic scripts and a few
# others).
_ALLOWED_CATEGORIES: Final[frozenset[str]] = frozenset(
    {"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc"}
)

# ASCII whitespace *is* allowlisted, but only so that the later folding
# step can consume it. Non-ASCII whitespace (NBSP U+00A0, Ogham space
# U+1680, narrow NBSP U+202F, line separator U+2028, ...) is *not*
# allowlisted: those glyphs are visually indistinguishable from a space
# and are a known smuggling vector, so they must be rejected, not
# silently folded.
_ALLOWED_WHITESPACE: Final[frozenset[str]] = frozenset(
    {" ", "\t", "\n", "\r", "\x0b", "\x0c"}
)

# Separators permitted *between* letters within a name token.
_ALLOWED_SEPARATORS: Final[frozenset[str]] = frozenset(
    {"-", "'", "\u2019"}
)

# Linear-time patterns only. No nested quantifiers over overlapping
# character classes; every match consumes at least one new character.
#
# The fold regex is deliberately ASCII-only. Using ``\s`` here would
# match Unicode whitespace and silently undo the NBSP rejection above.
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"[ \t\n\r\x0b\x0c]+")
_NAME_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*"
)
_TOKEN_SPLIT_RE: Final[re.Pattern[str]] = re.compile(r"(['\u2019-])")
_SEPARATORS: Final[frozenset[str]] = frozenset({"'", "\u2019", "-"})


# --- Errors ------------------------------------------------------------------

class SecurityError(Exception):
    """Base class for any input that fails the security pipeline."""


class InvalidNameError(SecurityError, TypeError):
    """Argument is neither ``str`` nor ``None``.

    Inherits from :class:`TypeError` for backward compatibility with the
    previous public API, which documented ``TypeError`` for bad types.
    """


class NameTooLongError(SecurityError):
    """Input exceeds the character or byte-length limit."""


class UnsafeCharacterError(SecurityError):
    """Input contains a character outside the allowlist."""


class MalformedUnicodeError(SecurityError):
    """Input contains invalid Unicode (lone surrogates, undecodable bytes)."""


# --- Validation --------------------------------------------------------------

def _is_safe_char(ch: str) -> bool:
    """Return ``True`` if ``ch`` is allowed anywhere in a name.

    A character is safe when it is in the ASCII whitespace allowlist,
    is one of the allowlisted separators, or its Unicode general
    category is in :data:`_ALLOWED_CATEGORIES`.

    Args:
        ch: A single-character string.

    Returns:
        ``True`` if the character may appear in a name, ``False`` otherwise.

    Examples:
        >>> _is_safe_char("A")
        True
        >>> _is_safe_char("\\n")
        True
        >>> _is_safe_char("\\u00a0")   # NBSP
        False
    """
    if ch in _ALLOWED_WHITESPACE or ch in _ALLOWED_SEPARATORS:
        return True
    return unicodedata.category(ch) in _ALLOWED_CATEGORIES


def _validate_and_normalize(raw: str) -> str:
    """Run the full security pipeline over a raw name.

    Performs size checks, NFC normalisation, and a per-character
    allowlist check, then collapses ASCII whitespace and trims the
    result.

    Args:
        raw: The raw, untrusted input string.

    Returns:
        The normalised name, or an empty string if the input was blank
        or whitespace-only.

    Raises:
        NameTooLongError: If ``raw`` exceeds the character or byte cap,
            either before or after normalisation.
        MalformedUnicodeError: If ``raw`` contains lone surrogates or
            otherwise cannot be encoded/normalised.
        UnsafeCharacterError: If any character falls outside the allowlist.
    """
    # 1. Cheap character-count guard, before any expensive work.
    if len(raw) > MAX_INPUT_CHARS:
        raise NameTooLongError("input exceeds character limit")

    # 2. Byte-length guard, before normalisation allocates more memory.
    try:
        encoded = raw.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise MalformedUnicodeError("input is not encodable as UTF-8") from exc
    if len(encoded) > MAX_INPUT_BYTES:
        raise NameTooLongError("input exceeds byte limit")

    # 3. NFC normalisation so downstream checks see one canonical form.
    try:
        normalized = unicodedata.normalize("NFC", raw)
    except (TypeError, ValueError) as exc:
        raise MalformedUnicodeError("input is not valid Unicode") from exc

    # Re-check length: NFC can expand the string.
    if len(normalized) > MAX_INPUT_CHARS:
        raise NameTooLongError("normalised input exceeds character limit")

    # 4. Per-character allowlist. Audit without echoing the offending
    #    codepoint, which could itself be a terminal payload.
    for ch in normalized:
        if not _is_safe_char(ch):
            audit_logger.warning(
                "rejected_char category=%s",
                unicodedata.category(ch),
            )
            raise UnsafeCharacterError("input contains a disallowed character")

    # 5. Collapse ASCII whitespace and trim; linear-time regex only.
    return _WHITESPACE_RE.sub(" ", normalized).strip()


# --- Formatting --------------------------------------------------------------

def _capitalize_token(token: str) -> str:
    """Capitalize each sub-part of a name token.

    Sub-parts are separated by hyphens or apostrophes. Each sub-part is
    capitalised independently; the separators are preserved verbatim.

    Args:
        token: A single whitespace-free name token.

    Returns:
        The token in title case with separators preserved.

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
    """Title-case a normalised name, honouring hyphens and apostrophes.

    Args:
        value: A whitespace-normalised, allowlist-validated string.

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
            tabs, newlines, and any mix of letter case. ``None`` is
            treated as an empty name and yields the fallback greeting.

    Returns:
        A formatted greeting string. Returns ``"Hello, Stranger!"`` when
        ``name`` is ``None``, empty, or whitespace-only.

    Raises:
        InvalidNameError: If ``name`` is neither ``str`` nor ``None``.
        NameTooLongError: If ``name`` exceeds the input size limits.
        UnsafeCharacterError: If ``name`` contains a disallowed character.
        MalformedUnicodeError: If ``name`` is not valid, encodable Unicode.

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
    if name is None:
        return f"{GREETING_PREFIX}{DEFAULT_NAME}{EMPTY_NAME_SUFFIX}"

    if not isinstance(name, str):
        raise InvalidNameError("name must be str or None")

    normalized = _validate_and_normalize(name)
    if not normalized:
        return f"{GREETING_PREFIX}{DEFAULT_NAME}{EMPTY_NAME_SUFFIX}"

    formatted = _to_display_name(normalized)

    # Defense in depth: the output must still satisfy the same allowlist
    # and size caps that the input did.
    if len(formatted) > MAX_OUTPUT_CHARS:
        raise NameTooLongError("formatted output exceeds limit")
    for ch in formatted:
        if not _is_safe_char(ch):
            raise UnsafeCharacterError("formatted output is not safe")

    # Template is a fixed constant; the user value is passed as data only.
    return f"{GREETING_PREFIX}{formatted}"


# --- CLI ---------------------------------------------------------------------

def _harden_stdio() -> None:
    """Reconfigure standard streams for a fail-closed CLI.

    Standard input is set to strict error handling so undecodable bytes
    raise rather than being silently replaced. Standard output and
    standard error are left alone: crashing on an unencodable name would
    be a worse outcome than printing it via the default error handler.
    """
    with contextlib.suppress(AttributeError, ValueError, OSError):
        sys.stdin.reconfigure(errors="strict")  # type: ignore[union-attr]


def _read_bounded(prompt: str, limit: int) -> str:
    """Read a single line from stdin without allocating unbounded memory.

    Unlike :func:`input`, this function reads one character at a time and
    raises as soon as ``limit`` is exceeded, after draining the rest of
    the line so the process leaves stdin in a sane state.

    Args:
        prompt: Text printed before reading.
        limit: Maximum number of characters to accept.

    Returns:
        The line with the trailing newline removed.

    Raises:
        NameTooLongError: If more than ``limit`` characters are supplied.
    """
    print(prompt, end="", flush=True)
    buf: list[str] = []
    while True:
        ch = sys.stdin.read(1)
        if not ch or ch == "\n":
            break
        buf.append(ch)
        if len(buf) > limit:
            # Drain the rest of the line; never buffer it.
            while ch and ch != "\n":
                ch = sys.stdin.read(1)
            raise NameTooLongError("input exceeds limit while reading")
    return "".join(buf)


def main() -> int:
    """Run the interactive greeting prompt.

    Reads a bounded line from standard input, prints the formatted
    greeting to standard output, and returns a process exit code.

    Returns:
        ``0`` on success, ``1`` on EOF or interrupt, ``2`` on rejected
        input. The raw input is never echoed back on rejection, since it
        may contain a terminal-control payload.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    _harden_stdio()

    try:
        raw = _read_bounded(PROMPT, MAX_INPUT_CHARS)
    except (EOFError, KeyboardInterrupt):
        print()
        return 1

    try:
        print(greeting(raw))
    except SecurityError as exc:
        # Audit the failure class, never the payload.
        audit_logger.warning("rejected_input reason=%s", type(exc).__name__)
        print("Sorry, that name can't be used.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
