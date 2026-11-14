"""Background supervisor for TF Deck Studio.

Runs app/main.py as a supervised child process, redirecting logs,
handling unexpected crashes, and responding to stop signals.
"""
import argparse
import datetime
import os
import signal
import subprocess
import sys
import time


def log(msg, log_file=None):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] [Supervisor] {msg}\n"
    if log_file:
        try:
            log_file.write(line)
            log_file.flush()
        except Exception:
            pass
    print(line, end='', flush=True)


def kill_tree(pid: int):
    if not pid or pid <= 0:
        return
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--home', default=None)
    args = parser.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    port = args.port
    pid_file = os.path.join(root, f'service_{port}.pid')
    child_pid_file = os.path.join(root, f'service_{port}_child.pid')
    stop_file = os.path.join(root, f'service_{port}.stop')
    log_path = os.path.join(logs_dir, f'service_{port}.log')

    # Remove stale stop file if present
    if os.path.exists(stop_file):
        try:
            os.remove(stop_file)
        except Exception:
            pass

    # Record supervisor PID
    with open(pid_file, 'w', encoding='utf-8') as f:
        f.write(str(os.getpid()))

    py_exe = os.path.join(root, '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(py_exe):
        py_exe = sys.executable

    cmd = [py_exe, os.path.join(root, 'app', 'main.py'), '--port', str(port)]
    if args.home:
        cmd.extend(['--home', args.home])

    running = True

    def handle_signal(sig, frame):
        nonlocal running
        running = False

    try:
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)
    except Exception:
        pass

    crash_timestamps = []

    with open(log_path, 'a', encoding='utf-8', buffering=1) as lf:
        log(f"Starting TF Deck Studio supervisor (PID {os.getpid()}) on port {port}", lf)
        log(f"Target command: {' '.join(cmd)}", lf)

        while running:
            if os.path.exists(stop_file):
                log("Stop file detected. Exiting supervisor.", lf)
                break

            log("Spawning app process...", lf)
            try:
                child = subprocess.Popen(
                    cmd,
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy()
                )
            except Exception as e:
                log(f"Failed to spawn app process: {e}", lf)
                time.sleep(5)
                continue

            with open(child_pid_file, 'w', encoding='utf-8') as f:
                f.write(str(child.pid))

            log(f"App process running with PID {child.pid}", lf)

            # Monitor child
            while running:
                if os.path.exists(stop_file):
                    log("Stop requested. Terminating child process tree...", lf)
                    kill_tree(child.pid)
                    running = False
                    break

                ret = child.poll()
                if ret is not None:
                    log(f"Child process exited with return code {ret}", lf)
                    break
                time.sleep(1)

            if os.path.exists(child_pid_file):
                try:
                    os.remove(child_pid_file)
                except Exception:
                    pass

            if not running:
                break

            # If child exited without stop requested: evaluate crash restart
            now = time.time()
            crash_timestamps.append(now)
            crash_timestamps = [t for t in crash_timestamps if now - t < 60]

            if len(crash_timestamps) > 5:
                log("Crash loop detected (> 5 crashes in 60s). Pausing for 30s before retry...", lf)
                time.sleep(30)
            else:
                log("Restarting child process in 2 seconds...", lf)
                time.sleep(2)

        # Cleanup
        if os.path.exists(stop_file):
            try:
                os.remove(stop_file)
            except Exception:
                pass
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except Exception:
                pass
        if os.path.exists(child_pid_file):
            try:
                os.remove(child_pid_file)
            except Exception:
                pass
        log("Supervisor shutdown complete.", lf)


if __name__ == '__main__':
    main()
