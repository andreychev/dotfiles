
#!/bin/sh

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.config/zsh/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

source "$XDG_CONFIG_HOME"/shell/config

export HOMEBREW_PREFIX="/opt/homebrew"
export HOMEBREW_CELLAR="/opt/homebrew/Cellar"
export HOMEBREW_REPOSITORY="/opt/homebrew"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin${PATH+:$PATH}"
export MANPATH="/opt/homebrew/share/man${MANPATH+:$MANPATH}:"
export INFOPATH="/opt/homebrew/share/info:${INFOPATH:-}"

# Lazy-load antidote and generate the static load file only when needed
zsh_plugins="${ZDOTDIR}"/.zsh_plugins
if [[ ! "${zsh_plugins}".zsh -nt "${zsh_plugins}".txt ]]; then
  (
    source "$HOMEBREW_PREFIX"/opt/antidote/share/antidote/antidote.zsh
    antidote bundle <"${zsh_plugins}".txt >"${zsh_plugins}".zsh
  )
fi
source ${zsh_plugins}.zsh

if type brew &>/dev/null; then
  FPATH="$HOMEBREW_PREFIX/share/zsh-completions:$FPATH"

  autoload -Uz compinit
  compinit -d "$XDG_CACHE_HOME"/zsh/zcompdump-"$ZSH_VERSION"
fi

autoload -Uz promptinit && promptinit && prompt powerlevel10k

# This loads scmpuff
eval "$(scmpuff init -s)"

# To customize prompt, run `p10k configure` or edit $ZDOTDIR/.p10k.zsh.
[[ ! -f "$ZDOTDIR"/.p10k.zsh ]] || source "$ZDOTDIR"/.p10k.zsh

