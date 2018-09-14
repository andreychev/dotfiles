# Install npm scripts globally
sudo -v

npmscripts=(
  caniuse-cmd
  tldr
  nativefier
  jscodeshift
  pure-prompt  
  yarn
)

npm install -g ${npmscripts[@]}
