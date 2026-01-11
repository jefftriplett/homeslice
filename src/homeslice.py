"""
homeslice - A dotfile management and synchronization tool.

Manages dotfiles by symlinking files from local directories to your home directory.
"""

from __future__ import annotations

__version__ = "2026.1.2"

import os
import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Annotated, Optional

import typer
from pydantic import BaseModel, Field
from rich import print as rprint
from rich.console import Console
from rich.table import Table

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w


# =============================================================================
# Configuration
# =============================================================================

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "homeslice"
CONFIG_FILE = CONFIG_DIR / "config.toml"

console = Console()
app = typer.Typer(
    name="homeslice",
    help="A dotfile management and synchronization tool.",
    no_args_is_help=True,
)


# =============================================================================
# Pydantic Models
# =============================================================================


class RepoConfig(BaseModel):
    """Configuration for a single dotfiles directory."""

    name: str
    path: Path
    ignore: list[str] = Field(default_factory=list)
    home_dir: str = "home"  # subdirectory containing dotfiles to link


class Config(BaseModel):
    """Global homeslice configuration."""

    repos: dict[str, RepoConfig] = Field(default_factory=dict)
    default_ignore: list[str] = Field(
        default_factory=lambda: [
            ".git",
            ".gitignore",
            ".gitmodules",
            "README*",
            "LICENSE*",
        ]
    )


# =============================================================================
# Config Management
# =============================================================================


def load_config() -> Config:
    """Load configuration from TOML file."""
    if not CONFIG_FILE.exists():
        return Config()

    with open(CONFIG_FILE, "rb") as f:
        data = tomllib.load(f)

    repos = {}
    for name, repo_data in data.get("repos", {}).items():
        repo_data["name"] = name
        repo_data["path"] = Path(repo_data["path"])
        repos[name] = RepoConfig(**repo_data)

    return Config(
        repos=repos,
        default_ignore=data.get("default_ignore", Config().default_ignore),
    )


def save_config(config: Config) -> None:
    """Save configuration to TOML file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict = {
        "default_ignore": config.default_ignore,
        "repos": {},
    }

    for name, repo in config.repos.items():
        repo_data = repo.model_dump(exclude={"name"})
        repo_data["path"] = str(repo_data["path"])
        data["repos"][name] = repo_data

    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)


# =============================================================================
# Symlink Operations
# =============================================================================


def should_ignore(path: Path, ignore_patterns: list[str]) -> bool:
    """Check if a path matches any ignore pattern."""
    name = path.name
    for pattern in ignore_patterns:
        if fnmatch(name, pattern):
            return True
    return False


def get_home_subdir(repo: RepoConfig) -> Path:
    """Get the home subdirectory within a repo."""
    return repo.path / repo.home_dir


def iter_linkable_files(repo: RepoConfig, config: Config) -> list[tuple[Path, Path]]:
    """
    Iterate over files that should be symlinked.

    Returns list of (source, target) tuples where:
    - source: path in the repo's home dir
    - target: path in user's home dir
    """
    home_dir = get_home_subdir(repo)
    if not home_dir.exists():
        return []

    ignore_patterns = config.default_ignore + repo.ignore
    links = []

    def walk(rel_path: Path = Path(".")):
        current = home_dir / rel_path
        for item in sorted(current.iterdir()):
            item_rel = (
                rel_path / item.name if rel_path != Path(".") else Path(item.name)
            )

            if should_ignore(item, ignore_patterns):
                continue

            source = home_dir / item_rel
            target = HOME / item_rel

            if item.is_dir() and not item.is_symlink():
                # Check if target exists as a real directory - descend into it
                if target.exists() and target.is_dir() and not target.is_symlink():
                    walk(item_rel)
                else:
                    # Link the whole directory
                    links.append((source, target))
            else:
                links.append((source, target))

    walk()
    return links


def create_symlink(source: Path, target: Path, force: bool = False) -> str:
    """
    Create a symbolic link.

    Returns status message.
    """
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

    # Ensure parent directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create relative symlink
    try:
        rel_source = os.path.relpath(source, target.parent)
        target.symlink_to(rel_source)
        return "linked"
    except OSError as e:
        return f"error: {e}"


def remove_symlink(source: Path, target: Path) -> str:
    """
    Remove a symbolic link if it points to source.

    Returns status message.
    """
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
def init():
    """Initialize homeslice configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        save_config(Config())
        rprint(f"[green]Created config:[/green] {CONFIG_FILE}")
    else:
        rprint(f"[yellow]Config exists:[/yellow] {CONFIG_FILE}")


