# UE 4.22 commandlet, after import_clip.py: drop the mesh + physics asset an animation import still creates, name the clips.
# run: ... -script="fix_clip.py <Char> <clip> [<clip> ...]"
import sys, unreal
lib = unreal.EditorAssetLibrary
d = '/Game/Mods/GalleryDance/' + sys.argv[1]
for clip in sys.argv[2:]:
    for extra in (clip, clip + '_PhysicsAsset'):
        a = unreal.load_asset(d + '/' + extra)
        if a and a.get_class().get_name() != 'AnimSequence':
            unreal.log_warning('DELETE %s %s' % (extra, lib.delete_asset(d + '/' + extra)))
    if lib.does_asset_exist(d + '/' + clip + '_Anim'):
        unreal.log_warning('RENAME %s' % lib.rename_asset(d + '/' + clip + '_Anim', d + '/' + clip))
    s = unreal.load_asset(d + '/' + clip)
    unreal.log_warning('CLIP %s %s length=%s' % (clip, s.get_class().get_name() if s else None,
                                                s.get_editor_property('sequence_length') if s else None))
