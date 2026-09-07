#!/usr/bin/env python3
"""Run real mise workflows with isolated HOME and recording external commands."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
MISE = shutil.which("mise")
YADM = shutil.which("yadm")
SOURCES = (
    ".xdg.dirs", ".config/shell/xdg",
    ".config/mise/bootstrap", ".config/mise/config.toml",
    ".config/mise/config.app-preferences.toml##class.home",
    ".config/mise/config.app-preferences.toml##class.work",
    ".config/mise/config.workstation.toml", ".config/macos/defaults-extra",
    ".config/iterm2/defaults", ".config/transmission/defaults",
)
STUB = r'''
import json
import os
from pathlib import Path
import sys

name, args = Path(sys.argv[0]).name, sys.argv[1:]
record = json.dumps({"command": name, "args": args, "cwd": os.getcwd(),
                     "env": {key: value for key, value in os.environ.items()
                             if key.startswith("XDG_") or key in
                             ("CARGO_HOME", "RUSTUP_HOME", "GOPATH", "DOCKER_CONFIG")}}) + "\n"
fd = os.open(os.environ["COMMAND_LOG"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
os.write(fd, record.encode())
os.close(fd)
if name == "defaults":
    if "read-type" in args:
        print("Type is string")
    elif "read" in args:
        print("__isolated_unset__")
    elif "write" not in args:
        sys.exit("Unexpected defaults operation")
elif name == "brew":
    if args == ["bundle"]:
        sys.exit(int(os.environ.get("FAIL_BUNDLE", "0")))
    elif args == ["shellenv"]:
        print('export PATH="' + os.environ["HOMEBREW_PREFIX"] + '/bin:$PATH"')
    elif args not in (["update"], ["upgrade"], ["cleanup"]):
        sys.exit("Unexpected brew operation")
elif name == "yadm":
    if args != ["sparse-checkout", "init"] and args[:3] != ["sparse-checkout", "set", "--no-cone"]:
        sys.exit("Unexpected yadm operation")
elif name == "curl":
    for flag, expected in (("--connect-timeout", "15"), ("--max-time", "300")):
        if args.count(flag) != 1 or args[args.index(flag) + 1] != expected:
            sys.exit("Missing bounded curl timeout: " + flag)
    options = args.copy()
    for flag in ("--connect-timeout", "--max-time"):
        index = options.index(flag)
        del options[index:index + 2]
    if options == ["-fsSL", "https://api.github.com/repos/amnezia-vpn/amnezia-client/releases/latest"]:
        print(os.environ.get("RELEASE_JSON", '{"tag_name": "v1.2.3"}'))
    elif len(options) == 4 and options[:2] == ["-fL", "-o"]:
        destination = Path(options[2]).resolve()
        if destination.parent != Path(os.environ["HOME"], "Downloads").resolve():
            sys.exit("Refusing download outside temporary Downloads")
        if not destination.name.rsplit(".part.", 1)[-1] or ".part." not in destination.name:
            sys.exit("App downloads must use temporary part files")
        if os.environ.get("FAIL_APP_DOWNLOAD"):
            destination.write_bytes(b"partial")
            sys.exit(18)
        destination.write_bytes(b"complete application download")
    else:
        sys.exit("Unexpected curl operation")
elif name == "jq":
    if len(args) != 2 or args[0] != "-er":
        sys.exit("Release lookup must reject missing values")
    try:
        payload = json.load(sys.stdin)
    except (ValueError, TypeError):
        sys.exit(4)
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    if not isinstance(tag, str) or not tag:
        sys.exit(4)
    print(tag)
elif name == "mise":
    if Path(sys.argv[0]).parent != Path(os.environ["HOME"], ".local/bin"):
        sys.exit("Homebrew mise must never be selected")
    if args not in (["upgrade"], ["self-update", "--no-plugins"]):
        sys.exit("Unexpected inner mise operation")
elif name == "sudo":
    if args != ["softwareupdate", "-i", "-a"]:
        sys.exit("Unexpected sudo operation")
elif name not in ("osascript", "zsh", "nvim"):
    sys.exit("Unexpected external command")
'''


@unittest.skipUnless(sys.platform == "darwin" and MISE, "Requires macOS and installed mise")
class MiseBootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mise bootstrap tests ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "isolated home"
        self.home.mkdir()
        self.other = self.base / "other directory"
        self.other.mkdir()
        self.prefix = self.base / "homebrew"
        self.bin = self.prefix / "bin"
        self.bin.mkdir(parents=True)
        self.local_bin = self.home / ".local/bin"
        self.local_bin.mkdir(parents=True)
        self.local_mise = self.local_bin / "mise"
        self.log = self.base / "commands.jsonl"
        self.config = self.home / ".config/mise/config.toml"
        self.config.parent.mkdir(parents=True)
        # Deliberately inherit no MISE/XDG configuration or executable search path.
        self.env = {
            "HOME": str(self.home), "USER": os.environ.get("USER", "test"),
            "PATH": f"{self.local_bin}:{self.bin}:{self.prefix / 'sbin'}:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOMEBREW_PREFIX": str(self.prefix),
            "COMMAND_LOG": str(self.log),
            "TERM": "dumb", "NO_COLOR": "1", "CI": "1", "MISE_YES": "1",
            "MISE_CONFIG_DIR": str(self.config.parent),
            "MISE_SYSTEM_CONFIG_DIR": str(self.base / "system-mise"),
            "MISE_DATA_DIR": str(self.home / ".local/share/mise"),
            "MISE_STATE_DIR": str(self.home / ".local/state/mise"),
            "MISE_CACHE_DIR": str(self.home / "Library/Caches/mise"),
            "MISE_CEILING_PATHS": str(self.base),
            "MISE_TRUSTED_CONFIG_PATHS": str(self.base),
            "MISE_TASK_RUN_AUTO_INSTALL": "false", "MISE_AUTO_INSTALL": "false",
            "TMPDIR": str(self.base / "tmp"),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        }
        for key, value in self.env.items():
            if key.endswith("_DIR") or key == "TMPDIR":
                Path(value).mkdir(parents=True, exist_ok=True)
        (self.home / "Downloads").mkdir()
        self.class_config = self.home / ".local/share/yadm/repo.git/config"
        self.class_config.parent.mkdir(parents=True)
        self.set_machine_class("work")
        for name in ("defaults", "brew", "yadm", "curl", "jq", "osascript", "zsh", "nvim", "sudo"):
            self.make_stub(name)
        self.make_stub("mise")
        self.local_mise.symlink_to(MISE)

        # Before exposing actual domains, prove native mise uses our fake defaults.
        # A failed interception can only affect an absolute temporary plist domain.
        domain = str(self.base / "harmless-probe")
        self.config.write_text(f'[bootstrap.macos.defaults.{json.dumps(domain)}]\nprobe = "intercepted"\n')
        self.assert_success(self.run_mise("bootstrap", "--only", "macos-defaults", "--yes"))
        self.assertTrue(any(row["command"] == "defaults" and row["args"] ==
                            ["write", domain, "probe", "-string", "intercepted"]
                            for row in self.records()),
                        "Safety probe failed; refusing to expose actual preference domains")
        self.clear_records()
        for source in SOURCES:
            destination = self.home / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, destination)
        self.manifest = self.config.parent / "config.app-preferences.toml##class.home"
        entries = tomllib.loads(self.manifest.read_text())["dotfiles"]
        self.assertEqual(len(entries), 13)
        self.snapshots = {}
        for target, entry in entries.items():
            self.assertTrue(target.startswith("~/"))
            source = (self.manifest.parent / entry["source"]).resolve()
            relative = source.relative_to(self.home)
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, source)
            self.snapshots[self.home / target[2:]] = source
        self.production_config = self.config.read_text()
        # Only runtimes are omitted; all production hooks/tasks/preferences remain.
        self.config.write_text(re.sub(r"(?ms)^\[tools\]\n.*?(?=^\[settings\])", "",
                                      self.production_config, count=1))

    def set_machine_class(self, profile):
        self.class_config.write_text(f'[local]\nclass = {json.dumps(profile)}\n')
        if profile in ("home", "work"):
            active = self.config.parent / "config.app-preferences.toml"
            active.unlink(missing_ok=True)
            active.symlink_to(f"config.app-preferences.toml##class.{profile}")

    def set_class_failure(self, state):
        if self.class_config.exists():
            self.class_config.chmod(0o600)
        self.set_machine_class("work")
        if state == "missing-file":
            self.class_config.unlink()
        elif state == "missing-key":
            self.class_config.write_text("[local]\n")
        elif state == "malformed":
            self.class_config.write_text("[invalid config\n")
        elif state == "unreadable":
            self.class_config.chmod(0o000)
        else:
            self.set_machine_class(state)

    def make_stub(self, name, directory=None):
        path = (directory or self.bin) / name
        path.write_text(f"#!{sys.executable}\n" + STUB)
        path.chmod(0o755)

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def clear_records(self):
        self.log.write_text("")

    def run_command(self, *args, env=None):
        return subprocess.run(args, cwd=self.other, env=self.env if env is None else env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)

    def run_mise(self, *args):
        return self.run_command(MISE, "-C", str(self.home), *args,
                                env={**self.env, "MISE_CEILING_PATHS": str(self.home)})

    def bootstrap(self, *args):
        return self.run_mise("-E", "workstation", "bootstrap", "--yes", *args)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout)

    def snapshot_command(self, *args):
        return subprocess.run(
            (MISE, "-C", str(self.home), "-E", "app-preferences", "bootstrap", "dotfiles", *args),
            cwd=self.other, env={**self.env, "MISE_CEILING_PATHS": str(self.home)}, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)

    def assert_snapshot_success(self, result):
        # Native diagnostics can contain private preference content; never echo it.
        self.assertEqual(result.returncode, 0, "App preference command failed")

    def assert_snapshots(self, restored):
        for target, source in self.snapshots.items():
            with self.subTest(target=target.relative_to(self.home)):
                if restored:
                    self.assertTrue(target.is_file() and not target.is_symlink())
                    self.assertTrue(target.read_bytes() == source.read_bytes(),
                                    "Restored snapshot bytes differ")
                    self.assertEqual(target.stat().st_mode & 0o077, 0,
                                     "Restored preferences must remain private")
                else:
                    self.assertFalse(os.path.lexists(target))

    def snapshot_state(self):
        return {path: (path.read_bytes(), path.stat().st_mode)
                for path in (self.manifest, *self.snapshots.values()) if path.exists()}

    def assert_snapshot_idle(self, before, config_mode):
        self.assertTrue(self.snapshot_state() == before, "Snapshot sources or modes changed")
        self.assertEqual((self.home / ".config").stat().st_mode, config_mode)
        self.assert_snapshots(restored=False)
        self.assertEqual(self.records(), [])
        self.assertFalse((self.home / ".config/docker").exists())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])

    def test_app_preferences_apply_capture_round_trip(self):
        self.set_machine_class("home")
        for source in self.snapshots.values():
            source.chmod(0o644)
        manifest = self.manifest.read_bytes()
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        self.assert_snapshots(restored=True)
        self.assertTrue(all(source.stat().st_mode & 0o077 == 0
                            for source in self.snapshots.values()))
        before = self.snapshot_state()
        target, source = next(iter(self.snapshots.items()))
        changed = b"bplist00\x00\xffisolated local preference\x00\x80"
        target.write_bytes(changed)
        self.assert_snapshot_success(self.snapshot_command("add", "--changed", "--no-apply"))
        self.assertTrue(source.read_bytes() == changed, "Capture did not copy local bytes")
        self.assertTrue(target.read_bytes() == changed, "Capture unexpectedly applied files")
        self.assertTrue(self.manifest.read_bytes() == manifest, "Capture changed selection")
        active = self.config.parent / "config.app-preferences.toml"
        self.assertTrue(active.is_symlink(), "Capture replaced the yadm alternate symlink")
        self.assertEqual(active.resolve(), self.manifest)
        self.assertEqual(source.stat().st_mode & 0o077, 0, "Captured preferences must remain private")
        for other_source in self.snapshots.values():
            if other_source != source:
                self.assertTrue((other_source.read_bytes(), other_source.stat().st_mode) ==
                                before[other_source], "Capture changed an unchanged source")
        target.write_bytes(b"second local edit")
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        self.assert_snapshots(restored=True)
        self.assertEqual(self.records(), [])

    def test_app_preferences_preserve_unmanaged_and_archive_targets(self):
        self.set_machine_class("home")
        unmanaged = [self.home / "Library/Preferences/unmanaged-neighbor.plist"]
        archive = ROOT / ".config/app-preferences/archive"
        unmanaged += [self.home / path.relative_to(archive)
                      for path in archive.rglob("*") if path.is_file()]
        self.assertEqual(len(unmanaged), 3)
        for path in unmanaged:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"isolated unmanaged preference")
            path.chmod(0o640)
        before = {path: (path.read_bytes(), path.stat().st_mode) for path in unmanaged}
        for args in (("apply", "--yes"), ("add", "--changed", "--no-apply"), ("apply", "--yes")):
            self.assert_snapshot_success(self.snapshot_command(*args))
            self.assertTrue(all((path.read_bytes(), path.stat().st_mode) == state
                                for path, state in before.items()), "Unmanaged target changed")
        self.assert_snapshots(restored=True)

    def test_app_preferences_status_and_dry_run_are_read_only(self):
        (self.home / ".config").chmod(0o755)
        for source in self.snapshots.values():
            source.chmod(0o644)
        before = self.snapshot_state()
        mode = (self.home / ".config").stat().st_mode
        for profile in ("home", "work"):
            self.set_machine_class(profile)
            for args in (("status",), ("apply", "--dry-run"), ("apply", "--dry-run", "--yes")):
                with self.subTest(profile=profile, args=args):
                    self.assert_snapshot_success(self.snapshot_command(*args))
                    self.assert_snapshot_idle(before, mode)

    def test_app_preferences_work_selects_no_snapshots(self):
        before = self.snapshot_state()
        mode = (self.home / ".config").stat().st_mode
        for args in (("status",), ("apply", "--yes"), ("add", "--changed", "--no-apply")):
            result = self.snapshot_command(*args)
            self.assert_snapshot_success(result)
            self.assert_snapshot_idle(before, mode)

    def test_app_preferences_excludes_project_and_home_configs_and_inherited_env(self):
        self.set_machine_class("home")
        marker = self.home / "unexpected-hook"
        env_script = self.base / "ambient-env.sh"
        env_script.write_text(f'touch {json.dumps(str(marker))}\n')
        unwanted = self.home / "unexpected-dotfile"
        ambient_source = self.base / "ambient-source"
        ambient_source.write_text("unselected config source\n")
        conflict = (f'[dotfiles]\n{json.dumps(str(unwanted))} = '
                    f'{{ source = {json.dumps(str(ambient_source))}, mode = "copy" }}\n'
                    f'[env]\n_.source = {json.dumps(str(env_script))}\n'
                    f'[hooks]\nenter = {json.dumps("touch " + json.dumps(str(marker)))}\n')
        for path in (self.other / "mise.toml", self.home / "mise.toml",
                     self.home / "mise.hostile.toml",
                     self.config.parent / "config.hostile.toml"):
            path.write_text(conflict)
        self.env["MISE_ENV"] = "hostile"
        for args in (("status",), ("apply", "--yes"), ("add", "--changed", "--no-apply")):
            self.assert_snapshot_success(self.snapshot_command(*args))
            self.assertFalse(marker.exists(), "Ambient environment or hook executed")
            self.assertFalse(unwanted.exists(), "Ambient dotfile selection applied")
            self.assertEqual(self.records(), [])
        self.assert_snapshots(restored=True)

    def test_app_preferences_missing_source_fails_without_installation(self):
        self.set_machine_class("home")
        missing = next(iter(self.snapshots.values()))
        missing.unlink()
        before = {path: state[0] for path, state in self.snapshot_state().items()}
        self.assertNotEqual(self.snapshot_command("apply", "--yes").returncode, 0,
                            "Missing source must fail apply")
        self.assertTrue({path: state[0] for path, state in self.snapshot_state().items()} == before,
                        "Failure changed snapshot bytes")
        self.assertEqual(self.records(), [])
        self.assertFalse((self.home / ".config/docker").exists())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])
        self.assertFalse(missing.exists())

    def test_missing_snapshot_stops_finish_before_buildx_and_downloads(self):
        self.set_machine_class("home")
        next(iter(self.snapshots.values())).unlink()
        result = self.run_command("/bin/bash", str(self.home / ".config/mise/bootstrap"), "finish")
        self.assertNotEqual(result.returncode, 0, "Missing snapshot must fail finish")
        self.assertEqual(self.records(), [])
        self.assertFalse((self.home / ".config/docker").exists())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])

    def test_app_preferences_invalid_class_stops_apply_hook(self):
        before = self.snapshot_state()
        mode = (self.home / ".config").stat().st_mode
        for state in ("", "unknown", "missing-file", "missing-key", "malformed", "unreadable"):
            if state == "unreadable" and os.geteuid() == 0:
                continue
            self.set_class_failure(state)
            with self.subTest(state=state):
                result = self.snapshot_command("apply", "--yes")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("local.class", result.stdout)
                self.assert_snapshot_idle(before, mode)

    def test_capture_does_not_add_missing_or_unselected_files(self):
        self.set_machine_class("home")
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        missing = next(iter(self.snapshots))
        missing.unlink()
        unselected = missing.parent / "unselected-capture.plist"
        unselected.write_bytes(b"not selected for capture")
        before = self.snapshot_state()
        self.assert_snapshot_success(self.snapshot_command("add", "--changed", "--no-apply"))
        self.assertFalse(missing.exists(), "Capture must not apply missing targets")
        self.assertTrue(self.snapshot_state() == before, "Capture changed missing or unselected sources")
        self.assertFalse((next(iter(self.snapshots.values())).parent / unselected.name).exists())
        self.assertTrue(unselected.read_bytes() == b"not selected for capture")

    def test_apply_replaces_symlink_without_changing_referent(self):
        self.set_machine_class("home")
        target = next(iter(self.snapshots))
        referent = self.base / "former-symlink-referent"
        referent.write_bytes(b"former external preference")
        referent.chmod(0o640)
        mode = referent.stat().st_mode
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(referent)
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        self.assert_snapshots(restored=True)
        self.assertTrue(referent.read_bytes() == b"former external preference")
        self.assertEqual(referent.stat().st_mode, mode)

    def test_capture_does_not_run_apply_hook(self):
        self.set_machine_class("home")
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        target, source = next(iter(self.snapshots.items()))
        target.write_bytes(b"captured without running the permission hook")
        source.parent.chmod(0o755)
        self.class_config.unlink()
        self.assert_snapshot_success(self.snapshot_command("add", "--changed", "--no-apply"))
        self.assertTrue(source.read_bytes() == target.read_bytes())
        self.assertEqual(source.parent.stat().st_mode & 0o777, 0o755)
        self.assertEqual(self.records(), [])

    def test_missing_active_snapshot_profile_stops_finish(self):
        active = self.config.parent / "config.app-preferences.toml"
        for profile in ("home", "work"):
            with self.subTest(profile=profile):
                self.set_machine_class(profile)
                active.unlink()
                result = self.run_command("/bin/bash", str(self.home / ".config/mise/bootstrap"), "finish")
                self.assertNotEqual(result.returncode, 0, "Missing active profile must fail finish")
                self.assertEqual(self.records(), [])
                self.assert_snapshots(restored=False)
                self.assertFalse((self.home / ".config/docker").exists())
                self.assertEqual(list((self.home / "Downloads").iterdir()), [])


    def assert_pipeline(self):
        rows = self.records()
        self.assertFalse(any(row["command"] == "brew" and "install" in row["args"] for row in rows))
        writes = [row["args"] for row in rows if row["command"] == "defaults" and "write" in row["args"]]
        self.assertEqual(len(writes), 79)
        identities = [(tuple(args[:args.index("write")]), *args[args.index("write") + 1:args.index("write") + 3])
                      for args in writes]
        self.assertEqual(len(set(identities)), 79, "Each domain/key/scope must be written once")
        applications = sum(args[args.index("write") + 1] in
                           ("org.m0k.transmission", "com.googlecode.iterm2.plist") for args in writes)
        self.assertEqual(applications, 12)
        for expected in (
            ["write", "NSGlobalDomain", "AppleLanguages", "-array", "en", "ru"],
            ["write", "com.apple.terminal", "StringEncodings", "-array", "4"],
            ["-currentHost", "write", "com.apple.ImageCapture", "disableHotPlug", "-bool", "true"],
            ["write", "com.apple.messageshelper.MessageController", "SOInputLineSettings", "-dict-add",
             "automaticEmojiSubstitutionEnablediMessage", "-bool", "false"],
            ["write", "kCFPreferencesAnyApplication", "TSMLanguageIndicatorEnabled", "-string", "0"],
            ["write", "com.apple.screencapture", "location", "-string", str(self.home / "Desktop")],
        ):
            self.assertIn(expected, writes)
        package = next(i for i, row in enumerate(rows) if row["command"] == "brew" and row["args"] == ["bundle"])
        defaults = [i for i, row in enumerate(rows) if row["command"] == "defaults" and "write" in row["args"]]
        self.assertLess(package, min(defaults))
        link = self.home / ".config/docker/cli-plugins/docker-buildx"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(self.prefix / "opt/docker-buildx/bin/docker-buildx"))

    def exercise_profile(self, profile):
        self.set_machine_class(profile)
        self.assert_success(self.bootstrap())
        self.assert_pipeline()
        self.assert_snapshots(restored=profile == "home")
        expected = {"ilya-birman-typolayout-3.9-mac.dmg"}
        if profile == "home":
            expected |= {"AmneziaVPN_1.2.3.dmg", "Yandex.Disk.dmg"}
        self.assertEqual({path.name for path in (self.home / "Downloads").iterdir()}, expected)
        if profile == "work":
            self.assertFalse(any("amnezia" in " ".join(row["args"]).lower() or
                                 "yandex" in " ".join(row["args"]).lower()
                                 for row in self.records() if row["command"] == "curl"))
        self.clear_records()
        self.assert_success(self.bootstrap())
        self.assert_pipeline()
        self.assert_snapshots(restored=profile == "home")
        self.assertFalse(any(row["command"] == "curl" and "-fL" in row["args"] for row in self.records()))
        self.assertEqual({path.name for path in (self.home / "Downloads").iterdir()}, expected)

    def test_work_pipeline(self):
        self.exercise_profile("work")

    def test_home_pipeline(self):
        self.exercise_profile("home")

    def test_project_bootstrap_does_not_inherit_workstation(self):
        captured = self.base / "project-env.json"
        probe = self.other / "project-env.py"
        probe.write_text(
            "import json, os\nfrom pathlib import Path\n"
            f"Path({str(captured)!r}).write_text(json.dumps(dict(os.environ)))\n"
            "print('project-bootstrap-only')\n")
        command = f"{json.dumps(sys.executable)} {json.dumps(str(probe))}"
        (self.other / "mise.toml").write_text(
            f'[tasks.bootstrap]\nrun = {json.dumps(command)}\n')
        self.assert_success(result := self.run_command(MISE, "bootstrap", "--yes"))
        self.assertIn("project-bootstrap-only", result.stdout)
        received = json.loads(captured.read_text())
        self.assertFalse(any(key.startswith("XDG_") for key in received))
        self.assertTrue({"CARGO_HOME", "RUSTUP_HOME", "GOPATH", "DOCKER_CONFIG"}.isdisjoint(received))
        self.assertEqual(self.records(), [], "Even global defaults reads must be opt-in")
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])
        self.assertFalse((self.home / ".config/docker").exists())

    def test_explicit_workstation_pipeline(self):
        self.assert_success(self.run_mise("-E", "workstation", "bootstrap", "--yes"))
        self.assert_pipeline()

    def test_native_tools_install_receives_workstation_environment(self):
        expected = {
            "XDG_CONFIG_HOME": self.home / ".config",
            "XDG_DATA_HOME": self.home / ".local/share",
            "XDG_STATE_HOME": self.home / ".local/state",
            "XDG_CACHE_HOME": self.home / "Library/Caches",
            "XDG_RUNTIME_DIR": self.home / ".tmp",
            "CARGO_HOME": self.home / ".local/share/cargo",
            "RUSTUP_HOME": self.home / ".local/share/rustup",
            "GOPATH": self.home / ".local/share/go",
            "DOCKER_CONFIG": self.home / ".config/docker",
        }
        self.assertTrue(set(expected).isdisjoint(self.env))
        fixture, replacements = re.subn(
            r"(?ms)^\[tools\]\n.*?(?=^\[settings\])",
            '[tools]\n"asdf:bootstrap-probe" = "1.0.0"\n\n',
            self.production_config, count=1,
        )
        self.assertEqual(replacements, 1, "Cannot isolate production runtime requests")
        self.config.write_text(fixture)
        plugin = Path(self.env["MISE_DATA_DIR"]) / "plugins/asdf-bootstrap-probe/bin"
        plugin.mkdir(parents=True)
        install_log = self.base / "native-install.json"
        scripts = {
            "list-all": "#!/bin/sh\nprintf '1.0.0\\n'\n",
            "install": f"#!{sys.executable}\n" +
                "import json, os\nfrom pathlib import Path\n" +
                f"Path({str(install_log)!r}).write_text(json.dumps(dict(os.environ)))\n" +
                'binary = Path(os.environ["ASDF_INSTALL_PATH"]) / "bin/bootstrap-probe"\n' +
                'binary.parent.mkdir(parents=True, exist_ok=True)\n' +
                'binary.write_text("#!/bin/sh\\nprintf \'native-probe-ran\\\\n\'\\n")\n' +
                'binary.chmod(0o755)\n',
        }
        for name, content in scripts.items():
            script = plugin / name
            script.write_text(content)
            script.chmod(0o755)
        installed = Path(self.env["MISE_DATA_DIR"]) / "installs/asdf-bootstrap-probe"
        self.assertFalse(installed.exists())
        (self.home / ".config").chmod(0o755)
        self.set_machine_class("unknown")
        self.assert_class_failure(self.bootstrap("--only", "tools"))
        self.assertFalse(install_log.exists(), "Invalid class reached the installer")
        self.assertFalse(installed.exists(), "Invalid class installed a tool")
        self.set_machine_class("work")
        self.assert_success(self.bootstrap("--only", "tools"))
        received = json.loads(install_log.read_text())
        for key, path in expected.items():
            self.assertEqual(received[key], str(path), key)
        paths = received["PATH"].split(os.pathsep)
        for path in (self.local_bin, self.bin, self.prefix / "sbin"):
            self.assertIn(str(path), paths)
        self.assertTrue(any(".fake-asdf" in path for path in paths),
                        "Workstation PATH must preserve mise's installer environment")
        self.assert_success(result := self.run_mise(
            "-E", "workstation", "exec", "--", "bootstrap-probe"))
        self.assertIn("native-probe-ran", result.stdout)
        self.assertEqual(self.records(), [])
        self.assertFalse((self.home / ".config/docker").exists())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])

    def test_missing_workstation_env_source_fails_before_mutations(self):
        for relative in (".xdg.dirs", ".config/shell/xdg"):
            with self.subTest(source=relative):
                source = self.home / relative
                source.unlink()
                try:
                    result = self.bootstrap("--only", "tools")
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(relative, result.stdout)
                    self.assertEqual(self.records(), [])
                    self.assertEqual(list((self.home / "Downloads").iterdir()), [])
                    self.assertFalse((self.home / ".config/docker").exists())
                finally:
                    shutil.copy2(ROOT / relative, source)

    def assert_class_failure(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("local.class", result.stdout)
        self.assertEqual(self.records(), [], "Class validation must not invoke external mutations")
        self.assertEqual((self.home / ".config").stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.home / ".config/docker").exists())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])

    def test_invalid_class_stops_native_entry_before_mutations(self):
        (self.home / ".config").chmod(0o755)
        for state in ("", "unknown", "missing-file", "missing-key", "malformed", "unreadable"):
            with self.subTest(state=state):
                if state == "unreadable" and os.geteuid() == 0:
                    continue  # root bypasses file read permissions
                self.set_class_failure(state)
                self.clear_records()
                result = self.bootstrap()
                self.assert_class_failure(result)
                self.assertIn("Invalid" if state in ("", "unknown") else "Cannot read", result.stdout)

    def test_missing_yadm_storage_is_not_created(self):
        (self.home / ".config").chmod(0o755)
        self.class_config.unlink()
        self.class_config.parent.rmdir()
        self.class_config.parent.parent.rmdir()
        yadm_config = self.home / ".config/yadm"
        self.assert_class_failure(self.run_command(
            "/bin/bash", str(self.home / ".config/mise/bootstrap"), "preflight"))
        self.assertFalse(self.class_config.parent.parent.exists())
        self.assertFalse(yadm_config.exists())

    def test_class_lookup_ignores_ambient_git_config_and_includes(self):
        unrelated = self.other / "unrelated.git"
        unrelated.mkdir()
        (unrelated / "config").write_text("[local]\nclass = unknown\n")
        included = self.base / "included.gitconfig"
        included.write_text("[local]\nclass = unknown\n")
        self.class_config.write_text(self.class_config.read_text() +
                                     f'[include]\npath = {json.dumps(str(included))}\n')
        self.env.update({
            "GIT_DIR": str(unrelated), "GIT_WORK_TREE": str(self.other),
            "GIT_CONFIG_GLOBAL": str(included), "GIT_CONFIG_SYSTEM": str(included),
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "local.class",
            "GIT_CONFIG_VALUE_0": "unknown",
        })
        self.assert_success(self.run_command(
            "/bin/bash", str(self.home / ".config/mise/bootstrap"), "preflight"))
        self.assertEqual(self.records(), [])
        # Ambient values must not supply a missing machine-local class either.
        self.class_config.write_text(f'[include]\npath = {json.dumps(str(included))}\n')
        (self.home / ".config").chmod(0o755)
        self.assert_class_failure(self.run_command(
            "/bin/bash", str(self.home / ".config/mise/bootstrap"), "preflight"))

    def test_invalid_class_stops_direct_phases_and_native_only_paths(self):
        (self.home / ".config").chmod(0o755)
        helper = str(self.home / ".config/mise/bootstrap")
        commands = [("/bin/bash", helper, phase)
                    for phase in ("preflight", "packages", "defaults", "finish")]
        commands += [(MISE, "-C", str(self.home), "-E", "workstation", "bootstrap",
                      "--only", phase, "--yes") for phase in ("macos-defaults", "tools")]
        for state in ("", "unknown", "missing-file", "missing-key", "malformed", "unreadable"):
            if state == "unreadable" and os.geteuid() == 0:
                continue  # root bypasses file read permissions
            self.set_class_failure(state)
            for command in commands:
                with self.subTest(state=state, command=command):
                    self.clear_records()
                    result = self.run_command(*command)
                    self.assert_class_failure(result)
                    self.assertIn("Invalid" if state in ("", "unknown") else "Cannot read", result.stdout)

    def test_interrupted_app_download_is_cleaned_and_retry_is_complete(self):
        self.env["FAIL_APP_DOWNLOAD"] = "1"
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        downloads = self.home / "Downloads"
        self.assertEqual(list(downloads.iterdir()), [])
        self.assertTrue(any(row["command"] == "curl" and "-fL" in row["args"]
                            for row in self.records()))
        self.env.pop("FAIL_APP_DOWNLOAD")
        self.clear_records()
        self.assert_success(self.bootstrap())
        destination = downloads / "ilya-birman-typolayout-3.9-mac.dmg"
        self.assertEqual(list(downloads.iterdir()), [destination])
        self.assertEqual(destination.read_bytes(), b"complete application download")
        self.assertTrue(any(row["command"] == "curl" and "-fL" in row["args"]
                            for row in self.records()))
        self.clear_records()
        self.assert_success(self.bootstrap())
        self.assertFalse(any(row["command"] == "curl" for row in self.records()))
        self.assertEqual(destination.read_bytes(), b"complete application download")
        self.assertEqual(list(downloads.iterdir()), [destination])

    def test_invalid_release_response_stops_before_release_download(self):
        self.set_machine_class("home")
        for payload in ("not json", "{}", '{"tag_name": null}', '{"tag_name": 12}',
                        '{"tag_name": ""}'):
            with self.subTest(payload=payload):
                self.env["RELEASE_JSON"] = payload
                self.clear_records()
                result = self.run_command("/bin/bash", str(self.home / ".config/mise/bootstrap"), "finish")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue(any(row["command"] == "jq" for row in self.records()))
                self.assertFalse(any("/releases/download/" in arg or "disk.yandex.ru" in arg
                                     for row in self.records() for arg in row["args"]))
                self.assertEqual({path.name for path in (self.home / "Downloads").iterdir()},
                                 {"ilya-birman-typolayout-3.9-mac.dmg"})

    def test_preview_has_no_external_mutations(self):
        # Runtimes remain omitted to keep this test offline; production tools
        # are covered by the separate native dry-run during migration.
        self.assert_success(self.bootstrap("--dry-run"))
        self.assertTrue(all(row["command"] == "defaults" and
                            row["args"][0] in ("read", "read-type")
                            for row in self.records()))
        self.assertFalse((self.home / ".config/docker/cli-plugins/docker-buildx").is_symlink())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])

    @unittest.skipUnless(YADM, "Requires installed yadm")
    def test_real_yadm_selects_native_snapshot_profiles(self):
        self.class_config.unlink()
        self.class_config.parent.rmdir()
        (self.bin / "yadm").unlink()
        (self.bin / "yadm").symlink_to(YADM)
        self.env.update({"GIT_DIR": str(self.class_config.parent),
                         "GIT_CONFIG_SYSTEM": os.devnull})
        active = self.config.parent / "config.app-preferences.toml"
        active.unlink()
        self.assert_success(self.run_command(YADM, "init"))
        self.assert_success(self.run_command(YADM, "config", "local.class", "work"))
        variants = [self.config.parent / f"config.app-preferences.toml##class.{profile}"
                    for profile in ("home", "work")]
        self.assert_success(self.run_command(YADM, "add", *(str(path) for path in variants)))
        self.assertTrue(active.is_symlink())
        self.assertEqual(active.resolve(), variants[1])
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        self.assert_snapshots(restored=False)
        self.assert_success(self.run_command(YADM, "config", "local.class", "home"))
        self.assert_success(self.run_command(YADM, "alt"))
        self.assertTrue(active.is_symlink())
        self.assertEqual(active.resolve(), variants[0])
        self.assert_snapshot_success(self.snapshot_command("apply", "--yes"))
        self.assert_snapshots(restored=True)
        self.assert_success(self.run_command(YADM, "config", "local.class", "work"))
        self.assert_success(self.run_command(YADM, "alt"))
        self.assertTrue(active.is_symlink())
        self.assertEqual(active.resolve(), variants[1])
        next(iter(self.snapshots)).write_bytes(b"not captured by work profile")
        before = self.snapshot_state()
        self.assert_snapshot_success(self.snapshot_command("add", "--changed", "--no-apply"))
        self.assertTrue(self.snapshot_state() == before, "Work captured home preferences")

    @unittest.skipUnless(YADM, "Requires installed yadm")
    def test_real_yadm_preview_and_preflight_preserve_files_and_permissions(self):
        # Real yadm setup is confined to the fixture HOME/XDG paths. The fixture
        # preference interception probe still guards every real mise invocation.
        self.class_config.unlink()
        self.class_config.parent.rmdir()
        (self.bin / "yadm").unlink()
        (self.bin / "yadm").symlink_to(YADM)
        self.env.update({
            "GIT_DIR": str(self.class_config.parent),
            "GIT_CONFIG_SYSTEM": os.devnull,
        })
        for args in (("init",), ("config", "local.class", "work")):
            self.assert_success(self.run_command(YADM, *args))
        self.assertTrue((self.class_config.parent / "HEAD").is_file(),
                        "Real yadm setup must create a Git repository")
        alternate = self.home / ".config/class-probe##class.work"
        alternate.write_text("work alternate\n")
        self.assert_success(self.run_command(YADM, "add", str(alternate)))
        generated = self.home / ".config/class-probe"
        self.assertTrue(generated.is_symlink(), "Setup must exercise real yadm auto-alt")
        generated.unlink()

        private_dir = self.home / ".ssh"
        private_dir.mkdir(exist_ok=True)
        sentinel = private_dir / "permission-sentinel"
        sentinel.write_text("not a real key\n")
        sentinel.chmod(0o644)
        private_dir.chmod(0o755)
        (self.home / ".config").chmod(0o755)
        modes = {path: path.stat().st_mode for path in (private_dir, sentinel, self.home / ".config")}
        hooks = self.home / ".config/yadm/hooks"
        hooks.mkdir(parents=True)
        hook = hooks / "pre_config"
        hook.write_text('#!/bin/sh\n: > "$HOME/yadm-hook-executed"\n')
        hook.chmod(0o755)

        commands = [
            ("preflight", ("/bin/bash", str(self.home / ".config/mise/bootstrap"), "preflight")),
            ("--dry-run", (MISE, "-C", str(self.home), "-E", "workstation", "bootstrap", "--dry-run")),
            ("--help", (MISE, "-C", str(self.home), "-E", "workstation", "bootstrap", "--help")),
        ]
        for option, command in commands:
            with self.subTest(option=option):
                self.clear_records()
                result = self.run_command(*command,
                                          env={**self.env, "MISE_CEILING_PATHS": str(self.home)})
                self.assert_success(result)
                self.assertFalse(os.path.lexists(generated), result.stdout)
                self.assertEqual({path: path.stat().st_mode for path in modes}, modes)
                self.assertFalse((self.home / "yadm-hook-executed").exists())
                self.assertEqual(sentinel.read_text(), "not a real key\n")
                self.assertEqual(alternate.read_text(), "work alternate\n")
                self.assertTrue(self.local_mise.exists())
                self.assertTrue(all(row["command"] == "defaults" and
                                    row["args"][0] in ("read", "read-type")
                                    for row in self.records()), self.records())
                self.assertEqual(list((self.home / "Downloads").iterdir()), [])
                self.assertFalse((self.home / ".config/docker").exists())

    def test_bash_startup_prefers_local_mise(self):
        shell_config = self.home / ".config/shell/config"
        shell_config.write_text('command -v mise\n')
        self.env["PATH"] = f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin"
        self.assert_success(result := self.run_command(
            "/bin/bash", "--noprofile", "--norc", "-c", 'source "$1"', "bash", str(ROOT / ".bashrc")))
        self.assertEqual(result.stdout.strip(), str(self.local_mise))

    def test_package_failure_stops_pipeline(self):
        self.env["FAIL_BUNDLE"] = "23"
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        rows = self.records()
        self.assertTrue(any(row["command"] == "brew" and row["args"] == ["bundle"] for row in rows))
        self.assertFalse(any(row["command"] in ("defaults", "osascript", "curl") for row in rows))
        self.assertFalse((self.home / ".config/docker/cli-plugins/docker-buildx").is_symlink())

    def test_maintenance_runs_exact_operations_from_home(self):
        self.local_mise.unlink()
        self.make_stub("mise", self.local_bin)
        tasks = {
            "update:mise": [("mise", ["self-update", "--no-plugins"])],
            "update:tools": [("mise", ["upgrade"])],
            "update:brew": [("brew", ["update"]), ("brew", ["upgrade"]), ("brew", ["cleanup"])],
            "update:zsh": [("zsh", [str(self.home / "Library/Caches/repos/mattmc3/antidote/antidote"), "update"])],
            "update:nvim": [("nvim", ["--headless", "+Lazy! sync", "+qa"])],
            "update:macos": [("sudo", ["softwareupdate", "-i", "-a"])],
        }
        for task, expected in tasks.items():
            with self.subTest(task=task):
                self.clear_records()
                # No -C: task.dir must work when launched from another directory.
                self.assert_success(self.run_command(MISE, "run", "--skip-tools", task))
                self.assertEqual([(row["command"], row["args"]) for row in self.records()], expected)
                self.assertTrue(all(Path(row["cwd"]).resolve() == self.home for row in self.records()))
                for row in self.records():
                    self.assertTrue({"CARGO_HOME", "RUSTUP_HOME", "GOPATH", "DOCKER_CONFIG"}
                                    .isdisjoint(row["env"]))
                    if task != "update:zsh":  # This task explicitly sources .xdg.dirs itself.
                        self.assertEqual(row["env"], {})


if __name__ == "__main__":
    unittest.main()
