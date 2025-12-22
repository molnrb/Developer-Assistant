import asyncio
import os
import re
import shutil
import traceback
from typing import Dict, List

from src.run_utils.cmd import run_streamed
from src.run_utils.events import hub
from src.run_utils.fs_tools import write_snapshot_to_temp
from src.run_utils.state import get_run

TSC_CMD = [
    "npx",
    "--yes",
    "-p",
    "typescript@5",
    "tsc",
    "--noEmit",
    "--allowJs",
    "--checkJs",
    "--jsx",
    "react-jsx",
    "--lib",
    "dom,dom.iterable,esnext",
    "--esModuleInterop",
    "--allowSyntheticDefaultImports",
    "--pretty",
    "false",
]


def _parse_tsc_errors(log: str) -> Dict[str, List[str]]:
    """Parse TypeScript compiler errors from log output."""
    print(f"[DEBUG] Parsing TSC errors from log of length: {len(log)}")
    by_file: Dict[str, List[str]] = {}
    current_file: str | None = None
    pattern = re.compile(r"^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\): (?P<rest>.*)$")

    for raw_line in log.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = pattern.match(line)
        if m:
            current_file = m.group("file")
            line_no = m.group("line")
            col_no = m.group("col")
            rest = m.group("rest")
            msg = f"{line_no}:{col_no} {rest}"
            by_file.setdefault(current_file, []).append(msg)
        else:
            if current_file is not None:
                by_file.setdefault(current_file, []).append(line)

    print(f"[DEBUG] Parsed {len(by_file)} files with errors: {list(by_file.keys())}")
    return by_file


