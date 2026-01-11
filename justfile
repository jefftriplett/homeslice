# List available recipes
_default:
    @just --list

# Run linting and formatting
@lint:
    uv tool run ruff check --fix
    uv tool run ruff format

# Bump CalVer version (format: YYYY.MM.PATCH)
@bump:
    uvx bumpver update --no-fetch

# Run tests
@test *args:
    uv run pytest {{ args }}

# Run tests with verbose output
@test-v:
    uv run pytest -v
