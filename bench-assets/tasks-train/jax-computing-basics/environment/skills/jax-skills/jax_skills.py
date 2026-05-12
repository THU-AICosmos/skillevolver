import jax
import jax.numpy as jnp
import numpy as np


def load(path):
    if path.endswith(".npz"):
        return dict(np.load(path))
    return jnp.array(np.load(path))


def save(data, path):
    np.save(path, np.array(data))


def map_op(array, op):
    if op == "tanh":
        return jax.vmap(lambda x: jnp.tanh(x))(array)
    raise ValueError("Unknown op")


def reduce_op(array, op, axis):
    if op == "prod":
        return jnp.prod(array, axis=axis)
    raise ValueError("Unknown reduce op")


def hinge_grad(x, y, w):
    def loss(w):
        logits = x @ w
        return jnp.mean(jnp.maximum(0, 1 - y * logits))

    return jax.grad(loss)(w)


def iir_scan(signal, alpha, beta):
    def step(h, x):
        h_new = alpha * h + beta * x
        return h_new, h_new

    h0 = jnp.zeros(signal.shape[1])
    _, filtered = jax.lax.scan(step, h0, signal)
    return filtered


def jit_run(fn, args):
    return jax.jit(fn)(*args)


def vmap_outer(a, b):
    return jax.vmap(lambda x, y: jnp.outer(x, y))(a, b)
