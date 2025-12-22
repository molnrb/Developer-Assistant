from asyncio import subprocess
import os
import tempfile
from typing import Any, Dict, List, Tuple

TSCONFIG_CONTENT = """{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020","DOM","DOM.Iterable"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noImplicitAny": false,
    "skipLibCheck": true,
    "baseUrl": ".",
    "allowJs": true
  },
  "include": ["src", "*.d.ts", "index.html"]
}
"""

INDEX_HTML_TEMPLATE = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>LLM Project Preview</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="{entry_src}"></script>
  </body>
</html>
"""

SYNTH_MAIN_TSX = """import { createRoot } from 'react-dom/client'
import App from './App'

const el = document.getElementById('root')
if (el) {
  createRoot(el).render(<App />)
} else {
  console.error('No #root found')
}
"""


def ensure_dirs(path: str):
    return


def apply_patches_in_memory(
    filemap: Dict[str, str], patches: List[Dict[str, Any]]
) -> List[str]:
    """
    Patches shape:
      {"path":"src/App.tsx","mode":"create|replace|delete","content":"..."}  # content required for create/replace
    Returns: list of changed paths
    """
    changed: List[str] = []
    for p in patches:
        path = p["path"].lstrip("/")
        mode = p.get("mode", "replace")
        if mode == "delete":
            if path in filemap:
                del filemap[path]
                changed.append(path)
        else:
            content = p.get("content", "")
            ensure_dirs(path)
            prev = filemap.get(path)
            if prev != content:
                filemap[path] = content
                changed.append(path)
    return changed


def _detect_entry(files: Dict[str, str]) -> Tuple[str, str]:
    """
    Returns (entry_src_path_for_html, relative_path_inside_tmp) for the TSX entry.

    Preferáljuk:
      - src/main.tsx
      - src/index.tsx
    Ha nincs, de van src/App.tsx, akkor /src/main.tsx-et szintetizálunk, ami az App-et mountolja.
    Végső fallback: az első src/*.tsx fájl.
    """
    candidates = ["src/main.tsx", "src/index.tsx"]
    for c in candidates:
        if c in files:
            # HTML-ben absolute jelleggel fogjuk használni (Vite így szereti)
            return (f"/{c}", c)

    if "src/App.tsx" in files:
        return ("/src/main.tsx", "src/main.tsx")

    for k in files.keys():
        if k.startswith("src/") and k.endswith(".tsx"):
            return (f"/{k}", k)

    # ha semmi, akkor is legyen valami determinisztikus fallback
    return ("/src/main.tsx", "src/main.tsx")


def write_snapshot_to_temp(filemap: Dict[str, str]) -> str:
    """
    Teljes Vite+TS (akár Tailwind-es) projekt kiírása egy temp mappába.

    - Minden kapott fájlt 1:1-ben kiír.
    - Ha nincs tsconfig.json, beszúr egy defaultot (TSCONFIG_CONTENT).
    - Ha nincs entry TSX, de van App, szintetizál egy main.tsx-et (SYNTH_MAIN_TSX).
    - Ha nincs index.html, beszúr egy minimal Vite-kompatibilis index.html-t,
      ami a detektált entry-re hivatkozik <script type="module" src="...">-tal.
    Semmit nem ír felül, ha a projekt már tartalmazza az adott fájlt.
    """
    tmp = tempfile.mkdtemp(prefix="runrepo_")

    # 1) az összes kapott fájl 1:1-ben kiírása
    for path, content in filemap.items():
        abs_path = os.path.join(tmp, path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)

    # 2) tsconfig.json – csak ha teljesen hiányzik
    tsconfig_path = os.path.join(tmp, "tsconfig.json")
    if not os.path.exists(tsconfig_path):
        with open(tsconfig_path, "w", encoding="utf-8") as f:
            f.write(TSCONFIG_CONTENT)

    # 3) entry TSX detektálása + esetleges szintetizálása
    entry_src_for_html, entry_rel = _detect_entry(filemap)
    entry_abs = os.path.join(tmp, entry_rel)

    if not os.path.exists(entry_abs):
        # nincs ilyen file a generált projektben → hozzuk létre
        os.makedirs(os.path.dirname(entry_abs), exist_ok=True)
        if entry_rel.endswith("main.tsx") and "src/App.tsx" in filemap:
            # klasszikus React entry: App-ot mountolja
            with open(entry_abs, "w", encoding="utf-8") as f:
                f.write(SYNTH_MAIN_TSX)
        else:
            # ultra-minimal fallback (debughoz jó)
            with open(entry_abs, "w", encoding="utf-8") as f:
                f.write(
                    "console.log('Synthetic entry loaded – no explicit entry file was provided.');\n"
                )

    # 4) index.html – csak ha nincs a generált fájlok között
    index_html_path = os.path.join(tmp, "index.html")
    if not os.path.exists(index_html_path):
        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(INDEX_HTML_TEMPLATE.format(entry_src=entry_src_for_html))

    return tmp

async def ensure_npm_install(cwd: str):
    """Ha nincs node_modules a temp projektben, futtat egy npm install-t."""
    node_modules = os.path.join(cwd, "node_modules")
    if os.path.exists(node_modules):
        return

    proc = subprocess.Popen(
        ["npm", "install"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Nem muszáj minden logot végigolvasni, de hasznos lehet debughoz
    for line in proc.stdout:
        print("[npm install]", line.rstrip())
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"npm install failed with exit code {code}")