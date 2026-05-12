## Task description

In `/app/workspace/dataset/img`, I provide a set of scanned receipt images. Each receipt image contains text such as date, product name, unit price, total amount cost, etc. The text mainly consists of digits and English characters.

Read all image files under the given path, extract only the **date** from each receipt, and write the results into an excel file `/app/workspace/receipt_dates.xlsx`.

The output file should only contain one sheet called "dates". It should have 2 columns:
- `filename`: source filename (e.g., "007.jpg").
- `date`: the extracted date in ISO format (YYYY-MM-DD). If extraction fails, the value is set to null.

The first row of the excel file should be column names. The following rows should be ordered by filename.

No extra columns/rows/sheets should be generated.

## Hint: how to identify dates from each receipt

Look for lines containing keywords like `DATE` or `TARIKH` (Malay for date) followed by a date pattern.

Common date formats found in these receipts:
- DD/MM/YYYY (e.g., 19/10/2018)
- DD-MM-YYYY (e.g., 29-12-2017)
- DD/MM/YY (e.g., 18-11-18)
- MM/DD/YYYY (e.g., 12/28/2017)

When a keyword like DATE or TARIKH is present, prefer the date on that line.

## Pre-installed Libraries

The following libraries are already installed in the environment:

- **Tesseract OCR** (`tesseract-ocr`) - Open-source OCR engine for text extraction from images
- **pytesseract** - Python wrapper for Tesseract OCR
- **Pillow** (`PIL`) - Python imaging library for image preprocessing
