from main import greeting

def test_greeting_valid():
    assert greeting("alex") == "Hello, Alex"

def test_greeting_empty():
    assert greeting("   ") == "Hello, Stranger!"

def test_greeting_mixed_case():
    assert greeting("iVAN") == "Hello, Ivan"

def test_greeting_with_leading_trailing_spaces():
    assert greeting("  alice  ") == "Hello, Alice"

def test_greeting_all_uppercase():
    assert greeting("BOB") == "Hello, Bob"

def test_greeting_all_lowercase():
    assert greeting("charlie") == "Hello, Charlie"

def test_greeting_single_character():
    assert greeting("z") == "Hello, Z"

def test_greeting_single_character_with_spaces():
    assert greeting("  z  ") == "Hello, Z"

def test_greeting_multiple_words():
    assert greeting("john doe") == "Hello, John Doe"

def test_greeting_multiple_words_mixed_case():
    assert greeting("jANE dOE") == "Hello, Jane Doe"

def test_greeting_empty_string():
    assert greeting("") == "Hello, Stranger!"

def test_greeting_only_newlines():
    assert greeting("\n\n") == "Hello, Stranger!"

def test_greeting_with_tabs():
    assert greeting("\tmary\t") == "Hello, Mary"

def test_greeting_special_characters_preserved():
    assert greeting("o'neil") == "Hello, O'Neil"

def test_greeting_numbers_in_name():
    assert greeting("john123") == "Hello, John123"

if __name__ == "__main__":
    test_greeting_valid()
    test_greeting_empty()
    test_greeting_mixed_case()
    test_greeting_with_leading_trailing_spaces()
    test_greeting_all_uppercase()
    test_greeting_all_lowercase()
    test_greeting_single_character()
    test_greeting_single_character_with_spaces()
    test_greeting_multiple_words()
    test_greeting_multiple_words_mixed_case()
    test_greeting_empty_string()
    test_greeting_only_newlines()
    test_greeting_with_tabs()
    test_greeting_special_characters_preserved()
    test_greeting_numbers_in_name()
    print("All tests passed!")
