"""Remap a cooked UE 4.22 AnimSequence's TrackToSkeletonMapTable to the game skeleton's bone order.

The editor skeleton we cook against has Lily's bones in a different order than the game's SK_Lily_SKEL
(the game order isn't a tree walk, FBX import always is). Each track stores a BoneTreeIndex; this rewrites
those ints in place (same size), matching bones by name.

usage:
  remap_tracks.py <anim.uasset> <ours.psa> <game.psa>        # patch anim.uexp next to it
  remap_tracks.py --dump <anim.uasset>                       # list BoneTreeIndex values
ours.psa = UModel export of the cooked clip (its bone list is in the editor skeleton's order)
game.psa = UModel export of any game clip on the same skeleton (e.g. A_Lily_GP_S.psa)
"""
import struct
import sys


def fstring(d, o):
    n = struct.unpack_from('<i', d, o)[0]; o += 4
    if n < 0:
        return d[o:o - n * 2].decode('utf-16-le').rstrip('\0'), o - n * 2
    return d[o:o + n].decode('latin-1').rstrip('\0'), o + n


def names(uasset):
    d = open(uasset, 'rb').read()
    o = 4  # Tag
    legacy = struct.unpack_from('<i', d, o)[0]; o += 4
    if legacy != -4: o += 4  # LegacyUE3Version
    o += 8  # FileVersionUE4, FileVersionLicenseeUE4
    ncv = struct.unpack_from('<i', d, o)[0]; o += 4 + ncv * 20
    o += 4  # TotalHeaderSize
    _, o = fstring(d, o)  # FolderName
    o += 4  # PackageFlags
    count, off = struct.unpack_from('<ii', d, o)
    out, o = [], off
    for _ in range(count):
        s, o = fstring(d, o); o += 4  # two u16 hashes
        out.append(s)
    return out


def bone_slots(uasset):
    """offsets (into .uexp) of every BoneTreeIndex int value, in track order"""
    nm = names(uasset)
    bti, intp = nm.index('BoneTreeIndex'), nm.index('IntProperty')
    d = open(uasset[:-7] + '.uexp', 'rb').read()
    # tag = Name FName, Type FName, Size=4, ArrayIndex=0
    tag = struct.pack('<ii', bti, 0) + struct.pack('<ii', intp, 0) + struct.pack('<ii', 4, 0)
    slots, o = [], d.find(tag)
    while o >= 0:
        slots.append(o + len(tag) + 1)  # + HasPropertyGuid byte
        o = d.find(tag, o + 1)
    return d, slots


def psa_names(p):
    d = open(p, 'rb').read(); o = 0
    while o < len(d):
        cid, _, sz, n = struct.unpack_from('<20sIII', d, o); o += 32
        if cid.startswith(b'BONENAMES'):
            return [d[o + i * sz:o + i * sz + 64].split(b'\0')[0].decode() for i in range(n)]
        o += sz * n


if __name__ == '__main__':
    if sys.argv[1] == '--dump':
        d, slots = bone_slots(sys.argv[2])
        vals = [struct.unpack_from('<i', d, s)[0] for s in slots]
        print(len(vals), 'tracks:', vals[:20], '...')
        sys.exit()
    ua, ours, game = sys.argv[1:4]
    on, gn = psa_names(ours), psa_names(game)
    gi = {n: i for i, n in enumerate(gn)}
    missing = [n for n in on if n not in gi]
    assert not missing, f'bones not in game skeleton: {missing[:10]}'
    d, slots = bone_slots(ua)
    vals = [struct.unpack_from('<i', d, s)[0] for s in slots]
    # cooked 4.22 clips also carry a raw copy (CompressedTrackToSkeletonMapTable: count + int32s) the runtime reads
    raw = d.find(struct.pack('<i', len(vals)) + struct.pack(f'<{len(vals)}i', *vals))
    assert raw >= 0, 'raw track table not found'
    d = bytearray(d)
    new = [gi[on[v]] for v in vals]
    for s, v in zip(slots, new):
        struct.pack_into('<i', d, s, v)
    struct.pack_into(f'<{len(new)}i', d, raw + 4, *new)
    open(ua[:-7] + '.uexp', 'wb').write(d)
    print(f'remapped {len(slots)} tracks (tagged + raw table @{raw}), {sum(a != b for a, b in zip(vals, new))} indices changed')
