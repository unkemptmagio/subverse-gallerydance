# Convert an MMD body motion (.vmd) into a Mixamo-style FBX (mixamorig: bones, baked FK, 30 fps) for retarget.py.
# No MMD model needed: a standard-proportioned MMD skeleton is built here, the VMD keys are sampled with their
# Bezier interpolation, leg IK (足ＩＫ / つま先ＩＫ) is solved analytically and everything is baked to FK.
# usage: blender -b --python vmd2fbx.py -- <in.vmd> <out.fbx> [preview_dir]
import bpy, sys, os, math
import numpy as np
from mathutils import Matrix, Vector, Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vmdparse import read_vmd

args = sys.argv[sys.argv.index('--') + 1:]
VMD, OUT = args[0], args[1]
PREV = args[2] if len(args) > 2 else None
U = 0.08  # metres per MMD unit (a ~20 unit model is ~1.6 m)


# ---------- 1. standard MMD skeleton, MMD coordinates (left-handed, Y up, model faces -Z, its left = +X)
def add(a, b, k=1.0):
    return tuple(a[i] + b[i] * k for i in range(3))


def norm(v):
    l = math.sqrt(sum(c * c for c in v)); return tuple(c / l for c in v)


BONES = [  # (name, parent, head) in parent-before-child order
    ('全ての親', None, (0, 0, 0)),
    ('センター', '全ての親', (0, 8.0, 0)),
    ('グルーブ', 'センター', (0, 8.2, 0)),
    ('腰', 'グルーブ', (0, 11.3, 0.5)),
    ('上半身', '腰', (0, 11.9, 0.3)),
    ('上半身2', '上半身', (0, 13.1, 0.2)),
    ('首', '上半身2', (0, 16.0, 0.45)),
    ('頭', '首', (0, 16.9, 0.25)),
    ('下半身', '腰', (0, 11.9, 0.3)),
]
EXTRA = {'Hips': (0, 11.2, 0.3), 'Spine2': (0, 14.5, 0.25), 'HeadTop': (0, 19.2, 0.0)}
FINGERS = {'Index': ('人指', 0.32, (0.5, 0.3, 0.25)), 'Middle': ('中指', 0.10, (0.55, 0.33, 0.27)),
           'Ring': ('薬指', -0.10, (0.5, 0.3, 0.25)), 'Pinky': ('小指', -0.28, (0.4, 0.25, 0.2))}
for side, sx in (('左', 1), ('右', -1)):
    M = lambda p: (sx * p[0], p[1], p[2])
    sh, ar, el, wr = (0.3, 15.6, 0.5), (1.35, 15.3, 0.55), (3.51, 13.68, 0.6), (5.51, 12.17, 0.55)  # arms ~37 deg down
    u = norm((wr[0] - el[0], wr[1] - el[1], 0)); f = (0, 0, -1); n = (u[1], -u[0], 0)  # f front, n palm normal (down)
    BONES += [
        (side + '肩P', '上半身2', M(sh)), (side + '肩', side + '肩P', M(sh)),
        (side + '肩C', side + '肩', M(ar)), (side + '腕', side + '肩C', M(ar)),
        (side + '腕捩', side + '腕', M(tuple((ar[i] + el[i]) / 2 for i in range(3)))),
        (side + 'ひじ', side + '腕捩', M(el)),
        (side + '手捩', side + 'ひじ', M(tuple((el[i] + wr[i]) / 2 for i in range(3)))),
        (side + '手首', side + '手捩', M(wr)),
    ]
    for fk, (jp, s, lens) in FINGERS.items():
        p = add(add(wr, u, 1.0 if fk != 'Pinky' else 0.92), f, s)
        par = side + '手首'
        for i, l in enumerate(lens):
            nm = side + jp + '１２３'[i]
            BONES.append((nm, par, M(p))); par = nm; p = add(p, u, l)
        BONES.append((side + jp + '先', par, M(p)))
    dt = norm(add(add(tuple(c * 0.6 for c in u), f, 0.7), n, 0.3))
    p = add(add(add(wr, u, 0.15), f, 0.2), n, 0.1); par = side + '手首'
    for i, l in enumerate((0.45, 0.4, 0.3)):
        nm = side + '親指' + '０１２'[i]
        BONES.append((nm, par, M(p))); par = nm; p = add(p, dt, l)
    BONES.append((side + '親指先', par, M(p)))
    hip, knee, ank, ball, toe = (0.95, 10.4, 0.25), (1.05, 5.9, -0.05), (1.15, 1.25, 0.6), (1.18, 0.3, -0.8), (1.2, 0.0, -1.5)
    BONES += [
        ('腰キャンセル' + side, '下半身', M(hip)), (side + '足', '腰キャンセル' + side, M(hip)),
        (side + 'ひざ', side + '足', M(knee)), (side + '足首', side + 'ひざ', M(ank)),
        (side + '足先EX', side + '足首', M(ball)), (side + 'つま先', side + '足首', M(toe)),
        (side + '足IK親', '全ての親', M((ank[0], 0, ank[2]))), (side + '足ＩＫ', side + '足IK親', M(ank)),
        (side + 'つま先ＩＫ', side + '足ＩＫ', M(toe)),
    ]
