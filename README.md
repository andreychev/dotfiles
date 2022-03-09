This playbook installs and configures most of the software I use on my Mac for web and software development. Some things in macOS are slightly difficult to automate, so I still have a few manual installation steps, but at least it's all documented here.

## Installation

1. Ensure macOS is updated (`sudo softwareupdate -i -a`).
1. Ensure Apple's command line tools are installed (`xcode-select --install` to launch the installer).
1. Ensure you were authorized in the Mac App Store.
1. [Install Ansible](https://docs.ansible.com/ansible/latest/installation_guide/index.html):

   1. [Install Python3](https://www.python.org/downloads/macos/)
   2. Upgrade Pip: `sudo pip3 install --upgrade pip`
   3. Install Ansible: `pip3 install ansible`

1. Clone or download this repository to your local drive.
1. Run `ansible-galaxy install -r requirements.yml` inside this directory to install required Ansible roles.
1. Run `ansible-playbook main.yml --ask-become-pass` inside this directory. Enter your macOS account password when prompted for the 'BECOME' password.

### Running a specific set of tagged tasks

You can filter which part of the provisioning process to run by specifying a set of tags using `ansible-playbook`'s `--tags` flag. The tags available are `homebrew`, `extra-packages` and `macos`.

    ansible-playbook main.yml -K --tags "homebrew"

My other dotfiles are also available into the current user's home directory, including the `.macos` dotfile for configuring many aspects of macOS for better performance and ease of use.

Finally, there are a few other preferences and settings added on for various apps and services.

### Things that need to be done manually

1. Install [vimi](https://github.com/miripiruni/vimi).
1. Set Solarized Dark as default iTerm2 theme.
1. Install [Ilya Birman Typography Layout](https://ilyabirman.net/projects/typography-layout).
1. Remap Caps Lock to Ctrl.
1. Install [Obinskit](https://www.hexcore.xyz/obinskit).
1. Install [Pure prompt](https://github.com/xcambar/purs).
1. Authorize Yandex.Disk and wait for sync.
1. Run `cp .mackup.cfg ~/.mackup.cfg`.
1. Run `export PATH="opt/mackup/bin/mackup:$PATH" && mackup restore`.
1. Run `/opt/homebrew/Caskroom/paragon-ntfs/15/FSInstaller.app`.
1. Configure extra Mail, Calendar.
1. Apply all licenses.

## Thanks to…

- [Jeff Geerling](https://www.jeffgeerling.com/) and [his Mac Development Ansible Playbook](https://github.com/geerlingguy/mac-dev-playbook)
- [Mathias Bynens](https://mathiasbynens.be/) and [his dotfiles repo](https://github.com/mathiasbynens/dotfiles)
- Nikita Barskov and [his dotfiles repo](https://github.com/nikitabarskov/dotfiles)
