# GalleryDance for Subverse

Looping dances for every Gallery heroine, picked from an in-game panel, with physics kept on.

Nexus Mods: https://www.nexusmods.com/subverse/mods/27

## Requirements
- Subverse (tested on GOG v1.2 + Celestina DLC)
- [UE4SS v3.0.1](https://github.com/UE4SS-RE/RE-UE4SS/releases) in `Subverse\Subverse\Binaries\Win64`

## Install
Download the zip from [Releases](../../releases) and extract it into the game folder (the one with `Subverse.exe`). This adds:
- `Subverse\Content\Paks\~mods\GalleryDance_P.pak` (the dances)
- `Subverse\Binaries\Win64\ue4ss\Mods\GalleryDance\` (the panel)

## Use
In the Gallery, press **F7**. Click a dance to loop it. Speed 0.5 / 1 / 1.5 / 2. **STOP** returns to the pose selected in the Gallery menu.

Dances: Twerk, Belly Dance, Bellydancing, Dancing, Addiction, Patrik, Helltaker, Ghost Dance. They're available on Blythe, Celestina, DEMI, Elaisha, Fortune, FowChan, Huntress, Killi, Lily, Sova and Taron.

## How it works
Each heroine's gallery AnimBP (`<Name>GalleryAnimBlueprint_C`) feeds its `AnimSequence` variable into a SequencePlayer. The Lua swaps that variable for one of our clips, so the game's own physics and bone tweaks keep running. On each switch, physics is re-initialised one tick later.

The clips are built offline, one command per clip:

```
python tools/prep_char.py <Heroine>                         # once per heroine: skeleton, rest pose, gallery mesh from the paks
./build.sh <Heroine> "source/<dance>.fbx" A_<Heroine>_Dance_<Name>
```

`build.sh` works in four steps:
1. **Retarget in Blender** (`blender/retarget.py`):
   - matches world rotations, Mixamo bones to 3ds Max Biped;
   - scales hip motion by leg length;
   - centers the dance on the platform;
   - grounds the feet on the lowest mesh vertex.
2. **Import and cook in UE 4.22** (`ue/`), unversioned.
3. **Check the rest pose** against the gallery mesh with UModel.
4. **Remap and pack:** remaps the track tables to the game's bone order (`tools/remap_tracks.py`), then paks everything with UnrealPak.

MMD `.vmd` motions convert to a Mixamo-style FBX first with `blender/vmd/vmd2fbx.py`. An optional `source/<dance>.trim` holding `first last` source frames cuts walk-in or walk-out steps.

Game assets, motion sources and built clips aren't in this repo.

## Known issues
- Killi floats a little above the platform in some dances.
- Patrik ends in a crouch, so there is a small jump when it loops (about every 3 minutes).

## Notes
- Don't use UE4SS hot reload (Ctrl+R).
- Uninstall: delete the `GalleryDance` folder and the pak. No game files are changed.

## Credits and license
Motion credits are in [`mod/release/CREDITS.txt`](mod/release/CREDITS.txt). The motions are for non-commercial use only.

Code: MIT, by unkemptmagio.
