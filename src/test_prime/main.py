"""Greeting module with name formatting functionality."""


def greeting(name: str) -> str:
    """
    Generate a personalized greeting message.
    
    Args:
        name: The name to greet. Can include leading/trailing whitespace.
    
    Returns:
        A formatted greeting string. Returns \"Hello, Stranger!\" if name is empty.
    
    Examples:
        >>> greeting(\"alex\")
        'Hello, Alex'
        >>> greeting(\"  \")
        'Hello, Stranger!'
        >>> greeting(\"jANE dOE\")
        'Hello, Jane Doe'
    """
    clear_name = name.strip().title()
    return f"Hello, {clear_name}" if clear_name else "Hello, Stranger!"


if __name__ == "__main__":
    user_input = input("What is your name?\n>>> ")
    print(greeting(user_input))
