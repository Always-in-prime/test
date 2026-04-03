from main import greeting

def test_greeting_valid():
    assert greeting("alex") == "Hello, Alex"

def test_greeting_empty():
    assert greeting("   ") == "Hello, Stranger!"

def test_greeting_mixed_case():
    assert greeting("iVAN") == "Hello, Ivan"

if __name__ == "__main__":
    test_greeting_valid()
    test_greeting_empty()
    test_greeting_mixed_case()
    print("All tests passed!")
