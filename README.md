# NYT Connection Puzzle Solver

An agentic virtual assistant to help solve the New York Times Connection Puzzle.

## Project Setup

### Virtual Environment (SETUP00)

This project uses a Python 3.11 virtual environment to manage dependencies.

```bash
# Create a virtual environment
/opt/homebrew/bin/python3.11 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

The project relies on the following key packages:

- **Quart** (SETUP01): A Python ASGI web framework with a Flask-like API
- **OpenAI** (SETUP02): Client library for the OpenAI API
- **LangChain & LangGraph** (SETUP02): Framework for developing applications powered by language models
- **Pytest** (SETUP03): Testing framework for Python
- **Black**: Code formatter for Python

All dependencies are listed in the `requirements.txt` file.

## Development

### Code Style

This project follows the Black code style. Format your code with:

```bash
black .
```

### Running Tests

Tests can be run using pytest:

```bash
pytest
```

### Running the Web Application

The web application is built using Quart (an ASGI web framework). More details on how to run the application will be provided as development progresses.