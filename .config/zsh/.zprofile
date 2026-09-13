#!/bin/zsh

# /etc/zprofile runs path_helper before this file, which re-prepends
# /usr/local/bin, /usr/bin, etc. from /etc/paths, undoing the ordering
# set in ~/.zshenv. Re-run brew shellenv here so Homebrew wins again.
eval "$(/opt/homebrew/bin/brew shellenv)"
