# JAX Skills Library

This directory contains reusable JAX computation skills for numerical computing tasks.

## Available Skills

### jax-load
Load numpy `.npy` or `.npz` files into JAX arrays.

### jax-save
Save JAX arrays to numpy `.npy` files.

### jax-map
Apply elementwise operations using vectorization (vmap). Supported ops: "tanh".

### jax-reduce
Reduce arrays along a given axis. Supported ops: "prod".

### jax-grad
Compute gradient of hinge loss using `jax.grad`.

### jax-scan
Run an IIR low-pass filter using `jax.lax.scan`.

### jax-jit
JIT compile and execute a function using `jax.jit`.

### jax-vmap-outer
Compute outer products of row pairs using `jax.vmap`.

## Usage

Each `.skill` file describes inputs, outputs, and the Python implementation reference.
Load skills from this directory and call their implementations with the specified arguments.
