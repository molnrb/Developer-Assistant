from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict


class PlanFile(TypedDict, total=False):
    name: str
    type: str
    description: str
    externalDependencies: List[str]
    internalDependencies: List[str]
    usedBy: List[str]
    exports: List[str]


class PlanSpec(TypedDict):
    files: List[PlanFile]


class MissingDep(TypedDict):
    file: str
    dependsOn: str


class IterationsResult(TypedDict):
    iterations: List[List[str]]
    unresolved: Dict[str, List[str] | List[MissingDep]]


def _strip_ext(p: str) -> str:
    """Remove the last extension ('.tsx', '.ts', '.jsx', '.js', etc.)."""
    if "." in p.split("/")[-1]:
        return p.rsplit(".", 1)[0]
    return p


def _norm_path(p: str) -> str:
    """
    Normalize a path-like token:
      - unify slashes
      - drop leading './'
      - also drop a single leading 'src/' if present
    """
    p = p.replace("\\", "/").lstrip("./")
    if p.startswith("src/"):
        p = p[len("src/") :]
    return p


def _file_keys(name: str) -> List[str]:
    """
    Generate matching keys for a file:
      - full (no extension), no leading './'
      - variant with possible 'src/' removal
      - basename (no dirs), all without extension
    """
    name = name.replace("\\", "/").lstrip("./")
    full_no_ext = _strip_ext(name)
    no_src_no_ext = _strip_ext(_norm_path(name))
    base_no_ext = full_no_ext.split("/")[-1]
    keys = {full_no_ext, no_src_no_ext, base_no_ext}
    return [k for k in keys if k]


def _dep_key(token: str) -> str:
    """Single normalized key for a dependency token."""
    return _strip_ext(_norm_path(token))


def _build_key_index(files_by_name: Dict[str, PlanFile]) -> Dict[str, List[str]]:
    """
    Map each key -> list of file names that can satisfy it.
    Multiple files can share a key; we’ll choose deterministically later.
    """
    idx: Dict[str, List[str]] = defaultdict(list)
    for fname in files_by_name:
        for k in _file_keys(fname):
            if fname not in idx[k]:
                idx[k].append(fname)
    return idx


def _resolve_dep(
    dep_token: str, key_index: Dict[str, List[str]], files_by_name: Dict[str, PlanFile]
) -> Optional[str]:
    """
    Resolve a dependency token to a concrete file name by:
      1) direct key match,
      2) suffix match against known keys (e.g., 'router/hashRouter' matches 'feature/router/hashRouter').
    If multiple candidates, pick the one with the *shortest* normalized key (most specific path match),
    then tiebreak by lexicographic file name for determinism.
    """
    key = _dep_key(dep_token)
    if key in key_index:
        cands = key_index[key]
        return sorted(cands)[0] if cands else None

    suffix_matches: List[Tuple[str, str]] = []
    for k, files in key_index.items():
        if k.endswith(key) or key.endswith(k):
            for f in files:
                suffix_matches.append((k, f))

    if not suffix_matches:
        return None

    suffix_matches.sort(key=lambda t: (len(t[0]), t[1]))
    return suffix_matches[0][1]


def _normalize_plan(
    plan: PlanSpec,
) -> Tuple[Dict[str, PlanFile], Dict[str, Set[str]], List[MissingDep]]:
    """Return: (files_by_name, deps_map, missing_list) with partial path matching."""
    files = plan.get("files", [])
    files_by_name: Dict[str, PlanFile] = {}
    for f in files:
        name = f.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(f"Every file needs a string 'name'. Offender: {f!r}")
        files_by_name[name] = f

    key_index = _build_key_index(files_by_name)

    deps: Dict[str, Set[str]] = {name: set() for name in files_by_name.keys()}
    missing: List[MissingDep] = []

    for name, f in files_by_name.items():
        for d in f.get("internalDependencies") or []:
            if not isinstance(d, str):
                continue

            resolved = _resolve_dep(d, key_index, files_by_name)
            if resolved:
                if resolved != name:
                    deps[name].add(resolved)
            else:
                looks_like_file = ("." in d) or ("/" in d)
                if looks_like_file:
                    missing.append({"file": name, "dependsOn": d})

    return files_by_name, deps, missing


def compute_iterations(plan: PlanSpec, *, sort_layers: bool = True) -> IterationsResult:
    """
    Layered (Kahn) topological grouping. Files in the same iteration can be generated in parallel.
    """
    _, deps, missing = _normalize_plan(plan)

    indegree: Dict[str, int] = {n: 0 for n in deps}
    adj: Dict[str, Set[str]] = defaultdict(set)

    for file_name, dset in deps.items():
        indegree[file_name] = len(dset)
        for dep in dset:
            adj[dep].add(file_name)

    q: deque[str] = deque([n for n, deg in indegree.items() if deg == 0])
    visited: Set[str] = set()
    iterations: List[List[str]] = []

    while q:
        layer_cnt = len(q)
        layer: List[str] = []
        for _ in range(layer_cnt):
            u = q.popleft()
            if u in visited:
                continue
            visited.add(u)
            layer.append(u)

        for u in layer:
            for v in adj.get(u, ()):
                indegree[v] -= 1

        for n, deg in indegree.items():
            if deg == 0 and n not in visited and n not in q:
                q.append(n)

        if layer:
            iterations.append(sorted(layer) if sort_layers else layer)

    leftover = sorted([n for n in deps.keys() if n not in visited])
    if leftover:
        iterations.append(leftover)

    return {
        "iterations": iterations,
        "unresolved": {
            "missing": missing,
            "cycles": leftover,
        },
    }


def result_to_json(
    result: IterationsResult, *, ensure_ascii: bool = False, indent: int = 2
) -> str:
    return json.dumps(result, ensure_ascii=ensure_ascii, indent=indent)


def compute_iterations_from_manifest(
    manifest: List[Dict[str, Any]],
    *,
    sort_layers: bool = True,
) -> IterationsResult:
    """
    Adapter for your manifest format, e.g.:

        {
          "name": "src/components/RouterLink.tsx",
          "type": "component",
          "responsibilities": "Lightweight link component...",
          "props": [...],
          "dependencies": ["react", "../router/hashRouter.ts"],
          "usedBy": ["src/components/Header.tsx", "src/pages/HomePage.tsx"],
          "exports": ["default"]
        }

    This converts the manifest list into an internal PlanSpec and then reuses
    the existing compute_iterations() logic (same partial path matching, etc.).
    """
    files: List[PlanFile] = []

    for item in manifest:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            description = item.get("responsibilities") or ""

        external_deps = item.get("externalDependencies") or []
        internal_deps = item.get("internalDependencies") or []
        used_by = item.get("usedBy") or []
        exports = item.get("exports") or []

        pf: PlanFile = {
            "name": name,
            "type": item.get("type") or "",
            "description": description,
            "externalDependencies": (
                list(external_deps) if isinstance(external_deps, list) else []
            ),
            "internalDependencies": (
                list(internal_deps) if isinstance(internal_deps, list) else []
            ),
            "usedBy": list(used_by) if isinstance(used_by, list) else [],
            "exports": list(exports) if isinstance(exports, list) else [],
        }
        files.append(pf)

    plan: PlanSpec = {"files": files}
    return compute_iterations(plan, sort_layers=sort_layers)