@app.command()
def add(
    path: Annotated[Path, typer.Argument(help="Path to dotfiles directory")],
    name: Annotated[
        Optional[str], typer.Option("--name", "-n", help="Name for the repo")
    ] = None,
    home_dir: Annotated[
        str, typer.Option("--home-dir", "-d", help="Subdirectory containing dotfiles")
    ] = "home",
):
    """Add a dotfiles directory to track."""
    config = load_config()

    path = path.expanduser().resolve()

    if not path.exists():
        rprint(f"[red]Error:[/red] Path does not exist: {path}")
        raise typer.Exit(1)

    if name is None:
        name = path.name

    if name in config.repos:
        rprint(f"[red]Error:[/red] '{name}' already exists")
        raise typer.Exit(1)

    repo_config = RepoConfig(name=name, path=path, home_dir=home_dir)
    config.repos[name] = repo_config
    save_config(config)

    rprint(f"[green]Added:[/green] {name} ({path})")


@app.command()
def remove(
    name: Annotated[str, typer.Argument(help="Name of the repo to remove")],
    unlink_files: Annotated[
        bool, typer.Option("--unlink", "-u", help="Also remove symlinks")
    ] = True,
):
    """Remove a repo from tracking (does not delete the directory)."""
    config = load_config()

    if name not in config.repos:
        rprint(f"[red]Error:[/red] '{name}' not found")
        raise typer.Exit(1)

    repo = config.repos[name]

    if unlink_files:
        rprint(f"[blue]Unlinking[/blue] {name}...")
        _unlink_repo(repo, config)

    del config.repos[name]
    save_config(config)

    rprint(f"[green]Removed:[/green] {name}")


@app.command("list")
def list_repos():
    """List all tracked directories."""
    config = load_config()

    if not config.repos:
        rprint(
            "[yellow]No directories tracked.[/yellow] Use 'homeslice add <path>' to add one."
        )
        return

    table = Table(title="Tracked Directories")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Home Dir", style="blue")
    table.add_column("Status")

    for name, repo in sorted(config.repos.items()):
        home_path = get_home_subdir(repo)
        if not repo.path.exists():
            status = "[red]missing[/red]"
        elif not home_path.exists():
            status = f"[yellow]no {repo.home_dir}/[/yellow]"
        else:
            status = "[green]ok[/green]"

        table.add_row(name, str(repo.path), repo.home_dir, status)

    console.print(table)


@app.command()
def link(
    repos: Annotated[
        Optional[list[str]], typer.Argument(help="Repos to link (default: all)")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing files")
    ] = False,
):
    """Create symlinks from repo(s) to home directory."""
    config = load_config()

    if not config.repos:
        rprint("[yellow]No directories tracked.[/yellow]")
        return

    repo_names = repos if repos else list(config.repos.keys())

    for name in repo_names:
        if name not in config.repos:
            rprint(f"[red]Error:[/red] '{name}' not found")
            continue

        repo = config.repos[name]
        rprint(f"\n[bold blue]{name}[/bold blue]")
        _link_repo(repo, config, force)


def _link_repo(repo: RepoConfig, config: Config, force: bool = False):
    """Link a single repo."""
    links = iter_linkable_files(repo, config)

    if not links:
        rprint("  [dim]No files to link[/dim]")
        return

    for source, target in links:
        rel_target = target.relative_to(HOME)
        status = create_symlink(source, target, force)

        if status == "linked":
            rprint(f"  [green]linked[/green]    {rel_target}")
        elif status == "identical":
            rprint(f"  [dim]identical[/dim] {rel_target}")
        elif status == "conflict":
            rprint(
                f"  [yellow]conflict[/yellow]  {rel_target} (use --force to overwrite)"
            )
        else:
            rprint(f"  [red]{status}[/red] {rel_target}")


@app.command()
def unlink(
    repos: Annotated[
        Optional[list[str]], typer.Argument(help="Repos to unlink (default: all)")
    ] = None,
):
    """Remove symlinks for repo(s)."""
    config = load_config()

    if not config.repos:
        rprint("[yellow]No directories tracked.[/yellow]")
        return

    repo_names = repos if repos else list(config.repos.keys())

    for name in repo_names:
        if name not in config.repos:
            rprint(f"[red]Error:[/red] '{name}' not found")
            continue

        repo = config.repos[name]
        rprint(f"\n[bold blue]{name}[/bold blue]")
        _unlink_repo(repo, config)


def _unlink_repo(repo: RepoConfig, config: Config):
    """Unlink a single repo."""
    links = iter_linkable_files(repo, config)

    if not links:
        rprint("  [dim]No files to unlink[/dim]")
        return

    for source, target in links:
        rel_target = target.relative_to(HOME)
        status = remove_symlink(source, target)

        if status == "unlinked":
            rprint(f"  [green]unlinked[/green]  {rel_target}")
        elif status == "missing":
            pass  # Silent for missing
        elif status == "not_symlink":
            rprint(f"  [yellow]skipped[/yellow]   {rel_target} (not a symlink)")
        elif status == "different":
            rprint(f"  [yellow]skipped[/yellow]   {rel_target} (points elsewhere)")


