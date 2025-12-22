import asyncio
import json
import os
from datetime import date
from typing import Any, Dict, List

from src.run_utils.llm import chat_json
from src.run_utils.state import get_run


class PlanValidationError(Exception):
    """Raised when plan validation fails and requires replanning"""

    def __init__(self, message: str, plan: Dict[str, Any], failures: List[str]):
        super().__init__(message)
        self.plan = plan
        self.failures = failures


MOCK = """{
  "files": [
    {
      "name": "index.html",
      "type": "config",
      "description": "HTML shell: <div id=\\"root\\"></div>, SEO/meta, Tailwind Play CDN (optional inline config). No app logic.",
      "responsibilities": [
        "Provide root DOM element for React app",
        "Include SEO meta tags and page title",
        "Load Tailwind Play CDN and optional inline config"
      ],
      "externalDependencies": [],
      "internalDependencies": [],
      "exports": []
    },
    {
      "name": "package.json",
      "type": "config",
      "description": "Project manifest for React 18 + TypeScript; scripts for dev/build if needed.",
      "responsibilities": [
        "Describe npm metadata, scripts and dependencies",
        "Pin React, ReactDOM and TypeScript versions"
      ],
      "externalDependencies": [],
      "internalDependencies": [],
      "exports": []
    },
    {
      "name": "tsconfig.json",
      "type": "config",
      "description": "TS config suitable for React 18 / TSX.",
      "responsibilities": [
        "Configure TypeScript compiler for React 18",
        "Enable strict type-checking where reasonable"
      ],
      "externalDependencies": [],
      "internalDependencies": [],
      "exports": []
    },
    {
      "name": "src/main.tsx",
      "type": "entry",
      "description": "React 18 entry. createRoot(document.getElementById('root')!) and render <App/>.",
      "responsibilities": [
        "Bootstraps React app into #root",
        "Wraps <App /> in React.StrictMode"
      ],
      "externalDependencies": ["react", "react-dom/client"],
      "internalDependencies": ["src/App.tsx"],
      "exports": [
        {
          "name": "default",
          "kind": "entry",
          "propsInterface": "none",
          "signature": "(): void",
          "description": "Entry module that mounts the React tree"
        }
      ]
    },
    {
      "name": "src/index.tsx",
      "type": "component",
      "description": "Barrel re-export of App to satisfy entry-presence needs.",
      "responsibilities": [
        "Re-export App as default for tooling compatibility"
      ],
      "externalDependencies": [],
      "internalDependencies": ["src/App.tsx"],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "AppProps",
          "signature": "(props: AppProps) => JSX.Element",
          "description": "Default export that forwards to App"
        }
      ]
    },
    {
      "name": "src/router.ts",
      "type": "router",
      "description": "Hash router utilities: useHashRoute (hook) parses location.hash; navigate and routeTo helpers. Routes: '/' -> src/pages/Home.tsx, '/blog' -> src/pages/Blog.tsx, '/docs' -> src/pages/Doc.tsx, '/search' -> src/pages/Search.tsx, '/sitemap' -> src/pages/Sitemap.tsx.",
      "responsibilities": [
        "Listen to hash changes and expose current route",
        "Provide helpers to navigate between routes"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": [
        "src/pages/Home.tsx",
        "src/pages/Blog.tsx",
        "src/pages/Doc.tsx",
        "src/pages/Search.tsx",
        "src/pages/Sitemap.tsx"
      ],
      "exports": [
        {
          "name": "useHashRoute",
          "kind": "hook",
          "propsInterface": "none",
          "signature": "() => { path: string; query: URLSearchParams }",
          "description": "Custom hook exposing current hash path and query"
        },
        {
          "name": "navigate",
          "kind": "util",
          "propsInterface": "none",
          "signature": "(path: string) => void",
          "description": "Programmatic navigation helper that updates location.hash"
        },
        {
          "name": "routeTo",
          "kind": "util",
          "propsInterface": "none",
          "signature": "(name: 'home' | 'blog' | 'docs' | 'search' | 'sitemap', params?: Record<string, string>) => void",
          "description": "Named route helper mapping logical route names to hash paths"
        }
      ]
    },
    {
      "name": "src/components/Header.tsx",
      "type": "component",
      "description": "Top navigation with links to #/, #/blog, #/docs, #/search, #/sitemap. Search input pushes to #/search?q=...",
      "responsibilities": [
        "Render brand/title and main navigation links",
        "Provide search input that updates search route"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": ["src/router.ts"],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "HeaderProps",
          "signature": "(props: HeaderProps) => JSX.Element",
          "description": "Top app header with navigation and search"
        }
      ]
    },
    {
      "name": "src/components/Footer.tsx",
      "type": "component",
      "description": "Simple footer visible on all routes.",
      "responsibilities": [
        "Display app footer with muted text",
        "Show current year and simple links if needed"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": [],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "FooterProps",
          "signature": "(props: FooterProps) => JSX.Element",
          "description": "Global footer for the application"
        }
      ]
    },
    {
      "name": "src/pages/Home.tsx",
      "type": "page",
      "description": "Todo app: add/toggle/delete with localStorage('todos'). Minimal state kept in this file.",
      "responsibilities": [
        "Render todo list UI with add/toggle/delete",
        "Persist todos to localStorage and hydrate on load"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": [],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "HomePageProps",
          "signature": "(props: HomePageProps) => JSX.Element",
          "description": "Home page showing the todo application"
        }
      ]
    },
    {
      "name": "src/pages/Blog.tsx",
      "type": "page",
      "description": "Blog list and simple detail (by slug in hash). Renders Markdown-ish content from content model.",
      "responsibilities": [
        "List available blog posts",
        "Render a selected blog post based on slug"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": ["src/content/blog.ts", "src/router.ts"],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "BlogPageProps",
          "signature": "(props: BlogPageProps) => JSX.Element",
          "description": "Blog index and detail page"
        }
      ]
    },
    {
      "name": "src/pages/Doc.tsx",
      "type": "page",
      "description": "Docs list and detail (by slug). Renders Markdown-ish content from content model.",
      "responsibilities": [
        "List docs sections and pages",
        "Render a selected doc based on slug"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": ["src/content/docs.ts", "src/router.ts"],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "DocPageProps",
          "signature": "(props: DocPageProps) => JSX.Element",
          "description": "Documentation list and detail page"
        }
      ]
    },
    {
      "name": "src/pages/Search.tsx",
      "type": "page",
      "description": "Search across todos (from localStorage), blog, and docs using a simple index over titles/body.",
      "responsibilities": [
        "Provide unified search input for in-app content",
        "Show grouped results for todos, blog posts and docs"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": ["src/content/blog.ts", "src/content/docs.ts"],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "SearchPageProps",
          "signature": "(props: SearchPageProps) => JSX.Element",
          "description": "Search page for all in-app content"
        }
      ]
    },
    {
      "name": "src/pages/Sitemap.tsx",
      "type": "page",
      "description": "Renders a sitemap XML string based on known routes/content and provides a download link.",
      "responsibilities": [
        "Generate sitemap XML string from known routes",
        "Offer copy/download UX for the generated sitemap"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": ["src/content/blog.ts", "src/content/docs.ts"],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "SitemapPageProps",
          "signature": "(props: SitemapPageProps) => JSX.Element",
          "description": "Sitemap generator page"
        }
      ]
    },
    {
      "name": "src/content/blog.ts",
      "type": "data",
      "description": "Static blog content model: array of { slug, title, excerpt, body }.",
      "responsibilities": [
        "Define strongly-typed blog post model",
        "Expose static list of demo blog posts"
      ],
      "externalDependencies": [],
      "internalDependencies": [],
      "exports": [
        {
          "name": "BLOG_POSTS",
          "kind": "data",
          "propsInterface": "BlogPost",
          "signature": "readonly BlogPost[]",
          "description": "Static list of blog post data"
        }
      ]
    },
    {
      "name": "src/content/docs.ts",
      "type": "data",
      "description": "Static docs content model: array of { slug, title, body, section }.",
      "responsibilities": [
        "Define strongly-typed docs model",
        "Expose static list of documentation pages"
      ],
      "externalDependencies": [],
      "internalDependencies": [],
      "exports": [
        {
          "name": "DOCS",
          "kind": "data",
          "propsInterface": "DocPage",
          "signature": "readonly DocPage[]",
          "description": "Static list of docs page data"
        }
      ]
    },
    {
      "name": "src/util/seo.ts",
      "type": "util",
      "description": "setMeta({ title, description }) helper updates document.title and meta[name='description'].",
      "responsibilities": [
        "Provide simple SEO helper for title + description",
        "Avoid duplicating document manipulation logic"
      ],
      "externalDependencies": [],
      "internalDependencies": [],
      "exports": [
        {
          "name": "setMeta",
          "kind": "util",
          "propsInterface": "SeoParams",
          "signature": "(params: SeoParams) => void",
          "description": "Utility for updating document title and meta description"
        }
      ]
    },
    {
      "name": "src/App.tsx",
      "type": "component",
      "description": "App shell with Header/Footer. Hash-based routing to Home, Blog, Doc, Search, Sitemap. Uses setMeta per route.",
      "responsibilities": [
        "Compose global layout with header and footer",
        "Resolve current route and render active page",
        "Call SEO helper when route changes"
      ],
      "externalDependencies": ["react"],
      "internalDependencies": [
        "src/router.ts",
        "src/components/Header.tsx",
        "src/components/Footer.tsx",
        "src/pages/Home.tsx",
        "src/pages/Blog.tsx",
        "src/pages/Doc.tsx",
        "src/pages/Search.tsx",
        "src/pages/Sitemap.tsx",
        "src/util/seo.ts"
      ],
      "exports": [
        {
          "name": "default",
          "kind": "component",
          "propsInterface": "AppProps",
          "signature": "(props: AppProps) => JSX.Element",
          "description": "Root application component and router shell"
        }
      ]
    }
  ],
  "style": "Clean, minimal Tailwind UI with soft neutral background, rounded-lg cards, subtle shadows, responsive layout, and clear typographic hierarchy. Use consistent spacing scale, focus-visible rings and hover states for all interactive elements.",
  "summary": "A small content-focused React SPA with a todo home page, embedded blog/docs content, search, and a generated sitemap, styled as a clean, minimal Tailwind-powered website."
}"""


PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "component",
                            "page",
                            "hook",
                            "context",
                            "data",
                            "style",
                            "util",
                            "router",
                            "entry",
                            "config",
                        ],
                    },
                    "description": {"type": "string"},
                    "responsibilities": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "props": {"type": "array", "items": {"type": "string"}},
                    "externalDependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "internalDependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "exports": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "kind": {"type": "string"},
                                "propsInterface": {"type": "string"},
                                "description": {"type": "string"},
                                "signature": {"type": "string"},
                            },
                            "required": [
                                "name",
                                "kind",
                                "propsInterface",
                                "description",
                                "signature",
                            ],
                        },
                    },
                },
                "required": [
                    "name",
                    "type",
                    "description",
                    "responsibilities",
                    "externalDependencies",
                    "internalDependencies",
                    "exports",
                ],
            },
        },
        "style": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["files", "style", "summary"],
}


BASE_SYS = (
    "You are a senior project planner for a React 18 + TypeScript app that runs in an in-browser bundler (Sandpack). "
    "Your job is to return a COMPLETE, UNAMBIGUOUS multi-file PLAN **as JSON only** that strictly matches the schema. "
    "Do not include markdown fences, comments, or explanations—return pure JSON.\n\n"
    "STRICT FILE CONTRACT (CRITICAL):\n"
    "• Each file entry describes exactly one real file that will be generated later.\n"
    "• You MUST split dependencies into:\n"
    "  - 'internalDependencies': other files in THIS plan (paths that match their 'name' exactly).\n"
    "  - 'externalDependencies': npm packages only (e.g., 'react', 'react-dom/client').\n"
    "• The 'exports' array MUST contain objects, not just strings. For each export you MUST provide:\n"
    "  - 'name': the exported symbol name (or 'default'),\n"
    "  - 'kind': one of 'component' | 'hook' | 'context' | 'util' | 'type' | 'data' | 'config' | 'router' | 'entry',\n"
    "  - 'signature': a brief human-readable description of its TypeScript shape or function signature,\n"
    "  - 'description': what this export is for in the app.\n"
    "• Filenames and import paths must be consistent and buildable. No placeholders. No magic. No missing extensions.\n"
    "• No circular dependencies unless explicitly unavoidable and documented in 'description'. Prefer a DAG.\n"
    "• Dependency way: domain & util → context → router → pages → smaller UI components.\n\n"
    "GLOBAL FIELDS (TOP-LEVEL):\n"
    "• 'style': a concise but concrete description of the overall UI/UX style to be implemented with Tailwind CSS. All components must be 'container-aware' and follow this style"
    "(colors, spacing, typography, components feel).\n"
    "• 'summary': a short, user-facing description of what the generated app will do.\n\n"
    "HARD REQUIREMENTS:\n"
    "0) Do not make circular dependencies!\n"
    "1) Use MULTIPLE .ts/.tsx files under src/ (no inline Babel, no UMD, no <script type='text/babel'>).\n"
    "2) index.html contains ONLY #root, SEO/meta, and Tailwind Play CDN (+ optional inline tailwind config). No app logic.\n"
    "3) Entry MUST be src/main.tsx using React 18 createRoot and importing src/App.tsx.\n"
    "4) Include package.json and tsconfig.json for React 18 + TypeScript.\n"
    "5) Keep responsibilities small (components/, pages/, hooks/, context/, util/). Use clear, unique names.\n"
    "6) Every file MUST have correct extension and explicit exports/imports that match the plan.\n"
    "7) No external network calls or remote modules at runtime; everything must bundle in-browser.\n"
    "8) Tailwind comes ONLY from the Play CDN in index.html. No PostCSS build steps.\n"
    "9) Core domain models (e.g. Product, GameState, RouteConfig) MUST live in 1–2 dedicated data/util files "
    "(e.g. 'src/domain/models.ts') and other files MUST import these types rather than redefining them.\n"
    "10) At least one router file (type='router') under src/ MUST define the route table in its description: "
    "for each route give path + page component file name.\n\n"
    "OUTPUT RULES:\n"
    "• Return ONLY JSON that matches the provided schema.\n"
    "• 'files' must be a non-empty array of file entries.\n"
    "• Each file entry MUST have: name, type, description, responsibilities, internalDependencies, externalDependencies, exports.\n"
    "• All paths must be valid for a case-sensitive filesystem.\n"
    "• Be concise but complete: the plan must be runnable without guessing.\n"
)


