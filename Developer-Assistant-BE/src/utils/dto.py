from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Action:
    action: str
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    reason: str = ""
