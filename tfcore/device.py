"""Save sync with a handheld over SSH (NextUI / NX Redux on the TrimUI Brick Pro, spruce on the
TrimUI Brick / Smart Pro; see SAVE_ROOTS).

Pull copies a save folder into a local mirror and records the device files' MD5s in
`.device.json`. The mirror is edited like any save folder. Push refuses while a game is running
or when the device save changed since the pull, backs the device save up on the device, writes
via temporary files + mv, syncs, and re-reads the MD5s. Nothing here ever starts a game.

The transport is pluggable: `SSHTransport` for the real device, `LocalTransport` (a folder that
plays the device's file system) for tests.
"""
import datetime, hashlib, ipaddress, json, os, posixpath, shlex, shutil, socket, subprocess
from concurrent.futures import ThreadPoolExecutor

from .games import game_for_save_dir

SAVES = '/mnt/SDCARD/Saves/PSP/SAVEDATA'
BACKUPS = '/mnt/SDCARD/Saves/PSP/SAVEDATA_backup'
# Where handheld firmwares keep PSP saves, first match wins for a folder name:
# NextUI / NX Redux (PPSSPP libretro core under minarch), then spruce's standalone PPSSPP.
SAVE_ROOTS = (SAVES, '/mnt/SDCARD/Saves/.config/ppsspp/PSP/SAVEDATA')
# Emulator processes; while one runs the game may save at any moment, so nothing is written.
# The [x]yz form keeps grep from matching its own command line.
_EMULATORS = ('[m]inarch.elf', '[P]PSSPPSDL', '[r]etroarch', '[r]a64')
META = '.device.json'
DEFAULT_KEY = os.path.expanduser('~/.ssh/nxredux_ed25519')


class DeviceError(Exception):
    pass


class GameRunning(DeviceError):
    pass


class RemoteChanged(DeviceError):
    pass


def _md5(b):
    return hashlib.md5(b).hexdigest()


# ---------------------------------------------------------------- transports

class SSHTransport:
    def __init__(self, host, key=DEFAULT_KEY, user='root', timeout=10):
        self.host, self.key, self.user, self.timeout = host, key, user, timeout

    def _ssh(self, cmd, data=None):
        args = ['ssh', '-i', self.key, '-o', 'BatchMode=yes', '-o', f'ConnectTimeout={self.timeout}',
                '-o', 'StrictHostKeyChecking=accept-new', '-o', 'LogLevel=ERROR', f'{self.user}@{self.host}', cmd]
        r = subprocess.run(args, input=data, capture_output=True, timeout=120)
        if r.returncode != 0:
            raise DeviceError(f'{cmd.split()[0]} failed on {self.host}: {r.stderr.decode(errors="replace").strip()}')
        return r.stdout

    def run(self, cmd):
        return self._ssh(cmd).decode('utf-8', 'replace')

    def describe(self):
        return self.run('uname -a').strip()

    def game_running(self):
        # NextUI runs every emulator through minarch.elf; spruce runs PSP games in standalone
        # PPSSPP (PPSSPPSDL_<device>) or RetroArch. PORTS have their own processes.
        pattern = ' '.join(f'-e {shlex.quote(p)}' for p in _EMULATORS)
        out = self.run(f'ps | grep {pattern} || true').strip()
        return bool(out)

    def listdir(self, path):
        out = self.run(f'ls -1 {shlex.quote(path)} 2>/dev/null || true')
        return [x for x in out.splitlines() if x]

    def read(self, path):
        return self._ssh(f'cat {shlex.quote(path)}')

    def write(self, path, data):
        self._ssh(f'cat > {shlex.quote(path)}', data)

    def md5(self, path):
        return self.run(f'md5sum {shlex.quote(path)}').split()[0]

    def copy_dir(self, src, dst):
        self.run(f'mkdir -p {shlex.quote(posixpath.dirname(dst))} && cp -rp {shlex.quote(src)} {shlex.quote(dst)}')

    def rename(self, src, dst):
        self.run(f'mv {shlex.quote(src)} {shlex.quote(dst)}')

    def sync(self):
        self.run('sync')


class LocalTransport:
    """A local folder standing in for the device's root (for tests)."""

    def __init__(self, root, running=False):
        self.root, self.running = root, running

    def _p(self, path):
        return os.path.join(self.root, path.lstrip('/'))

    def describe(self):
        return 'LocalTransport'

    def game_running(self):
        return self.running

    def listdir(self, path):
        p = self._p(path)
        return sorted(os.listdir(p)) if os.path.isdir(p) else []

    def read(self, path):
        with open(self._p(path), 'rb') as f:
            return f.read()

    def write(self, path, data):
        with open(self._p(path), 'wb') as f:
            f.write(data)

    def md5(self, path):
        return _md5(self.read(path))

    def copy_dir(self, src, dst):
        shutil.copytree(self._p(src), self._p(dst))

    def rename(self, src, dst):
        os.replace(self._p(src), self._p(dst))

    def sync(self):
        pass


