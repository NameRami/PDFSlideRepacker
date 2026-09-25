# PDF Slide Repacker

> Automatically detect, extract, and repack presentation slides from PDF handouts into clean, readable PDF layouts.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-NameRami-black?logo=github)](https://github.com/NameRami)

**PDF Slide Repacker** is a Python utility for recovering presentation slides from PDF handouts where multiple tiny slides have been placed on a single A4 page.

It automatically detects bordered slides, extracts them, removes unnecessary surrounding whitespace and page furniture, and lets you rebuild the document into a cleaner PDF with the layout you actually want.

---

## Why this project exists

Lecture notes and course materials are often distributed as PDF handouts where several slides are squeezed onto one page.

A typical page might contain:

- 6 tiny slides
- excessive white margins
- dates
- page numbers
- headers or footers
- partially filled slide grids

That makes the document harder to read and awkward to print or study from.

**PDF Slide Repacker** solves that by detecting the actual slide rectangles and rebuilding the document around them.

---

## Features

### Automatic slide detection

The program detects slides by analyzing their visible rectangular borders.

It does **not** rely on a fixed 2×3 grid, so it can handle pages containing different numbers of slides.

The detector includes:

- dark-border detection
- contour filtering
- duplicate suppression
- nested rectangle rejection
- size consistency checks
- reading-order sorting

This helps prevent large boxes or diagrams inside a slide from being incorrectly detected as separate slides.

---

### Extract individual slides

Detected slides can be exported as PNG files:

```text
lecture_slides/
├── slide_0001.png
├── slide_0002.png
├── slide_0003.png
├── slide_0004.png
└── ...
```

This is useful for:

- studying slides individually
- importing them into note-taking software
- rebuilding presentations
- OCR workflows
- image processing
- archiving

---

### Repack slides into a new PDF

You can rebuild the extracted slides into a fresh A4 PDF.

Choose how many slides should appear on each page:

```text
1
2
3
4
5
6
...
up to 12
```

---

### Portrait, landscape, or automatic orientation

Choose:

```text
Portrait
Landscape
Auto
```

In **Auto** mode, the program selects the A4 orientation that allows the slides to appear larger.

---

### Custom spacing between slides

You can control the gap between neighboring slides in millimeters.

Examples:

```text
0 mm    maximum slide size
2 mm    compact
4 mm    default
8 mm    wider spacing
```

Decimal values are supported:

```text
2.5
```

and comma decimal notation works too:

```text
2,5
```

---

### Process one PDF or every PDF in the folder

The program supports:

- processing one selected PDF
- processing all source PDFs in the script folder

Generated output PDFs are ignored during batch processing so they are not accidentally processed again.

---

### Output to a dedicated subfolder

You can save generated files:

- beside the source PDFs
- or inside a custom subfolder

Example:

```text
Course PDFs/
├── pdf_slide_repacker.py
├── Lecture_01.pdf
├── Lecture_02.pdf
└── Processed/
    ├── Lecture_01_slides/
    ├── Lecture_02_slides/
    ├── Lecture_01_repacked_4up_landscape.pdf
    └── Lecture_02_repacked_4up_landscape.pdf
```

---

### Fully interactive mode

No command-line arguments need to be memorized.

Run the script and follow the menu:

```text
========================================================================
       PDF HANDOUT SLIDE EXTRACTOR / REPACKER
========================================================================

What do you want to do?

  1. Extract slides only
  2. Merge/repack slides that were already extracted
  3. Extract slides AND create a custom merged PDF
  4. Exit
```

The program then asks for:

- which PDF to process
- one PDF or all PDFs
- output location
- slides per page
- page orientation
- slide spacing
- rendering DPI
- debug output
- custom output filename

---

## Workflow

```text
Original PDF
     │
     ▼
Render each PDF page
     │
     ▼
Detect dark rectangular slide borders
     │
     ▼
Filter false positives
     │
     ▼
Sort slides in reading order
     │
     ▼
Crop each detected slide
     │
     ├──────────────► Save individual PNG files
     │
     ▼
Choose A4 layout
     │
     ▼
Repack slides
     │
     ▼
New clean PDF
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/NameRami/PDFSlideRepacker.git
```

Enter the project directory:

```bash
cd PDFSlideRepacker
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Or install them manually:

```bash
python -m pip install pymupdf opencv-python numpy pillow
```

If your Python installation requires user-level packages:

```bash
python -m pip install --user pymupdf opencv-python numpy pillow
```

---

## Requirements

- Python 3.10+
- PyMuPDF
- OpenCV
- NumPy
- Pillow

`requirements.txt`:

```text
PyMuPDF
opencv-python
numpy
Pillow
```

---

## Usage

### Option 1 — Run from IDLE

Open:

```text
pdf_slide_repacker.py
```

Then press:

```text
F5
```

The interactive menu will appear.

---

### Option 2 — Run from a terminal

```bash
python pdf_slide_repacker.py
```

The same interactive menu will appear.

---

## Recommended folder setup

Place the script and your source PDFs together:

```text
My Course/
├── pdf_slide_repacker.py
├── lecture_01.pdf
├── lecture_02.pdf
└── lecture_03.pdf
```

Then run the script.

---

## Available modes

### 1. Extract slides only

Extracts every detected slide as an individual image.

Example:

```text
lecture_01_slides/
├── slide_0001.png
├── slide_0002.png
├── slide_0003.png
└── ...
```

---

### 2. Merge already-extracted slides

Reuses an existing `*_slides` directory.

This is useful when experimenting with several output layouts without repeating slide detection.

For example:

```text
2 slides / portrait
4 slides / landscape
6 slides / portrait
```

---

### 3. Extract and merge

Runs the full workflow:

```text
PDF
 ↓
Detection
 ↓
Extraction
 ↓
Repacking
 ↓
Custom output PDF
```

---

## Detection strategy

PDF Slide Repacker uses several image-processing stages.

### 1. PDF rendering

Each PDF page is rendered at a configurable DPI using **PyMuPDF**.

Default:

```text
180 DPI
```

Higher values may improve detection on difficult PDFs.

---

### 2. Grayscale conversion

Rendered pages are converted to grayscale.

---

### 3. Dark-pixel thresholding

Dark lines are isolated so slide borders stand out from the background.

---

### 4. Morphological processing

OpenCV horizontal and vertical kernels reconnect small gaps in borders.

---

### 5. Contour detection

Large rectangular contours are filtered using:

- page-relative area
- width
- height
- aspect ratio
- rectangularity

---

### 6. Duplicate suppression

Inner and outer edges of the same slide border can create duplicate contours.

Intersection-over-union filtering removes those duplicates.

---

### 7. Nested rectangle rejection

Large boxes, diagrams, or content regions inside slides can sometimes look like separate slide rectangles.

If a smaller candidate is almost entirely inside a larger valid slide candidate, it is rejected.

---

### 8. Page-level consistency checks

Slides on the same page normally have similar dimensions.

Strong size outliers are filtered out.

---

### 9. Reading-order sorting

Slides are exported in:

```text
top → bottom
left → right
```

order.

---

## Debug mode

The program can save debug images showing the slide rectangles it detected.

Example:

```text
lecture_debug/
├── page_001_detected.jpg
├── page_002_detected.jpg
└── ...
```

This is useful when troubleshooting unusual PDFs.

---

## Output naming

Automatically generated PDFs use this pattern:

```text
SOURCE_repacked_NUMBERup_ORIENTATION.pdf
```

Examples:

```text
lecture_repacked_2up_portrait.pdf
lecture_repacked_4up_landscape.pdf
lecture_repacked_6up_auto.pdf
```

For single-file processing, you can also enter your own filename.

---

## Example use cases

PDF Slide Repacker is useful for:

- university lecture handouts
- PowerPoint printouts
- training materials
- conference presentations
- course PDFs
- corporate handouts
- archived slide decks
- scanned presentation pages
- making tiny multi-slide PDFs readable again

---

## Known limitations

The project currently works best when slides have clearly visible rectangular borders.

Detection may need tuning when:

- slides have no border
- borders are extremely faint
- the page background is dark
- slides overlap
- scans are heavily rotated
- layouts are highly irregular
- borders are severely broken

The detection constants are kept near the top of the source code so advanced users can tune them.

---

## Future improvements

Possible future features:

- graphical user interface
- drag-and-drop support
- PDF preview
- visual crop editor
- automatic threshold calibration
- borderless slide detection
- deskewing for scanned pages
- OCR-assisted detection
- vector-preserving PDF extraction
- custom page sizes
- configurable outer page margins
- slide reordering
- excluding individual slides
- Windows standalone `.exe`
- macOS application bundle
- Linux package

---

## Technical stack

PDF Slide Repacker uses:

- **PyMuPDF** — PDF rendering and PDF creation
- **OpenCV** — slide-border and contour detection
- **NumPy** — image and geometry processing
- **Pillow** — image export and metadata handling

---

## Repository structure

```text
PDFSlideRepacker/
├── pdf_slide_repacker.py
├── README.md
├── requirements.txt
├── LICENSE
├── .gitignore
└── examples/
    └── README.md
```

---

## Contributing

Contributions are welcome.

If you find a PDF that is detected incorrectly, a useful issue report should include:

- expected number of slides
- detected number of slides
- debug image
- Python version
- operating system
- a sample page if you are allowed to share it

Please do not upload confidential or copyrighted course material unless you have permission to share it.

---

## License

This project is released under the **MIT License**.

See [`LICENSE`](LICENSE) for details.

---

## Author

Created and maintained by **NameRami**.

GitHub:

**https://github.com/NameRami**

Repository:

**https://github.com/NameRami/PDFSlideRepacker**

---

## Project philosophy

> You should not have to manually crop dozens or hundreds of presentation slides just because the original PDF was exported as a handout.

PDF Slide Repacker automates the repetitive work while keeping control over the final layout in the user's hands.

---

## Acknowledgements

Built for anyone who has ever opened a lecture PDF, discovered six tiny slides squeezed onto a page with huge margins, and thought:

> There has to be a better way.

There is now.
