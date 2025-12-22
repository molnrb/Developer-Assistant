
from __future__ import annotations

import os
from typing import Dict, Iterable, List

REQUIRED_FILES = [
    ("index.html", "config"),
    ("package.json", "config"),
    ("tsconfig.json", "config"),
    ("src/main.tsx", "entry"),
    ("src/App.tsx", None),
]

RESOLVABLE_EXTS = (".ts", ".tsx", ".json")


def _index_files(files: List[Dict]) -> Dict[str, Dict]:
    """Return a mapping from file name to file descriptor object."""
    return {
        f.get("name", ""): f for f in files if isinstance(f, dict) and f.get("name")
    }


def _has_file(files_by_name: Dict[str, Dict], name: str, ftype: str | None = None) -> bool:
    """Check if a file with a given name (and optional type) exists in the index."""
    f = files_by_name.get(name)
    return bool(f and (ftype is None or f.get("type") == ftype))


def _mentions(items: Iterable[str], needle: str) -> bool:
    """Return True if any of the given strings contains the needle (case-insensitive)."""
    n = needle.lower()
    return any(n in (s or "").lower() for s in items)


def _collect_text(plan: Dict) -> List[str]:
    """Collect textual fields from the plan for soft, domain-level checks."""
    files = plan.get("files") or []

    names = [f.get("name", "") for f in files]
    resp_blocks: List[str] = []
    for f in files:
        rs = f.get("responsibilities") or []
        if isinstance(rs, list):
            resp_blocks.extend(str(r) for r in rs)

    return [*names, *resp_blocks]


def _resolve_rel_import(spec: str, importer_name: str) -> List[str]:
    """
    Given a relative import specifier and an importing filename, return candidate
    concrete filenames that should exist in the plan.
    """
    base_dir = os.path.dirname(importer_name)
    raw = os.path.normpath(os.path.join(base_dir, spec))
    root, ext = os.path.splitext(raw)
    if ext:
        return [raw.replace("\\", "/")]
    return [f"{raw}{e}".replace("\\", "/") for e in RESOLVABLE_EXTS]


def _light_graph_check(files: List[Dict]) -> List[str]:
    """
    Perform light coherence checks on internalDependencies and usedBy associations.
    Validates that dependencies point to existing files (absolute or relative spec)
    and that usedBy references refer to known files.
    """
    fails: List[str] = []
    by_name = _index_files(files)
    nameset = set(by_name.keys())

    for f in files:
        fname = f.get("name") or ""
        deps = f.get("internalDependencies") or []

        for spec in deps:
            if not isinstance(spec, str):
                fails.append(f"{fname}: internalDependencies entries must be strings")
                continue

            if spec.startswith("./") or spec.startswith("../"):
                candidates = _resolve_rel_import(spec, fname)
                if not any(c in nameset for c in candidates):
                    fails.append(
                        f"Unresolvable relative dependency in {fname}: '{spec}' "
                        f"(tried {', '.join(candidates)})"
                    )
            else:
                if spec not in nameset:
                    fails.append(
                        f"{fname}: internal dependency '{spec}' not found in plan files"
                    )

        used_by = f.get("usedBy") or []
        for ub in used_by:
            if not ub:
                continue
            if ub not in nameset:
                fails.append(
                    f"{fname} declares usedBy '{ub}' which does not exist in plan"
                )

    return fails


