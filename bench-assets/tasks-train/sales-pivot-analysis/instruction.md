read through the enrollment data in `/root/enrollment.pdf` and performance data in `/root/performance.xlsx` and create a new report called `/root/education_report.xlsx`

the new Excel file should contain four new pivot tables and five different sheets:

1. "Enrollment by Province"
This sheet contains a pivot table with the following structure:
Rows: PROVINCE
Values: Sum of ENROLLMENT_2024

2. "Teachers by Province"
This sheet contains a pivot table with the following structure:
Rows: PROVINCE
Values: Sum of TEACHERS

3. "Schools by Province"
This sheet contains a pivot table with the following structure:
Rows: PROVINCE
Values: Count (number of schools)

4. "Province Funding Tier"
This sheet contains a pivot table with the following structure:
Rows: PROVINCE
Columns: Tier. Use the terms "T1", "T2", "T3" and "T4" as the tiers based on FUNDING ranges across all schools.
Values: Sum of TEACHERS

5. "SourceData"
This sheet contains a regular table with the original data
enriched with the following columns:

- Tier - Use the terms "T1", "T2", "T3" and "T4" as the Tiers and base them on FUNDING quartile range
- Budget - TEACHERS × FUNDING

Save the final results in `/root/education_report.xlsx`
