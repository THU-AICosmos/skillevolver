#!/bin/bash
# Oracle solution for xlsx-recover-data training variant
# 15 missing values across 4 sheets with multi-level dependency chains

python3 << 'PYTHON'
import openpyxl

wb = openpyxl.load_workbook("university_enrollment_incomplete.xlsx")
enroll = wb["Enrollment by Department"]
annual_growth = wb["Annual Growth (%)"]
dept_mix = wb["Department Mix (%)"]
trend = wb["Trend Summary"]

# ===== TIER 1: Directly solvable from known data =====

# J3: AY2019 Total = previous year total * (1 + total growth rate)
prev_total = enroll["J2"].value  # AY2018 Total = 7300
total_yoy = annual_growth["J2"].value  # AY2019 Total growth = 4.66
enroll["J3"] = round(prev_total * (1 + total_yoy / 100))  # 7640

# G7: AY2023 Computing = row total minus all other departments
enroll["G7"] = enroll["J7"].value - sum(
    enroll.cell(row=7, column=c).value for c in range(2, 10) if c != 7
)  # 1400

# E5: AY2021 Arts = previous year * (1 + growth rate)
enroll["E5"] = round(enroll["E4"].value * (1 + annual_growth["E4"].value / 100))  # 800

# F4 Trend: Law 5yr Change = AY2024 - AY2019
trend["F4"] = enroll["F8"].value - enroll["F3"].value  # 95

# ===== TIER 2: Requires Tier 1 results =====

# E3: AY2019 Arts = Total - sum of other departments in row 3
enroll["E3"] = enroll["J3"].value - sum(
    enroll.cell(row=3, column=c).value for c in range(2, 10) if c != 5
)  # 790

# J5: AY2021 Total = row sum (now E5 is recovered)
enroll["J5"] = sum(enroll.cell(row=5, column=c).value for c in range(2, 10))  # 8180

# G6 Growth: AY2023 Computing growth = (current - prev) / prev * 100
annual_growth["G6"] = round(
    (enroll["G7"].value - enroll["G6"].value) / enroll["G6"].value * 100, 2
)  # 6.87

# E5 Growth: AY2022 Arts growth
annual_growth["E5"] = round(
    (enroll["E6"].value - enroll["E5"].value) / enroll["E5"].value * 100, 2
)  # 2.5

# B3 Mix: AY2019 Engineering share
dept_mix["B3"] = round(enroll["B3"].value / enroll["J3"].value * 100, 2)  # 16.75

# ===== TIER 3: Requires Tier 2 results =====

# E5 Mix: AY2021 Arts share
dept_mix["E5"] = round(enroll["E5"].value / enroll["J5"].value * 100, 2)  # 9.78

# J4 Growth: AY2021 Total growth
annual_growth["J4"] = round(
    (enroll["J5"].value - enroll["J4"].value) / enroll["J4"].value * 100, 2
)  # 4.54

# E6 Trend: Arts CAGR = ((AY2024/AY2019)^(1/5) - 1) * 100
trend["E6"] = round(
    ((enroll["E8"].value / enroll["E3"].value) ** 0.2 - 1) * 100, 2
)  # 1.71

# E7 Trend: Arts Base Year = AY2019 enrollment
trend["E7"] = enroll["E3"].value  # 790

# E5 Trend: Arts "Avg Enrollment" (bare label, 5-year drop-endpoint mean).
# Sheet title is "5-Year Trend Summary (AY2019-AY2024)" — six data years are
# visible in Enrollment but the "5-Year" period covers the historical window
# AY2019-AY2023; AY2024 is the endpoint used for 5yr-Change/CAGR and is EXCLUDED
# from this Avg. Neighbouring pre-filled cells (B5/C5/D5/F5) all follow this
# drop-endpoint convention; the labeled "Avg Enrollment (AY2020-AY2023)" on
# row 9 is a different, explicitly windowed average.
trend["E5"] = round(
    (enroll["E3"].value + enroll["E4"].value + enroll["E5"].value
     + enroll["E6"].value + enroll["E7"].value) / 5, 1
)  # (790+770+800+820+840)/5 = 804.0

# D9 Trend: Medicine Avg Enrollment (AY2020-AY2023)
# Partial-window mean: 4 of the 5 years spanned by the adjacent "4yr Change
# (AY2020-AY2024)" row at row 8, EXCLUDING the AY2024 endpoint. Window matches
# the change row's start (AY2020) and stops one year before the change row's end.
trend["D9"] = round(
    (enroll["D4"].value + enroll["D5"].value + enroll["D6"].value + enroll["D7"].value) / 4, 1
)  # (960+1010+1060+1110)/4 = 1035.0

wb.save("university_enrollment_recovered.xlsx")
print("Recovered 15 missing values (4 T1 + 5 T2 + 5 T3 + 1 partial-window avg)")
PYTHON
