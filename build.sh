#!/usr/bin/env bash
# Build gallery dance clips (each dance normal + mirrored "_M") for a heroine, in one UE session:
#   ./build.sh <Char> [Dance ...]     Dance = source/<Dance>.fbx (default: every source/*.fbx)
#   ./build.sh all [Dance ...]        every prepped heroine, two at a time (one bakes in Blender while the other is in UE)
#   ./build.sh pak                    re-pak stage/ and install
# One-time per heroine first: python tools/prep_char.py <Char>. Built clips stay in stage/ and all go into one pak.
# Env: SKIP_BAKE=1 reuses fbx/ bakes, JOBS = parallel Blender bakes, PROJ = UE project dir, NOPAK=1 skips the pak step.
set -euo pipefail
export MSYS_NO_PATHCONV=1
D="$(cd "$(dirname "$0")" && pwd)"; cd "$D"
UE=/d/Modding/UE_4.22/Engine/Binaries/Win64

pak() {
  : > stage/filelist.txt
  find "$D/stage/Subverse" -type f | while read -r f; do echo "\"$(cygpath -w "$f")\" \"../../../${f#$D/stage/}\"" >> stage/filelist.txt; done
  mkdir -p dist
  "$UE/UnrealPak.exe" "$(cygpath -w "$D/dist/GalleryDance_P.pak")" -create="$(cygpath -w "$D/stage/filelist.txt")" -compress | grep -E 'Added [0-9]+ files'
  if tasklist 2>/dev/null | grep -qi Subverse-Win64; then  # the running game does NOT lock the pak: never overwrite it under the game
    echo "== built dist/GalleryDance_P.pak - game running, run ./install.sh after closing it"
  else
    cp dist/GalleryDance_P.pak "/d/Games/R18/Subverse/Subverse/Content/Paks/~mods/" && echo "== installed GalleryDance_P.pak ($(grep -c . stage/filelist.txt) files)"
  fi
}
if [ "${1:-}" = pak ]; then pak; exit; fi
if [ "${1:-}" = all ]; then
  shift; DA=("$@"); mkdir -p log
  mapfile -t CH < <(ls export/*/char.json | sed 's#export/##; s#/char.json##' | grep -vxE "${SKIPCH:-^$}")  # SKIPCH="Killi|Lily" skips
  [ -f ue/SubverseDance2/SubverseDance.uproject ] || { mkdir -p ue/SubverseDance2; cp -r ue/SubverseDance/SubverseDance.uproject ue/SubverseDance/Config ue/SubverseDance2/; }
  stream() {  # <project dir> <heroines...>
    local p=$1; shift
    for c in "$@"; do
      s=$(date +%s)
      if PROJ="$D/ue/$p" NOPAK=1 JOBS=4 "$0" "$c" "${DA[@]}" > "log/build_$c.txt" 2>&1; then r=ok; else r=FAILED; fi
      echo "$c $r $(( $(date +%s) - s ))s | $(grep -h 'rest check' "log/build_$c.txt")" | tee -a log/build_all.txt
    done
  }
  : > log/build_all.txt
  A=(); B=(); for i in "${!CH[@]}"; do if (( i % 2 )); then B+=("${CH[$i]}"); else A+=("${CH[$i]}"); fi; done
  stream SubverseDance "${A[@]}" & stream SubverseDance2 "${B[@]}" & wait
  pak | tee -a log/build_all.txt; echo "ALL DONE" >> log/build_all.txt; exit
fi

CHAR="$1"; shift
BL="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
PROJ="${PROJ:-$D/ue/SubverseDance}"; COOK="$PROJ/Saved/Cooked/WindowsNoEditor/SubverseDance"
JOBS=${JOBS:-6}  # parallel Blender bakes (each ~2-4 GB RAM)
w() { cygpath -am "$1"; }  # absolute: UE resolves relative paths from its own folder
J="$(w "$D/export/$CHAR/char.json")"; test -f "$J" || { echo "run: python tools/prep_char.py $CHAR"; exit 1; }
cfg() { python -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$J" "$1"; }
SKEL="$(cfg skeleton)"; SKDIR="${SKEL%/*}"; GPSK="$(cfg gallery_mesh_psk)"; GPSA="$(cfg gallery_pose_psa)"
DANCES=("$@"); [ ${#DANCES[@]} -gt 0 ] || mapfile -t DANCES < <(cd source && ls *.fbx | sed 's/\.fbx$//')
CLIPS=(); for d in "${DANCES[@]}"; do CLIPS+=("A_${CHAR}_Dance_$d" "A_${CHAR}_Dance_${d}_M"); done
mkdir -p log fbx

echo "== 1. retarget ${#CLIPS[@]} clips in Blender ($CHAR, $JOBS at a time)"
bake() {  # <dance> <clip> [mirror]
  "$BL" -b --python "$(w blender/retarget.py)" -- "$(w "$D")" "$CHAR" "$(w "source/$1.fbx")" "$2" ${3:-} > "log/$2.log" 2>&1
  "$BL" -b "$(w "blender/$2.blend")" --python "$(w blender/export_fbx.py)" -- "$(w "fbx/$2.fbx")" >> "log/$2.log" 2>&1
}
for d in "${DANCES[@]}"; do
  for m in "" mirror; do
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n || true; done
    [ -n "${SKIP_BAKE:-}" ] && [ -f "fbx/A_${CHAR}_Dance_$d${m:+_M}.fbx" ] && continue  # reuse earlier bakes
    rm -f "fbx/A_${CHAR}_Dance_$d${m:+_M}.fbx"; bake "$d" "A_${CHAR}_Dance_$d${m:+_M}" $m &
  done
done
wait || true
PAIRS=(); for c in "${CLIPS[@]}"; do
  test -f "fbx/$c.fbx" || { echo "Blender failed for $c, see log/$c.log"; grep -E 'Error|Traceback' -A3 "log/$c.log" | head; exit 1; }
  echo "$c: $(grep -h 'GROUND after' "log/$c.log")"; PAIRS+=("$(w "fbx/$c.fbx")" "$c")
done

echo "== 2. import + cook in UE 4.22 (fresh skeleton every time: its rest pose comes from the FBX)"
rm -rf "$PROJ/Content/StudioFow" "$PROJ/Content/Mods" "$PROJ/Saved/Cooked"
ue() { "$UE/UE4Editor-Cmd.exe" "$(cygpath -w "$PROJ/SubverseDance.uproject")" "$@" -unattended -nopause -nosplash -stdout; }
ue -run=pythonscript -script="$(w "$D/ue/import_clip.py") $SKEL ${PAIRS[*]}" > "log/${CHAR}_import.log" 2>&1 || true
ue -run=pythonscript -script="$(w "$D/ue/fix_clip.py") $CHAR ${CLIPS[*]}" > "log/${CHAR}_fix.log" 2>&1 || true
ue -run=cook -targetplatform=WindowsNoEditor -unversioned -cookall > "log/${CHAR}_cook.log" 2>&1 || true
CL="$COOK/Content/Mods/GalleryDance/$CHAR"
for c in "${CLIPS[@]}"; do test -f "$CL/$c.uexp" || { echo "cook failed for $c, see log/${CHAR}_cook.log"; exit 1; }; done

echo "== 3. read back our skeleton order + rest pose with UModel"
O="export/ours_$CHAR"; rm -rf "$O"; mkdir -p "$O"
um() { (cd tools/umodel && ./umodel_64.exe -path="$(cygpath -w "$COOK")" -game=ue4.22 -export -out="$(cygpath -w "$D/$O")" "$1" > /dev/null); }
um "$SKDIR/SK_$CHAR"  # one package per call (2nd arg = object name)
for c in "${CLIPS[@]}"; do um "/Game/Mods/GalleryDance/$CHAR/$c"; done
python tools/check_rest.py "$(w "$(ls "$O/${SKDIR#/Game/}/SK_$CHAR".psk*)")" "$GPSK"

echo "== 4. remap track tables to the game's bone order, stage"
ST="stage/Subverse/Content/Mods/GalleryDance/$CHAR"; mkdir -p "$ST"
for c in "${CLIPS[@]}"; do
  cp "$CL/$c".uasset "$CL/$c".uexp "$ST/"
  python tools/remap_tracks.py "$(w "$ST/$c.uasset")" "$(w "$O/Mods/GalleryDance/$CHAR/$c.psa")" "$GPSA" | sed "s/^/$c: /"
done
[ -n "${NOPAK:-}" ] || pak
