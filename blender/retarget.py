# Retarget a Mixamo clip onto a heroine's full game skeleton (names/parents/rest pose from export/<Name>/char.json).
# usage: blender -b --python retarget.py -- <workspace> <Name> <source.fbx> <out_name>
import bpy, sys, json, os
from mathutils import Matrix, Vector, Quaternion

W, CHAR, SRC, OUT = sys.argv[sys.argv.index('--') + 1:][:4]
C = json.load(open(W + f'/export/{CHAR}/char.json'))


MAP = {'Hips': 'Biped_Pelvis', 'Spine': 'Biped_Spine1', 'Spine1': 'Biped_Spine2', 'Spine2': 'Biped_Spine3',
       'Neck': 'Biped_Neck', 'Head': 'Biped_Head'}
for s, t in (('Left', 'L'), ('Right', 'R')):
    MAP.update({s + 'Shoulder': 'Biped_Clavicle_' + t, s + 'Arm': 'Biped_UpperArm_' + t, s + 'ForeArm': 'Biped_LowerArm_' + t,
                s + 'Hand': 'Biped_Hand_' + t, s + 'UpLeg': 'Biped_Thigh_' + t, s + 'Leg': 'Biped_Calf_' + t,
                s + 'Foot': 'Biped_Foot_' + t, s + 'ToeBase': 'Biped_Toe_Base_' + t})
    for f, k in (('Thumb', 0), ('Index', 1), ('Middle', 2), ('Ring', 3), ('Pinky', 4)):
        MAP[f'{s}Hand{f}1'] = f'Biped_Finger_{k}_{t}'
        MAP[f'{s}Hand{f}2'] = f'Biped_Finger_{k}1_{t}'
        MAP[f'{s}Hand{f}3'] = f'Biped_Finger_{k}2_{t}'

# the mapped child that defines each bone's aim direction
AIM = {'Biped_Pelvis': 'Biped_Spine1', 'Biped_Spine1': 'Biped_Spine2', 'Biped_Spine2': 'Biped_Spine3',
       'Biped_Spine3': 'Biped_Neck', 'Biped_Neck': 'Biped_Head'}
for t in 'LR':
    AIM.update({f'Biped_Clavicle_{t}': f'Biped_UpperArm_{t}', f'Biped_UpperArm_{t}': f'Biped_LowerArm_{t}',
                f'Biped_LowerArm_{t}': f'Biped_Hand_{t}', f'Biped_Hand_{t}': f'Biped_Finger_2_{t}',
                f'Biped_Thigh_{t}': f'Biped_Calf_{t}', f'Biped_Calf_{t}': f'Biped_Foot_{t}',
                f'Biped_Foot_{t}': f'Biped_Toe_Base_{t}'})
    for k in range(5):
        AIM[f'Biped_Finger_{k}_{t}'] = f'Biped_Finger_{k}1_{t}'
        AIM[f'Biped_Finger_{k}1_{t}'] = f'Biped_Finger_{k}2_{t}'

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=C['gallery_mesh_gltf'])
G = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == G)
for o in list(bpy.data.objects):
    if o not in (G, mesh):
        bpy.data.objects.remove(o)

# 1) game skeleton. Rest pose = the cooked SKEL ref pose (equals the gallery mesh rest), NOT the glTF bones:
# Blender's glTF importer re-aims bones, and clip rotations are stored relative to each bone's rest frame.
names, parents = C['names'], C['parents']
gq, gp = [], []
for i, r in enumerate(C['ref']):
    q = Quaternion((r[3], r[0], r[1], r[2])); p = Vector(r[4:7])
    if parents[i] < 0:
        gq.append(q); gp.append(p)
    else:
        gq.append(gq[parents[i]] @ q); gp.append(gp[parents[i]] + gq[parents[i]] @ p)
arm = bpy.data.armatures.new(C['root'])
T = bpy.data.objects.new('Armature', arm)
scn.collection.objects.link(T)
bpy.context.view_layer.objects.active = T
bpy.ops.object.mode_set(mode='EDIT')
eb = []
for i, name in enumerate(names):
    e = arm.edit_bones.new(name)
    q, p = gq[i], gp[i]
    # UE (left-handed, cm) -> Blender: mirror Y; for rotations S R S, i.e. quat (w, -x, y, -z)
    m = Matrix.Translation(Vector((p.x, -p.y, p.z)) / 100) @ Quaternion((q.w, -q.x, q.y, -q.z)).to_matrix().to_4x4()
    e.head = m.translation; e.tail = m.translation + m.to_3x3().col[1] * 0.05
    e.matrix = m
    if parents[i] >= 0:
        e.parent = eb[parents[i]]
    eb.append(e)
