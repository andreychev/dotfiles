#!/bin/zsh

# Powerlevel10k Instant Prompt
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Source Configurations
source "$XDG_CONFIG_HOME/shell/config"
source "$XDG_CONFIG_HOME/zsh/environment.zsh"

# Plugin Management (antidote)
export ANTIDOTE_HOME=${XDG_CACHE_HOME:=~/.cache}/repos

# Clone antidote if not exists
[[ -d $ANTIDOTE_HOME/mattmc3/antidote ]] ||
  git clone --depth 1 --quiet https://github.com/mattmc3/antidote $ANTIDOTE_HOME/mattmc3/antidote

# Generate plugins file
zsh_plugins="${ZDOTDIR}/.zsh_plugins"
if [[ ! "${zsh_plugins}".zsh -nt "${zsh_plugins}".txt ]]; then
  (
    source $ANTIDOTE_HOME/mattmc3/antidote/antidote.zsh
    antidote bundle < "${zsh_plugins}".txt > "${zsh_plugins}".zsh
  )
fi
source "${zsh_plugins}".zsh

# Functions and Theming
fpath=("$XDG_CONFIG_HOME/shell/functions" $fpath)
autoload -Uz "$XDG_CONFIG_HOME/shell/functions/*(.:t)"

# Set theme
fast-theme -q XDG:catppuccin-mocha

# Prompt Configuration
autoload -Uz promptinit
promptinit
prompt powerlevel10k

# Tool Initialization
eval "$(scmpuff init -s --aliases=false)"
eval "$(mise activate zsh)"

# Powerlevel10k Configuration
[[ ! -f "$ZDOTDIR/.p10k.zsh" ]] || source "$ZDOTDIR/.p10k.zsh"
