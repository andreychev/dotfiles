# Install npm scripts globally
sudo -v

npmscripts=(
	node-gyp

	npm-check-updates
	which
	caniuse-cmd
	tldr

	pure-prompt

	gulp
	browser-sync

	guppy-cli

	karma

	csscomb
)

npm install -g ${npmscripts[@]}
