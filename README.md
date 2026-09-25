# PDF Slide Repacker

> Automatically detect, extract, and repack presentation slides from PDF handouts into clean, readable PDF layouts.

**PDF Slide Repacker** is a Python utility designed for a very common problem: presentation slides that have been exported or printed into PDF handouts containing multiple tiny slides per A4 page, often surrounded by excessive margins, dates, page numbers, headers, or other unwanted content.

Instead of manually cropping every slide, PDF Slide Repacker detects the slide borders automatically, extracts each slide, and lets you rebuild the presentation into a new PDF with the layout you actually want.

---

## Why this project exists

Many lecture notes, course materials, and presentation handouts are distributed as PDFs where several slides are squeezed onto a single A4 page.

A typical source page may look like this:

```text
+------------------------------------------------------+
|                                           25/09/2026 |
|                                                      |
|    +----------------+    +----------------+          |
|    |                |    |                |          |
|    |    Slide 1     |    |    Slide 2     |          |
|    |                |    |                |          |
|    +----------------+    +----------------+          |
|                                                      |
|    +----------------+    +----------------+          |
|    |                |    |                |          |
|    |    Slide 3     |    |    Slide 4     |          |
|    |                |    |                |          |
|    +----------------+    +----------------+          |
|                                                      |
|    +----------------+    +----------------+          |
|    |                |    |                |          |
|    |    Slide 5     |    |    Slide 6     |          |
|    |                |    |                |          |
|    +----------------+    +----------------+          |
|                                                   12 |
+------------------------------------------------------+
```

The slides themselves may occupy only a fraction of the page.

PDF Slide Repacker turns that into individually detected slides and lets you reconstruct the document using layouts such as:

```text
1 slide per page
2 slides per page
4 slides per page
6 slides per page
...
```

with your preferred A4 orientation and spacing.

---

## Features

### Automatic slide detection

The program analyzes every PDF page and detects large rectangular slide borders using OpenCV.

It does **not** rely on a fixed 2x3 grid.

This means it can handle pages containing:

- 6 slides
- 4 slides
- 2 slides
- partially filled pages
- different slide positions
- extra text outside the slides

The detector also includes protection against false detections caused by large rectangular objects *inside* a slide.

---

### Extract individual slides

Every detected slide can be exported as a separate image:

```text
course_slides/
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
- image processing
- OCR workflows
- creating new PDFs

---

### Repack slides into a new PDF

Extracted slides can be placed into a fresh A4 PDF.

You choose how many slides should appear on each page.

Supported values include:

```text
1
2
3
4
5
6
...
up to 12 slides per page
```

---

### Portrait, landscape, or automatic orientation

You can explicitly choose:

```text
Portrait
Landscape
Auto
```

In **Auto** mode, the program compares both A4 orientations and selects the one that allows the slides to be displayed larger.

---

### Custom spacing between slides

The distance between slides can be configured in millimeters.

Examples:

```text
0 mm    maximum slide size
2 mm    very compact
4 mm    default
8 mm    wider separation
```

Decimal values are supported:

```text
2.5
```

and comma decimal notation also works:

```text
2,5
```

---

### Process one PDF or an entire folder

The program can operate on:

- one selected PDF
- all source PDFs in the current folder

Generated PDFs are automatically ignored when batch processing, preventing accidental recursive processing.

---

### Dedicated output folders

Output files can either be saved beside the source PDFs or inside a custom subfolder.

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

### Interactive mode

No command-line arguments need to be memorized.

Run the Python file directly from IDLE, VS Code, PyCharm, a terminal, or another Python environment.

The program presents an interactive menu:

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

The program then guides you through each setting.

---

## Workflow

PDF Slide Repacker follows this pipeline:

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

## Detection strategy

The slide detector uses several techniques together rather than relying on one simple contour search.

### 1. PDF rendering

Each page is rendered at a configurable DPI using **PyMuPDF**.

Higher rendering resolutions can improve border detection.

Default:

```text
180 DPI
```

---

### 2. Grayscale conversion

Rendered pages are converted to grayscale so that dark borders can be isolated efficiently.

---

### 3. Dark-pixel thresholding

Dark lines are converted into a binary mask.

This makes black or dark slide borders stand out from the page background.

---

### 4. Morphological processing

Horizontal and vertical OpenCV kernels reconnect small breaks in slide borders.

This improves detection when PDF rendering produces imperfect or interrupted lines.

---

### 5. Contour detection

Large rectangular contours are identified and filtered according to:

- page-relative area
- width
- height
- aspect ratio
- rectangularity

---

### 6. Duplicate suppression

Borders often generate both an inner and outer contour.

Intersection-over-union filtering removes duplicate detections.

---

### 7. Nested rectangle rejection

Some slides contain large internal rectangles, tables, diagrams, or text boxes.

If a smaller candidate is almost completely contained inside a larger valid slide candidate, the smaller candidate is rejected.

This prevents one slide from accidentally being detected as two.

---

### 8. Page-level consistency checking

Slides on the same handout page normally have similar dimensions.

The detector compares candidates against the median slide width and height and removes strong size outliers.

---

### 9. Reading-order sorting

Detected slides are arranged from:

```text
top → bottom
left → right
```

before being exported.

---

## Requirements

- Python 3.10+ recommended
- Windows, Linux, or macOS
- PyMuPDF
- OpenCV
- NumPy
- Pillow

Install dependencies with:

```bash
python -m pip install pymupdf opencv-python numpy pillow
```

On systems where Python packages must be installed only for the current user:

```bash
python -m pip install --user pymupdf opencv-python numpy pillow
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/pdf-slide-repacker.git
```

Enter the project directory:

```bash
cd pdf-slide-repacker
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Or install them manually:

