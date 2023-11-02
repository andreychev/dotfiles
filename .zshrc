source "$HOME/.aliases"
source "$HOME/.xdg.dirs"

# Make some path, must be done before antigen
export PATH="/opt/homebrew/bin:$PATH"
export PATH="/opt/homebrew/sbin:$PATH"

# Install all zsh-related stuff using antigen
export ADOTDIR="$XDG_CONFIG_HOME/antigen"
source $(brew --prefix)/share/antigen/antigen.zsh
antigen init "$ADOTDIR/config"

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export EDITOR="vim"

export PATH="$HOME/.yarn/bin:$HOME/.config/yarn/global/node_modules/.bin:$PATH"

# Tweak Node
export NODE_OPTIONS=--max_old_space_size=1536

if type brew &>/dev/null; then
  FPATH=$(brew --prefix)/share/zsh-completions:$FPATH

  autoload -Uz compinit
  compinit -d "$XDG_CACHE_HOME"/zsh/zcompdump-"$ZSH_VERSION"
fi

# Prefer US English and use UTF-8.
export LANG="en_US.UTF-8"
export LC_ALL="en_US.UTF-8"

# Make Python use UTF-8 encoding for output to stdin, stdout, and stderr.
export PYTHONIOENCODING="UTF-8"

# Don’t clear the screen after quitting a manual page.
export MANPAGER="less -X";

# Deactivate Homebrew analytics, see https://docs.brew.sh/Analytics
export HOMEBREW_NO_ANALYTICS=1

# Avoid issues with `gpg` as installed via Homebrew.
# https://stackoverflow.com/a/42265848/96656
export GPG_TTY=$(tty);

# Hide the “default interactive shell is now zsh” warning on macOS.
export BASH_SILENCE_DEPRECATION_WARNING=1;

# Make HOME great again!
export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
export CARGO_HOME="$XDG_DATA_HOME"/cargo
export GNUPGHOME="$XDG_DATA_HOME"/gnupg
export LESSHISTFILE="$XDG_CACHE_HOME"/less/history
export WGETRC="$XDG_CONFIG_HOME/wgetrc"
export HISTFILE="$XDG_STATE_HOME"/zsh/history
export TERMINFO="$XDG_DATA_HOME"/terminfo
export TERMINFO_DIRS="$XDG_DATA_HOME"/terminfo:/usr/share/terminfo

# This loads scmpuff
eval "$(scmpuff init -s)"

if [ -z "$SSH_AUTH_SOCK" ] ; then
    eval `ssh-agent -s`
    ssh-add
fi

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
