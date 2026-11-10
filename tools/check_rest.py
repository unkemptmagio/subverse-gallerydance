"""Compare the rest pose of two .psk exports bone by bone (by name).
usage: check_rest.py <ours.psk> <game.psk>
A clip only plays correctly in-game if our editor skeleton's local rest rotations equal the game's."""
import math
import struct
import sys


def bones(p):
    d = open(p, 'rb').read(); o = 0
    while o < len(d):
        cid, _, sz, n = struct.unpack_from('<20sIII', d, o); o += 32
        if cid.startswith(b'REFSKEL'):
            out = {}
            for i in range(n):
                r = d[o + i * sz:o + (i + 1) * sz]
                out[r[:64].split(b'\0')[0].decode()] = (struct.unpack_from('<4f', r, 76), struct.unpack_from('<3f', r, 92))
            return out
        o += sz * n


ours, game = bones(sys.argv[1]), bones(sys.argv[2])
worst = []
for n, (q, p) in game.items():
    if n not in ours:
        continue
    oq, op = ours[n]
    dot = min(1.0, abs(sum(a * b for a, b in zip(q, oq))))
    worst.append((math.degrees(2 * math.acos(dot)), math.dist(p, op), n))
worst.sort(reverse=True)
bad = [x for x in worst if x[0] > 1 or x[1] > 0.1]
print(f'rest check: {len(worst)} bones compared, {len(bad)} off (>1 deg or >0.1 cm)')
for a, dpos, n in (worst[:5] if len(sys.argv) < 4 else bad):
    print(f'   {n}: {a:.2f} deg, {dpos:.3f} cm')
