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
    _read_bounded,  # internal, but it *is* a security boundary
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
            pytest.param("alex", "Alex", id="lowercase"),
            pytest.param("ALEX", "Alex", id="uppercase"),
            pytest.param("iVAN", "Ivan", id="mixed-case"),
            pytest.param("BOB", "Bob", id="uppercase-short"),
            pytest.param("charlie", "Charlie", id="lowercase-long"),
            pytest.param("z", "Z", id="single-char"),
            pytest.param("  z  ", "Z", id="single-char-padded"),
            pytest.param("john doe", "John Doe", id="two-words"),
            pytest.param("jANE dOE", "Jane Doe", id="two-words-mixed"),
            pytest.param("\tmary\t", "Mary", id="tabs-around"),
            pytest.param("o'neil", "O'Neil", id="apostrophe"),
            pytest.param("mary-jane", "Mary-Jane", id="hyphen"),
            pytest.param(
                "o'brien-smith", "O'Brien-Smith", id="apostrophe-hyphen"
            ),
            pytest.param(
                "o\u2019neil", "O\u2019Neil", id="typographic-apostrophe"
            ),
        ],
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
        [
            pytest.param(None, id="none"),
            pytest.param("", id="empty"),
            pytest.param(" ", id="one-space"),
            pytest.param("   ", id="three-spaces"),
            pytest.param("\t", id="tab"),
            pytest.param("\n", id="newline"),
            pytest.param("\r", id="cr"),
            pytest.param("\n\n", id="two-newlines"),
            pytest.param(" \t \n ", id="mixed-whitespace"),
        ],
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
        [
            pytest.param(42, id="int"),
            pytest.param(3.14, id="float"),
            pytest.param(0, id="zero"),
            pytest.param(True, id="bool"),
            pytest.param([], id="list"),
            pytest.param({}, id="dict"),
            pytest.param((), id="tuple"),
            pytest.param(b"alex", id="bytes"),
            pytest.param(bytearray(b"alex"), id="bytearray"),
            pytest.param(object(), id="object"),
        ],
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
        [
            pytest.param("\ud800", id="high-surrogate"),
            pytest.param("\udfff", id="low-surrogate"),
            pytest.param("Jane\ud800Doe", id="high-surrogate-mid"),
            pytest.param("Jane\udfff", id="low-surrogate-trailing"),
        ],
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
        "hostile",
        [
            pytest.param("\x00", id="nul"),
            pytest.param("\x07", id="bell"),
            pytest.param("\x1b", id="escape"),
            pytest.param("\x1b]0;pwned\x07", id="ansi-osc"),
            pytest.param("\x9b", id="c1-csi"),
            pytest.param("\u200b", id="zero-width"),
            pytest.param("\u200e", id="lrm"),
            pytest.param("\u200f", id="rlm"),
            pytest.param("\u202a", id="bidi-lre"),
            pytest.param("\u202e", id="bidi-rlo"),
            pytest.param("\u2066", id="bidi-lri"),
            pytest.param("\ufeff", id="bom-zwnbsp"),
            pytest.param("\u00a0", id="nbsp"),
            pytest.param(".", id="period"),
            pytest.param("!", id="exclamation"),
            pytest.param(",", id="comma"),
            pytest.param("/", id="slash"),
            pytest.param("\\", id="backslash"),
            pytest.param("0", id="ascii-digit"),
        ],
    )
    def test_disallowed_char_anywhere__raises(self, hostile: str) -> None:
        with pytest.raises(UnsafeCharacterError):
            greeting(f"Jane{hostile}Doe")

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("john123", id="trailing-digits"),
            pytest.param("user42", id="digits-inside"),
            pytest.param("x9y", id="digit-between-letters"),
        ],
    )
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
            pytest.param("o'neil", "O'Neil", id="apostrophe-lower"),
            pytest.param("O'NEIL", "O'Neil", id="apostrophe-upper"),
            pytest.param("mary-jane", "Mary-Jane", id="hyphen-lower"),
            pytest.param("MARY-JANE", "Mary-Jane", id="hyphen-upper"),
            pytest.param(
                "o'brien-smith", "O'Brien-Smith", id="both-separators"
            ),
            pytest.param(
                "o\u2019neil", "O\u2019Neil", id="typographic-apostrophe"
            ),
            pytest.param("jean-luc", "Jean-Luc", id="french-hyphen"),
        ],
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
            pytest.param("  mary  ", "Mary", id="surrounding-spaces"),
            pytest.param("\tmary\t", "Mary", id="surrounding-tabs"),
            pytest.param("\nmary\n", "Mary", id="surrounding-newlines"),
            pytest.param("\rmary\r", "Mary", id="surrounding-cr"),
            pytest.param("\x0bmary\x0c", "Mary", id="vt-ff"),
            pytest.param("mary\t\n doe", "Mary Doe", id="tab-newline-inner"),
            pytest.param("jane   doe", "Jane Doe", id="three-spaces-inner"),
            pytest.param(
                "  jane   doe  ", "Jane Doe", id="padded-inner-spaces"
            ),
            pytest.param(
                "\tjane\n\n  doe\n", "Jane Doe", id="mixed-inner"
            ),
        ],
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
        raw = ("\ufb03 " * (MAX_INPUT_CHARS // 2))[:MAX_INPUT_CHARS].rstrip()
        result = greeting(raw)
        assert len(result) <= MAX_OUTPUT_CHARS

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("alex", id="simple"),
            pytest.param("o'neil", id="apostrophe"),
            pytest.param("mary-jane", id="hyphen"),
            pytest.param("o'brien-smith", id="both"),
            pytest.param("jANE dOE", id="two-words"),
        ],
    )
    def test_output__contains_only_allowlisted_characters(self, raw: str) -> None:
        result = greeting(raw)
        display = result[len(GREETING_PREFIX):]
        allowed_marks = {" ", "-", "'", "\u2019"}
        allowed_categories = {"Lu", "Ll", "Lt", "Lm", "Lo", "Mn", "Mc"}
        for ch in display:
            category = unicodedata.category(ch)
            # De Morgan form of (ch in marks or category in cats); kept as
            # an if/else rather than an ``assert ... or ...`` so that the
            # composite-assertion lint rule (PT018) stays quiet.
            if ch not in allowed_marks and category not in allowed_categories:
                pytest.fail(
                    f"disallowed char {ch!r} (category {category}) "
                    f"in output {display!r}"
                )


# =============================================================================
# 10. Logging
# =============================================================================

class TestGreetingLogging:
    """User input must never reach a log record, on any path."""

    def test_rejected_input__never_reaches_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        payload = "Jane\x1b]0;evil\u202eDoe"
        # Combined context managers, as required by ruff's SIM117.
        with caplog.at_level(logging.DEBUG), pytest.raises(
            UnsafeCharacterError
        ):
            greeting(payload)

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert payload not in joined
        assert "\x1b" not in joined
        assert "\u202e" not in joined

    def test_audit_log__records_category_only(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING), pytest.raises(
            UnsafeCharacterError
        ):
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
