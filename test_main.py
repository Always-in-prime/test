"""Enterprise-grade unit tests for the greeting module.

Test strategy
-------------
The module under test is a security boundary: it accepts untrusted user
input and must never let anything through that could compromise the host
process, its logs, or the operator's terminal. This suite is therefore
organised by *trust boundary*, not by feature, so each class maps to one
invariant that must hold under adversarial input.

Layers
------
1.  Happy path          Formatting is correct for well-formed names.
2.  None / empty        Fallback greeting for absent or blank input.
3.  Type safety         Non-str inputs raise ``InvalidNameError``.
4.  Size limits         Oversized input raises ``NameTooLongError``.
5.  Unicode hygiene     Lone surrogates rejected; NFC normalisation applied.
6.  Char allowlist      Cc/Cf/Zl/Zp/Cs/Co, digits, and stray punctuation
                        raise ``UnsafeCharacterError``.
7.  Separators          Hyphens and both apostrophe glyphs are preserved
                        and each side is capitalised independently.
8.  Whitespace          Tabs, newlines, CR, and runs of spaces collapse
                        to a single ASCII space and are trimmed.
9.  Output invariants   The returned string obeys the same allowlist and
                        length cap as the input, and formatting is
                        idempotent.
10. Logging             Raw user input never reaches a log record; the
                        audit trail records categories only.
11. CLI                 The bounded reader enforces the char cap and
                        drains the rest of the offending line.

Running
-------
    $ pytest -q
    $ pytest -q --cov=src --cov-report=term-missing

Requires ``pytest``. No third-party property-testing library is used so
the suite runs on a bare CI image; property-style invariants are
expressed via ``@pytest.mark.parametrize``.
"""

from __future__ import annotations

import io
import logging
import sys
import unicodedata

import pytest

from src.test_prime.main import (
    EMPTY_NAME_SUFFIX,
    GREETING_PREFIX,
    MAX_INPUT_CHARS,
    MAX_OUTPUT_CHARS,
    InvalidNameError,
    MalformedUnicodeError,
    NameTooLongError,
    SecurityError,
    UnsafeCharacterError,
    _read_bounded,           # internal, but it *is* a security boundary
    greeting,
)


# =============================================================================
# 1. Happy path
# =============================================================================

class TestGreetingHappyPath:
    """Well-formed names are formatted correctly and predictably."""

    @pytest.mark.parametrize(
        ("raw", "expected_display"),
        [
            ("alex", "Alex"),
            ("ALEX", "Alex"),
            ("iVAN", "Ivan"),
            ("BOB", "Bob"),
            ("charlie", "Charlie"),
            ("z", "Z"),
            ("  z  ", "Z"),
            ("john doe", "John Doe"),
            ("jANE dOE", "Jane Doe"),
            ("\tmary\t", "Mary"),
            ("o'neil", "O'Neil"),
            ("mary-jane", "Mary-Jane"),
            ("o'brien-smith", "O'Brien-Smith"),
            ("o\u2019neil", "O\u2019Neil"),  # typographic apostrophe
        ],
        ids=lambda v: repr(v) if isinstance(v, str) else str(v),
    )
    def test_valid_name__formats_correctly(
        self, raw: str, expected_display: str
    ) -> None:
        assert greeting(raw) == f"{GREETING_PREFIX}{expected_display}"


# =============================================================================
# 2. None and empty
# =============================================================================

class TestGreetingNoneAndEmpty:
    """Absent or blank input yields the fallback greeting."""

    @pytest.mark.parametrize(
        "raw",
        [None, "", " ", "   ", "\t", "\n", "\r", "\n\n", " \t \n "],
        ids=repr,
    )
    def test_missing_or_blank__returns_fallback(self, raw: str | None) -> None:
        assert greeting(raw) == f"{GREETING_PREFIX}Stranger{EMPTY_NAME_SUFFIX}"


# =============================================================================
# 3. Type safety
# =============================================================================

class TestGreetingTypeSafety:
    """Non-string arguments are rejected with a typed, catchable error."""

    @pytest.mark.parametrize(
        "bad",
        [42, 3.14, 0, True, [], {}, (), b"alex", bytearray(b"alex"), object()],
        ids=lambda v: type(v).__name__,
    )
    def test_non_string__raises_invalid_name(self, bad: object) -> None:
        with pytest.raises(InvalidNameError):
            greeting(bad)  # type: ignore[arg-type]

    def test_invalid_name__is_security_error(self) -> None:
        # Every rejection path is catchable as a single SecurityError.
        assert issubclass(InvalidNameError, SecurityError)

    def test_invalid_name__is_type_error(self) -> None:
        # Backward compatibility with callers that catch TypeError.
        assert issubclass(InvalidNameError, TypeError)


# =============================================================================
# 4. Size limits
# =============================================================================

