#!/usr/bin/env python3
"""Check explicit maintenance isolation with real mise and a local asdf plugin."""

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
RECORDER = r'''
import json
import os
from pathlib import Path
import sys

with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps({"command": Path(sys.argv[0]).name,
                          "args": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
'''
INSTALLER = r'''#!/bin/sh
set -eu
printf '%s\n' "$ASDF_INSTALL_VERSION" >> "$INSTALL_MARKER"
mkdir -p "$ASDF_INSTALL_PATH/bin"
cat > "$ASDF_INSTALL_PATH/bin/maintenance-probe" <<'SCRIPT'
#!/bin/sh
set -eu
printf 'probe-ran\n' > "$PROJECT_MARKER"
SCRIPT
chmod +x "$ASDF_INSTALL_PATH/bin/maintenance-probe"
'''


@unittest.skipUnless(sys.platform == "darwin" and MISE, "Requires macOS and installed mise")
class MiseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mise maintenance tests ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "isolated home"
        self.home.mkdir()
        self.project = self.base / "ordinary project"
        self.project.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.log = self.base / "commands.jsonl"
        self.install_marker = self.base / "installed"
        self.project_marker = self.base / "project-ran"
        self.config = self.home / ".config/mise/config.toml"
        self.config.parent.mkdir(parents=True)
        self.env = {
            "HOME": str(self.home), "USER": os.environ.get("USER", "test"),
            "PATH": f"{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
            "TERM": "dumb", "NO_COLOR": "1", "CI": "1", "MISE_YES": "1",
            "COMMAND_LOG": str(self.log), "INSTALL_MARKER": str(self.install_marker),
            "PROJECT_MARKER": str(self.project_marker),
            "MISE_CONFIG_DIR": str(self.config.parent),
            "MISE_SYSTEM_CONFIG_DIR": str(self.base / "system-mise"),
            "MISE_DATA_DIR": str(self.home / ".local/share/mise"),
            "MISE_STATE_DIR": str(self.home / ".local/state/mise"),
            "MISE_CACHE_DIR": str(self.home / "Library/Caches/mise"),
            "MISE_CEILING_PATHS": str(self.base),
            "MISE_TRUSTED_CONFIG_PATHS": str(self.base),
            # Unlike the bootstrap fixture, both auto-install switches stay enabled.
            "MISE_TASK_RUN_AUTO_INSTALL": "true", "MISE_AUTO_INSTALL": "true",
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

        # Preserve the six production tasks verbatim. Replace only runtime requests
        # with a missing, entirely local tool: no real backend can download anything.
        production = (ROOT / ".config/mise/config.toml").read_text()
        fixture, replacements = re.subn(
            r"(?ms)^\[tools\]\n.*?(?=^\[settings\])",
            '[tools]\n"asdf:maintenance-probe" = "1.0.0"\n\n',
            production, count=1,
        )
        self.assertEqual(replacements, 1, "Cannot isolate production runtime requests")
        self.config.write_text(fixture)
        shutil.copy2(ROOT / ".xdg.dirs", self.home / ".xdg.dirs")

        # mise's asdf backend considers an existing plugin directory installed.
        # Its list-all and install scripts need neither a remote repo nor downloads.
        plugin = Path(self.env["MISE_DATA_DIR"]) / "plugins/asdf-maintenance-probe/bin"
        plugin.mkdir(parents=True)
        self.write_executable(plugin / "list-all", "#!/bin/sh\nprintf '1.0.0\\n'\n")
        self.write_executable(plugin / "install", INSTALLER)
        self.project.joinpath("mise.toml").write_text(
            '[tasks.ordinary]\nrun = "maintenance-probe"\n'
        )

        # The real runner performs installation decisions, but maintenance effects
        # (including its explicit mise upgrade/self-update commands) are recorded.
        for command in ("brew", "zsh", "nvim", "sudo"):
            self.write_executable(self.bin / command, f"#!{sys.executable}\n" + RECORDER)
        local_bin = self.home / ".local/bin"
        local_bin.mkdir(parents=True)
        self.write_executable(local_bin / "mise", f"#!{sys.executable}\n" + RECORDER)

    def write_executable(self, path, content):
        path.write_text(content)
        path.chmod(0o755)

    def run_mise(self, directory, *args):
        result = subprocess.run(
            [MISE, "-C", str(directory), *args], cwd=self.project, env=self.env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def test_explicit_maintenance_skips_install_without_disabling_project_install(self):
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
                self.log.write_text("")
                self.run_mise(self.home, "run", "--skip-tools", task)
                self.assertFalse(self.install_marker.exists(), f"{task} implicitly installed a tool")
                rows = [json.loads(line) for line in self.log.read_text().splitlines()]
                self.assertEqual([(row["command"], row["args"]) for row in rows], expected)
                self.assertTrue(all(Path(row["cwd"]).resolve() == self.home for row in rows))

        # Same isolated configuration and enabled auto-install settings, no flag:
        # a normal project task must install the missing tool and execute its binary.
        self.run_mise(self.project, "run", "ordinary")
        self.assertEqual(self.install_marker.read_text().splitlines(), ["1.0.0"])
        self.assertEqual(self.project_marker.read_text(), "probe-ran\n")


if __name__ == "__main__":
    unittest.main()
