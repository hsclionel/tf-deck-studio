"""CLI manager for TF Deck Studio background service.

Usage:
    python service.py start [--port 8081]
    python service.py stop [--port 8081]
    python service.py restart [--port 8081]
    python service.py status [--port 8081]
    python service.py logs [--port 8081] [-n LINES]
    python service.py autostart enable|disable [--port 8081]
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHONW = os.path.join(ROOT, '.venv', 'Scripts', 'pythonw.exe')
if not os.path.exists(PYTHONW):
    PYTHONW = 'pythonw.exe'


def pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        out = subprocess.check_output(
            ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
            stderr=subprocess.DEVNULL,
            text=True
        )
        return str(pid) in out
    except Exception:
        return False


def get_pids(port: int):
    sup_pid_file = os.path.join(ROOT, f'service_{port}.pid')
    child_pid_file = os.path.join(ROOT, f'service_{port}_child.pid')
    sup_pid = None
    child_pid = None

    if os.path.exists(sup_pid_file):
        try:
            with open(sup_pid_file, 'r', encoding='utf-8') as f:
                sup_pid = int(f.read().strip())
        except Exception:
            pass

    if os.path.exists(child_pid_file):
        try:
            with open(child_pid_file, 'r', encoding='utf-8') as f:
                child_pid = int(f.read().strip())
        except Exception:
            pass

    return sup_pid, child_pid


def is_running(port: int):
    sup_pid, child_pid = get_pids(port)
    sup_alive = bool(sup_pid and pid_alive(sup_pid))
    child_alive = bool(child_pid and pid_alive(child_pid))
    return (sup_alive or child_alive), sup_pid, child_pid


def check_http(port: int) -> bool:
    for endpoint in ('/favicon.ico', '/'):
        try:
            url = f'http://127.0.0.1:{port}{endpoint}'
            req = urllib.request.Request(url, headers={'User-Agent': 'ServiceHealthCheck/1.0'})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status in (200, 302, 307):
                    return True
        except Exception:
            pass
    return False


def kill_tree(pid: int):
    if not pid or pid <= 0:
        return
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
    except Exception:
        pass


def cmd_start(args):
    port = args.port
    running, sup_pid, child_pid = is_running(port)
    if running:
        print(f"[!] TF Deck Studio is already running on port {port}.")
        print(f"    Supervisor PID: {sup_pid}, Child PID: {child_pid}")
        print(f"    URL: http://localhost:{port}")
        return 0

    print(f"[*] Starting TF Deck Studio service on port {port} in background...")

    # Spawn supervisor via WMI so it's decoupled from the launching console session
    runner_script = os.path.join(ROOT, 'service_runner.py')
    cli_cmd = f'"{PYTHONW}" "{runner_script}" --port {port}'
    if getattr(args, 'home', None):
        cli_cmd += f' --home "{args.home}"'

    ps_script = f'''
    $res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{
        CommandLine = '{cli_cmd}';
        CurrentDirectory = '{ROOT}'
    }}
    exit $res.ReturnValue
    '''

    res = subprocess.run(['powershell', '-NoProfile', '-Command', ps_script], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[X] Failed to launch background process via WMI. Exit code: {res.returncode}")
        if res.stderr:
            print(res.stderr.strip())
        return 1

    # Poll service health
    print("    Waiting for service initialization...", end='', flush=True)
    for _ in range(30):
        time.sleep(0.5)
        print('.', end='', flush=True)
        if check_http(port):
            print(" [OK]")
            _, sup_pid, child_pid = is_running(port)
            print(f"[+] Service successfully started!")
            print(f"    Port:           {port}")
            print(f"    Supervisor PID: {sup_pid}")
            print(f"    App PID:        {child_pid}")
            print(f"    Local URL:      http://localhost:{port}")
            print(f"    Log file:       {os.path.join(ROOT, 'logs', f'service_{port}.log')}")
            return 0

    print(" [Timeout]")
    print(f"[?] Service process spawned, but HTTP port {port} is not responding yet.")
    print(f"    Check logs at: {os.path.join(ROOT, 'logs', f'service_{port}.log')}")
    return 1


def cmd_stop(args):
    port = args.port
    running, sup_pid, child_pid = is_running(port)
    stop_file = os.path.join(ROOT, f'service_{port}.stop')

    if not running and not os.path.exists(stop_file):
        print(f"[*] No running service found for port {port}.")
        return 0

    print(f"[*] Stopping service on port {port}...")
    try:
        with open(stop_file, 'w', encoding='utf-8') as f:
            f.write('stop')
    except Exception as e:
        print(f"    Could not write stop file: {e}")

    # Wait for graceful shutdown
    stopped = False
    for _ in range(12):
        time.sleep(0.5)
        r, _, _ = is_running(port)
        if not r:
            stopped = True
            break

    if not stopped:
        print("    Graceful stop timed out. Forcing termination...")
        for pid in (child_pid, sup_pid):
            if pid and pid_alive(pid):
                kill_tree(pid)

    # Clean leftover files
    for fpath in (
        stop_file,
        os.path.join(ROOT, f'service_{port}.pid'),
        os.path.join(ROOT, f'service_{port}_child.pid')
    ):
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass

    print(f"[+] Service on port {port} has been stopped.")
    return 0


def cmd_restart(args):
    cmd_stop(args)
    time.sleep(1)
    return cmd_start(args)


def cmd_status(args):
    port = args.port
    running, sup_pid, child_pid = is_running(port)
    http_ok = check_http(port)

    print("=" * 50)
    print(f"TF Deck Studio Service Status (Port {port})")
    print("=" * 50)
    status_str = 'RUNNING' if (running and http_ok) else ('STARTING / UNHEALTHY' if running else 'STOPPED')
    print(f"Status:         {status_str}")
    print(f"HTTP Endpoint:  {'200 OK' if http_ok else 'Not Responding'}")
    print(f"Supervisor PID: {sup_pid if (sup_pid and pid_alive(sup_pid)) else 'None'}")
    print(f"App PID:        {child_pid if (child_pid and pid_alive(child_pid)) else 'None'}")
    print(f"Local URL:      http://localhost:{port}")
    log_file = os.path.join(ROOT, 'logs', f'service_{port}.log')
    print(f"Log Path:       {log_file}")

    # Check autostart
    startup_dir = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
    vbs_path = os.path.join(startup_dir, f'TFDeckStudio_{port}.vbs')
    print(f"Autostart:      {'Enabled' if os.path.exists(vbs_path) else 'Disabled'}")

    if os.path.exists(log_file):
        print("\n--- Recent Logs (last 10 lines) ---")
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                for line in lines[-10:]:
                    print(line.rstrip())
        except Exception as e:
            print(f"Could not read log file: {e}")
    print("=" * 50)
    return 0 if (running and http_ok) else 1


def cmd_logs(args):
    port = args.port
    log_file = os.path.join(ROOT, 'logs', f'service_{port}.log')
    if not os.path.exists(log_file):
        print(f"[!] No log file found at {log_file}")
        return 1

    n = args.lines
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            for line in lines[-n:]:
                print(line.rstrip())
    except Exception as e:
        print(f"[X] Error reading logs: {e}")
        return 1
    return 0


def cmd_autostart(args):
    port = args.port
    action = args.action.lower()
    startup_dir = os.path.expandvars(r'%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup')
    vbs_path = os.path.join(startup_dir, f'TFDeckStudio_{port}.vbs')

    if action == 'enable':
        python_exe = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')
        service_py = os.path.join(ROOT, 'service.py')
        # VBScript escapes a quote inside a string by doubling it ("" not \")
        vbs_content = 'Set WshShell = CreateObject("WScript.Shell")\n' \
                      f'WshShell.Run """{python_exe}"" ""{service_py}"" start --port {port}", 0, False\n'
        with open(vbs_path, 'w', encoding='utf-8') as f:
            f.write(vbs_content)
        print(f"[+] Autostart enabled on Windows login.")
        print(f"    Startup shortcut created: {vbs_path}")
        return 0
    elif action == 'disable':
        if os.path.exists(vbs_path):
            os.remove(vbs_path)
            print(f"[+] Autostart disabled (removed {vbs_path}).")
        else:
            print(f"[*] Autostart was not enabled.")
        return 0
    else:
        print(f"[!] Unknown action '{action}'. Use 'enable' or 'disable'.")
        return 1


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--port', type=int, default=8081, help="Service port (default: 8081)")
    common.add_argument('--home', default=None, help="Custom TFDS_HOME directory")

    parser = argparse.ArgumentParser(description="TF Deck Studio Background Service Manager", parents=[common])
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('start', parents=[common], help="Start service in background")
    sub.add_parser('stop', parents=[common], help="Stop service")
    sub.add_parser('restart', parents=[common], help="Restart service")
    sub.add_parser('status', parents=[common], help="Show service status")

    p_logs = sub.add_parser('logs', parents=[common], help="View recent logs")
    p_logs.add_argument('-n', '--lines', type=int, default=30, help="Number of lines to show (default: 30)")

    p_auto = sub.add_parser('autostart', parents=[common], help="Manage Windows login autostart")
    p_auto.add_argument('action', choices=['enable', 'disable'], help="enable or disable autostart")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    dispatch = {
        'start': cmd_start,
        'stop': cmd_stop,
        'restart': cmd_restart,
        'status': cmd_status,
        'logs': cmd_logs,
        'autostart': cmd_autostart,
    }
    return dispatch[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
