#!/usr/bin/env python3
"""One-off, backup-first migration of an existing legacy yadm HOME.

The default is a read-only plan. Run from a separate, committed new checkout.
Only --apply writes; no workstation bootstrap, package removal, or tool upgrade
is performed. Close shells/applications that write managed data before applying.

Requires macOS, Python 3.9+, Git and yadm, standard XDG paths, a clean tracked
yadm worktree and one home/work class. The new commit must descend from the
legacy main baseline c454ecb and the existing yadm HEAD.
Backups: ~/.local/state/dotfiles-migration/migration-*/. On failure retain the
backup and its checkpoint manifest; there is no automatic rollback.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile


BASELINE = "c454ecbd62d84d3906dc0da17c56f242f792bbbe"
STORAGE = Path(".config/Mackup")
REPOSITORY = Path(".local/share/yadm/repo.git")
BACKUPS = Path(".local/state/dotfiles-migration")
HISTORY = Path(".local/state/zsh/history")
EXTRA_PREFERENCES = Path("Library/Preferences/us.zoom.xos.Hotkey.plist")


class MigrationError(Exception):
    """An actionable, deliberately content-free failure."""


def inside(path, root):
    return path == root or root in path.parents


def present(path):
    return path.exists() or path.is_symlink()


def run(args, *, cwd, env, ok=(0,), timeout=60):
    try:
        result = subprocess.run(
            [str(arg) for arg in args], cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MigrationError("A required command failed to start or timed out.") from error
    if result.returncode not in ok:
        # Git errors can contain filenames and application contents. Do not echo them.
        raise MigrationError("A required command failed; no command output is disclosed. See the last checkpoint.")
    return result


def safe_parents(path, root, include_leaf=False):
    """Reject symlink traversal rather than writing through a surprising parent."""
    if not inside(path, root):
        raise MigrationError("Unsupported path outside the expected root.")
    current = root
    parts = path.relative_to(root).parts
    for part in parts if include_leaf else parts[:-1]:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise MigrationError("A managed path has a symlink or non-directory parent; resolve it manually first.")


def checked_copy(source, destination, home, *, private=True, active=()):
    """Copy referents, never backup symlinks; reject escapes, loops and devices."""
    try:
        resolved = source.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise MigrationError("A backup input is missing, dangling, or cyclic.") from error
    if not inside(resolved, home) or resolved == home or resolved in active:
        raise MigrationError("A backup input escapes HOME or contains a symlink cycle.")
    mode = resolved.stat().st_mode
    if stat.S_ISREG(mode):
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(resolved, destination)
        if private:
            destination.chmod(stat.S_IMODE(mode) & 0o700)
    elif stat.S_ISDIR(mode):
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        for child in sorted(source.iterdir()):
            checked_copy(child, destination / child.name, home,
                         private=private, active=(*active, resolved))
        destination.chmod(0o700 if private else stat.S_IMODE(mode))
    else:
        raise MigrationError("A backup input is not a regular file or directory.")


class Migration:
    def __init__(self, source, home, *, baseline=BASELINE):
        self.source = Path(source).resolve()
        self.home = Path(home).resolve()
        self.baseline = baseline
        self.repo = self.home / REPOSITORY
        # Ignore user Git overrides, shell functions and repository-local executables.
        self.env = {
            "HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C",
            # Local-only migration; override even repository protocol.*.allow settings.
            "GIT_ALLOW_PROTOCOL": "file",
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "GIT_NO_REPLACE_OBJECTS": "1",
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
        }
        self.backup = None
        self.links = []
        self.backup_paths = set()
        self.alternates = {}

    def git(self, *args, target=False, ok=(0,)):
        prefix = ["git", "-c", "core.hooksPath=" + os.devnull,
                  "-c", "core.fsmonitor=false", "-c", "maintenance.auto=false",
                  "-c", "gc.auto=0", "-c", "core.attributesFile=" + os.devnull]
        if target:
            prefix += ["--git-dir=" + str(self.repo), "--work-tree=" + str(self.home)]
        return run([*prefix, *args], cwd=self.home if target else self.source,
                   env=self.env, ok=ok)

    def tree(self, commit):
        rows = self.git("ls-tree", "-rz", commit).stdout.split(b"\0")
        result = {}
        for row in rows:
            if not row:
                continue
            metadata, name = row.split(b"\t", 1)
            mode, kind, blob = metadata.decode().split()
            path = Path(os.fsdecode(name))
            if path.is_absolute() or ".." in path.parts or kind != "blob":
                raise MigrationError("Unsupported tracked path or submodule.")
            if mode not in ("100644", "100755"):
                raise MigrationError("Tracked symlinks are unsupported; migrate them manually first.")
            result[path] = blob
        return result

    def add_backup(self, path):
        if present(path):
            self.backup_paths.add(path)

    def preflight(self, apply=False):
        if not self.home.is_dir() or not self.source.is_dir():
            raise MigrationError("HOME and the separate source checkout must exist.")
        if self.source == self.home or inside(self.home, self.source):
            raise MigrationError("Run this script from a separate new checkout, not the yadm worktree.")
        for relative in (REPOSITORY, BACKUPS, Path(".local/bin")):
            safe_parents(self.home / relative, self.home, include_leaf=True)
        if not self.repo.is_dir() or not (self.source / ".git").is_dir():
            raise MigrationError("Expected a normal new checkout and existing XDG yadm repository.")
        for root, expected in (("XDG_CONFIG_HOME", ".config"),
                               ("XDG_DATA_HOME", ".local/share"),
                               ("XDG_STATE_HOME", ".local/state")):
            if root in os.environ and Path(os.environ[root]).resolve() != self.home / expected:
                raise MigrationError("Custom XDG locations are unsupported; use the legacy standard layout.")
        configured = self.git("config", "--no-includes", "--get", "core.worktree", target=True)
        if Path(os.fsdecode(configured.stdout).strip()).resolve() != self.home:
            raise MigrationError("The existing yadm repository does not use HOME as its worktree.")
        for flag in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "index.lock", "shallow", "commondir", "objects/info/alternates"):
            if present(self.repo / flag):
                raise MigrationError("The yadm repository has an unfinished operation or unsupported object layout.")
        self.machine_class = self.git("config", "--no-includes", "--get-all", "local.class", target=True, ok=(0, 1)).stdout.decode().strip()
        if self.machine_class not in ("home", "work"):
            raise MigrationError("Set exactly one existing yadm local.class to home or work before migration.")
        # Includes, filters and URL rewrites can select executable code or external sources.
        for target in (False, True):
            config = self.git("config", "--no-includes", "--name-only", "--list", target=target).stdout.decode().splitlines()
            if any(key.lower().startswith(("include.", "includeif.", "filter.", "url.")) for key in config):
                raise MigrationError("Git includes or content filters or URL rewrites require manual migration.")
        self.target = self.git("rev-parse", "HEAD").stdout.decode().strip()
        self.old = self.git("rev-parse", "HEAD", target=True).stdout.decode().strip()
        if self.git("merge-base", "--is-ancestor", self.baseline, self.target, ok=(0, 1, 128)).returncode:
            raise MigrationError("The new checkout must contain and descend from the immutable legacy baseline.")
        if self.git("merge-base", "--is-ancestor", self.old, self.target, ok=(0, 1, 128)).returncode:
            raise MigrationError("Target history diverged or is unknown to this checkout; reconcile it manually.")
        if self.git("merge-base", "--is-ancestor", self.baseline, self.old, ok=(0, 1, 128)).returncode:
            raise MigrationError("The existing yadm HEAD predates or does not descend from the supported baseline.")
        self.legacy = self.tree(self.baseline)
        self.current = self.tree(self.old)
        self.new = self.tree(self.target)
        for path in set(self.current) | set(self.new):
            if inside(self.source, self.home / path) or inside(self.source, (self.home / path).parent) and len(path.parts) > 1:
                raise MigrationError("The source checkout overlaps a managed target directory.")
            safe_parents(self.home / path, self.home)
        if Path(".config/yadm/bootstrap") in self.new or any(inside(path, STORAGE) or path.name.startswith(".mackup.cfg") for path in self.new):
            raise MigrationError("The committed new HEAD still contains legacy bootstrap or Mackup files.")
        config_text = self.git("show", self.target + ":.config/mise/config.toml").stdout.decode()
        version = re.search(r'^min_version\s*=\s*"(\d+\.\d+\.\d+)"\s*(?:#.*)?$', config_text, re.M)
        if not version:
            raise MigrationError("The committed mise configuration must declare a numeric min_version.")
        self.minimum = tuple(map(int, version[1].split(".")))
        self.version = version[1]
        source_dirty = self.git("status", "--porcelain", "--untracked-files=no").stdout
        untracked = [Path(os.fsdecode(name)) for name in
                     self.git("ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0") if name]
        source_dirty = source_dirty or any(
            path.suffix.lower() not in (".md", ".txt", ".rst")
            or (len(path.parts) > 1 and path.parts[0] != "docs")
            for path in untracked
        )
        if source_dirty and apply:
            raise MigrationError("Commit or discard tracked changes in the source checkout before --apply.")
        self.source_dirty = bool(source_dirty)
        self.check_target_clean()
        for relative in self.new.keys() - self.current.keys():
            if present(self.home / relative):
                raise MigrationError("A new tracked file would overwrite an untracked local file; move it aside first.")
        for relative in self.new:
            if "##" not in str(relative):
                continue
            base, condition = str(relative).split("##", 1)
            if condition not in ("class.home", "class.work"):
                raise MigrationError("Only the repository's home/work class alternates are supported.")
            destination = self.home / base
            safe_parents(destination, self.home)
            if present(destination) and not destination.is_symlink():
                raise MigrationError("A class alternate has a regular local file; preserve it manually before migration.")
            if destination.is_symlink() and destination.resolve() not in {
                self.home / (base + "##class.home"), self.home / (base + "##class.work")
            }:
                raise MigrationError("A class alternate points to an unsupported local path.")
            self.add_backup(destination)
            if condition == "class." + self.machine_class:
                self.alternates[destination] = self.home / relative
        self.collect_legacy()
        for relative in set(self.current) | set(self.legacy):
            self.add_backup(self.home / relative)
        for relative in (REPOSITORY, Path(".config/yadm"), STORAGE, HISTORY,
                         Path(".local/state/bash/history"), EXTRA_PREFERENCES,
                         Path(".local/bin/mise"), Path(".mackup.cfg")):
            self.add_backup(self.home / relative)
        old_config = self.home / ".mackup.cfg"
        if present(old_config):
            expected = self.home / (".mackup.cfg##class." + self.machine_class)
            if not old_config.is_symlink() or old_config.resolve() != expected:
                raise MigrationError("The legacy Mackup config is not the selected native class link; preserve it manually first.")
        if not shutil.which("yadm", path=self.env["PATH"]):
            raise MigrationError("Install yadm before running this migration.")
        return self

    def check_target_clean(self):
        if self.git("status", "--porcelain", "--untracked-files=no", target=True).stdout:
            raise MigrationError("The yadm worktree has tracked changes; save and reconcile them before migration.")
        # status alone hides assume-unchanged and sparse/skip-worktree entries.
        rows = self.git("ls-files", "-v", "-z", target=True).stdout.split(b"\0")
        for row in rows:
            if not row:
                continue
            flag, name = row[:1], Path(os.fsdecode(row[2:]))
            if flag.islower() or (flag == b"S" and str(name) not in ("README.md", "LICENSE", ".editorconfig")):
                raise MigrationError("Unsupported assume-unchanged or sparse index entries; normalize the index first.")

    def collect_legacy(self):
        # Use the old inventory, not the deliberately pruned new snapshot set.
        candidates = {self.home / path.relative_to(STORAGE) for path in self.legacy if inside(path, STORAGE)}
        candidates.add(self.home / EXTRA_PREFERENCES)
        # Include untracked storage entries (Mackup may have backed up whole directories).
        storage = self.home / STORAGE
        if storage.exists():
            for directory, dirs, files in os.walk(storage, followlinks=False):
                for name in [*dirs, *files]:
                    relative = (Path(directory) / name).relative_to(storage)
                    if relative.parts and relative.parts[0] == "Library":
                        live = self.home / relative
                        if name in files or live.is_symlink():
                            candidates.add(live)
        links = set()
        for candidate in candidates:
            # A directory-level Mackup link must be materialized as a whole.
            for path in reversed((candidate, *candidate.parents)):
                if path == self.home or not inside(path, self.home):
                    continue
                if path.is_symlink():
                    try:
                        referent = path.resolve(strict=True)
                    except (OSError, RuntimeError) as error:
                        raise MigrationError("A legacy application link is broken; restore its source before migration.") from error
                    if not inside(referent, storage):
                        raise MigrationError("A legacy application link points outside Mackup storage; migrate it manually.")
                    safe_parents(path, self.home)
                    links.add(path)
                    self.add_backup(path)
                    break
            else:
                self.add_backup(candidate)
        self.links = sorted(links)

    def make_backup(self):
        root = self.home / BACKUPS
        safe_parents(root, self.home, include_leaf=True)
        if root.exists() and (root.stat().st_uid != os.getuid() or stat.S_IMODE(root.stat().st_mode) & 0o077):
            raise MigrationError("The migration backup directory must be owned by you with mode 700.")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.backup = Path(tempfile.mkdtemp(prefix="migration-", dir=root))
        manifest = {"baseline": self.baseline, "previous_head": self.old, "target_head": self.target,
                    "class": self.machine_class, "symlinks": {}, "checkpoint": "backup-incomplete"}
        self.manifest = manifest
        self.checkpoint("backup-incomplete")
        roots = sorted(self.backup_paths, key=lambda p: (len(p.parts), str(p)))
        copied = []
        for path in roots:
            if any(inside(path, parent) for parent in copied):
                continue
            if path.is_symlink():
                manifest["symlinks"][str(path.relative_to(self.home))] = os.readlink(path)
            checked_copy(path, self.backup / "home" / path.relative_to(self.home), self.home)
            copied.append(path)
        for directory, _, _ in os.walk(self.backup / "home", followlinks=False):
            Path(directory).chmod(0o700)
        # A byte-preserving metadata copy retains executable hooks and internal modes,
        # while its enclosing directory remains private. It is never executed here.
        metadata = self.backup / "repository"
        checked_copy(self.repo, metadata, self.home, private=False)
        self.checkpoint("backup-complete")
        print("Private recovery copy: " + str(self.backup.relative_to(self.home)))

    def checkpoint(self, name):
        self.manifest["checkpoint"] = name
        file = self.backup / "manifest.json"
        file.write_text(json.dumps(self.manifest, indent=2) + "\n")
        file.chmod(0o600)
        print("Checkpoint: " + name)

    def adequate_mise(self, binary):
        if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
            return False
        try:
            result = run([binary, "--version"], cwd=self.backup, env={
                **self.env, "MISE_CONFIG_FILE": os.devnull, "MISE_NO_AUTO_INSTALL": "1",
            }, ok=tuple(range(256)), timeout=15)
        except MigrationError:
            return False
        match = re.match(rb"(?:mise\s+)?(\d+)\.(\d+)\.(\d+)(?:\s|$)", result.stdout)
        return bool(result.returncode == 0 and match and b"homebrew" not in result.stdout.lower()
                    and tuple(map(int, match.groups())) >= self.minimum)

    def stage_mise(self):
        binary = self.home / ".local/bin/mise"
        if self.adequate_mise(binary):
            return None
        architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64"}.get(platform.machine())
        if platform.system() != "Darwin" or not architecture:
            raise MigrationError("Official standalone installation requires supported macOS arm64/x64.")
        asset = "mise-v" + self.version + "-macos-" + architecture + ".tar.gz"
        url = "https://github.com/jdx/mise/releases/download/v" + self.version + "/"
        stage = self.backup / "install"
        stage.mkdir(mode=0o700)
        for name in (asset, "SHASUMS256.txt"):
            run(["curl", "--disable", "--fail", "--silent", "--show-error", "--location",
                 "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "15",
                 "--max-time", "300", "--output", stage / name, url + name],
                cwd=stage, env=self.env, timeout=310)
        checksums = (stage / "SHASUMS256.txt").read_text().splitlines()
        matches = [line.split()[0] for line in checksums if len(line.split()) == 2
                   and line.split()[1].lstrip("*./") == asset]
        digest = hashlib.sha256((stage / asset).read_bytes()).hexdigest()
        if matches != [digest]:
            raise MigrationError("The official mise archive failed its release checksum verification.")
        staged = stage / "mise"
        with tarfile.open(stage / asset, "r:gz") as archive:
            members = [member for member in archive.getmembers() if member.name == "mise/bin/mise"]
            if len(members) != 1 or not members[0].isfile():
                raise MigrationError("The official mise archive has an unexpected binary layout.")
            with archive.extractfile(members[0]) as source, staged.open("xb") as output:
                shutil.copyfileobj(source, output)
        staged.chmod(0o700)
        if not self.adequate_mise(staged):
            raise MigrationError("The downloaded standalone mise does not meet the committed minimum version.")
        return staged

    def apply(self):
        if self.source_dirty:
            raise MigrationError("Commit managed source changes before applying this plan.")
        for target, expected in ((False, self.target), (True, self.old)):
            if self.git("rev-parse", "HEAD", target=target).stdout.decode().strip() != expected:
                raise MigrationError("A repository HEAD changed since preflight; create a fresh plan.")
        print("Creating private backup; no application or repository mutation yet.")
        self.make_backup()
        print("Checking/staging the official standalone mise binary.")
        staged = self.stage_mise()
        self.check_target_clean()
        self.checkpoint("materializing-legacy-links")
        for link in self.links:
            safe_parents(link, self.home)
            temporary = Path(tempfile.mkdtemp(prefix=".migration-", dir=link.parent))
            try:
                copy = temporary / "data"
                checked_copy(link, copy, self.home)
                if copy.is_dir():
                    # POSIX cannot rename a directory over a symlink. The private
                    # backup is complete before this short unlink/rename window.
                    link.unlink()
                os.replace(copy, link)
            finally:
                shutil.rmtree(temporary)
        # .mackup.cfg is an untracked yadm alternate; remove only its legacy link.
        old_config = self.home / ".mackup.cfg"
        if old_config.is_symlink():
            if not old_config.resolve().name.startswith(".mackup.cfg##class.") or old_config.resolve().parent != self.home:
                raise MigrationError("Unexpected Mackup config link; the private backup is available.")
            old_config.unlink()
        if staged is not None:
            binary = self.home / ".local/bin/mise"
            safe_parents(binary, self.home)
            binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.NamedTemporaryFile(prefix=".mise-", dir=binary.parent, delete=False) as handle:
                temporary = Path(handle.name)
            try:
                shutil.copyfile(staged, temporary)
                temporary.chmod(0o755)
                os.replace(temporary, binary)
            finally:
                if temporary.exists():
                    temporary.unlink()
        self.checkpoint("deploying-committed-head")
        self.git("fetch", "--no-tags", "--no-write-fetch-head", str(self.source), self.target, target=True)
        self.git("merge", "--ff-only", "--no-edit", self.target, target=True)
        self.checkpoint("selecting-native-alternates")
        # Do not invoke the user's hooks/config/bootstrap. Only native yadm alt,
        # with the real repository's local.class, runs against a private config.
        alternate_config = self.backup / "alternate-config"
        alternate_config.mkdir(mode=0o700)
        (alternate_config / "config").write_text(
            "[yadm]\n\tauto-alt = false\n\tauto-perms = false\n\tauto-exclude = false\n\tauto-private-dirs = false\n"
        )
        run(["yadm", "--yadm-dir", alternate_config, "--yadm-repo", self.repo, "alt"],
            cwd=self.home, env={**self.env, "GIT_CONFIG_COUNT": "2",
                               "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": os.devnull,
                               "GIT_CONFIG_KEY_1": "core.fsmonitor", "GIT_CONFIG_VALUE_1": "false"})
        for destination, expected in self.alternates.items():
            if not destination.is_symlink() or destination.resolve() != expected:
                raise MigrationError("Native alternate selection did not select the expected class.")
        for link in self.links:
            if link.is_symlink() or not link.exists():
                raise MigrationError("A materialized application path failed its final check.")
        if self.git("rev-parse", "HEAD", target=True).stdout.decode().strip() != self.target:
            raise MigrationError("The deployed repository did not reach the planned commit.")
        self.checkpoint("complete")
        print("Migration complete. History and local application data retained; Homebrew packages untouched.")
        print("Open a new shell before using the new configuration. No workstation bootstrap was run.")

    def report(self):
        print("Plan: " + self.old[:12] + " -> " + self.target[:12] + " (class " + self.machine_class + ")")
        print("Private backup, materialize " + str(len(self.links)) + " legacy application links, fast-forward, native alternates.")
        print("Standalone mise minimum: " + self.version + "; installation checked only on --apply.")
        print("Existing shared history stays unchanged; Bash starts a separate history. No app/defaults/bootstrap actions.")
        if self.source_dirty:
            print("Uncommitted source changes are ignored in this preview; commit managed files before --apply.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="back up and apply the committed migration (default: read-only)")
    args = parser.parse_args(argv)
    migration = Migration(Path(__file__).resolve().parents[1], Path.home())
    try:
        migration.preflight(apply=args.apply)
        migration.report()
        if args.apply:
            migration.apply()
        else:
            print("Dry run: no files changed and no downloads or yadm commands run. Use --apply after closing writers.")
        return 0
    except (MigrationError, OSError, ValueError, tarfile.TarError) as error:
        message = str(error) if isinstance(error, MigrationError) else "A filesystem or archive operation failed; no sensitive details are printed."
        print("Migration stopped: " + message, file=sys.stderr)
        if migration.backup:
            print("Private recovery copy: " + str(migration.backup.relative_to(migration.home)), file=sys.stderr)
            print("Inspect manifest.json privately. Do not delete the backup or reset the repository blindly.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
