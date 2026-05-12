You are working on a pptx file `/root/input.pptx` for a technical reference document. The file contains an embedded Excel table of weight unit conversion factors, where each value corresponds to the conversion factor from the row unit to the column unit and some cells contain formulas. There is a text box next to the table that provides an updated conversion factor for one unit pair.

You need to:
1. Extract the embedded Excel table and read the contents
2. Read the text box next to the Excel table to get the updated conversion factor
3. Update the Excel table with the updated conversion factor, keep formula cells as they are, do not change them to hardcoded values
4. Save the pptx file with the updated Excel table as `/root/results.pptx` with everything else unchanged
