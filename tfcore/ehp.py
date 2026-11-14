"""EHP container: u32 magic 0x03504845, u32 size, 'NOT ' (uncompressed), u32 count, then
(name offset, data offset) pairs; each name is NUL-terminated and followed by a u32 size."""
import struct

MAGIC = 0x03504845


def members(data):
    magic, _, tag, n = struct.unpack_from('<II4sI', data, 0)
    if magic != MAGIC or tag != b'NOT ':
        raise ValueError(f'unsupported EHP (magic {magic:#x}, tag {tag!r})')
    out = {}
    for i in range(n):
        no, do = struct.unpack_from('<II', data, 16 + i * 8)
        name = data[no:data.index(b'\0', no)].decode()
        size = struct.unpack_from('<I', data, no + len(name) + 1)[0]
        out[name] = data[do:do + size]
    return out