GRANT = {'腰キャンセル左': '腰', '腰キャンセル右': '腰', '左肩C': '左肩P', '右肩C': '右肩P'}  # rotation grant x -1


def to_bl(p):  # MMD position -> Blender metres (swap Y/Z flips handedness; MMD front -Z -> Blender front -Y)
    return Vector((p[0], p[2], p[1])) * U


PARENT = {n: p for n, p, _ in BONES}
REST = {n: to_bl(h) for n, _, h in BONES}
for k, h in EXTRA.items():
    REST[k] = to_bl(h)
ORDER = [n for n, _, _ in BONES]

# ---------- 2. sample the VMD at every frame (Bezier interpolation, slerp)
V = read_vmd(VMD)['bones']
F = max(k[-1][0] for k in V.values()) + 1
print('VMD frames', F, 'tracks', len(V))


def bez(s, x1, y1, x2, y2):
    lo, hi = np.zeros_like(s), np.ones_like(s)
    for _ in range(22):
        t = (lo + hi) / 2
        x = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3
        m = x < s
        lo, hi = np.where(m, t, lo), np.where(m, hi, t)
    t = (lo + hi) / 2
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3


def slerp(a, b, t):
    d = (a * b).sum(1)
    b = np.where(d[:, None] < 0, -b, b); d = np.abs(d)
    om = np.arccos(np.clip(d, -1, 1)); so = np.sin(om); sm = so < 1e-6; so = np.where(sm, 1, so)
    k0 = np.where(sm, 1 - t, np.sin((1 - t) * om) / so); k1 = np.where(sm, t, np.sin(t * om) / so)
    r = k0[:, None] * a + k1[:, None] * b
    return r / np.linalg.norm(r, axis=1)[:, None]


def sample(keys):
    fr = np.array([k[0] for k in keys], float)
    P = np.array([k[1] for k in keys], float); Q = np.array([k[2] for k in keys], float)
    I = np.array([list(k[3]) for k in keys], float) / 127.0
    fs = np.arange(F, dtype=float)
    if len(keys) == 1:
        pos, quat = np.repeat(P, F, 0), np.repeat(Q, F, 0)
    else:
        i1 = np.clip(np.searchsorted(fr, fs, side='right'), 1, len(keys) - 1); i0 = i1 - 1
        s = np.clip((fs - fr[i0]) / np.maximum(fr[i1] - fr[i0], 1), 0, 1)
        ip = I[i1]
        pos = np.empty((F, 3))
        for c in range(3):
            w = bez(s, ip[:, c], ip[:, 4 + c], ip[:, 8 + c], ip[:, 12 + c])
            pos[:, c] = P[i0, c] + (P[i1, c] - P[i0, c]) * w
        quat = slerp(Q[i0], Q[i1], bez(s, ip[:, 3], ip[:, 7], ip[:, 11], ip[:, 15]))
    # -> Blender: position (x, z, y); rotation: reflect the axis, (w, -x, -z, -y)
    posb = np.stack([pos[:, 0], pos[:, 2], pos[:, 1]], 1) * U
    qb = np.stack([quat[:, 3], -quat[:, 0], -quat[:, 2], -quat[:, 1]], 1)
    return posb, qb