class TestGreetingSizeLimits:
    """Inputs above the hard caps are rejected before any processing."""

    def test_at_char_limit__is_accepted(self) -> None:
        raw = "a" * MAX_INPUT_CHARS
        result = greeting(raw)
        assert result.startswith(GREETING_PREFIX)
        assert result[len(GREETING_PREFIX):].lower() == raw

    def test_over_char_limit__raises(self) -> None:
        with pytest.raises(NameTooLongError):
            greeting("a" * (MAX_INPUT_CHARS + 1))

    def test_very_large_input__rejected_immediately(self) -> None:
        # 10 MB of hostility must not be normalised or scanned char-by-char.
        with pytest.raises(NameTooLongError):
            greeting("A" * 10_000_000)

    def test_multibyte_over_byte_limit__raises(self) -> None:
        # Four-byte-per-char letters (U+20000, CJK ext-B) at the char cap
        # land exactly on the byte cap; one char past the char cap trips
        # the char check first, which is the intended ordering.
        with pytest.raises(NameTooLongError):
            greeting("\U00020000" * (MAX_INPUT_CHARS + 1))


# =============================================================================
# 5. Unicode hygiene
# =============================================================================

class TestGreetingUnicodeHygiene:
    """Malformed Unicode is rejected; well-formed Unicode is NFC-normalised."""

    @pytest.mark.parametrize(
        "raw",
        ["\ud800", "\udfff", "Jane\ud800Doe", "Jane\udfff"],
        ids=repr,
    )
    def test_lone_surrogate__raises(self, raw: str) -> None:
        with pytest.raises(MalformedUnicodeError):
            greeting(raw)

    def test_decomposed__normalises_to_nfc(self) -> None:
        nfd = "Jose\u0301"            # e + combining acute
        nfc = "Jos\u00e9"             # precomposed é
        assert greeting(nfd) == greeting(nfc) == f"{GREETING_PREFIX}Jos\u00e9"


# =============================================================================
# 6. Character allowlist
# =============================================================================

class TestGreetingCharacterAllowlist:
    """Characters outside the allowlist raise UnsafeCharacterError."""

    @pytest.mark.parametrize(
        ("label", "hostile"),
        [
            ("nul",           "\x00"),
            ("bell",          "\x07"),
            ("escape",        "\x1b"),
            ("ansi_osc",      "\x1b]0;pwned\x07"),   # terminal-title injection
            ("c1_csi",        "\x9b"),
            ("zero_width",    "\u200b"),
            ("lrm",           "\u200e"),
            ("rlm",           "\u200f"),
            ("bidi_lre",      "\u202a"),
            ("bidi_rlo",      "\u202e"),             # Trojan Source, CVE-2021-42574
            ("bidi_lri",      "\u2066"),
            ("bom_zwnbsp",    "\ufeff"),
            ("nbsp",          "\u00a0"),             # homoglyph smuggling
            ("period",        "."),
            ("exclamation",   "!"),
            ("comma",         ","),
            ("slash",         "/"),
            ("backslash",     "\\"),
            ("ascii_digit",   "0"),
        ],
        ids=lambda v: v if isinstance(v, str) and v.isidentifier() else repr(v),
    )
    def test_disallowed_char_anywhere__raises(
        self, label: str, hostile: str
    ) -> None:
        del label  # used only for the test id
        with pytest.raises(UnsafeCharacterError):
            greeting(f"Jane{hostile}Doe")

    @pytest.mark.parametrize("raw", ["john123", "user42", "x9y"], ids=repr)
    def test_digits_in_name__raise(self, raw: str) -> None:
        # Digits are category Nd, outside the allowlist by design.
        with pytest.raises(UnsafeCharacterError):
            greeting(raw)

    def test_other_scripts__are_allowed(self) -> None:
        # The allowlist is script-agnostic. Homoglyph confusion is an
        # acknowledged residual risk, not a rejection criterion.
        assert greeting("\u0418\u0432\u0430\u043d") == (
            f"{GREETING_PREFIX}\u0418\u0432\u0430\u043d"
        )  # Иван

    def test_combining_marks_survive_nfc__are_allowed(self) -> None:
        # After NFC, only marks that don't compose remain (e.g. Devanagari).
        # They are category Mn and must be permitted.
        assert greeting("\u0915\u094d\u0937").startswith(GREETING_PREFIX)  # क्ष


# =============================================================================
# 7. Separators
# =============================================================================

class TestGreetingSeparators:
    """Hyphens and both apostrophe glyphs are preserved and capitalised."""

    @pytest.mark.parametrize(
        ("raw", "expected_display"),
        [
            ("o'neil", "O'Neil"),
            ("O'NEIL", "O'Neil"),
            ("mary-jane", "Mary-Jane"),
            ("MARY-JANE", "Mary-Jane"),
            ("o'brien-smith", "O'Brien-Smith"),
            ("o\u2019neil", "O\u2019Neil"),
            ("jean-luc", "Jean-Luc"),
        ],
        ids=repr,
    )
    def test_separators__preserved_and_capitalised(
        self, raw: str, expected_display: str
    ) -> None:
        assert greeting(raw) == f"{GREETING_PREFIX}{expected_display}"

    def test_repeated_separators_between_letters__each_letter_capitalised(
        self,
    ) -> None:
        # "a--b" is not a single token; each letter is capitalised on its
        # own. The output must remain within the allowlist.
        assert greeting("a--b") == f"{GREETING_PREFIX}A--B"