REQUIRED_FILES = [
    "index.html",
    "package.json",
    "tsconfig.json",
    "src/App.tsx",
    "src/main.tsx",
]


DOMAIN_HINTS = {
    "website": (
        "Layout shell (Header, Footer), meta/SEO handling, simple hash routing, at least Home + Blog/Docs pages, "
        "embedded content model (Markdown/JSON), basic search across content, sitemap stub route."
    ),
    "webshop": (
        "Product model + mock data, catalog grid + filters/sort, product detail page, cart context (add/remove/totals), "
        "checkout stub page with route guard, currency/price util."
    ),
    "dashboard": (
        "Auth stub, sidebar + topbar layout, 2–3 widgets (charts/tables) with mock data, data-fetching util that can be swapped, "
        "settings page with persisted preferences (localStorage)."
    ),
    "docs": (
        "Docs layout with sidebar TOC, Markdown or MD-like content model, search over headings/body, deep-linkable headings, "
        "sitemap and basic theming (light/dark)."
    ),
    "game": (
        "Canvas element, game loop with requestAnimationFrame, input abstraction (keyboard/mouse), simple entity/state system, "
        "restart/pause controls, minimal collision or scoring. Keep code split: engine util vs scene/game objects."
    ),
    "general": (
        "Balanced defaults: small router, layout, a couple of pages/screens, a shared state/context example, and a util or two."
    ),
}

