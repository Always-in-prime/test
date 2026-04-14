# Greeting Script

A simple Python script that greets users with their names, featuring clean code and automated testing.

## Features

- **Type Hinting**: Fully annotated functions for better IDE support.
- **Input Cleaning**: Trims whitespace and capitalizes names properly.
- **Edge Case Handling**: Greets as "Stranger" if no name is provided.
- **Well-Tested**: Comprehensive unit tests covering various input scenarios.
- **Package Structure**: Properly organized as an importable Python package.

## Installation

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## How to Run

1. Clone the repository:
   ```bash
   git clone https://github.com/Always-in-prime/test.git
   cd test
   ```

2. Run the script:
   ```bash
   python src/test_prime/main.py
   ```

3. Or use it as a module:
   ```python
   from src.test_prime import greeting
   print(greeting("Alice"))  # Hello, Alice
   ```

## Testing

Run the automated tests:

```bash
python test_main.py
```

Or with pytest (if installed):

```bash
pytest test_main.py -v
```

## Project Structure

```
├── src/
│   └── test_prime/
│       ├── __init__.py      # Package initialization
│       └── main.py          # Main greeting function
├── test_main.py             # Unit tests
├── pyproject.toml           # Project configuration
├── README.md                # This file
└── .gitignore               # Git ignore rules
```

## API

### `greeting(name: str) -> str`

Generate a personalized greeting message.

**Parameters:**
- `name` (str): The name to greet. Can include leading/trailing whitespace.

**Returns:**
- str: A formatted greeting string. Returns "Hello, Stranger!" if name is empty.

**Examples:**
```python
>>> greeting("alex")
'Hello, Alex'
>>> greeting("  ")
'Hello, Stranger!'
>>> greeting("jANE dOE")
'Hello, Jane Doe'
```
