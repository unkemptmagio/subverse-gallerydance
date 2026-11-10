# Minimal VMD (Vocaloid Motion Data) parser: bone keys, morph count, IK on/off frames.
import struct

def _name(b):
    b = b.split(b'\0')[0]
    try:
        return b.decode('shift_jis')
    except UnicodeDecodeError:
        return b.decode('shift_jis', 'ignore')

def read_vmd(path):
    d = open(path, 'rb').read()
    o = 0
    hdr = d[:30]; o = 30
    model = _name(d[o:o + 20]); o += 20
    n, = struct.unpack_from('<I', d, o); o += 4
    bones = {}
    for _ in range(n):
        nm = _name(d[o:o + 15]); fr, px, py, pz, qx, qy, qz, qw = struct.unpack_from('<I7f', d, o + 15)
        ip = d[o + 47:o + 63]  # first 16 bytes: X/Y/Z/R x1, then y1, x2, y2 (0..127)
        o += 15 + 4 + 28 + 64
        bones.setdefault(nm, []).append((fr, (px, py, pz), (qx, qy, qz, qw), ip))
    for k in bones:
        bones[k].sort(key=lambda t: t[0])
    res = {'header': hdr, 'model': model, 'bones': bones, 'ik': []}
    try:
        n, = struct.unpack_from('<I', d, o); o += 4 + n * 23          # morphs
        n, = struct.unpack_from('<I', d, o); o += 4 + n * 61          # camera
        n, = struct.unpack_from('<I', d, o); o += 4 + n * 28          # light
        n, = struct.unpack_from('<I', d, o); o += 4 + n * 9           # self shadow
        n, = struct.unpack_from('<I', d, o); o += 4                   # show/IK
        for _ in range(n):
            fr, show, cnt = struct.unpack_from('<IBI', d, o); o += 9
            iks = {}
            for _ in range(cnt):
                iks[_name(d[o:o + 20])] = d[o + 20]; o += 21
            res['ik'].append((fr, show, iks))
    except struct.error:
        pass
    return res

if __name__ == '__main__':
    import sys
    r = read_vmd(sys.argv[1])
    print(r['header'], r['model'])
    mx = 0
    for k, v in sorted(r['bones'].items(), key=lambda kv: -len(kv[1])):
        mx = max(mx, v[-1][0])
        moved = any(abs(c) > 1e-4 for t in v for c in t[1])
        rot = any(abs(t[2][3]) < 0.99999 for t in v)
        print(f'{k!r:24} keys={len(v):5} last={v[-1][0]:5} pos={moved} rot={rot}')
    print('max frame', mx, 'ik frames', r['ik'][:5], len(r['ik']))