# =============================================================================
# 8. Whitespace
# =============================================================================

class TestGreetingWhitespace:
    """All ASCII whitespace collapses to a single space and is trimmed."""

    @pytest.mark.parametrize(
        ("raw", "expected_display"),
        [
            ("  mary  ", "Mary"),
            ("\tmary\t", "Mary"),
            ("\nmary\n", "Mary"),
            ("\rmary\r", "Mary"),
            ("\x0bmary\x0c", "Mary"),
            ("mary\t\n doe", "Mary Doe"),
            ("jane   doe", "Jane Doe"),
            ("  jane   doe  ", "Jane Doe"),
            ("\tjane\n\n  doe\n", "Jane Doe"),
        ],
        ids=repr,
    )
    def test_whitespace__collapsed_and_trimmed(
        self, raw: str, expected_display: str
    ) -> None:
        assert greeting(raw) == f"{GREETING_PREFIX}{expected_display}"

    def test_nbsp__rejected_not_collapsed(self) -> None:
        # NBSP (U+00A0) is category Zs, outside the allowlist, and a
        # known homoglyph-smuggling vector. It must be *rejected*, not
        # silently normalised to a space.
        with pytest.raises(UnsafeCharacterError):
            greeting("jane\u00a0doe")


# =============================================================================
# 9. Output invariants
# =============================================================================

class TestGreetingOutputInvariants:
    """The returned string satisfies the same contract as the input."""

    def test_idempotent(self) -> None:
        once = greeting("o'neil-mcdonald")
        display = once[len(GREETING_PREFIX):]
        assert greeting(display) == once

    def test_output_length__bounded(self) -> None:
        result = greeting("a" * MAX_INPUT_CHARS)
        assert len(result) <= MAX_OUTPUT_CHARS

    def test_title_case_expansion__within_cap(self) -> None:
        # U+FB03 "ﬃ" title-cases to "FFI" (3 chars). A full input of
        # such characters must still fit under MAX_OUTPUT_CHARS, or the
        # module rejects a legitimate script outright.
        raw = "\ufb03 " * (MAX_INPUT_CHARS // 2)
        raw = raw[: MAX_INPUT_CHARS].rstrip()
        result = greeting(raw)
        assert len(result) <= MAX_OUTPUT_CHARS

    @pytest.mark.parametrize(
        "raw",
        ["alex", "o'neil", "mary-jane", "o'brien-smith", "jANE dOE"],
        ids=repr,
    )
    def test_output__contains_only_allowlisted_characters(self, raw: str) -> None:
        result = greeting(raw)
        display = result[len(GREETING_PREFIX):]
        allowed_marks = {" ", "-", "'", "\u2019"}
        allowed_categories = {"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc"}
        for ch in display:
            category = unicodedata.category(ch)
            assert (
                ch in allowed_marks or category in allowed_categories
            ), f"disallowed char {ch!r} (category {category}) in output {display!r}"


# =============================================================================
# 10. Logging
# =============================================================================

class TestGreetingLogging:
    """User input must never reach a log record, on any path."""

    def test_rejected_input__never_reaches_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        payload = "Jane\x1b]0;evil\u202eDoe"
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(UnsafeCharacterError):
                greeting(payload)

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert payload not in joined
        assert "\x1b" not in joined
        assert "\u202e" not in joined

    def test_audit_log__records_category_only(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING):
            with pytest.raises(UnsafeCharacterError):
                greeting("Jane\x1bDoe")

        messages = [r.getMessage() for r in caplog.records]
        assert any("rejected_char" in m and "Cc" in m for m in messages), messages


# =============================================================================
# 11. CLI bounded reader
# =============================================================================

class TestBoundedReader:
    """`_read_bounded` enforces the char cap and leaves stdin consistent."""

    def test_normal_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("alex\n"))
        assert _read_bounded("", MAX_INPUT_CHARS) == "alex"

    def test_eof_returns_partial_line(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("alex"))
        assert _read_bounded("", MAX_INPUT_CHARS) == "alex"

    def test_over_limit__raises_and_drains_line(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        line = "a" * (MAX_INPUT_CHARS + 1) + "b" * 100 + "\nnext\n"
        fake_stdin = io.StringIO(line)
        monkeypatch.setattr(sys, "stdin", fake_stdin)

        with pytest.raises(NameTooLongError):
            _read_bounded("", MAX_INPUT_CHARS)

        # The remainder of the oversized line was drained, not buffered.
        assert fake_stdin.readline() == "next\n"

    def test_empty_line__returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("\n"))
        assert _read_bounded("", MAX_INPUT_CHARS) == ""