@app.command()
def track(
    file: Annotated[Path, typer.Argument(help="File or directory to track")],
    repo: Annotated[str, typer.Argument(help="Repo to add the file to")],
):
    """Move a file/directory into a repo and replace with symlink."""
    config = load_config()

    if repo not in config.repos:
        rprint(f"[red]Error:[/red] '{repo}' not found")
        raise typer.Exit(1)

    repo_config = config.repos[repo]
    home_dir = get_home_subdir(repo_config)

    file = file.expanduser().resolve()

    if not file.exists():
        rprint(f"[red]Error:[/red] File does not exist: {file}")
        raise typer.Exit(1)

    if not str(file).startswith(str(HOME)):
        rprint("[red]Error:[/red] File must be in home directory")
        raise typer.Exit(1)

    # Calculate relative path from home
    rel_path = file.relative_to(HOME)
    target_path = home_dir / rel_path

    if target_path.exists():
        rprint(f"[red]Error:[/red] Already tracked: {rel_path}")
        raise typer.Exit(1)

    # Create parent directories
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Move file to repo
    shutil.move(str(file), str(target_path))
    rprint(f"[blue]Moved[/blue]   {rel_path} -> {target_path}")

    # Create symlink
    rel_source = os.path.relpath(target_path, file.parent)
    file.symlink_to(rel_source)
    rprint(f"[green]Linked[/green]  {rel_path}")


@app.command()
def untrack(
    file: Annotated[Path, typer.Argument(help="Symlinked file to untrack")],
):
    """Move a tracked file back to home and remove from repo."""
    config = load_config()

    file = file.expanduser().resolve()

    if not file.is_symlink():
        rprint(f"[red]Error:[/red] Not a symlink: {file}")
        raise typer.Exit(1)

    # Resolve where the symlink points
    target = file.resolve()

    # Find which repo this belongs to
    found_repo = None
    for repo in config.repos.values():
        home_dir = get_home_subdir(repo)
        try:
            target.relative_to(home_dir)
            found_repo = repo
            break
        except ValueError:
            continue

    if not found_repo:
        rprint("[red]Error:[/red] File is not tracked by any repo")
        raise typer.Exit(1)

    # Remove symlink and move file back
    file.unlink()
    shutil.move(str(target), str(file))

    rel_path = file.relative_to(HOME)
    rprint(f"[green]Untracked[/green] {rel_path}")


@app.command()
def ignore(
    pattern: Annotated[str, typer.Argument(help="Glob pattern to ignore")],
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", "-r", help="Add to specific repo (default: global)"),
    ] = None,
):
    """Add an ignore pattern."""
    config = load_config()

    if repo:
        if repo not in config.repos:
            rprint(f"[red]Error:[/red] '{repo}' not found")
            raise typer.Exit(1)
        config.repos[repo].ignore.append(pattern)
        rprint(f"[green]Added to {repo}:[/green] {pattern}")
    else:
        config.default_ignore.append(pattern)
        rprint(f"[green]Added globally:[/green] {pattern}")

    save_config(config)


@app.command()
def show(
    name: Annotated[str, typer.Argument(help="Repo name")],
):
    """Show details and linkable files for a repo."""
    config = load_config()

    if name not in config.repos:
        rprint(f"[red]Error:[/red] '{name}' not found")
        raise typer.Exit(1)

    repo = config.repos[name]
    home_dir = get_home_subdir(repo)

    rprint(f"[bold]{name}[/bold]")
    rprint(f"  Path: {repo.path}")
    rprint(f"  Home dir: {repo.home_dir}")
    rprint(f"  Ignore: {repo.ignore or '(none)'}")
    rprint()

    if not home_dir.exists():
        rprint(f"  [yellow]Warning:[/yellow] {home_dir} does not exist")
        return

    links = iter_linkable_files(repo, config)
    if links:
        rprint("  [bold]Linkable files:[/bold]")
        for source, target in links:
            rel_target = target.relative_to(HOME)
            if target.is_symlink() and target.resolve() == source.resolve():
                rprint(f"    [green]✓[/green] {rel_target}")
            elif target.exists():
                rprint(f"    [yellow]![/yellow] {rel_target} (exists)")
            else:
                rprint(f"    [dim]○[/dim] {rel_target}")
    else:
        rprint("  [dim]No linkable files[/dim]")


@app.command()
def config_show():
    """Show configuration file path and contents."""
    if not CONFIG_FILE.exists():
        rprint("[yellow]No config file.[/yellow] Run 'homeslice init' first.")
        rprint(f"Path: {CONFIG_FILE}")
        return

    rprint(f"[bold]Config:[/bold] {CONFIG_FILE}\n")
    rprint(CONFIG_FILE.read_text())


@app.command()
def version():
    """Show version."""
    rprint(f"[bold]homeslice[/bold] {__version__}")


if __name__ == "__main__":
    app()
