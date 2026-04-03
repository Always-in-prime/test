def greeting(name : str) -> str:
  clear_name = name.strip().title()
  if clear_name == "":
    return "Hello, Stranger!"
  else clear_name !="":
    return f"Hello, {clear_name}"

user_input = input('What is your name?\n>>> ')

print(greeting(user_input))
