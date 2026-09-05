#!/bin/bash

# Source the XDG directories configuration
source "$HOME"/.xdg.dirs

# mise.run and other user-local tools take precedence over package-manager binaries.
export PATH="$HOME/.local/bin:$PATH"

# Check if XDG_CONFIG_HOME is set before sourcing the shell config
if [ -n "$XDG_CONFIG_HOME" ]; then
    source "$XDG_CONFIG_HOME"/shell/config
else
    echo "Warning: XDG_CONFIG_HOME is not set. Skipping shell config."
fi
