from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import numpy as np


ProgressCallback = Callable[[str, float], None]


@dataclass(frozen=True, slots=True)
class AnalysisParams:
    """Parameters from the penultimate notebook version."""

    channel: str = "red"
    enhancement_method: str = "clahe"
    gaussian_sigma: float = 1.0
    clahe_clip: float = 0.03
    vessel_sigma_min: float = 1.0
    vessel_sigma_max: float = 3.0
    tophat_radius: int = 12

    threshold_method: str = "otsu"
    threshold_multiplier: float = 0.75
    manual_threshold: float = 0.3
    sauvola_window: int = 51

    min_object_size: int = 40
    hole_area: int = 40
    opening_radius: int = 0
    closing_radius: int = 1
    dilation_radius: int = 0
    erosion_radius: int = 0
    invert_mask: bool = False

    skeleton_method: str = "skeletonize"
    thin_iterations: int = 0
    prune_iterations: int = 0

    pixel_size_um: float = 1.0
    bootstrap_n: int = 20
    uncertainty_range: float = 0.10

    cluster_mode: str = "two_largest"
    manual_center_x: int = 0
    manual_center_y: int = 0
    min_cluster_area: int = 50
    max_clusters: int = 4
    sholl_radius_step_um: float = 10.0
    sholl_max_radius_um: float = 300.0

    ring_width_px: float = 1.4
    skeleton_linewidth: float = 1.2
    show_branch_colors: bool = True
    show_nodes: bool = True
    show_scale_bar: bool = True
    scale_bar_um: float = 100.0

    def validate(self) -> None:
        choices = {
            "channel": (self.channel, {"red", "green", "blue", "mean", "gray"}),
            "enhancement_method": (
                self.enhancement_method,
                {"clahe", "frangi", "sato", "meijering", "tophat", "nlm"},
            ),
            "threshold_method": (
                self.threshold_method,
                {"otsu", "yen", "li", "triangle", "sauvola", "manual"},
            ),
            "skeleton_method": (
                self.skeleton_method,
                {"skeletonize", "thin", "medial_axis"},
            ),
            "cluster_mode": (
                self.cluster_mode,
                {"auto_components", "two_largest", "single_center", "manual"},
            ),
        }
        for name, (value, allowed) in choices.items():
            if value not in allowed:
                raise ValueError(f"Недопустимое значение {name}: {value}")

        if self.pixel_size_um <= 0:
            raise ValueError("Размер пикселя должен быть больше нуля.")
        if self.sholl_radius_step_um <= 0 or self.sholl_max_radius_um <= 0:
            raise ValueError("Радиусы Sholl должны быть больше нуля.")
        if self.vessel_sigma_min <= 0 or self.vessel_sigma_max < self.vessel_sigma_min:
            raise ValueError("Sigma max должна быть не меньше Sigma min.")
        if self.sauvola_window < 3 or self.sauvola_window % 2 == 0:
            raise ValueError("Окно Sauvola должно быть нечётным числом не меньше 3.")
        if not 0 <= self.manual_threshold <= 1:
            raise ValueError("Ручной порог должен быть от 0 до 1.")
        if self.threshold_multiplier <= 0:
            raise ValueError("Множитель порога должен быть больше нуля.")
        if self.bootstrap_n < 0 or self.max_clusters < 1:
            raise ValueError("Количество итераций и центров не может быть отрицательным.")

        non_negative = (
            self.gaussian_sigma,
            self.clahe_clip,
            self.tophat_radius,
            self.min_object_size,
            self.hole_area,
            self.opening_radius,
            self.closing_radius,
            self.dilation_radius,
            self.erosion_radius,
            self.thin_iterations,
            self.prune_iterations,
            self.min_cluster_area,
            self.ring_width_px,
            self.skeleton_linewidth,
            self.scale_bar_um,
        )
        if any(value < 0 for value in non_negative):
            raise ValueError("Числовые параметры не могут быть отрицательными.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisResult:
    original: np.ndarray
    signal_raw: np.ndarray
    enhanced: np.ndarray
    binary: np.ndarray
    skeleton: np.ndarray
    threshold_value: float
    metrics: dict[str, Any]
    branches: list[dict[str, Any]] = field(default_factory=list)
    sholl: list[dict[str, Any]] = field(default_factory=list)
    sholl_summary: list[dict[str, Any]] = field(default_factory=list)
    uncertainty: list[dict[str, Any]] = field(default_factory=list)
    centers: list[dict[str, Any]] = field(default_factory=list)
    params: AnalysisParams = field(default_factory=AnalysisParams)
