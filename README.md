This scripts installs and configures most of the software I use on my Mac for web and software development.

## Intro

1. Setup uses [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html) and heavily inspired by [this blogpost](https://gist.github.com/sharadhr/39b804236c1941e9c30d90af828ad41e).
2. [`yadm`](https://yadm.io/) is used for managing dotfiles, [`mackup`](https://github.com/lra/mackup) is used for managing some desktop application preferences.
3. [`zsh`](https://en.wikipedia.org/wiki/Z_shell), [`powerline10k`](https://github.com/romkatv/powerlevel10k) and [`antidote`](https://github.com/mattmc3/antidote) are working together with [`iterm2`](https://iterm2.com/) to provide high-perfomant, beaufiful and handy terminal defaults.
4. Some things in macOS are slightly difficult to automate, so there are a few manual installation steps, but at least it's all documented here.

## Installation

```sh
# Take Me Home, Country Roads.
cd $HOME

# Ensure macOS is updated.
sudo softwareupdate -i -a

# Ensure Apple's command line tools are installed.
xcode-select --install
sudo xcodebuild -license

# **Ensure you were authorized in the Mac App Store**.

# Enable TouchID for sudo (uncomment corresponding line).
# Note: at least in the US, you cannot be compelled to give up a password by a court (it's considered a violation of the 5th amendment), but your biometrics are not secret, so you can absolutely be forced by a court to biometric auth.
sudo cp sudo_local.template sudo_local
sudo vi sudo_local

# Install Homebrew.
if [[ $(command -v brew) == "" ]]; then
  /bin/sh -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install mas, yadm, mackup.
/opt/homebrew/bin/brew install mas
/opt/homebrew/bin/brew install yadm
/opt/homebrew/bin/brew install mackup

# Clone this repository to your local drive using yadm.
yadm clone git@github.com:andreychev/dotfiles.git --bootstrap
```

### Things that need to be done manually

1. [Remap Caps Lock to Ctrl](https://support.apple.com/zh-sg/guide/mac-help/mchlp1011/mac), [Launchpad to F13](https://github.com/the-via/releases/issues/92#issuecomment-826337718).
1. Install [QuickGPT](https://sindresorhus.gumroad.com/l/quickgpt).
1. Install [CryptoPRO 5.0](https://www.cryptopro.ru/products/csp).
1. Install [Paragon NTFS](https://uc.paragon-software.com/cabinet).
1. Authorize Yandex.Disk and wait for sync.
1. Authorize iCloud Drive and Photos.
1. Configure extra Mail, Calendar.
1. Apply all licenses.
1. Install Microsoft Office and Microsoft Teams.

## Thanks to…

- [Github dotfiles repos](https://dotfiles.github.io/)
