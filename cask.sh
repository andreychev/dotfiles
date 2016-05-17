# Brew cask

brew install caskroom/cask/brew-cask

brew tap caskroom/versions

brew tap caskroom/fonts

apps=(
	slack

	java

	tunnelblic

	sequel-pro

	google-chrome
	google-chrome-canary
	firefox
	opera
	torbrowser-ru

	iterm2
	rescuetime
	anybar
	quicklook-json

	flux

	appcleaner
	raindrop
	calibre
	vlc
	utorrent
	xld
	sopcast

	microsoft-office

	teamviewer

	dockertoolbox
	vagrant
	parallels-desktop

	intellij-idea-ce
	webstorm
)

fonts=(
	font-hack
	font-ubuntu
	font-ubuntu-mono-powerline
	font-roboto
)

brew cask install ${apps[@]}
brew cask install ${fonts[@]}

brew cask cleanup