TAILWIND_NOTE = (
    "Load Tailwind **Play CDN** in index.html before your app script; optionally include inline tailwind config. "
    "Do not use PostCSS or external build steps."
)


def make_prompt(domain: str, description: str) -> str:
    required = "\n".join(f"- {p}" for p in REQUIRED_FILES)
    domain_text = DOMAIN_HINTS.get(domain, DOMAIN_HINTS["general"])
    return (
        f"Domain: {domain}\n\n"
        f"Project description:\n{description}\n\n"
        "Constraints:\n"
        "- React 18 + TypeScript (.tsx) running in an in-browser bundler (Sandpack)\n"
        "- Tailwind via Play CDN in index.html (no PostCSS)\n"
        "- Hash routing preferred (no react-router dependency unless justified)\n"
        "- Deterministic routes and import paths; avoid ambiguity\n\n"
        f"Must include these files:\n{required}\n\n"
        "TOP-LEVEL FIELDS:\n"
        "- 'style': overall Tailwind-based visual style (colors, spacing, typography, component feel) that every file should follow.\n"
        "- 'summary': short user-facing explanation of what this app will do once generated.\n\n"
        "File field requirements (per file):\n"
        "- 'name': full path (e.g. 'src/components/Header.tsx').\n"
        "- 'type': one of component | page | hook | context | data | style | util | router | entry | config.\n"
        "- 'description': what this file is for in the app.\n"
        "- 'responsibilities': array of 1–3 short strings describing what this file does (and what it does NOT do).\n"
        "- 'internalDependencies': ONLY other plan file names this file imports from (paths EXACTLY matching 'name').\n"
        "- 'externalDependencies': ONLY npm package names this file imports (e.g. 'react').\n"
        "- 'exports': array of objects with 'name', 'kind', 'propsInterface', 'signature', 'description'.\n"
        "SILOS / DOMAIN MODELS:\n"
        "- Put core domain models and shared types into 1–2 dedicated files under src/domain or src/model.\n"
        "- Other files MUST import these types instead of redefining them.\n\n"
        "Router requirements:\n"
        "- At least one router file (type='router') under src/ (e.g. 'src/router.ts').\n"
        "- Its 'description' MUST include a clear route table: path -> page file name.\n\n"
        f"Domain checklist:\n{domain_text}\n\n"
        f"{TAILWIND_NOTE}\n\n"
        "In each file's 'description' field, explain everything that is critical for a future LLM to decide EXACTLY how to "
        "implement this file (not generic marketing copy).\n\n"
        f"Schema (for JSON output):\n{json.dumps(PLAN_SCHEMA, ensure_ascii=False)}"
    )


