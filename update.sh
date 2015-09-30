#!/bin/bash

# Update Homebrew

function header() {
	echo -e "$(tput sgr 0 1)$(tput setaf 6)$1$(tput sgr0)"
}

# Ask for the administrator password upfront
sudo -v
echo

# Homebrew
header "Updating Homebrew..."
sudo -v
brew update
brew upgrade
brew cleanup
echo
