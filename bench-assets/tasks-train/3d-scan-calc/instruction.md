You need to estimate the coating cost for a sonar-scanned underwater structure. The input (`/root/sonar_scan.stl`) is a binary STL, but the 2-byte "Attribute Byte Count" at the end of each triangle record is being used to store the **Coating Code** of the surface.

You need to:
1. Parse the binary STL and identify the **largest connected component** (by surface area) to filter out sonar noise artifacts.
2. Extract the Coating Code and reference it with `/root/coating_price_list.md` to find the corresponding cost per unit area.
3. Calculate the total coating cost based on the formula `Surface Area * Cost Per Unit Area` and save the result to `/root/coating_estimate.json` in the following format:

```json
{
 "total_coating_cost": 12345.67,
 "coating_code": 37,
 "surface_area": 9876.54
}
```

NOTE: The result will be considered correct if it is within **0.1% accuracy**.
