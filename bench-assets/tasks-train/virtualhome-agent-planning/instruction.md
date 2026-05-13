# Logistics Delivery — PDDL Planning (TRAIN variant)

You are the dispatch planner for a small package-delivery fleet. Your job is to
read each PDDL planning problem, generate a *valid* PDDL plan, and write it to
disk.

The planning task family (read PDDL domain + problem, run a planner, write the
resulting action sequence) is identical to the validation task — only the
domain (logistics delivery instead of airport ground movement) and the problem
instances differ. The skill you need is the same: parse PDDL, invoke a sound
planner, emit a syntactically correct action plan.

## Inputs

The manifest at `/app/problem.json` lists every problem you must solve. Each
entry has:

```json
{
  "id": "delivery01",
  "domain": "logistics/domain01.pddl",
  "problem": "logistics/task01.pddl",
  "plan_output": "delivery01.txt"
}
```

For every entry you must:

1. Parse the PDDL domain at `domain` and the PDDL problem at `problem`.
2. Generate a sequential PDDL plan that satisfies the problem's `:goal`.
3. Write the plan to the path given in `plan_output`, one action per line.

A plan line is a parenthesised action call, for example:

```
(drive truck1 warehouse store_b)
(load pkg1 truck1 warehouse)
(unload pkg1 truck1 store_b)
```

## The logistics domain

Each problem uses the STRIPS fragment of PDDL with three object types:
`location`, `package`, `vehicle`. The actions are `drive`, `load`, and
`unload`. A vehicle may move between any two locations (fully connected), may
load a package it is co-located with, and may unload a package it is carrying.
Packages arrive at their goal locations once unloaded.

## Per-problem snapshot

| id         | vehicles           | packages                       | initial layout                                                  | goal                                                             |
|------------|--------------------|--------------------------------|-----------------------------------------------------------------|------------------------------------------------------------------|
| delivery01 | truck1             | pkg1                           | truck1@warehouse, pkg1@warehouse                                | pkg1 at store_b                                                  |
| delivery02 | truck_a, truck_b   | crate_red, crate_blue          | truck_a@depot, truck_b@port, crate_red@depot, crate_blue@port   | crate_red at port and crate_blue at depot                        |
| delivery03 | rover              | parcel_1, parcel_2, parcel_3   | rover@loc_alpha, parcels at alpha/beta/gamma respectively       | parcel_1 at gamma, parcel_2 at alpha, parcel_3 at beta           |

## Constraints on the plan

- The plan must use only action names that the relevant `domainNN.pddl` file
  defines (`drive`, `load`, `unload`).
- All object names (locations, packages, vehicles) must match the PDDL files.
- Each action goes on its own line and is wrapped in exactly one pair of
  parentheses.
- The plan must be *valid* — applying it from the problem's initial state must
  reach the goal. The verifier uses `unified_planning.PlanValidator` to check
  this.
