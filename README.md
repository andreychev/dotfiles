This scripts installs and configures most of the software I use on my Mac for web and software development. Some things in macOS are slightly difficult to automate, so I still have a few manual installation steps, but at least it's all documented here.

## Installation

```bash
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
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install mas, yadm, mackup.
/opt/homebrew/bin/brew install mas
/opt/homebrew/bin/brew install yadm
/opt/homebrew/bin/brew install mackup

# Install vimi.
git clone https://github.com/miripiruni/vimi.git "$HOME/.vimi" && cd "$HOME/.vimi" && make

# Create basic directories.
mkdir work
mkdir personal

# Clone this repository to your local drive using yadm.
yadm clone git@github.com:andreychev/dotfiles.git

# Install all dependencies.
/opt/homebrew/bin/brew bundle

# Apply all defaults.
/bin/bash -c ".macos --no-restart && .apps --no-restart"

# Restore all mackup settings.
/opt/homebrew/bin/mackup restore && /opt/homebrew/bin/mackup uninstall

# Download old-fashioned sources.
/bin/bash tasks/download.sh

# Install FS.
/opt/homebrew/Caskroom/paragon-ntfs/15/FSInstaller.app

# Install nvm.
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
```

### Things that need to be done manually

1. [Remap Caps Lock to Ctrl](https://support.apple.com/zh-sg/guide/mac-help/mchlp1011/mac), [Launchpad to F13](https://github.com/the-via/releases/issues/92#issuecomment-826337718).
1. Install [QuickGPT](https://sindresorhus.gumroad.com/l/quickgpt).
1. Install [CryptoPRO 5.0](https://www.cryptopro.ru/products/csp).
1. Authorize Yandex.Disk and wait for sync.
1. Authorize iCloud Drive and Photos.
1. Configure extra Mail, Calendar.
1. Apply all licenses.
1. Install Microsoft Office and Microsoft Teams.

## Thanks to…

- [Mathias Bynens](https://mathiasbynens.be/) and [his dotfiles repo](https://github.com/mathiasbynens/dotfiles)
- [Nikita Barskov](https://dev-tau-seven.vercel.app/) and [his dotfiles repo](https://github.com/nikitabarskov/dotfiles)
