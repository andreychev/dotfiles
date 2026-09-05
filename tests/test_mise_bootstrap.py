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
import unittest


ROOT = Path(__file__).resolve().parents[1]
MISE = shutil.which("mise")
SOURCES = (
    ".xdg.dirs", ".config/shell/xdg", ".config/yadm/bootstrap",
    ".config/mise/bootstrap", ".config/mise/config.toml",
    ".config/mise/conf.d/macos.toml", ".config/macos/defaults-extra",
    ".config/iterm2/defaults", ".config/transmission/defaults",
)
STUB = r'''
import json
import os
from pathlib import Path
import sys

name, args = Path(sys.argv[0]).name, sys.argv[1:]
record = json.dumps({"command": name, "args": args, "cwd": os.getcwd()}) + "\n"
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
    if args == ["install", "mise"]:
        Path(os.environ["HOMEBREW_PREFIX"], "bin", "mise").symlink_to(os.environ["REAL_MISE"])
    elif args == ["bundle"]:
        sys.exit(int(os.environ.get("FAIL_BUNDLE", "0")))
    elif args not in (["update"], ["upgrade"], ["cleanup"]):
        sys.exit("Unexpected brew operation")
elif name == "yadm":
    if args == ["config", "local.class"]:
        print(os.environ["MACHINE_CLASS"])
    elif args != ["sparse-checkout", "init"] and args[:3] != ["sparse-checkout", "set", "--no-cone"]:
        sys.exit("Unexpected yadm operation")
elif name == "curl":
    if args == ["-s", "https://api.github.com/repos/amnezia-vpn/amnezia-client/releases/latest"]:
        print('{"tag_name": "v1.2.3"}')
    elif len(args) == 5 and args[0] == "-fLo" and args[2:4] == ["--connect-timeout", "300"]:
        destination = Path(args[1]).resolve()
        if destination.parent != Path(os.environ["HOME"], "Downloads").resolve():
            sys.exit("Refusing download outside temporary Downloads")
        destination.touch()
    else:
        sys.exit("Unexpected curl operation")
elif name == "mise":
    if args != ["upgrade"]:
        sys.exit("Unexpected inner mise operation")
elif name == "sudo":
    if args != ["softwareupdate", "-i", "-a"]:
        sys.exit("Unexpected sudo operation")
elif name not in ("mackup", "osascript", "zsh", "nvim"):
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
        self.log = self.base / "commands.jsonl"
        self.config = self.home / ".config/mise/config.toml"
        self.config.parent.mkdir(parents=True)
        # Deliberately inherit no MISE/XDG configuration or executable search path.
        self.env = {
            "HOME": str(self.home), "USER": os.environ.get("USER", "test"),
            "PATH": f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOMEBREW_PREFIX": str(self.prefix), "REAL_MISE": str(Path(MISE).absolute()),
            "COMMAND_LOG": str(self.log), "MACHINE_CLASS": "work",
            "TERM": "dumb", "NO_COLOR": "1", "CI": "1", "MISE_YES": "1",
            "MISE_CONFIG_DIR": str(self.config.parent),
            "MISE_GLOBAL_CONFIG_FILE": str(self.config),
            "MISE_SYSTEM_CONFIG_DIR": str(self.base / "system-mise"),
            "MISE_DATA_DIR": str(self.home / ".local/share/mise"),
            "MISE_STATE_DIR": str(self.home / ".local/state/mise"),
            "MISE_CACHE_DIR": str(self.home / "Library/Caches/mise"),
            "MISE_CEILING_PATHS": str(self.base),
            "MISE_TRUSTED_CONFIG_PATHS": str(self.base),
            "MISE_TASK_RUN_AUTO_INSTALL": "false", "MISE_AUTO_INSTALL": "false",
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_CACHE_HOME": str(self.home / "Library/Caches"),
            "XDG_RUNTIME_DIR": str(self.home / ".tmp"),
            "XDG_CONFIG_DIRS": str(self.base / "system-config"),
            "XDG_DATA_DIRS": str(self.base / "system-data"),
            "TMPDIR": str(self.base / "tmp"),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        }
        for key, value in self.env.items():
            if key.startswith("XDG_") or key.endswith("_DIR") or key == "TMPDIR":
                Path(value).mkdir(parents=True, exist_ok=True)
        (self.home / "Downloads").mkdir()
        for name in ("defaults", "brew", "yadm", "mackup", "curl", "osascript", "zsh", "nvim", "sudo"):
            self.make_stub(name)
        (self.bin / "mise").symlink_to(MISE)

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
        self.production_config = self.config.read_text()
        # Only runtimes are omitted; all production hooks/tasks/preferences remain.
        self.config.write_text(re.sub(r"(?ms)^\[tools\]\n.*?(?=^\[settings\])", "",
                                      self.production_config, count=1))

    def make_stub(self, name):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n" + STUB)
        path.chmod(0o755)

    def records(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def clear_records(self):
        self.log.write_text("")

    def run_command(self, *args):
        return subprocess.run(args, cwd=self.other, env=self.env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)

    def run_mise(self, *args):
        return self.run_command(MISE, "-C", str(self.home), *args)

    def bootstrap(self, *args):
        return self.run_command("/bin/bash", str(self.home / ".config/yadm/bootstrap"), "--yes", *args)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout)

    def assert_pipeline(self):
        rows = self.records()
        writes = [row["args"] for row in rows if row["command"] == "defaults" and "write" in row["args"]]
        self.assertEqual(len(writes), 75)
        identities = [(tuple(args[:args.index("write")]), *args[args.index("write") + 1:args.index("write") + 3])
                      for args in writes]
        self.assertEqual(len(set(identities)), 75, "Each domain/key/scope must be written once")
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
        restore = next(i for i, row in enumerate(rows) if row["command"] == "mackup" and row["args"] == ["restore"])
        defaults = [i for i, row in enumerate(rows) if row["command"] == "defaults" and "write" in row["args"]]
        self.assertLess(package, min(defaults))
        self.assertLess(max(defaults), restore)
        link = self.home / ".config/docker/cli-plugins/docker-buildx"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(self.prefix / "opt/docker-buildx/bin/docker-buildx"))

    def exercise_profile(self, profile):
        self.env["MACHINE_CLASS"] = profile
        self.assert_success(self.bootstrap())
        self.assert_pipeline()
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
        self.assertFalse(any(row["command"] == "curl" and "-fLo" in row["args"] for row in self.records()))
        self.assertEqual({path.name for path in (self.home / "Downloads").iterdir()}, expected)

    def test_work_pipeline(self):
        self.exercise_profile("work")

    def test_home_pipeline(self):
        self.exercise_profile("home")

    def test_preview_has_no_external_mutations(self):
        # Runtimes remain omitted to keep this test offline; production tools
        # are covered by the separate native dry-run during migration.
        self.assert_success(self.bootstrap("--dry-run"))
        self.assertTrue(all(row["command"] == "defaults" and
                            row["args"][0] in ("read", "read-type")
                            for row in self.records()))
        self.assertFalse((self.home / ".config/docker/cli-plugins/docker-buildx").is_symlink())
        self.assertEqual(list((self.home / "Downloads").iterdir()), [])

    def test_preview_without_mise_never_installs(self):
        (self.bin / "mise").unlink()
        result = self.bootstrap("--dry-run")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("nothing was changed", result.stdout)
        self.assertEqual(self.records(), [])
        self.assertFalse((self.bin / "mise").exists())

    def test_cold_start_installs_mise_then_continues(self):
        (self.bin / "mise").unlink()
        self.assert_success(self.bootstrap())
        first = self.records()[0]
        self.assertEqual((first["command"], first["args"]), ("brew", ["install", "mise"]))
        self.assert_pipeline()

    def test_package_failure_stops_pipeline(self):
        self.env["FAIL_BUNDLE"] = "23"
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        rows = self.records()
        self.assertTrue(any(row["command"] == "brew" and row["args"] == ["bundle"] for row in rows))
        self.assertFalse(any(row["command"] in ("defaults", "osascript", "mackup", "curl") for row in rows))
        self.assertFalse((self.home / ".config/docker/cli-plugins/docker-buildx").is_symlink())

    def test_maintenance_runs_exact_operations_from_home(self):
        (self.bin / "mise").unlink()
        self.make_stub("mise")
        tasks = {
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
                self.assert_success(self.run_command(MISE, "run", task))
                self.assertEqual([(row["command"], row["args"]) for row in self.records()], expected)
                self.assertTrue(all(Path(row["cwd"]).resolve() == self.home for row in self.records()))


if __name__ == "__main__":
    unittest.main()
