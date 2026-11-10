"""One-time per heroine: pull everything the dance pipeline needs out of the game paks.

usage: python tools/prep_char.py <Name>          (Name = folder under StudioFow/Characters, e.g. Lily, DEMI)
writes export/<Name>/char.json : skeleton path, gallery mesh/pose paths, bone names in game order, real parents, ref pose
and exports (UModel) the gallery mesh as glTF + PSK and one gallery pose as PSA into export/Game/...
"""
import json
import os
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
PAKS = r'D:\Games\R18\Subverse\Subverse\Content\Paks'
MOUNT = '../../../Subverse/Content/'


def index():
    """{asset path under Content: pak file} from the pre-built listing (tools/all.txt, made by paklist.py)"""
    out = {}
    for line in open(os.path.join(HERE, 'all.txt'), encoding='latin-1'):
        pak, path = line.rstrip('\n').split(' ', 1)
        if path.startswith(MOUNT):
            out[path[len(MOUNT):]] = pak
    return out


def rawread(pak, want):
    def rs(f):
        n = struct.unpack('<i', f.read(4))[0]
        return f.read(-n * 2).decode('utf-16-le') if n < 0 else f.read(n).decode('latin-1')
    f = open(os.path.join(PAKS, pak), 'rb'); f.seek(-172, 2); t = f.read()
    f.seek(struct.unpack('<Q', t[8:16])[0]); mount = rs(f).rstrip('\0'); cnt = struct.unpack('<i', f.read(4))[0]
    for _ in range(cnt):
        name = rs(f).rstrip('\0'); o, s, u, cm = struct.unpack('<QQQB', f.read(25)); f.read(20)
        blocks = [struct.unpack('<QQ', f.read(16)) for _ in range(struct.unpack('<i', f.read(4))[0])] if cm else []
        f.read(5)
        if (mount + name).endswith(want):
            data = b''
            for a, b in blocks:
                f.seek(o + a); data += zlib.decompress(f.read(b - a))
            if not cm:
                f.seek(o + 53); data = f.read(u)
            return data
    raise SystemExit(f'{want} not found in {pak}')


def umodel(pkg, gltf=False):
    cmd = [os.path.join(HERE, 'umodel', 'umodel_64.exe'), '-path=' + PAKS, '-game=ue4.22', '-export',
           '-out=' + os.path.join(WS, 'export')] + (['-gltf'] if gltf else []) + [pkg]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def psa_names(p):
    d = open(p, 'rb').read(); o = 0
    while o < len(d):
        cid, _, sz, n = struct.unpack_from('<20sIII', d, o); o += 32
        if cid.startswith(b'BONENAMES'):
            return [d[o + i * sz:o + i * sz + 64].split(b'\0')[0].decode() for i in range(n)]
        o += sz * n