TR = {n: sample(V[n]) for n in ORDER if n in V}
missing = [n for n in ORDER if n not in V and not n.endswith('先')]
print('bones without keys (identity):', missing)

# ---------- 3. FK + IK per frame
QI = Quaternion()


def solve_leg(side, Pw, Rw, LQ):
    th, kn, an, ex, toe = side + '足', side + 'ひざ', side + '足首', side + '足先EX', side + 'つま先'
    H, Rt = Pw[th], Rw[th]
    a, b = REST[kn] - REST[th], REST[an] - REST[kn]
    T = Pw[side + '足ＩＫ']
    K = ((T - H).length_squared - a.length_squared - b.length_squared) / 2 - a.x * b.x
    A, B = a.y * b.y + a.z * b.z, a.z * b.y - a.y * b.z
    R = math.hypot(A, B); phi = math.atan2(B, A); al = math.acos(max(-1, min(1, K / R)))
    lo = math.radians(0.5)
    cands = [math.atan2(math.sin(c), math.cos(c)) for c in (phi + al, phi - al)]
    valid = [c for c in cands if lo <= c <= math.pi]
    tk = min(valid) if valid else lo  # knee bends about its X axis only, like MMD's knee limit
    Rk = Quaternion((1, 0, 0), tk)
    v = Rt @ (a + Rk @ b)
    Rt = v.rotation_difference(T - H) @ Rt
    Rw[th] = Rt; Rw[kn] = Rt @ Rk; Pw[kn] = H + Rt @ a
    Pw[an] = Pw[kn] + Rw[kn] @ b
    Ra = Rw[kn] @ LQ[an]
    tt = Pw[side + 'つま先ＩＫ'] - Pw[an]
    if tt.length > 1e-6:
        Ra = (Ra @ (REST[toe] - REST[an])).rotation_difference(tt) @ Ra
    Rw[an] = Ra
    for c in (ex, toe):
        Rw[c] = Ra @ LQ[c]; Pw[c] = Pw[an] + Ra @ (REST[c] - REST[an])


def frame(f):
    LQ, LP = {}, {}
    for n in ORDER:
        if n in TR:
            p, q = TR[n]; LP[n] = Vector(p[f]); LQ[n] = Quaternion(q[f])
        else:
            LP[n] = Vector(); LQ[n] = QI.copy()
    for n, src in GRANT.items():
        LQ[n] = LQ[src].inverted()
    Pw, Rw = {}, {}
    for n in ORDER:
        par = PARENT[n]
        if par is None:
            Pw[n] = REST[n] + LP[n]; Rw[n] = LQ[n]
        else:
            Pw[n] = Pw[par] + Rw[par] @ (REST[n] - REST[par] + LP[n]); Rw[n] = Rw[par] @ LQ[n]
    for side in '左右':
        solve_leg(side, Pw, Rw, LQ)
    return Pw, Rw, LQ


# ---------- 4. Mixamo armature
OUTB = {}  # mixamo name -> (parent, head, tail, driver)
def ob(n, par, head, tail, drv):
    OUTB[n] = (par, head, tail, drv)


