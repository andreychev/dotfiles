# Install npm scripts globally
sudo -v

npmscripts=(
  node-gyp

  which
  caniuse-cmd
  tldr

  # LOL
  gify

  pure-prompt

  gulp
  browser-sync

  guppy-cli

  karma
)

npm install -g ${npmscripts[@]}
