"""
homeslice - A dotfile management and synchronization tool.

Manages dotfiles by symlinking files from a dotfiles directory to your home directory.
"""

# /// script
# requires-python = "3.11"
# dependencies = [
#   "pydantic",
#   "rich",
#   "tomli-w",
#   "typer",
# ]
# ///

from __future__ import annotations

__version__ = "2026.1.2"

import os
import shutil
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, Field
from rich import print as rprint
from rich.console import Console

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w


# =============================================================================
# Configuration
# =============================================================================

HOME = Path.home()
GLOBAL_CONFIG_DIR = HOME / ".config" / "homeslice"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.toml"
REPO_CONFIG_FILENAME = "homeslice.toml"

console = Console()
app = typer.Typer(
    name="homeslice",
    help="A dotfile management and synchronization tool.",
    no_args_is_help=True,
)


# =============================================================================
# Pydantic Models
# =============================================================================


class GlobalConfig(BaseModel):
    """Global homeslice configuration stored in ~/.config/homeslice/config.toml."""

    repo_path: Path | None = None


class IncludeConfig(BaseModel):
    """Configuration for partial folder tracking."""

    files: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)


class RepoConfig(BaseModel):
    """Repo-specific configuration stored in homeslice.toml."""

    links: list[str] = Field(default_factory=list)
    include: dict[str, IncludeConfig] = Field(default_factory=dict)
    source_dir: str | None = None


# =============================================================================
# Global Config Management
# =============================================================================


def load_global_config() -> GlobalConfig:
    """Load global configuration from ~/.config/homeslice/config.toml."""
    if not GLOBAL_CONFIG_FILE.exists():
        return GlobalConfig()

    with open(GLOBAL_CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)

    if "repo_path" in data and data["repo_path"]:
        data["repo_path"] = Path(data["repo_path"])

    return GlobalConfig(**data)


def save_global_config(config: GlobalConfig) -> None:
    """Save global configuration."""
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = {}
    if config.repo_path:
        data["repo_path"] = str(config.repo_path)

    with open(GLOBAL_CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)


# =============================================================================
# Repo Config Management
# =============================================================================


def find_repo_root_from_cwd() -> Path | None:
    """Find repo root by looking for homeslice.toml in current or parent dirs."""
    current = Path.cwd()
    while current != current.parent:
        if (current / REPO_CONFIG_FILENAME).exists():
            return current
        current = current.parent
    if (current / REPO_CONFIG_FILENAME).exists():
        return current
    return None


def get_repo_root() -> Path:
    """Get repo root from global config or by searching from cwd."""
    # First try to find from current directory
    root = find_repo_root_from_cwd()
    if root:
        return root

    # Fall back to global config
    global_config = load_global_config()
    if global_config.repo_path and global_config.repo_path.exists():
        if (global_config.repo_path / REPO_CONFIG_FILENAME).exists():
            return global_config.repo_path

    rprint("[red]Error:[/red] No homeslice repo found.")
    rprint("  Run 'homeslice init' in your dotfiles directory, or")
    rprint("  Run 'homeslice init <path>' to set up a repo.")
    raise typer.Exit(1)


def load_repo_config(repo_root: Path) -> RepoConfig:
    """Load repo configuration from homeslice.toml."""
    config_file = repo_root / REPO_CONFIG_FILENAME
    if not config_file.exists():
        return RepoConfig()

    with open(config_file, "rb") as f:
        data = tomllib.load(f)

    # Parse include sections
    include = {}
    if "include" in data:
        for path, config in data["include"].items():
            include[path] = IncludeConfig(**config)
        del data["include"]

    return RepoConfig(include=include, **data)


def save_repo_config(repo_root: Path, config: RepoConfig) -> None:
    """Save repo configuration to homeslice.toml."""
    config_file = repo_root / REPO_CONFIG_FILENAME

    data: dict = {"links": config.links}

    if config.source_dir:
        data["source_dir"] = config.source_dir

    if config.include:
        data["include"] = {}
        for path, inc_config in config.include.items():
            data["include"][path] = inc_config.model_dump(exclude_defaults=True)

    with open(config_file, "wb") as f:
        tomli_w.dump(data, f)


# =============================================================================
# Path Utilities
# =============================================================================


def get_source_dir(repo_root: Path, config: RepoConfig) -> Path:
    """Get the source directory within a repo (where dotfiles are stored)."""
    if config.source_dir:
        return repo_root / config.source_dir
    return repo_root


def normalize_path(path: str) -> str:
    """Normalize a path for consistent storage in config."""
    # Remove leading ./ if present
    if path.startswith("./"):
        path = path[2:]
    # Remove trailing slashes
    path = path.rstrip("/")
    return path