ob('Hips', None, REST['Hips'], REST['上半身'], '下半身')
ob('Spine', 'Hips', REST['上半身'], REST['上半身2'], '上半身')
ob('Spine1', 'Spine', REST['上半身2'], REST['Spine2'], 'SPINE1')
ob('Spine2', 'Spine1', REST['Spine2'], REST['首'], '上半身2')
ob('Neck', 'Spine2', REST['首'], REST['頭'], '首')
ob('Head', 'Neck', REST['頭'], REST['HeadTop'], '頭')
for side, S in (('左', 'Left'), ('右', 'Right')):
    j = lambda x: REST[side + x]
    ob(S + 'Shoulder', 'Spine2', j('肩'), j('腕'), side + '肩')
    ob(S + 'Arm', S + 'Shoulder', j('腕'), j('ひじ'), side + '腕')
    ob(S + 'ForeArm', S + 'Arm', j('ひじ'), j('手首'), side + 'ひじ')
    ob(S + 'Hand', S + 'ForeArm', j('手首'), j('中指１'), side + '手首')
    for fk, (jp, _, _) in list(FINGERS.items()) + [('Thumb', ('親指', 0, 0))]:
        names = [side + jp + c for c in ('０１２' if fk == 'Thumb' else '１２３')] + [side + jp + '先']
        par = S + 'Hand'
        for i in range(3):
            ob(f'{S}Hand{fk}{i + 1}', par, REST[names[i]], REST[names[i + 1]], names[i]); par = f'{S}Hand{fk}{i + 1}'
    ob(S + 'UpLeg', 'Hips', j('足'), j('ひざ'), side + '足')
    ob(S + 'Leg', S + 'UpLeg', j('ひざ'), j('足首'), side + 'ひざ')
    ob(S + 'Foot', S + 'Leg', j('足首'), j('足先EX'), side + '足首')
    ob(S + 'ToeBase', S + 'Foot', j('足先EX'), j('つま先'), side + '足先EX')

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.fps = 30
ad = bpy.data.armatures.new('Armature')
A = bpy.data.objects.new('Armature', ad)
scn.collection.objects.link(A)
bpy.context.view_layer.objects.active = A
bpy.ops.object.mode_set(mode='EDIT')
for n, (par, h, t, _) in OUTB.items():
    e = ad.edit_bones.new('mixamorig:' + n); e.head = h; e.tail = t; e.roll = 0
for n, (par, h, t, _) in OUTB.items():
    if par:
        ad.edit_bones['mixamorig:' + n].parent = ad.edit_bones['mixamorig:' + par]
bpy.ops.object.mode_set(mode='OBJECT')
RB = {n: ad.bones['mixamorig:' + n].matrix_local.to_quaternion() for n in OUTB}

# ---------- 5. bake every frame into arrays, then write fcurves in one go
names = list(OUTB)
rot = np.zeros((F, len(names), 4)); loc = np.zeros((F, 3))
for f in range(F):
    Pw, Rw, LQ = frame(f)
    D = {}
    for i, n in enumerate(names):
        par, h, t, drv = OUTB[n]
        D[n] = (Rw['上半身'] @ Quaternion().slerp(LQ['上半身2'], 0.5)) if drv == 'SPINE1' else Rw[drv]
        Rp = D[par] if par else QI
        q = RB[n].inverted() @ Rp.inverted() @ D[n] @ RB[n]
        q.normalize()
        if f and np.dot(rot[f - 1, i], q) < 0:
            q.negate()
        rot[f, i] = q
    hw = Pw['下半身'] + Rw['下半身'] @ (REST['Hips'] - REST['下半身'])
    loc[f] = RB['Hips'].inverted() @ (hw - REST['Hips'])
    if f % 1000 == 0:
        print('baked', f)

A.animation_data_create()
act = bpy.data.actions.new('Addiction')
A.animation_data.action = act
for n in names:
    pb = A.pose.bones['mixamorig:' + n]; pb.rotation_mode = 'QUATERNION'
    pb.keyframe_insert('rotation_quaternion', frame=0)
    if n == 'Hips':
        pb.keyframe_insert('location', frame=0)
from bpy_extras import anim_utils
bag = anim_utils.action_get_channelbag_for_slot(act, A.animation_data.action_slot)
fs = np.arange(F, dtype=float)
for fc in bag.fcurves:
    n = fc.data_path.split('"')[1][len('mixamorig:'):]
    vals = rot[:, names.index(n), fc.array_index] if fc.data_path.endswith('rotation_quaternion') else loc[:, fc.array_index]
    fc.keyframe_points.add(F - 1)
    fc.keyframe_points.foreach_set('co', np.stack([fs, vals], 1).ravel().tolist())
    fc.keyframe_points.foreach_set('interpolation', [1] * F)  # LINEAR
    fc.update()
