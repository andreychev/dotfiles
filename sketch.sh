sketch=(
  sketch
  sketch-toolbox
  zeplin
)

brew cask install ${sketch[@]}

brew cask cleanup

# Install Sketch plugins
# Move It
curl -L https://github.com/dawidw/move-it/archive/master.zip > MoveIt.zip; unzip MoveIt.zip
# Sort Me
curl -L https://github.com/romashamin/sort-me-sketch/archive/master.zip > SortMe.zip; unzip SortMe.zip
# Craft 
curl -L https://s3.amazonaws.com/www-assets.invisionapp.com/labs/craft/manager/CraftInstaller.zip
