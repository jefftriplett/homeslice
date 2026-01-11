# List available recipes
_default:
    @just --list

# Run linting and formatting
@lint:
    uv tool run ruff check --fix
    uv tool run ruff format
