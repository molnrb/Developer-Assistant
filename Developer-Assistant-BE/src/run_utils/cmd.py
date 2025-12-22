import asyncio
import os
import shutil
import subprocess
from typing import List, Optional, Tuple


def _resolve_cmd(cmd: List[str]) -> List[str]:
    """Resolve the executable on Windows so 'npx' works (npx.cmd shim)."""
    if os.name == "nt":
        exe = cmd[0]
        if not os.path.splitext(exe)[1]:
            which = (
                shutil.which(exe)
                or shutil.which(exe + ".cmd")
                or shutil.which(exe + ".exe")
            )
            if which:
                cmd = [which] + cmd[1:]
    return cmd


async def _run_streamed_asyncio(
    cmd: List[str], cwd: str, emit, run_id: str, tool_name: str, timeout: Optional[int]
) -> Tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    out_buf: list[str] = []
    err_buf: list[str] = []

    async def pump(stream, tag, buf):
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                s = line.decode(errors="ignore").rstrip("\n\r")
                buf.append(s)
        except Exception as e:
            raise e

    pump_out = asyncio.create_task(pump(proc.stdout, "stdout", out_buf))
    pump_err = asyncio.create_task(pump(proc.stderr, "stderr", err_buf))

    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": f"cmd: timeout after {timeout}s, process killed.",
            },
        )
    finally:
        try:
            await proc.wait()
        except Exception:
            pass
        await asyncio.gather(pump_out, pump_err, return_exceptions=True)

    return proc.returncode or 0, "\n".join(out_buf), "\n".join(err_buf)


async def _run_streamed_threaded(
    cmd: List[str], cwd: str, emit, run_id: str, tool_name: str, timeout: Optional[int]
) -> Tuple[int, str, str]:
    """
    Fallback path when the event loop doesn't support subprocess transports.
    Uses subprocess.Popen + background threads to stream output.
    """
    loop = asyncio.get_running_loop()
    out_buf: list[str] = []
    err_buf: list[str] = []

    def _pump_and_wait() -> Tuple[int, str, str]:
        p = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def pump(stream, tag, buf):
            for line in iter(stream.readline, ""):
                s = line.rstrip("\n")
                buf.append(s)
                asyncio.run_coroutine_threadsafe(
                    emit(run_id, {"t": "log", "stream": tag, "chunk": s[:20]}), loop
                )
            stream.close()

        import threading

        t_out = threading.Thread(
            target=pump, args=(p.stdout, "stdout", out_buf), daemon=True
        )
        t_err = threading.Thread(
            target=pump, args=(p.stderr, "stderr", err_buf), daemon=True
        )
        t_out.start()
        t_err.start()

        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = p.wait()

        t_out.join()
        t_err.join()
        return rc, "\n".join(out_buf), "\n".join(err_buf)

    return await asyncio.to_thread(_pump_and_wait)


async def run_streamed(
    cmd: List[str],
    cwd: str,
    emit,
    run_id: str,
    tool_name: str,
    timeout: Optional[int] = 180,
) -> Tuple[int, str, str]:
    await emit(
        run_id, {"t": "tool.start", "name": tool_name, "cmd": " ".join(cmd), "cwd": cwd}
    )

    cmd = _resolve_cmd(cmd)

    try:
        code, so, se = await _run_streamed_asyncio(
            cmd, cwd, emit, run_id, tool_name, timeout
        )
    except NotImplementedError:
        await emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": "cmd: asyncio subprocess not supported by current event loop, using threaded fallback.",
            },
        )
        code, so, se = await _run_streamed_threaded(
            cmd, cwd, emit, run_id, tool_name, timeout
        )
    except FileNotFoundError as e:
        await emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": f"cmd: executable not found: {cmd[0]} ({e})",
            },
        )
        raise
    except Exception as e:
        await emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": f"cmd: asyncio subprocess failed ({type(e).__name__}: {e!r}), using threaded fallback.",
            },
        )
        code, so, se = await _run_streamed_threaded(
            cmd, cwd, emit, run_id, tool_name, timeout
        )

    await emit(run_id, {"t": "tool.end", "name": tool_name, "code": code})
    return code, so, se
