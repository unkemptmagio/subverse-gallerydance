#!/usr/bin/env bash
# Build one gallery dance clip end to end:  ./build.sh <Char> <source.fbx> <ClipName>
#   e.g. ./build.sh Lily "source/Dancing Twerk.fbx" A_Lily_Dance_Twerk
# One-time per heroine first: python tools/prep_char.py <Char>   (writes export/<Char>/char.json)
# Every built clip stays in stage/ and goes into the one GalleryDance_P.pak.
set -euo pipefail
export MSYS_NO_PATHCONV=1
D="$(cd "$(dirname "$0")" && pwd)"; CHAR="$1"; SRC="$2"; CLIP="$3"
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
UE=/d/Modding/UE_4.22/Engine/Binaries/Win64
PROJ="$D/ue/SubverseDance"; COOK="$PROJ/Saved/Cooked/WindowsNoEditor/SubverseDance"
w() { cygpath -m "$1"; }
J="$(w "$D/export/$CHAR/char.json")"; test -f "$J" || { echo "run: python tools/prep_char.py $CHAR"; exit 1; }
cfg() { python -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$J" "$1"; }
SKEL="$(cfg skeleton)"; SKDIR="${SKEL%/*}"; GPSK="$(cfg gallery_mesh_psk)"; GPSA="$(cfg gallery_pose_psa)"

echo "== 1. retarget in Blender ($CHAR)"
"$BL" -b --python "$(w "$D/blender/retarget.py")" -- "$(w "$D")" "$CHAR" "$(w "$SRC")" "$CLIP" 2>&1 | grep -E 'mapped|leg scale|GROUND|DONE|Error'
"$BL" -b "$(w "$D/blender/$CLIP.blend")" --python "$(w "$D/blender/export_fbx.py")" -- "$(w "$D/fbx/$CLIP.fbx")" 2>&1 | grep -E 'EXPORTED|Error'

echo "== 2. import + cook in UE 4.22 (fresh skeleton every time: its rest pose comes from the FBX)"
rm -rf "$PROJ/Content/StudioFow" "$PROJ/Content/Mods" "$PROJ/Saved/Cooked"
"$UE/UE4Editor-Cmd.exe" "$(cygpath -w "$PROJ/SubverseDance.uproject")" -run=pythonscript -script="$(w "$D/ue/import_clip.py") $(w "$D/fbx/$CLIP.fbx") $CLIP $SKEL" -unattended -nopause -nosplash -stdout > "$D/ue/import.log" 2>&1 || true
"$UE/UE4Editor-Cmd.exe" "$(cygpath -w "$PROJ/SubverseDance.uproject")" -run=pythonscript -script="$(w "$D/ue/fix_clip.py") $CLIP $CHAR" -unattended -nopause -nosplash -stdout > "$D/ue/fix.log" 2>&1 || true
grep -E 'CLIP ' "$D/ue/fix.log" | grep -v LogInit | tail -1
"$UE/UE4Editor-Cmd.exe" "$(cygpath -w "$PROJ/SubverseDance.uproject")" -run=cook -targetplatform=WindowsNoEditor -unversioned -cookall -unattended -nopause -nosplash -stdout > "$D/ue/cook.log" 2>&1 || true
CL="$COOK/Content/Mods/GalleryDance/$CHAR"; test -f "$CL/$CLIP.uexp" || { echo "cook failed, see ue/cook.log"; exit 1; }

echo "== 3. read back our skeleton order + rest pose with UModel"
rm -rf "$D/export/ours"; mkdir -p "$D/export/ours"
for pkg in "/Game/Mods/GalleryDance/$CHAR/$CLIP" "$SKDIR/SK_$CHAR"; do  # one package per call (2nd arg = object name)
  (cd "$D/tools/umodel" && ./umodel_64.exe -path="$(cygpath -w "$COOK")" -game=ue4.22 -export -out="$(cygpath -w "$D/export/ours")" "$pkg" > /dev/null)
done
python "$(w "$D/tools/check_rest.py")" "$(w "$(ls "$D/export/ours/${SKDIR#/Game/}/SK_$CHAR".psk*)")" "$GPSK"

echo "== 4. remap track tables to the game's bone order, pak, install"
ST="$D/stage/Subverse/Content/Mods/GalleryDance/$CHAR"; mkdir -p "$ST"; cp "$CL/$CLIP".uasset "$CL/$CLIP".uexp "$ST/"
python "$(w "$D/tools/remap_tracks.py")" "$(w "$ST/$CLIP.uasset")" "$(w "$D/export/ours/Mods/GalleryDance/$CHAR/$CLIP.psa")" "$GPSA"
: > "$D/stage/filelist.txt"
find "$D/stage/Subverse" -type f | while read -r f; do echo "\"$(cygpath -w "$f")\" \"../../../${f#$D/stage/}\"" >> "$D/stage/filelist.txt"; done
mkdir -p "$D/dist"
"$UE/UnrealPak.exe" "$(cygpath -w "$D/dist/GalleryDance_P.pak")" -create="$(cygpath -w "$D/stage/filelist.txt")" -compress | grep -E 'Added [0-9]+ files'
if cp "$D/dist/GalleryDance_P.pak" "/d/Games/R18/Subverse/Subverse/Content/Paks/~mods/" 2>/dev/null; then
  echo "== installed GalleryDance_P.pak ($(grep -c . "$D/stage/filelist.txt") files)"
else  # the running game locks the pak
  echo "== built dist/GalleryDance_P.pak ($(grep -c . "$D/stage/filelist.txt") files) - game running, install after closing it"
fi
