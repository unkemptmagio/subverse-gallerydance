import struct, sys, glob, os
def rs(f):
    n = struct.unpack('<i', f.read(4))[0]
    if n < 0: return f.read(-n*2).decode('utf-16-le').rstrip('\0')
    return f.read(n).decode('latin-1').rstrip('\0')
for p in sorted(glob.glob(sys.argv[1] + '/*.pak')):
    with open(p, 'rb') as f:
        f.seek(-172, 2); tail = f.read()  # v8A footer: magic sits 172 bytes from end
        i = tail.rfind(struct.pack('<I', 0x5A6F12E1))
        ver, off, size = struct.unpack('<IQQ', tail[i+4:i+24])
        f.seek(off); mount = rs(f); cnt = struct.unpack('<i', f.read(4))[0]
        for _ in range(cnt):
            name = rs(f)
            o, s, u, cm = struct.unpack('<QQQB', f.read(25)); f.read(20)  # v8A: u8 compression index, then SHA1
            if cm: nb = struct.unpack('<i', f.read(4))[0]; f.read(16*nb)
            f.read(5)
            print(os.path.basename(p), mount + name)
