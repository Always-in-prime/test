def greeting(name: str) -> str:
    """
    Takes a name and returns a formatted greeting string.
    If the name is empty, returns a default greeting.
    """
    clear_name = name.strip().title()
    return f"Hello, {clear_name}" if clear_name else "Hello, Stranger!"


if __name__ == "__main__":
    user_input = input("What is your name?\n>>> ")
    print(greeting(user_input))
