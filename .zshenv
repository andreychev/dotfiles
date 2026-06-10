#!/bin/zsh

source "$HOME"/.xdg.dirs

export ZDOTDIR="$XDG_CONFIG_HOME"/zsh

# Homebrew (must be set before .zshrc so yadm/brew tools are on PATH early)
eval "$(/opt/homebrew/bin/brew shellenv)"

# User-local binaries (Claude Code, uv-installed tools, etc.)
export PATH="$HOME/.local/bin:$PATH"
