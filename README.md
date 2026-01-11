# homeslice

A dotfile management tool that symlinks files from a dotfiles directory to your home directory.

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
# Create/navigate to your dotfiles directory
mkdir ~/dotfiles && cd ~/dotfiles

# Initialize as a homeslice repo
homeslice init

# Add files from your home directory
homeslice add ~/.bashrc ~/.gitconfig

# Add a folder
homeslice add ~/.config/nvim

# Check status
homeslice list
```

## Commands

| Command | Description |
|---------|-------------|
| `init [path]` | Initialize a homeslice repo (default: current directory) |
| `add <files...>` | Move file(s)/folder(s) from $HOME into repo and create symlinks |
| `remove <files...>` | Move file(s)/folder(s) back to $HOME and remove from config |
| `link` | Create symlinks for all tracked files |
| `unlink` | Remove all symlinks (keeps files in repo) |
| `list` / `status` | Show status of tracked files |
| `show <file>` | Show details for a specific file |
| `config` | Show global and repo configuration |
| `version` | Show version |

## How It Works

Run `homeslice init` in your dotfiles directory. This creates:
- `homeslice.toml` - Configuration file listing tracked files

When you `add` a file like `~/.bashrc`:
1. The file is moved to `~/dotfiles/.bashrc`
2. A symlink is created: `~/.bashrc` → `~/dotfiles/.bashrc`
3. The path is added to `homeslice.toml`

When you `remove` a file:
1. The symlink is removed
2. The file is moved back to its original location
3. The path is removed from `homeslice.toml`

## Configuration

Homeslice uses two config files:

**Global config** (`~/.config/homeslice/config.toml`):
```toml
repo_path = "/path/to/your/dotfiles"
```
This is set automatically by `homeslice init` and allows commands to work from anywhere.

**Repo config** (`homeslice.toml` in your dotfiles directory):
```toml
# Simple flat list of files and folders to track
links = [
    ".bashrc",
    ".zshrc",
    ".gitconfig",
    ".config/nvim",
    ".ssh",
]

# Optional: store dotfiles in a subdirectory (default: repo root)
# source_dir = "home"
```

### Partial Folder Tracking

When you only want specific files from a directory:

```toml
links = [".bashrc", ".zshrc"]

[include.".config/karabiner"]
files = ["karabiner.json"]

[include.".config/kitty"]
files = ["kitty.conf", "theme.conf"]
```

## Development

```bash
# Install dependencies
uv sync

# Run linting
just lint

# Bump version
just bump

# Run the CLI
uv run homeslice --help
```

## License

MIT
