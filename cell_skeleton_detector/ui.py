from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox, ttk

from .core import AnalysisEngine, load_image
from .exporters import (
    export_results,
    image_to_pil,
    mask_to_pil,
    render_overlay,
)
from .i18n import (
    LANGUAGE_NAMES,
    column_labels,
    metric_labels,
    translate,
)
from .models import AnalysisParams, AnalysisResult


BG = "#101820"
PANEL = "#17232d"
CARD = "#1d2c37"
TEXT = "#ecf3f6"
MUTED = "#a9bac3"
ACCENT = "#22b8cf"
SUCCESS = "#32b768"


class ScrollFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.canvas = tk.Canvas(
            self,
            background=PANEL,
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.body = ttk.Frame(self.canvas, style="Panel.TFrame")
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.body, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_body_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _bind_wheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class ImagePane(ttk.Frame):
    def __init__(self, parent: tk.Misc, empty_text: str):
        super().__init__(parent, style="Image.TFrame")
        self.canvas = tk.Canvas(
            self,
            background="#081015",
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.empty_text = empty_text
        self.source: Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.canvas.bind("<Configure>", self._render)
        self._render()

    def set_image(self, image: Image.Image | None) -> None:
        self.source = image.copy() if image is not None else None
        self._render()

    def set_empty_text(self, text: str) -> None:
        self.empty_text = text
        if self.source is None:
            self._render()

    def _render(self, _event: tk.Event | None = None) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 2)
        height = max(self.canvas.winfo_height(), 2)
        if self.source is None:
            self.canvas.create_text(
                width / 2,
                height / 2,
                text=self.empty_text,
                fill=MUTED,
                font=("Segoe UI", 12),
                width=max(width - 60, 100),
                justify="center",
            )
            return
        source_width, source_height = self.source.size
        scale = min(width / source_width, height / source_height)
        target = (
            max(1, int(source_width * scale)),
            max(1, int(source_height * scale)),
        )
        preview = self.source.resize(target, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.canvas.create_image(
            width / 2, height / 2, image=self.photo, anchor="center"
        )


class DataTable(ttk.Frame):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.tree = ttk.Treeview(self, show="headings")
        vertical = ttk.Scrollbar(
            self, orient="vertical", command=self.tree.yview
        )
        horizontal = ttk.Scrollbar(
            self, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def set_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        labels: dict[str, str] | None = None,
        transpose: bool = False,
        no_data_text: str = "Нет данных",
    ) -> None:
        self.tree.delete(*self.tree.get_children())
        if transpose and rows:
            materialized = [
                {
                    "metric": (labels or {}).get(key, key),
                    "value": self._format(value),
                }
                for key, value in rows[0].items()
            ]
        else:
            materialized = rows

        if not materialized:
            columns = ("message",)
            self.tree.configure(columns=columns)
            self.tree.heading("message", text=no_data_text)
            self.tree.column("message", width=500, stretch=True)
            return

        columns = tuple(materialized[0].keys())
        self.tree.configure(columns=columns)
        for column in columns:
            title = (labels or {}).get(column, column)
            self.tree.heading(column, text=title)
            width = 260 if column == "metric" else 135
            self.tree.column(column, width=width, minwidth=80, stretch=True)
        for row in materialized:
            self.tree.insert(
                "",
                "end",
                values=[self._format(row.get(column, "")) for column in columns],
            )

    @staticmethod
    def _format(value: Any) -> str:
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value)


class DetectorApp:
    COMBOS = {
        "channel": [
            ("Красный канал", "red"),
            ("Зелёный канал", "green"),
            ("Синий канал", "blue"),
            ("Среднее RGB", "mean"),
            ("Яркость RGB", "gray"),
        ],
        "enhancement_method": [
            ("CLAHE", "clahe"),
            ("CLAHE + Frangi", "frangi"),
            ("CLAHE + Sato", "sato"),
            ("CLAHE + Meijering", "meijering"),
            ("White top-hat", "tophat"),
            ("Non-local means", "nlm"),
        ],
        "threshold_method": [
            ("Otsu", "otsu"),
            ("Yen", "yen"),
            ("Li", "li"),
            ("Triangle", "triangle"),
            ("Sauvola (локальный)", "sauvola"),
            ("Ручной порог", "manual"),
        ],
        "skeleton_method": [
            ("Skeletonize", "skeletonize"),
            ("Thin", "thin"),
            ("Medial axis", "medial_axis"),
        ],
        "cluster_mode": [
            ("2 крупнейших компонента", "two_largest"),
            ("Несколько компонентов", "auto_components"),
            ("Один общий центр", "single_center"),
            ("Ручной центр X/Y", "manual"),
        ],
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cell Skeleton Detector")
        self.root.geometry("1320x860")
        self.root.minsize(1040, 700)
        self.root.configure(background=BG)
        self._configure_style()

        self.image_path: Path | None = None
        self.image: np.ndarray | None = None
        self.result: AnalysisResult | None = None
        self.events: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.language_code = "en"
        self.language_variable = tk.StringVar(value="English")
        self.variables: dict[str, tk.Variable] = {}
        self.combo_maps: dict[str, dict[str, str]] = {}
        self.combo_reverse: dict[str, dict[str, str]] = {}
        self.combo_widgets: dict[str, ttk.Combobox] = {}
        self.localized_widgets: list[tuple[tk.Widget, str]] = []
        self.localized_tabs: list[tuple[ttk.Notebook, tk.Widget, str]] = []
        self.pane_empty_sources: dict[str, str] = {}
        self.status_source = "Готово"
        self.status_values: dict[str, Any] = {}
        self.busy = False

        self._build_header()
        self._build_main()
        self._build_status()
        self._set_defaults()
        self.root.after(100, self._poll_events)

    def _t(self, source: str, **values: Any) -> str:
        return translate(source, self.language_code, **values)

    def _localized(
        self, widget: tk.Widget, source: str
    ) -> tk.Widget:
        self.localized_widgets.append((widget, source))
        widget.configure(text=self._t(source))
        return widget

    def _localized_tab(
        self,
        notebook: ttk.Notebook,
        child: tk.Widget,
        source: str,
    ) -> None:
        notebook.add(child, text=self._t(source))
        self.localized_tabs.append((notebook, child, source))

    def _set_status(self, source: str, **values: Any) -> None:
        self.status_source = source
        self.status_values = values
        self.status.configure(text=self._t(source, **values))

    def _on_language_changed(self, _event: tk.Event | None = None) -> None:
        new_language = LANGUAGE_NAMES.get(
            self.language_variable.get(), "ru"
        )
        if new_language == self.language_code:
            return

        current_combo_values = {
            name: self.combo_maps[name].get(
                str(variable.get()), getattr(AnalysisParams(), name)
            )
            for name, variable in self.variables.items()
            if name in self.combo_maps
        }
        self.language_code = new_language

        for widget, source in self.localized_widgets:
            widget.configure(text=self._t(source))
        for notebook, child, source in self.localized_tabs:
            notebook.tab(child, text=self._t(source))

        for name, widget in self.combo_widgets.items():
            choices = [
                (self._t(display), value)
                for display, value in self.COMBOS[name]
            ]
            self.combo_maps[name] = dict(choices)
            self.combo_reverse[name] = {
                value: display for display, value in choices
            }
            widget.configure(values=[display for display, _ in choices])
            internal_value = current_combo_values[name]
            self.variables[name].set(
                self.combo_reverse[name][internal_value]
            )

        for key, pane in self.image_panes.items():
            pane.set_empty_text(self._t(self.pane_empty_sources[key]))

        if self.image_path is None:
            self.file_label.configure(
                text=self._t("Откройте изображение астроцитов")
            )
        self._set_status(self.status_source, **self.status_values)
        self._refresh_tables()
        if self.result is not None:
            self.image_panes["overlay"].set_image(
                render_overlay(self.result, self.language_code)
            )

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Image.TFrame", background="#081015")
        style.configure("TLabel", background=PANEL, foreground=TEXT)
        style.configure(
            "Title.TLabel",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "Subtitle.TLabel", background=BG, foreground=MUTED
        )
        style.configure(
            "TLabelframe",
            background=PANEL,
            foreground=TEXT,
            bordercolor="#38505e",
        )
        style.configure(
            "TLabelframe.Label",
            background=PANEL,
            foreground=ACCENT,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "TNotebook", background=BG, borderwidth=0
        )
        style.configure(
            "TNotebook.Tab",
            background=CARD,
            foreground=MUTED,
            padding=(12, 7),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", PANEL)],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "Treeview",
            background="#111b22",
            fieldbackground="#111b22",
            foreground=TEXT,
            rowheight=25,
        )
        style.configure(
            "Treeview.Heading",
            background="#29404d",
            foreground=TEXT,
            font=("Segoe UI Semibold", 9),
        )
        style.map(
            "Treeview",
            background=[("selected", "#246b7a")],
            foreground=[("selected", "white")],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#061216",
            padding=(15, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", "#4dd0e1"),
                ("disabled", "#35535c"),
            ],
        )
        style.configure(
            "Success.TButton",
            background=SUCCESS,
            foreground="#06140b",
            padding=(15, 8),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Success.TButton",
            background=[
                ("active", "#59d183"),
                ("disabled", "#355443"),
            ],
        )
        style.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        style.map(
            "TCheckbutton",
            background=[("active", PANEL)],
            foreground=[("disabled", "#71808a")],
        )

    def _build_header(self) -> None:
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=18, pady=(14, 10))
        title_area = ttk.Frame(header)
        title_area.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_area,
            text="Cell Skeleton Detector",
            style="Title.TLabel",
        ).pack(anchor="w")
        self.file_label = ttk.Label(
            title_area,
            text=self._t("Откройте изображение астроцитов"),
            style="Subtitle.TLabel",
        )
        self.file_label.pack(anchor="w", pady=(2, 0))

        self.open_button = ttk.Button(
            header, command=self.open_image
        )
        self._localized(self.open_button, "Открыть изображение")
        self.open_button.pack(side="left", padx=5)
        self.run_button = ttk.Button(
            header,
            style="Accent.TButton",
            command=self.start_analysis,
        )
        self._localized(self.run_button, "Обработать")
        self.run_button.pack(side="left", padx=5)
        self.save_button = ttk.Button(
            header,
            style="Success.TButton",
            command=self.start_export,
            state="disabled",
        )
        self._localized(self.save_button, "Сохранить результаты")
        self.save_button.pack(side="left", padx=(5, 0))

        language_selector = ttk.Combobox(
            header,
            state="readonly",
            values=list(LANGUAGE_NAMES),
            textvariable=self.language_variable,
            width=9,
        )
        language_selector.bind(
            "<<ComboboxSelected>>", self._on_language_changed
        )
        language_selector.pack(side="left", padx=(10, 0))

    def _build_main(self) -> None:
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=18)

        settings_container = ttk.Frame(paned, style="Panel.TFrame")
        settings_container.configure(width=355)
        paned.add(settings_container, weight=0)

        settings_header = ttk.Frame(
            settings_container, style="Panel.TFrame"
        )
        settings_header.pack(fill="x", padx=10, pady=(9, 5))
        settings_title = ttk.Label(
            settings_header,
            font=("Segoe UI Semibold", 12),
        )
        self._localized(settings_title, "Параметры")
        settings_title.pack(side="left")
        reset_button = ttk.Button(
            settings_header, command=self._set_defaults
        )
        self._localized(reset_button, "Сбросить")
        reset_button.pack(side="right")

        settings_tabs = ttk.Notebook(settings_container)
        settings_tabs.pack(fill="both", expand=True)
        basic = ScrollFrame(settings_tabs)
        advanced = ScrollFrame(settings_tabs)
        self._localized_tab(settings_tabs, basic, "Основные")
        self._localized_tab(settings_tabs, advanced, "Дополнительно")
        self._build_basic_settings(basic.body)
        self._build_advanced_settings(advanced.body)

        content = ttk.Frame(paned)
        paned.add(content, weight=1)
        preview_tabs = ttk.Notebook(content)
        preview_tabs.pack(fill="both", expand=True)
        self.image_panes: dict[str, ImagePane] = {}
        for key, label in (
            ("original", "Исходное"),
            ("enhanced", "Сигнал"),
            ("binary", "Маска"),
            ("skeleton", "Скелет"),
            ("overlay", "Sholl / Overlay"),
        ):
            empty_source = (
                "Результат появится после обработки"
                if key != "original"
                else "Откройте изображение"
            )
            pane = ImagePane(
                preview_tabs,
                self._t(empty_source),
            )
            self._localized_tab(preview_tabs, pane, label)
            self.image_panes[key] = pane
            self.pane_empty_sources[key] = empty_source

        result_tabs = ttk.Notebook(content)
        result_tabs.pack(fill="x", pady=(8, 0))
        result_tabs.configure(height=230)
        self.metrics_table = DataTable(result_tabs)
        self.sholl_table = DataTable(result_tabs)
        self.branches_table = DataTable(result_tabs)
        self.uncertainty_table = DataTable(result_tabs)
        self._localized_tab(result_tabs, self.metrics_table, "Метрики")
        self._localized_tab(
            result_tabs, self.sholl_table, "Sholl summary"
        )
        self._localized_tab(result_tabs, self.branches_table, "Ветви")
        self._localized_tab(
            result_tabs, self.uncertainty_table, "Bootstrap"
        )
        self._refresh_tables()

    def _build_status(self) -> None:
        bar = ttk.Frame(self.root)
        bar.pack(fill="x", padx=18, pady=(8, 13))
        self.progress = ttk.Progressbar(
            bar, orient="horizontal", mode="determinate", maximum=100
        )
        self.progress.pack(side="right", fill="x", expand=True, padx=(16, 0))
        self.status = ttk.Label(
            bar, text=self._t("Готово"), style="Subtitle.TLabel"
        )
        self.status.pack(side="left")

    def _group(self, parent: tk.Misc, title: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=self._t(title))
        self.localized_widgets.append((frame, title))
        frame.pack(fill="x", padx=10, pady=7)
        frame.columnconfigure(1, weight=1)
        return frame

    def _add_combo(
        self,
        parent: ttk.LabelFrame,
        row: int,
        name: str,
        label: str,
    ) -> ttk.Combobox:
        choices = [
            (self._t(display), value)
            for display, value in self.COMBOS[name]
        ]
        display_values = [display for display, _ in choices]
        self.combo_maps[name] = dict(choices)
        self.combo_reverse[name] = {
            value: display for display, value in choices
        }
        variable = tk.StringVar()
        self.variables[name] = variable
        label_widget = ttk.Label(parent, text=self._t(label))
        self.localized_widgets.append((label_widget, label))
        label_widget.grid(
            row=row, column=0, sticky="w", padx=8, pady=5
        )
        widget = ttk.Combobox(
            parent,
            state="readonly",
            values=display_values,
            textvariable=variable,
            width=22,
        )
        widget.grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        self.combo_widgets[name] = widget
        return widget

    def _add_number(
        self,
        parent: ttk.LabelFrame,
        row: int,
        name: str,
        label: str,
        *,
        minimum: float,
        maximum: float,
        increment: float,
    ) -> ttk.Spinbox:
        variable = tk.StringVar()
        self.variables[name] = variable
        label_widget = ttk.Label(parent, text=self._t(label))
        self.localized_widgets.append((label_widget, label))
        label_widget.grid(
            row=row, column=0, sticky="w", padx=8, pady=5
        )
        widget = ttk.Spinbox(
            parent,
            textvariable=variable,
            from_=minimum,
            to=maximum,
            increment=increment,
            width=12,
        )
        widget.grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        return widget

    def _add_bool(
        self,
        parent: ttk.LabelFrame,
        row: int,
        name: str,
        label: str,
    ) -> ttk.Checkbutton:
        variable = tk.BooleanVar()
        self.variables[name] = variable
        widget = ttk.Checkbutton(parent, variable=variable)
        self._localized(widget, label)
        widget.grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=5,
        )
        return widget

    def _build_basic_settings(self, parent: tk.Misc) -> None:
        preprocessing = self._group(parent, "Сигнал")
        self._add_combo(preprocessing, 0, "channel", "Канал")
        self._add_combo(
            preprocessing, 1, "enhancement_method", "Усиление"
        )

        segmentation = self._group(parent, "Сегментация")
        self._add_combo(
            segmentation, 0, "threshold_method", "Метод порога"
        )
        self._add_number(
            segmentation,
            1,
            "threshold_multiplier",
            "Множитель порога",
            minimum=0.1,
            maximum=2.0,
            increment=0.05,
        )
        self._add_number(
            segmentation,
            2,
            "min_object_size",
            "Мин. объект, px",
            minimum=0,
            maximum=100000,
            increment=10,
        )
        self._add_number(
            segmentation,
            3,
            "closing_radius",
            "Замыкание, px",
            minimum=0,
            maximum=100,
            increment=1,
        )

        calibration = self._group(parent, "Калибровка и анализ")
        self._add_number(
            calibration,
            0,
            "pixel_size_um",
            "Размер пикселя, мкм",
            minimum=0.000001,
            maximum=10000,
            increment=0.1,
        )
        self._add_combo(
            calibration, 1, "cluster_mode", "Центры Sholl"
        )
        self._add_number(
            calibration,
            2,
            "sholl_radius_step_um",
            "Шаг Sholl, мкм",
            minimum=0.000001,
            maximum=10000,
            increment=1,
        )
        self._add_number(
            calibration,
            3,
            "sholl_max_radius_um",
            "Max радиус, мкм",
            minimum=0.000001,
            maximum=100000,
            increment=10,
        )
        self._add_number(
            calibration,
            4,
            "bootstrap_n",
            "Bootstrap итерации",
            minimum=0,
            maximum=1000,
            increment=5,
        )

        hint = ttk.Label(
            parent,
            text="",
            wraplength=300,
            foreground=MUTED,
        )
        self._localized(
            hint,
            "Совет: если тонкие отростки теряются, уменьшите "
            "множитель порога. Если захватывается фон — увеличьте его.",
        )
        hint.pack(fill="x", padx=16, pady=10)

    def _build_advanced_settings(self, parent: tk.Misc) -> None:
        preprocessing = self._group(parent, "Предобработка")
        for row, args in enumerate(
            (
                ("gaussian_sigma", "Gaussian sigma", 0, 10, 0.1),
                ("clahe_clip", "CLAHE clip", 0.001, 1, 0.001),
                ("vessel_sigma_min", "Vessel sigma min", 0.1, 20, 0.5),
                ("vessel_sigma_max", "Vessel sigma max", 0.1, 30, 0.5),
                ("tophat_radius", "Top-hat радиус", 1, 500, 1),
            )
        ):
            self._add_number(
                preprocessing,
                row,
                args[0],
                args[1],
                minimum=args[2],
                maximum=args[3],
                increment=args[4],
            )

        mask = self._group(parent, "Маска")
        for row, args in enumerate(
            (
                ("manual_threshold", "Ручной порог", 0, 1, 0.01),
                ("sauvola_window", "Окно Sauvola", 3, 999, 2),
                ("hole_area", "Заполнение дыр, px", 0, 100000, 10),
                ("opening_radius", "Открытие, px", 0, 100, 1),
                ("dilation_radius", "Дилатация, px", 0, 100, 1),
                ("erosion_radius", "Эрозия, px", 0, 100, 1),
            )
        ):
            self._add_number(
                mask,
                row,
                args[0],
                args[1],
                minimum=args[2],
                maximum=args[3],
                increment=args[4],
            )
        self._add_bool(mask, 6, "invert_mask", "Инвертировать маску")

        skeleton = self._group(parent, "Скелет")
        self._add_combo(
            skeleton, 0, "skeleton_method", "Метод скелетизации"
        )
        self._add_number(
            skeleton,
            1,
            "thin_iterations",
            "Thin итерации",
            minimum=0,
            maximum=1000,
            increment=1,
        )
        self._add_number(
            skeleton,
            2,
            "prune_iterations",
            "Pruning концов",
            minimum=0,
            maximum=1000,
            increment=1,
        )

        sholl = self._group(parent, "Sholl и устойчивость")
        for row, args in enumerate(
            (
                ("uncertainty_range", "Разброс порога ±", 0.001, 1, 0.01),
                ("manual_center_x", "Ручной центр X", 0, 100000, 1),
                ("manual_center_y", "Ручной центр Y", 0, 100000, 1),
                ("min_cluster_area", "Мин. компонент, px", 1, 1000000, 10),
                ("max_clusters", "Макс. центров", 1, 100, 1),
            )
        ):
            self._add_number(
                sholl,
                row,
                args[0],
                args[1],
                minimum=args[2],
                maximum=args[3],
                increment=args[4],
            )

        visual = self._group(parent, "Визуализация")
        self._add_number(
            visual,
            0,
            "ring_width_px",
            "Толщина колец",
            minimum=0.1,
            maximum=20,
            increment=0.1,
        )
        self._add_number(
            visual,
            1,
            "skeleton_linewidth",
            "Толщина скелета",
            minimum=0.1,
            maximum=20,
            increment=0.1,
        )
        self._add_bool(visual, 2, "show_branch_colors", "Цветной скелет")
        self._add_bool(visual, 3, "show_nodes", "Показывать узлы")
        self._add_bool(
            visual, 4, "show_scale_bar", "Масштабная линейка"
        )
        self._add_number(
            visual,
            5,
            "scale_bar_um",
            "Длина линейки, мкм",
            minimum=0,
            maximum=100000,
            increment=10,
        )

    def _set_defaults(self) -> None:
        defaults = AnalysisParams()
        for name, variable in self.variables.items():
            value = getattr(defaults, name)
            if name in self.combo_reverse:
                value = self.combo_reverse[name][value]
            variable.set(value)
        self._set_status("Параметры сброшены")

    def _combo_value(self, name: str) -> str:
        display = str(self.variables[name].get())
        return self.combo_maps[name][display]

    def _float(self, name: str) -> float:
        raw = str(self.variables[name].get()).strip().replace(",", ".")
        try:
            return float(raw)
        except ValueError as error:
            raise ValueError(
                self._t(
                    "Проверьте поле «{name}»: {value}",
                    name=name,
                    value=raw,
                )
            ) from error

    def _int(self, name: str) -> int:
        return int(round(self._float(name)))

    def collect_params(self) -> AnalysisParams:
        params = AnalysisParams(
            channel=self._combo_value("channel"),
            enhancement_method=self._combo_value("enhancement_method"),
            gaussian_sigma=self._float("gaussian_sigma"),
            clahe_clip=self._float("clahe_clip"),
            vessel_sigma_min=self._float("vessel_sigma_min"),
            vessel_sigma_max=self._float("vessel_sigma_max"),
            tophat_radius=self._int("tophat_radius"),
            threshold_method=self._combo_value("threshold_method"),
            threshold_multiplier=self._float("threshold_multiplier"),
            manual_threshold=self._float("manual_threshold"),
            sauvola_window=self._int("sauvola_window"),
            min_object_size=self._int("min_object_size"),
            hole_area=self._int("hole_area"),
            opening_radius=self._int("opening_radius"),
            closing_radius=self._int("closing_radius"),
            dilation_radius=self._int("dilation_radius"),
            erosion_radius=self._int("erosion_radius"),
            invert_mask=bool(self.variables["invert_mask"].get()),
            skeleton_method=self._combo_value("skeleton_method"),
            thin_iterations=self._int("thin_iterations"),
            prune_iterations=self._int("prune_iterations"),
            pixel_size_um=self._float("pixel_size_um"),
            bootstrap_n=self._int("bootstrap_n"),
            uncertainty_range=self._float("uncertainty_range"),
            cluster_mode=self._combo_value("cluster_mode"),
            manual_center_x=self._int("manual_center_x"),
            manual_center_y=self._int("manual_center_y"),
            min_cluster_area=self._int("min_cluster_area"),
            max_clusters=self._int("max_clusters"),
            sholl_radius_step_um=self._float("sholl_radius_step_um"),
            sholl_max_radius_um=self._float("sholl_max_radius_um"),
            ring_width_px=self._float("ring_width_px"),
            skeleton_linewidth=self._float("skeleton_linewidth"),
            show_branch_colors=bool(
                self.variables["show_branch_colors"].get()
            ),
            show_nodes=bool(self.variables["show_nodes"].get()),
            show_scale_bar=bool(
                self.variables["show_scale_bar"].get()
            ),
            scale_bar_um=self._float("scale_bar_um"),
        )
        params.validate()
        return params

    def open_image(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("Выберите изображение"),
            filetypes=(
                (
                    self._t("Изображения"),
                    "*.png *.jpg *.jpeg *.tif *.tiff *.bmp",
                ),
                (self._t("Все файлы"), "*.*"),
            ),
        )
        if not path:
            return
        try:
            image = load_image(path)
        except Exception as error:
            messagebox.showerror(
                self._t("Не удалось открыть изображение"),
                self._t(str(error)),
                parent=self.root,
            )
            return
        self.image_path = Path(path)
        self.image = image
        self.result = None
        self.file_label.configure(
            text=f"{self.image_path.name}  •  {image.shape[1]} × {image.shape[0]} px"
        )
        self.image_panes["original"].set_image(image_to_pil(image))
        for key in ("enhanced", "binary", "skeleton", "overlay"):
            self.image_panes[key].set_image(None)
        self.save_button.configure(state="disabled")
        self._set_status("Изображение загружено")
        self.progress.configure(value=0)

    def start_analysis(self) -> None:
        if self.busy:
            return
        if self.image is None:
            messagebox.showinfo(
                self._t("Нет изображения"),
                self._t("Сначала откройте изображение."),
                parent=self.root,
            )
            return
        try:
            params = self.collect_params()
        except Exception as error:
            messagebox.showerror(
                self._t("Ошибка параметров"),
                self._t(str(error)),
                parent=self.root,
            )
            return

        self._set_busy(True)
        self.save_button.configure(state="disabled")
        self.progress.configure(value=1)
        self._set_status("Запуск обработки…")
        image = self.image.copy()

        def worker() -> None:
            try:
                engine = AnalysisEngine(params)

                def progress(message: str, fraction: float) -> None:
                    self.events.put(("progress", message, fraction))

                result = engine.analyze(image, progress=progress)
                previews = {
                    "original": image_to_pil(result.original),
                    "enhanced": image_to_pil(result.enhanced),
                    "binary": mask_to_pil(result.binary),
                    "skeleton": mask_to_pil(result.skeleton),
                    "overlay": render_overlay(
                        result, self.language_code
                    ),
                }
                self.events.put(("analysis_done", result, previews))
            except Exception as error:
                self.events.put(("error", error, traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def start_export(self) -> None:
        if self.busy or self.result is None or self.image_path is None:
            return
        destination = filedialog.askdirectory(
            title=self._t("Куда сохранить результаты?")
        )
        if not destination:
            return
        self._set_busy(True)
        self._set_status("Сохранение результатов…")
        result = self.result
        stem = self.image_path.stem
        language = self.language_code

        def worker() -> None:
            try:
                folder, archive = export_results(
                    result, destination, stem, language
                )
                self.events.put(("export_done", folder, archive))
            except Exception as error:
                self.events.put(("error", error, traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self._set_status(event[1])
                    self.progress.configure(value=float(event[2]) * 100)
                elif kind == "analysis_done":
                    self._show_result(event[1], event[2])
                elif kind == "export_done":
                    self._set_busy(False)
                    folder, archive = event[1], event[2]
                    self._set_status("Сохранено: {name}", name=folder.name)
                    messagebox.showinfo(
                        self._t("Результаты сохранены"),
                        self._t(
                            "Папка:\n{folder}\n\nАрхив:\n{archive}",
                            folder=folder,
                            archive=archive,
                        ),
                        parent=self.root,
                    )
                elif kind == "error":
                    self._set_busy(False)
                    self._set_status("Ошибка")
                    error = event[1]
                    details = event[2]
                    messagebox.showerror(
                        self._t("Ошибка обработки"),
                        self._t(str(error))
                        if error
                        else self._t("Неизвестная ошибка"),
                        detail=details,
                        parent=self.root,
                    )
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _refresh_tables(self) -> None:
        no_data = self._t("Нет данных")
        columns = column_labels(self.language_code)
        if self.result is None:
            for table in (
                self.metrics_table,
                self.sholl_table,
                self.branches_table,
                self.uncertainty_table,
            ):
                table.set_rows([], no_data_text=no_data)
            return

        metrics = metric_labels(self.language_code)
        metric_table_labels = {
            **metrics,
            "metric": self._t("Показатель"),
            "value": self._t("Значение"),
        }
        uncertainty_rows = [
            {
                **row,
                "metric": metrics.get(row.get("metric"), row.get("metric")),
            }
            for row in self.result.uncertainty
        ]
        self.metrics_table.set_rows(
            [self.result.metrics],
            labels=metric_table_labels,
            transpose=True,
            no_data_text=no_data,
        )
        self.sholl_table.set_rows(
            self.result.sholl_summary,
            labels=columns,
            no_data_text=no_data,
        )
        self.branches_table.set_rows(
            self.result.branches,
            labels=columns,
            no_data_text=no_data,
        )
        self.uncertainty_table.set_rows(
            uncertainty_rows,
            labels=columns,
            no_data_text=no_data,
        )

    def _show_result(
        self,
        result: AnalysisResult,
        previews: dict[str, Image.Image],
    ) -> None:
        self.result = result
        for name, preview in previews.items():
            self.image_panes[name].set_image(preview)
        self._refresh_tables()
        self._set_busy(False)
        self.save_button.configure(state="normal")
        self.progress.configure(value=100)
        self._set_status("Обработка завершена")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.open_button.configure(state=state)
        self.run_button.configure(state=state)
        if busy:
            self.save_button.configure(state="disabled")
        elif self.result is not None:
            self.save_button.configure(state="normal")


def run_app() -> None:
    root = tk.Tk()
    DetectorApp(root)
    root.mainloop()
