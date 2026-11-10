# UE 4.22 commandlet: import a heroine's rebuilt skeleton at the game's skeleton path, then a dance clip on it.
# run: UE4Editor-Cmd.exe SubverseDance.uproject -run=pythonscript -script="import_clip.py <fbx> <clip name> <skeleton path>"
import sys
import unreal

fbx, clip, skel_full = sys.argv[1], sys.argv[2], sys.argv[3]   # e.g. /Game/StudioFow/Characters/DEMI/Meshes/SK_DEMI_SKEL
SKEL_DIR, SKEL = skel_full.rsplit('/', 1)                      # same path as the game's skeleton
CHAR = SKEL_DIR.split('/')[-2]
CLIP_DIR = '/Game/Mods/GalleryDance/' + CHAR
lib = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def task(dest, name, ui):
    t = unreal.AssetImportTask()
    t.set_editor_property('filename', fbx)
    t.set_editor_property('destination_path', dest)
    t.set_editor_property('destination_name', name)
    t.set_editor_property('automated', True)
    t.set_editor_property('replace_existing', True)
    t.set_editor_property('save', True)
    t.set_editor_property('options', ui)
    tools.import_asset_tasks([t])
    return list(t.get_editor_property('imported_object_paths'))


skel_path = SKEL_DIR + '/' + SKEL
if not lib.does_asset_exist(skel_path):
    ui = unreal.FbxImportUI()
    ui.set_editor_property('import_mesh', True)
    ui.set_editor_property('import_as_skeletal', True)
    ui.set_editor_property('import_animations', False)
    ui.set_editor_property('import_materials', False)
    ui.set_editor_property('import_textures', False)
    ui.set_editor_property('create_physics_asset', False)
    ui.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    print('MESH IMPORT', task(SKEL_DIR, 'SK_' + CHAR, ui))
    made = SKEL_DIR + '/SK_' + CHAR + '_Skeleton'
    print('RENAME skeleton', lib.rename_asset(made, skel_path))

skeleton = unreal.load_asset(skel_path)
ui = unreal.FbxImportUI()
ui.set_editor_property('import_mesh', False)
ui.set_editor_property('import_as_skeletal', True)
ui.set_editor_property('import_animations', True)
ui.set_editor_property('import_materials', False)
ui.set_editor_property('import_textures', False)
ui.set_editor_property('skeleton', skeleton)
ui.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_ANIMATION)
ui.set_editor_property('original_import_type', unreal.FBXImportType.FBXIT_ANIMATION)  # without this 4.22 imports a mesh
ad = ui.get_editor_property('anim_sequence_import_data')
ad.set_editor_property('import_bone_tracks', True)
ad.set_editor_property('animation_length', unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME)
paths = task(CLIP_DIR, clip, ui)
print('ANIM IMPORT', paths)
for p in paths:  # name the clip exactly, whatever take name the FBX carried
    base = p.split('.')[0]
    if base != CLIP_DIR + '/' + clip and not lib.does_asset_exist(CLIP_DIR + '/' + clip):
        lib.rename_asset(base, CLIP_DIR + '/' + clip)
seq = unreal.load_asset(CLIP_DIR + '/' + clip)
print('CLIP', seq.get_class().get_name() if seq else None, seq.get_editor_property('skeleton').get_path_name() if seq else None,
      )
lib.save_directory('/Game', only_if_is_dirty=False, recursive=True)
