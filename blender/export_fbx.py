# usage: blender -b <clip>.blend --python export_fbx.py -- <out.fbx>
# UE 4.22 ignores the FBX unit, and its import_uniform_scale bakes a scale into the clip's root bone (giant Lily),
# so write raw centimetres: scale rig + mesh x100, apply, and scale the location keys to match.
import bpy, sys
from bpy_extras import anim_utils

out = sys.argv[sys.argv.index('--') + 1]
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
objs = [o for o in bpy.data.objects if o.type in ('ARMATURE', 'MESH')]

ad = arm.animation_data
bag = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
n = 0
for fc in bag.fcurves:
    if fc.data_path.endswith('.location'):
        for kp in fc.keyframe_points:
            kp.co.y *= 100; kp.handle_left.y *= 100; kp.handle_right.y *= 100
        n += 1
print('scaled location curves', n)

bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
    if o.parent is None:
        o.scale = [s * 100 for s in o.scale]
bpy.context.view_layer.objects.active = arm
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={'ARMATURE', 'MESH'},
    add_leaf_bones=False, use_armature_deform_only=False, armature_nodetype='NULL',
    bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
    bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
    apply_scale_options='FBX_SCALE_ALL', primary_bone_axis='Y', secondary_bone_axis='X')
print('EXPORTED', out)
