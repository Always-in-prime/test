def greeting(name : str) -> str:
  return f"Hello, {name}"

user_input = input('What is your name?\n>>> ')

print(greeting(user_input))
