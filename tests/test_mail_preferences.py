#!/usr/bin/env python3
"""Check managed Mail preferences against the archived snapshot without live domains."""

import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / ".config/app-preferences/archive/Library/Preferences/com.apple.mail.plist"
DEFAULTS = Path("/usr/bin/defaults")


@unittest.skipUnless(sys.platform == "darwin" and DEFAULTS.is_file(), "Requires macOS defaults")
class MailPreferencesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mail preferences tests ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "isolated home"
        self.home.mkdir()
        # An absolute domain is essential: changing HOME alone does not isolate cfprefsd.
        self.domain = self.base / "isolated-mail"
        self.env = {
            "HOME": str(self.home), "USER": os.environ.get("USER", "test"),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        }

    def run_defaults(self, operation, *args):
        result = subprocess.run(
            [str(DEFAULTS), operation, str(self.domain), *args],
            env=self.env, cwd=self.home, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result.stdout

    def test_managed_values_and_types_match_archive_preserving_unmanaged_preferences(self):
        golden = plistlib.loads(GOLDEN.read_bytes())
        config = tomllib.loads((ROOT / ".config/mise/config.workstation.toml").read_text())
        scalars = config["bootstrap"]["macos"]["defaults"]["com.apple.mail"]
        self.assertEqual(set(scalars), set(golden) - {"NSUserKeyEquivalents"})
        for key, value in scalars.items():
            with self.subTest(key=key):
                self.assertIs(type(value), type(golden[key]))
                self.assertEqual(value, golden[key])

        # Extract only production Mail writes, never execute other application's defaults.
        commands = []
        for line in (ROOT / ".config/macos/defaults-extra").read_text().splitlines():
            args = shlex.split(line, comments=True)
            if args[:3] == ["defaults", "write", "com.apple.mail"]:
                commands.append(args[3:])
        self.assertTrue(commands, "Missing production Mail dictionary writes")

        self.run_defaults("write", "UnmanagedPreference", "-string", "keep me")
        self.run_defaults("write", "NSUserKeyEquivalents", "-dict-add", "UnmanagedShortcut", "-string", "@~u")
        self.run_defaults("write", "NSUserKeyEquivalents", "-dict-add", "Send", "-string", "old shortcut")

        # Reapply to prove managed values converge without replacing unrelated preferences.
        for _ in range(2):
            for key, value in scalars.items():
                if type(value) is bool:
                    self.run_defaults("write", key, "-bool", str(value).lower())
                else:
                    self.assertIs(type(value), str)
                    self.run_defaults("write", key, "-string", value)
            for args in commands:
                self.run_defaults("write", *args)

            actual = plistlib.loads(self.run_defaults("export", "-"))
            expected = dict(golden)
            expected["UnmanagedPreference"] = "keep me"
            expected["NSUserKeyEquivalents"] = {
                **golden["NSUserKeyEquivalents"], "UnmanagedShortcut": "@~u",
            }
            self.assertEqual(actual, expected)
            for key, value in golden.items():
                with self.subTest(key=key):
                    self.assertIs(type(actual[key]), type(value))
            for key, value in golden["NSUserKeyEquivalents"].items():
                with self.subTest(shortcut=key):
                    self.assertIs(type(actual["NSUserKeyEquivalents"][key]), type(value))


if __name__ == "__main__":
    unittest.main()
