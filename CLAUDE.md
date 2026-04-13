# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Personal macOS dotfiles managed with **yadm** (Yet Another Dotfiles Manager) and **Mackup**. Follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) to keep `$HOME` clean — nearly all configs live under `~/.config/`.

## Initial Setup

```sh
# Prerequisites: macOS updated, Xcode CLI tools, Mac App Store signed in
brew install mas yadm mackup
yadm clone git@github.com:andreychev/dotfiles.git --bootstrap
```

The `--bootstrap` flag runs `.config/yadm/bootstrap` automatically.

## Home vs Work Machines

The repo uses **yadm alternates** (`##class.home` / `##class.work`) to support two machine profiles. Set the class once per machine — it's stored locally and never committed:

```sh
yadm config local.class home  # or: work
yadm alt                       # applies symlinks for the active class
```

**Files that differ by class:**

| File | home | work |
|------|------|------|
| `Brewfile` | symlink → `Brewfile##class.home` | symlink → `Brewfile##class.work` |
| `.mackup.cfg` | symlink → `.mackup.cfg##class.home` | symlink → `.mackup.cfg##class.work` |
| `~/.config/shell/aliases.*` | sources `aliases.home` | sources `aliases.work` (if exists) |
| `~/.config/shell/environment.*` | sources `environment.home` (not tracked) | sources `environment.work` (not tracked) |
| `~/.config/git/config.work` | not needed | created manually, not tracked |

**Brewfile structure:** `Brewfile.base` has shared tools. Class files include it via Ruby `instance_eval` then add class-specific apps. `brew bundle` works without flags.

**Git identity:** personal email is the default everywhere. Repos inside `~/work/` use the work email from `~/.config/git/config.work` (user creates manually, not committed).

**After cloning on a new machine:** set `local.class`, run `yadm alt`, then create `~/.config/git/config.work` and `~/.config/shell/environment.work` locally.

## Bootstrap Script (`.config/yadm/bootstrap`)

Runs in order:
1. Validates macOS environment
2. Sources `.xdg.dirs` and `.config/shell/xdg` for XDG paths
3. `brew bundle` — installs `Brewfile` (symlinked by yadm to the active class variant)
4. Executes all `defaults` files found under `$XDG_CONFIG_HOME`
5. `mackup restore && mackup uninstall` — restores app prefs then removes symlinks
6. Sets up `docker-buildx` CLI plugin symlink
7. Downloads: Ilya Birman Typography Layout (all); Amnezia VPN + Yandex.Disk (home only)
8. Initializes yadm sparse-checkout (excludes README, LICENSE, .editorconfig)

## Update Commands (shell aliases)

| Alias | What it does |
|-------|-------------|
| `brewup` | `brew update && brew upgrade && brew cleanup` |
| `macosup` | `sudo softwareupdate -i -a` |
| `zshup` | Updates antidote plugins |
| `nvimup` | `nvim --headless "+Lazy! sync" +qa` |
| `dotfiles` | Opens all yadm-tracked files in editor |

## Adding New Software

- **Shared CLI tool**: add to `Brewfile.base`
- **Home-only app**: add to `Brewfile##class.home`
- **Work-only app**: add to `Brewfile##class.work`
- **Mac App Store app**: same pattern with `mas "Name", id: <id>`
- **macOS system defaults**: add `defaults write` commands to `.config/macos/defaults`
- **App preferences via Mackup**: add to `.mackup.cfg##class.home` or `.mackup.cfg##class.work`

## Architecture

### Shell Initialization Chain

```
~/.zshenv  →  sets ZDOTDIR=$XDG_CONFIG_HOME/zsh
~/.config/zsh/.zshrc  →  loads antidote plugins, initializes Powerlevel10k, activates mise
~/.config/shell/environment  →  language, editors, FZF defaults, Homebrew analytics off
~/.config/shell/aliases  →  shared aliases for bash and zsh
~/.config/shell/aliases.home  →  home-only aliases (disk, rn-photos); sourced automatically
~/.config/shell/xdg  →  maps XDG dirs for individual tools (Cargo, GPG, npm, Docker, AWS, Go, etc.)
```

`.bashrc` follows the same pattern but sources bash-specific config.

### Key Config Locations

| Tool | Config path |
|------|------------|
| Zsh plugins | `.config/zsh/.zsh_plugins.txt` (antidote) |
| Neovim | `.config/nvim/` (LazyVim-based, Catppuccin Macchiato theme) |
| Git | `.config/git/config` |
| Mise (runtimes) | `.config/mise/config.toml` |
| macOS defaults | `.config/macos/defaults` |
| iTerm2 | `.config/iterm2/` |

### Runtime Versions (Mise)

Node 22, Python 3.11, Go 1.26, Rust stable. Global npm tools: yarn, pnpm, sql-formatter.

### Theming

Catppuccin Mocha/Macchiato is used consistently across iTerm2, bat, fzf, Neovim, and the Zsh theme.

### Yadm vs Mackup

- **yadm**: tracks dotfiles (shell configs, tool configs, Brewfiles, this repo)
- **Mackup**: syncs GUI app preferences via the file system backend pointing to `.config/`; split by class — home syncs Bartender, CleanShot, Spotify etc.; work syncs only Mail, VLC, Zoom
