from __future__ import annotations

from typing import Any


LANGUAGE_NAMES = {"Русский": "ru", "English": "en"}


ENGLISH = {
    # Header, navigation, and status.
    "Откройте изображение астроцитов": "Open an astrocyte image",
    "Открыть изображение": "Open Image",
    "Обработать": "Process",
    "Сохранить результаты": "Save Results",
    "Параметры": "Parameters",
    "Сбросить": "Reset",
    "Основные": "Basic",
    "Дополнительно": "Advanced",
    "Исходное": "Original",
    "Сигнал": "Signal",
    "Маска": "Mask",
    "Скелет": "Skeleton",
    "Метрики": "Metrics",
    "Ветви": "Branches",
    "Результат появится после обработки": "The result will appear after processing",
    "Откройте изображение": "Open an image",
    "Нет данных": "No data",
    "Показатель": "Metric",
    "Значение": "Value",
    "Готово": "Ready",
    "Параметры сброшены": "Parameters reset",
    "Изображение загружено": "Image loaded",
    "Запуск обработки…": "Starting analysis…",
    "Сохранение результатов…": "Saving results…",
    "Сохранено: {name}": "Saved: {name}",
    "Ошибка": "Error",
    "Обработка завершена": "Analysis complete",
    # Groups and fields.
    "Сегментация": "Segmentation",
    "Калибровка и анализ": "Calibration and Analysis",
    "Предобработка": "Preprocessing",
    "Sholl и устойчивость": "Sholl and Robustness",
    "Визуализация": "Visualization",
    "Канал": "Channel",
    "Усиление": "Enhancement",
    "Метод порога": "Threshold Method",
    "Множитель порога": "Threshold Multiplier",
    "Мин. объект, px": "Min. Object, px",
    "Замыкание, px": "Closing Radius, px",
    "Размер пикселя, мкм": "Pixel Size, µm",
    "Центры Sholl": "Sholl Centers",
    "Шаг Sholl, мкм": "Sholl Step, µm",
    "Max радиус, мкм": "Max Radius, µm",
    "Bootstrap итерации": "Bootstrap Iterations",
    "Top-hat радиус": "Top-hat Radius",
    "Ручной порог": "Manual Threshold",
    "Окно Sauvola": "Sauvola Window",
    "Заполнение дыр, px": "Fill Holes, px",
    "Открытие, px": "Opening Radius, px",
    "Дилатация, px": "Dilation Radius, px",
    "Эрозия, px": "Erosion Radius, px",
    "Инвертировать маску": "Invert Mask",
    "Метод скелетизации": "Skeletonization Method",
    "Thin итерации": "Thin Iterations",
    "Pruning концов": "Endpoint Pruning",
    "Разброс порога ±": "Threshold Variation ±",
    "Ручной центр X": "Manual Center X",
    "Ручной центр Y": "Manual Center Y",
    "Мин. компонент, px": "Min. Component, px",
    "Макс. центров": "Max. Centers",
    "Толщина колец": "Ring Width",
    "Толщина скелета": "Skeleton Width",
    "Цветной скелет": "Colored Skeleton",
    "Показывать узлы": "Show Nodes",
    "Масштабная линейка": "Scale Bar",
    "Длина линейки, мкм": "Scale Bar Length, µm",
    "Совет: если тонкие отростки теряются, уменьшите множитель порога. "
    "Если захватывается фон — увеличьте его.": (
        "Tip: if thin processes are lost, decrease the threshold multiplier. "
        "If background is included, increase it."
    ),
    # Combo values.
    "Красный канал": "Red Channel",
    "Зелёный канал": "Green Channel",
    "Синий канал": "Blue Channel",
    "Среднее RGB": "RGB Mean",
    "Яркость RGB": "RGB Luminance",
    "Sauvola (локальный)": "Sauvola (Local)",
    "2 крупнейших компонента": "2 Largest Components",
    "Несколько компонентов": "Multiple Components",
    "Один общий центр": "Single Center",
    "Ручной центр X/Y": "Manual Center X/Y",
    # Dialogs.
    "Выберите изображение": "Select an Image",
    "Изображения": "Images",
    "Все файлы": "All Files",
    "Не удалось открыть изображение": "Could Not Open Image",
    "Нет изображения": "No Image",
    "Сначала откройте изображение.": "Open an image first.",
    "Ошибка параметров": "Invalid Parameters",
    "Куда сохранить результаты?": "Where Should the Results Be Saved?",
    "Результаты сохранены": "Results Saved",
    "Папка:\n{folder}\n\nАрхив:\n{archive}": (
        "Folder:\n{folder}\n\nArchive:\n{archive}"
    ),
    "Ошибка обработки": "Processing Error",
    "Неизвестная ошибка": "Unknown error",
    "Проверьте поле «{name}»: {value}": "Check the “{name}” field: {value}",
    # Core progress.
    "Выделение канала…": "Extracting channel…",
    "Усиление сигнала…": "Enhancing signal…",
    "Построение маски…": "Creating mask…",
    "Скелетизация…": "Skeletonizing…",
    "Расчёт морфометрии…": "Calculating morphometry…",
    "Sholl-анализ…": "Running Sholl analysis…",
    "Оценка устойчивости…": "Estimating robustness…",
    "Оценка устойчивости: {current}/{total}": (
        "Estimating robustness: {current}/{total}"
    ),
    # Validation and loading errors.
    "Размер пикселя должен быть больше нуля.": "Pixel size must be greater than zero.",
    "Радиусы Sholl должны быть больше нуля.": "Sholl radii must be greater than zero.",
    "Sigma max должна быть не меньше Sigma min.": (
        "Sigma max must be greater than or equal to Sigma min."
    ),
    "Окно Sauvola должно быть нечётным числом не меньше 3.": (
        "The Sauvola window must be an odd integer of at least 3."
    ),
    "Ручной порог должен быть от 0 до 1.": (
        "The manual threshold must be between 0 and 1."
    ),
    "Множитель порога должен быть больше нуля.": (
        "The threshold multiplier must be greater than zero."
    ),
    "Количество итераций и центров не может быть отрицательным.": (
        "Iteration and center counts cannot be negative."
    ),
    "Числовые параметры не могут быть отрицательными.": (
        "Numeric parameters cannot be negative."
    ),
    "Поддерживаются двумерные серые и RGB-изображения.": (
        "Only 2-D grayscale and RGB images are supported."
    ),
    "Изображение пустое.": "The image is empty.",
    "Изображение не содержит конечных значений.": (
        "The image does not contain finite values."
    ),
    # Overlay and report.
    "мкм": "µm",
    "Нет данных.": "No data.",
    "отчёт": "report",
    "Исследовательский отчёт. Результаты требуют проверки на контрольной "
    "выборке и не предназначены для клинической диагностики.": (
        "Research report. Results require validation against a control dataset "
        "and are not intended for clinical diagnosis."
    ),
    "Усиленный сигнал": "Enhanced Signal",
    "Бинарная маска": "Binary Mask",
    "Основные метрики": "Primary Metrics",
}


