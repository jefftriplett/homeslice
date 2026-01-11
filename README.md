# homeslice

A dotfile management tool that symlinks files from local directories to your home directory.

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install from source
uv tool install .

# Or run directly without installing
uv run homeslice --help
```

## Quick Start

```bash
# Initialize config
homeslice init

# Add a dotfiles directory
homeslice add ~/dotfiles

# Create symlinks
homeslice link

# Track a new file (moves it to repo and creates symlink)
homeslice track ~/.bashrc dotfiles
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create config directory |
| `add <path>` | Add a dotfiles directory to track |
| `remove <name>` | Remove from tracking |
| `list` | List tracked directories |
| `link [repos...]` | Create symlinks to home |
| `unlink [repos...]` | Remove symlinks |
| `track <file> <repo>` | Move file into repo, create symlink |
| `untrack <file>` | Move file back, remove from repo |
| `show <name>` | Show repo details and linkable files |
| `ignore <pattern>` | Add ignore pattern |

## How It Works

Homeslice tracks local directories containing dotfiles. Each directory should have a `home/` subdirectory with files structured as they should appear in your home directory:

```
~/dotfiles/
  home/
    .bashrc
    .config/
      git/
        config
```

Running `homeslice link` creates symlinks:
- `~/.bashrc` → `~/dotfiles/home/.bashrc`
- `~/.config/git/config` → `~/dotfiles/home/.config/git/config`

If a directory already exists in your home (like `~/.config`), homeslice descends into it rather than replacing it.

## Configuration

Config is stored at `~/.config/homeslice/config.toml`:

```toml
default_ignore = [".git", ".gitignore", ".gitmodules", "README*", "LICENSE*"]

[repos.dotfiles]
path = "/Users/you/dotfiles"
home_dir = "home"
ignore = []
```

## Development

```bash
# Install dependencies
uv sync

# Run linting
just lint

# Run the CLI
uv run homeslice --help
```

## License

MIT
