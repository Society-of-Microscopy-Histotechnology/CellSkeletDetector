# Cell Skeleton Detector

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21709108.svg)](https://doi.org/10.5281/zenodo.21709108)

A Windows application for skeletonization, morphometry, and multi-center
Sholl analysis of astrocyte images. It is based on the **penultimate**
version of the code from `Untitled5.ipynb` (cell 5 of 7).

## Quick Start from the Terminal

Run the following command in PowerShell from the project directory:

```powershell
.\run.ps1
```

If Python and the required libraries are not installed yet:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\run.ps1
```

PNG, JPEG, BMP, and TIFF images are supported. First click
`Открыть изображение` (Open Image), configure the main parameters, and click
`Обработать` (Process). Advanced parameters are available on a separate tab.

## Exported Results

The `Сохранить результаты` (Save Results) button creates a separate directory
and a ZIP archive containing:

- the enhanced signal, binary mask, and white skeleton;
- a Neurolucida-like overlay with centers and Sholl circles;
- primary metrics, branch measurements, Sholl results, and bootstrap
  estimates in CSV format;
- processing parameters in JSON format;
- an HTML report that can be opened in any web browser.

CSV files are encoded as UTF-8 with BOM and use `;` as the delimiter for
compatibility with localized versions of Microsoft Excel.

## Optimizations

- The scientific processing core is separated from the UI and Colab.
- `ipywidgets`, `google.colab`, OpenCV, Matplotlib, and the unused NetworkX
  dependency were removed from the application.
- Sholl analysis limits its calculations to the area within the maximum
  radius.
- Processing and export run in background threads, keeping the UI responsive.
- Branching points are counted as connected nodes rather than individual
  pixels.
- Bootstrap standard deviation and standard error are calculated separately.
- Parameter validation and support for 16-bit TIFF images and empty results
  were added.

The manual threshold is applied as an absolute value from 0 to 1. The threshold
multiplier is used only by automatic global thresholding methods.

## Tests

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Building the EXE

```powershell
.\build.ps1
```

The standalone executable will be created at
`dist\CellSkeletDetector.exe`. It does not require Python to be installed on
the user's computer.

This application is intended for research image processing. Before drawing
quantitative conclusions, validate its parameters and results against a
manually annotated control dataset.