scn.frame_start, scn.frame_end = 0, F - 1
print('keyed frames 0..', F - 1, 'bones', len(names))

# sanity numbers: lowest foot point / hip height
for f in (0, F // 4, F // 2):
    scn.frame_set(f)
    zs = [(A.matrix_world @ A.pose.bones['mixamorig:' + b].tail).z for b in ('LeftToeBase', 'RightToeBase')]
    zf = [(A.matrix_world @ A.pose.bones['mixamorig:' + b].head).z for b in ('LeftFoot', 'RightFoot')]
    print(f'frame {f}: toe tips z {zs[0]:.3f} {zs[1]:.3f}  ankles z {zf[0]:.3f} {zf[1]:.3f}  hips z',
          round((A.matrix_world @ A.pose.bones['mixamorig:Hips'].head).z, 3))

# ---------- 6. stick-figure mesh skinned to the rig. Exported too: without a skinned mesh the FBX has no bind pose and
# Blender's importer takes the export-time POSE as the rest pose, which breaks retarget.py's rest alignment (roll).
if True:
    verts, faces, groups = [], [], []
    for n in names:
        b = ad.bones['mixamorig:' + n]
        h, t = b.head_local, b.tail_local
        r = 0.012 if ('Hand' in n and n[-1].isdigit()) or 'Toe' in n else 0.03
        if n in ('Hips', 'Spine', 'Spine1', 'Spine2'): r = 0.07
        if n == 'Head': r = 0.08
        ax = (t - h).normalized(); x = ax.orthogonal().normalized(); y = ax.cross(x)
        base = len(verts)
        for e in (h, t):
            for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                verts.append(e + (x * sx + y * sy) * r)
        faces += [(base + a, base + b_, base + c, base + d) for a, b_, c, d in
                  ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))]
        groups.append((n, range(base, base + 8)))
    me = bpy.data.meshes.new('stick'); me.from_pydata([tuple(v) for v in verts], [], faces)
    st = bpy.data.objects.new('stick', me); scn.collection.objects.link(st)
    for n, idx in groups:
        st.vertex_groups.new(name='mixamorig:' + n).add(list(idx), 1.0, 'REPLACE')
    st.modifiers.new('arm', 'ARMATURE').object = A

# ---------- 7. export (armature + skinned stick mesh, like a Mixamo download with skin)
bpy.ops.object.select_all(action='DESELECT')
A.select_set(True); st.select_set(True); bpy.context.view_layer.objects.active = A
bpy.ops.export_scene.fbx(filepath=OUT, use_selection=True, object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False,
                         armature_nodetype='NULL', bake_anim=True, bake_anim_use_all_actions=False,
                         bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True,
                         bake_anim_simplify_factor=0.0, primary_bone_axis='Y', secondary_bone_axis='X')
print('EXPORTED', OUT)

# ---------- 8. optional preview, front + side views
if PREV:
    os.makedirs(PREV, exist_ok=True)
    bpy.ops.mesh.primitive_plane_add(size=3)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scn.collection.objects.link(cam); scn.camera = cam
    cam.data.lens = 35
    scn.render.engine = 'BLENDER_WORKBENCH'
    scn.render.resolution_x, scn.render.resolution_y = 300, 420
    frames = [int(x) for x in np.linspace(0, F - 1, 8)]
    if len(args) > 3:
        frames = [int(x) for x in args[3].split(',')]
    for view, loc_, rot_ in (('front', (0, -3.6, 0.8), (math.pi / 2, 0, 0)), ('side', (3.6, 0, 0.8), (math.pi / 2, 0, math.pi / 2))):
        cam.location = loc_; cam.rotation_euler = rot_
        for f in frames:
            scn.frame_set(f)
            scn.render.filepath = os.path.join(PREV, f'{view}_{f:05d}.png')
            bpy.ops.render.render(write_still=True)
    print('PREVIEW', PREV, frames)