def main(name):
    idx = index()
    low = name.lower()
    # gallery pose first (folder casing differs per heroine; names are *_GP_* or *GP)
    poses = sorted(p for p in idx if p.lower().startswith(f'artassets/gallery/animations/{low}/') and p.endswith('.uasset')
                   and 'gp' in p.lower().rsplit('/', 1)[1])
    assert poses, f'no gallery poses for {name}'
    pose = poses[0]
    # the skeleton the gallery really uses = the one the gallery pose imports
    import re
    hdr = rawread(idx[pose], pose)
    sk = sorted(set(m.decode() for m in re.findall(rb'/Game/[A-Za-z0-9_/]+_SKEL', hdr)))
    assert sk, f'no skeleton import in {pose}'
    skel = sk[0][len('/Game/'):] + '.uexp'
    assert skel in idx, f'no skeleton {skel}'
    # gallery mesh, else the heroine's regular nude mesh (FowChan's gallery has none of its own)
    meshes = sorted(p for p in idx if p.lower().startswith(f'artassets/gallery/characters/{low}/meshes/sk_')
                    and p.endswith('.uasset') and '_phys' not in p.lower() and '_skel' not in p.lower())
    if not meshes:
        sdir = skel.rsplit('/', 1)[0].lower() + '/'
        meshes = sorted(p for p in idx if p.lower().startswith(sdir + 'sk_') and p.endswith('.uasset')
                        and '_phys' not in p.lower() and '_skel' not in p.lower())
    nude = [m for m in meshes if 'nude' in m.lower()]
    mesh = min(nude or meshes, key=len)  # shortest name = the base variant
    pkg = lambda p: '/Game/' + p[:-len('.uasset')]
    print('skeleton', skel, '| mesh', mesh, '| pose', pose)

    umodel(pkg(mesh), gltf=True); umodel(pkg(mesh)); umodel(pkg(pose))
    names = psa_names(os.path.join(WS, 'export', 'Game', pose[:-len('.uasset')] + '.psa'))
    n = len(names)

    d = rawread(idx[skel], skel)
    for o in range(len(d) - 16):  # FReferenceSkeleton: int32 N, N x (FName 8 bytes, int32 parent), int32 N, N x FTransform
        if struct.unpack_from('<i', d, o)[0] == n and struct.unpack_from('<i', d, o + 12)[0] == -1:
            par = [struct.unpack_from('<i', d, o + 4 + 12 * i + 8)[0] for i in range(n)]
            if all(-1 <= p < i for i, p in enumerate(par)):
                break
    else:
        raise SystemExit('bone table not found')
    r = o + 4 + 12 * n
    assert struct.unpack_from('<i', d, r)[0] == n, 'ref pose count mismatch'
    ref = [list(struct.unpack_from('<10f', d, r + 4 + 40 * i)) for i in range(n)]

    out = os.path.join(WS, 'export', name)
    os.makedirs(out, exist_ok=True)
    meshbase = os.path.join(WS, 'export', 'Game', mesh[:-len('.uasset')])
    # the game skins against the GALLERY MESH rest, which can differ from the skeleton (tiptoe feet on
    # Celestina/Elaisha/Huntress/Sova) -> take rest rot/pos from the mesh PSK wherever it has the bone
    psk = next(meshbase + e for e in ('.psk', '.pskx') if os.path.exists(meshbase + e))
    d2 = open(psk, 'rb').read(); o = 0
    while o < len(d2):
        cid, _, sz, cnt = struct.unpack_from('<20sIII', d2, o); o += 32
        if cid.startswith(b'REFSKEL'):
            mr = {d2[o + i * sz:o + i * sz + 64].split(b'\0')[0].decode(): struct.unpack_from('<7f', d2, o + i * sz + 76)
                  for i in range(cnt)}
            break
        o += sz * cnt
    fixed = 0
    for i, bn in enumerate(names):
        if bn in mr:
            x, y, z, w, px, py, pz = mr[bn]
            new = [x, -y, z, w, px, -py, pz]
            fixed += any(abs(a - b) > 1e-3 for a, b in zip(new[4:], ref[i][4:7])) or abs(sum(a * b for a, b in zip(new[:4], ref[i][:4]))) < 0.9998
            ref[i][:7] = new
    print(f'rest from gallery mesh: {fixed} bones differ from the skeleton default')
    cfg = {'name': name, 'skeleton': '/Game/' + skel[:-len('.uexp')], 'root': names[0],
           'gallery_mesh_gltf': meshbase + '.gltf',
           'gallery_mesh_psk': next(meshbase + e for e in ('.psk', '.pskx') if os.path.exists(meshbase + e)),
           'gallery_pose_psa': os.path.join(WS, 'export', 'Game', pose[:-len('.uasset')] + '.psa'),
           'names': names, 'parents': par, 'ref': ref}
    json.dump(cfg, open(os.path.join(out, 'char.json'), 'w'))
    biped = sum(x.startswith('Biped_') for x in names)
    print(f'{name}: {n} bones, root {names[0]}, {biped} Biped_ bones -> export/{name}/char.json')


if __name__ == '__main__':
    main(sys.argv[1])