def _require_file(files: list[dict], name: str, ftype: str | None = None):
    for f in files:
        if f.get("name") == name and (ftype is None or f.get("type") == ftype):
            return
    raise AssertionError(
        f"missing required file: {name}{'' if ftype is None else f' (type={ftype})'}"
    )


def validate_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    files = plan.get("files")
    validation_failures: List[str] = []

    # top-level style and summary
    style = plan.get("style")
    summary = plan.get("summary")
    if not isinstance(style, str) or not style.strip():
        validation_failures.append("style must be a non-empty string")
    if not isinstance(summary, str) or not summary.strip():
        validation_failures.append("summary must be a non-empty string")

    if not isinstance(files, list) or not files:
        validation_failures.append("files must be a non-empty LIST")
        raise PlanValidationError(
            "Basic plan structure validation failed", plan, validation_failures
        )

    required_keys: List[str] = [
        "name",
        "type",
        "description",
        "responsibilities",
        "internalDependencies",
        "externalDependencies",
        "exports",
    ]
    allowed_types = {
        "component",
        "page",
        "hook",
        "context",
        "data",
        "style",
        "util",
        "router",
        "entry",
        "config",
    }

    for idx, f in enumerate(files):
        if not isinstance(f, dict):
            validation_failures.append(f"files[{idx}] must be an object")
            continue

        for k in required_keys:
            if k not in f:
                validation_failures.append(f"files[{idx}] missing `{k}`")

        if "type" in f and f["type"] not in allowed_types:
            validation_failures.append(f"files[{idx}].type invalid: {f['type']}")

        if "name" in f and (not isinstance(f["name"], str) or not f["name"]):
            validation_failures.append("file name must be non-empty string")
        if "description" in f and (
            not isinstance(f["description"], str) or not f["description"]
        ):
            validation_failures.append("description must be non-empty string")
        if "responsibilities" in f and (
            not isinstance(f["responsibilities"], list) or not f["responsibilities"]
        ):
            validation_failures.append("responsibilities must be non-empty list")
        if "internalDependencies" in f and not isinstance(
            f["internalDependencies"], list
        ):
            validation_failures.append("internalDependencies must be a list")
        if "externalDependencies" in f and not isinstance(
            f["externalDependencies"], list
        ):
            validation_failures.append("externalDependencies must be a list")
        if "exports" in f and not isinstance(f["exports"], list):
            validation_failures.append("exports must be a list")
        if "usedBy" in f and not isinstance(f["usedBy"], list):
            validation_failures.append("usedBy must be a list")

        if "exports" in f and isinstance(f["exports"], list):
            for e_idx, e in enumerate(f["exports"]):
                if not isinstance(e, dict):
                    validation_failures.append(
                        f"files[{idx}].exports[{e_idx}] must be an object"
                    )
                    continue
                for key in (
                    "name",
                    "kind",
                    "signature",
                    "description",
                    "propsInterface",
                ):
                    if key not in e:
                        validation_failures.append(
                            f"files[{idx}].exports[{e_idx}] missing `{key}`"
                        )
                    elif not isinstance(e[key], str) or not e[key]:
                        validation_failures.append(
                            f"files[{idx}].exports[{e_idx}].{key} must be non-empty string"
                        )

    plan_names = {f["name"] for f in files if "name" in f}

    for f in files:
        if "internalDependencies" not in f or "name" not in f:
            continue

        for dep in f["internalDependencies"]:
            if not isinstance(dep, str):
                validation_failures.append(
                    f"{f['name']}: internalDependencies entries must be strings"
                )
            elif dep not in plan_names:
                validation_failures.append(
                    f"{f['name']}: internal dependency '{dep}' not found in plan files"
                )

        if "externalDependencies" in f:
            for dep in f["externalDependencies"]:
                if not isinstance(dep, str):
                    validation_failures.append(
                        f"{f['name']}: externalDependencies entries must be strings"
                    )
                elif dep in plan_names:
                    validation_failures.append(
                        f"{f['name']}: external dependency '{dep}' looks like a plan file name; "
                        "internalDependencies must be used for plan files."
                    )

    computed_used_by: Dict[str, set] = {name: set() for name in plan_names}
    for f in files:
        name = f.get("name")
        deps = f.get("internalDependencies") or []
        if not name or not isinstance(deps, list):
            continue
        for dep in deps:
            if isinstance(dep, str) and dep in computed_used_by:
                computed_used_by[dep].add(name)

    for f in files:
        name = f.get("name")
        if not name:
            continue
        f["usedBy"] = sorted(computed_used_by.get(name, set()))

    try:
        _require_file(files, "index.html", "config")
        _require_file(files, "package.json", "config")
        _require_file(files, "tsconfig.json", "config")
        _require_file(files, "src/App.tsx")
        _require_file(files, "src/main.tsx", "entry")
    except AssertionError as e:
        validation_failures.append(str(e))

    has_router = any(
        f.get("type") == "router" and f.get("name", "").startswith("src/")
        for f in files
    )
    if not has_router:
        validation_failures.append("missing router setup file (e.g., src/router.ts)")

    if validation_failures:
        raise PlanValidationError(
            f"Plan validation failed with {len(validation_failures)} issues",
            plan,
            validation_failures,
        )

    return plan


