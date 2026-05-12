"""Generate data and reference outputs using numpy only (no jax dependency)."""
import os
import numpy as np

np.random.seed(42)

os.makedirs("data", exist_ok=True)
os.makedirs("reference", exist_ok=True)

# 1. v.npy (7x4)
v = np.random.randn(7, 4).astype(np.float32)
np.save("data/v.npy", v)

# 2. hinge loss data (15 samples, 6 features)
N, D = 15, 6
X_hin = np.random.randn(N, D).astype(np.float32)
true_w = np.random.randn(D).astype(np.float32)
logits = X_hin @ true_w
y = np.sign(logits + 0.05 * np.random.randn(N)).astype(np.float32)
np.savez("data/hinge.npz", x=X_hin, y=y, w=true_w)

# 3. signal data for IIR filter (20 timesteps, 5 channels)
signal = np.random.randn(20, 5).astype(np.float32)
alpha = np.float32(0.8)
beta = np.float32(0.2)
np.savez("data/signal.npz", signal=signal, alpha=alpha, beta=beta)

# 4. Residual block (12x8)
X_res = np.random.randn(12, 8).astype(np.float32)
W1_res = np.random.randn(8, 8).astype(np.float32) * 0.1
b1_res = np.random.randn(8).astype(np.float32) * 0.1
W2_res = np.random.randn(8, 8).astype(np.float32) * 0.1
b2_res = np.random.randn(8).astype(np.float32) * 0.1
np.savez("data/resblock.npz", X=X_res, W1=W1_res, b1=b1_res, W2=W2_res, b2=b2_res)

# 5. Outer product data (9 pairs, dim 3 and 4)
A_outer = np.random.randn(9, 3).astype(np.float32)
B_outer = np.random.randn(9, 4).astype(np.float32)
np.savez("data/outer.npz", a=A_outer, b=B_outer)

# =========================================================
# Generate reference outputs using numpy
# =========================================================

# reduce_prod: product along axis=0
ref_prod = np.prod(v, axis=0)
np.save("reference/reduce_prod.npy", ref_prod)

# map_tanh
ref_tanh = np.tanh(v)
np.save("reference/map_tanh.npy", ref_tanh)

# grad_hinge: numerical gradient for verification
# hinge_loss(w) = mean(max(0, 1 - y * (X @ w)))
# gradient: for each sample, if 1 - y_i * (x_i @ w) > 0, contribute -y_i * x_i / N
margins = 1 - y * (X_hin @ true_w)
mask = (margins > 0).astype(np.float32)
ref_grad = -np.mean((mask * y)[:, None] * X_hin, axis=0)
np.save("reference/grad_hinge.npy", ref_grad)

# scan_filter (IIR): h[t] = alpha * h[t-1] + beta * x[t]
h = np.zeros((20, 5), dtype=np.float32)
h_prev = np.zeros(5, dtype=np.float32)
for t in range(20):
    h[t] = alpha * h_prev + beta * signal[t]
    h_prev = h[t]
np.save("reference/scan_filter.npy", h)

# jit_residual: relu(x @ W1 + b1) @ W2 + b2 + x
hidden = np.maximum(0, X_res @ W1_res + b1_res)
ref_res = hidden @ W2_res + b2_res + X_res
np.save("reference/jit_residual.npy", ref_res)

# vmap_outer: outer product of each pair
ref_outer = np.array([np.outer(A_outer[i], B_outer[i]) for i in range(9)])
np.save("reference/vmap_outer.npy", ref_outer)

print("Data and reference outputs generated (numpy only).")