METRIC_LABELS_RU = {
    "mask_area_px": "Площадь маски, px",
    "mask_area_um2": "Площадь маски, мкм²",
    "skeleton_length_px": "Длина скелета, px",
    "skeleton_length_um": "Длина скелета, мкм",
    "endpoints": "Концевые точки",
    "junctions": "Узлы ветвления",
    "branches": "Ветви",
    "objects": "Объекты",
    "mean_branch_length_um": "Средняя длина ветви, мкм",
    "median_branch_length_um": "Медианная длина ветви, мкм",
    "mean_tortuosity": "Средняя извилистость",
    "mean_diameter_px": "Средний диаметр, px",
    "mean_diameter_um": "Средний диаметр, мкм",
    "mean_intensity_on_mask": "Средняя интенсивность маски",
    "total_intensity_on_mask": "Суммарная интенсивность маски",
    "network_density_length_per_area": "Плотность сети",
    "threshold_value": "Базовый порог",
    "threshold_method": "Метод порога",
    "enhancement_method": "Усиление сигнала",
    "skeleton_method": "Скелетизация",
    "pixel_size_um": "Размер пикселя, мкм/px",
    "sholl_centers": "Центры Sholl",
    "sholl_max_intersections_mean": "Средний максимум пересечений Sholl",
    "sholl_auc_mean": "Средняя площадь под кривой Sholl",
    "sholl_total_intersections_mean": "Средняя сумма пересечений Sholl",
}

