You are working on environmental water quality monitoring data. The dataset consolidates measurements from multiple international monitoring stations that use different measurement systems. This means different labs may report the same analyte in different units. I need your help conducting unit harmonization! Be careful about the data format issues and inconsistent units used.

The input data is `/root/environment/data/water_quality_data.csv` with 50 water quality parameters from different monitoring stations. Some station records may be incomplete and should be discarded. Please see `/root/environment/data/water_quality_feature_descriptions.csv` for understanding the parameters and their target units.

## Problem
The raw data has several data quality problems you need to address:
- incomplete records: some rows have missing values and cannot be harmonized
- scientific notation issue: you should convert `1.23e2` to something like `123.00`
- decimal format: there are many ',' that should be interpreted as '.' (`12,34` is actually `12.34`). Also, there could be different decimal places randomly.
- the key issue -- mixed units: many values are reported in alternative units that need conversion (e.g., mmol/L instead of mg/L for nutrients, mg/L instead of µg/L for heavy metals)

## Your Task
Please conduct the unit harmonization with the following steps:
1. remove station rows with any missing values as they cannot be recovered or harmonized
2. handle scientific notation expressions to normal numeric style
3. values outside the expected measurement ranges are likely using an alternative unit. You need to apply the appropriate conversion factor based on your domain knowledge of water chemistry and environmental monitoring.
4. round all values to 2 decimal places in the format: `X.XX`

## Output

Please save the harmonized data to: `/root/water_quality_harmonized.csv`

Requirements:
- output data should have the same column count as the input data
- numeric values should have 2 decimal places in the format: `X.XX`
- all values should use US EPA standard units and be within expected measurement ranges
- make sure there are no scientific notation, commas, or inconsistent decimals in the output data
