# Install npm scripts globally
sudo -v

npmscripts=(
	node-gyp

	npm-check-updates
	which
	caniuse-cmd

	osx-wifi-cli
	pure-prompt

	jshint
	jscs

	gulp
	browser-sync

	docpad

	karma

	csscomb
)

npm install -g ${npmscripts[@]}
