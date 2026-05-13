#!/bin/bash

# Oracle solution for shock-analysis-supply training variant (Armenia).
# Copies the completed answer file (structurally aligned with the Georgia
# validation task) to the expected output path.
#
# The answer file contains:
# - PWT with Penn World Table real GDP (rgdpna) and capital stock (rnna) data for Armenia
# - WEO_Data with real GDP level + growth rate (2000..2027 hardcoded, 2028..2043 extended via formula)
# - CFC data with CFC-based depreciation rate calculations
# - Production sheet:
#   - HP filter optimization (lambda=100) on rows 6..27, LnZ_HP in column L,
#     objective in P5 (SUMXMY2 + 100 * SUMSQ)
#   - Cobb-Douglas production function (alpha=0.35)
#   - 8-year CFC depreciation average in B3
#   - Lower table rows 36..75 with K/Y anchor via AVERAGE(D$49:D$57) (9 yrs 2015-2023)
#   - TREND formula extending LnZ to 2041
#   - Capital accumulation with 8-year investment shock starting 2026 (~$6.5B total)
# - Investment sheet with deflated investment schedule (8 rows)

cp "/solution/answer-output.xlsx" "analysis-output.xlsx"
