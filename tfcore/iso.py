"""ISO9660 access that reads only the sectors it needs.

`open_iso(path)` returns a reader for a local file, or for a path on the device (read over
SSH with dd) when the path does not exist on this PC.
"""
import os, struct, subprocess

SECTOR = 2048


class LocalISO:
    def __init__(self, path):
        self.path = path

    def read(self, lba, count):
        with open(self.path, 'rb') as f:
            f.seek(lba * SECTOR)
            return f.read(count * SECTOR)


class DeviceISO:
    def __init__(self, path, ssh):
        self.path, self.ssh = path, ssh

    def read(self, lba, count):
        cmd = f"dd if='{self.path}' bs={SECTOR} skip={lba} count={count} 2>/dev/null"
        return subprocess.run(self.ssh + [cmd], capture_output=True, check=True).stdout


def open_iso(path, ssh=None):
    if os.path.exists(path):
        return LocalISO(path)
    if ssh is None:
        raise FileNotFoundError(path)
    return DeviceISO(path, ssh)


def _entries(iso, lba, size):
    data = iso.read(lba, (size + SECTOR - 1) // SECTOR)
    pos = 0
    while pos < size:
        ln = data[pos]
        if ln == 0:
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        e_lba, e_size = struct.unpack_from('<I', data, pos + 2)[0], struct.unpack_from('<I', data, pos + 10)[0]
        flags, nlen = data[pos + 25], data[pos + 32]
        name = data[pos + 33:pos + 33 + nlen].decode('latin-1').split(';')[0]
        yield name, e_lba, e_size, bool(flags & 2)
        pos += ln


def locate(iso, path):
    """(lba, size) of a file inside the ISO, e.g. 'PSP_GAME/USRDIR/duelsys/cardinfo_jpn.ehp'."""
    pvd = iso.read(16, 1)
    if pvd[1:6] != b'CD001':
        raise ValueError('not an ISO9660 image')
    lba, size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
    for part in path.split('/'):
        for name, e_lba, e_size, _ in _entries(iso, lba, size):
            if name.upper() == part.upper():
                lba, size = e_lba, e_size
                break
        else:
            raise FileNotFoundError(f'{path} ({part})')
    return lba, size


def fetch(iso, path):
    lba, size = locate(iso, path)
    return iso.read(lba, (size + SECTOR - 1) // SECTOR)[:size]
