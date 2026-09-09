# Dotfiles

Personal macOS configuration: **yadm** deploys files and selects `home` / `work`;
**mise** manages runtimes and machine setup; **Homebrew** installs system packages.
Configs live under `~/.config/`.

## New Mac

Install Xcode Command Line Tools, [Homebrew](https://brew.sh/) and the
[official mise binary](https://mise.jdx.dev/getting-started.html) at
`~/.local/bin/mise` (2026.9.1 or newer, not the Homebrew formula).
Sign in to the Mac App Store first.

```sh
brew install yadm mas
export HOMEBREW_PREFIX="$(brew --prefix)"
export PATH="$HOME/.local/bin:$HOMEBREW_PREFIX/bin:$HOMEBREW_PREFIX/sbin:$PATH"
yadm clone git@github.com:andreychev/dotfiles.git
yadm config local.class home  # or work
yadm alt
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E workstation bootstrap --dry-run
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E workstation bootstrap
```

Bootstrap installs packages/tools, applies macOS preferences and selected app
settings, and completes machine setup. Preview skips hooks, including class checks.
App logins, licenses and cloud synchronization remain manual.
On work machines, create local `~/.config/git/config.work` and
`~/.config/shell/environment.work`; keep them out of Git.

## Existing Mac: migrate

Run from a **separate checkout of the committed new version**, before updating the
old yadm checkout. Close affected apps and resolve tracked local changes first.
The legacy baseline is `main` at `c454ecb` (the repository has no `master` branch).

```sh
python3 scripts/migrate-from-legacy.py          # preview; no changes
python3 scripts/migrate-from-legacy.py --apply  # back up and migrate
```

The script preserves current app data and machine class, detaches old Mackup
symlinks, updates yadm by fast-forward and selects the new alternates. It ensures
`~/.local/bin/mise` is available without running workstation bootstrap, overwriting
live preferences with repository snapshots, upgrading runtimes or uninstalling
packages. Keep the private backup it reports until you have checked your apps.
See `--help` for prerequisites and failure handling.

## Maintenance

```sh
mise tasks
mise -C "$HOME" run --skip-tools update:tools
```

Other tasks: `update:mise`, `update:brew`, `update:zsh`, `update:nvim`, `update:macos`.
Use `--skip-tools` to avoid implicit runtime installation; add `--dry-run` to preview.
Machine setup stays opt-in: do not export `MISE_ENV=workstation` globally.

## App settings

Home keeps two VLC/VLSub config files and explicit scalar preferences in the mise
profile; work has no app snapshots. Full plists, accounts, licenses and media history
are excluded. Complex layouts/rules stay in private backups, not automatic transfer.
After changing machine class, run `yadm alt`. Edit scalar settings in the profile;
`add --changed` captures files only. Workstation bootstrap applies both parts.

```sh
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles status
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles apply --dry-run
# Close affected apps and back up before applying: selected files are overwritten.
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles apply
# Apply only the explicitly managed scalar preferences, preserving other plist keys.
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap --only macos-defaults
# After changing settings and quitting the apps, capture selected files only.
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles add --changed --no-apply
```

Review captured changes before committing. Keep hooks enabled on apply.
Old Git history still contains the original snapshots; this migration does not rewrite it.

## Checks

On macOS with Python 3.11+, standalone mise and yadm installed:

```sh
PATH="$HOME/.local/bin:$PATH" python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Tests use temporary homes; they do not verify application GUI behavior.
