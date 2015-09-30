# Ask for the administrator password upfront
sudo -v

# Make sure we’re using the latest Homebrew
brew update

# Upgrade any already-installed formulae
brew upgrade

# More recent versions of some OS X tools
brew tap homebrew/dupes
brew install homebrew/dupes/grep

# Subversions
subversions=(
	git
	git-extras
	hub
	gist
	tig

	subversions
	mercurial
)

brew install ${subversions[@]}

# Extend global $PATH
echo -e "setenv PATH $HOME/dotfiles/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" | sudo tee /etc/launchd.conf

# OS X crutches
crutches=(
	coreutils
	findutils
	vim

	ack
	bash
	ntfs-3g

	tree
	ctags

	htop-osx
	wget
	unrar

	gnu-sed

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
)

brew install ${languages[@]}

# Terminal multiplexers
brew install tmux
brew install screen
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

# Remove outdated versions from the cellar
brew cleanup
