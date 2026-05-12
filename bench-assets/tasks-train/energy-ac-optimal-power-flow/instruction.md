As a transmission planning engineer at a Regional Transmission Organization, you are preparing a summer peak reliability assessment to verify that the system can operate within thermal and voltage limits under the forecasted peak demand. Using the mathematical formulation in `math-model.md`, solve for a minimum-cost, AC-feasible dispatch and produce a report in `report.json`. The report must follow the structure below with all power values in MW or MVAr, angles in degrees, voltages in per-unit.

```json
{
  "summary": {
    "total_cost_per_hour": 1234567.89,
    "total_load_MW": 3138.00,
    "total_load_MVAr": 700.00,
    "total_generation_MW": 3200.00,
    "total_generation_MVAr": 850.00,
    "total_losses_MW": 62.00,
    "solver_status": "optimal"
  },
  "generators": [
    {
      "id": 1,
      "bus": 1,
      "pg_MW": 245.5,
      "qg_MVAr": 50.0,
      "pmin_MW": 0.0,
      "pmax_MW": 350.0,
      "qmin_MVAr": -100.0,
      "qmax_MVAr": 150.0
    }
  ],
  "buses": [
    {
      "id": 1,
      "vm_pu": 1.02,
      "va_deg": 0.0,
      "vmin_pu": 0.9,
      "vmax_pu": 1.1
    }
  ],
  "most_loaded_branches": [
    {
      "from_bus": 10,
      "to_bus": 20,
      "loading_pct": 95.2,
      "flow_from_MVA": 571.2,
      "flow_to_MVA": 568.1,
      "limit_MVA": 600.0
    }
  ],
  "feasibility_check": {
    "max_p_mismatch_MW": 0.001,
    "max_q_mismatch_MVAr": 0.002,
    "max_voltage_violation_pu": 0.0,
    "max_branch_overload_MVA": 0.0
  }
}
```
