import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from src.api.database.database_dto import ChatMessage
from src.run_utils.events import hub
from src.run_utils.fs_tools import apply_patches_in_memory
from src.run_utils.llm import chat_json
from src.run_utils.state import get_run

canvas_project: dict[str, str] = {
    "package.json": """{
  "name": "canvas-react-demo",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.6.3",
    "vite": "^5.4.0"
  }
}
""",
    "index.html": """<!doctype html>
<html lang="hu">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Canvas React Demo</title>
    <link rel="stylesheet" href="/src/global.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
    "src/global.css": """/* Globális CSS – reset + stílus */
:root {
  --bg: #0f1220;
  --fg: #e7e9ee;
  --muted: #aab2c5;
}

* { box-sizing: border-box; }

html, body, #root {
  margin: 0;
  height: 100%;
  background: radial-gradient(circle at 20% 10%, #141830 0%, var(--bg) 60%);
  color: var(--fg);
  font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', Arial;
}

header {
  padding: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  background: rgba(255, 255, 255, 0.03);
  backdrop-filter: blur(6px);
}

canvas {
  display: block;
  width: 100%;
  height: calc(100vh - 70px);
}
""",
    "src/main.tsx": """import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import "./global.css";

const CanvasDemo: React.FC = () => {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    window.addEventListener("resize", resize);
    resize();

    type Ball = { x: number; y: number; vx: number; vy: number; r: number; color: string };
    const rand = (a: number, b: number) => Math.random() * (b - a) + a;
    const balls: Ball[] = Array.from({ length: 10 }, () => ({
      x: rand(50, canvas.clientWidth - 50),
      y: rand(50, canvas.clientHeight - 50),
      vx: rand(-150, 150),
      vy: rand(-150, 150),
      r: rand(8, 18),
      color: `hsl(${rand(180, 280)}, 90%, 70%)`,
    }));

    const mouse = { x: 0, y: 0, active: false };
    canvas.addEventListener("pointermove", e => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.active = true;
    });
    canvas.addEventListener("pointerleave", () => (mouse.active = false));
    canvas.addEventListener("pointerdown", e => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      balls.push({
        x, y,
        vx: rand(-120, 120),
        vy: rand(-120, 120),
        r: rand(10, 18),
        color: `hsl(${rand(0, 360)}, 85%, 65%)`,
      });
    });

    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.033, (now - last) / 1000);
      last = now;
      ctx.fillStyle = "#0f1220";
      ctx.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);

      for (const b of balls) {
        if (mouse.active) {
          const dx = mouse.x - b.x;
          const dy = mouse.y - b.y;
          const dist2 = dx * dx + dy * dy + 1e-3;
          const pull = Math.min(80 / dist2, 0.2);
          b.vx += dx * pull * dt * 60;
          b.vy += dy * pull * dt * 60;
        }
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        b.vx *= 0.998;
        b.vy = b.vy * 0.998 + 220 * dt;

        if (b.x - b.r < 0) { b.x = b.r; b.vx = Math.abs(b.vx) * 0.9; }
        if (b.x + b.r > canvas.clientWidth) { b.x = canvas.clientWidth - b.r; b.vx = -Math.abs(b.vx) * 0.9; }
        if (b.y - b.r < 0) { b.y = b.r; b.vy = Math.abs(b.vy) * 0.9; }
        if (b.y + b.r > canvas.clientHeight) { b.y = canvas.clientHeight - b.r; b.vy = -Math.abs(b.vy) * 0.9; }

        const g = ctx.createRadialGradient(b.x - b.r*0.4, b.y - b.r*0.6, b.r*0.1, b.x, b.y, b.r);
        g.addColorStop(0, "rgba(255,255,255,0.9)");
        g.addColorStop(0.2, b.color);
        g.addColorStop(1, "rgba(0,0,0,0.15)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();
      }

      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);

    return () => window.removeEventListener("resize", resize);
  }, []);

  return (
    <div>
      <header>
        <h1>Canvas Demo (React + TS)</h1>
        <p>Kattints a vászonra új golyóért, mozgasd az egeret: vonzás hatás</p>
      </header>
      <canvas ref={ref}></canvas>
    </div>
  );
};

