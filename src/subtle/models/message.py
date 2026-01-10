from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    raw: dict

    @property
    def type(self) -> str:
        return self.raw.get("type", "unknown")

    @property
    def timestamp(self) -> datetime | None:
        ts = self.raw.get("timestamp")
        if ts:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return None

    @property
    def model(self) -> str | None:
        message = self.raw.get("message", {})
        return message.get("model")

    @property
    def input_tokens(self) -> int | None:
        message = self.raw.get("message", {})
        usage = message.get("usage", {})
        if not usage:
            return None
        return (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )

    @property
    def output_tokens(self) -> int | None:
        message = self.raw.get("message", {})
        usage = message.get("usage", {})
        if not usage:
            return None
        return usage.get("output_tokens", 0)

    @property
    def tools(self) -> list[str]:
        message = self.raw.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            return []
        tool_names = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                name = item.get("name")
                if name:
                    tool_names.append(name)
        return tool_names

    @property
    def preview(self) -> str:
        message = self.raw.get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_use":
                        text_parts.append(f"[Tool: {item.get('name', 'unknown')}]")
                    elif item.get("type") == "tool_result":
                        text_parts.append("[Tool Result]")
                elif isinstance(item, str):
                    text_parts.append(item)
            text = " ".join(text_parts)
        else:
            text = str(content)
        text = " ".join(text.split())
        max_len = 100
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
