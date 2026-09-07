#!/usr/bin/env python3
"""Isolated migration behavior tests: synthetic history, real Git and native yadm."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dotfiles_migration", ROOT / "scripts/migrate-from-legacy.py")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)
YADM = shutil.which("yadm")
GIT = shutil.which("git")


@unittest.skipUnless(GIT and YADM, "Requires Git and yadm; all worktrees and data are temporary")
class MigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dotfiles migration tests ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.source = self.base / "new checkout"
        self.source.mkdir()
        self.env = {
            "HOME": str(self.home), "PATH": os.environ["PATH"],
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Migration Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Migration Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "LC_ALL": "C",
        }
        environment = mock.patch.dict(os.environ, self.env, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.git("init", "-q", "--initial-branch=main")
        self.storage_file = migration.STORAGE / "Library/Preferences/example.plist"
        self.directory_file = migration.STORAGE / "Library/Application Support/Example/settings"
        self.put(self.source, self.storage_file, b"legacy preferences\x00full data")
        self.put(self.source, self.directory_file, b"directory contents")
        self.put(self.source, ".config/yadm/bootstrap", "#!/bin/sh\nexit 99\n", executable=True)
        self.put(self.source, ".config/yadm/config", "[core]\n sparseCheckout = true\n")
        self.put(self.source, ".config/macos/defaults", "old defaults\n")
        self.put(self.source, ".config/shell/environment", "old shell\n")
        self.put(self.source, ".config/mise/config.toml", '[tools]\n')
        for kind in ("home", "work"):
            self.put(self.source, ".mackup.cfg##class." + kind, "[storage]\nengine=file_system\npath=.config\n")
            self.put(self.source, "Brewfile##class." + kind, "# " + kind + "\n")
        self.put(self.source, "README.md", "fixture\n")
        self.commit("Legacy baseline")
        self.baseline = self.git("rev-parse", "HEAD").strip()
        self.repo = self.home / migration.REPOSITORY
        self.repo.parent.mkdir(parents=True)
        self.git("clone", "--bare", str(self.source), str(self.repo))
        self.target_git("config", "core.bare", "false")
        self.target_git("config", "core.worktree", str(self.home))
        self.target_git("config", "local.class", "home")
        self.target_git("config", "migration.keep", "local-value")
        self.target_git("read-tree", "--reset", "-u", "HEAD")
        self.live_file = self.home / self.storage_file.relative_to(migration.STORAGE)
        self.live_file.parent.mkdir(parents=True)
        self.live_file.symlink_to(self.home / self.storage_file)
        self.live_directory = self.home / "Library/Application Support/Example"
        self.live_directory.parent.mkdir(parents=True)
        self.live_directory.symlink_to(self.home / migration.STORAGE / "Library/Application Support/Example")
        self.put(self.home, migration.STORAGE / "Library/Application Support/Example/local-state", b"untracked application state")
        self.put(self.home, migration.STORAGE / "Library/Application Support/Example/launch-helper",
                 b"#!/bin/sh\nexit 0\n", executable=True)
        self.put(self.home, migration.EXTRA_PREFERENCES, b"extra live hotkeys")
        self.put(self.home, "Library/Unrelated/untouched", b"unrelated application bytes")
        self.put(self.home, migration.HISTORY, b"shared history bytes\n")
        self.put(self.home, ".config/shell/environment.home", b"local environment bytes\n")
        (self.home / ".mackup.cfg").symlink_to(".mackup.cfg##class.home")
        (self.home / "Brewfile").symlink_to("Brewfile##class.home")
        self.binary = self.home / ".local/bin/mise"
        self.put(self.home, ".local/bin/mise", "#!/bin/sh\nprintf '2026.9.1 macos-arm64 (official)\\n'\n", executable=True)
        self.marker = self.home / "unexpected-hook"
        trap = '#!/bin/sh\nprintf executed > "$HOME/unexpected-hook"\nexit 98\n'
        self.put(self.repo, "hooks/post-merge", trap, executable=True)
        self.put(self.home, ".config/yadm/hooks/pre_alt", trap, executable=True)
        self.put(self.home, ".config/yadm/hooks/post_alt", trap, executable=True)
        shutil.rmtree(self.source / migration.STORAGE)
        for kind in ("home", "work"):
            (self.source / (".mackup.cfg##class." + kind)).unlink()
            self.put(self.source, ".config/mise/config.app-preferences.toml##class." + kind,
                     '# profile ' + kind + '\n')
        (self.source / ".config/yadm/bootstrap").unlink()
        (self.source / ".config/macos/defaults").rename(self.source / ".config/macos/defaults-extra")
        self.put(self.source, ".config/mise/config.toml", 'min_version = "2026.9.1"\n')
        self.put(self.source, ".config/shell/environment", "new shell\n")
        self.commit("Current committed configuration")
        self.head = self.git("rev-parse", "HEAD").strip()

    def put(self, root, relative, content, executable=False):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        if executable:
            path.chmod(0o755)
        return path

    def git(self, *args):
        result = subprocess.run([GIT, "-c", "core.hooksPath=" + os.devnull, *args],
                                cwd=self.source, env=self.env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout.decode()

    def target_git(self, *args):
        return self.git("--git-dir=" + str(self.repo), "--work-tree=" + str(self.home), *args)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def operation(self, apply=False):
        return migration.Migration(self.source, self.home, baseline=self.baseline).preflight(apply=apply)

    def apply(self):
        operation = self.operation(apply=True)
        with contextlib.redirect_stdout(io.StringIO()):
            operation.apply()
        return operation

    def snapshot(self, root):
        result = {}
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in [*dirs, *files]:
                path = Path(directory) / name
                info = path.lstat()
                data = os.readlink(path) if path.is_symlink() else (
                    hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
                )
                result[str(path.relative_to(root))] = (info.st_mode, info.st_mtime_ns, data)
        return result

    def ext_helper_url(self):
        helper = self.put(self.base, "ext helper.sh",
                          '#!/bin/sh\nprintf executed > "$HOME/unexpected-ext-helper"\nexit 0\n')
        return "ext::sh " + str(helper).replace("%", "%%").replace(" ", "% ")

    def test_dry_run_is_read_only_and_ignores_untracked_source_notes(self):
        self.put(self.source, "untracked-notes.txt", "not deployed\n")
        before_home = self.snapshot(self.home)
        before_source = self.snapshot(self.source)
        with mock.patch.object(migration.Migration, "stage_mise", side_effect=AssertionError("install during preview")), \
                contextlib.redirect_stdout(io.StringIO()):
            operation = self.operation()
            operation.report()
        self.assertEqual(self.snapshot(self.home), before_home)
        self.assertEqual(self.snapshot(self.source), before_source)
        self.assertFalse((self.home / migration.BACKUPS).exists())
        self.assertEqual(operation.target, self.head)

    def test_successful_home_preserves_referents_private_backups_metadata_and_history(self):
        configuration = (self.repo / "config").read_bytes()
        original_binary = self.binary.read_bytes()
        (self.home / ".config").chmod(0o700)
        (self.home / self.storage_file).chmod(0o644)
        self.live_directory.resolve().chmod(0o755)
        operation = self.apply()
        self.assertEqual(self.target_git("rev-parse", "HEAD").strip(), self.head)
        self.assertEqual((self.repo / "config").read_bytes(), configuration)
        self.assertEqual(self.live_file.read_bytes(), b"legacy preferences\x00full data")
        self.assertFalse(self.live_file.is_symlink())
        self.assertFalse(self.live_directory.is_symlink())
        self.assertEqual((self.live_directory / "local-state").read_bytes(), b"untracked application state")
        self.assertEqual(stat.S_IMODE(self.live_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.live_directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.live_directory / "settings").stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.live_directory / "launch-helper").stat().st_mode), 0o700)
        self.assertTrue(os.access(self.live_directory / "launch-helper", os.X_OK))
        self.assertEqual((self.home / migration.EXTRA_PREFERENCES).read_bytes(), b"extra live hotkeys")
        self.assertEqual((self.home / migration.HISTORY).read_bytes(), b"shared history bytes\n")
        self.assertFalse((self.home / ".local/state/bash/history").exists())
        self.assertEqual((self.home / ".config/shell/environment.home").read_bytes(), b"local environment bytes\n")
        self.assertEqual(self.binary.read_bytes(), original_binary)
        self.assertFalse((self.home / ".config/yadm/bootstrap").exists())
        self.assertFalse((self.home / ".config/macos/defaults").exists())
        self.assertTrue((self.home / ".config/macos/defaults-extra").is_file())
        self.assertFalse((self.home / ".mackup.cfg").is_symlink())
        self.assertFalse(self.marker.exists())
        alternate = self.home / ".config/mise/config.app-preferences.toml"
        self.assertEqual(alternate.resolve().name, "config.app-preferences.toml##class.home")
        self.assertEqual(stat.S_IMODE(operation.backup.stat().st_mode), 0o700)
        private = operation.backup / "home"
        for path in private.rglob("*"):
            self.assertFalse(path.is_symlink())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)
        self.assertEqual((private / self.storage_file).read_bytes(), b"legacy preferences\x00full data")
        self.assertEqual((private / migration.EXTRA_PREFERENCES).read_bytes(), b"extra live hotkeys")
        self.assertFalse((private / "Library/Unrelated").exists())
        self.assertEqual((self.home / "Library/Unrelated/untouched").read_bytes(), b"unrelated application bytes")
        self.assertEqual((operation.backup / "repository/config").read_bytes(), configuration)
        self.assertTrue(os.access(operation.backup / "repository/hooks/post-merge", os.X_OK))
        self.assertEqual(json.loads((operation.backup / "manifest.json").read_text())["checkpoint"], "complete")

    def test_work_class_and_repeated_run_preserve_completed_state(self):
        self.target_git("config", "local.class", "work")
        for name in (".mackup.cfg", "Brewfile"):
            (self.home / name).unlink()
            (self.home / name).symlink_to(name + "##class.work")
        first = self.apply()
        live = self.live_file.read_bytes()
        second = self.apply()
        self.assertNotEqual(first.backup, second.backup)
        self.assertEqual(second.links, [])
        self.assertEqual(self.live_file.read_bytes(), live)
        self.assertEqual((self.home / ".config/mise/config.app-preferences.toml").resolve().name,
                         "config.app-preferences.toml##class.work")
        self.assertEqual(self.target_git("config", "--local", "--get", "local.class").strip(), "work")
        self.assertFalse(self.marker.exists())

    def test_dirty_tracked_target_is_rejected_without_backup_or_mutation(self):
        self.put(self.home, ".config/shell/environment", "local tracked edit\n")
        before = self.snapshot(self.home)
        with self.assertRaisesRegex(migration.MigrationError, "tracked changes"):
            self.operation(apply=True)
        self.assertEqual(self.snapshot(self.home), before)

    def test_dirty_source_apply_rejected_but_preview_uses_committed_head(self):
        self.put(self.source, ".config/shell/environment", "uncommitted source edit\n")
        self.assertTrue(self.operation().source_dirty)
        with self.assertRaisesRegex(migration.MigrationError, "tracked changes in the source"):
            self.operation(apply=True)

    def test_divergent_target_is_rejected(self):
        self.put(self.home, ".config/shell/environment", "divergent edit\n")
        self.target_git("add", ".config/shell/environment")
        self.target_git("commit", "-qm", "Local divergence")
        before = self.snapshot(self.home)
        with self.assertRaisesRegex(migration.MigrationError, "diverged"):
            self.operation(apply=True)
        self.assertEqual(self.snapshot(self.home), before)

    def test_untracked_collision_and_regular_local_alternate_are_rejected(self):
        self.put(self.home, ".config/macos/defaults-extra", "local settings\n")
        with self.assertRaisesRegex(migration.MigrationError, "untracked local file"):
            self.operation()
        (self.home / ".config/macos/defaults-extra").unlink()
        self.put(self.home, ".config/mise/config.app-preferences.toml", "local preference policy\n")
        with self.assertRaisesRegex(migration.MigrationError, "regular local file"):
            self.operation()

    def test_broken_library_link_is_rejected(self):
        self.live_file.unlink()
        self.live_file.symlink_to(self.home / migration.STORAGE / "missing")
        with self.assertRaisesRegex(migration.MigrationError, "broken"):
            self.operation()

    def test_escaping_library_link_and_symlinked_backup_parent_are_rejected(self):
        outside = self.put(self.base, "outside-data", "untouched\n")
        self.live_file.unlink()
        self.live_file.symlink_to(outside)
        with self.assertRaisesRegex(migration.MigrationError, "outside Mackup"):
            self.operation()
        self.live_file.unlink()
        self.live_file.symlink_to(self.home / self.storage_file)
        backup_parent = self.home / migration.BACKUPS
        backup_parent.parent.mkdir(parents=True, exist_ok=True)
        backup_parent.symlink_to(self.base)
        with self.assertRaisesRegex(migration.MigrationError, "symlink"):
            self.operation()
        self.assertEqual(outside.read_text(), "untouched\n")

    def test_backup_failure_precedes_materialization_install_or_git_mutation(self):
        operation = self.operation(apply=True)
        config = (self.repo / "config").read_bytes()
        with mock.patch.object(migration, "checked_copy", side_effect=OSError("simulated storage failure")), \
                mock.patch.object(operation, "stage_mise") as install, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            operation.apply()
        install.assert_not_called()
        self.assertTrue(self.live_file.is_symlink())
        self.assertTrue(self.live_directory.is_symlink())
        self.assertEqual(self.target_git("rev-parse", "HEAD").strip(), self.baseline)
        self.assertEqual((self.repo / "config").read_bytes(), config)

    def test_install_failure_leaves_binary_and_legacy_repository_intact(self):
        self.put(self.home, ".local/bin/mise", "#!/bin/sh\necho '2025.1.0 old'\n", executable=True)
        original = self.binary.read_bytes()
        operation = self.operation(apply=True)
        real_run = migration.run
        def failing_download(args, **kwargs):
            if args[0] == "curl":
                raise migration.MigrationError("Simulated download failure")
            return real_run(args, **kwargs)
        with mock.patch.object(migration, "run", side_effect=failing_download), \
                mock.patch.object(migration.platform, "system", return_value="Darwin"), \
                mock.patch.object(migration.platform, "machine", return_value="arm64"), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(migration.MigrationError, "download failure"):
            operation.apply()
        self.assertEqual(self.binary.read_bytes(), original)
        self.assertTrue(self.live_file.is_symlink())
        self.assertEqual(self.target_git("rev-parse", "HEAD").strip(), self.baseline)
        self.assertEqual(json.loads((operation.backup / "manifest.json").read_text())["checkpoint"], "backup-complete")

    def stage_download(self, *, corrupt=False):
        archive = self.base / "official.tar.gz"
        payload = b"#!/bin/sh\necho '2026.9.1 macos-arm64 (official)'\n"
        with tarfile.open(archive, "w:gz") as handle:
            member = tarfile.TarInfo("mise/bin/mise")
            member.size = len(payload)
            member.mode = 0o755
            handle.addfile(member, io.BytesIO(payload))
        real_run = migration.run
        def download(args, **kwargs):
            if args[0] != "curl":
                return real_run(args, **kwargs)
            self.assertEqual(args[args.index("--connect-timeout") + 1], "15")
            self.assertEqual(args[args.index("--max-time") + 1], "300")
            self.assertTrue(args[-1].startswith("https://github.com/jdx/mise/releases/download/v2026.9.1/"))
            destination = Path(args[args.index("--output") + 1])
            if destination.name == "SHASUMS256.txt":
                digest = "0" * 64 if corrupt else hashlib.sha256(archive.read_bytes()).hexdigest()
                destination.write_text(digest + "  ./mise-v2026.9.1-macos-arm64.tar.gz\n")
            else:
                shutil.copyfile(archive, destination)
            return subprocess.CompletedProcess(args, 0, b"", b"")
        return download, payload

    def test_official_install_is_version_checked_and_does_not_touch_old_formula(self):
        self.binary.unlink()
        formula = self.put(self.home, "formula-placeholder", "unchanged old package\n")
        download, payload = self.stage_download()
        with mock.patch.object(migration, "run", side_effect=download), \
                mock.patch.object(migration.platform, "system", return_value="Darwin"), \
                mock.patch.object(migration.platform, "machine", return_value="arm64"):
            self.apply()
        self.assertEqual(self.binary.read_bytes(), payload)
        self.assertTrue(os.access(self.binary, os.X_OK))
        self.assertFalse(self.binary.is_symlink())
        self.assertEqual(formula.read_text(), "unchanged old package\n")
        self.assertEqual(list(self.binary.parent.glob(".mise-*")), [])

    def test_checksum_failure_does_not_replace_standalone_or_deploy(self):
        self.binary.unlink()
        download, _ = self.stage_download(corrupt=True)
        with mock.patch.object(migration, "run", side_effect=download), \
                mock.patch.object(migration.platform, "system", return_value="Darwin"), \
                mock.patch.object(migration.platform, "machine", return_value="arm64"), \
                self.assertRaisesRegex(migration.MigrationError, "checksum"):
            self.apply()
        self.assertFalse(self.binary.exists())
        self.assertTrue(self.live_file.is_symlink())
        self.assertEqual(self.target_git("rev-parse", "HEAD").strip(), self.baseline)

    def test_missing_class_repository_baseline_or_minimum_fails_closed(self):
        self.target_git("config", "--unset", "local.class")
        with self.assertRaises(migration.MigrationError):
            self.operation()
        self.target_git("config", "local.class", "home")
        with self.assertRaisesRegex(migration.MigrationError, "baseline"):
            migration.Migration(self.source, self.home, baseline="0" * 40).preflight()
        self.put(self.source, ".config/mise/config.toml", "# no minimum\n")
        self.commit("Remove minimum")
        with self.assertRaisesRegex(migration.MigrationError, "min_version"):
            self.operation()
        shutil.rmtree(self.repo)
        with self.assertRaisesRegex(migration.MigrationError, "existing XDG yadm"):
            self.operation()

    def test_home_as_source_and_custom_xdg_fail_closed(self):
        with self.assertRaisesRegex(migration.MigrationError, "separate new checkout"):
            migration.Migration(self.home, self.home, baseline=self.baseline).preflight()
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.base / "custom")}):
            with self.assertRaisesRegex(migration.MigrationError, "Custom XDG"):
                self.operation()

    def test_sparse_checkout_worktree_configuration_migrates_and_is_preserved(self):
        self.target_git("sparse-checkout", "init")
        self.target_git("sparse-checkout", "set", "--no-cone", "/*", "!README.md", "!LICENSE", "!.editorconfig")
        self.assertEqual(self.target_git("config", "--worktree", "--get", "core.worktree").strip(), str(self.home))
        local = (self.repo / "config").read_bytes()
        worktree = (self.repo / "config.worktree").read_bytes()
        sparse = (self.repo / "info/sparse-checkout").read_bytes()
        before = self.snapshot(self.home)
        self.operation()
        self.assertEqual(self.snapshot(self.home), before)
        operation = self.apply()
        self.assertEqual(self.target_git("rev-parse", "HEAD").strip(), self.head)
        self.assertEqual((self.repo / "config").read_bytes(), local)
        self.assertEqual((self.repo / "config.worktree").read_bytes(), worktree)
        self.assertEqual((self.repo / "info/sparse-checkout").read_bytes(), sparse)
        self.assertEqual((operation.backup / "repository/config.worktree").read_bytes(), worktree)
        self.assertFalse((self.home / "README.md").exists())
        self.assertFalse(self.live_file.is_symlink())

    def test_worktree_config_includes_and_filters_are_rejected_in_both_repositories(self):
        for target in (False, True):
            command = self.target_git if target else self.git
            command("config", "extensions.worktreeConfig", "true")
            for key in ("include.path", "includeIf.gitdir:/unmatched/.path", "filter.example.clean"):
                with self.subTest(target=target, key=key):
                    command("config", "--worktree", key, "/nonexistent-migration-fixture")
                    with self.assertRaisesRegex(migration.MigrationError, "includes or content filters"):
                        self.operation()
                    command("config", "--worktree", "--unset", key)

    def test_url_rewrites_are_rejected_without_execution_or_mutation_in_both_repositories(self):
        key = "url." + self.ext_helper_url() + ".insteadOf"
        marker = self.home / "unexpected-ext-helper"
        for target in (False, True):
            command = self.target_git if target else self.git
            command("config", "extensions.worktreeConfig", "true")
            command("config", "protocol.ext.allow", "always")
            for scope in ("--local", "--worktree"):
                command("config", scope, key, str(self.source))
                try:
                    for apply in (False, True):
                        with self.subTest(target=target, scope=scope, apply=apply):
                            before_home = self.snapshot(self.home)
                            before_source = self.snapshot(self.source)
                            with self.assertRaisesRegex(migration.MigrationError, "URL rewrites"):
                                self.operation(apply=apply)
                            self.assertFalse(marker.exists())
                            self.assertFalse((self.home / migration.BACKUPS).exists())
                            self.assertEqual(self.snapshot(self.home), before_home)
                            self.assertEqual(self.snapshot(self.source), before_source)
                finally:
                    command("config", scope, "--unset", key)

    def test_git_fetch_blocks_ext_helper_despite_local_and_inherited_protocol_permissions(self):
        url = self.ext_helper_url()
        marker = self.home / "unexpected-ext-helper"
        self.target_git("config", "protocol.allow", "always")
        self.target_git("config", "protocol.ext.allow", "always")
        before_home = self.snapshot(self.home)
        before_source = self.snapshot(self.source)
        with mock.patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file:ext"}):
            operation = migration.Migration(self.source, self.home, baseline=self.baseline)
            result = operation.git("fetch", "--no-write-fetch-head", url, target=True, ok=(0, 128))
        self.assertFalse(marker.exists())
        self.assertEqual(result.returncode, 128)
        self.assertIn(b"transport 'ext' not allowed", result.stderr)
        self.assertFalse((self.home / migration.BACKUPS).exists())
        self.assertEqual(self.snapshot(self.home), before_home)
        self.assertEqual(self.snapshot(self.source), before_source)

    def test_assume_unchanged_and_sparse_hidden_changes_are_rejected(self):
        self.target_git("update-index", "--assume-unchanged", ".config/shell/environment")
        self.put(self.home, ".config/shell/environment", "hidden modification\n")
        with self.assertRaisesRegex(migration.MigrationError, "assume-unchanged"):
            self.operation()


if __name__ == "__main__":
    unittest.main()
