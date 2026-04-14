# Greeting Script

A simple Python script that greets users with their names, featuring clean code and automated testing.

## Features
- **Type Hinting**: Fully annotated functions.
- **Input Cleaning**: Trims whitespace and capitalizes names.
- **Edge Case Handling**: Greets as "Stranger" if no name is provided.
- **CI/CD**: Automated testing via GitHub Actions on every push and pull request.

## How to Run
1. Clone the repository:
   ```bash
   git clone https://github.com/Always-in-prime/test.git
   cd test
   ```
2. Run the script:
   ```bash
   python main.py
   ```

## Testing

### Manual Testing
Run the automated tests manually:
```bash
python test_main.py
```

### Auto Build & CI/CD
This project uses GitHub Actions for continuous integration. Tests are automatically run:
- On every push to any branch
- On every pull request

The CI pipeline:
1. Sets up Python 3.10 environment
2. Runs all unit tests
3. Reports pass/fail status

Check the **Actions** tab in the GitHub repository to view build history and test results.

## Project Structure
```
├── .github/
│   └── workflows/
│       └── python-tests.yml    # CI/CD configuration
├── main.py                     # Main greeting script
├── test_main.py                # Unit tests
├── README.md                   # This file
└── .gitignore                  # Git ignore rules
```
