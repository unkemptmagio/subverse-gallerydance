#!/usr/bin/env bash
# Install the GalleryDance UE4SS mod + pak into the game. Safe to rerun after every build.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
GAME=/d/Games/R18/Subverse/Subverse
MODS="$GAME/Binaries/Win64/ue4ss/Mods"

# dances.txt = every clip staged by build.sh, as /Game paths
( cd "$D/stage/Subverse/Content" && find Mods/GalleryDance -name '*.uasset' | sort | sed 's#^#/Game/#; s#\.uasset$##' ) > "$D/mod/GalleryDance/dances.txt"
touch "$D/mod/GalleryDance/enabled.txt"
mkdir -p "$MODS/GalleryDance/Scripts"
cp "$D/mod/GalleryDance/Scripts/main.lua" "$MODS/GalleryDance/Scripts/"
cp "$D/mod/GalleryDance/dances.txt" "$D/mod/GalleryDance/enabled.txt" "$MODS/GalleryDance/"
rm -f "$MODS/GalleryProbe/enabled.txt"   # the probe's F-keys clash (its F7 breaks the menu)
if tasklist 2>/dev/null | grep -qi Subverse-Win64; then echo "pak NOT installed: game running (it does not lock the pak, so never copy under it)"
else cp "$D/dist/GalleryDance_P.pak" "$GAME/Content/Paks/~mods/" && echo "pak installed"; fi
echo "GalleryDance installed with $(grep -c . "$D/mod/GalleryDance/dances.txt") dances:"; sed 's#.*/##' "$D/mod/GalleryDance/dances.txt" | tr '\n' ' '; echo
