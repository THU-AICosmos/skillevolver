"""Generate input data and reference outputs for the train variant of jax-computing-basics.

Six sub-tasks (one per JAX verb family, shapes deliberately differ from validation):
  * reduce -> basic_sum   (jnp.sum along axis=0 of a 2D matrix)
  * vmap   -> map_exp     (elementwise exp via vmap-of-vmap)
  * grad   -> grad_mse    (gradient of MSE loss on continuous targets)
  * grad   -> grad_bce    (gradient of binary cross-entropy/logistic loss with
                           sigmoid, labels in {0,1}; bridges to val's grad_logistic)
  * scan   -> scan_rnn_v  (RNN forward pass with tanh cell using jax.lax.scan;
                           weight names are Ux/Uh/c — deliberately different from val's
                           Wx/Wh/b to force schema-inspect-first distillation)
  * jit    -> jit_mlp     (JIT-compiled 2-layer MLP with ReLU; same key layout as val)
"""
import os

import jax
import jax.numpy as jnp
import numpy as np

np.random.seed(42)

os.makedirs("data", exist_ok=True)
os.makedirs("reference", exist_ok=True)

# ------------------------------------------------------------
# 1. u.npy -- shared input for reduce (basic_sum) and vmap (map_exp)
#    Shape 6x8 (differs from val's 10x5)
# ------------------------------------------------------------
u = np.random.standard_normal((6, 8)).astype(np.float32)
np.save("data/u.npy", u)

# ------------------------------------------------------------
# 2. mse.npz -- linear regression data for grad_mse (continuous targets)
#    N=18 samples, D=5 features
# ------------------------------------------------------------
N_mse, D_mse = 18, 5
X_mse = np.random.standard_normal((N_mse, D_mse)).astype(np.float32)
w_mse = np.random.standard_normal(D_mse).astype(np.float32)
noise_mse = (0.15 * np.random.standard_normal(N_mse)).astype(np.float32)
t_mse = (X_mse @ w_mse + noise_mse).astype(np.float32)
np.savez("data/mse.npz", x=X_mse, t=t_mse, w=w_mse)

# ------------------------------------------------------------
# 3. bce.npz -- binary classification data for grad_bce (sigmoid BCE loss)
#    N=22 samples, D=4 features, y_bin in {0,1}
# ------------------------------------------------------------
N_bce, D_bce = 22, 4
X_bce = np.random.standard_normal((N_bce, D_bce)).astype(np.float32)
w_bce = (0.5 * np.random.standard_normal(D_bce)).astype(np.float32)
logits_bce = X_bce @ w_bce
probs_bce = 1.0 / (1.0 + np.exp(-logits_bce))
# Deterministic labels: threshold on probability rank to get roughly balanced set.
y_bin = (probs_bce > np.median(probs_bce)).astype(np.float32)
np.savez("data/bce.npz", x=X_bce, y_bin=y_bin, w=w_bce)

# ------------------------------------------------------------
# 4. seq_rnn.npz -- sequence data for scan_rnn_v
#    T=12 timesteps, input dim I=5, hidden dim H=4
#    Keys: seq, init, Ux, Uh, c  (DELIBERATELY differ from val's Wx/Wh/b)
# ------------------------------------------------------------
T_seq, I_rnn, H_rnn = 12, 5, 4
seq_rnn = np.random.standard_normal((T_seq, I_rnn)).astype(np.float32)
init_rnn = np.zeros(H_rnn, dtype=np.float32)
# Ux maps input -> hidden (H, I); Uh maps hidden -> hidden (H, H); c bias (H,)
Ux = (0.3 * np.random.standard_normal((H_rnn, I_rnn))).astype(np.float32)
Uh = (0.3 * np.random.standard_normal((H_rnn, H_rnn))).astype(np.float32)
c = (0.1 * np.random.standard_normal(H_rnn)).astype(np.float32)
np.savez("data/seq_rnn.npz", seq=seq_rnn, init=init_rnn, Ux=Ux, Uh=Uh, c=c)

# ------------------------------------------------------------
# 5. mlp.npz -- inputs for jit_mlp (2-layer MLP with ReLU)
#    Batch B=9, input dim Din=7, hidden H=12, output Dout=3
#    Keys: X, W1, b1, W2, b2  (same schema as val's jit_mlp)
# ------------------------------------------------------------
B_mlp, Din_mlp, H_mlp, Dout_mlp = 9, 7, 12, 3
X_mlp = np.random.standard_normal((B_mlp, Din_mlp)).astype(np.float32)
W1 = (0.2 * np.random.standard_normal((Din_mlp, H_mlp))).astype(np.float32)
b1 = (0.1 * np.random.standard_normal(H_mlp)).astype(np.float32)
W2 = (0.2 * np.random.standard_normal((H_mlp, Dout_mlp))).astype(np.float32)
b2 = (0.1 * np.random.standard_normal(Dout_mlp)).astype(np.float32)
np.savez("data/mlp.npz", X=X_mlp, W1=W1, b1=b1, W2=W2, b2=b2)

# ============================================================
# Reference outputs (computed with JAX, saved to /reference)
# ============================================================

# basic_sum: sum along columns (axis=0)
ref_sum = jnp.sum(u, axis=0)
np.save("reference/basic_sum.npy", np.asarray(ref_sum))

# map_exp: elementwise exp via nested vmap (row-wise then column-wise)
ref_exp = jax.vmap(lambda row: jax.vmap(jnp.exp)(row))(u)
np.save("reference/map_exp.npy", np.asarray(ref_exp))


# grad_mse: gradient of mean-squared-error loss w.r.t. weights
def mse_loss(w, x, t):
    pred = jnp.dot(x, w)
    return jnp.mean((pred - t) ** 2)


ref_grad_mse = jax.grad(mse_loss, argnums=0)(w_mse, X_mse, t_mse)
np.save("reference/grad_mse.npy", np.asarray(ref_grad_mse))


# grad_bce: gradient of binary cross-entropy with sigmoid probs, labels in {0,1}
def bce_loss(w, x, y_bin):
    logits = jnp.dot(x, w)
    probs = jax.nn.sigmoid(logits)
    eps = 1e-12
    return -jnp.mean(
        y_bin * jnp.log(probs + eps) + (1.0 - y_bin) * jnp.log(1.0 - probs + eps)
    )


ref_grad_bce = jax.grad(bce_loss, argnums=0)(w_bce, X_bce, y_bin)
np.save("reference/grad_bce.npy", np.asarray(ref_grad_bce))


# scan_rnn_v: h_new = tanh(Ux @ x_t + Uh @ h + c), stacked hidden states
def rnn_step(h, x_t):
    h_new = jnp.tanh(Ux @ x_t + Uh @ h + c)
    return h_new, h_new


_, ref_hs = jax.lax.scan(rnn_step, init_rnn, seq_rnn)
np.save("reference/scan_rnn_v.npy", np.asarray(ref_hs))


# jit_mlp: y = relu(X @ W1 + b1) @ W2 + b2 (jit-compiled)
@jax.jit
def mlp(X, W1, b1, W2, b2):
    h = jax.nn.relu(jnp.dot(X, W1) + b1)
    return jnp.dot(h, W2) + b2


ref_mlp = mlp(X_mlp, W1, b1, W2, b2)
np.save("reference/jit_mlp.npy", np.asarray(ref_mlp))

print("Data and reference outputs generated (6 sub-tasks).")
