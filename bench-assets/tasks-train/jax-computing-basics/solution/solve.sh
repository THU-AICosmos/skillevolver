#!/bin/bash
# Oracle solver for the jax-computing-basics train variant (6 sub-tasks).
#
# Works without depending on /app/skills so it can be verified standalone via Docker.

set -e
echo "=== solve.sh starting ==="
echo "PWD: $(pwd)"
echo "Contents of /app:"
ls -la /app/ || echo "Cannot list /app"

python3 << 'EOF'
import json
import os
import numpy as np
import jax
import jax.numpy as jnp


def load_problems(path="/app/problem.json"):
    with open(path) as fh:
        return json.load(fh)


def load_input(rel_path, root="/app"):
    full = os.path.join(root, rel_path)
    if full.endswith(".npz"):
        return dict(np.load(full))
    return np.load(full)


def save_output(arr, rel_path, root="/app"):
    out = os.path.join(root, rel_path)
    np.save(out, np.asarray(arr))


# ---- Per-task solvers ---------------------------------------------------

# basic_sum: column sum reduction via jnp.sum(u, axis=0).
def solve_basic_sum(inp):
    u = load_input(inp)
    return jnp.sum(u, axis=0)


# map_exp: elementwise exp via nested vmap (vmap-of-vmap over 2D input).
def solve_map_exp(inp):
    u = load_input(inp)
    return jax.vmap(lambda row: jax.vmap(jnp.exp)(row))(u)


# grad_mse: jax.grad of L(w) = mean((x @ w - t)**2) w.r.t. w,
# reading x/t/w from the npz bundle.
def solve_grad_mse(inp):
    data = load_input(inp)
    X = jnp.asarray(data["x"])
    t = jnp.asarray(data["t"])
    w = jnp.asarray(data["w"])

    def loss(weights):
        pred = jnp.dot(X, weights)
        return jnp.mean((pred - t) ** 2)

    return jax.grad(loss)(w)


# grad_bce: jax.grad of sigmoid binary cross-entropy loss w.r.t. w,
# reading x/y_bin/w from the npz bundle. Labels are {0,1}.
def solve_grad_bce(inp):
    data = load_input(inp)
    X = jnp.asarray(data["x"])
    y_bin = jnp.asarray(data["y_bin"])
    w = jnp.asarray(data["w"])

    def loss(weights):
        logits = jnp.dot(X, weights)
        probs = jax.nn.sigmoid(logits)
        eps = 1e-12
        return -jnp.mean(
            y_bin * jnp.log(probs + eps)
            + (1.0 - y_bin) * jnp.log(1.0 - probs + eps)
        )

    return jax.grad(loss)(w)


# scan_rnn_v: h_new = tanh(Ux @ x_t + Uh @ h + c) via jax.lax.scan,
# reading Ux/Uh/c (NOT Wx/Wh/b) from the npz bundle. Output is stacked hidden states.
def solve_scan_rnn_v(inp):
    data = load_input(inp)
    seq = jnp.asarray(data["seq"])
    init = jnp.asarray(data["init"])
    Ux = jnp.asarray(data["Ux"])
    Uh = jnp.asarray(data["Uh"])
    c = jnp.asarray(data["c"])

    def step(h, x_t):
        h_new = jnp.tanh(Ux @ x_t + Uh @ h + c)
        return h_new, h_new

    _, stacked = jax.lax.scan(step, init, seq)
    return stacked


# jit_mlp: jax.jit of 2-layer MLP y = relu(X @ W1 + b1) @ W2 + b2,
# reading X/W1/b1/W2/b2 from the npz bundle.
def solve_jit_mlp(inp):
    data = load_input(inp)
    X = jnp.asarray(data["X"])
    W1 = jnp.asarray(data["W1"])
    b1 = jnp.asarray(data["b1"])
    W2 = jnp.asarray(data["W2"])
    b2 = jnp.asarray(data["b2"])

    @jax.jit
    def mlp(X, W1, b1, W2, b2):
        h = jax.nn.relu(jnp.dot(X, W1) + b1)
        return jnp.dot(h, W2) + b2

    return mlp(X, W1, b1, W2, b2)


DISPATCH = {
    "basic_sum": solve_basic_sum,
    "map_exp": solve_map_exp,
    "grad_mse": solve_grad_mse,
    "grad_bce": solve_grad_bce,
    "scan_rnn_v": solve_scan_rnn_v,
    "jit_mlp": solve_jit_mlp,
}

problems = load_problems()
for prob in problems:
    pid = prob["id"]
    print(f"Solving problem: {pid}")
    solver = DISPATCH[pid]
    result = solver(prob["input"])
    save_output(result, prob["output"])

print("All problems solved.")
EOF
