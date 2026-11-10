#!/usr/bin/env bash
# Build the Nexus/GitHub release zip from stage/:  ./release.sh 1.1
# Test-only dances (EXCLUDE, a grep -E pattern) stay out of the release pak and list.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"; cd "$D"; V="$1"
EXCLUDE="${EXCLUDE:-JumpingJacks}"; UE=/d/Modding/UE_4.22/Engine/Binaries/Win64
R=dist/release; G=$R/Subverse; M=$G/Binaries/Win64/ue4ss/Mods/GalleryDance
rm -rf "$R"; mkdir -p "$G/Content/Paks/~mods" "$M/Scripts" "$R/credits"
( cd stage/Subverse/Content && find Mods/GalleryDance -name '*.uasset' | grep -vE "$EXCLUDE" | sort | sed 's#^#/Game/#; s#\.uasset$##' ) > mod/GalleryDance/dances.txt
find "$D/stage/Subverse" -type f | grep -vE "$EXCLUDE" | while read -r f; do echo "\"$(cygpath -w "$f")\" \"../../../${f#$D/stage/}\""; done > dist/release_filelist.txt
"$UE/UnrealPak.exe" "$(cygpath -w "$D/$G/Content/Paks/~mods/GalleryDance_P.pak")" -create="$(cygpath -w "$D/dist/release_filelist.txt")" -compress | grep -E 'Added [0-9]+ files'
cp mod/GalleryDance/Scripts/main.lua "$M/Scripts/"; cp mod/GalleryDance/dances.txt "$M/"; : > "$M/enabled.txt"
cp mod/release/README.txt mod/release/CREDITS.txt "$R/"
cp source/GhostDance/GhostDance_readme_utf8.txt "$R/credits/GhostDance_readme.txt"
cp source/GhostDance/GhostDance_readme_original_SJIS.txt "$R/credits/GhostDance_readme_original.txt"
rm -f "dist/GalleryDance-$V.zip"
( cd "$R" && python -m zipfile -c "../GalleryDance-$V.zip" Subverse README.txt CREDITS.txt credits )
echo "dist/GalleryDance-$V.zip: $(grep -c . mod/GalleryDance/dances.txt) dances, $(du -h "dist/GalleryDance-$V.zip" | cut -f1)"
