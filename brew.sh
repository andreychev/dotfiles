#!/usr/bin/env bash

# Install command-line tools using Homebrew.

# Ask for the administrator password upfront.
sudo -v

# Keep-alive: update existing `sudo` time stamp until the script has finished.
while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &

# Make sure we’re using the latest Homebrew.
brew update

# Upgrade any already-installed formulae.
brew upgrade --all

# More recent versions of some OS X tools
brew tap homebrew/dupes
brew install homebrew/dupes/grep
brew install homebrew/dupes/screen

utils=(
  coreutils
  moreutils
  findutils
  m-cli
)

brew install ${utils[@]}
sudo ln -s /usr/local/bin/gsha256sum /usr/local/bin/sha256sum

# Subversions
subversions=(
  git
  git-extras
  hub
  gist
  tig

  subversion
  mercurial
)

brew install ${subversions[@]}

# Extend global $PATH
echo -e "setenv PATH $HOME/dotfiles/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" | sudo tee /etc/launchd.conf

# OS X crutches
crutches=(
  vim --override-system-vi

  ack

  bash
  shellcheck
  ntfs-3g

  tree
  ctags

  htop-osx
  wget --with-iri
  unrar

  gnu-sed --with-default-names
  openssl

  httpie

  msmtp --with-macosx-keyring
)

brew install ${crutches[@]}

# Everything else
everythingelse=(
  archey
  thefuck
  dark-mode
  youtube-dl
  mackup
  ranger
  ansiweather
)

brew install ${everythingelse[@]}

languages=(
  python
  ansible

  scala
  sbt

  erlang

  go

  racket

  postgresql

  rbenv
)

brew install ${languages[@]}

# Terminal multiplexer
brew install tmux
brew install reattach-to-user-namespace

# Frontend libs
brew install imagemagick
brew install watchman
brew install jq

# Node.js && npm
brew install nvm
mkdir "$HOME/.nvm"
export NVM_DIR="$HOME/.nvm"
source $(brew --prefix nvm)/nvm.sh
nvm install stable
nvm use stable
nvm alias default stable

brew install ttfautohint fontforge --with-python
brew link --force openssl

# Remove outdated versions from the cellar
brew cleanup
