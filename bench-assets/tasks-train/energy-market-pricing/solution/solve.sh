#!/bin/bash
set -e

pip3 install --break-system-packages numpy==1.26.4 scipy==1.11.4 cvxpy==1.4.2 -q

python3 << 'EOF'
import json
import numpy as np
import cvxpy as cp

# =============================================================================
# 1. Parse Grid Topology and Define Upgrade Parameters
# =============================================================================
with open('/root/grid_data.json') as fh:
    grid = json.load(fh)

# Upgrade scenario: raise thermal rating of corridor 108->111 by 25%
UPGRADE_ORIGIN = 108
UPGRADE_DEST = 111
UPGRADE_PCT = 25

base_power = grid['baseMVA']
nodes = np.array(grid['bus'])
units = np.array(grid['gen'])
corridors = np.array(grid['branch']).copy()
unit_costs = np.array(grid['gencost'])

res_cap = np.array(grid['reserve_capacity'])
res_req = grid['reserve_requirement']

num_nodes = len(nodes)
num_units = len(units)
num_corridors = len(corridors)

print(f"Grid '{grid.get('name', 'unknown')}': {num_nodes} nodes, {num_units} units, {num_corridors} corridors")
print(f"Upgrade scenario: corridor {UPGRADE_ORIGIN}->{UPGRADE_DEST}, +{UPGRADE_PCT}% thermal rating")

# Map node IDs to contiguous indices
node_lookup = {int(nodes[i, 0]): i for i in range(num_nodes)}

# Identify reference node (type == 3)
ref_idx = next(i for i in range(num_nodes) if nodes[i, 1] == 3)


class MarketClearing:
    """Encapsulates the DC-OPF with spinning reserve co-optimization."""

    def __init__(self, corridor_data, tag=""):
        self.corridor_data = corridor_data
        self.tag = tag

    def execute(self):
        """Solve and return structured results including dual-derived prices."""
        # Build nodal susceptance matrix
        Bmat = np.zeros((num_nodes, num_nodes))
        suscept = []

        for cr in self.corridor_data:
            fi = node_lookup[int(cr[0])]
            ti = node_lookup[int(cr[1])]
            xval = cr[3]
            if xval != 0:
                bval = 1.0 / xval
                Bmat[fi, fi] += bval
                Bmat[ti, ti] += bval
                Bmat[fi, ti] -= bval
                Bmat[ti, fi] -= bval
                suscept.append(bval)
            else:
                suscept.append(0)

        # Optimization variables
        P = cp.Variable(num_units)    # generation dispatch (pu)
        R = cp.Variable(num_units)    # spinning reserve (MW)
        angle = cp.Variable(num_nodes)

        unit_node = [node_lookup[int(u[0])] for u in units]

        # Cost objective
        obj_expr = 0
        for j in range(num_units):
            a2, a1, a0 = unit_costs[j, 4], unit_costs[j, 5], unit_costs[j, 6]
            P_mw = P[j] * base_power
            obj_expr += a2 * cp.square(P_mw) + a1 * P_mw + a0

        cstr = []
        nodal_balance = []  # kept for dual extraction

        # Nodal power balance (duals = nodal prices)
        for i in range(num_nodes):
            gen_at_node = sum(P[j] for j in range(num_units) if unit_node[j] == i)
            load_pu = nodes[i, 2] / base_power
            eq = gen_at_node - load_pu == Bmat[i, :] @ angle
            nodal_balance.append(eq)
            cstr.append(eq)

        # Unit output bounds
        for j in range(num_units):
            cstr.append(P[j] >= units[j, 9] / base_power)
            cstr.append(P[j] <= units[j, 8] / base_power)

        # Reserve constraints
        cstr.append(R >= 0)
        for j in range(num_units):
            cstr.append(R[j] <= res_cap[j])
            cstr.append(P[j] * base_power + R[j] <= units[j, 8])

        # System reserve requirement (dual = reserve clearing price)
        res_constraint = cp.sum(R) >= res_req
        cstr.append(res_constraint)

        # Reference angle
        cstr.append(angle[ref_idx] == 0)

        # Corridor thermal limits
        for k, cr in enumerate(self.corridor_data):
            fi = node_lookup[int(cr[0])]
            ti = node_lookup[int(cr[1])]
            xval = cr[3]
            cap = cr[5]
            if xval != 0 and cap > 0:
                bval = suscept[k]
                pf = bval * (angle[fi] - angle[ti]) * base_power
                cstr.append(pf <= cap)
                cstr.append(pf >= -cap)

        # Solve
        prob = cp.Problem(cp.Minimize(obj_expr), cstr)
        prob.solve(solver=cp.CLARABEL)

        if prob.status != "optimal":
            raise RuntimeError(f"[{self.tag}] Solver status: {prob.status}")

        print(f"[{self.tag}] cost=${prob.value:.2f}/hr  status={prob.status}")

        angle_val = angle.value

        # Extract nodal prices from balance duals
        nodal_prices = []
        for i in range(num_nodes):
            nid = int(nodes[i, 0])
            dv = nodal_balance[i].dual_value
            price = float(dv) * base_power if dv is not None else 0.0
            nodal_prices.append({"node": nid, "price_usd_mwh": round(price, 2)})

        # Reserve clearing price
        res_price = 0.0
        if res_constraint.dual_value is not None:
            res_price = float(res_constraint.dual_value)

        # Identify congested corridors (>= 99% loading)
        congested = []
        for k, cr in enumerate(self.corridor_data):
            fi = node_lookup[int(cr[0])]
            ti = node_lookup[int(cr[1])]
            xval = cr[3]
            cap = cr[5]
            if xval != 0 and cap > 0:
                bval = suscept[k]
                flow_mw = bval * (angle_val[fi] - angle_val[ti]) * base_power
                pct = abs(flow_mw) / cap * 100
                if pct >= 99.0:
                    congested.append({
                        "origin": int(cr[0]),
                        "destination": int(cr[1]),
                        "power_flow_mw": round(float(flow_mw), 2),
                        "thermal_limit_mw": round(float(cap), 2)
                    })

        return {
            "objective_cost_usd_hr": round(float(prob.value), 2),
            "nodal_prices": nodal_prices,
            "spinning_reserve_price_usd_mwh": round(res_price, 2),
            "congested_corridors": congested
        }