async def plan_project(
    run_id: str, description: str, domain: str, model: str = "gpt-5.1"
) -> Dict[str, Any]:
    if os.getenv("DEVMODE") == "true":
        await asyncio.sleep(3)
        return json.loads(MOCK)

    resp = await chat_json(
        run_id,
        "planner",
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": BASE_SYS},
            {"role": "user", "content": make_prompt(domain, description)},
        ],
    )
    content = resp.choices[0].message.content
    if content is None:
        raise ValueError("No content returned from OpenAI response.")

    data = json.loads(content)
    try:
        return validate_plan(data)
    except PlanValidationError as e:
        print(f"Plan validation failed, triggering replan: {str(e)}")
        return await replan(run_id, e.plan, description, e.failures, domain, model)


async def replan(
    run_id: str,
    plan: Dict[str, Any],
    description: str,
    fails: list,
    domain: str,
    model: str = "gpt-5-mini",
) -> Dict[str, Any]:
    r = get_run(run_id)
    prompt = (
        "You must fix the plan based on the feedback and return the FULL corrected plan "
        "as JSON strictly matching the schema. Do NOT return partial plans, prose, or "
        "explanations. Keep the same multi-file structure and include all required fields.\n\n"
        f"Project description:\n{description}\n\n"
        f"Domain hint:\n{DOMAIN_HINTS.get(domain, DOMAIN_HINTS['general'])}\n\n"
        f"Schema:\n{json.dumps(PLAN_SCHEMA)}\n\n"
        f"Feedback to address (list):\n{json.dumps(fails, ensure_ascii=False)}\n\n"
        "Original plan (JSON):\n"
        f"{json.dumps(plan, ensure_ascii=False)}"
    )

    resp = await chat_json(
        run_id,
        "replanner",
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": BASE_SYS},
            {"role": "user", "content": prompt},
        ],
    )

    content = resp.choices[0].message.content
    if content is None:
        raise ValueError("No content returned from OpenAI response.")
    data = json.loads(content)
    try:
        return validate_plan(data)
    except PlanValidationError as e:
        print(f"Plan validation failed, triggering replan: {str(e)}")
        if r.get("replan_tries") > 0:
            r["replan_tries"] -= 1
            return await replan(run_id, e.plan, description, e.failures, domain, model)


async def generate_title(description: str, model: str = "gpt-5-nano") -> str:
    if os.getenv("DEVMODE") == "true":
        return "Sample Project Title" + date.today().strftime(" %Y-%m-%d")
    prompt = (
        "Generate a concise, short, descriptive title for the following project description. "
        "Maximum 50 characters. No quotes or punctuation around the title. "
        "The title should capture the essence of the app being built.\n\n"
        f"Project description:\n{description}\n\n"
        "Title:"
    )
    resp = await chat_json(
        "titlegen",
        "title_generator",
        model=model,
        response_format={"type": "text"},
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that generates concise project titles.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    title = resp.choices[0].message.content.strip().strip('"')
    return title
