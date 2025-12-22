import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.run_utils.metrics import add_tokens

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def chat_json(run_id: str, where: str, **kwargs) -> Dict[str, Any]:
    resp = await client.chat.completions.create(**kwargs)
    try:
        u = resp.usage
        if u:
            add_tokens(
                run_id,
                where,
                getattr(u, "prompt_tokens", 0),
                getattr(u, "completion_tokens", 0),
            )
    except Exception:
        pass
    return resp
