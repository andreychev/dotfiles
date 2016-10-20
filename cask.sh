# Brew cask

brew install caskroom/cask/brew-cask

brew tap caskroom/versions

brew tap caskroom/fonts

apps=(
  slack

  java

  haskell-platform

  tunnelblic

  sequel-pro

  google-chrome
  google-chrome-canary
  firefox
  opera
  torbrowser-ru

  quicklook-json
  qlmarkdown
  quicklook-csv
  qlimagesize

  iterm2
  rescuetime
  anybar
  postman
  choosy
  quitter

  flux

  appcleaner
  raindropio
  calibre
  vlc
  utorrent
  xld
  sopcast
  spotify
  mailbutler
  fantastical

  microsoft-office

  teamviewer
  ngrok

  docker
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
  font-fira-code
)

brew cask install ${apps[@]}
brew cask install ${fonts[@]}

brew cask cleanup