createRoot(document.getElementById("root")!).render(<CanvasDemo />);
""",
}


IMPL_SYS = (
    "You are an implementer agent. Generate exactly one file for a React 18 + TypeScript app "
    "according to the given plan and already-available dependency files. Output strict JSON."
)


def per_file_prompt(
    plan: Dict[str, Any],
    domain: str,
    description: str,
    target_file: Dict[str, Any],
    dep_file_blobs: List[Tuple[str, str]],
    file_hard_constraints: Optional[str] = None,
) -> str:
    """
    Build a prompt for generating a single file based on the global plan and already-generated dependencies.
    """
    plan_files_min = [
        {
            "name": f.get("name"),
            "type": f.get("type"),
            "description": f.get("description"),
            "responsibilities": f.get("responsibilities", []),
            "internalDependencies": f.get("internalDependencies", []),
            "externalDependencies": f.get("externalDependencies", []),
            "exports": f.get("exports", []),
            "usedBy": f.get("usedBy", []),
        }
        for f in plan.get("files", [])
    ]
    
    style = plan.get("style")

    def _truncate(s: str, limit: int = 40000) -> str:
        if len(s) <= limit:
            return s
        head = s[: int(limit * 0.7)]
        tail = s[-int(limit * 0.2) :]
        return head + "\n/* ... truncated ... */\n" + tail

    dep_payload = [{"path": p, "content": _truncate(c)} for (p, c) in dep_file_blobs]

    special_constraints_block = ""
    if file_hard_constraints:
        special_constraints_block = f"""
Special HARD constraints for THIS file:
{file_hard_constraints}
""".rstrip()

    return f"""
Application domain: {domain}
High-level project description:
{description}

Goal
- Generate the SINGLE target file exactly as specified by its plan entry.
- Use React 18 + TypeScript conventions as needed. Keep code type safe!
- Respect the dependencies already provided (their contents are available below).
- Keep content runnable and aligned with the plan description.

Important rules
- Return ONLY a JSON object with this shape:
  {{
    "content":"<full file content>",
    "summary":"<short but informative summary>"
  }}
- NO extra text. NO markdown. NO backticks.
- Do not generate any other files than the target.
- The file must be COMPLETE and runnable.
- Do NOT leave TODOs for core logic.
- Do NOT use ellipses ("...") or pseudo-code.
- Do NOT reference functions, components, or types that are not defined in this file or imported from the plan/external deps.
- Keep within the target file's responsibilities in the plan.
- If the file exports named symbols, implement and export them.
- You MUST:
  - Import only from:
    - internal plan files listed in "internalDependencies"
    - external packages listed in "externalDependencies"
  - Export exactly the symbols listed under "exports" for this file (you may also have private helpers).
- Do NOT:
  - Add imports from files that are NOT in the plan.
  - Change the name or existence of listed exports.
- Use Tailwind Play CDN only if you generate index.html (no PostCSS).
- If file type is 'config' or 'data', keep code straightforward and valid.
- Use strict TypeScript typings for:
  - component props,
  - hook parameters/return values,
  - context values.
- Avoid `any` unless absolutely unavoidable; prefer explicit interfaces.
- Make sure JSX elements use correct React 18 + TSX types (e.g., React.FC<Props>).
- For each export object in "exports":
  - If "kind" is "component" and "propsInterface" is set, define that interface and use it for the component props.
  - If "signature" describes a function or hook shape, follow it closely for parameters and return type.

Summary requirements (STRICT):
- MAX 250-300 characters. 
- Use "teleprompter style": short, dense, technical statements.
- Focus ONLY on behavior/side-effects not obvious from the plan (e.g., internal state, storage, timers, specific DOM listeners).
- NO "This file contains...", NO fluff, NO markdown.
- Focus on what isn't obvious from the plan description.

{special_constraints_block}

Target file (from plan):
{json.dumps({
    "name": target_file.get("name"),
    "type": target_file.get("type"),
    "description": target_file.get("description"),
    "responsibilities": target_file.get("responsibilities", []),
    "internalDependencies": target_file.get("internalDependencies", []),
    "externalDependencies": target_file.get("externalDependencies", []),
    "exports": target_file.get("exports", [])
}, ensure_ascii=False)}

Plan (files, minimal view):
{json.dumps(plan_files_min, ensure_ascii=False)}

Already-available dependency files (path + content):
{json.dumps(dep_payload, ensure_ascii=False)}

Global style guidance:
{style}

