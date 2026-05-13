In macroeconomics, understanding how different sectors of the economy co-move over the business cycle is a fundamental question. This task involves applying standard detrending techniques to analyze the cyclical relationship between government spending and exports.

Goal: Calculate the Pearson correlation coefficient between the detrended real government spending and the detrended real exports for the years 1965 to 2019 (inclusive).

The following data files are provided in `/root/`:
- `government_spending_annual.csv` — Annual total government spending (nominal, billions of dollars), with columns: Year, Total_Government_Spending, Federal, State_Local
- `exports_annual.csv` — Annual total exports of goods and services (nominal, billions of dollars), with columns: Year, Total_Exports, Goods, Services
- `ppi_index.xlsx` — Producer Price Index (for deflation), with columns: Year, PPI

Requirements:
1. Extract the total government spending (column `Total_Government_Spending`) and total exports (column `Total_Exports`) from the CSV files.
2. Convert to real values by deflating the nominal series using the PPI.
3. Apply the Hodrick-Prescott filter to extract the cyclical component:
   - Use the natural logarithm of the real series before filtering
   - Use $\lambda$ = 100 (the standard smoothing parameter for annual data)
4. Compute the Pearson correlation between the two cyclical components.
5. Write the result to `/root/result.txt`:
   - Output only the correlation coefficient as a single number
   - Round to 5 decimal places

Example Output:

If the correlation is 0.72345678, your `result.txt` should contain:
```
0.72346
```
