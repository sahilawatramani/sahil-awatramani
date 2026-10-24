"""Reviewable thresholds with physical units; no station identifiers or dates."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Thresholds:
    pressure_jump_hpa: float = 2.5
    pressure_shift_hpa: float = 4.0
    pressure_window_hours: int = 12
    pressure_group_tolerance_hpa: float = 1.5
    wind_log_shift: float = .65  # approximately a factor of 1.92
    wind_window_hours: int = 12
    wind_group_tolerance_log: float = .22
    required_window_coverage: float = .75
    robust_noise_multiplier: float = 6.0
    temperature_burst_c: float = 12.0
    temperature_burst_max_hours: int = 6
    temperature_context_hours: int = 3

    def as_dict(self):
        return asdict(self)


DEFAULTS = Thresholds()