# =============================================================================
# 2. Run Baseline
# =============================================================================
baseline_corridors = corridors.copy()
baseline_mc = MarketClearing(baseline_corridors, tag="Baseline")
baseline_out = baseline_mc.execute()

# =============================================================================
# 3. Apply Capacity Upgrade and Run
# =============================================================================
upgraded_corridors = corridors.copy()

applied = False
for k in range(num_corridors):
    o = int(upgraded_corridors[k, 0])
    d = int(upgraded_corridors[k, 1])
    if (o == UPGRADE_ORIGIN and d == UPGRADE_DEST) or \
       (o == UPGRADE_DEST and d == UPGRADE_ORIGIN):
        prev_cap = upgraded_corridors[k, 5]
        upgraded_corridors[k, 5] = prev_cap * (1 + UPGRADE_PCT / 100.0)
        print(f"Upgraded corridor {UPGRADE_ORIGIN}->{UPGRADE_DEST}: "
              f"{prev_cap:.1f} -> {upgraded_corridors[k, 5]:.1f} MW")
        applied = True
        break

if not applied:
    raise ValueError(f"Corridor {UPGRADE_ORIGIN}->{UPGRADE_DEST} not found in grid")

upgraded_mc = MarketClearing(upgraded_corridors, tag="Upgraded")
upgraded_out = upgraded_mc.execute()

# =============================================================================
# 4. Build Sensitivity Summary
# =============================================================================
savings = baseline_out["objective_cost_usd_hr"] - upgraded_out["objective_cost_usd_hr"]

# Compute per-node price changes
base_price_map = {e["node"]: e["price_usd_mwh"] for e in baseline_out["nodal_prices"]}
upg_price_map = {e["node"]: e["price_usd_mwh"] for e in upgraded_out["nodal_prices"]}

price_changes = []
for nid in base_price_map:
    bp = base_price_map[nid]
    up = upg_price_map[nid]
    ch = up - bp
    price_changes.append({
        "node": nid,
        "baseline_price": bp,
        "upgraded_price": up,
        "change": round(ch, 2)
    })

# Top 4 nodes with largest price reduction (most negative change)
ranked = sorted(price_changes, key=lambda x: x["change"])
top4_reduction = ranked[:4]

# Check if bottleneck resolved
target_pair = (UPGRADE_ORIGIN, UPGRADE_DEST)
baseline_congested = set()
for c in baseline_out["congested_corridors"]:
    baseline_congested.add((c["origin"], c["destination"]))
    baseline_congested.add((c["destination"], c["origin"]))

upgraded_congested = set()
for c in upgraded_out["congested_corridors"]:
    upgraded_congested.add((c["origin"], c["destination"]))
    upgraded_congested.add((c["destination"], c["origin"]))

was_congested = target_pair in baseline_congested or \
                (target_pair[1], target_pair[0]) in baseline_congested
still_congested = target_pair in upgraded_congested or \
                  (target_pair[1], target_pair[0]) in upgraded_congested
bottleneck_resolved = was_congested and not still_congested

sensitivity = {
    "savings_usd_hr": round(savings, 2),
    "nodes_with_greatest_price_reduction": top4_reduction,
    "bottleneck_resolved": bottleneck_resolved
}

# =============================================================================
# 5. Write Results
# =============================================================================
output = {
    "baseline": baseline_out,
    "upgraded": upgraded_out,
    "sensitivity_summary": sensitivity
}

with open('/root/results.json', 'w') as fh:
    json.dump(output, fh, indent=2)

print("\n" + "=" * 60)
print("SENSITIVITY SUMMARY")
print("=" * 60)
print(f"Savings: ${savings:.2f}/hr")
print(f"Bottleneck resolved: {bottleneck_resolved}")
print(f"\nTop 4 nodes with largest price reduction:")
for nd in top4_reduction:
    print(f"  Node {nd['node']}: ${nd['baseline_price']:.2f} -> "
          f"${nd['upgraded_price']:.2f} (Δ={nd['change']:.2f})")

print("\nResults written to /root/results.json")
EOF