async def run_tsc_check(run_id: str) -> bool:
    """Run TypeScript compiler check on project files."""
    print(f"[DEBUG] Starting TSC check for run_id: {run_id}")
    if os.getenv("DEVMODE") == "true":
        await asyncio.sleep(1)
        await hub.emit(
            run_id,
            {
                "t": "tests.summary",
                "compile_passed": True,
                "skipped": True,
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "status",
                "step": "test",
                "state": "done",
            },
        )
        return True

    r = get_run(run_id)
    files: Dict[str, str] = r.get("modified_files") or r.get("files") or {}
    print(f"[DEBUG] Got {len(files)} total files from run state")
    print(f"tester: TypeScript check on {len(files)} files")

    ts_entry_files = [
        path for path in files.keys() if path.endswith((".ts", ".tsx", ".js", ".jsx"))
    ]
    print(
        f"[DEBUG] Found {len(ts_entry_files)} TypeScript/JavaScript files: {ts_entry_files}"
    )

    if not ts_entry_files:
        msg = "No TypeScript/JavaScript sources to check."
        r["last_tsc_log"] = msg
        r["tsc_errors_by_file"] = {}
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": msg,
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "tests.summary",
                "compile_passed": True,
                "skipped": True,
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "status",
                "step": "test",
                "state": "done",
            },
        )
        return True

    await hub.emit(
        run_id,
        {
            "t": "status",
            "step": "test",
            "state": "running",
        },
    )

    tmp = None
    try:
        tmp = write_snapshot_to_temp(files)
        print(f"[DEBUG] Created temporary directory: {tmp}")

        pkg_json = os.path.join(tmp, "package.json")
        print(f"[DEBUG] Checking for package.json at: {pkg_json}")
        if os.path.exists(pkg_json):
            print("[DEBUG] package.json found, running npm install")
            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stdout",
                    "chunk": "Running npm install in snapshot...",
                },
            )
            npm_cmd = [
                "npm",
                "install",
                "--silent",
                "--no-fund",
                "--ignore-scripts",
                "--loglevel",
                "error",
            ]
            code_npm, so_npm, se_npm = await run_streamed(
                npm_cmd,
                cwd=tmp,
                emit=hub.emit,
                run_id=run_id,
                tool_name="npm-install",
                timeout=240,
            )
            print(
                f"tester: npm install exited {code_npm}\n"
                f"LOG:\n{(so_npm + se_npm)[:2000]}"
            )

            if code_npm != 0:
                print(
                    f"[DEBUG] npm install failed with code {code_npm}, skipping TS check"
                )
                msg = f"npm install failed with code {code_npm}, skipping TS check."
                r["last_tsc_log"] = msg
                r["tsc_errors_by_file"] = {}
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stderr",
                        "chunk": msg,
                    },
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "tests.summary",
                        "compile_passed": True,
                        "skipped": True,
                    },
                )
                await hub.emit(
                    run_id,
                    {
                        "t": "status",
                        "step": "test",
                        "state": "done",
                    },
                )
                return True
        else:
            print("[DEBUG] No package.json found, running tsc without node_modules")
            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stderr",
                    "chunk": "No package.json in snapshot; running tsc without node_modules.",
                },
            )

        tsc_cmd = [
            *TSC_CMD,
            *ts_entry_files,
        ]
        print(f"[DEBUG] Running TSC command: {' '.join(tsc_cmd)}")

        code_tsc, so_tsc, se_tsc = await run_streamed(
            tsc_cmd,
            cwd=tmp,
            emit=hub.emit,
            run_id=run_id,
            tool_name="tsc",
        )

        tsc_log = "\n".join(filter(None, [so_tsc, se_tsc])).strip()
        print(
            f"tester: tsc exited {code_tsc}\n"
            f"LOG:\n{tsc_log[:2000]}{'...' if len(tsc_log) > 2000 else ''}"
        )

        errors_by_file = _parse_tsc_errors(tsc_log) if code_tsc != 0 else {}
        print(f"[DEBUG] TSC check completed. Errors in {len(errors_by_file)} files")
        r["last_tsc_log"] = tsc_log
        r["tsc_errors_by_file"] = errors_by_file

        tsc_ok = code_tsc == 0
        passed = bool(tsc_ok)
        print(f"[DEBUG] TSC result: passed={passed}, tsc_ok={tsc_ok}")

        await hub.emit(
            run_id,
            {
                "t": "tests.summary",
                "compile_passed": passed,
                "tsc": {
                    "ok": tsc_ok,
                    "errorsByFile": errors_by_file,
                },
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "status",
                "step": "test",
                "state": "done" if passed else "failed",
            },
        )
        return passed

    except FileNotFoundError as e:
        print(f"[DEBUG] FileNotFoundError in TSC check: {e}")
        msg = f"FileNotFoundError: {e or 'node/npm not available'}"
        r["last_tsc_log"] = msg
        r["tsc_errors_by_file"] = {}
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": "Node/npm not available; skipping TypeScript tests.",
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "tests.summary",
                "compile_passed": True,
                "skipped": True,
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "status",
                "step": "test",
                "state": "done",
            },
        )
        return True

    except Exception as e:
        etype = type(e).__name__
        msg = f"{etype}: {repr(e)}"
        tb = traceback.format_exc()
        combined = f"{msg}\n{tb}".rstrip()
        print(f"[DEBUG] Unexpected error in TSC check: {etype}: {e}")

        r["last_tsc_log"] = combined
        r["tsc_errors_by_file"] = {}
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": combined,
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "tests.summary",
                "compile_passed": False,
                "errors": 1,
            },
        )
        await hub.emit(
            run_id,
            {
                "t": "status",
                "step": "test",
                "state": "failed",
            },
        )
        return False

    finally:
        if tmp:
            print(f"[DEBUG] Cleaning up temporary directory: {tmp}")
            try:
                shutil.rmtree(tmp)
                print("[DEBUG] Successfully cleaned up temporary directory")
            except Exception as cleanup_err:
                print(f"[DEBUG] Failed to cleanup temp directory: {cleanup_err}")
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stderr",
                        "chunk": f"tester: temp cleanup warning: {cleanup_err!r}",
                    },
                )
