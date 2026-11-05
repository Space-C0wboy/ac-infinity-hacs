from __future__ import annotations

from dataclasses import dataclass

from .coordinator import ACInfinityDataUpdateCoordinator
from .device import ACInfinityDevice


@dataclass
class ACInfinityData:
    title: str
    device: ACInfinityDevice
    coordinator: ACInfinityDataUpdateCoordinator
