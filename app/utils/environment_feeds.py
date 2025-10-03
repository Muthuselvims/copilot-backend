from __future__ import annotations

from typing import Callable, Dict, Any


class EnvironmentFeeds:
    def __init__(self) -> None:
        self._feeds: Dict[str, Callable[[], Any]] = {}

    def register(self, name: str, provider: Callable[[], Any]) -> None:
        self._feeds[name] = provider

    def read(self, name: str) -> Any:
        provider = self._feeds.get(name)
        if not provider:
            return None
        return provider()


_GLOBAL_FEEDS = EnvironmentFeeds()


def get_environment_feeds() -> EnvironmentFeeds:
    return _GLOBAL_FEEDS


