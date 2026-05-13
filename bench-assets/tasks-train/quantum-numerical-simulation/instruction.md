Simulate a driven-dissipative Dicke model and compute the cavity Wigner function under 3 different decoherence scenarios. Save each result as a CSV file.

The Dicke model describes N identical two-level atoms interacting with a single cavity mode. The Hamiltonian reads:

$$
H = \omega_a J_z + \omega_c a^\dagger a + \lambda (a^\dagger + a)(J_+ + J_-)
$$

Use the following parameter set:

N = 3 (number of two-level atoms)
$\omega_a = 2$ (atomic transition frequency)
$\omega_c = 1.5$ (cavity frequency)
$\lambda = 3 / \sqrt{N}$ (coupling strength)
$\kappa = 0.5$ (cavity photon decay rate)
$n_\text{max} = 12$ (Fock-space truncation)

The Wigner function should be evaluated on a 500 × 500 grid with $x, p \in [-4, 4]$.

The 3 decoherence scenarios are:

1. Local emission & collective dephasing: $\gamma_\downarrow = 0.05$, $\gamma_\text{CD} = 0.2$
2. Local pumping & collective emission: $\gamma_\uparrow = 0.05$, $\gamma_\Downarrow = 0.15$
3. Local emission & local pumping & collective dephasing: $\gamma_\downarrow = 0.05$, $\gamma_\uparrow = 0.08$, $\gamma_\text{CD} = 0.2$

Workflow for each scenario:
1. Construct the total Liouvillian (cavity + atoms + interaction + dissipation)
2. Find the steady-state density matrix
3. Partial trace over the atomic degrees of freedom to obtain the cavity reduced state
4. Evaluate the Wigner function on the specified grid
5. Save the result as a CSV file: wigner_a.csv, wigner_b.csv, wigner_c.csv (for scenarios 1, 2, 3 respectively)

References:
`https://arxiv.org/pdf/1608.06293`
`https://arxiv.org/pdf/1611.03342`
