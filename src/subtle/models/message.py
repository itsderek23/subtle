import difflib
import re
from dataclasses import dataclass
from datetime import datetime

EXCLUDED_TOOLS = {"TodoWrite", "ExitPlanMode", "KillShell"}

COMMIT_PATTERN = re.compile(
    r"\[[\w\-/]+ ([a-f0-9]{7,})\] (.+?)(?:\n|$)"
)
GIT_STAT_PATTERN = re.compile(
    r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?"
)


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

    def _get_tool_uses(self) -> list[dict]:
        message = self.raw.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            return []
        return [
            item for item in content
            if isinstance(item, dict) and item.get("type") == "tool_use"
        ]

    def _get_tool_results(self) -> list[dict]:
        message = self.raw.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            return []
        return [
            item for item in content
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ]

    @property
    def edit_loc(self) -> dict | None:
        for tool_use in self._get_tool_uses():
            if tool_use.get("name") == "Edit":
                inp = tool_use.get("input", {})
                old_str = inp.get("old_string", "")
                new_str = inp.get("new_string", "")

                old_lines = old_str.splitlines(keepends=True)
                new_lines = new_str.splitlines(keepends=True)

                diff = difflib.unified_diff(old_lines, new_lines)

                added = 0
                removed = 0
                for line in diff:
                    if line.startswith("+") and not line.startswith("+++"):
                        added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        removed += 1

                return {"added": added, "removed": removed}
        return None

    @property
    def write_loc(self) -> int | None:
        for tool_use in self._get_tool_uses():
            if tool_use.get("name") == "Write":
                inp = tool_use.get("input", {})
                content = inp.get("content", "")
                return content.count("\n") + (1 if content else 0)
        return None

    @property
    def is_commit(self) -> bool:
        for tool_result in self._get_tool_results():
            content = tool_result.get("content", "")
            if isinstance(content, str) and COMMIT_PATTERN.search(content):
                if not tool_result.get("is_error", False):
                    return True
        return False

    @property
    def commit_info(self) -> dict | None:
        for tool_result in self._get_tool_results():
            content = tool_result.get("content", "")
            if isinstance(content, str):
                match = COMMIT_PATTERN.search(content)
                if match and not tool_result.get("is_error", False):
                    return {
                        "hash": match.group(1),
                        "message": match.group(2),
                        "timestamp": self.timestamp,
                    }
        return None

    @property
    def git_diff_loc(self) -> dict | None:
        for tool_result in self._get_tool_results():
            content = tool_result.get("content", "")
            if isinstance(content, str):
                match = GIT_STAT_PATTERN.search(content)
                if match:
                    insertions = int(match.group(2)) if match.group(2) else 0
                    deletions = int(match.group(3)) if match.group(3) else 0
                    return {"added": insertions, "removed": deletions}
        return None

    @property
    def is_rejection(self) -> bool:
        for tool_result in self._get_tool_results():
            if tool_result.get("is_error"):
                content = tool_result.get("content", "")
                if isinstance(content, str) and content.startswith("The user doesn't want to proceed"):
                    return True
        return False

    @property
    def is_tool_error(self) -> bool:
        for tool_result in self._get_tool_results():
            if tool_result.get("is_error"):
                content = tool_result.get("content", "")
                if isinstance(content, str) and "<tool_use_error>" in content:
                    return True
        return False

    @property
    def is_command_failure(self) -> bool:
        for tool_result in self._get_tool_results():
            if tool_result.get("is_error"):
                content = tool_result.get("content", "")
                if isinstance(content, str) and content.startswith("Exit code"):
                    return True
        return False

    def _has_thinking(self) -> bool:
        message = self.raw.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            return False
        return any(
            isinstance(item, dict) and item.get("type") == "thinking"
            for item in content
        )

    def _has_text_only(self) -> bool:
        message = self.raw.get("message", {})
        content = message.get("content", [])
        if not isinstance(content, list):
            return False
        has_text = any(
            isinstance(item, dict) and item.get("type") == "text"
            for item in content
        )
        has_tool_use = any(
            isinstance(item, dict) and item.get("type") == "tool_use"
            for item in content
        )
        return has_text and not has_tool_use

    def _is_skill_prompt(self, text: str) -> bool:
        return "allowed-tools:" in text and text.lstrip().startswith("---")

    def _is_slash_command(self, text: str) -> bool:
        return "<command-name>/" in text

    @property
    def breakdown_category(self) -> dict | None:
        msg_type = self.type

        if msg_type == "assistant":
            tools = self.tools
            non_excluded = [t for t in tools if t not in EXCLUDED_TOOLS]
            if non_excluded:
                return {"category": non_excluded[0], "type": "tool"}
            if self._has_thinking():
                return {"category": "assistant:thinking", "type": "assistant"}
            if self._has_text_only():
                return {"category": "assistant:text", "type": "assistant"}
            return None

        if msg_type == "user":
            message = self.raw.get("message", {})
            content = message.get("content", "")

            if isinstance(content, str):
                if self._is_slash_command(content):
                    return {"category": "user:slash_command", "type": "user"}
                return {"category": "user:human_input", "type": "user"}

            if isinstance(content, list):
                has_tool_result = any(
                    isinstance(item, dict) and item.get("type") == "tool_result"
                    for item in content
                )
                if has_tool_result:
                    return None

                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        if self._is_skill_prompt(text):
                            return None
                        if self._is_slash_command(text):
                            return {"category": "user:slash_command", "type": "user"}
                has_text = any(
                    isinstance(item, dict) and item.get("type") == "text"
                    for item in content
                )
                if has_text:
                    return {"category": "user:human_input", "type": "user"}
                return None

        return None