def get_include_entry_for_rel_path(
    rel_path: str, config: RepoConfig
) -> tuple[str, IncludeConfig] | None:
    """Find the include entry for a tracked file path."""
    parts = Path(rel_path).parts
    if len(parts) <= 1:
        return None

    parent = normalize_path("/".join(parts[:-1]))
    for folder_path, inc_config in config.include.items():
        if normalize_path(folder_path) == parent:
            return folder_path, inc_config
    return None


def is_tracked_path(rel_path: str, config: RepoConfig) -> bool:
    """Check if a path is tracked via links or include."""
    normalized = normalize_path(rel_path)
    if normalized in config.links:
        return True

    include_entry = get_include_entry_for_rel_path(normalized, config)
    if not include_entry:
        return False

    _, inc_config = include_entry
    filename = Path(normalized).name
    return filename in inc_config.files


# =============================================================================
# Symlink Operations
# =============================================================================


def iter_linkable_files(
    repo_root: Path, config: RepoConfig
) -> list[tuple[Path, Path, str]]:
    """
    Iterate over files that should be symlinked based on config.

    Returns list of (source, target, rel_path) tuples where:
    - source: path in the repo
    - target: path in user's home dir
    - rel_path: the path as stored in config (for display)
    """
    source_dir = get_source_dir(repo_root, config)
    links = []

    # Process links list
    for rel_path in config.links:
        source = source_dir / rel_path
        target = HOME / rel_path
        links.append((source, target, rel_path))

    # Process include sections (partial folder tracking)
    for folder_path, inc_config in config.include.items():
        ignore = set(inc_config.ignore)
        for filename in inc_config.files:
            if filename in ignore:
                continue
            rel_path = f"{folder_path}/{filename}"
            source = source_dir / rel_path
            target = HOME / rel_path
            links.append((source, target, rel_path))

    return links


def create_symlink(source: Path, target: Path, force: bool = False) -> str:
    """Create a symbolic link. Returns status message."""
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current_target = target.resolve()
            if current_target == source.resolve():
                return "identical"
            if force:
                target.unlink()
            else:
                return "conflict"
        elif target.is_dir():
            if force:
                shutil.rmtree(target)
            else:
                return "conflict"
        else:
            if force:
                target.unlink()
            else:
                return "conflict"

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        rel_source = os.path.relpath(source, target.parent)
        target.symlink_to(rel_source)
        return "linked"
    except OSError as e:
        return f"error: {e}"


def remove_symlink(source: Path, target: Path) -> str:
    """Remove a symbolic link if it points to source. Returns status message."""
    if not target.exists() and not target.is_symlink():
        return "missing"

    if not target.is_symlink():
        return "not_symlink"

    current_target = target.resolve()
    if current_target != source.resolve():
        return "different"

    target.unlink()
    return "unlinked"


# =============================================================================
# CLI Commands
# =============================================================================


@app.command()
def init(
    path: Annotated[
        Path | None,
        typer.Argument(help="Path to dotfiles directory (default: current)"),
    ] = None,
    source_dir: Annotated[
        str | None,
        typer.Option("--source-dir", "-s", help="Subdirectory for dotfiles"),
    ] = None,
):
    """Initialize a homeslice dotfiles repo."""
    if path is None:
        repo_root = Path.cwd()
    else:
        repo_root = Path(path).expanduser().resolve()
        if not repo_root.exists():
            repo_root.mkdir(parents=True)
            rprint(f"[green]Created:[/green] {repo_root}")

    repo_config_file = repo_root / REPO_CONFIG_FILENAME

    # Create/update repo config
    if repo_config_file.exists():
        rprint(f"[dim]Exists:[/dim] {repo_config_file}")
    else:
        repo_config = RepoConfig(source_dir=source_dir)
        save_repo_config(repo_root, repo_config)
        rprint(f"[green]Created:[/green] {repo_config_file}")

    # Create source directory if specified
    if source_dir:
        source_path = repo_root / source_dir
        if not source_path.exists():
            source_path.mkdir(parents=True)
            rprint(f"[green]Created:[/green] {source_path}/")
        else:
            rprint(f"[dim]Exists:[/dim] {source_path}/")

    # Update global config to point to this repo
    global_config = load_global_config()
    global_config.repo_path = repo_root
    save_global_config(global_config)
    rprint(f"[green]Set default repo:[/green] {repo_root}")


