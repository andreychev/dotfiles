# Brew cask

brew install caskroom/cask/brew-cask

brew tap caskroom/versions

brew tap caskroom/fonts

apps=(
  slack
  skype

  java
  
  google-chrome
  google-chrome-canary
  firefox
  opera
  
  alfred
  hazel
  bartender
  
  powershell
    
  visual-studio-code
  
  tunnelblick

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
  
  day-o
  appcleaner
  raindropio
  calibre
  vlc
  transmission
  xld
  mailbutler
  fantastical
  telegram

  microsoft-office

  docker
)

fonts=(
  font-hack
  font-roboto
  font-roboto-mono
  font-fira-code
)

brew cask install ${apps[@]}
brew cask install ${fonts[@]}

brew cask cleanup