# ---------------------------------------------------------------- device

class Device:
    def __init__(self, transport, roots=SAVE_ROOTS):
        self.t, self.roots = transport, roots
        self._where = {}

    def list_saves(self):
        """[(folder name, Game)] for every Tag Force save on the device, in any known save root."""
        self._where = {}
        for root in self.roots:
            for n in self.t.listdir(root):
                if game_for_save_dir(n) and n not in self._where:
                    self._where[n] = root
        return sorted((n, game_for_save_dir(n)) for n in self._where)

    def locate(self, name):
        if name not in self._where:
            self.list_saves()
        if name not in self._where:
            raise DeviceError(f'{name} is not on the handheld')
        return posixpath.join(self._where[name], name)

    @staticmethod
    def backups_for(remote):
        """Device backups go next to the SAVEDATA folder the save lives in (…/SAVEDATA_backup)."""
        return posixpath.dirname(remote).rstrip('/') + '_backup'

    def pull(self, name, local_root):
        """Copy a device save into local_root/name and remember its device MD5s."""
        if self.t.game_running():
            # pulling is harmless, but the game may save again right after; say so in the meta
            running = True
        else:
            running = False
        remote = self.locate(name)
        local = os.path.join(local_root, name)
        os.makedirs(local, exist_ok=True)
        files = self.t.listdir(remote)
        if 'DATA0' not in files or 'PARAM.SFO' not in files:
            raise DeviceError(f'{remote} is not a complete save')
        sums = {}
        for f in files:
            data = self.t.read(posixpath.join(remote, f))
            with open(os.path.join(local, f), 'wb') as out:
                out.write(data)
            sums[f] = _md5(data)
        meta = dict(host=getattr(self.t, 'host', 'local'), remote=remote, md5=sums,
                    pulled=datetime.datetime.now().isoformat(timespec='seconds'), game_was_running=running)
        with open(os.path.join(local, META), 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=1)
        return local

    @staticmethod
    def meta(local):
        p = os.path.join(local, META)
        if not os.path.exists(p):
            return None
        with open(p, encoding='utf-8') as f:
            return json.load(f)

    def push(self, local, files=('DATA0', 'PARAM.SFO')):
        """Send an edited mirror back. Returns the device-side backup folder."""
        meta = self.meta(local)
        if meta is None:
            raise DeviceError('this folder was not pulled from a device')
        remote = meta['remote']
        if self.t.game_running():
            raise GameRunning('a game is running on the handheld; quit it to the menu first')
        for f in files:
            if self.t.md5(posixpath.join(remote, f)) != meta['md5'].get(f):
                raise RemoteChanged('the save on the handheld changed since it was pulled (the game saved); '
                                    'pull it again and redo the edit')
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
        backup = posixpath.join(self.backups_for(remote), f'{posixpath.basename(remote)}_{stamp}_before-push')
        self.t.copy_dir(remote, backup)
        blobs = {}
        for f in files:
            with open(os.path.join(local, f), 'rb') as fh:
                blobs[f] = fh.read()
            self.t.write(posixpath.join(remote, f + '.new'), blobs[f])
        for f in files:
            self.t.rename(posixpath.join(remote, f + '.new'), posixpath.join(remote, f))
        self.t.sync()
        for f in files:
            if self.t.md5(posixpath.join(remote, f)) != _md5(blobs[f]):
                raise DeviceError(f'{f} on the handheld does not match after writing; the backup is at {backup}')
            meta['md5'][f] = _md5(blobs[f])
        meta['pushed'] = datetime.datetime.now().isoformat(timespec='seconds')
        with open(os.path.join(local, META), 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=1)
        return backup


# ---------------------------------------------------------------- discovery

def _local_networks():
    nets = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(('127.', '169.254.')):
                nets.add(ipaddress.ip_network(f'{ip}/24', strict=False))
    except OSError:
        pass
    return sorted(nets)


def _port_open(ip, port=22, timeout=0.4):
    try:
        with socket.create_connection((str(ip), port), timeout=timeout):
            return True
    except OSError:
        return False


def discover(key=DEFAULT_KEY, networks=None):
    """Hosts on the local /24 networks with SSH open that accept the key and have /mnt/SDCARD."""
    nets = networks or _local_networks()
    hosts = [ip for net in nets for ip in net.hosts()]
    with ThreadPoolExecutor(64) as ex:
        open_hosts = [ip for ip, ok in zip(hosts, ex.map(_port_open, hosts)) if ok]
    found = []
    for ip in open_hosts:
        try:
            t = SSHTransport(str(ip), key, timeout=4)
            if t.run('test -d /mnt/SDCARD && echo ok || true').strip() == 'ok':
                found.append((str(ip), t.describe()))
        except (DeviceError, subprocess.TimeoutExpired):
            pass
    return found
