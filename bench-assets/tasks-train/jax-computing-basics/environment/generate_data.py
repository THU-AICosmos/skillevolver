import os

import jax
import jax.numpy as jnp
import numpy as np

np.random.seed(42)

os.makedirs("data", exist_ok=True)
os.makedirs("reference", exist_ok=True)

# ------------------------
# 1. v.npy for basic tasks (7x4 matrix, different from original 10x5)
# ------------------------
v = np.random.randn(7, 4).astype(np.float32)
np.save("data/v.npy", v)

# ------------------------
# 2. hinge loss data (different from logistic: 15 samples, 6 features)
# ------------------------
N, D = 15, 6
X_hin = np.random.randn(N, D).astype(np.float32)
true_w = np.random.randn(D).astype(np.float32)
logits = X_hin @ true_w
y = np.sign(logits + 0.05 * np.random.randn(N)).astype(np.float32)
np.savez("data/hinge.npz", x=X_hin, y=y, w=true_w)

# ------------------------
# 3. signal data for IIR filter scan (20 timesteps, 5 channels)
# ------------------------
signal = np.random.randn(20, 5).astype(np.float32)
alpha = np.float32(0.8)
beta = np.float32(0.2)
np.savez("data/signal.npz", signal=signal, alpha=alpha, beta=beta)

# ------------------------
# 4. Residual block data (12x8 input, hidden=8 so residual connection works)
# ------------------------
X_res = np.random.randn(12, 8).astype(np.float32)
W1_res = np.random.randn(8, 8).astype(np.float32) * 0.1
b1_res = np.random.randn(8).astype(np.float32) * 0.1
W2_res = np.random.randn(8, 8).astype(np.float32) * 0.1
b2_res = np.random.randn(8).astype(np.float32) * 0.1
np.savez("data/resblock.npz", X=X_res, W1=W1_res, b1=b1_res, W2=W2_res, b2=b2_res)

# ------------------------
# 5. Outer product data (9 pairs of vectors, dim 3 and dim 4)
# ------------------------
A_outer = np.random.randn(9, 3).astype(np.float32)
B_outer = np.random.randn(9, 4).astype(np.float32)
np.savez("data/outer.npz", a=A_outer, b=B_outer)

# =========================================================
# Generate reference outputs using same definitions as oracle
# =========================================================

# reduce_prod: product along axis=0
ref_prod = jnp.prod(v, axis=0)
np.save("reference/reduce_prod.npy", np.array(ref_prod))

# map_tanh
ref_tanh = jnp.tanh(v)
np.save("reference/map_tanh.npy", np.array(ref_tanh))

# grad_hinge
def hinge_loss(w):
    logits = jnp.dot(X_hin, w)
    return jnp.mean(jnp.maximum(0, 1 - y * logits))

ref_grad = jax.grad(hinge_loss)(true_w)
np.save("reference/grad_hinge.npy", np.array(ref_grad))

# scan_filter (IIR)
def iir_step(h, x):
    h_new = alpha * h + beta * x
    return h_new, h_new

h0 = jnp.zeros(5)
_, ref_filter = jax.lax.scan(iir_step, h0, signal)
np.save("reference/scan_filter.npy", np.array(ref_filter))

# jit_residual
def residual_block(x, W1, b1, W2, b2):
    h = jax.nn.relu(jnp.dot(x, W1) + b1)
    return jnp.dot(h, W2) + b2 + x

jres = jax.jit(residual_block)
ref_res = jres(X_res, W1_res, b1_res, W2_res, b2_res)
np.save("reference/jit_residual.npy", np.array(ref_res))

# vmap_outer
ref_outer = jax.vmap(lambda a, b: jnp.outer(a, b))(A_outer, B_outer)
np.save("reference/vmap_outer.npy", np.array(ref_outer))

print("Data and reference outputs generated.")
