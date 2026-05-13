"""
Test cases for Grid Capacity Upgrade Sensitivity Study task.

Validates the agent's solution using:
1. Schema validation (report structure is correct)
2. Feasibility verification (internal consistency of reported values)
3. Optimality verification (costs match optimal costs)

Since DC-OPF with reserves could have multiple co-optimal solutions, we verify:
- The solution is FEASIBLE (satisfies physical constraints)
- The solution is OPTIMAL (costs within tolerance of optimal)

We do NOT compare individual nodal price values or congested corridor sets, as these
may differ between equally-valid optimal solutions.
"""
import json
import os

import cvxpy as cp
import numpy as np
import pytest

OUTPUT_FILE = "/root/results.json"
GRID_FILE = "/root/grid_data.json"

# Scenario: increase thermal rating of corridor 108->111 by 25%
TARGET_ORIGIN = 108
TARGET_DESTINATION = 111
UPGRADE_PERCENT = 25

# Tolerances
TOL_COST = 10.0        # Cost tolerance ($/hr)
TOL_PRICE = 1.0        # Price tolerance ($/MWh)
OPTIMALITY_GAP = 1e-4  # 0.01% allowed gap


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def report():
    """Load the agent's results.json."""
    assert os.path.exists(OUTPUT_FILE), f"Output file {OUTPUT_FILE} does not exist"
    with open(OUTPUT_FILE, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def grid():
    """Load the grid data."""
    with open(GRID_FILE, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def reference_costs(grid):
    """
    Compute optimal costs for baseline and upgraded using cvxpy.
    Only returns cost values — dispatch and prices may vary across optimal solutions.
    """
    nodes = np.array(grid["bus"])
    units = np.array(grid["gen"])
    corridors = np.array(grid["branch"])
    unit_costs = np.array(grid["gencost"])
    base_power = grid["baseMVA"]
    res_cap = np.array(grid["reserve_capacity"])
    res_req = grid["reserve_requirement"]

    num_nodes = len(nodes)
    num_units = len(units)
    num_corridors = len(corridors)

    node_lookup = {int(nodes[i, 0]): i for i in range(num_nodes)}
    ref_node = next(i for i in range(num_nodes) if nodes[i, 1] == 3)

    def run_market_clearing(corridor_data):
        """Run DC-OPF and return optimal cost."""
        Bmat = np.zeros((num_nodes, num_nodes))
        suscept_list = []

        for cr in corridor_data:
            fi = node_lookup[int(cr[0])]
            ti = node_lookup[int(cr[1])]
            xval = cr[3]
            if xval != 0:
                bval = 1.0 / xval
                Bmat[fi, fi] += bval
                Bmat[ti, ti] += bval
                Bmat[fi, ti] -= bval
                Bmat[ti, fi] -= bval
                suscept_list.append(bval)
            else:
                suscept_list.append(0)

        P = cp.Variable(num_units)
        R = cp.Variable(num_units)
        angle = cp.Variable(num_nodes)
        unit_node = [node_lookup[int(u[0])] for u in units]

        obj = 0
        for j in range(num_units):
            a2, a1, a0 = unit_costs[j, 4], unit_costs[j, 5], unit_costs[j, 6]
            P_mw = P[j] * base_power
            obj += a2 * cp.square(P_mw) + a1 * P_mw + a0

        cstr = []

        for i in range(num_nodes):
            gen_sum = sum(P[j] for j in range(num_units) if unit_node[j] == i)
            demand = nodes[i, 2] / base_power
            cstr.append(gen_sum - demand == Bmat[i, :] @ angle)

        for j in range(num_units):
            cstr.append(P[j] >= units[j, 9] / base_power)
            cstr.append(P[j] <= units[j, 8] / base_power)

        cstr.append(R >= 0)
        for j in range(num_units):
            cstr.append(R[j] <= res_cap[j])
            cstr.append(P[j] * base_power + R[j] <= units[j, 8])
        cstr.append(cp.sum(R) >= res_req)
        cstr.append(angle[ref_node] == 0)

        for k, cr in enumerate(corridor_data):
            fi = node_lookup[int(cr[0])]
            ti = node_lookup[int(cr[1])]
            xval = cr[3]
            cap = cr[5]
            if xval != 0 and cap > 0:
                bval = suscept_list[k]
                pf = bval * (angle[fi] - angle[ti]) * base_power
                cstr.append(pf <= cap)
                cstr.append(pf >= -cap)

        prob = cp.Problem(cp.Minimize(obj), cstr)
        prob.solve(solver=cp.CLARABEL)

        assert prob.status == "optimal", f"Solver failed: {prob.status}"
        return prob.value

    # Baseline
    baseline_cost = run_market_clearing(corridors.copy())

    # Upgraded scenario
    upgraded_corridors = corridors.copy()
    for k in range(num_corridors):
        cr_origin = int(upgraded_corridors[k, 0])
        cr_dest = int(upgraded_corridors[k, 1])
        if (cr_origin == TARGET_ORIGIN and cr_dest == TARGET_DESTINATION) or \
           (cr_origin == TARGET_DESTINATION and cr_dest == TARGET_ORIGIN):
            upgraded_corridors[k, 5] *= (1 + UPGRADE_PERCENT / 100.0)
            break

    upgraded_cost = run_market_clearing(upgraded_corridors)

    return {"baseline": baseline_cost, "upgraded": upgraded_cost}


# =============================================================================
# Schema Validation
# =============================================================================
class TestSchema:
    """Verify report has correct structure and all required fields."""

    def test_report_structure(self, report, grid):
        """Validate complete report structure."""
        num_nodes = len(grid["bus"])

        # Top-level fields
        assert "baseline" in report, "Missing baseline"
        assert "upgraded" in report, "Missing upgraded"
        assert "sensitivity_summary" in report, "Missing sensitivity_summary"

        # Scenario result structure
        scenario_fields = [
            "objective_cost_usd_hr",
            "nodal_prices",
            "spinning_reserve_price_usd_mwh",
            "congested_corridors"
        ]
        for case_name in ["baseline", "upgraded"]:
            for field in scenario_fields:
                assert field in report[case_name], f"{case_name} missing {field}"

            # Nodal prices structure
            prices = report[case_name]["nodal_prices"]
            assert isinstance(prices, list), f"{case_name} nodal_prices should be a list"
            assert len(prices) == num_nodes, \
                f"{case_name} nodal_prices should have {num_nodes} entries"
            for entry in prices:
                assert "node" in entry, "price entry missing 'node'"
                assert "price_usd_mwh" in entry, "price entry missing 'price_usd_mwh'"

            # Congested corridors structure
            assert isinstance(report[case_name]["congested_corridors"], list)
            for corridor in report[case_name]["congested_corridors"]:
                assert "origin" in corridor and "destination" in corridor, \
                    "congested corridor missing origin/destination"

        # Sensitivity summary structure
        summary_fields = [
            "savings_usd_hr",
            "nodes_with_greatest_price_reduction",
            "bottleneck_resolved"
        ]
        for field in summary_fields:
            assert field in report["sensitivity_summary"], \
                f"sensitivity_summary missing {field}"

        # Top 4 nodes structure
        top4 = report["sensitivity_summary"]["nodes_with_greatest_price_reduction"]
        assert isinstance(top4, list), "nodes_with_greatest_price_reduction should be a list"
        assert len(top4) == 4, "nodes_with_greatest_price_reduction should have 4 entries"
        for entry in top4:
            for field in ["node", "baseline_price", "upgraded_price", "change"]:
                assert field in entry, f"top4 entry missing {field}"

        # bottleneck_resolved is boolean
        assert isinstance(report["sensitivity_summary"]["bottleneck_resolved"], bool)


# =============================================================================
# Feasibility Tests
# =============================================================================
class TestFeasibility:
    """Verify solutions are internally consistent."""

    def test_internal_consistency(self, report):
        """Reported values must be internally consistent."""
        baseline_cost = report["baseline"]["objective_cost_usd_hr"]
        upgraded_cost = report["upgraded"]["objective_cost_usd_hr"]

        # Savings = baseline - upgraded
        reported_savings = report["sensitivity_summary"]["savings_usd_hr"]
        computed_savings = baseline_cost - upgraded_cost
        assert reported_savings == pytest.approx(computed_savings, abs=TOL_COST), \
            f"Savings {reported_savings} != computed {computed_savings}"

        # Change values in nodes_with_greatest_price_reduction should be correct
        for entry in report["sensitivity_summary"]["nodes_with_greatest_price_reduction"]:
            computed_change = entry["upgraded_price"] - entry["baseline_price"]
            assert entry["change"] == pytest.approx(computed_change, abs=TOL_PRICE), \
                f"Node {entry['node']}: change {entry['change']} != computed {computed_change}"


# =============================================================================
# Optimality Tests
# =============================================================================
class TestOptimality:
    """Verify solutions are optimal and economically sensible."""

    def test_costs_near_optimal(self, report, reference_costs):
        """Both scenario costs should be close to optimal."""
        for case_name, key in [("baseline", "baseline"), ("upgraded", "upgraded")]:
            actual = report[case_name]["objective_cost_usd_hr"]
            optimal = reference_costs[key]

            tol = max(abs(optimal) * OPTIMALITY_GAP, 10.0)
            assert actual <= optimal + tol, \
                f"{case_name} cost {actual} exceeds optimal {optimal} by more than {OPTIMALITY_GAP:.4%} (tol={tol})"
            assert actual >= optimal - tol, \
                f"{case_name} cost {actual} is lower than optimal {optimal} beyond {OPTIMALITY_GAP:.4%} (tol={tol})"

    def test_savings_non_negative(self, report):
        """Relaxing a constraint should not increase cost."""
        savings = report["sensitivity_summary"]["savings_usd_hr"]
        assert savings >= -TOL_COST, \
            f"Cost increased by {-savings} when upgrading corridor (should decrease or stay same)"
