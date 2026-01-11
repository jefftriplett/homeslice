"""Tests for homeslice using pyfakefs."""

from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem
from typer.testing import CliRunner

import homeslice
from homeslice import (
    GlobalConfig,
    IncludeConfig,
    RepoConfig,
    app,
    create_symlink,
    get_source_dir,
    iter_linkable_files,
    load_global_config,
    load_repo_config,
    normalize_path,
    remove_symlink,
    save_global_config,
    save_repo_config,
)

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fake_home(fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake home directory and patch homeslice.HOME."""
    home = Path("/fakehome")
    fs.create_dir(home)
    monkeypatch.setattr(homeslice, "HOME", home)
    return home


@pytest.fixture
def fake_repo(fs: FakeFilesystem, fake_home: Path) -> Path:
    """Create a fake dotfiles repo."""
    repo = fake_home / "dotfiles"
    fs.create_dir(repo)
    return repo


@pytest.fixture
def global_config_dir(
    fs: FakeFilesystem, fake_home: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Create global config directory and patch homeslice constants."""
    config_dir = fake_home / ".config" / "homeslice"
    fs.create_dir(config_dir)
    monkeypatch.setattr(homeslice, "GLOBAL_CONFIG_DIR", config_dir)
    monkeypatch.setattr(homeslice, "GLOBAL_CONFIG_FILE", config_dir / "config.toml")
    return config_dir


@pytest.fixture
def initialized_repo(
    fs: FakeFilesystem,
    fake_repo: Path,
    global_config_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Create an initialized homeslice repo with config files."""
    # Create homeslice.toml
    config = RepoConfig()
    save_repo_config(fake_repo, config)

    # Set global config to point to this repo
    global_config = GlobalConfig(repo_path=fake_repo)
    save_global_config(global_config)

    # Change to repo directory for cwd-based discovery
    monkeypatch.chdir(fake_repo)

    return fake_repo


# =============================================================================
# Test: Path Utilities
# =============================================================================


class TestNormalizePath:
    def test_removes_leading_dot_slash(self):
        assert normalize_path("./.bashrc") == ".bashrc"

    def test_removes_trailing_slash(self):
        assert normalize_path(".config/nvim/") == ".config/nvim"

    def test_removes_both(self):
        assert normalize_path("./.config/nvim/") == ".config/nvim"

    def test_leaves_normal_path_unchanged(self):
        assert normalize_path(".bashrc") == ".bashrc"
        assert normalize_path(".config/nvim") == ".config/nvim"


# =============================================================================
# Test: Global Config
# =============================================================================


class TestGlobalConfig:
    def test_load_nonexistent_returns_empty(self, global_config_dir: Path):
        config = load_global_config()
        assert config.repo_path is None

    def test_save_and_load(self, global_config_dir: Path, fake_repo: Path):
        config = GlobalConfig(repo_path=fake_repo)
        save_global_config(config)

        loaded = load_global_config()
        assert loaded.repo_path == fake_repo

    def test_save_creates_directory(
        self, fs: FakeFilesystem, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        config_dir = fake_home / ".config" / "homeslice2"
        monkeypatch.setattr(homeslice, "GLOBAL_CONFIG_DIR", config_dir)
        monkeypatch.setattr(homeslice, "GLOBAL_CONFIG_FILE", config_dir / "config.toml")

        config = GlobalConfig(repo_path=fake_home / "dotfiles")
        save_global_config(config)

        assert config_dir.exists()
        assert (config_dir / "config.toml").exists()


# =============================================================================
# Test: Repo Config
# =============================================================================


class TestRepoConfig:
    def test_load_nonexistent_returns_defaults(self, fake_repo: Path):
        config = load_repo_config(fake_repo)
        assert config.links == []
        assert config.include == {}
        assert config.source_dir is None

    def test_save_and_load_simple(self, fs: FakeFilesystem, fake_repo: Path):
        config = RepoConfig(links=[".bashrc", ".zshrc"])
        save_repo_config(fake_repo, config)

        loaded = load_repo_config(fake_repo)
        assert loaded.links == [".bashrc", ".zshrc"]

    def test_save_and_load_with_source_dir(self, fs: FakeFilesystem, fake_repo: Path):
        config = RepoConfig(links=[".bashrc"], source_dir="home")
        save_repo_config(fake_repo, config)

        loaded = load_repo_config(fake_repo)
        assert loaded.source_dir == "home"

    def test_save_and_load_with_include(self, fs: FakeFilesystem, fake_repo: Path):
        config = RepoConfig(
            links=[".bashrc"],
            include={
                ".config/karabiner": IncludeConfig(files=["karabiner.json"]),
            },
        )
        save_repo_config(fake_repo, config)

        loaded = load_repo_config(fake_repo)
        assert ".config/karabiner" in loaded.include
        assert loaded.include[".config/karabiner"].files == ["karabiner.json"]


# =============================================================================
# Test: Source Directory
# =============================================================================


class TestGetSourceDir:
    def test_returns_repo_root_by_default(self, fake_repo: Path):
        config = RepoConfig()
        assert get_source_dir(fake_repo, config) == fake_repo

    def test_returns_subdirectory_when_set(self, fake_repo: Path):
        config = RepoConfig(source_dir="home")
        assert get_source_dir(fake_repo, config) == fake_repo / "home"


# =============================================================================
# Test: Iter Linkable Files
# =============================================================================


class TestIterLinkableFiles:
    def test_empty_config_returns_empty(self, fake_repo: Path):
        config = RepoConfig()
        links = iter_linkable_files(fake_repo, config)
        assert links == []

    def test_returns_links_from_config(self, fake_repo: Path, fake_home: Path):
        config = RepoConfig(links=[".bashrc", ".zshrc"])
        links = iter_linkable_files(fake_repo, config)

        assert len(links) == 2
        assert (fake_repo / ".bashrc", fake_home / ".bashrc", ".bashrc") in links
        assert (fake_repo / ".zshrc", fake_home / ".zshrc", ".zshrc") in links

    def test_includes_partial_folder_files(self, fake_repo: Path, fake_home: Path):
        config = RepoConfig(
            links=[".bashrc"],
            include={
                ".config/karabiner": IncludeConfig(files=["karabiner.json"]),
            },
        )
        links = iter_linkable_files(fake_repo, config)

        assert len(links) == 2
        expected_path = ".config/karabiner/karabiner.json"
        assert (
            fake_repo / expected_path,
            fake_home / expected_path,
            expected_path,
        ) in links

    def test_uses_source_dir(self, fake_repo: Path, fake_home: Path):
        config = RepoConfig(links=[".bashrc"], source_dir="home")
        links = iter_linkable_files(fake_repo, config)

        source, target, rel_path = links[0]
        assert source == fake_repo / "home" / ".bashrc"
        assert target == fake_home / ".bashrc"


# =============================================================================
# Test: Symlink Operations
# =============================================================================


class TestCreateSymlink:
    def test_creates_symlink(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# bashrc")

        status = create_symlink(source, target)

        assert status == "linked"
        assert target.is_symlink()
        assert target.resolve() == source

    def test_creates_parent_directories(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".config" / "nvim" / "init.lua"
        target = fake_home / ".config" / "nvim" / "init.lua"
        fs.create_file(source, contents="-- nvim config")

        status = create_symlink(source, target)

        assert status == "linked"
        assert target.is_symlink()

    def test_returns_identical_for_existing_correct_symlink(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# bashrc")
        fs.create_symlink(target, source)

        status = create_symlink(source, target)

        assert status == "identical"

    def test_returns_conflict_for_existing_file(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# repo bashrc")
        fs.create_file(target, contents="# home bashrc")

        status = create_symlink(source, target)

        assert status == "conflict"

    def test_force_overwrites_existing_file(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# repo bashrc")
        fs.create_file(target, contents="# home bashrc")

        status = create_symlink(source, target, force=True)

        assert status == "linked"
        assert target.is_symlink()


class TestRemoveSymlink:
    def test_removes_symlink(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# bashrc")
        fs.create_symlink(target, source)

        status = remove_symlink(source, target)

        assert status == "unlinked"
        assert not target.exists()

    def test_returns_missing_for_nonexistent(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"

        status = remove_symlink(source, target)

        assert status == "missing"

    def test_returns_not_symlink_for_regular_file(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# bashrc")
        fs.create_file(target, contents="# bashrc")

        status = remove_symlink(source, target)

        assert status == "not_symlink"

    def test_returns_different_for_wrong_target(
        self, fs: FakeFilesystem, fake_repo: Path, fake_home: Path
    ):
        source = fake_repo / ".bashrc"
        other = fake_repo / ".other"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# bashrc")
        fs.create_file(other, contents="# other")
        fs.create_symlink(target, other)

        status = remove_symlink(source, target)

        assert status == "different"


# =============================================================================
# Test: CLI Commands
# =============================================================================


class TestInitCommand:
    def test_init_creates_config_file(
        self,
        fs: FakeFilesystem,
        fake_repo: Path,
        global_config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.chdir(fake_repo)

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output
        assert (fake_repo / "homeslice.toml").exists()

    def test_init_with_path_creates_config_file(
        self,
        fs: FakeFilesystem,
        fake_home: Path,
        global_config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        repo = fake_home / "new-dotfiles"
        fs.create_dir(repo)
        monkeypatch.chdir(fake_home)

        result = runner.invoke(app, ["init", str(repo)])

        assert result.exit_code == 0, result.output
        assert (repo / "homeslice.toml").exists()

    def test_init_sets_global_repo_path(
        self,
        fs: FakeFilesystem,
        fake_repo: Path,
        global_config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.chdir(fake_repo)
        runner.invoke(app, ["init"])

        config = load_global_config()
        assert config.repo_path == fake_repo

    def test_init_with_source_dir_creates_directory(
        self,
        fs: FakeFilesystem,
        fake_repo: Path,
        global_config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.chdir(fake_repo)

        result = runner.invoke(app, ["init", "--source-dir", "home"])

        assert result.exit_code == 0, result.output
        assert (fake_repo / "home").exists()

        config = load_repo_config(fake_repo)
        assert config.source_dir == "home"


class TestAddCommand:
    def test_add_moves_file_and_creates_symlink(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        # Create file in home
        bashrc = fake_home / ".bashrc"
        fs.create_file(bashrc, contents="# my bashrc")

        # Add the file
        result = runner.invoke(app, ["add", str(bashrc)])

        assert result.exit_code == 0, result.output
        assert "Added" in result.output

        # File should be moved to repo
        assert (initialized_repo / ".bashrc").exists()
        assert (initialized_repo / ".bashrc").read_text() == "# my bashrc"

        # Symlink should be created
        assert bashrc.is_symlink()

        # Config should be updated
        config = load_repo_config(initialized_repo)
        assert ".bashrc" in config.links

    def test_add_multiple_files(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        fs.create_file(fake_home / ".bashrc", contents="# bashrc")
        fs.create_file(fake_home / ".zshrc", contents="# zshrc")

        result = runner.invoke(
            app, ["add", str(fake_home / ".bashrc"), str(fake_home / ".zshrc")]
        )

        assert result.exit_code == 0, result.output
        config = load_repo_config(initialized_repo)
        assert ".bashrc" in config.links
        assert ".zshrc" in config.links

    def test_add_skips_already_symlinked(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        source = initialized_repo / ".bashrc"
        target = fake_home / ".bashrc"
        fs.create_file(source, contents="# bashrc")
        fs.create_symlink(target, source)

        result = runner.invoke(app, ["add", str(target)])

        assert "already a symlink" in result.output

    def test_add_directory(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        nvim_dir = fake_home / ".config" / "nvim"
        fs.create_dir(nvim_dir)
        fs.create_file(nvim_dir / "init.lua", contents="-- nvim")

        result = runner.invoke(app, ["add", str(nvim_dir)])

        assert result.exit_code == 0, result.output
        assert (initialized_repo / ".config" / "nvim" / "init.lua").exists()
        assert nvim_dir.is_symlink()


class TestRemoveCommand:
    def test_remove_moves_file_back(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        # Add file first
        bashrc = fake_home / ".bashrc"
        fs.create_file(bashrc, contents="# bashrc")
        runner.invoke(app, ["add", str(bashrc)])

        # Remove
        result = runner.invoke(app, ["remove", str(bashrc)])

        assert result.exit_code == 0, result.output
        assert "Removed" in result.output

        # File should be back as regular file
        assert bashrc.exists()
        assert not bashrc.is_symlink()
        assert bashrc.read_text() == "# bashrc"

        # Config should be updated
        config = load_repo_config(initialized_repo)
        assert ".bashrc" not in config.links

    def test_remove_error_on_non_symlink(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        bashrc = fake_home / ".bashrc"
        fs.create_file(bashrc, contents="# bashrc")

        result = runner.invoke(app, ["remove", str(bashrc)])

        assert "Not a symlink" in result.output


class TestLinkCommand:
    def test_link_creates_symlinks(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        # Add file to repo manually
        fs.create_file(initialized_repo / ".bashrc", contents="# bashrc")

        # Update config
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)

        # Link
        result = runner.invoke(app, ["link"])

        assert result.exit_code == 0, result.output
        assert "Linked" in result.output
        assert (fake_home / ".bashrc").is_symlink()

    def test_link_dry_run(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        fs.create_file(initialized_repo / ".bashrc", contents="# bashrc")
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)

        result = runner.invoke(app, ["link", "--dry-run"])

        assert "Would link" in result.output
        assert not (fake_home / ".bashrc").exists()

    def test_link_force_overwrites(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        fs.create_file(initialized_repo / ".bashrc", contents="# repo bashrc")
        fs.create_file(fake_home / ".bashrc", contents="# home bashrc")
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)

        result = runner.invoke(app, ["link", "--force"])

        assert "Linked" in result.output
        assert (fake_home / ".bashrc").is_symlink()


class TestUnlinkCommand:
    def test_unlink_removes_symlinks(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        # Setup: add file to repo and link it
        fs.create_file(initialized_repo / ".bashrc", contents="# bashrc")
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)
        runner.invoke(app, ["link"])

        # Unlink
        result = runner.invoke(app, ["unlink"])

        assert result.exit_code == 0, result.output
        assert "Unlinked" in result.output
        assert not (fake_home / ".bashrc").exists()

        # Config should still have the entry
        config = load_repo_config(initialized_repo)
        assert ".bashrc" in config.links

    def test_unlink_dry_run(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        fs.create_file(initialized_repo / ".bashrc", contents="# bashrc")
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)
        runner.invoke(app, ["link"])

        result = runner.invoke(app, ["unlink", "--dry-run"])

        assert "Would unlink" in result.output
        assert (fake_home / ".bashrc").is_symlink()


class TestStatusCommand:
    def test_status_shows_tracked_files(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        fs.create_file(initialized_repo / ".bashrc", contents="# bashrc")
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)
        runner.invoke(app, ["link"])

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.output
        assert ".bashrc" in result.output

    def test_list_is_alias_for_status(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        fs.create_file(initialized_repo / ".bashrc", contents="# bashrc")
        config = load_repo_config(initialized_repo)
        config.links.append(".bashrc")
        save_repo_config(initialized_repo, config)
        runner.invoke(app, ["link"])

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, result.output
        assert ".bashrc" in result.output


class TestShowCommand:
    def test_show_displays_file_info(
        self, fs: FakeFilesystem, initialized_repo: Path, fake_home: Path
    ):
        bashrc = fake_home / ".bashrc"
        fs.create_file(bashrc, contents="# bashrc")
        runner.invoke(app, ["add", str(bashrc)])

        result = runner.invoke(app, ["show", str(bashrc)])

        assert result.exit_code == 0, result.output
        assert ".bashrc" in result.output
        assert "Tracked: yes" in result.output
        assert "linked" in result.output


class TestVersionCommand:
    def test_version_shows_version(self):
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "homeslice" in result.output
        assert homeslice.__version__ in result.output


class TestConfigCommand:
    def test_config_shows_configuration(
        self, fs: FakeFilesystem, initialized_repo: Path
    ):
        result = runner.invoke(app, ["config"])

        assert result.exit_code == 0, result.output
        assert "Global config" in result.output
        assert "Repo config" in result.output
