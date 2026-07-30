from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage as ndi
from skimage import exposure, filters, io, measure, morphology, restoration
from skimage.filters import frangi, meijering, sato
from skimage.morphology import medial_axis, skeletonize, thin

from .models import AnalysisParams, AnalysisResult, ProgressCallback


NEIGHBOR_KERNEL = np.array(
    [[1, 1, 1], [1, 10, 1], [1, 1, 1]],
    dtype=np.uint8,
)
CONNECTIVITY_8 = np.ones((3, 3), dtype=np.uint8)


def load_image(path: str | Path) -> np.ndarray:
    """Load the first 2-D plane from a common microscopy image."""

    image = np.asarray(io.imread(str(path)))
    while image.ndim > 3:
        image = image[0]
    if image.ndim not in (2, 3):
        raise ValueError("Поддерживаются двумерные серые и RGB-изображения.")
    if image.size == 0:
        raise ValueError("Изображение пустое.")
    return image


def normalize01(array: np.ndarray) -> np.ndarray:
    result = np.asarray(array, dtype=np.float32)
    finite = np.isfinite(result)
    if not finite.any():
        raise ValueError("Изображение не содержит конечных значений.")
    if not finite.all():
        result = result.copy()
        result[~finite] = float(np.nanmedian(result[finite]))
    low = float(result.min())
    high = float(result.max())
    if high <= low:
        return np.zeros_like(result, dtype=np.float32)
    return (result - low) / (high - low)


def get_channel(image: np.ndarray, channel: str) -> np.ndarray:
    if image.ndim == 2:
        return normalize01(image)

    if image.shape[2] < 3:
        return normalize01(image[..., 0])

    rgb = image[..., :3].astype(np.float32, copy=False)
    if channel == "red":
        signal = rgb[..., 0]
    elif channel == "green":
        signal = rgb[..., 1]
    elif channel == "blue":
        signal = rgb[..., 2]
    elif channel == "mean":
        signal = rgb.mean(axis=2)
    else:
        signal = (
            0.2126 * rgb[..., 0]
            + 0.7152 * rgb[..., 1]
            + 0.0722 * rgb[..., 2]
        )
    return normalize01(signal)


def _remove_small_objects(binary: np.ndarray, minimum: int) -> np.ndarray:
    if minimum <= 1:
        return binary
    try:
        return morphology.remove_small_objects(
            binary, max_size=minimum - 1, connectivity=2
        )
    except TypeError:  # scikit-image < 0.26
        return morphology.remove_small_objects(
            binary, min_size=minimum, connectivity=2
        )


def _remove_small_holes(binary: np.ndarray, minimum: int) -> np.ndarray:
    if minimum <= 1:
        return binary
    try:
        return morphology.remove_small_holes(
            binary, max_size=minimum - 1, connectivity=2
        )
    except TypeError:  # scikit-image < 0.26
        return morphology.remove_small_holes(
            binary, area_threshold=minimum, connectivity=2
        )


def _notify(callback: ProgressCallback | None, text: str, fraction: float) -> None:
    if callback is not None:
        callback(text, max(0.0, min(1.0, fraction)))


