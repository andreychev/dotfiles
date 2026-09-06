This scripts installs and configures most of the software I use on my Mac for web and software development.

## Intro

1. Setup uses [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) and is heavily inspired by [this blog post](https://gist.github.com/sharadhr/39b804236c1941e9c30d90af828ad41e).
2. [`yadm`](https://yadm.io/) manages dotfiles and app snapshots; [`mise`](https://mise.jdx.dev/) manages tools, bootstrap and explicit snapshot restore/capture.
3. [`zsh`](https://en.wikipedia.org/wiki/Z_shell), [`powerlevel10k`](https://github.com/romkatv/powerlevel10k), and [`antidote`](https://github.com/mattmc3/antidote) work together with [`Ghostty`](https://ghostty.org/) to provide high-performance, beautiful, and handy terminal defaults.
4. Some things in macOS are slightly difficult to automate, so there are a few manual installation steps, but at least it's all documented here.

## Installation

```sh
# Take Me Home, Country Roads.
cd $HOME

# Ensure macOS is updated.
sudo softwareupdate -i -a

# Ensure Apple's command line tools are installed.
xcode-select --install

# **Ensure you are authorized in the Mac App Store**.

# Enable TouchID for sudo (uncomment corresponding line).
# Note: at least in the US, you cannot be compelled to give up a password by a court (it's considered a violation of the 5th amendment), but your biometrics are not secret, so you can absolutely be forced by a court to biometric auth.
sudo cp /etc/pam.d/sudo_local.template /etc/pam.d/sudo_local
sudo vi /etc/pam.d/sudo_local

# Install Homebrew.
if [[ $(command -v brew) == "" ]]; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install bootstrap prerequisites.
/opt/homebrew/bin/brew install mas
/opt/homebrew/bin/brew install yadm

# Install the official mise binary (also installed automatically by bootstrap if missing).
curl -fsSL https://mise.run | MISE_INSTALL_PATH="$HOME/.local/bin/mise" sh
export PATH="$HOME/.local/bin:$PATH"

# Clone this repository and set the machine class before running bootstrap.
# yadm clone --bootstrap doesn't support passing a class, so do it in steps:
yadm clone git@github.com:andreychev/dotfiles.git
yadm config local.class home   # or: work
yadm alt
# Preview first: "$HOME/.config/yadm/bootstrap" --dry-run
yadm bootstrap
```

### Bootstrap and maintenance

The yadm entry point prepares XDG paths and requires `local.class` to be `home` or
`work` before installation or other changes. It installs mise from
[mise.run](https://mise.run) into `~/.local/bin/mise` if missing, then invokes
`mise -C "$HOME" -E workstation bootstrap` (mise 2026.9.1 or newer). Homebrew owns
the other packages and uses the Brewfile selected by yadm. Bootstrap runs Homebrew,
macOS preferences, mise tool installation, then home app snapshot restore, Docker
buildx, downloads and yadm sparse-checkout. Work uses Mail defaults without file restore.

Global `config.toml` contains tools, environment and maintenance tasks only.
Machine hooks, preferences and the finishing task live in
`.config/mise/config.workstation.toml`, loaded only with `-E workstation`.
Ordinary project bootstrap does not inherit these operations. Do not export
`MISE_ENV=workstation` globally. The yadm entry fixes `MISE_CONFIG_DIR` to the
deployed XDG config and clears `MISE_GLOBAL_CONFIG_FILE` for its child process:
that override disables environment-sibling discovery in mise 2026.9.1.

Bootstrap downloads the installer completely before executing it and removes the
temporary script on success or failure. Preview/help with missing local mise does
not download anything and does not fall back to a Homebrew binary. Use the plain
installer endpoint, not `/zsh` or `/bash`: shell activation is already managed here.

Missing, unknown or unreadable `local.class` stops bootstrap before mutations.
Set it with `yadm config local.class home` (or `work`), then run `yadm alt`.
Direct helper phases and targeted workstation defaults/tools phases also validate
the class. For applying a subset, use the guarded entry, for example
`"$HOME/.config/yadm/bootstrap" --only macos-defaults`.

Class reads use Git directly against `$XDG_DATA_HOME/yadm/repo.git/config`, the
standard yadm repository location used here, with includes disabled. They do not
invoke yadm: even `yadm config local.class` can run hooks, relink alternates and
change permissions. Set the class and apply alternates explicitly with yadm.

Application downloads use a same-directory temporary file and an atomic rename
only after curl succeeds. Failures remove the partial file so a later run retries.
Our curl requests use a 15-second connection deadline and a 300-second total
deadline; release metadata is parsed with `jq`. A damaged final DMG left by an
older bootstrap still needs explicit removal before retrying.

When migrating an existing machine, verify `command -v mise` resolves to
`~/.local/bin/mise` before separately removing the old formula with
`brew uninstall mise`. Bootstrap does not uninstall that formula automatically.

Scalar macOS preferences live in `.config/mise/config.workstation.toml`. Arrays,
dictionary updates, host-scoped preferences and the dynamic screenshot path remain
in `.config/macos/defaults-extra`. Mise 2026.9.1 does not expand templates in raw
defaults values or bootstrap hooks; hooks use shell variables instead. Existing
application `defaults` scripts still run after the native preferences.

Deploy the rename, including removal of the old `conf.d/macos.toml`; leaving that
file in `$HOME` would keep its preferences globally active.

After the configs are deployed to `$HOME`:

```sh
# Preview the whole machine bootstrap without installing or applying anything.
"$HOME/.config/yadm/bootstrap" --dry-run

# Inspect only the declarative macOS preferences; this excludes the shell extras.
mise -C "$HOME" -E workstation bootstrap macos defaults status

# List tasks, then run one explicit maintenance operation.
mise tasks
mise -C "$HOME" run --skip-tools update:tools
```

| Task | Operation |
|---|---|
| `update:mise` | Update the official mise binary with `self-update --no-plugins` |
| `update:tools` | `mise upgrade`, preserving version constraints; no `--bump` |
| `update:brew` | Homebrew update, upgrade and cleanup |
| `update:zsh` | Update antidote plugins |
| `update:nvim` | Synchronize Neovim plugins |
| `update:macos` | Install macOS updates; explicit and potentially restart-requiring |

These tasks replace `brewup`, `zshup`, `nvimup` and `macosup`. Navigation and other
interactive aliases remain in the shell. Exact runtime pins and `NODE_OPTIONS`
are unchanged; `mise upgrade` does not advance an exact pin automatically.

Use `--skip-tools` for all six maintenance tasks. It skips the runner's implicit
runtime installation, not the requested `upgrade` or `self-update` operation.
Bare `mise run update:...` retains mise's normal auto-install behavior. Mise
2026.9.1 has no task-local opt-out for its initial installation pass; global
auto-install settings remain unchanged so ordinary project tasks still work.

To preview a task without installing tools or running commands:

```sh
mise -C "$HOME" run --dry-run --skip-tools update:brew
```

### Application preference snapshots

Yadm selects `.config/mise/config.app-preferences.toml` from the `##class.home` or
`##class.work` alternate. Home declares 13 explicit `copy` entries sourced from
`.config/app-preferences/home/Library/`; work declares no file snapshots. Both classes
apply six Mail preferences through workstation defaults. Archived Mail and Raycast
snapshots under `.config/app-preferences/archive/` are never selected.

After deploying both alternates to HOME, run `yadm alt`, then use native mise commands:

```sh
# Inspect or preview without changing snapshots or target files.
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles status
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles apply --dry-run

# Close affected apps and back up current preferences before applying.
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles apply

# After changing settings and quitting the apps, capture changed selected files.
MISE_CEILING_PATHS="$HOME" mise -C "$HOME" -E app-preferences bootstrap dotfiles add --changed --no-apply
```

There is no custom status/restore/capture shell interface. `-E app-preferences` opts
into the selected profile; `-C` plus the HOME ceiling excludes the caller's project
and HOME-local configs. System/global configuration still follows native mise merging.
These commands assume normal XDG discovery, without a `MISE_GLOBAL_CONFIG_FILE`
override. Keep the profile out of `conf.d` and do not activate it globally.

The native `pre-dotfiles` hook runs the existing class preflight. The home hook also
restricts source-tree permissions so native copies inherit private file modes. Apply
must run with hooks enabled. Status, dry-run and `add --changed --no-apply` do not run
the apply hook. Capture updates existing selected regular files without rewriting the
profile or its yadm symlink; missing targets and archives are skipped. Review changes
in yadm before committing.

Apply overwrites selected files even without `--force`; it is not a merge or a
transaction. Full workstation bootstrap invokes the same native apply command before
buildx/downloads. Ordinary project bootstrap and maintenance do not select this profile.
Existing target symlinks are replaced with regular files; preserve their former data.

Deployment and removal of an installed Mackup remain separate from checkout edits.
Preserve local config additions and live targets, run `yadm alt`, and remove the old
standalone `app-preferences.home.toml` and obsolete Mackup paths only after checking
their data. Rollback restores backed-up live files and the exported Mail domain, not
merely Git state; native `unapply` is not undo. See
[MACKUP-REMOVAL-PLAN.md](MACKUP-REMOVAL-PLAN.md) for deployment gates.

### Shell initialization

Bash initializes available Homebrew before shared shell configuration and keeps
`~/.local/bin` first in PATH. Interactive `.bashrc` loading activates the official
mise binary; noninteractive loading does not install a mise shell hook.

History is shell-specific: `$XDG_STATE_HOME/bash/history` and
`$XDG_STATE_HOME/zsh/history`. Parent directories are created by interactive Bash
and Zsh setup. Existing history contents are not rewritten or automatically split.
The shared XDG file no longer owns `HISTFILE`.

Shared configuration loads XDG tool defaults first, then general and class-specific
environment settings, then aliases. `environment.home` / `environment.work`
overrides therefore survive and are visible to aliases. Class lookup is read-only.

### Regression checks

On macOS with mise installed, run from this checkout:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The tests run real mise and finite Bash/Zsh sessions with temporary homes and
recording substitutes for macOS/package commands and downloads. They cover
workstation isolation, class validation, both profiles, interrupted transfers and
retry, installer failure/cleanup, dry-run, shell activation/history, PATH precedence
and maintenance tasks without network access, runtime installs or host preferences.
The preview regression also uses real yadm with a temporary repository. The
maintenance regression keeps auto-install enabled and uses a local, network-free
probe tool: maintenance skips its installer while an ordinary project task runs it.

### Things that need to be done manually

1. [Remap Caps Lock to Ctrl](https://support.apple.com/zh-sg/guide/mac-help/mchlp1011/mac), [Launchpad to F13](https://github.com/the-via/releases/issues/92#issuecomment-826337718).
3. Install [Paragon NTFS](https://uc.paragon-software.com/cabinet).
4. Install M1-compatible apps: Streisand, Xiaomi Home, SailTies.
5. Install Adobe Lightroom from Adobe Creative Cloud.
8. Authorize Yandex.Disk and wait for sync.
9. Authorize iCloud Drive and Photos.
10. Configure extra Mail, Calendar.
11. Apply all licenses.

## Thanks to…

- [Github dotfiles repos](https://dotfiles.github.io/)
