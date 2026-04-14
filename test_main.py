"""Unit tests for the greeting module."""

from src.test_prime.main import greeting


def test_greeting_valid():
    """Test greeting with a valid lowercase name."""
    assert greeting("alex") == "Hello, Alex"


def test_greeting_empty():
    """Test greeting with whitespace-only input."""
    assert greeting("   ") == "Hello, Stranger!"


def test_greeting_mixed_case():
    """Test greeting with mixed case input."""
    assert greeting("iVAN") == "Hello, Ivan"


def test_greeting_with_leading_trailing_spaces():
    """Test greeting trims leading and trailing spaces."""
    assert greeting("  alice  ") == "Hello, Alice"


def test_greeting_all_uppercase():
    """Test greeting with all uppercase input."""
    assert greeting("BOB") == "Hello, Bob"


def test_greeting_all_lowercase():
    """Test greeting with all lowercase input."""
    assert greeting("charlie") == "Hello, Charlie"


def test_greeting_single_character():
    """Test greeting with a single character."""
    assert greeting("z") == "Hello, Z"


def test_greeting_single_character_with_spaces():
    """Test greeting with single character surrounded by spaces."""
    assert greeting("  z  ") == "Hello, Z"


def test_greeting_multiple_words():
    """Test greeting with multiple words."""
    assert greeting("john doe") == "Hello, John Doe"


def test_greeting_multiple_words_mixed_case():
    """Test greeting with multiple words in mixed case."""
    assert greeting("jANE dOE") == "Hello, Jane Doe"


def test_greeting_empty_string():
    """Test greeting with empty string."""
    assert greeting("") == "Hello, Stranger!"


def test_greeting_only_newlines():
    """Test greeting with newline characters only."""
    assert greeting("\n\n") == "Hello, Stranger!"


def test_greeting_with_tabs():
    """Test greeting with tab characters."""
    assert greeting("\tmary\t") == "Hello, Mary"


def test_greeting_special_characters_preserved():
    """Test that special characters like apostrophes are preserved."""
    assert greeting("o'neil") == "Hello, O'Neil"


def test_greeting_numbers_in_name():
    """Test that numbers in names are preserved."""
    assert greeting("john123") == "Hello, John123"


if __name__ == "__main__":
    # Run all tests manually without pytest
    test_functions = [
        test_greeting_valid,
        test_greeting_empty,
        test_greeting_mixed_case,
        test_greeting_with_leading_trailing_spaces,
        test_greeting_all_uppercase,
        test_greeting_all_lowercase,
        test_greeting_single_character,
        test_greeting_single_character_with_spaces,
        test_greeting_multiple_words,
        test_greeting_multiple_words_mixed_case,
        test_greeting_empty_string,
        test_greeting_only_newlines,
        test_greeting_with_tabs,
        test_greeting_special_characters_preserved,
        test_greeting_numbers_in_name,
    ]
    
    for test_func in test_functions:
        test_func()
        print(f"✓ {test_func.__name__}")
    
    print("\nAll tests passed!")
