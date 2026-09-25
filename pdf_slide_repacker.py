#!/usr/bin/env python3
"""
extract_slides_from_handout.py

Detect slide rectangles inside PDF handout pages, extract them,
and optionally rebuild them into a new A4 PDF with a chosen number
of slides per page.

Typical input:
- A4 PDF pages
- several presentation slides per page
- each slide has a visible dark/black rectangular border
- extra text such as date/page number outside the slide rectangles

Dependencies:
    pip install pymupdf opencv-python numpy pillow

Examples:
    python extract_slides_from_handout.py input.pdf
    python extract_slides_from_handout.py input.pdf --per-page 1
    python extract_slides_from_handout.py input.pdf --per-page 4
    python extract_slides_from_handout.py input.pdf --per-page 6 --debug

Outputs:
    <input>_slides/slide_0001.png ...
    <input>_extracted.pdf
    <input>_repacked_4up.pdf
"""

import argparse
import math
from pathlib import Path

import cv2
import pymupdf as fitz  # PyMuPDF
import numpy as np
from PIL import Image


# ----------------------------
# Configuration / heuristics
# ----------------------------

DEFAULT_DPI = 180

# Minimum/maximum fraction of rendered PDF page occupied by a slide candidate.
MIN_AREA_FRAC = 0.045
MAX_AREA_FRAC = 0.42

# Most presentation slides are landscape. We keep a broad range because
# exported handouts can distort them slightly.
MIN_ASPECT = 1.15
MAX_ASPECT = 2.20

# Ignore very thin rectangles / lines.
MIN_WIDTH_FRAC = 0.18
MIN_HEIGHT_FRAC = 0.10

# Border detection threshold.
DARK_THRESHOLD = 110

# Padding around detected slide border, in rendered-image pixels.
CROP_PADDING = 4


def render_pdf_page(page, dpi=DEFAULT_DPI):
    """Render a PyMuPDF page to a BGR OpenCV image."""
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8)
    arr = arr.reshape(pix.height, pix.width, pix.n)

    if pix.n == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    else:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    return arr