TECHNICAL LAYOUT RULES:
- Never use fixed viewport units like 100vh or 100vw for layout containers; use 100% or flex-1.
- Ensure all elements stay within the bounds of their parent container.
- Use 'relative' positioning as the default for layout shells to avoid overlapping the parent's boundaries.
- The root layout should be responsive and use 'min-h-full' instead of 'h-screen'.

Before you respond:
- Internally verify that:
  - All named exports listed in "exports" exist and are correctly exported.
  - All imports refer to modules listed in the plan or externalDependencies.
  - There are no obvious TypeScript errors (missing types, invalid JSX attributes, etc.).
Then respond with the final JSON only.
""".strip()


def _plan_index(plan: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Build an index of plan files keyed by file name.
    """
    return {f["name"]: f for f in plan.get("files", [])}


def _in_plan_deps(target: Dict[str, Any], plan_names: Set[str]) -> List[str]:
    """
    Return only those dependencies that are internal plan file names.
    """
    deps = target.get("internalDependencies") or []
    return [d for d in deps if isinstance(d, str) and d in plan_names]


def _dep_blobs_for_target(
    target_name: str,
    plan_index_by_name: Dict[str, Dict[str, Any]],
    current_files: Dict[str, str],
) -> List[Tuple[str, str]]:
    """
    Collect (path, content) for the target's in-plan dependencies that already exist in current_files.
    """
    target = plan_index_by_name.get(target_name, {})
    plan_names = set(plan_index_by_name.keys())
    needed = _in_plan_deps(target, plan_names)

    blobs: List[Tuple[str, str]] = []
    for dep_name in needed:
        if dep_name in current_files:
            blobs.append((dep_name, current_files[dep_name]))
    return blobs


MAX_LLM_RETRIES = 3
BASE_RETRY_DELAY_SEC = 2


async def _generate_single_file(
    run_id: str,
    plan: Dict[str, Any],
    domain: str,
    description: str,
    target_name: str,
    plan_index_by_name: Dict[str, Dict[str, Any]],
    current_files: Dict[str, str],
    model: str,
) -> Optional[Dict[str, Any]]:
    """
    Generate exactly one file via LLM and return a 'patches' JSON object or None if generation failed.
    Retries a few times on transient errors (e.g. rate limits).
    """
    target_file = plan_index_by_name.get(target_name)
    if not target_file:
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stderr",
                "chunk": f"[skip] {target_name}: not in plan",
            },
        )
        return None

    dep_blobs = _dep_blobs_for_target(target_name, plan_index_by_name, current_files)

    file_hard_constraints: Optional[str] = None

    if target_name == "index.html":
        file_hard_constraints = """
- The <body> element MUST have a clean reset and ensure it doesn't force scrollbars.
- Use <body class="m-0 p-0 h-full overflow-x-hidden">.
- The <body> element MUST contain these two direct children, in this order:
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
""".strip()

    elif target_name == "package.json":
        file_hard_constraints = """
- It MUST be compatible with a standard Vite + React 18 + TypeScript setup.
- scripts MUST look like this:
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "check": "tsc --noEmit"
  }
- you must include vite, react, react-dom, and typescript as dependencies/devDependencies.
""".strip()

    elif target_name == "tsconfig.json":
        file_hard_constraints = """
- It MUST be compatible with a standard Vite + React 18 + TypeScript setup.
""".strip()

    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            user_prompt = per_file_prompt(
                plan, domain, description, target_file, dep_blobs, file_hard_constraints
            )

            resp = await chat_json(
                run_id,
                "implementer",
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": IMPL_SYS},
                    {"role": "user", "content": user_prompt},
                ],
            )

            data = json.loads(resp.choices[0].message.content)

            content = data.get("content")
            summary = data.get("summary", "")

            if not isinstance(content, str) or not content.strip():
                raise ValueError("Response 'content' must be a non-empty string.")

            patches = [
                {
                    "path": target_name,
                    "content": content,
                }
            ]

            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stdout",
                    "chunk": f" Generated {target_name}\n{summary}",
                },
            )

            return {
                "summary": summary,
                "patches": patches,
            }

        except Exception as e:
            last_error = e
            is_last = attempt == MAX_LLM_RETRIES

            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stderr",
                    "chunk": (
                        f"[fail] {target_name} attempt {attempt}/{MAX_LLM_RETRIES}: {e}"
                        + ("" if is_last else " → retrying after delay")
                    ),
                },
            )

            if is_last:
                break

            delay = BASE_RETRY_DELAY_SEC * attempt
            await asyncio.sleep(delay)

    await hub.emit(
        run_id,
        {
            "t": "log",
            "stream": "stderr",
            "chunk": f"[fail] {target_name}: giving up after {MAX_LLM_RETRIES} attempts ({last_error})",
        },
    )
    return None


