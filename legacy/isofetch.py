"""Fetch one file out of an ISO9660 image, reading only the sectors needed.

The ISO is a local file when the path exists on this PC, otherwise a path on the device
(read over SSH with dd).

  python -I isofetch.py <iso path> <path/inside/iso> <local out>
"""
import os, struct, subprocess, sys

SSH = ['ssh', '-i', os.path.expanduser('~/.ssh/nxredux_ed25519'), '-o', 'LogLevel=ERROR', 'root@192.168.0.12']


def read(iso, lba, count):
    if os.path.exists(iso):
        with open(iso, 'rb') as f:
            f.seek(lba * 2048)
            return f.read(count * 2048)
    cmd = f"dd if='{iso}' bs=2048 skip={lba} count={count} 2>/dev/null"
    return subprocess.run(SSH + [cmd], capture_output=True, check=True).stdout


def dir_entries(iso, lba, size):
    data = read(iso, lba, (size + 2047) // 2048)
    pos = 0
    while pos < size:
        ln = data[pos]
        if ln == 0:
            pos = (pos // 2048 + 1) * 2048
            continue
        e_lba, e_size = struct.unpack_from('<I', data, pos + 2)[0], struct.unpack_from('<I', data, pos + 10)[0]
        flags, nlen = data[pos + 25], data[pos + 32]
        name = data[pos + 33:pos + 33 + nlen].decode('latin-1').split(';')[0]
        yield name, e_lba, e_size, bool(flags & 2)
        pos += ln


def locate(iso, path):
    """(lba, size) of a file inside the ISO."""
    pvd = read(iso, 16, 1)
    assert pvd[1:6] == b'CD001'
    root = pvd[156:156 + 34]
    lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    for part in path.split('/'):
        for name, e_lba, e_size, is_dir in dir_entries(iso, lba, size):
            if name.upper() == part.upper():
                lba, size = e_lba, e_size
                break
        else:
            raise FileNotFoundError(f'{path}: {part}')
    return lba, size


def fetch(iso, path):
    lba, size = locate(iso, path)
    return read(iso, lba, (size + 2047) // 2048)[:size]


def main(iso, path, out):
    data = fetch(iso, path)
    open(out, 'wb').write(data)
    print(f'{path}: {len(data)} bytes -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