```bash
python -m pip install pymupdf opencv-python numpy pillow
```

---

## Recommended repository structure

```text
pdf-slide-repacker/
├── pdf_slide_repacker.py
├── README.md
├── requirements.txt
├── LICENSE
├── .gitignore
└── examples/
    └── README.md
```

A minimal `requirements.txt` can contain:

```text
PyMuPDF
opencv-python
numpy
Pillow
```

---

## Usage

### Interactive usage

Place the Python script in the same folder as your PDFs:

```text
My Course/
├── pdf_slide_repacker.py
├── lecture_01.pdf
├── lecture_02.pdf
└── lecture_03.pdf
```

Run:

```bash
python pdf_slide_repacker.py
```

Or open the file in Python IDLE and press:

```text
F5
```

The program will guide you through the process.

---

## Available modes

### 1. Extract slides only

Detects and exports each slide as an individual image.

Example output:

```text
lecture_01_slides/
├── slide_0001.png
├── slide_0002.png
├── slide_0003.png
└── ...
```

---

### 2. Merge already-extracted slides

Uses an existing `*_slides` folder and builds a new PDF.

This is useful when experimenting with different layouts because slide detection does not have to run again.

For example, you can create:

```text
2 slides / portrait
4 slides / landscape
6 slides / portrait
```

from the same extracted slide set.

---

### 3. Extract and merge

Runs the complete process automatically:

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

## Debug mode

The program can save debug images showing every detected slide rectangle.

Example:

```text
lecture_01_debug/
├── page_001_detected.jpg
├── page_002_detected.jpg
└── ...
```

These images are useful when adjusting detection parameters for unusual PDFs.

---

## Output naming

Automatically generated PDFs follow this pattern:

```text
SOURCE_repacked_NUMBERup_ORIENTATION.pdf
```

Examples:

```text
lecture_repacked_2up_portrait.pdf
lecture_repacked_4up_landscape.pdf
lecture_repacked_6up_auto.pdf
```

A custom filename can also be entered when processing a single PDF.

---

## Example use cases

PDF Slide Repacker can be useful for:

- university lecture handouts
- PowerPoint printouts
- training materials
- conference presentations
- course PDFs
- corporate presentation handouts
- archived slide decks
- scanned or printed presentation pages
- rebuilding compact lecture notes into readable slides

---

## Known limitations

PDF Slide Repacker currently works best when the original slides have clearly visible rectangular borders.

Detection may require adjustment when:

- slides have no border
- borders are extremely faint
- the page background is very dark
- slides overlap
- borders are heavily broken
- scanned pages are strongly rotated
- the document uses highly irregular layouts

The detector parameters are intentionally kept near the top of the source code so advanced users can tune them.

---

## Future ideas

Possible future improvements include:

- graphical user interface
- drag-and-drop PDF support
- PDF preview before processing
- visual crop editor
- automatic border-threshold calibration
- borderless slide detection
- deskewing for scanned PDFs
- OCR-assisted slide detection
- preserving PDF vector content instead of rasterizing
- custom page sizes
- configurable outer page margins
- reorder slides before export
- delete or exclude selected slides
- Windows standalone `.exe`
- macOS application bundle
- Linux package
- automatic update checker

---

## Technical stack

PDF Slide Repacker uses:

- **PyMuPDF** for PDF rendering and PDF generation
- **OpenCV** for border and contour detection
- **NumPy** for image and geometry processing
- **Pillow** for image export and image metadata

---

## Philosophy

The project is intentionally designed around a simple principle:

> The user should not have to manually crop dozens or hundreds of presentation slides just because the original PDF was exported as a handout.

The tool tries to automate the repetitive work while still giving the user control over the final layout.

---

## Contributing

Contributions are welcome.

Ideas, bug reports, improvements, and pull requests are encouraged.

If you encounter a PDF that is not detected correctly, a useful bug report should ideally include:

- a sample page
- the expected number of slides
- the detected number of slides
- the generated debug image
- operating system
- Python version

Please avoid uploading confidential or copyrighted course material unless you have permission to share it.

---

## License

A permissive license such as the **MIT License** is a good choice for this project.

If you use MIT, add a `LICENSE` file containing the standard MIT license text and your copyright information.

---

## Project name

**PDF Slide Repacker**

Suggested GitHub repository name:

```text
pdf-slide-repacker
```

Suggested GitHub description:

> Automatically detect, extract, and repack presentation slides from PDF handouts. Supports batch processing, custom A4 layouts, portrait/landscape output, configurable spacing, and interactive operation.

---

## Acknowledgements

Built for anyone who has ever opened a lecture PDF, discovered six tiny slides squeezed onto one page with enormous margins, and thought:

> There has to be a better way.

There is now.
