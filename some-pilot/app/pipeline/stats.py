"""Small, dependency-free statistics helpers for learning and experiments.

Bootstrap intervals use a fixed seed so reports are reproducible. With the
sample sizes this channel will have for months, intervals will usually be wide;
that is the honest answer, not a bug.
"""

import random
import statistics

BOOTSTRAP_RESAMPLES = 1000
DEFAULT_LEVEL = 0.90


def _quantile(ordered: list[float], q: float) -> float:
    if not ordered:
        raise ValueError("empty")
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def median_ci(values: list[float], level: float = DEFAULT_LEVEL, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = 0) -> tuple[float, float] | None:
    if len(values) < 3:
        return None
    rng = random.Random(seed)
    medians = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(resamples))
    tail = (1 - level) / 2
    return round(_quantile(medians, tail), 6), round(_quantile(medians, 1 - tail), 6)


def median_difference_ci(treatment: list[float], control: list[float], level: float = DEFAULT_LEVEL, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = 0) -> tuple[float, float] | None:
    """Interval for median(treatment) - median(control)."""
    if len(treatment) < 2 or len(control) < 2:
        return None
    rng = random.Random(seed)
    differences = sorted(statistics.median(rng.choices(treatment, k=len(treatment))) - statistics.median(rng.choices(control, k=len(control))) for _ in range(resamples))
    tail = (1 - level) / 2
    return round(_quantile(differences, tail), 6), round(_quantile(differences, 1 - tail), 6)


def interpolate(points: list[tuple[float, float]], x: float) -> float | None:
    """Linear interpolation on (x, y) points sorted by x; clamps to the ends."""
    if not points:
        return None
    ordered = sorted(points)
    if x <= ordered[0][0]:
        return ordered[0][1]
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return ordered[-1][1]
