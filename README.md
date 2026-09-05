This scripts installs and configures most of the software I use on my Mac for web and software development.

## Intro

1. Setup uses [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) and is heavily inspired by [this blog post](https://gist.github.com/sharadhr/39b804236c1941e9c30d90af828ad41e).
2. [`yadm`](https://yadm.io/) is used for managing dotfiles, and [`mackup`](https://github.com/lra/mackup) is used for managing some desktop application preferences.
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
/opt/homebrew/bin/brew install mackup

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

The yadm entry point prepares XDG paths, installs mise from [mise.run](https://mise.run)
into `~/.local/bin/mise` if missing, and delegates to `mise bootstrap`
(mise 2026.9.1 or newer). Homebrew still owns the other packages and uses the
home/work Brewfile selected by yadm. Bootstrap runs Homebrew, macOS preferences,
mise tool installation, then Mackup restore, Docker buildx setup, downloads and
yadm sparse-checkout. It does not run `mackup uninstall`.

Bootstrap downloads the installer completely before executing it and removes the
temporary script on success or failure. Preview/help with missing local mise does
not download anything and does not fall back to a Homebrew binary. Use the plain
installer endpoint, not `/zsh` or `/bash`: shell activation is already managed here.

When migrating an existing machine, verify `command -v mise` resolves to
`~/.local/bin/mise` before separately removing the old formula with
`brew uninstall mise`. Bootstrap does not uninstall that formula automatically.

Scalar macOS preferences live in `.config/mise/conf.d/macos.toml`. Arrays,
dictionary updates, host-scoped preferences and the dynamic screenshot path remain
in `.config/macos/defaults-extra`. Mise 2026.9.1 does not expand templates in raw
defaults values or bootstrap hooks; hooks use shell variables instead. Existing
application `defaults` scripts still run after the native preferences.

After the configs are deployed to `$HOME`:

```sh
# Preview the whole machine bootstrap without installing or applying anything.
"$HOME/.config/yadm/bootstrap" --dry-run

# Inspect only the declarative macOS preferences; this excludes the shell extras.
mise -C "$HOME" bootstrap macos defaults status

# List tasks, then run one explicit maintenance operation.
mise tasks
mise -C "$HOME" run update:tools
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

To preview a task without installing tools or running commands:

```sh
mise -C "$HOME" run --dry-run --skip-tools update:brew
```

### Regression checks

On macOS with mise installed, run from this checkout:

```sh
python3 tests/test_mise_bootstrap.py -v
```

The tests run real mise with temporary homes and recording substitutes for
macOS/package commands and the installer download. They cover both profiles,
reruns, cold start, interrupted downloads, installer failure/cleanup, dry-run,
PATH precedence and maintenance tasks without network access, runtime installs or
changes to the current user's preferences.

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
