You're a grid reliability engineer at a regional balancing authority. The operations team has flagged anomalous price spikes at several nodes during last week's day-ahead auction. They believe a single overloaded corridor is the root cause and want you to perform a "capacity upgrade" sensitivity study.

Your task is to run the day-ahead market clearing twice: once for the **baseline** and once for the **upgraded** scenario. In the upgraded scenario, the thermal rating of the transmission corridor from bus 108 to bus 111 is raised by 25% compared to the baseline.

The grid topology is stored in `grid_data.json`, using the MATPOWER array format.

The market model uses DC-OPF with spinning reserve co-optimization, minimizing total generation cost subject to:
1. Nodal power balance (DC approximation)
2. Generator output limits and transmission line thermal limits
3. System-wide spinning reserve requirement with generator-level capacity coupling

Produce a file called `results.json` with the following layout:

```json
{
  "baseline": {
    "objective_cost_usd_hr": 19240.0,
    "nodal_prices": [
      {"node": 101, "price_usd_mwh": 30.5},
      {"node": 102, "price_usd_mwh": 28.1},
      ...
    ],
    "spinning_reserve_price_usd_mwh": 3.0,
    "congested_corridors": [
      {"origin": 108, "destination": 111, "power_flow_mw": 55.0, "thermal_limit_mw": 55.0}
    ]
  },
  "upgraded": {
    "objective_cost_usd_hr": 19187.0,
    "nodal_prices": [
      {"node": 101, "price_usd_mwh": 29.0},
      {"node": 102, "price_usd_mwh": 29.0},
      ...
    ],
    "spinning_reserve_price_usd_mwh": 3.0,
    "congested_corridors": []
  },
  "sensitivity_summary": {
    "savings_usd_hr": 53.0,
    "nodes_with_greatest_price_reduction": [
      {"node": 110, "baseline_price": 38.7, "upgraded_price": 29.0, "change": -9.7},
      {"node": 109, "baseline_price": 37.1, "upgraded_price": 29.0, "change": -8.1},
      {"node": 111, "baseline_price": 36.5, "upgraded_price": 29.0, "change": -7.5},
      {"node": 112, "baseline_price": 35.0, "upgraded_price": 29.0, "change": -6.0}
    ],
    "bottleneck_resolved": true
  }
}
```

Field definitions:

- **baseline** & **upgraded**: market-clearing outputs for each scenario
  - `objective_cost_usd_hr`: total system generation cost ($/hr)
  - `nodal_prices`: locational marginal price at every node
  - `spinning_reserve_price_usd_mwh`: system-wide spinning reserve clearing price
  - `congested_corridors`: lines loaded at ≥ 99% of thermal rating

- **sensitivity_summary**: comparison between scenarios
  - `savings_usd_hr`: baseline cost minus upgraded cost
  - `nodes_with_greatest_price_reduction`: the **four** nodes with the largest price decrease
  - `bottleneck_resolved`: boolean flag — `true` if the upgraded corridor is no longer congested
