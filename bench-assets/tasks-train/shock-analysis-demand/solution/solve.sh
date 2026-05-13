#!/bin/bash

# Oracle solution for export shock analysis task (Armenia)
# This copies the completed answer file to the test file location

# The answer file contains all the completed work with formulas:
# - WEO_Projections populated with IMF WEO data and projection formulas
# - EXPORTS-2023 and IMPORTS-2023 sheets from armstat website
# - Trade_Calc with formulas linking to EXPORTS/IMPORTS and export dependency ratio
# - Impact sheet with all three scenarios and their calculations

cp "/solution/answer - export.xlsx" "test - export.xlsx"
