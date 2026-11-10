import struct, sys, zlib
# usage: rawextract.py <pak> <exact entry suffix> <out file>
def rs(f):
    n = struct.unpack('<i', f.read(4))[0]
    return f.read(-n*2).decode('utf-16-le') if n < 0 else f.read(n).decode('latin-1')
pak, want, out = sys.argv[1:4]
f = open(pak, 'rb'); f.seek(-172, 2); t = f.read()
f.seek(struct.unpack('<Q', t[8:16])[0]); rs(f); cnt = struct.unpack('<i', f.read(4))[0]
for _ in range(cnt):
    name = rs(f).rstrip('\0'); o, s, u, cm = struct.unpack('<QQQB', f.read(25)); f.read(20)
    blocks = [struct.unpack('<QQ', f.read(16)) for _ in range(struct.unpack('<i', f.read(4))[0])] if cm else []
    f.read(5)
    if name.endswith(want):
        pos = f.tell(); data = b''
        for a, b in blocks: f.seek(o + a); data += zlib.decompress(f.read(b - a))
        if not cm: f.seek(o + 53); data = f.read(u)
        open(out, 'wb').write(data); print('wrote', out, len(data)); break
