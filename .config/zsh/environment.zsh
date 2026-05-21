#!/bin/zsh

setopt AUTO_CD           # Auto changes to a directory without typing cd.
setopt AUTO_PUSHD        # Push the old directory onto the stack on cd.
setopt PUSHD_IGNORE_DUPS # Do not store duplicates in the stack.
setopt PUSHD_SILENT      # Do not print the directory stack after pushd or popd.
setopt PUSHD_TO_HOME     # Push to home directory when no argument is given.
setopt CDABLE_VARS       # Change directory to a path stored in a variable.
setopt MULTIOS           # Write to multiple descriptors.
setopt EXTENDED_GLOB     # Use extended globbing syntax.

HISTSIZE=10000          # Max number of history entries in memory.
SAVEHIST=10000          # Max number of history entries saved to disk.

setopt SHARE_HISTORY         # Share history between all sessions.
setopt HIST_IGNORE_ALL_DUPS  # Remove older duplicate entries from history.
setopt HIST_IGNORE_SPACE     # Do not record entries starting with a space.
setopt HIST_REDUCE_BLANKS    # Remove superfluous blanks from history entries.

