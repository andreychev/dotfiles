#!/usr/bin/env python3
"""Exercise shell initialization with isolated homes and recording tool stubs."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
ZSH = shutil.which("zsh")
SOURCES = (".bashrc", ".xdg.dirs", ".config/shell/xdg", ".config/zsh/environment.zsh")
REPORT = r'''
source "$XDG_CONFIG_HOME/shell/xdg"
printf 'history=%s\npath=%s\nactivated=%s\nconfig_path=%s\nyadm=%s\n' \
    "$HISTFILE" "$PATH" "${MISE_ACTIVATED:-}" "${CONFIG_PATH:-}" "${CONFIG_YADM:-}"
/bin/sh -c 'printf "exported_history=%s\n" "$HISTFILE"'
'''


@unittest.skipUnless(BASH, "Requires Bash")
class ShellInitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="shell init tests ")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "isolated home"
        self.local_bin = self.home / ".local/bin"
        self.brew_bin = self.base / "homebrew prefix/bin"
        self.local_bin.mkdir(parents=True)
        self.brew_bin.mkdir(parents=True)
        self.log = self.base / "commands.log"
        self.state = self.home / ".local/state"
        self.env = {
            "HOME": str(self.home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOMEBREW_PREFIX": str(self.brew_bin.parent),
            "COMMAND_LOG": str(self.log), "TERM": "dumb",
        }
        for source in SOURCES:
            destination = self.home / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, destination)
        # Capture discovery at the real shared-config boundary without loading
        # unrelated aliases, runtime integrations, or plugin installers.
        (self.home / ".config/shell/config").write_text(
            'export CONFIG_PATH="$PATH"\n'
            'export CONFIG_YADM="$(command -v yadm || :)"\n'
            'source "$XDG_CONFIG_HOME/shell/xdg"\n'
        )
        self.make_stub(self.brew_bin / "brew", r'''
[ "$#" -eq 1 ] && [ "$1" = shellenv ] || exit 31
printf 'brew shellenv\n' >> "$COMMAND_LOG"
printf 'export PATH="$HOMEBREW_PREFIX/bin:$PATH"\n'
''')
        self.make_stub(self.brew_bin / "yadm", "exit 0\n")
        self.make_stub(self.brew_bin / "mise", r'''
printf 'forbidden brew mise\n' >> "$COMMAND_LOG"
exit 32
''')
        self.make_stub(self.local_bin / "mise", r'''
[ "$#" -eq 2 ] && [ "$1" = activate ] && [ "$2" = bash ] || exit 33
printf 'mise activate bash\n' >> "$COMMAND_LOG"
printf 'export MISE_ACTIVATED=official\n'
''')

    def make_stub(self, path, body):
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)

    def records(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def run_shell(self, shell, script, interactive=False):
        args = ([shell, "--noprofile", "--norc"] if shell == BASH else [shell, "-f"])
        args += ["-ic" if interactive else "-c", script]
        result = subprocess.run(args, cwd=self.home, env=self.env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def bash(self, interactive=False, ostype="darwin-test"):
        return self.run_shell(BASH, f'OSTYPE={ostype}; source "$HOME/.bashrc"\n' + REPORT,
                              interactive=interactive)

    def assert_history(self, result, shell):
        expected = str(self.state / shell / "history")
        self.assertEqual(result["history"], expected)
        self.assertEqual(result["exported_history"], expected)

    def test_interactive_bash_initializes_brew_before_config_and_activates_local_mise(self):
        result = self.bash(interactive=True)
        self.assertEqual(self.records(), ["brew shellenv", "mise activate bash"])
        self.assertEqual(result["activated"], "official")
        self.assertEqual(result["yadm"], str(self.brew_bin / "yadm"))
        for key in ("path", "config_path"):
            self.assertEqual(result[key].split(os.pathsep)[:2],
                             [str(self.local_bin), str(self.brew_bin)])
        self.assert_history(result, "bash")
        self.assertTrue((self.state / "bash").is_dir())

    def test_noninteractive_bash_does_not_activate_or_create_history_directory(self):
        result = self.bash()
        self.assertEqual(self.records(), ["brew shellenv"])
        self.assertEqual(result["activated"], "")
        self.assert_history(result, "bash")
        self.assertFalse((self.state / "bash").exists())

    def test_missing_optional_binaries_allow_startup(self):
        (self.brew_bin / "brew").unlink()
        (self.local_bin / "mise").unlink()
        for interactive in (False, True):
            with self.subTest(interactive=interactive):
                result = self.bash(interactive=interactive)
                self.assertEqual(result["activated"], "")
                self.assert_history(result, "bash")
        self.assertEqual(self.records(), [])
        self.assertTrue((self.state / "bash").is_dir())

    def test_nonexecutable_local_mise_never_falls_back_to_brew_mise(self):
        (self.local_bin / "mise").chmod(0o644)
        result = self.bash(interactive=True)
        self.assertEqual(self.records(), ["brew shellenv"])
        self.assertEqual(result["activated"], "")
        self.assert_history(result, "bash")

    def test_non_macos_does_not_initialize_homebrew(self):
        result = self.bash(interactive=True, ostype="linux-gnu")
        self.assertEqual(self.records(), ["mise activate bash"])
        self.assertNotIn(str(self.brew_bin), result["config_path"].split(os.pathsep))
        self.assertEqual(result["path"].split(os.pathsep)[0], str(self.local_bin))

    @unittest.skipUnless(ZSH, "Requires Zsh")
    def test_zsh_history_is_separate_and_preserves_history_policies(self):
        bash = self.bash(interactive=True)
        zsh = self.run_shell(ZSH, r'''
source "$HOME/.xdg.dirs"
source "$XDG_CONFIG_HOME/shell/xdg"
source "$XDG_CONFIG_HOME/zsh/environment.zsh"
printf 'size=%s\nsave=%s\n' "$HISTSIZE" "$SAVEHIST"
for option in SHARE_HISTORY HIST_IGNORE_ALL_DUPS HIST_IGNORE_SPACE HIST_REDUCE_BLANKS; do
    [[ -o "$option" ]] || exit 34
done
''' + REPORT)
        self.assert_history(zsh, "zsh")
        self.assertNotEqual(bash["history"], zsh["history"])
        self.assertTrue((self.state / "zsh").is_dir())
        self.assertEqual((zsh["size"], zsh["save"]), ("10000", "10000"))
        self.assertEqual(self.records(), ["brew shellenv", "mise activate bash"])

    def test_shared_xdg_preserves_existing_history_file(self):
        for shell in filter(None, (BASH, ZSH)):
            with self.subTest(shell=shell):
                result = self.run_shell(shell, r'''
source "$HOME/.xdg.dirs"
export HISTFILE="$HOME/custom history"
''' + REPORT)
                self.assertEqual(result["history"], str(self.home / "custom history"))
                self.assertEqual(result["exported_history"], result["history"])
        self.assertEqual(self.records(), [])

    def check_shared_environment(self, shell):
        for source in (".config/shell/config", ".config/shell/environment"):
            shutil.copy2(ROOT / source, self.home / source)
        shell_config = self.home / ".config/shell"
        (shell_config / "aliases").write_text(
            'export ALIASES_DOCKER_CONFIG="$DOCKER_CONFIG"\n'
            'export ALIASES_GNUPGHOME="$GNUPGHOME"\n'
        )
        (shell_config / "aliases.work").write_text(
            'export CLASS_ALIASES_DOCKER_CONFIG="$DOCKER_CONFIG"\n'
            'export CLASS_ALIASES_GNUPGHOME="$GNUPGHOME"\n'
        )
        self.make_stub(self.local_bin / "yadm", r'''
printf 'forbidden yadm %s\n' "$*" >> "$COMMAND_LOG"
exit 35
''')
        self.make_stub(self.local_bin / "tty", "printf '/dev/tty-test\\n'\n")
        self.env["PATH"] = str(self.local_bin) + os.pathsep + self.env["PATH"]
        repo_config = self.home / ".local/share/yadm/repo.git/config"
        repo_config.parent.mkdir(parents=True)
        unrelated_git_dir = self.base / "unrelated.git"
        unrelated_git_dir.mkdir()
        (unrelated_git_dir / "config").write_text("[local]\nclass = home\n")
        self.env["GIT_DIR"] = str(unrelated_git_dir)
        override = shell_config / "environment.work"
        script = ('OSTYPE=darwin-test; source "$HOME/.bashrc"\n' if shell == BASH else
                  'source "$HOME/.config/shell/config"\n'
                  'source "$XDG_CONFIG_HOME/zsh/environment.zsh"\n')
        script += r'''
printf 'docker=%s\ngnupg=%s\nalias_docker=%s\nalias_gnupg=%s\n' \
    "$DOCKER_CONFIG" "$GNUPGHOME" "$ALIASES_DOCKER_CONFIG" "$ALIASES_GNUPGHOME"
printf 'class_alias_docker=%s\nclass_alias_gnupg=%s\n' \
    "${CLASS_ALIASES_DOCKER_CONFIG:-}" "${CLASS_ALIASES_GNUPGHOME:-}"
printf 'history=%s\neditor=%s\npython_encoding=%s\n' \
    "$HISTFILE" "$EDITOR" "$PYTHONIOENCODING"
/bin/sh -c 'printf "exported_history=%s\nexported_docker=%s\nexported_gnupg=%s\n" \
    "$HISTFILE" "$DOCKER_CONFIG" "$GNUPGHOME"'
'''
        for case in ("work_override", "work_defaults", "no_class"):
            with self.subTest(case=case):
                if case == "no_class":
                    repo_config.unlink()
                else:
                    repo_config.write_text("[local]\nclass = work\n")
                if case == "work_override":
                    override.write_text(
                        'export DOCKER_CONFIG="$HOME/work docker"\n'
                        'export GNUPGHOME="$HOME/work gnupg"\n'
                    )
                    docker = str(self.home / "work docker")
                    gnupg = str(self.home / "work gnupg")
                else:
                    if override.exists():
                        override.unlink()
                    docker = str(self.home / ".config/docker")
                    gnupg = str(self.home / ".local/share/gnupg")
                result = self.run_shell(shell, script)
                for key in ("docker", "alias_docker", "exported_docker"):
                    self.assertEqual(result[key], docker)
                for key in ("gnupg", "alias_gnupg", "exported_gnupg"):
                    self.assertEqual(result[key], gnupg)
                self.assertEqual(result["class_alias_docker"],
                                 "" if case == "no_class" else docker)
                self.assertEqual(result["class_alias_gnupg"],
                                 "" if case == "no_class" else gnupg)
                self.assert_history(result, "bash" if shell == BASH else "zsh")
                self.assertEqual(result["editor"], "nvim")
                self.assertEqual(result["python_encoding"], "UTF-8")
        self.assertEqual(self.records(), ["brew shellenv"] * 3 if shell == BASH else [])

    def test_bash_shared_config_preserves_class_overrides_and_defaults(self):
        self.check_shared_environment(BASH)

    @unittest.skipUnless(ZSH, "Requires Zsh")
    def test_zsh_shared_config_preserves_class_overrides_and_defaults(self):
        self.check_shared_environment(ZSH)


if __name__ == "__main__":
    unittest.main()
