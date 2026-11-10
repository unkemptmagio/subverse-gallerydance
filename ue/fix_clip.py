import sys, unreal
lib = unreal.EditorAssetLibrary
d, clip = '/Game/Mods/GalleryDance/' + sys.argv[2], sys.argv[1]
for extra in (clip, clip + '_PhysicsAsset'):
    a = unreal.load_asset(d + '/' + extra)
    if a and a.get_class().get_name() != 'AnimSequence':
        unreal.log_warning('DELETE %s %s' % (extra, lib.delete_asset(d + '/' + extra)))
if lib.does_asset_exist(d + '/' + clip + '_Anim'):
    unreal.log_warning('RENAME %s' % lib.rename_asset(d + '/' + clip + '_Anim', d + '/' + clip))
s = unreal.load_asset(d + '/' + clip)
unreal.log_warning('CLIP %s skeleton=%s frames=%s' % (s.get_class().get_name(), s.get_editor_property('skeleton').get_path_name(), s.get_editor_property('sequence_length')))
