# Brew cask

brew install caskroom/cask/brew-cask

brew tap caskroom/versions

apps=(
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

	dockertoolbox
	vagrant
	parallels-desktop

	intellij-idea-ce
	webstorm
)

brew cask install ${apps[@]}

brew cask cleanup
