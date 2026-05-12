Process quality engineers in electronics assembly use the reflow oven handbook alongside production data to verify that solder joint quality standards are met. To complete thermal profile audits, engineers must cross-reference thermocouple measurements, MES production logs, and the handbook specifications. Your task is to perform a thermal profile compliance audit for the reflow soldering process. Consult the handbook for all threshold values and specifications. The files handbook.pdf, mes_log.csv, test_defects.csv and thermocouples.csv are saved under /app/data/.

Task A: For each production run, determine whether the peak reflow temperature meets the handbook requirement. Use thermocouple sensor data to find the minimum peak temperature across all thermocouples for each run. The handbook specifies how much the peak must exceed the solder liquidus temperature. Runs without thermocouple data should be marked as failing.

You are required to generate /app/output/task_a.json. Please follow the following format. Round float values to 2 decimals. Sort arrays by run_id ascending. Use null if necessary.

{
  "non_passing_run_ids": [""],
  "peak_analysis":
  {
    "R0000":
    {
      "thermocouple": "",
      "observed_peak_c": ,
      "handbook_min_peak_c":
    },
  }
}


Task B: Calculate the time above liquidus (TAL) for each production run using thermocouple data and the solder liquidus temperature from MES logs. Refer to the handbook for the TAL measurement method, the liquidus threshold, and the acceptable TAL range.

You are required to generate /app/output/task_b.json. Please follow the following format. Round float values to 2 decimals. Sort arrays by run_id ascending. Use null if necessary.

[
  {
    "run_id": "",
    "thermocouple": "",
    "measured_tal_s": ,
    "handbook_min_tal_s": ,
    "handbook_max_tal_s": ,
    "compliance": "pass" or "fail"
  },
]
