"""
Tests for the driven-dissipative Dicke model Wigner function task.

Validates three Wigner CSV outputs:
- file presence and grid shape
- data quality (real, finite values)
- distinct behaviour across the three decoherence scenarios
- phase-space normalisation against the oracle run
- full numerical agreement with the oracle reference
"""

import os
from pathlib import Path

import numpy as np
import pytest
from qutip import (
    destroy,
    liouvillian,
    qeye,
    spost,
    spre,
    steadystate,
    super_tensor,
    tensor,
    to_super,
    wigner,
)
from qutip.piqs import Dicke, jspin, num_dicke_states

# Candidate directories where agents commonly write outputs.
SEARCH_DIRS = []
if os.getenv("OUTPUT_DIR"):
    SEARCH_DIRS.append(Path(os.getenv("OUTPUT_DIR")))
SEARCH_DIRS.extend(
    [
        Path.cwd(),
        Path("/root"),
        Path("/app"),
    ]
)

CASE_LABELS = ["a", "b", "c"]
GRID_EXTENT = 8  # total span: from -4 to 4
GRID_PTS = 500


def _find_csv(label: str) -> Path | None:
    """Return the path to wigner_<label>.csv if found in known search locations."""
    fname = f"wigner_{label}.csv"
    for base in SEARCH_DIRS:
        if not base:
            continue
        candidate = base / fname
        if candidate.exists():
            return candidate
    return None


def _build_reference_wigners():
    """Run the reference simulation to produce expected Wigner arrays."""
    # Atom parameters
    num_atoms = 3
    nds = num_dicke_states(num_atoms)
    jx_op, _, jz_op = jspin(num_atoms)
    omega_a = 2.0
    h_atoms = omega_a * jz_op

    # Cavity parameters
    n_fock = 12
    omega_c = 1.5
    kappa = 0.5
    lam = 3.0 / np.sqrt(num_atoms)
    a_op = destroy(n_fock)

    # Cavity Liouvillian
    h_cav = omega_c * a_op.dag() * a_op
    liouv_cav = liouvillian(h_cav, [np.sqrt(kappa) * a_op])

    # Identity superoperators
    id_atoms = to_super(qeye(nds))
    id_cav = to_super(qeye(n_fock))

    # Interaction Liouvillian
    h_coupling = lam * tensor(a_op + a_op.dag(), jx_op)
    liouv_coupling = -1j * spre(h_coupling) + 1j * spost(h_coupling)

    # Build atom Liouvillians for each scenario
    def atom_liouv(emission=0, pumping=0, dephasing=0,
                   col_emission=0, col_pumping=0, col_dephasing=0):
        sys = Dicke(N=num_atoms)
        sys.hamiltonian = h_atoms
        sys.emission = emission
        sys.pumping = pumping
        sys.dephasing = dephasing
        sys.collective_emission = col_emission
        sys.collective_pumping = col_pumping
        sys.collective_dephasing = col_dephasing
        return sys.liouvillian()

    scenarios = [
        atom_liouv(emission=0.05, col_dephasing=0.2),
        atom_liouv(pumping=0.05, col_emission=0.15),
        atom_liouv(emission=0.05, pumping=0.08, col_dephasing=0.2),
    ]

    def full_liouvillian(liouv_atom):
        return (super_tensor(liouv_cav, id_atoms)
                + super_tensor(id_cav, liouv_atom)
                + liouv_coupling)

    coord = np.linspace(-4, 4, GRID_PTS)
    results = []
    for liouv_atom in scenarios:
        liouv_full = full_liouvillian(liouv_atom)
        rho_ss = steadystate(liouv_full, method="direct")
        cav_dm = rho_ss.ptrace(0)
        results.append(wigner(cav_dm, coord, coord))

    return results


@pytest.fixture(scope="session")
def csv_paths():
    """Collect paths to all three CSV files."""
    paths = []
    for label in CASE_LABELS:
        path = _find_csv(label)
        if path is None:
            searched = ", ".join(str(p) for p in SEARCH_DIRS)
            pytest.fail(f"Missing CSV for scenario '{label}'. Searched: {searched}")
        paths.append(path)
    return paths


@pytest.fixture(scope="session")
def loaded_arrays(csv_paths):
    """Load CSV data into numpy arrays."""
    return [np.loadtxt(p, delimiter=",") for p in csv_paths]


@pytest.fixture(scope="session")
def reference_wigners():
    """Generate reference Wigner arrays using oracle parameters."""
    return _build_reference_wigners()


def test_all_files_present(csv_paths):
    """Ensure all three Wigner CSV outputs exist."""
    assert len(csv_paths) == 3, "Expected three CSV output files"
    for path in csv_paths:
        assert path.exists(), f"CSV not found at {path}"


def test_grid_shape(loaded_arrays):
    """Verify each CSV encodes a 500x500 Wigner grid."""
    for idx, arr in enumerate(loaded_arrays):
        assert arr.shape == (GRID_PTS, GRID_PTS), (
            f"Scenario {CASE_LABELS[idx]}: shape {arr.shape}, expected ({GRID_PTS}, {GRID_PTS})"
        )


def test_finite_real_values(loaded_arrays):
    """Ensure outputs are real and finite (no NaN/inf)."""
    for idx, arr in enumerate(loaded_arrays):
        assert np.isrealobj(arr), f"Scenario {CASE_LABELS[idx]} has non-real values"
        assert np.isfinite(arr).all(), f"Scenario {CASE_LABELS[idx]} has NaN or inf"


def test_normalisation(loaded_arrays):
    """Check that each Wigner function integrates to 1 within tolerance."""
    tol = 0.02
    cell_area = (GRID_EXTENT / (GRID_PTS - 1)) ** 2
    errors = []
    for idx, arr in enumerate(loaded_arrays):
        total = float(arr.sum() * cell_area)
        if not np.isclose(total, 1.0, rtol=0, atol=tol):
            errors.append(
                f"Scenario {CASE_LABELS[idx]}: integral={total:.6f} (|diff|={abs(total - 1):.6f})"
            )
    assert not errors, "Wigner normalisation failures:\n" + "\n".join(errors)


def test_scenarios_are_distinct(loaded_arrays):
    """Verify the three cases are not copies of one another."""
    for i in range(len(loaded_arrays)):
        for j in range(i + 1, len(loaded_arrays)):
            delta = np.max(np.abs(loaded_arrays[i] - loaded_arrays[j]))
            assert delta > 1e-5, (
                f"Scenarios {CASE_LABELS[i]} and {CASE_LABELS[j]} appear identical"
            )


def test_diagonal_trace_matches_reference(loaded_arrays, reference_wigners):
    """Check that each CSV's diagonal sum matches the oracle."""
    for idx, (actual, expected) in enumerate(zip(loaded_arrays, reference_wigners)):
        tr_actual = float(np.trace(actual))
        tr_expected = float(np.trace(expected))
        assert np.isclose(tr_actual, tr_expected, rtol=1e-3, atol=1e-4), (
            f"Diagonal trace mismatch for scenario {CASE_LABELS[idx]}"
        )


def test_wigner_numerical_agreement(loaded_arrays, reference_wigners):
    """Confirm each CSV matches the oracle Wigner function within ~1% tolerance."""
    assert len(loaded_arrays) == len(reference_wigners) == 3
    for idx, (actual, expected) in enumerate(zip(loaded_arrays, reference_wigners)):
        assert np.allclose(actual, expected, rtol=1e-2, atol=1e-12), (
            f"Wigner data mismatch for scenario {CASE_LABELS[idx]}"
        )