@app.command()
def add(
    files: Annotated[list[Path], typer.Argument(help="File(s) or directory(s) to add")],
):
    """Move file(s)/directory(s) from $HOME into the repo and create symlink(s)."""
    repo_root = get_repo_root()
    config = load_repo_config(repo_root)
    source_dir = get_source_dir(repo_root, config)

    modified = False

    for file in files:
        file = Path(file).expanduser().absolute()

        if not file.exists() and not file.is_symlink():
            rprint(f"[red]Error:[/red] Does not exist: {file}")
            continue

        if file.is_symlink():
            rprint(f"[yellow]Skipping:[/yellow] {file} (already a symlink)")
            continue

        if not str(file).startswith(str(HOME)):
            rprint(f"[red]Error:[/red] Must be in home directory: {file}")
            continue

        rel_path = str(file.relative_to(HOME))
        target_path = source_dir / rel_path

        if target_path.exists():
            rprint(f"[yellow]Skipping:[/yellow] {rel_path} (already in repo)")
            continue

        # Check if already in config
        normalized = normalize_path(rel_path)
        if is_tracked_path(normalized, config):
            rprint(f"[yellow]Skipping:[/yellow] {rel_path} (already tracked)")
            continue

        # Move file to repo
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file), str(target_path))

        # Create symlink
        rel_source = os.path.relpath(target_path, file.parent)
        file.symlink_to(rel_source)

        # Add to config
        include_entry = get_include_entry_for_rel_path(normalized, config)
        if include_entry:
            _, inc_config = include_entry
            filename = target_path.name
            if filename in inc_config.ignore:
                inc_config.ignore.remove(filename)
            if filename not in inc_config.files:
                inc_config.files.append(filename)
                inc_config.files.sort()
        else:
            config.links.append(normalized)
        modified = True

        rprint(f"[green]Added:[/green] {rel_path}")

    if modified:
        # Sort links for consistent output
        config.links.sort()
        save_repo_config(repo_root, config)


@app.command()
def remove(
    files: Annotated[
        list[Path],
        typer.Argument(help="File(s) or directory(s) to remove from tracking"),
    ],
):
    """Move file(s)/directory(s) back to $HOME and remove from repo."""
    repo_root = get_repo_root()
    config = load_repo_config(repo_root)
    source_dir = get_source_dir(repo_root, config)

    modified = False

    for file in files:
        file = Path(file).expanduser().absolute()

        if not file.is_symlink():
            rprint(f"[red]Error:[/red] Not a symlink: {file}")
            continue

        target = file.resolve()

        try:
            target.relative_to(source_dir)
        except ValueError:
            rprint(f"[red]Error:[/red] Not tracked by this repo: {file}")
            continue

        rel_path = str(file.relative_to(HOME))
        normalized = normalize_path(rel_path)
        include_entry = get_include_entry_for_rel_path(normalized, config)

        # Remove symlink and move file back
        file.unlink()
        shutil.move(str(target), str(file))

        # Remove from config
        if include_entry:
            folder_path, inc_config = include_entry
            filename = Path(normalized).name
            if filename in inc_config.files:
                inc_config.files.remove(filename)
                if not inc_config.files and not inc_config.ignore:
                    del config.include[folder_path]
                modified = True
        if normalized in config.links:
            config.links.remove(normalized)
            modified = True

        rprint(f"[green]Removed:[/green] {rel_path}")

    if modified:
        save_repo_config(repo_root, config)


@app.command()
def link(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing files")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Show what would be done")
    ] = False,
):
    """Create symlinks from repo to home directory."""
    repo_root = get_repo_root()
    config = load_repo_config(repo_root)
    links = iter_linkable_files(repo_root, config)

    if not links:
        rprint("[dim]No files to link[/dim]")
        return

    for source, target, rel_path in links:
        if not source.exists():
            rprint(f"[red]Missing:[/red]   {rel_path} (not in repo)")
            continue

        if dry_run:
            if target.is_symlink() and target.resolve() == source.resolve():
                rprint(f"[dim]Identical:[/dim] {rel_path}")
            elif target.exists():
                if force:
                    rprint(f"[yellow]Would overwrite:[/yellow] {rel_path}")
                else:
                    rprint(f"[yellow]Conflict:[/yellow]  {rel_path} (use --force)")
            else:
                rprint(f"[green]Would link:[/green] {rel_path}")
            continue

        status = create_symlink(source, target, force)

        if status == "linked":
            rprint(f"[green]Linked:[/green]    {rel_path}")
        elif status == "identical":
            rprint(f"[dim]Identical:[/dim] {rel_path}")
        elif status == "conflict":
            rprint(f"[yellow]Conflict:[/yellow]  {rel_path} (use --force)")
        else:
            rprint(f"[red]Error:[/red]     {rel_path}: {status}")


