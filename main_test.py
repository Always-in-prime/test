from main import greeting

def test_greeting_with_name():
    assert greeting("ivan") == "Hello, Ivan"

def test_greeting_empty():
    assert greeting("  ") == "Hello, Stranger!"
