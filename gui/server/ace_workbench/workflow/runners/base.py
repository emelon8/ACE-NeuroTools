from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Runner(ABC):
    @abstractmethod
    def check(self, root: Path, configuration: dict) -> dict: ...

    @abstractmethod
    def run(self, root: Path, configuration: dict, output: Path) -> None: ...