def iou(a, b):
    """Intersection-over-union for rectangles x,y,w,h."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - inter

    return inter / union if union else 0.0


def deduplicate_rectangles(rects, threshold=0.80):
    """
    Remove duplicate rectangles caused by finding both the inside and outside
    edges of the same black border.
    """
    rects = sorted(rects, key=lambda r: r[2] * r[3], reverse=True)
    kept = []

    for rect in rects:
        if all(iou(rect, existing) < threshold for existing in kept):
            kept.append(rect)

    return kept


def detect_slide_rectangles(image, debug=False):
    """
    Find large rectangular black-bordered regions likely to be slides.

    Returns:
        rects: list of (x, y, w, h), sorted reading order
        debug_image: annotated image if debug=True, else None
    """
    h, w = image.shape[:2]
    page_area = w * h

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Black / dark pixels become white in the binary image.
    mask = cv2.threshold(
        gray,
        DARK_THRESHOLD,
        255,
        cv2.THRESH_BINARY_INV
    )[1]

    # Connect small breaks in the slide borders.
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9))

    horiz = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_h, iterations=2)
    vert = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_v, iterations=2)
    combined = cv2.bitwise_or(horiz, vert)

    # Slightly strengthen connected rectangles.
    combined = cv2.dilate(
        combined,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
        iterations=1
    )

    contours, _ = cv2.findContours(
        combined,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE
    )

    candidates = []

    for cnt in contours:
        x, y, rw, rh = cv2.boundingRect(cnt)
        area = rw * rh

        if area < MIN_AREA_FRAC * page_area:
            continue

        if area > MAX_AREA_FRAC * page_area:
            continue

        if rw < MIN_WIDTH_FRAC * w or rh < MIN_HEIGHT_FRAC * h:
            continue

        aspect = rw / float(rh)

        if not (MIN_ASPECT <= aspect <= MAX_ASPECT):
            continue

        # Candidate should resemble a rectangle.
        contour_area = cv2.contourArea(cnt)
        rectangularity = contour_area / float(area) if area else 0

        # A border itself can have low filled contour area, so be permissive.
        if rectangularity < 0.05:
            continue

        candidates.append((x, y, rw, rh))

    candidates = deduplicate_rectangles(candidates)

    # Remove false "slides" detected INSIDE a real slide.
    #
    # Example:
    #   - outer rectangle = actual slide border
    #   - inner rectangle = a large text/content box or another strong
    #     rectangular structure within the slide
    #
    # The old version only removed near-duplicate nested rectangles.
    # This version removes any smaller candidate that is almost completely
    # contained inside a larger slide-like candidate.
    def intersection_area(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b

        x1 = max(ax, bx)
        y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw)
        y2 = min(ay + ah, by + bh)

        return max(0, x2 - x1) * max(0, y2 - y1)

    filtered = []

    for small in candidates:
        sx, sy, sw, sh = small
        small_area = sw * sh
        discard = False

        for large in candidates:
            if small == large:
                continue

            lx, ly, lw, lh = large
            large_area = lw * lh

            # Only compare against genuinely larger rectangles.
            if large_area <= small_area * 1.12:
                continue

            inter = intersection_area(small, large)
            contained_fraction = inter / float(small_area) if small_area else 0.0

            # If at least 92% of the smaller candidate lies inside a
            # significantly larger candidate, it is almost certainly an
            # internal content rectangle rather than another slide.
            if contained_fraction >= 0.92:
                discard = True
                break

        if not discard:
            filtered.append(small)

    # Extra page-level consistency filter:
    # real slides on a handout page normally have nearly identical dimensions.
    # If we have several candidates, reject strong size outliers.
    if len(filtered) >= 3:
        widths = np.array([r[2] for r in filtered], dtype=float)
        heights = np.array([r[3] for r in filtered], dtype=float)

        median_w = float(np.median(widths))
        median_h = float(np.median(heights))

        consistent = []
        for r in filtered:
            _, _, rw, rh = r

            width_ratio = rw / median_w if median_w else 1.0
            height_ratio = rh / median_h if median_h else 1.0

            # Broad enough for slight PDF/rendering differences, but rejects
            # things like a content box that is much shorter than the slides.
            if 0.78 <= width_ratio <= 1.22 and 0.72 <= height_ratio <= 1.28:
                consistent.append(r)

        # Do not apply the filter if it would throw almost everything away.
        if len(consistent) >= max(2, len(filtered) // 2):
            filtered = consistent

    # Reading order: row-major. Group rectangles by approximate Y position.
    filtered.sort(key=lambda r: (r[1], r[0]))

    rows = []
    for rect in filtered:
        cy = rect[1] + rect[3] / 2

        matched = False
        for row in rows:
            row_cy = np.mean([r[1] + r[3] / 2 for r in row])
            typical_h = np.mean([r[3] for r in row])

            if abs(cy - row_cy) < typical_h * 0.45:
                row.append(rect)
                matched = True
                break

        if not matched:
            rows.append([rect])

    rows.sort(key=lambda row: min(r[1] for r in row))

    ordered = []
    for row in rows:
        row.sort(key=lambda r: r[0])
        ordered.extend(row)

    dbg = None

    if debug:
        dbg = image.copy()
        for idx, (x, y, rw, rh) in enumerate(ordered, start=1):
            cv2.rectangle(dbg, (x, y), (x + rw, y + rh), (0, 0, 255), 4)
            cv2.putText(
                dbg,
                str(idx),
                (x + 8, y + 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                3,
                cv2.LINE_AA
            )

    return ordered, dbg


def crop_slide(image, rect, padding=CROP_PADDING):
    """Crop a detected slide rectangle."""
    x, y, w, h = rect
    H, W = image.shape[:2]

    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(W, x + w + padding)
    y2 = min(H, y + h + padding)

    return image[y1:y2, x1:x2]


def save_png(path, bgr_image):
    rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb).save(path, optimize=True)


def slides_to_pdf(slide_paths, output_pdf):
    """
    Create a PDF with one extracted slide per PDF page.
    Page dimensions match each slide's image aspect ratio.
    """
    doc = fitz.open()

    for slide_path in slide_paths:
        img = Image.open(slide_path)
        iw, ih = img.size

        # Use points with a convenient width.
        page_w = 960
        page_h = page_w * ih / iw

        page = doc.new_page(width=page_w, height=page_h)
        page.insert_image(page.rect, filename=str(slide_path))

    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()


def best_grid(per_page, page_width, page_height, slide_aspect):
    """
    Select rows/columns that maximize slide size on the target page.
    """
    best = None

    for cols in range(1, per_page + 1):
        rows = math.ceil(per_page / cols)

        cell_w = page_width / cols
        cell_h = page_height / rows

        # Maximum rectangle with slide_aspect inside a cell.
        if cell_w / cell_h > slide_aspect:
            draw_h = cell_h
            draw_w = draw_h * slide_aspect
        else:
            draw_w = cell_w
            draw_h = draw_w / slide_aspect

        area = draw_w * draw_h

        if best is None or area > best[0]:
            best = (area, rows, cols)

    _, rows, cols = best
    return rows, cols


def repack_to_a4(
    slide_paths,
    output_pdf,
    per_page=4,
    orientation="auto",
    margin_mm=8,
    gap_mm=4
):
    """
    Repack slides onto A4.

    orientation:
        "portrait"  -> force A4 portrait
        "landscape" -> force A4 landscape
        "auto"      -> choose whichever gives larger slides
    """
    if not slide_paths:
        return

    sample = Image.open(slide_paths[0])
    slide_aspect = sample.width / sample.height

    MM_TO_PT = 72 / 25.4
    a4_portrait = (210 * MM_TO_PT, 297 * MM_TO_PT)
    a4_landscape = (297 * MM_TO_PT, 210 * MM_TO_PT)

    margin = margin_mm * MM_TO_PT
    gap = gap_mm * MM_TO_PT

    def evaluate(page_size):
        pw, ph = page_size
        usable_w = pw - 2 * margin
        usable_h = ph - 2 * margin

        rows, cols = best_grid(per_page, usable_w, usable_h, slide_aspect)

        cell_w = (usable_w - gap * (cols - 1)) / cols
        cell_h = (usable_h - gap * (rows - 1)) / rows

        if cell_w / cell_h > slide_aspect:
            draw_h = cell_h
            draw_w = draw_h * slide_aspect
        else:
            draw_w = cell_w
            draw_h = draw_w / slide_aspect

        return draw_w * draw_h, rows, cols, cell_w, cell_h

    portrait_eval = evaluate(a4_portrait)
    landscape_eval = evaluate(a4_landscape)

    orientation = orientation.lower()

    if orientation == "portrait":
        page_size = a4_portrait
        _, rows, cols, cell_w, cell_h = portrait_eval

    elif orientation == "landscape":
        page_size = a4_landscape
        _, rows, cols, cell_w, cell_h = landscape_eval

    elif orientation == "auto":
        if landscape_eval[0] > portrait_eval[0]:
            page_size = a4_landscape
            _, rows, cols, cell_w, cell_h = landscape_eval
        else:
            page_size = a4_portrait
            _, rows, cols, cell_w, cell_h = portrait_eval

    else:
        raise ValueError(
            "orientation must be 'portrait', 'landscape', or 'auto'"
        )

    page_w, page_h = page_size
    doc = fitz.open()

    for start in range(0, len(slide_paths), per_page):
        batch = slide_paths[start:start + per_page]
        page = doc.new_page(width=page_w, height=page_h)

        for i, slide_path in enumerate(batch):
            row = i // cols
            col = i % cols

            x0 = margin + col * (cell_w + gap)
            y0 = margin + row * (cell_h + gap)

            img = Image.open(slide_path)
            aspect = img.width / img.height

            if cell_w / cell_h > aspect:
                draw_h = cell_h
                draw_w = draw_h * aspect
            else:
                draw_w = cell_w
                draw_h = draw_w / aspect

            dx = (cell_w - draw_w) / 2
            dy = (cell_h - draw_h) / 2

            rect = fitz.Rect(
                x0 + dx,
                y0 + dy,
                x0 + dx + draw_w,
                y0 + dy + draw_h
            )

            page.insert_image(rect, filename=str(slide_path), keep_proportion=True)

    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()


def process_pdf(input_pdf, per_page=1, orientation='auto', dpi=DEFAULT_DPI, debug=False):
    input_pdf = Path(input_pdf)

    if not input_pdf.exists():
        raise FileNotFoundError(input_pdf)

    stem = input_pdf.stem
    out_dir = input_pdf.with_name(f"{stem}_slides")
    out_dir.mkdir(exist_ok=True)

    debug_dir = output_root / f"{stem}_debug"
    if debug:
        debug_dir.mkdir(exist_ok=True)

    doc = fitz.open(input_pdf)
    slide_paths = []
    slide_number = 1

    print(f"Input: {input_pdf}")
    print(f"Pages: {len(doc)}")
    print(f"Rendering at {dpi} DPI")
    print(f"Slides per A4 page: {per_page}")
    print(f"Orientation: {orientation}")
    print()

    for page_index in range(len(doc)):
        page = doc[page_index]
        image = render_pdf_page(page, dpi=dpi)

        rects, dbg = detect_slide_rectangles(image, debug=debug)

        print(
            f"Page {page_index + 1:03d}: "
            f"detected {len(rects)} slide candidate(s)"
        )

        if debug and dbg is not None:
            dbg_path = debug_dir / f"page_{page_index + 1:03d}_detected.jpg"
            cv2.imwrite(str(dbg_path), dbg)

        for rect in rects:
            slide = crop_slide(image, rect)
            slide_path = out_dir / f"slide_{slide_number:04d}.png"
            save_png(slide_path, slide)
            slide_paths.append(slide_path)
            slide_number += 1

    doc.close()

    if not slide_paths:
        print()
        print("No slide rectangles were detected.")
        print("Try:")
        print("  --debug")
        print("  --dpi 250")
        print("or adjust the detection constants near the top of the script.")
        return

    extracted_pdf = input_pdf.with_name(f"{stem}_extracted.pdf")
    slides_to_pdf(slide_paths, extracted_pdf)

    repacked_pdf = input_pdf.with_name(
        f"{stem}_repacked_{per_page}up_{orientation}.pdf"
    )
    repack_to_a4(
        slide_paths,
        repacked_pdf,
        per_page=per_page,
        orientation=orientation
    )

    print()
    print(f"Extracted slides: {len(slide_paths)}")
    print(f"Images folder:     {out_dir}")
    print(f"1 slide/page PDF:  {extracted_pdf}")
    print(f"A4 repacked PDF:   {repacked_pdf}")

    if debug:
        print(f"Debug previews:    {debug_dir}")



def _input_int(prompt, minimum=None, maximum=None, default=None):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()

        if not value and default is not None:
            return default

        try:
            value = int(value)
        except ValueError:
            print("Please enter a number.")
            continue

        if minimum is not None and value < minimum:
            print(f"Please enter a number >= {minimum}.")
            continue

        if maximum is not None and value > maximum:
            print(f"Please enter a number <= {maximum}.")
            continue

        return value


def _input_float(prompt, minimum=None, maximum=None, default=None):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()

        if not value and default is not None:
            return float(default)

        # Accept both 2.5 and 2,5 for convenience.
        value = value.replace(",", ".")

        try:
            value = float(value)
        except ValueError:
            print("Please enter a valid number.")
            continue

        if minimum is not None and value < minimum:
            print(f"Please enter a number >= {minimum}.")
            continue

        if maximum is not None and value > maximum:
            print(f"Please enter a number <= {maximum}.")
            continue

        return value


def _input_choice(prompt, choices, default=None):
    """
    choices: list of tuples: (key, label)
    """
    valid = {str(k).lower(): (k, label) for k, label in choices}

    while True:
        print()
        print(prompt)
        for key, label in choices:
            default_mark = "  [default]" if default is not None and str(key) == str(default) else ""
            print(f"  {key}. {label}{default_mark}")

        value = input("> ").strip().lower()

        if not value and default is not None:
            value = str(default).lower()

        if value in valid:
            return valid[value][0]

        print("Invalid choice. Please try again.")


def _is_generated_pdf(path):
    """
    Avoid accidentally re-processing output PDFs produced by this script.
    """
    name = path.stem.lower()

    generated_tokens = (
        "_extracted",
        "_repacked_",
    )

    return any(token in name for token in generated_tokens)


def _source_pdfs(folder):
    return sorted(
        p for p in folder.glob("*.pdf")
        if p.is_file() and not _is_generated_pdf(p)
    )


def _choose_one_pdf(folder):
    pdfs = _source_pdfs(folder)

    if not pdfs:
        print()
        print(f"No source PDF files were found in:")
        print(folder)
        return None

    print()
    print("PDF files in this folder:")
    for i, pdf in enumerate(pdfs, start=1):
        print(f"  {i}. {pdf.name}")

    print("  0. Cancel")

    while True:
        value = input("Choose a PDF number: ").strip()

        try:
            index = int(value)
        except ValueError:
            print("Please enter one of the numbers shown above.")
            continue

        if index == 0:
            return None

        if 1 <= index <= len(pdfs):
            return pdfs[index - 1]

        print("Invalid number.")


def _choose_pdf_scope(folder):
    scope = _input_choice(
        "Which PDF files do you want to process?",
        [
            ("1", "Choose one PDF from the current script folder"),
            ("2", "Process ALL source PDFs in the current script folder"),
        ],
        default="1",
    )

    if str(scope) == "1":
        pdf = _choose_one_pdf(folder)
        return [pdf] if pdf else []

    pdfs = _source_pdfs(folder)

    if not pdfs:
        print()
        print(f"No source PDF files were found in:")
        print(folder)

    return pdfs


def _ask_orientation():
    value = _input_choice(
        "A4 orientation?",
        [
            ("1", "Portrait (vertical A4)"),
            ("2", "Landscape (horizontal A4)"),
            ("3", "Auto — choose whichever makes the slides largest"),
        ],
        default="3",
    )

    return {
        "1": "portrait",
        "2": "landscape",
        "3": "auto",
    }[str(value)]


def _get_slide_images(slides_dir):
    extensions = {".png", ".jpg", ".jpeg", ".webp"}
    files = [
        p for p in slides_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    ]

    def sort_key(path):
        # Numeric filenames such as slide_0001.png sort naturally anyway,
        # but case-insensitive filename sorting keeps behavior predictable.
        return path.name.lower()

    return sorted(files, key=sort_key)


def extract_pdf_slides(input_pdf, dpi=DEFAULT_DPI, debug=False, output_root=None):
    """
    Extract slide images only.

    Returns:
        list[Path] of extracted slide image files.
    """
    input_pdf = Path(input_pdf)
    stem = input_pdf.stem

    if output_root is None:
        output_root = input_pdf.parent
    else:
        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)

    out_dir = output_root / f"{stem}_slides"
    out_dir.mkdir(exist_ok=True)

    # Remove old slide images from a previous run so stale slides cannot remain.
    for old in out_dir.glob("slide_*.png"):
        try:
            old.unlink()
        except OSError:
            pass

    debug_dir = output_root / f"{stem}_debug"
    if debug:
        debug_dir.mkdir(exist_ok=True)

    doc = fitz.open(input_pdf)
    slide_paths = []
    slide_number = 1

    print()
    print("=" * 72)
    print(f"Extracting: {input_pdf.name}")
    print(f"Pages: {len(doc)}")
    print(f"Rendering at {dpi} DPI")
    print("=" * 72)

    for page_index in range(len(doc)):
        page = doc[page_index]
        image = render_pdf_page(page, dpi=dpi)

        rects, dbg = detect_slide_rectangles(image, debug=debug)

        print(
            f"Page {page_index + 1:03d}: "
            f"detected {len(rects)} slide(s)"
        )

        if debug and dbg is not None:
            dbg_path = debug_dir / f"page_{page_index + 1:03d}_detected.jpg"
            cv2.imwrite(str(dbg_path), dbg)

        for rect in rects:
            slide = crop_slide(image, rect)
            slide_path = out_dir / f"slide_{slide_number:04d}.png"
            save_png(slide_path, slide)
            slide_paths.append(slide_path)
            slide_number += 1

    doc.close()

    if not slide_paths:
        print("No slide rectangles were detected.")
        return []

    print(f"Extracted {len(slide_paths)} slides to:")
    print(out_dir)

    return slide_paths


def _safe_pdf_name(name):
    name = name.strip()

    if not name:
        return None

    if not name.lower().endswith(".pdf"):
        name += ".pdf"

    return name


def _output_path_for_pdf(
    input_pdf,
    per_page,
    orientation,
    custom_name=None,
    output_root=None,
):
    input_pdf = Path(input_pdf)

    if output_root is None:
        output_root = input_pdf.parent
    else:
        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)

    if custom_name:
        return output_root / _safe_pdf_name(custom_name)

    return output_root / (
        f"{input_pdf.stem}_repacked_{per_page}up_{orientation}.pdf"
    )


def _output_path_for_slide_folder(
    slides_dir,
    per_page,
    orientation,
    custom_name=None,
    output_root=None,
):
    slides_dir = Path(slides_dir)

    if output_root is None:
        output_root = slides_dir.parent
    else:
        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)

    if custom_name:
        return output_root / _safe_pdf_name(custom_name)

    stem = slides_dir.name
    if stem.endswith("_slides"):
        stem = stem[:-7]

    return output_root / f"{stem}_repacked_{per_page}up_{orientation}.pdf"



def _choose_output_folder(base_folder):
    """
    Ask whether outputs should stay in the current script folder
    or be placed inside a subfolder of it.
    """
    choice = _input_choice(
        "Where should output files be saved?",
        [
            ("1", "Current script folder"),
            ("2", "A subfolder inside the current script folder"),
        ],
        default="1",
    )

    if str(choice) == "1":
        return base_folder

    print()
    name = input(
        "Subfolder name [Processed]: "
    ).strip()

    if not name:
        name = "Processed"

    # Prevent accidentally creating an absolute/outside path.
    name = Path(name).name

    output_folder = base_folder / name
    output_folder.mkdir(parents=True, exist_ok=True)

    print(f"Output folder: {output_folder}")
    return output_folder


def interactive_extract_only(folder):
    pdfs = _choose_pdf_scope(folder)
    if not pdfs:
        return

    output_root = _choose_output_folder(folder)

    dpi = _input_int(
        "Rendering DPI (higher = sharper but slower)",
        minimum=100,
        maximum=600,
        default=180,
    )

    debug_choice = _input_choice(
        "Save debug images showing detected slide borders?",
        [
            ("1", "No"),
            ("2", "Yes"),
        ],
        default="1",
    )
    debug = str(debug_choice) == "2"

    total = 0
    for pdf in pdfs:
        slides = extract_pdf_slides(
            pdf,
            dpi=dpi,
            debug=debug,
            output_root=output_root,
        )
        total += len(slides)

    print()
    print(f"Finished. Total slides extracted: {total}")


def interactive_extract_and_merge(folder):
    pdfs = _choose_pdf_scope(folder)
    if not pdfs:
        return

    output_root = _choose_output_folder(folder)

    per_page = _input_int(
        "How many slides per A4 output page?",
        minimum=1,
        maximum=12,
        default=4,
    )
    orientation = _ask_orientation()

    gap_mm = _input_float(
        "Space between slides in millimeters",
        minimum=0,
        maximum=50,
        default=4,
    )

    dpi = _input_int(
        "Rendering DPI",
        minimum=100,
        maximum=600,
        default=180,
    )

    debug_choice = _input_choice(
        "Save debug images showing detected slide borders?",
        [
            ("1", "No"),
            ("2", "Yes"),
        ],
        default="1",
    )
    debug = str(debug_choice) == "2"

    custom_name = None
    if len(pdfs) == 1:
        print()
        value = input(
            "Output PDF filename "
            "(press Enter for automatic name): "
        ).strip()
        custom_name = value or None
    else:
        print()
        print(
            "Because you selected ALL PDFs, each output file will receive "
            "an automatic name based on its source PDF."
        )

    for pdf in pdfs:
        slides = extract_pdf_slides(
            pdf,
            dpi=dpi,
            debug=debug,
            output_root=output_root,
        )

        if not slides:
            print(f"Skipping merge for {pdf.name}: no slides detected.")
            continue

        output_pdf = _output_path_for_pdf(
            pdf,
            per_page,
            orientation,
            custom_name=custom_name,
            output_root=output_root,
        )

        repack_to_a4(
            slides,
            output_pdf,
            per_page=per_page,
            orientation=orientation,
            gap_mm=gap_mm,
        )

        print(f"Created: {output_pdf.name}")

    print()
    print("Finished.")


def _available_slide_folders(folder):
    folders = []

    # Search the current folder and any output subfolders beneath it.
    for p in sorted(folder.rglob("*_slides")):
        if p.is_dir() and _get_slide_images(p):
            folders.append(p)

    return folders


def _choose_slide_folder(folder):
    folders = _available_slide_folders(folder)

    if not folders:
        print()
        print("No *_slides folders containing extracted slide images were found.")
        print("Run 'Extract only' or 'Extract + merge' first.")
        return None

    print()
    print("Extracted slide folders:")
    for i, slide_dir in enumerate(folders, start=1):
        count = len(_get_slide_images(slide_dir))
        print(f"  {i}. {slide_dir.name}  ({count} slides)")

    print("  0. Cancel")

    while True:
        value = input("Choose a folder number: ").strip()

        try:
            index = int(value)
        except ValueError:
            print("Please enter one of the numbers shown above.")
            continue

        if index == 0:
            return None

        if 1 <= index <= len(folders):
            return folders[index - 1]

        print("Invalid number.")


def interactive_merge_only(folder):
    output_root = _choose_output_folder(folder)

    scope = _input_choice(
        "Which extracted slide sets do you want to merge?",
        [
            ("1", "Choose one existing *_slides folder"),
            ("2", "Merge ALL existing *_slides folders"),
        ],
        default="1",
    )

    if str(scope) == "1":
        slide_dir = _choose_slide_folder(folder)
        slide_dirs = [slide_dir] if slide_dir else []
    else:
        slide_dirs = _available_slide_folders(folder)

    if not slide_dirs:
        return

    per_page = _input_int(
        "How many slides per A4 output page?",
        minimum=1,
        maximum=12,
        default=4,
    )
    orientation = _ask_orientation()

    gap_mm = _input_float(
        "Space between slides in millimeters",
        minimum=0,
        maximum=50,
        default=4,
    )

    custom_name = None
    if len(slide_dirs) == 1:
        print()
        value = input(
            "Output PDF filename "
            "(press Enter for automatic name): "
        ).strip()
        custom_name = value or None
    else:
        print()
        print(
            "Because you selected ALL slide folders, each output PDF will "
            "receive an automatic filename."
        )

    for slides_dir in slide_dirs:
        slides = _get_slide_images(slides_dir)

        if not slides:
            print(f"Skipping {slides_dir.name}: no slide images found.")
            continue

        output_pdf = _output_path_for_slide_folder(
            slides_dir,
            per_page,
            orientation,
            custom_name=custom_name,
            output_root=output_root,
        )

        repack_to_a4(
            slides,
            output_pdf,
            per_page=per_page,
            orientation=orientation,
            gap_mm=gap_mm,
        )

        print(f"Created: {output_pdf.name}")

    print()
    print("Finished.")


def interactive_main():
    # "Current folder" means the folder containing this Python script.
    # This is more predictable in IDLE than relying on the process working dir.
    folder = Path(__file__).resolve().parent

    print()
    print("=" * 72)
    print("       PDF HANDOUT SLIDE EXTRACTOR / REPACKER — CUSTOM OUTPUT")
    print("=" * 72)
    print()
    print("Working folder:")
    print(folder)

    while True:
        action = _input_choice(
            "What do you want to do?",
            [
                ("1", "Extract slides only"),
                ("2", "Merge/repack slides that were already extracted"),
                ("3", "Extract slides AND create a custom merged PDF"),
                ("4", "Exit"),
            ],
            default="3",
        )

        if str(action) == "1":
            interactive_extract_only(folder)

        elif str(action) == "2":
            interactive_merge_only(folder)

        elif str(action) == "3":
            interactive_extract_and_merge(folder)

        else:
            print()
            print("Goodbye.")
            return

        again = _input_choice(
            "Do you want to perform another operation?",
            [
                ("1", "Yes"),
                ("2", "No / Exit"),
            ],
            default="2",
        )

        if str(again) != "1":
            print()
            print("Done.")
            return


if __name__ == "__main__":
    interactive_main()
