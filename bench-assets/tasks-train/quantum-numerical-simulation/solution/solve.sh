#!/bin/bash
set -e

# Driven-dissipative Dicke model: compute cavity Wigner functions for 3
# decoherence scenarios and save to wigner_a.csv, wigner_b.csv, wigner_c.csv.

python3 <<'PYEOF'
import os
from pathlib import Path
import numpy as np
from qutip import (
    destroy, liouvillian, qeye, spost, spre,
    steadystate, super_tensor, tensor, to_super, wigner,
)
from qutip.piqs import Dicke, jspin, num_dicke_states

# ---------- output directory resolution ----------
dest = None
for candidate in [Path(os.getenv("OUTPUT_DIR", "")), Path.cwd(), Path("/root")]:
    if candidate and candidate.exists():
        dest = candidate
        break
if dest is None:
    dest = Path.cwd()
print(f"[solve] Output directory: {dest}")

# ---------- model parameters ----------
NUM_ATOMS = 3
OMEGA_A = 2.0
OMEGA_C = 1.5
KAPPA = 0.5
LAMBDA = 3.0 / np.sqrt(NUM_ATOMS)
N_FOCK = 12
GRID_N = 500
GRID_LIM = 4.0

nds = num_dicke_states(NUM_ATOMS)
jx_op, _, jz_op = jspin(NUM_ATOMS)
h_spin = OMEGA_A * jz_op

cav_annihil = destroy(N_FOCK)
h_cavity = OMEGA_C * cav_annihil.dag() * cav_annihil

# ---------- superoperators ----------
liouv_cavity = liouvillian(h_cavity, [np.sqrt(KAPPA) * cav_annihil])
sup_id_atoms = to_super(qeye(nds))
sup_id_cav = to_super(qeye(N_FOCK))

h_interact = LAMBDA * tensor(cav_annihil + cav_annihil.dag(), jx_op)
liouv_interact = -1j * spre(h_interact) + 1j * spost(h_interact)


def make_atom_liouvillian(
    emission=0, pumping=0, dephasing=0,
    col_emission=0, col_pumping=0, col_dephasing=0,
):
    """Construct the atomic Liouvillian via PIQS."""
    d = Dicke(N=NUM_ATOMS)
    d.hamiltonian = h_spin
    d.emission = emission
    d.pumping = pumping
    d.dephasing = dephasing
    d.collective_emission = col_emission
    d.collective_pumping = col_pumping
    d.collective_dephasing = col_dephasing
    return d.liouvillian()


def assemble_total_liouvillian(atom_liouv):
    """Combine cavity, atom, and interaction Liouvillians."""
    return (
        super_tensor(liouv_cavity, sup_id_atoms)
        + super_tensor(sup_id_cav, atom_liouv)
        + liouv_interact
    )


# ---------- decoherence scenarios ----------
scenario_configs = {
    "a": dict(emission=0.05, col_dephasing=0.2),
    "b": dict(pumping=0.05, col_emission=0.15),
    "c": dict(emission=0.05, pumping=0.08, col_dephasing=0.2),
}

coord_vec = np.linspace(-GRID_LIM, GRID_LIM, GRID_N)

for tag, kwargs in scenario_configs.items():
    print(f"[solve] Computing scenario {tag} ...")
    atom_L = make_atom_liouvillian(**kwargs)
    full_L = assemble_total_liouvillian(atom_L)
    rho_steady = steadystate(full_L, method="direct")
    cavity_dm = rho_steady.ptrace(0)
    W = wigner(cavity_dm, coord_vec, coord_vec)
    out_file = dest / f"wigner_{tag}.csv"
    np.savetxt(out_file, W, delimiter=",")
    print(f"[solve] Saved {out_file}")

print("[solve] Done.")
PYEOF
