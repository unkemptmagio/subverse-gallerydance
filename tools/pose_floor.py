"""Lowest toe/foot joint height (cm) in a heroine's own gallery pose (frame 0 of export/<Name>/char.json gallery_pose_psa).
Our clips are grounded at 0 in Blender; if the game's gallery poses put the feet elsewhere, the platform is not at the
mesh origin for that heroine and the clip must be offset by this much.   usage: python tools/pose_floor.py [Name ...]"""
import json, struct, sys


def qmul(a, b):
    ax, ay, az, aw = a; bx, by, bz, bw = b
    return (aw*bx+ax*bw+ay*bz-az*by, aw*by-ax*bz+ay*bw+az*bx, aw*bz+ax*by-ay*bx+az*bw, aw*bw-ax*bx-ay*by-az*bz)


def rot(q, v):
    x, y, z, w = q; vx, vy, vz = v
    t = (2*(y*vz-z*vy), 2*(z*vx-x*vz), 2*(x*vy-y*vx))
    return (vx+w*t[0]+y*t[2]-z*t[1], vy+w*t[1]+z*t[0]-x*t[2], vz+w*t[2]+x*t[1]-y*t[0])


def floor(name):
    j = json.load(open(f'export/{name}/char.json')); n, P = j['names'], j['parents']
    d = open(j['gallery_pose_psa'], 'rb').read(); o = 0; keys = None
    while o < len(d):
        cid, _, sz, cnt = struct.unpack_from('<20sIII', d, o); o += 32
        if cid.startswith(b'ANIMKEYS'):
            keys = [struct.unpack_from('<3f4f', d, o + i * sz) for i in range(len(n))]  # frame 0
        o += sz * cnt
    gq, gp = [None] * len(n), [None] * len(n)
    for i, (px, py, pz, qx, qy, qz, qw) in enumerate(keys):
        q, p = (qx, -qy, qz, qw), (px, -py, pz)
        if i == 0:
            q = (-q[0], -q[1], -q[2], q[3])  # ActorX stores the root conjugated
        if P[i] < 0: gq[i], gp[i] = q, p
        else:
            gq[i] = qmul(gq[P[i]], q); gp[i] = tuple(a + b for a, b in zip(gp[P[i]], rot(gq[P[i]], p)))
    feet = [gp[i][2] for i, b in enumerate(n) if b.startswith(('Biped_Toe', 'Biped_Foot'))]
    return min(feet), gp[n.index('Biped_Pelvis')][2]


if __name__ == '__main__':
    for c in sys.argv[1:] or 'Blythe Celestina DEMI Elaisha Fortune FowChan Huntress Killi Lily Sova Taron'.split():
        f, p = floor(c)
        print(f'{c:10s} lowest foot joint {f:6.1f} cm   pelvis {p:6.1f} cm')
