from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable, List, Set

from .activation import ActivationResult


@dataclass
class RewardResult:
    delta_state: float
    delta_distance: float
    reward: float


def activation_reward(
    before: ActivationResult,
    after: ActivationResult,
    alpha: float = 1.0,
    beta: float = 0.5,
    regression_lambda: float = 0.5,
) -> RewardResult:
    gained = after.state - before.state
    lost = before.state - after.state
    delta_state = float(len(gained)) - regression_lambda * float(len(lost))
    delta_distance = float(before.frontier_distance - after.frontier_distance)
    reward = alpha * delta_state + beta * delta_distance
    return RewardResult(
        delta_state=delta_state,
        delta_distance=delta_distance,
        reward=reward,
    )


def relative_advantages(rewards: Iterable[float], eps: float = 1e-8) -> List[float]:
    values = [float(x) for x in rewards]
    if not values:
        return []
    mean = statistics.fmean(values)
    sigma = statistics.pstdev(values)
    return [(value - mean) / (sigma + eps) for value in values]

