import os
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict

from src.run_utils.fs_tools import write_snapshot_to_temp
from src.run_utils.state import get_run
from src.run_utils.db import load_all_files

PREVIEW_PORT = int(os.getenv("PREVIEW_PORT", "4173"))


@dataclass
class PreviewState:
    port: int
    cwd: str
    proc: subprocess.Popen


_preview_registry: Dict[str, PreviewState] = {}

def _is_port_free(port: int) -> bool:
    """Check if the port is free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def _wait_for_port_free(port: int, timeout: float = 5.0, interval: float = 0.2) -> bool:
    """
    Wait until the port is free, max `timeout` seconds.
    Returns True if freed, False if timeout expired.
    """
    start = time.time()
    while time.time() - start < timeout:
        if _is_port_free(port):
            return True
        time.sleep(interval)
    return False


def _wait_for_server_or_fail(proc: subprocess.Popen, run_id: str, timeout: float = 5.0) -> None:
    """
    Wait briefly for the dev server to run stably.
    If the process exits during this time (e.g. port occupied), raise an error.
    """
    start = time.time()
    while time.time() - start < timeout:
        code = proc.poll()
        if code is not None:
            raise RuntimeError(
                f"Preview dev server for run {run_id} exited early with code {code}"
            )
        time.sleep(0.1)

def _ensure_node_modules(cwd: str) -> None:
    if os.path.exists(os.path.join(cwd, "node_modules")):
        return

    subprocess.run(
        ["npm", "install"],
        cwd=cwd,
        check=True,
    )


def _stream_logs(proc: subprocess.Popen, run_id: str) -> None:
    from src.run_utils.events import hub

    if not proc.stdout:
        return

    for line in proc.stdout:
        try:
            msg = line.rstrip()
            print(f"[preview:{run_id}] {msg}")
            hub.emit_sync(
                run_id,
                {"t": "log", "stream": "stdout", "chunk": f"[preview] {msg}\n"},
            )
        except Exception:
            pass


def _stop_preview_state(state: PreviewState) -> None:
    try:
        if state.proc.poll() is None:
            try:
                os.killpg(os.getpgid(state.proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass

            try:
                state.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(state.proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
    except Exception:
        pass


def _stop_all_previews() -> None:
    global _preview_registry
    for rid, st in list(_preview_registry.items()):
        print(f"[preview] Stopping previous preview for run {rid}")
        _stop_preview_state(st)
        _preview_registry.pop(rid, None)


import threading

# Globális lock objektum
_preview_lock = threading.Lock()

def start_preview(run_id: str, user: str, keep: bool) -> PreviewState:
    # A 'with' blokk garantálja, hogy egyszerre csak egy szál futtatja ezt a részt
    with _preview_lock:
        
        # 1. Ha "keep=True" és már fut az adott run_id, akkor azonnal visszaadjuk
        if keep:
            existing = _preview_registry.get(run_id)
            if existing and existing.proc.poll() is None:
                print(f"[preview] Reusing existing preview for {run_id}")
                return existing

        # 2. Mindenképpen leállítunk MINDENT, ami a fix porton futhat
        # Ezzel kitakarítjuk az utat az új folyamatnak
        _stop_all_previews()

        # 3. Biztonsági várakozás, hogy az OS felszabadítsa a portot
        if not _wait_for_port_free(PREVIEW_PORT, timeout=15.0):
            raise RuntimeError(f"Port {PREVIEW_PORT} stuck.")

        # 4. Előkészületek (adatbázis, fájlok, npm install)
        # Ez a rész kritikus: amíg ez fut, a lock miatt más nem tud belépni
        files = load_all_files(run_id, user)
        if not files:
            raise RuntimeError("No files")

        tmp_dir = write_snapshot_to_temp(files)
        
        # Opcionális: Ha az npm install túl lassú, ki lehet venni a lock-ból, 
        # de akkor bonyolultabb a logika. Fix portnál jobb benntartani.
        _ensure_node_modules(tmp_dir)

        # 5. Indítás
        cmd = [
            "npm", "run", "dev", "--",
            "--host", "0.0.0.0",
            "--port", str(PREVIEW_PORT),
            "--strictPort",
        ]

        proc = subprocess.Popen(
            cmd,
            cwd=tmp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid,
        )

        # Szál indítása a logokhoz
        t = threading.Thread(target=_stream_logs, args=(proc, run_id), daemon=True)
        t.start()

        # Megvárjuk, amíg tényleg elindul a szerver, mielőtt elengednénk a lock-ot
        _wait_for_server_or_fail(proc, run_id)

        state = PreviewState(port=PREVIEW_PORT, cwd=tmp_dir, proc=proc)
        _preview_registry[run_id] = state
        
        return state