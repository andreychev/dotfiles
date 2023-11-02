#!/usr/bin/env bash

DOWNLOADS_DIR="$HOME/Downloads"

TYPOGRAPHY="3.8"
CHROMIUM_GOST="119.0.6045.105"
AMNEZIA="4.0.8.6"

cd $DOWNLOADS_DIR
curl -fLo "ilya-birman-typolayout-$TYPOGRAPHY-mac.dmg" "https://ilyabirman.ru/typography-layout/download/ilya-birman-typolayout-$TYPOGRAPHY-mac.dmg"
curl -fLo NEO65_0816.json https://cdn.shopify.com/s/files/1/0508/8716/4061/files/NEO65_0816.json
curl -fLo "$CHROMIUM_GOST-macos-arm64.tar.bz2" "https://github.com/deemru/Chromium-Gost/releases/download/$CHROMIUM_GOST/chromium-gost-$CHROMIUM_GOST-macos-arm64.tar.bz2"
curl -fLo "AmneziaVPN_$AMNEZIA.dmg" "https://github.com/amnezia-vpn/amnezia-client/releases/download/${AMNEZIA%.*}/AmneziaVPN_$AMNEZIA.dmg"
cd $HOME