def _domain_checks(plan: Dict, domain: str) -> List[str]:
    """
    Perform pragmatic domain-specific checks that are resilient to naming choices
    and focus on intent rather than exact filenames.
    """
    files = plan.get("files") or []
    text = _collect_text(plan)
    fails: List[str] = []

    def has_type(t: str) -> bool:
        return any(f.get("type") == t for f in files)

    def has_name_part(part: str) -> bool:
        return _mentions((f.get("name", "") for f in files), part)

    def has_desc_part(part: str) -> bool:
        return _mentions(text, part)

    if not any(
        f.get("type") == "router" and (f.get("name", "").startswith("src/"))
        for f in files
    ):
        fails.append("Missing router setup file under src/ (type='router').")

    if domain == "website":
        if not (has_name_part("Header") and has_name_part("Footer")):
            fails.append("Website should include Header and Footer components.")
        if sum(1 for f in files if f.get("type") == "page") < 2:
            fails.append("Website should define at least two distinct pages.")
        if not (
            has_name_part("seo")
            or has_desc_part("SEO")
            or _mentions(text, "meta description")
        ):
            fails.append(
                "Website should mention SEO/meta handling or provide an SEO utility."
            )

    elif domain == "webshop":
        if not (_mentions(text, "product") or has_name_part("product")):
            fails.append(
                "Webshop should include a product model/data and related views."
            )
        if not (_mentions(text, "cart") or has_name_part("Cart")):
            fails.append("Webshop should include cart context/page.")
        if not (_mentions(text, "checkout") or has_name_part("Checkout")):
            fails.append("Webshop should include a checkout page or flow.")
        if not (_mentions(text, "filter") or _mentions(text, "sort")):
            fails.append("Webshop should mention filters or sorting.")
        if not _mentions(text, "currency"):
            fails.append("Webshop should mention currency/price formatting.")

    elif domain == "dashboard":
        if not (
            _mentions(text, "sidebar")
            or _mentions(text, "topbar")
            or has_name_part("Layout")
        ):
            fails.append("Dashboard should include an application layout (sidebar/topbar).")
        if not (
            _mentions(text, "chart")
            or _mentions(text, "table")
            or _mentions(text, "widget")
        ):
            fails.append("Dashboard should include widgets such as charts or tables.")
        if not (_mentions(text, "settings") or _mentions(text, "preferences")):
            fails.append("Dashboard should include a settings or preferences area.")
        if not (_mentions(text, "localStorage") or _mentions(text, "persist")):
            fails.append(
                "Dashboard should mention persisted preferences (for example localStorage)."
            )

    elif domain == "docs":
        if not (_mentions(text, "docs") or has_name_part("docs")):
            fails.append("Docs site should include docs content model and pages.")
        if not (_mentions(text, "search")):
            fails.append("Docs site should include search over documentation content.")
        if not (_mentions(text, "heading") or _mentions(text, "deep-link")):
            fails.append("Docs site should mention deep-linkable headings or TOC.")

    elif domain == "game":
        if not (
            _mentions(text, "board")
            or _mentions(text, "grid")
            or _mentions(text, "chess")
            or _mentions(text, "game state")
        ):
            fails.append("Game domain should clearly describe a playable board or game state.")
        if not (
            has_name_part("engine")
            or _mentions(text, "engine")
            or _mentions(text, "rules")
        ):
            fails.append("Game domain should include a pure engine or rule utility module.")
        if not has_type("page"):
            fails.append("Game domain should define at least one page-type file for the main view.")
        if not (
            has_name_part("Board")
            or _mentions(text, "board component")
        ):
            fails.append("Game domain should include a dedicated board or playfield component.")

    return fails


def sanity_check(plan: Dict, domain: str) -> Dict:
    """
    Perform a high-level sanity check of the planned project structure.
    Returns a dictionary with ok: bool and fails: List[str] describing issues.
    """
    if os.getenv("DEVMODE") == "true":
        return {"ok": True, "fails": []}

    files = plan.get("files") or []
    if not isinstance(files, list) or not files:
        return {"ok": False, "fails": ["files must be a non-empty list"]}

    files_by_name = _index_files(files)
    fails: List[str] = []

    for name, ftype in REQUIRED_FILES:
        if not _has_file(files_by_name, name, ftype):
            if ftype:
                fails.append(f"Missing required file: {name} (type='{ftype}').")
            else:
                fails.append(f"Missing required file: {name}.")

    main = files_by_name.get("src/main.tsx")
    if main:
        deps = main.get("internalDependencies") or []
        if not any(d == "src/App.tsx" or d.endswith("/App.tsx") for d in deps if isinstance(d, str)):
            fails.append("src/main.tsx should depend on src/App.tsx as the root component.")

    fails.extend(_light_graph_check(files))
    fails.extend(_domain_checks(plan, domain))

    return {"ok": not fails, "fails": fails}
