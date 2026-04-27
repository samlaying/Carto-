"""LLM-driven Windows VM UI exploration loop (MVP stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Action:
    type: str
    x: int | None = None
    y: int | None = None
    reason: str = ""


class ScreenshotProvider:
    def capture(self) -> bytes:
        """Return raw screenshot bytes from VM."""
        raise NotImplementedError


class Planner:
    def next_action(self, screenshot: bytes, state: dict[str, Any]) -> tuple[dict[str, Any], Action, bool]:
        """Return (page_description, action, is_current_path_done)."""
        raise NotImplementedError


class Executor:
    def run(self, action: Action) -> bool:
        """Execute UI action and return success status."""
        raise NotImplementedError


class AgentLoop:
    def __init__(self, screenshot_provider: ScreenshotProvider, planner: Planner, executor: Executor) -> None:
        self.screenshot_provider = screenshot_provider
        self.planner = planner
        self.executor = executor
        self.state: dict[str, Any] = {"visited": set(), "steps": []}

    def run(self, max_steps: int = 200) -> list[dict[str, Any]]:
        for _ in range(max_steps):
            screenshot = self.screenshot_provider.capture()
            page, action, path_done = self.planner.next_action(screenshot=screenshot, state=self.state)
            executed = self.executor.run(action)
            self.state["steps"].append(
                {
                    "page": page,
                    "action": action,
                    "executed": executed,
                    "path_done": path_done,
                }
            )
            if path_done:
                break
        return self.state["steps"]
