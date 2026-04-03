def greeting(name):
  return f"Hello, {name.strip().title()}"

user_input = input('What is your name?\n>>> ')

print(greeting(user_input))
