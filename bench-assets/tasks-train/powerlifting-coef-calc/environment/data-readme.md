# Olympic Weightlifting Results Data README

## Column Descriptions

### Athlete
Mandatory. The name of the athlete in UTF-8 encoding.

### Gender
Mandatory. The gender category in which the athlete competed: `M` for male or `F` for female.

### Age
Optional. The age of the athlete at the time of competition.

### Country
Optional. The three-letter country code of the athlete's nationality (e.g., `GEO`, `CHN`, `USA`).

### BodyweightKg
Mandatory. The recorded bodyweight of the athlete at weigh-in, in kilograms to two decimal places.

### WeightClass
Mandatory. The weight class in which the athlete competed. For the heaviest class, shown as `+109` (men) or `+87` (women).

### BestSnatchKg
Mandatory. The best successful snatch attempt in kilograms.

### BestCleanJerkKg
Mandatory. The best successful clean & jerk attempt in kilograms.

### Competition
Mandatory. The name of the competition where the results were recorded.

## Sinclair Coefficient

The Sinclair coefficient is used to compare lifters across different weight classes. It adjusts the total lifted weight based on bodyweight using a mathematical formula.

The Sinclair Total is calculated as:
- If bodyweight >= threshold: `Sinclair = Total`
- If bodyweight < threshold: `Sinclair = Total * 10^(A * (log10(bodyweight / threshold))^2)`

Where:
- `Total = BestSnatchKg + BestCleanJerkKg`
- For males: `A = 0.751945030`, threshold `b = 200.0`
- For females: `A = 0.783497476`, threshold `b = 175.0`

The coefficient should be rounded to 3 decimal places.

Reference: [IWF Sinclair Coefficients](https://iwf.sport/weightlifting_/sinclair-coefficient/)