@app.command()
def unlink(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Show what would be done")
    ] = False,
):
    """Remove symlinks for this repo (keeps files in repo)."""
    repo_root = get_repo_root()
    config = load_repo_config(repo_root)
    links = iter_linkable_files(repo_root, config)

    if not links:
        rprint("[dim]No files to unlink[/dim]")
        return

    for source, target, rel_path in links:
        if dry_run:
            if target.is_symlink() and target.resolve() == source.resolve():
                rprint(f"[green]Would unlink:[/green] {rel_path}")
            elif target.is_symlink():
                rprint(f"[yellow]Skipped:[/yellow]  {rel_path} (points elsewhere)")
            elif target.exists():
                rprint(f"[yellow]Skipped:[/yellow]  {rel_path} (not a symlink)")
            continue

        status = remove_symlink(source, target)

        if status == "unlinked":
            rprint(f"[green]Unlinked:[/green] {rel_path}")
        elif status == "missing":
            pass
        elif status == "not_symlink":
            rprint(f"[yellow]Skipped:[/yellow]  {rel_path} (not a symlink)")
        elif status == "different":
            rprint(f"[yellow]Skipped:[/yellow]  {rel_path} (points elsewhere)")


@app.command("list")
@app.command("status")
def status():
    """Show status of tracked files."""
    repo_root = get_repo_root()
    config = load_repo_config(repo_root)
    source_dir = get_source_dir(repo_root, config)

    rprint(f"[bold]Repo:[/bold] {repo_root}")
    rprint(f"[bold]Config:[/bold] {repo_root / REPO_CONFIG_FILENAME}")
    if config.source_dir:
        rprint(f"[bold]Source dir:[/bold] {source_dir}")
    rprint()

    links = iter_linkable_files(repo_root, config)
    if not links:
        rprint("[dim]No files tracked[/dim]")
        return

    for source, target, rel_path in links:
        if not source.exists():
            rprint(f"  [red]✗[/red] {rel_path} (missing from repo)")
        elif target.is_symlink() and target.resolve() == source.resolve():
            rprint(f"  [green]✓[/green] {rel_path}")
        elif target.exists():
            rprint(f"  [yellow]![/yellow] {rel_path} (conflict)")
        else:
            rprint(f"  [dim]○[/dim] {rel_path} (not linked)")


@app.command()
def show(
    file: Annotated[Path, typer.Argument(help="File to show details for")],
):
    """Show details for a specific tracked file."""
    repo_root = get_repo_root()
    config = load_repo_config(repo_root)
    source_dir = get_source_dir(repo_root, config)

    file = Path(file).expanduser().absolute()

    # Get relative path
    try:
        rel_path = str(file.relative_to(HOME))
    except ValueError:
        rprint("[red]Error:[/red] File must be in home directory")
        raise typer.Exit(1)

    normalized = normalize_path(rel_path)
    source = source_dir / normalized
    target = HOME / normalized

    rprint(f"[bold]{rel_path}[/bold]")
    rprint()

    # Check if tracked
    is_tracked = is_tracked_path(normalized, config)
    rprint(f"  Tracked: {'yes' if is_tracked else 'no'}")

    # Check status
    if source.exists():
        rprint(f"  In repo: {source}")
    else:
        rprint("  In repo: [dim]not found[/dim]")

    if target.is_symlink():
        link_target = os.readlink(target)
        resolved = target.resolve()
        if resolved == source.resolve():
            rprint("  Status:  [green]linked[/green]")
        else:
            rprint("  Status:  [yellow]symlink to different target[/yellow]")
        rprint(f"  Link:    {target} -> {link_target}")
    elif target.exists():
        rprint("  Status:  [yellow]conflict (file exists)[/yellow]")
        rprint(f"  Path:    {target}")
    else:
        rprint("  Status:  [dim]not linked[/dim]")


@app.command()
def config():
    """Show configuration."""
    global_config = load_global_config()

    rprint(f"[bold]Global config:[/bold] {GLOBAL_CONFIG_FILE}")
    if global_config.repo_path:
        rprint(f"  repo_path: {global_config.repo_path}")
    else:
        rprint("  [dim](no repo configured)[/dim]")

    rprint()

    try:
        repo_root = get_repo_root()
        repo_config = load_repo_config(repo_root)
        rprint(f"[bold]Repo config:[/bold] {repo_root / REPO_CONFIG_FILENAME}")
        if repo_config.source_dir:
            rprint(f"  source_dir: {repo_config.source_dir}")
        rprint(f"  links: {len(repo_config.links)} files")
        if repo_config.include:
            rprint(f"  include: {len(repo_config.include)} partial folders")
    except SystemExit:
        pass


@app.command()
def version():
    """Show version."""
    rprint(f"[bold]homeslice[/bold] {__version__}")


if __name__ == "__main__":
    app()