class AnalysisEngine:
    def __init__(self, params: AnalysisParams):
        params.validate()
        self.params = params

    def analyze(
        self,
        image: np.ndarray,
        progress: ProgressCallback | None = None,
    ) -> AnalysisResult:
        _notify(progress, "Выделение канала…", 0.05)
        original = np.asarray(image)
        signal_raw = get_channel(original, self.params.channel)

        _notify(progress, "Усиление сигнала…", 0.14)
        enhanced = self.enhance_signal(signal_raw)

        _notify(progress, "Построение маски…", 0.25)
        binary, threshold_value = self.make_binary(enhanced)

        _notify(progress, "Скелетизация…", 0.37)
        skeleton = self.skeleton_from_binary(binary)

        _notify(progress, "Расчёт морфометрии…", 0.48)
        metrics, branches = self.skeleton_graph_analysis(
            skeleton, binary, enhanced, include_branches=True
        )

        _notify(progress, "Sholl-анализ…", 0.59)
        sholl, sholl_summary, centers = self.sholl_analysis_multi(
            skeleton, binary
        )

        _notify(progress, "Оценка устойчивости…", 0.68)
        uncertainty = self.uncertainty_analysis(
            enhanced,
            progress=progress,
            progress_start=0.68,
            progress_end=0.96,
        )

        metrics.update(
            {
                "threshold_value": float(threshold_value),
                "threshold_method": self.params.threshold_method,
                "enhancement_method": self.params.enhancement_method,
                "skeleton_method": self.params.skeleton_method,
                "pixel_size_um": float(self.params.pixel_size_um),
                "sholl_centers": len(centers),
            }
        )
        if sholl_summary:
            metrics["sholl_max_intersections_mean"] = float(
                np.mean([row["max_intersections"] for row in sholl_summary])
            )
            metrics["sholl_auc_mean"] = float(
                np.mean([row["sholl_auc"] for row in sholl_summary])
            )
            metrics["sholl_total_intersections_mean"] = float(
                np.mean([row["total_intersections"] for row in sholl_summary])
            )

        _notify(progress, "Готово", 1.0)
        return AnalysisResult(
            original=original,
            signal_raw=signal_raw,
            enhanced=enhanced,
            binary=binary,
            skeleton=skeleton,
            threshold_value=float(threshold_value),
            metrics=metrics,
            branches=branches,
            sholl=sholl,
            sholl_summary=sholl_summary,
            uncertainty=uncertainty,
            centers=centers,
            params=self.params,
        )

    def enhance_signal(self, signal: np.ndarray) -> np.ndarray:
        p = self.params
        x = exposure.equalize_adapthist(signal, clip_limit=p.clahe_clip)

        if p.enhancement_method in {"frangi", "sato", "meijering"}:
            sigmas = np.arange(
                p.vessel_sigma_min,
                p.vessel_sigma_max + 0.25,
                0.5,
            )
            if p.enhancement_method == "frangi":
                vessels = frangi(x, sigmas=sigmas, black_ridges=False)
            elif p.enhancement_method == "sato":
                vessels = sato(x, sigmas=sigmas, black_ridges=False)
            else:
                vessels = meijering(x, sigmas=sigmas, black_ridges=False)
            x = normalize01(x + vessels)
        elif p.enhancement_method == "tophat":
            background = morphology.opening(x, morphology.disk(p.tophat_radius))
            x = normalize01(x - background)
        elif p.enhancement_method == "nlm":
            sigma_est = float(
                np.mean(restoration.estimate_sigma(x, channel_axis=None))
            )
            if sigma_est > 0:
                x = restoration.denoise_nl_means(
                    x,
                    h=0.8 * sigma_est,
                    fast_mode=True,
                    patch_size=5,
                    patch_distance=6,
                    channel_axis=None,
                )
            x = normalize01(x)

        if p.gaussian_sigma > 0:
            x = filters.gaussian(
                x, sigma=p.gaussian_sigma, preserve_range=True
            )
        return normalize01(x)

    def get_threshold(self, signal: np.ndarray) -> float:
        method = self.params.threshold_method
        if method == "otsu":
            return float(filters.threshold_otsu(signal))
        if method == "yen":
            return float(filters.threshold_yen(signal))
        if method == "li":
            return float(filters.threshold_li(signal))
        if method == "triangle":
            return float(filters.threshold_triangle(signal))
        if method == "manual":
            return float(self.params.manual_threshold)
        raise ValueError(f"Порог {method} не является глобальным.")

    def make_binary(
        self,
        signal: np.ndarray,
        threshold_scale: float = 1.0,
    ) -> tuple[np.ndarray, float]:
        p = self.params
        if p.threshold_method == "sauvola":
            threshold_map = filters.threshold_sauvola(
                signal, window_size=p.sauvola_window
            )
            binary = signal > threshold_map * threshold_scale
            threshold_value = float(np.mean(threshold_map))
        else:
            threshold_value = self.get_threshold(signal)
            multiplier = (
                1.0
                if p.threshold_method == "manual"
                else p.threshold_multiplier
            )
            binary = signal > threshold_value * multiplier * threshold_scale

        if p.invert_mask:
            binary = ~binary
        if p.opening_radius:
            binary = morphology.opening(
                binary, morphology.disk(p.opening_radius)
            )
        if p.closing_radius:
            binary = morphology.closing(
                binary, morphology.disk(p.closing_radius)
            )
        if p.dilation_radius:
            binary = morphology.dilation(
                binary, morphology.disk(p.dilation_radius)
            )
        if p.erosion_radius:
            binary = morphology.erosion(
                binary, morphology.disk(p.erosion_radius)
            )

        binary = _remove_small_objects(binary.astype(bool), p.min_object_size)
        binary = _remove_small_holes(binary, p.hole_area)
        return binary.astype(bool, copy=False), threshold_value

    @staticmethod
    def neighbor_count(skeleton: np.ndarray) -> np.ndarray:
        skeleton_u8 = skeleton.astype(np.uint8, copy=False)
        convolution = ndi.convolve(
            skeleton_u8,
            NEIGHBOR_KERNEL,
            mode="constant",
            cval=0,
        )
        return convolution - 10 * skeleton_u8

    def prune_endpoints(
        self, skeleton: np.ndarray, iterations: int
    ) -> np.ndarray:
        pruned = skeleton.copy()
        for _ in range(iterations):
            endpoints = pruned & (self.neighbor_count(pruned) == 1)
            if not endpoints.any():
                break
            pruned[endpoints] = False
        return pruned

    def skeleton_from_binary(self, binary: np.ndarray) -> np.ndarray:
        p = self.params
        if p.skeleton_method == "skeletonize":
            result = skeletonize(binary)
        elif p.skeleton_method == "thin":
            iterations = p.thin_iterations or None
            result = thin(binary, max_num_iter=iterations)
        else:
            result = medial_axis(binary)

        if p.prune_iterations:
            result = self.prune_endpoints(result, p.prune_iterations)
        return result.astype(bool, copy=False)

    @staticmethod
    def _component_edge_length(component: np.ndarray) -> float:
        horizontal = np.count_nonzero(component[:, :-1] & component[:, 1:])
        vertical = np.count_nonzero(component[:-1, :] & component[1:, :])
        diagonal_a = np.count_nonzero(component[:-1, :-1] & component[1:, 1:])
        diagonal_b = np.count_nonzero(component[:-1, 1:] & component[1:, :-1])
        return float(
            horizontal + vertical + math.sqrt(2.0) * (diagonal_a + diagonal_b)
        )

    def skeleton_graph_analysis(
        self,
        skeleton: np.ndarray,
        binary: np.ndarray,
        signal: np.ndarray,
        *,
        include_branches: bool,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        neighbors = self.neighbor_count(skeleton)
        endpoint_mask = skeleton & (neighbors == 1)
        junction_mask = skeleton & (neighbors >= 3)
        endpoint_count = int(
            ndi.label(endpoint_mask, structure=CONNECTIVITY_8)[1]
        )
        junction_count = int(
            ndi.label(junction_mask, structure=CONNECTIVITY_8)[1]
        )

        branch_pixels = skeleton & ~(endpoint_mask | junction_mask)
        labeled_branches, branch_count = ndi.label(
            branch_pixels, structure=CONNECTIVITY_8
        )
        branches: list[dict[str, Any]] = []
        px_um = self.params.pixel_size_um

        if include_branches:
            objects = ndi.find_objects(labeled_branches)
            for label_id, bounds in enumerate(objects, start=1):
                if bounds is None:
                    continue
                component = labeled_branches[bounds] == label_id
                count = int(component.sum())
                if count < 2:
                    continue

                local_coords = np.argwhere(component)
                origin_y = bounds[0].start or 0
                origin_x = bounds[1].start or 0
                ys = local_coords[:, 0] + origin_y
                xs = local_coords[:, 1] + origin_x
                length_px = self._component_edge_length(component)
                if length_px <= 0:
                    length_px = float(count)

                local_neighbors = self.neighbor_count(component)
                ends = np.argwhere(component & (local_neighbors <= 1))
                if len(ends) >= 2:
                    start = ends[0]
                    squared = np.sum((ends - start) ** 2, axis=1)
                    finish = ends[int(np.argmax(squared))]
                    euclidean_px = float(np.linalg.norm(finish - start))
                else:
                    euclidean_px = float(
                        math.hypot(
                            int(xs.max()) - int(xs.min()),
                            int(ys.max()) - int(ys.min()),
                        )
                    )

                branches.append(
                    {
                        "branch_id": len(branches) + 1,
                        "pixel_count": count,
                        "length_px": length_px,
                        "length_um": length_px * px_um,
                        "mean_intensity": float(np.mean(signal[ys, xs])),
                        "tortuosity_approx": length_px
                        / max(euclidean_px, 1e-6),
                    }
                )

        mask_area = int(binary.sum())
        skeleton_pixels = int(skeleton.sum())
        distance = ndi.distance_transform_edt(binary)
        diameters_px = 2.0 * distance[skeleton]
        branch_lengths_um = [row["length_um"] for row in branches]
        tortuosities = [row["tortuosity_approx"] for row in branches]
        object_count = int(
            ndi.label(binary, structure=CONNECTIVITY_8)[1]
        )

        metrics: dict[str, Any] = {
            "mask_area_px": mask_area,
            "mask_area_um2": mask_area * px_um * px_um,
            "skeleton_length_px": skeleton_pixels,
            "skeleton_length_um": skeleton_pixels * px_um,
            "endpoints": endpoint_count,
            "junctions": junction_count,
            "branches": len(branches) if include_branches else branch_count,
            "objects": object_count,
            "mean_branch_length_um": float(np.mean(branch_lengths_um))
            if branch_lengths_um
            else 0.0,
            "median_branch_length_um": float(np.median(branch_lengths_um))
            if branch_lengths_um
            else 0.0,
            "mean_tortuosity": float(np.mean(tortuosities))
            if tortuosities
            else 0.0,
            "mean_diameter_px": float(np.mean(diameters_px))
            if diameters_px.size
            else 0.0,
            "mean_diameter_um": float(np.mean(diameters_px) * px_um)
            if diameters_px.size
            else 0.0,
            "mean_intensity_on_mask": float(np.mean(signal[binary]))
            if mask_area
            else 0.0,
            "total_intensity_on_mask": float(np.sum(signal[binary])),
            "network_density_length_per_area": skeleton_pixels
            / max(mask_area, 1),
        }
        return metrics, branches

    def get_node_masks(
        self, skeleton: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        neighbors = self.neighbor_count(skeleton)
        return skeleton & (neighbors == 1), skeleton & (neighbors >= 3)

    def extract_skeleton_segments(
        self, skeleton: np.ndarray
    ) -> tuple[list[np.ndarray], np.ndarray, np.ndarray]:
        endpoints, junctions = self.get_node_masks(skeleton)
        branch_pixels = skeleton & ~(endpoints | junctions)
        labels = measure.label(branch_pixels, connectivity=2)
        segments = [
            region.coords
            for region in measure.regionprops(labels)
            if region.area >= 2
        ]
        return segments, endpoints, junctions

    def get_sholl_centers(
        self, binary: np.ndarray
    ) -> list[dict[str, Any]]:
        p = self.params
        height, width = binary.shape
        if p.cluster_mode == "manual":
            return [
                {
                    "center_id": 1,
                    "x": int(np.clip(p.manual_center_x, 0, width - 1)),
                    "y": int(np.clip(p.manual_center_y, 0, height - 1)),
                    "area_px": int(binary.sum()),
                }
            ]

        labels = measure.label(binary, connectivity=2)
        regions = measure.regionprops(labels)
        if p.cluster_mode == "single_center":
            if regions:
                largest = max(regions, key=lambda region: region.area)
                cy, cx = largest.centroid
                area = int(largest.area)
            else:
                cy, cx = height // 2, width // 2
                area = 0
            return [
                {
                    "center_id": 1,
                    "x": int(round(cx)),
                    "y": int(round(cy)),
                    "area_px": area,
                }
            ]

        regions = [
            region
            for region in regions
            if region.area >= p.min_cluster_area
        ]
        regions.sort(key=lambda region: region.area, reverse=True)
        limit = 2 if p.cluster_mode == "two_largest" else p.max_clusters
        centers = []
        for region in regions[:limit]:
            cy, cx = region.centroid
            centers.append(
                {
                    "center_id": len(centers) + 1,
                    "x": int(round(cx)),
                    "y": int(round(cy)),
                    "area_px": int(region.area),
                }
            )
        if not centers:
            centers.append(
                {
                    "center_id": 1,
                    "x": width // 2,
                    "y": height // 2,
                    "area_px": int(binary.sum()),
                }
            )
        return centers

    def sholl_analysis_multi(
        self,
        skeleton: np.ndarray,
        binary: np.ndarray,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        p = self.params
        centers = self.get_sholl_centers(binary)
        radii_um = np.arange(
            p.sholl_radius_step_um,
            p.sholl_max_radius_um + p.sholl_radius_step_um * 0.5,
            p.sholl_radius_step_um,
        )
        height, width = skeleton.shape
        max_radius_px = p.sholl_max_radius_um / p.pixel_size_um
        half_width = max(0.75, p.ring_width_px / 2.0)
        rows: list[dict[str, Any]] = []

        for center in centers:
            cx = center["x"]
            cy = center["y"]
            margin = int(math.ceil(max_radius_px + half_width))
            x0, x1 = max(0, cx - margin), min(width, cx + margin + 1)
            y0, y1 = max(0, cy - margin), min(height, cy + margin + 1)
            yy, xx = np.ogrid[y0:y1, x0:x1]
            distance_px = np.hypot(xx - cx, yy - cy)
            local_skeleton = skeleton[y0:y1, x0:x1]

            for radius_um in radii_um:
                radius_px = radius_um / p.pixel_size_um
                ring = np.abs(distance_px - radius_px) <= half_width
                intersections = int(
                    ndi.label(
                        local_skeleton & ring,
                        structure=CONNECTIVITY_8,
                    )[1]
                )
                rows.append(
                    {
                        "center_id": center["center_id"],
                        "center_x_px": cx,
                        "center_y_px": cy,
                        "radius_um": float(radius_um),
                        "intersections": intersections,
                    }
                )

        summaries: list[dict[str, Any]] = []
        for center in centers:
            center_rows = [
                row
                for row in rows
                if row["center_id"] == center["center_id"]
            ]
            if not center_rows:
                continue
            radii = np.array(
                [row["radius_um"] for row in center_rows], dtype=float
            )
            intersections = np.array(
                [row["intersections"] for row in center_rows], dtype=float
            )
            max_index = int(np.argmax(intersections))
            sample_std = (
                float(np.std(intersections, ddof=1))
                if len(intersections) > 1
                else 0.0
            )
            summaries.append(
                {
                    "center_id": center["center_id"],
                    "x_px": center["x"],
                    "y_px": center["y"],
                    "cluster_area_px": center["area_px"],
                    "max_intersections": int(intersections[max_index]),
                    "critical_radius_um": float(radii[max_index]),
                    "sholl_auc": float(np.trapezoid(intersections, radii)),
                    "total_intersections": int(intersections.sum()),
                    "mean_intersections": float(intersections.mean()),
                    "se_intersections": sample_std
                    / math.sqrt(max(len(intersections), 1)),
                }
            )
        return rows, summaries, centers

    def uncertainty_analysis(
        self,
        signal: np.ndarray,
        *,
        progress: ProgressCallback | None,
        progress_start: float,
        progress_end: float,
    ) -> list[dict[str, Any]]:
        iterations = self.params.bootstrap_n
        if iterations <= 0:
            return []

        generator = np.random.default_rng(42)
        runs: list[dict[str, float]] = []
        for index in range(iterations):
            threshold_scale = float(
                generator.uniform(
                    1.0 - self.params.uncertainty_range,
                    1.0 + self.params.uncertainty_range,
                )
            )
            noise_sigma = float(generator.uniform(0.0, 0.015))
            noisy = np.clip(
                signal + generator.normal(0.0, noise_sigma, signal.shape),
                0.0,
                1.0,
            )
            binary, _ = self.make_binary(
                noisy, threshold_scale=threshold_scale
            )
            skeleton = self.skeleton_from_binary(binary)
            metrics, _ = self.skeleton_graph_analysis(
                skeleton, binary, noisy, include_branches=False
            )
            _, sholl_summary, _ = self.sholl_analysis_multi(skeleton, binary)
            numeric = {
                key: float(value)
                for key, value in metrics.items()
                if isinstance(value, (int, float, np.integer, np.floating))
            }
            if sholl_summary:
                numeric["sholl_max_intersections_mean_centers"] = float(
                    np.mean(
                        [row["max_intersections"] for row in sholl_summary]
                    )
                )
                numeric["sholl_auc_mean_centers"] = float(
                    np.mean([row["sholl_auc"] for row in sholl_summary])
                )
                numeric["sholl_total_intersections_mean_centers"] = float(
                    np.mean(
                        [
                            row["total_intersections"]
                            for row in sholl_summary
                        ]
                    )
                )
            runs.append(numeric)
            fraction = progress_start + (
                (index + 1) / iterations
            ) * (progress_end - progress_start)
            _notify(
                progress,
                f"Оценка устойчивости: {index + 1}/{iterations}",
                fraction,
            )

        keys = sorted(set().union(*(run.keys() for run in runs)))
        summary = []
        for key in keys:
            values = np.array(
                [run[key] for run in runs if key in run], dtype=float
            )
            if values.size < 2:
                continue
            sample_std = float(np.std(values, ddof=1))
            summary.append(
                {
                    "metric": key,
                    "mean": float(values.mean()),
                    "sample_std": sample_std,
                    "standard_error": sample_std
                    / math.sqrt(values.size),
                    "ci95_low": float(np.percentile(values, 2.5)),
                    "ci95_high": float(np.percentile(values, 97.5)),
                    "iterations": int(values.size),
                }
            )
        return summary
