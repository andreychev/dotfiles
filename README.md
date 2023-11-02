This playbook installs and configures most of the software I use on my Mac for web and software development. Some things in macOS are slightly difficult to automate, so I still have a few manual installation steps, but at least it's all documented here.

## Installation

```bash
# Ensure macOS is updated
sudo softwareupdate -i -a

# Ensure Apple's command line tools are installed
xcode-select --install
sudo xcodebuild -license

# Ensure you were authorized in the Mac App Store.

# Install homebrew.
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install mas.
/opt/homebrew/bin/brew install mas

# Clone or download this repository to your local drive.

# Install all dependencies.
brew bundle
```

<!-- 1. Ensure macOS is updated (`sudo softwareupdate -i -a`).
1. Ensure Apple's command line tools are installed (`xcode-select --install` to launch the installer).
1. Ensure you were authorized in the Mac App Store.
1. [Install brew](https://brew.sh/).
1. Install ansible by running `/opt/homebrew/bin/brew install ansible`.
1. Clone or download this repository to your local drive.
1. Run `/opt/homebrew/Cellar/ansible/x.x.x/bin/ansible-playbook main.yml --ask-become-pass` inside this directory. Enter your account password when prompted. -->

### Things that need to be done manually

1. Remap Caps Lock to Ctrl.
1. Install [vimi](https://github.com/miripiruni/vimi).
1. Install [Ilya Birman Typography Layout](https://ilyabirman.net/projects/typography-layout).
1. Install [QMK Toolbox](https://github.com/qmk/qmk_toolbox/releases) and [latest Neo65 firmware](https://www.qwertykeys.com/pages/fw), [map Launchpad to F13](https://github.com/the-via/releases/issues/92#issuecomment-826337718).
1. Install [QuickGPT](https://sindresorhus.gumroad.com/l/quickgpt).
1. Install [CryptoPRO 5.0](https://www.cryptopro.ru/products/csp) and [Chromium ГОСТ](https://github.com/deemru/Chromium-Gost/releases).
1. Install [Amnezia VPN](https://amnezia.org/en).
1. Authorize Yandex.Disk and wait for sync.
1. Run `cp .mackup.cfg ~/.mackup.cfg`.
1. Run `export PATH="opt/mackup/bin/mackup:$PATH" && mackup restore`.
1. Run `/opt/homebrew/Caskroom/paragon-ntfs/15/FSInstaller.app`.
1. Configure extra Mail, Calendar.
1. Apply all licenses.
1. Install Microsoft Office and Microsoft Teams.

## Thanks to…

- [Jeff Geerling](https://www.jeffgeerling.com/) and [his Mac Development Ansible Playbook](https://github.com/geerlingguy/mac-dev-playbook)
- [Mathias Bynens](https://mathiasbynens.be/) and [his dotfiles repo](https://github.com/mathiasbynens/dotfiles)
- [Nikita Barskov](https://dev-tau-seven.vercel.app/) and [his dotfiles repo](https://github.com/nikitabarskov/dotfiles)
