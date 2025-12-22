import asyncio
import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.run_utils.llm import chat_json

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {
            "type": "string",
            "enum": ["games", "webshop", "website", "general"],
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "alt_candidates": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["domain", "confidence", "rationale"],
}

ROUTER_SYS = (
    "You classify a project description into a target planner domain. "
    "Return only JSON for the given schema. Be decisive but honest about confidence."
)


def _heuristic_router(text: str):
    t = text.lower()
    if any(
        k in t
        for k in ["cart", "checkout", "product", "sku", "stripe", "filter", "catalog"]
    ):
        return {
            "domain": "webshop",
            "confidence": 0.55,
            "alt_candidates": ["website"],
            "rationale": "ecommerce terms present",
        }
    if any(
        k in t
        for k in ["canvas", "sprite", "enemy", "physics", "score", "level", "game loop"]
    ):
        return {
            "domain": "games",
            "confidence": 0.55,
            "alt_candidates": ["website"],
            "rationale": "game dev terms present",
        }
    if any(
        k in t for k in ["landing", "blog", "docs", "marketing", "portfolio", "seo"]
    ):
        return {
            "domain": "website",
            "confidence": 0.55,
            "alt_candidates": ["webshop"],
            "rationale": "content/marketing site terms",
        }
    return {
        "domain": "general",
        "confidence": 0.4,
        "alt_candidates": ["website"],
        "rationale": "no strong domain cues",
    }


async def route_domain(
    run_id: str, description: str, model: str = "gpt-5-mini"
) -> dict:
    if os.getenv("DEVMODE") == "true":
        await asyncio.sleep(3)
        return _heuristic_router("general fallback")
    try:
        resp = await chat_json(
            run_id,
            "router",
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ROUTER_SYS},
                {
                    "role": "user",
                    "content": f"Classify this description:\n\n{description}\n\nSchema: {json.dumps(ROUTER_SCHEMA)}",
                },
            ],
        )
        data = json.loads(resp.choices[0].message.content)

        if data.get("domain") not in ["games", "webshop", "website", "general"]:
            raise ValueError("invalid domain")
        if "confidence" not in data:
            data["confidence"] = 0.5
        if "alt_candidates" not in data:
            data["alt_candidates"] = []
        return data
    except Exception:

        return _heuristic_router(description)