METRIC_LABELS_EN = {
    "mask_area_px": "Mask Area, px",
    "mask_area_um2": "Mask Area, µm²",
    "skeleton_length_px": "Skeleton Length, px",
    "skeleton_length_um": "Skeleton Length, µm",
    "endpoints": "Endpoints",
    "junctions": "Branching Nodes",
    "branches": "Branches",
    "objects": "Objects",
    "mean_branch_length_um": "Mean Branch Length, µm",
    "median_branch_length_um": "Median Branch Length, µm",
    "mean_tortuosity": "Mean Tortuosity",
    "mean_diameter_px": "Mean Diameter, px",
    "mean_diameter_um": "Mean Diameter, µm",
    "mean_intensity_on_mask": "Mean Mask Intensity",
    "total_intensity_on_mask": "Total Mask Intensity",
    "network_density_length_per_area": "Network Density",
    "threshold_value": "Base Threshold",
    "threshold_method": "Threshold Method",
    "enhancement_method": "Signal Enhancement",
    "skeleton_method": "Skeletonization",
    "pixel_size_um": "Pixel Size, µm/px",
    "sholl_centers": "Sholl Centers",
    "sholl_max_intersections_mean": "Mean Maximum Sholl Intersections",
    "sholl_auc_mean": "Mean Sholl Area Under Curve",
    "sholl_total_intersections_mean": "Mean Total Sholl Intersections",
}


COLUMN_LABELS_RU = {
    "branch_id": "ID ветви",
    "pixel_count": "Пиксели",
    "length_px": "Длина, px",
    "length_um": "Длина, мкм",
    "mean_intensity": "Средняя интенсивность",
    "tortuosity_approx": "Извилистость",
    "center_id": "ID центра",
    "center_x_px": "Центр X, px",
    "center_y_px": "Центр Y, px",
    "x_px": "X, px",
    "y_px": "Y, px",
    "cluster_area_px": "Площадь компонента, px",
    "radius_um": "Радиус, мкм",
    "intersections": "Пересечения",
    "max_intersections": "Макс. пересечений",
    "critical_radius_um": "Критический радиус, мкм",
    "sholl_auc": "Площадь под кривой Sholl",
    "total_intersections": "Сумма пересечений",
    "mean_intersections": "Среднее пересечений",
    "se_intersections": "Станд. ошибка пересечений",
    "metric": "Показатель",
    "mean": "Среднее",
    "sample_std": "Станд. отклонение",
    "standard_error": "Станд. ошибка",
    "ci95_low": "Нижняя граница 95% ДИ",
    "ci95_high": "Верхняя граница 95% ДИ",
    "iterations": "Итерации",
}

COLUMN_LABELS_EN = {
    "branch_id": "Branch ID",
    "pixel_count": "Pixel Count",
    "length_px": "Length, px",
    "length_um": "Length, µm",
    "mean_intensity": "Mean Intensity",
    "tortuosity_approx": "Tortuosity",
    "center_id": "Center ID",
    "center_x_px": "Center X, px",
    "center_y_px": "Center Y, px",
    "x_px": "X, px",
    "y_px": "Y, px",
    "cluster_area_px": "Component Area, px",
    "radius_um": "Radius, µm",
    "intersections": "Intersections",
    "max_intersections": "Max. Intersections",
    "critical_radius_um": "Critical Radius, µm",
    "sholl_auc": "Sholl Area Under Curve",
    "total_intersections": "Total Intersections",
    "mean_intersections": "Mean Intersections",
    "se_intersections": "Intersection Standard Error",
    "metric": "Metric",
    "mean": "Mean",
    "sample_std": "Sample Standard Deviation",
    "standard_error": "Standard Error",
    "ci95_low": "95% CI Lower Bound",
    "ci95_high": "95% CI Upper Bound",
    "iterations": "Iterations",
}


def translate(source: str, language: str = "ru", **values: Any) -> str:
    bootstrap_prefix = "Оценка устойчивости: "
    if source.startswith(bootstrap_prefix) and "/" in source:
        current, total = source[len(bootstrap_prefix) :].split("/", 1)
        source = "Оценка устойчивости: {current}/{total}"
        values = {"current": current, "total": total, **values}
    template = ENGLISH.get(source, source) if language == "en" else source
    return template.format(**values) if values else template


def metric_labels(language: str) -> dict[str, str]:
    return METRIC_LABELS_EN if language == "en" else METRIC_LABELS_RU


def column_labels(language: str) -> dict[str, str]:
    return COLUMN_LABELS_EN if language == "en" else COLUMN_LABELS_RU
