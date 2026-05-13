This task is to estimate an export revenue shock to a small open economy (Armenia) using the macro accounting framework (supply side). The export revenue boost will last 6 years beginning from 2027, which is worth 4.2 billion USD. You are going to collect the relevant data from country authority website and IMF WEO databases, populate data in test file, and test several scenarios in excel. You should ONLY use excel for this task (no python, no hardcoded numbers for the cells that needs calculation). Keep all the formulas in the test file you did.

STEP 1: data collection
- Go to IMF WEO database and populate data into the relevant rows of the sheet "WEO_Projections". Assume the 2027 real GDP growth rate stays unchanged until 2039. Calculate the rest of the columns left in this sheet by extending the GDP deflator using the average deflator growth rate (recent 4 years) as a fixed anchor.
- Get the latest merchandise trade data on armstat website. Copy both EXPORTS and IMPORTS sheets (35 sectors) into the test file, keeping the original sheet name unchanged. Link the relevant data from those two sheets to sheet "Trade_Calc" (Column B-D). Fill Column B-F, and calculate the estimated export dependency ratio in cell C43.

STEP 2:
- On sheet "Impact", link the relevant data from "WEO_Projections" for Column B and C. Fill the assumptions (cell D13 - D16).
  - You should always use 387.5 as the AMD/USD exchange rate.
  - For small open economy, assume 0.7 for supply multiplier.
  - Project allocation is bell shape.
- Fill the rest of the table. (HINT: use GDP deflator as export price deflator).

STEP 3:
- Replicate the first table's structure and build 2 other scenarios below.
- For Scenario 2, assume the supply multiplier is 0.9.
- For Scenario 3, assume the export dependency ratio is 0.4.

Output answers in `test - export.xlsx`.