async def generate_scaffold(
    run_id: str,
    plan: Dict[str, Any],
    domain: str,
    description: str,
    iterations: List[List[str]],
    implementer_model: str,
    *,
    concurrency: int = 8,
):
    """
    Generate all files defined in the plan across multiple iterations, updating in-memory files and plan summaries.
    """
    if os.getenv("DEVMODE") == "true":
        try:
            await asyncio.sleep(2)
            r = get_run(run_id)
            log = "[dev] Mocked files"
            r["messages"].append(
                ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
            )
            await hub.emit(
                run_id, {"t": "log", "stream": "stdout", "chunk": "[dev] Mocked files"}
            )
            r["files"] = canvas_project
            return True
        except Exception as e:
            await hub.emit(
                run_id,
                {"t": "log", "stream": "stderr", "chunk": f"[dev] Mock failed: {e}"},
            )
            return None
    try:
        r = get_run(run_id)
        plan_index_by_name = _plan_index(plan)
        current_files: Dict[str, str] = r.get("files", {}) or {}
        file_summaries: Dict[str, str] = {}

        log = f"Implementer starting with {len(iterations or [])} iterations."
        r["messages"].append(
            ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
        )
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stdout",
                "chunk": log,
            },
        )

        for idx, layer in enumerate(iterations):
            log = f"Iteration {idx+1}: generating {len(layer)} files."
            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stdout",
                    "chunk": log,
                },
            )

            sem = asyncio.Semaphore(concurrency)

            async def _task(target_name: str) -> Optional[Dict[str, Any]]:
                async with sem:
                    return await _generate_single_file(
                        run_id=run_id,
                        plan=plan,
                        domain=domain,
                        description=description,
                        target_name=target_name,
                        plan_index_by_name=plan_index_by_name,
                        current_files=current_files,
                        model=implementer_model,
                    )

            tasks = [_task(name) for name in layer]
            results = await asyncio.gather(*tasks, return_exceptions=False)

            patches: List[Dict[str, Any]] = []
            for res in results:
                if not res or not isinstance(res, dict):
                    continue

                res_patches = res.get("patches")
                if isinstance(res_patches, list):
                    patches.extend(res_patches)
                    first_patch = (
                        res_patches[0]
                        if res_patches and isinstance(res_patches[0], dict)
                        else None
                    )
                    path = (
                        first_patch.get("path")
                        if isinstance(first_patch, dict)
                        else None
                    )
                else:
                    path = None

                summary = res.get("summary")
                if isinstance(path, str) and isinstance(summary, str):
                    file_summaries[path] = summary

            if not patches:
                await hub.emit(
                    run_id,
                    {
                        "t": "log",
                        "stream": "stderr",
                        "chunk": f"Iteration {idx+1}: no patches produced",
                    },
                )
                continue

            log = f"Iteration {idx+1}: generated {layer} files."
            r["messages"].append(
                ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
            )
            await hub.emit(
                run_id,
                {
                    "t": "log",
                    "stream": "stdout",
                    "chunk": log,
                },
            )
            apply_patches_in_memory(current_files, patches)
            r["files"] = current_files

        files_meta = plan.get("files")
        if isinstance(files_meta, list):
            for meta in files_meta:
                if not isinstance(meta, dict):
                    continue
                name = meta.get("name")
                if isinstance(name, str) and name in file_summaries:
                    meta["summary"] = file_summaries[name]

        r["plan"] = plan

        log = "Implementer completed all iterations."
        r["messages"].append(
            ChatMessage(id=len(r["messages"]), content=log, fromUser=False)
        )
        await hub.emit(
            run_id,
            {
                "t": "log",
                "stream": "stdout",
                "chunk": log,
            },
        )
        return True

    except Exception as e:
        print(f"Implementer failed: {e}")
        await hub.emit(
            run_id,
            {"t": "log", "stream": "stderr", "chunk": f"Implementer failed: {e}"},
        )
        await hub.emit(run_id, {"t": "status", "step": "implement", "state": "failed"})
        return False
