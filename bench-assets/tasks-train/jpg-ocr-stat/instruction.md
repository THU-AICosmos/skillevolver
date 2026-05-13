## Task description

The folder `/app/workspace/dataset/img` holds a batch of scanned receipt JPEGs.
Each receipt shows (among other things) a **transaction date** and a **total
monetary amount**. For this exercise you must OCR every image and pull out
*both* fields per receipt, then write the results into an Excel workbook at
`/app/workspace/receipts_summary.xlsx`.

The workbook must contain exactly one sheet named **`summary`** with these
three columns (header row is row 1):

- `filename` — the source filename, e.g. `007.jpg`.
- `receipt_date` — the extracted date in ISO format (`YYYY-MM-DD`). If you
  cannot parse a date for a given receipt, leave the cell blank (null).
- `receipt_total` — the monetary value as a string with exactly two decimal
  places (e.g. `"47.70"`). If you cannot extract a total, leave the cell
  blank (null).

Data rows must be sorted alphabetically by `filename`. The workbook must
contain no extra sheets, no extra columns, and no extra rows. The verifier
compares the workbook cell-by-cell against a fixed oracle, so `null` vs an
empty string, or an extra trailing row, will fail the test.

## Hint: how to identify the transaction date

Receipts typically print the date next to a keyword. Common formats:

- `DATE: 19/10/2018`
- `TARIKH: 29-12-2017` (Malay for "date")
- `Date  18-11-18`
- `12/28/2017`

Common formats you will encounter:

- DD/MM/YYYY (e.g. `19/10/2018`)
- DD-MM-YYYY (e.g. `29-12-2017`)
- DD/MM/YY  (e.g. `18-11-18`)
- MM/DD/YYYY (e.g. `12/28/2017`)

When a keyword like `DATE` or `TARIKH` is present, prefer the date on that
line over any other date you might find. Normalize every parsed date to
`YYYY-MM-DD` before writing it out.

## Hint: how to identify the total amount

Scan the OCR text for lines containing these keywords (most specific first):

- `GRAND TOTAL`
- `TOTAL RM`, `TOTAL: RM`
- `TOTAL AMOUNT`
- `TOTAL`, `AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`,
  `NETT TOTAL`, `NET TOTAL`

If the matching line has no number on it, fall back to the last number on
the following line.

Skip lines containing any of these words to avoid picking up sub-totals or
other intermediate values:

- `SUBTOTAL`, `SUB TOTAL`
- `TAX`, `GST`, `SST`
- `DISCOUNT`
- `CHANGE`
- `CASH TENDERED`

The numeric value can include a thousands separator, e.g. `1,234.56`. Strip
commas before formatting, and always print exactly two decimals.

## Pre-installed Libraries

- **Tesseract OCR** (`tesseract-ocr`)
- **pytesseract**
- **Pillow** (`PIL`)
- **openpyxl**
