from __future__ import annotations

import csv
import html
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

from .core import CONNECTIVITY_8, normalize01
from .i18n import column_labels, metric_labels, translate
from .models import AnalysisResult


CENTER_COLORS = (
    "#00e5ff",
    "#ffe600",
    "#ff00d4",
    "#00ff4c",
    "#ff7b00",
    "#9d00ff",
    "#ff3b3b",
    "#00ffcc",
    "#b6ff00",
    "#ff9ed8",
    "#ffffff",
    "#00a2ff",
)

def to_uint8(array: np.ndarray) -> np.ndarray:
    source = np.asarray(array)
    if source.dtype == np.uint8:
        return source
    if source.dtype == bool:
        return source.astype(np.uint8) * 255
    return np.round(normalize01(source) * 255.0).astype(np.uint8)


def image_to_pil(array: np.ndarray) -> Image.Image:
    converted = to_uint8(array)
    if converted.ndim == 2:
        return Image.fromarray(converted, mode="L").convert("RGB")
    if converted.shape[2] == 1:
        return Image.fromarray(converted[..., 0], mode="L").convert("RGB")
    return Image.fromarray(converted[..., :3], mode="RGB")


def mask_to_pil(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(mask.astype(np.uint8) * 255, mode="L")


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _component_centroids(mask: np.ndarray) -> list[tuple[float, float]]:
    labeled, count = ndi.label(mask, structure=CONNECTIVITY_8)
    if count == 0:
        return []
    centers = ndi.center_of_mass(mask, labeled, range(1, count + 1))
    return [(float(x), float(y)) for y, x in centers]


def render_overlay(
    result: AnalysisResult, language: str = "ru"
) -> Image.Image:
    """Render the notebook's Neurolucida-like output without Matplotlib."""

    skeleton = result.skeleton
    params = result.params
    height, width = skeleton.shape
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    ys, xs = np.nonzero(skeleton)

    if len(xs):
        dilation_iterations = max(
            0, int(round((params.skeleton_linewidth - 1.0) / 2.0))
        )
        if params.show_branch_colors and result.centers:
            center_xy = np.array(
                [(center["x"], center["y"]) for center in result.centers],
                dtype=np.float32,
            )
            point_xy = np.column_stack((xs, ys)).astype(np.float32)
            nearest = np.argmin(
                np.sum(
                    (point_xy[:, None, :] - center_xy[None, :, :]) ** 2,
                    axis=2,
                ),
                axis=1,
            )
            palette = np.array(
                [
                    tuple(
                        int(CENTER_COLORS[index % len(CENTER_COLORS)][offset : offset + 2], 16)
                        for offset in (1, 3, 5)
                    )
                    for index in range(len(result.centers))
                ],
                dtype=np.uint8,
            )
            for center_index, color in enumerate(palette):
                center_mask = np.zeros_like(skeleton)
                selected = nearest == center_index
                center_mask[ys[selected], xs[selected]] = True
                if dilation_iterations:
                    center_mask = ndi.binary_dilation(
                        center_mask,
                        structure=CONNECTIVITY_8,
                        iterations=dilation_iterations,
                    )
                canvas[center_mask] = color
        else:
            display_skeleton = skeleton
            if dilation_iterations:
                display_skeleton = ndi.binary_dilation(
                    skeleton,
                    structure=CONNECTIVITY_8,
                    iterations=dilation_iterations,
                )
            canvas[display_skeleton] = 255

    image = Image.fromarray(canvas, mode="RGB")
    draw = ImageDraw.Draw(image)
    ring_width = max(1, int(round(params.ring_width_px)))

    for index, center in enumerate(result.centers):
        color = CENTER_COLORS[index % len(CENTER_COLORS)]
        center_rows = [
            row
            for row in result.sholl
            if row["center_id"] == center["center_id"]
        ]
        for row in center_rows:
            radius_px = row["radius_um"] / params.pixel_size_um
            bounds = (
                center["x"] - radius_px,
                center["y"] - radius_px,
                center["x"] + radius_px,
                center["y"] + radius_px,
            )
            draw.ellipse(bounds, outline=color, width=ring_width)

        marker_radius = max(5, min(height, width) // 100)
        draw.ellipse(
            (
                center["x"] - marker_radius,
                center["y"] - marker_radius,
                center["x"] + marker_radius,
                center["y"] + marker_radius,
            ),
            fill=color,
            outline="black",
            width=1,
        )
        label = str(center["center_id"])
        draw.text(
            (center["x"], center["y"]),
            label,
            fill="black",
            font=_font(max(9, marker_radius)),
            anchor="mm",
        )

    if params.show_nodes:
        neighbors = ndi.convolve(
            skeleton.astype(np.uint8),
            np.array([[1, 1, 1], [1, 10, 1], [1, 1, 1]], dtype=np.uint8),
            mode="constant",
            cval=0,
        ) - 10 * skeleton.astype(np.uint8)
        endpoint_mask = skeleton & (neighbors == 1)
        junction_mask = skeleton & (neighbors >= 3)
        node_radius = max(2, min(height, width) // 350)
        for x, y in _component_centroids(endpoint_mask):
            draw.ellipse(
                (x - node_radius, y - node_radius, x + node_radius, y + node_radius),
                fill="#00e5ff",
            )
        for x, y in _component_centroids(junction_mask):
            draw.ellipse(
                (
                    x - node_radius - 1,
                    y - node_radius - 1,
                    x + node_radius + 1,
                    y + node_radius + 1,
                ),
                fill="#ff3b3b",
                outline="white",
            )

    if params.show_scale_bar and params.scale_bar_um > 0:
        requested_px = params.scale_bar_um / params.pixel_size_um
        bar_px = min(requested_px, width * 0.75)
        shown_um = bar_px * params.pixel_size_um
        x1 = width - max(16, width // 30)
        x0 = x1 - bar_px
        y = height - max(18, height // 20)
        line_width = max(3, height // 250)
        draw.line((x0, y, x1, y), fill="white", width=line_width)
        draw.text(
            ((x0 + x1) / 2, y - line_width - 2),
            f"{shown_um:g} {translate('мкм', language)}",
            fill="white",
            font=_font(max(10, min(height, width) // 50)),
            anchor="ms",
        )
    return image


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        path.write_text("", encoding="utf-8-sig")
        return
    columns: list[str] = []
    for row in materialized:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows(materialized)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _html_table(
    rows: Iterable[dict[str, Any]],
    language: str,
    labels: dict[str, str] | None = None,
) -> str:
    materialized = list(rows)
    if not materialized:
        return f"<p>{translate('Нет данных.', language)}</p>"
    columns = list(materialized[0])
    head = "".join(
        f"<th>{html.escape(str((labels or {}).get(column, column)))}</th>"
        for column in columns
    )
    body = []
    for row in materialized:
        cells = "".join(
            f"<td>{html.escape(_format_value(row.get(column, '')))}</td>"
            for column in columns
        )
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _write_report(
    result: AnalysisResult, path: Path, language: str
) -> None:
    labels = metric_labels(language)
    columns = column_labels(language)
    metric_rows = [
        {
            translate("Показатель", language): labels.get(key, key),
            translate("Значение", language): _format_value(value),
        }
        for key, value in result.metrics.items()
    ]
    document = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Cell Skeleton Detector — {translate("отчёт", language)}</title>
<style>
body {{ font: 15px/1.45 "Segoe UI", sans-serif; margin: 32px; color: #17212b; }}
h1, h2 {{ color: #123047; }}
.images {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
.images img {{ width: 100%; background: #000; border: 1px solid #cad4dc; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
th, td {{ border: 1px solid #cad4dc; padding: 7px 9px; text-align: left; }}
th {{ background: #e9f1f5; position: sticky; top: 0; }}
.note {{ color: #56636d; }}
</style>
</head>
<body>
<h1>Cell Skeleton Detector</h1>
<p class="note">{translate("Исследовательский отчёт. Результаты требуют проверки на контрольной выборке и не предназначены для клинической диагностики.", language)}</p>
<div class="images">
  <figure><img src="enhanced_signal.png"><figcaption>{translate("Усиленный сигнал", language)}</figcaption></figure>
  <figure><img src="binary_mask.png"><figcaption>{translate("Бинарная маска", language)}</figcaption></figure>
  <figure><img src="skeleton.png"><figcaption>{translate("Скелет", language)}</figcaption></figure>
  <figure><img src="neurolucida_overlay.png"><figcaption>Neurolucida-like + Sholl</figcaption></figure>
</div>
<h2>{translate("Основные метрики", language)}</h2>
{_html_table(metric_rows, language)}
<h2>Sholl summary</h2>
{_html_table(result.sholl_summary, language, columns)}
<h2>{translate("Параметры", language)}</h2>
{_html_table([result.params.to_dict()], language)}
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _unique_output_directory(parent: Path, stem: str) -> Path:
    safe_stem = re.sub(r'[<>:"/\\|?*]+', "_", stem).strip(" .") or "image"
    base = parent / f"{safe_stem}_results"
    if not base.exists():
        return base
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = parent / f"{safe_stem}_results_{timestamp}"
    suffix = 2
    while candidate.exists():
        candidate = parent / f"{safe_stem}_results_{timestamp}_{suffix}"
        suffix += 1
    return candidate


def export_results(
    result: AnalysisResult,
    parent_directory: str | Path,
    source_stem: str,
    language: str = "ru",
) -> tuple[Path, Path]:
    parent = Path(parent_directory)
    parent.mkdir(parents=True, exist_ok=True)
    target = _unique_output_directory(parent, source_stem)
    target.mkdir()

    image_to_pil(result.enhanced).save(target / "enhanced_signal.png")
    mask_to_pil(result.binary).save(target / "binary_mask.png")
    mask_to_pil(result.skeleton).save(target / "skeleton.png")
    render_overlay(result, language).save(target / "neurolucida_overlay.png")

    _write_csv(target / "metrics.csv", [result.metrics])
    _write_csv(target / "branch_table.csv", result.branches)
    _write_csv(target / "sholl_intersections.csv", result.sholl)
    _write_csv(target / "sholl_summary_by_centers.csv", result.sholl_summary)
    _write_csv(target / "uncertainty_bootstrap.csv", result.uncertainty)
    (target / "parameters.json").write_text(
        json.dumps(result.params.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(result, target / "report.html", language)

    archive = target.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file_path in sorted(target.iterdir()):
            bundle.write(file_path, arcname=file_path.name)
    return target, archive
