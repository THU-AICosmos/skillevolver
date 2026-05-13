I want to enhance gradient flow in a nanoGPT (124M) model during training. Inspired by recent work on optimal transport for residual connections, I want to implement a Stochastic Depth Routing (SDR) layer that uses Sinkhorn-Knopp normalization to create doubly stochastic routing matrices between multiple parallel pathways.

The training uses an A100 GPU from modal(https://modal.com/) on the Fineweb dataset. The baseline model is provided in /root/src (data, model, train.py). Your task is to implement the SDR layer, then train both the baseline and the SDR-enhanced model until validation loss < 4.5 or 3000 steps.

The SDR layer works as follows:
- Maintain `num_pathways` parallel residual streams (use 3 pathways)
- Use a learnable routing matrix projected to doubly stochastic via Sinkhorn-Knopp
- A selection vector picks which pathway feeds each sub-layer (attention or MLP)
- A distribution vector spreads the sub-layer output back across pathways

You should train both the baseline and SDR model in the same script, and return the following results in JSON format as output.json.

```json
{
  "sdr_final_loss": <float>,
  "standard_final_loss": <float>,
  "sdr_grad_std": <float>,
  "standard_grad_std": <float>,
  "sdr_peak_grad": <float>,
  "standard_peak_grad": <float>,
  "routing_matrices": [[<float>, ...], ...]
}
```

Reference: Sinkhorn-Knopp algorithm for optimal transport; doubly stochastic matrix projection for neural network routing.
