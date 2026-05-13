"""Numpy-only version of generate_data.py (for hosts without JAX installed).

Produces byte-identical data files and numerically equivalent reference outputs
for the 6 sub-task variant (adds grad_bce; swaps scan_cumsum -> scan_rnn_v;
swaps jit_linear -> jit_mlp).
"""
import os
import numpy as np

np.random.seed(42)

os.makedirs("data", exist_ok=True)
os.makedirs("reference", exist_ok=True)

# 1. u.npy (6x8)
u = np.random.standard_normal((6, 8)).astype(np.float32)
np.save("data/u.npy", u)

# 2. mse.npz (N=18, D=5)
N_mse, D_mse = 18, 5
X_mse = np.random.standard_normal((N_mse, D_mse)).astype(np.float32)
w_mse = np.random.standard_normal(D_mse).astype(np.float32)
noise_mse = (0.15 * np.random.standard_normal(N_mse)).astype(np.float32)
t_mse = (X_mse @ w_mse + noise_mse).astype(np.float32)
np.savez("data/mse.npz", x=X_mse, t=t_mse, w=w_mse)

# 3. bce.npz (N=22, D=4, y in {0,1})
N_bce, D_bce = 22, 4
X_bce = np.random.standard_normal((N_bce, D_bce)).astype(np.float32)
w_bce = (0.5 * np.random.standard_normal(D_bce)).astype(np.float32)
logits_bce = X_bce @ w_bce
probs_bce = 1.0 / (1.0 + np.exp(-logits_bce))
y_bin = (probs_bce > np.median(probs_bce)).astype(np.float32)
np.savez("data/bce.npz", x=X_bce, y_bin=y_bin, w=w_bce)

# 4. seq_rnn.npz (T=12, I=5, H=4) -- keys Ux/Uh/c
T_seq, I_rnn, H_rnn = 12, 5, 4
seq_rnn = np.random.standard_normal((T_seq, I_rnn)).astype(np.float32)
init_rnn = np.zeros(H_rnn, dtype=np.float32)
Ux = (0.3 * np.random.standard_normal((H_rnn, I_rnn))).astype(np.float32)
Uh = (0.3 * np.random.standard_normal((H_rnn, H_rnn))).astype(np.float32)
c = (0.1 * np.random.standard_normal(H_rnn)).astype(np.float32)
np.savez("data/seq_rnn.npz", seq=seq_rnn, init=init_rnn, Ux=Ux, Uh=Uh, c=c)

# 5. mlp.npz (B=9, Din=7, H=12, Dout=3)
B_mlp, Din_mlp, H_mlp, Dout_mlp = 9, 7, 12, 3
X_mlp = np.random.standard_normal((B_mlp, Din_mlp)).astype(np.float32)
W1 = (0.2 * np.random.standard_normal((Din_mlp, H_mlp))).astype(np.float32)
b1 = (0.1 * np.random.standard_normal(H_mlp)).astype(np.float32)
W2 = (0.2 * np.random.standard_normal((H_mlp, Dout_mlp))).astype(np.float32)
b2 = (0.1 * np.random.standard_normal(Dout_mlp)).astype(np.float32)
np.savez("data/mlp.npz", X=X_mlp, W1=W1, b1=b1, W2=W2, b2=b2)

# ============================================================
# Reference outputs (numpy formulas matching the JAX oracle)
# ============================================================

# basic_sum
ref_sum = np.sum(u, axis=0)
np.save("reference/basic_sum.npy", ref_sum.astype(np.float32))

# map_exp
ref_exp = np.exp(u)
np.save("reference/map_exp.npy", ref_exp.astype(np.float32))

# grad_mse: dL/dw = (2/N) * X^T (X w - t) for L = mean((X w - t)^2)
resid = X_mse @ w_mse - t_mse
ref_grad_mse = (2.0 / N_mse) * (X_mse.T @ resid)
np.save("reference/grad_mse.npy", ref_grad_mse.astype(np.float32))

# grad_bce: for L = -mean(y log p + (1-y) log(1-p)) with p = sigmoid(Xw),
# dL/dw = (1/N) * X^T (p - y). (eps term below threshold of numerical effect.)
logits = X_bce @ w_bce
probs = 1.0 / (1.0 + np.exp(-logits))
ref_grad_bce = (1.0 / N_bce) * (X_bce.T @ (probs - y_bin))
np.save("reference/grad_bce.npy", ref_grad_bce.astype(np.float32))

# scan_rnn_v: iterate h_t = tanh(Ux @ x_t + Uh @ h + c), stack.
h = init_rnn.copy()
hs = []
for t in range(T_seq):
    h = np.tanh(Ux @ seq_rnn[t] + Uh @ h + c)
    hs.append(h)
ref_rnn = np.stack(hs).astype(np.float32)
np.save("reference/scan_rnn_v.npy", ref_rnn)

# jit_mlp: relu(X @ W1 + b1) @ W2 + b2
h = np.maximum(0.0, X_mlp @ W1 + b1)
ref_mlp = (h @ W2 + b2).astype(np.float32)
np.save("reference/jit_mlp.npy", ref_mlp)

print("Data and reference outputs generated (numpy only, 6 sub-tasks).")
