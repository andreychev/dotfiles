#!/usr/bin/env python3
"""Native scalar application preserves unmanaged private preference fields."""

import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
MISE = shutil.which("mise")
DEFAULTS = Path("/usr/bin/defaults")
# Explicit golden copied from reviewed legacy settings, not live preference data.
EXPECTED = {'net.freemacsoft.AppCleaner': {'SUEnableAutomaticChecks': True,
                                'SUAutomaticallyUpdate': True,
                                'SUSendProfileInfo': False},
 'com.surteesstudios.Bartender': {'UseBartenderBar': False,
                                  'ClickingMenuBarTogglesBartender': True,
                                  'MouseOverMenuBarTogglesBartender': True,
                                  'HideItemsWhenShowingOthers': False,
                                  'HideSecondaryMenuBarItems': False,
                                  'ShowAllItemsWhenDragging': True,
                                  'SUEnableAutomaticChecks': True,
                                  'SUAutomaticallyUpdate': False,
                                  'SUSendProfileInfo': False},
 'pl.maketheweb.cleanshotx': {'popupSize': 2,
                              'analyticsAllowed': False,
                              'annotateTextStyle': 0,
                              'annotatePixelateIntensity': 10,
                              'popupAskForDestinationWhenSaving': False,
                              'confirmVideoDelete': False,
                              'captureWithoutDesktopIcons': True,
                              'deletePopupAfterDragging': True,
                              'doNotDisturbWhileRecording': False,
                              'SUEnableAutomaticChecks': False,
                              'SUAutomaticallyUpdate': False},
 'com.marcoarment.quitter': {'active': False,
                             'SUEnableAutomaticChecks': True,
                             'SUAutomaticallyUpdate': True,
                             'SUSendProfileInfo': False},
 'org.videolan.vlc': {'language': 'auto',
                      'SUEnableAutomaticChecks': False,
                      'SUAutomaticallyUpdate': True,
                      'SUSendProfileInfo': False},
 'us.zoom.xos': {'kZMShowNotificationCenter': True,
                 'WebContinuousSpellCheckingEnabled': True,
                 'ZMInputTextViewAutomaticSpellingCorrectionEnabled': False,
                 'ZMInputTextViewContinuousSpellCheckingEnabled': False,
                 'ZMInputTextViewGrammarCheckingEnabled': False,
                 'NSAllowContinuousSpellChecking': True}}


@unittest.skipUnless(sys.platform == "darwin" and MISE, "Requires macOS and mise")
class AppDefaultsTests(unittest.TestCase):
    def test_native_scalars_preserve_private_fields_and_types(self):
        profile = ROOT / ".config/mise/config.app-preferences.toml##class.home"
        settings = tomllib.loads(profile.read_text())["bootstrap"]["macos"]["defaults"]
        self.assertEqual(settings, EXPECTED)
        with tempfile.TemporaryDirectory(prefix="portable app defaults ") as directory:
            root = Path(directory).resolve()
            home = root / "home"
            home.mkdir()
            config = home / ".config/mise/config.toml"
            config.parent.mkdir(parents=True)
            env = {
                "HOME": str(home), "USER": os.environ.get("USER", "test"),
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "NO_COLOR": "1", "CI": "1",
                "MISE_CONFIG_DIR": str(config.parent), "MISE_GLOBAL_CONFIG_FILE": str(config),
                "MISE_SYSTEM_CONFIG_DIR": str(root / "system"),
                "MISE_DATA_DIR": str(root / "data"), "MISE_STATE_DIR": str(root / "state"),
                "MISE_CACHE_DIR": str(root / "cache"), "MISE_CEILING_PATHS": str(home),
                "MISE_TRUSTED_CONFIG_PATHS": str(root), "MISE_YES": "1",
            }

            def command(*args):
                result = subprocess.run(args, cwd=home, env=env, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, "Isolated preference command failed")
                return result.stdout

            lines = []
            for domain, values in settings.items():
                # Absolute temporary domains, never real application domains:
                # changing HOME alone does not isolate cfprefsd.
                target = root / domain
                lines.append("[bootstrap.macos.defaults." + json.dumps(str(target)) + "]")
                lines.extend(key + " = " + json.dumps(value) for key, value in values.items())
                command(str(DEFAULTS), "write", str(target), "license6", "-string", "test-license")
                command(str(DEFAULTS), "write", str(target), "accountToken", "-string", "test-account")
                command(str(DEFAULTS), "write", str(target), "recentlyPlayedMediaList", "-array", "test-media")
            config.write_text("\n".join(lines) + "\n")
            for _ in range(2):
                command(MISE, "-C", str(home), "--no-env", "--no-hooks", "bootstrap", "macos", "defaults", "apply", "--yes")
                for domain, values in settings.items():
                    actual = plistlib.loads(command(str(DEFAULTS), "export", str(root / domain), "-"))
                    self.assertEqual(actual, {**values, "license6": "test-license",
                                             "accountToken": "test-account",
                                             "recentlyPlayedMediaList": ["test-media"]})
                    for key, value in values.items():
                        self.assertIs(type(actual[key]), type(value))


if __name__ == "__main__":
    unittest.main()