bpy.ops.object.mode_set(mode='OBJECT')
# order can't match (game order isn't a tree walk); the cooked clip's track table is remapped by name afterwards
assert sorted(b.name for b in arm.bones) == sorted(names), 'bone set changed'
mesh.parent = T
mesh.modifiers[0].object = T
bpy.data.objects.remove(G)

# 2) source clip, turned to face the same way as Lily
bpy.ops.import_scene.fbx(filepath=SRC)
S = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o != T)
pre = next(b.name[:-4] for b in S.data.bones if b.name.endswith('Hips'))  # 'mixamorig:' / 'mixamorig1:' ...


def fwd(ob, left_hip, right_hip):
    # facing from the hip line, not the feet: some heroines (DEMI) stand with feet splayed ~30 deg
    m = ob.matrix_world
    r = (m @ ob.data.bones[right_hip].head_local) - (m @ ob.data.bones[left_hip].head_local)
    r.z = 0
    return Vector((0, 0, 1)).cross(r.normalized())  # right x up would point backward (only matters for the preview camera)


ft, fs = fwd(T, 'Biped_Thigh_L', 'Biped_Thigh_R'), fwd(S, pre + 'LeftUpLeg', pre + 'RightUpLeg')
S.rotation_mode = 'QUATERNION'
S.rotation_quaternion = fs.rotation_difference(ft) @ S.rotation_quaternion
bpy.context.view_layer.update()
pairs = {MAP[k]: pre + k for k in MAP if pre + k in S.data.bones and MAP[k] in arm.bones}
print('mapped bones', len(pairs), 'facing turn deg', round(fs.angle(ft) * 57.3, 1))

act = S.animation_data.action
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
TRIM = os.path.splitext(SRC)[0] + '.trim'  # optional "first last" source frames, e.g. to cut walk-in/walk-out steps
if os.path.exists(TRIM):
    f0, f1 = map(int, open(TRIM).read().split())
    print('trimmed to frames', f0, f1)
Srest = {s: S.matrix_world @ S.data.bones[s].matrix_local for s in pairs.values()}
Trest = {b.name: b.matrix_local.copy() for b in arm.bones}


def aimdir(rest, n, child):
    v = (rest[child].translation - rest[n].translation) if child else rest[n].to_3x3().col[1]
    return v.normalized()


# rest alignment: rotate Lily's rest so each bone aims like the source rest (A-pose vs T-pose)
Tm = {}
for t, s in pairs.items():
    c = AIM.get(t) if AIM.get(t) in pairs else None
    dt = aimdir(Trest, t, c)
    ds = aimdir(Srest, s, pairs[c] if c else None)
    Tm[t] = dt.rotation_difference(ds).to_matrix() @ Trest[t].to_3x3().normalized()
# Hip motion scaled by LEG LENGTH (Lily's rest has legs spread ~50 deg, so her rest hip height understates it),
# then offset so both ankles sit at the same height above the floor (z=0 in both rigs).
def leg(rest, th, ca, fo):
    return (rest[ca].translation - rest[th].translation).length + (rest[fo].translation - rest[ca].translation).length
k = leg(Trest, 'Biped_Thigh_L', 'Biped_Calf_L', 'Biped_Foot_L') / leg(Srest, pre + 'LeftUpLeg', pre + 'LeftLeg', pre + 'LeftFoot')
ankle = Trest['Biped_Foot_L'].translation.z - Srest[pre + 'LeftFoot'].translation.z * k
print('leg scale', round(k, 3), 'ankle offset cm', round(ankle * 100, 1))

# 3) bake: world rotations from the source, Lily's own bone lengths, hip motion scaled to her height
T.animation_data_create()
T.animation_data.action = bpy.data.actions.new(OUT)


