
You need to calculate the Sinclair coefficients for Olympic Weightlifting competition results in the file `/root/data/weightlifting_results.xlsx`.
The workbook contains two sheets:
1. "Results" which contains all performance records of athletes,
2. "Sinclair" which is empty for you to work on.
The column definitions are documented in `/root/data/data-readme.md`.

You need to calculate the [Sinclair](https://iwf.sport/weightlifting_/sinclair-coefficient/)
coefficients for each athlete.
Please keep 3 digits precision for all computation.

Step 1: Find which columns are needed to compute the Sinclair coefficient.
Copy these columns to "Sinclair" with the athletes' name.
Keep the order and names of the columns the same in "Sinclair" as in "Results".

Step 2: With the data you have in "Sinclair",
append a new column "TotalKg" after the existing columns,
using Excel formula to compute each athlete's total lifted weight in Kg,

Step 3: With the data you have and added in "Sinclair",
append a new column "Sinclair" after "TotalKg",
using Excel formula to compute each athlete's Sinclair coefficient.
