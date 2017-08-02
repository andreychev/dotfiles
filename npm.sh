# Install npm scripts globally
sudo -v

npmscripts=(
  which
  caniuse-cmd
  tldr
  nativefier
  jscodeshift

  pure-prompt

  browser-sync
  
  create-react-app
)

npm install -g ${npmscripts[@]}