def bake(ankle):
    mesh.hide_viewport = True  # ponytail: re-skinning the mesh on every frame_set was most of the bake time
    hs = []  # center the dance on the platform: median hip XY over the clip goes to the origin
    for f in range(f0, f1 + 1, 10):
        scn.frame_set(f)
        hs.append((S.matrix_world @ S.pose.bones[pairs['Biped_Pelvis']].matrix).translation)
    C0 = Vector((sorted(h.x for h in hs)[len(hs) // 2], sorted(h.y for h in hs)[len(hs) // 2], 0))
    print('centering hips by cm', round(C0.x * 100, 1), round(C0.y * 100, 1))
    order = [b.name for b in arm.bones]
    for f in range(f0, f1 + 1):
        scn.frame_set(f)
        M = {}
        for n in order:
            b = arm.bones[n]
            P = M[b.parent.name] if b.parent else Matrix()
            rel = (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent else b.matrix_local
            base = P @ rel
            if n in pairs:
                Ws = S.matrix_world @ S.pose.bones[pairs[n]].matrix
                rot = Ws.to_3x3().normalized() @ Srest[pairs[n]].to_3x3().normalized().inverted() @ Tm[n]
                loc = ((Ws.translation - C0) * k + Vector((0, 0, ankle))) if n == 'Biped_Pelvis' else base.translation
                want = Matrix.Translation(loc) @ rot.to_4x4()
                pb = T.pose.bones[n]
                pb.rotation_mode = 'QUATERNION'
                basis = base.inverted() @ want
                pb.rotation_quaternion = basis.to_quaternion()
                pb.keyframe_insert('rotation_quaternion', frame=f)
                if n == 'Biped_Pelvis':
                    pb.location = basis.translation
                    pb.keyframe_insert('location', frame=f)
                M[n] = want
            else:
                M[n] = base
    mesh.hide_viewport = False


def shift(dz):  # same result as re-baking with ankle+dz: only the pelvis location keys move (ancestors are static)
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    d = arm.bones['Biped_Pelvis'].matrix_local.to_3x3().inverted() @ Vector((0, 0, dz))
    cb = action_get_channelbag_for_slot(T.animation_data.action, T.animation_data.action_slot)
    for fc in cb.fcurves:
        if fc.data_path == 'pose.bones["Biped_Pelvis"].location':
            for kp in fc.keyframe_points:
                for v in (kp.co, kp.handle_left, kp.handle_right):
                    v.y += d[fc.array_index]
            fc.update()


def lowest():  # lowest mesh vertex (m) over the clip, sampled every 10 frames
    lo = 1e9
    for f in range(f0, f1 + 1, 10):
        scn.frame_set(f)
        me = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        lo = min(lo, min(v.co.z for v in me.vertices))
    return lo


bake(ankle)
lo = lowest()
print(f'GROUND first pass lowest {lo * 100:.1f} cm -> shifting hips {-lo * 100:.1f} cm')
shift(-lo)
print(f'GROUND after: lowest {lowest() * 100:.1f} cm')
if f0 != 1:  # clip starts at frame 1 (trimmed sources)
    from bpy_extras.anim_utils import action_get_channelbag_for_slot
    for fc in action_get_channelbag_for_slot(T.animation_data.action, T.animation_data.action_slot).fcurves:
        for kp in fc.keyframe_points:
            for v in (kp.co, kp.handle_left, kp.handle_right):
                v.x -= f0 - 1
        fc.update()
    f0, f1 = 1, f1 - f0 + 1
scn.frame_start, scn.frame_end = f0, f1
scn.render.fps = 30
bpy.data.objects.remove(S)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o != mesh:
        bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=W + f'/blender/{OUT}.blend')

# 4) preview stills from the front
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
scn.collection.objects.link(cam)
scn.camera = cam
cam.location = ft * 4.2 + Vector((0, 0, 1.0))
cam.rotation_euler = (-ft).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 40
scn.render.engine = 'BLENDER_WORKBENCH'
scn.render.resolution_x, scn.render.resolution_y = 480, 640
for i, f in enumerate((f0, f0 + (f1 - f0) // 4, f0 + (f1 - f0) // 2, f0 + 3 * (f1 - f0) // 4)):
    scn.frame_set(f)
    me = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    print(f'FLOOR frame {f}: lowest vertex {min(v.co.z for v in me.vertices) * 100:.1f} cm')
    scn.render.filepath = W + f'/blender/preview_{OUT}_{i}.png'
    bpy.ops.render.render(write_still=True)
print('DONE frames', f0, f1)
