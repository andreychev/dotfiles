# Install npm scripts globally
sudo -v

npmscripts=(
	node-gyp

	npm-check-updates
	which
	caniuse-cmd

	pure-prompt

	gulp
	browser-sync

	guppy-cli

	karma

	csscomb
)

npm install -g ${npmscripts[@]}
