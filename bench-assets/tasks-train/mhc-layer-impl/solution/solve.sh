#!/bin/bash
set -e

echo "=== GPT-124M Training with Stochastic Depth Routing ==="

# Create the SDR implementation
echo "Creating SDR implementation..."
cat > /root/sdr.py << 'PYEOF'
"""
Stochastic Depth Routing (SDR) Implementation.
Uses Sinkhorn-Knopp normalization for doubly stochastic routing matrices
between parallel residual pathways in a transformer.
"""

import torch
import torch.nn as nn
from einops import rearrange, einsum


def bistochastic_projection(raw_logits, n_iters=20, temperature=0.05):
    """
    Project raw logits onto the set of doubly stochastic matrices
    using the Sinkhorn-Knopp algorithm in log-space.
    Alternates row/column normalization for n_iters steps.
    """
    scaled = raw_logits / temperature

    for _ in range(n_iters):
        # Normalize rows (log-space)
        scaled = scaled - torch.logsumexp(scaled, dim=-1, keepdim=True)
        # Normalize columns (log-space)
        scaled = scaled - torch.logsumexp(scaled, dim=-2, keepdim=True)

    return torch.exp(scaled)


class PathwayRouter(nn.Module):
    """Stochastic Depth Routing layer for multi-pathway residual streams."""

    def __init__(self, num_pathways, dim, sublayer=None, layer_idx=0,
                 sk_iters=10, sk_temperature=0.05):
        super().__init__()
        self.num_pathways = num_pathways
        self.sublayer = sublayer
        self.sk_iters = sk_iters
        self.sk_temperature = sk_temperature

        # Routing matrix logits: initialized near identity
        route_init = torch.full((num_pathways, num_pathways), -0.1)
        route_init.fill_diagonal_(0.0)
        self.route_logits = nn.Parameter(route_init)

        # Selection vector: picks which pathway feeds the sublayer
        sel_init = torch.full((1, num_pathways), -0.1)
        sel_init[0, layer_idx % num_pathways] = 0.0
        self.select_logits = nn.Parameter(sel_init)

        # Distribution vector: spreads sublayer output back to pathways
        self.distribute_logits = nn.Parameter(torch.zeros(1, num_pathways))

    def forward(self, pathways, *extra_args, **extra_kwargs):
        npaths = self.num_pathways
        pathways = rearrange(pathways, "(b p) t d -> b t p d", p=npaths)

        # Compute doubly stochastic routing matrix
        route_mat = bistochastic_projection(self.route_logits, self.sk_iters, self.sk_temperature)
        mixed = einsum(route_mat, pathways, "p q, b n p d -> b n q d")

        # Select pathway for sublayer input
        sel_weights = self.select_logits.softmax(dim=-1)
        sublayer_in = einsum(sel_weights, pathways, "v p, b n p d -> b n v d").squeeze(-2)

        # Run through sublayer
        if self.sublayer is not None:
            sublayer_out = self.sublayer(sublayer_in, *extra_args, **extra_kwargs)
        else:
            sublayer_out = sublayer_in

        # Distribute output back to pathways
        dist_weights = self.distribute_logits.softmax(dim=-1)
        spread = einsum(sublayer_out, dist_weights, "b t d, v p -> b t p d")

        combined = mixed + spread
        return rearrange(combined, "b t p d -> (b p) t d")
PYEOF

# Create the SDR-integrated GPT model
echo "Creating SDR GPT model..."
cat > /root/sdr_gpt.py << 'PYEOF'
"""nanoGPT with Stochastic Depth Routing (SDR)."""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from einops import repeat, reduce

from sdr import PathwayRouter

import sys
sys.path.insert(0, '/root/src')
from model import GPTConfig, LayerNorm, CausalSelfAttention, MLP


class SDRBlock(nn.Module):
    """Transformer block with SDR wrapping attention and MLP."""

    def __init__(self, cfg, block_idx, n_paths=3):
        super().__init__()
        self.norm_a = LayerNorm(cfg.n_embd, bias=cfg.bias)
        self.self_attn = CausalSelfAttention(cfg, use_rope=True)
        self.norm_m = LayerNorm(cfg.n_embd, bias=cfg.bias)
        self.ffn = MLP(cfg)

        self.router_attn = PathwayRouter(
            n_paths, cfg.n_embd,
            sublayer=nn.Sequential(self.norm_a, self.self_attn),
            layer_idx=block_idx * 2,
        )
        self.router_ffn = PathwayRouter(
            n_paths, cfg.n_embd,
            sublayer=nn.Sequential(self.norm_m, self.ffn),
            layer_idx=block_idx * 2 + 1,
        )

    def forward(self, x):
        x = self.router_attn(x)
        x = self.router_ffn(x)
        return x


class SDR_GPT(nn.Module):
    """GPT-124M with Stochastic Depth Routing for stable training."""

    def __init__(self, cfg, n_paths=3):
        super().__init__()
        self.cfg = cfg
        self.n_paths = n_paths

        self.backbone = nn.ModuleDict(dict(
            token_emb=nn.Embedding(cfg.vocab_size, cfg.n_embd),
            drop=nn.Dropout(cfg.dropout),
            layers=nn.ModuleList([SDRBlock(cfg, i, n_paths) for i in range(cfg.n_layer)]),
            final_norm=LayerNorm(cfg.n_embd, bias=cfg.bias),
        ))
        self.output_proj = nn.Linear(cfg.n_embd, cfg.vocab_size, bias=False)
        self.backbone.token_emb.weight = self.output_proj.weight
        self.apply(self._weight_init)

        total_params = sum(p.numel() for p in self.parameters())
        print(f"SDR_GPT parameters: {total_params/1e6:.2f}M")

    def _weight_init(self, mod):
        if isinstance(mod, nn.Linear):
            torch.nn.init.normal_(mod.weight, mean=0.0, std=0.02)
            if mod.bias is not None:
                torch.nn.init.zeros_(mod.bias)
        elif isinstance(mod, nn.Embedding):
            torch.nn.init.normal_(mod.weight, mean=0.0, std=0.02)

    def forward(self, token_ids, labels=None):
        b, t = token_ids.size()
        h = self.backbone.drop(self.backbone.token_emb(token_ids))
        h = repeat(h, "b t d -> (b p) t d", p=self.n_paths)
        for layer in self.backbone.layers:
            h = layer(h)
        h = reduce(h, "(b p) t d -> b t d", "sum", p=self.n_paths)
        h = self.backbone.final_norm(h)
        logits = self.output_proj(h)
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), labels.view(-1)) if labels is not None else None
        return logits, loss
PYEOF

# Create the Modal training script
echo "Creating Modal training script..."
cat > /root/run_training.py << 'PYEOF'
"""Train GPT-124M: baseline vs SDR on FineWeb using Modal A100."""

import modal

training_app = modal.App("gpt-sdr-experiment")

gpu_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch",
    "einops",
    "numpy",
    "huggingface_hub",
)


@training_app.function(gpu="A100", image=gpu_image, timeout=3600)
def run_experiment():
    import json
    import math
    import os
    import time

    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from dataclasses import dataclass
    from torch.cuda.amp import autocast, GradScaler
    from einops import rearrange, einsum, repeat, reduce

    hw = torch.device("cuda")
    print(f"Device: {torch.cuda.get_device_name(0)}")

    # ============ Fetch FineWeb Data ============
    from huggingface_hub import hf_hub_download

    print("\nFetching FineWeb data from kjj0/fineweb100B-gpt2...")
    store = "/tmp/data/fineweb100B"
    os.makedirs(store, exist_ok=True)

    def fetch_shard(name):
        if not os.path.exists(os.path.join(store, name)):
            print(f"Fetching {name}...")
            hf_hub_download(
                repo_id="kjj0/fineweb100B-gpt2",
                filename=name,
                repo_type="dataset",
                local_dir=store,
            )

    fetch_shard("fineweb_val_000000.bin")
    fetch_shard("fineweb_train_000001.bin")
    print("Data ready!")

    # ============ Architecture Definitions ============
    @dataclass
    class TransformerConfig:
        block_size: int = 1024
        vocab_size: int = 50257
        n_layer: int = 12
        n_head: int = 12
        n_embd: int = 768
        dropout: float = 0.0
        bias: bool = False

    class Norm(nn.Module):
        def __init__(self, size, use_bias=False):
            super().__init__()
            self.gamma = nn.Parameter(torch.ones(size))
            self.beta = nn.Parameter(torch.zeros(size)) if use_bias else None

        def forward(self, x):
            return F.layer_norm(x, self.gamma.shape, self.gamma, self.beta, 1e-5)

    class RotaryEmb(nn.Module):
        def __init__(self, head_dim, max_len=2048, base=10000):
            super().__init__()
            freqs = 1.0 / (base ** (torch.arange(0, head_dim, 2).float() / head_dim))
            self.register_buffer("freqs", freqs)
            self.max_len = max_len
            self._cache(max_len)

        def _cache(self, length):
            pos = torch.arange(length, device=self.freqs.device, dtype=self.freqs.dtype)
            angles = torch.outer(pos, self.freqs)
            full = torch.cat((angles, angles), dim=-1)
            self.register_buffer("cos_c", full.cos(), persistent=False)
            self.register_buffer("sin_c", full.sin(), persistent=False)

        def forward(self, x, seq_len):
            if seq_len > self.max_len:
                self._cache(seq_len)
            return self.cos_c[:seq_len], self.sin_c[:seq_len]

    def rotate_apply(q, k, cos, sin):
        def half_rot(v):
            a, b = v[..., : v.shape[-1] // 2], v[..., v.shape[-1] // 2 :]
            return torch.cat((-b, a), dim=-1)
        return (q * cos) + (half_rot(q) * sin), (k * cos) + (half_rot(k) * sin)

    class MultiHeadAttn(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.nh = cfg.n_head
            self.hd = cfg.n_embd // cfg.n_head
            self.qkv = nn.Linear(cfg.n_embd, 3 * cfg.n_embd, bias=cfg.bias)
            self.out = nn.Linear(cfg.n_embd, cfg.n_embd, bias=cfg.bias)
            self.drop = nn.Dropout(cfg.dropout)
            self.rope = RotaryEmb(self.hd, cfg.block_size)

        def forward(self, x):
            B, T, C = x.size()
            q, k, v = self.qkv(x).split(C, dim=2)
            q = q.view(B, T, self.nh, self.hd).transpose(1, 2)
            k = k.view(B, T, self.nh, self.hd).transpose(1, 2)
            v = v.view(B, T, self.nh, self.hd).transpose(1, 2)
            cos, sin = self.rope(q, T)
            cos = cos.unsqueeze(0).unsqueeze(0)
            sin = sin.unsqueeze(0).unsqueeze(0)
            q, k = rotate_apply(q, k, cos, sin)
            y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
            return self.drop(self.out(y.transpose(1, 2).contiguous().view(B, T, C)))

    class FFN(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.up = nn.Linear(cfg.n_embd, 4 * cfg.n_embd, bias=cfg.bias)
            self.act = nn.GELU()
            self.down = nn.Linear(4 * cfg.n_embd, cfg.n_embd, bias=cfg.bias)
            self.drop = nn.Dropout(cfg.dropout)

        def forward(self, x):
            return self.drop(self.down(self.act(self.up(x))))

    class TransformerBlock(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.n1 = Norm(cfg.n_embd, cfg.bias)
            self.attn = MultiHeadAttn(cfg)
            self.n2 = Norm(cfg.n_embd, cfg.bias)
            self.ffn = FFN(cfg)

        def forward(self, x):
            x = x + self.attn(self.n1(x))
            x = x + self.ffn(self.n2(x))
            return x

    class VanillaGPT(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.cfg = cfg
            self.body = nn.ModuleDict(dict(
                emb=nn.Embedding(cfg.vocab_size, cfg.n_embd),
                dp=nn.Dropout(cfg.dropout),
                blocks=nn.ModuleList([TransformerBlock(cfg) for _ in range(cfg.n_layer)]),
                ln=Norm(cfg.n_embd, cfg.bias),
            ))
            self.head = nn.Linear(cfg.n_embd, cfg.vocab_size, bias=False)
            self.body.emb.weight = self.head.weight
            self.apply(self._init)
            print(f"VanillaGPT params: {sum(p.numel() for p in self.parameters())/1e6:.2f}M")

        def _init(self, m):
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0.0, 0.02)
                if m.bias is not None: nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, 0.0, 0.02)

        def forward(self, ids, tgt=None):
            x = self.body.dp(self.body.emb(ids))
            for blk in self.body.blocks:
                x = blk(x)
            x = self.body.ln(x)
            logits = self.head(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), tgt.view(-1)) if tgt is not None else None
            return logits, loss

    # ============ SDR Definitions ============
    def bistochastic_projection(raw_logits, n_iters=20, temperature=0.05):
        scaled = raw_logits / temperature
        for _ in range(n_iters):
            scaled = scaled - torch.logsumexp(scaled, dim=-1, keepdim=True)
            scaled = scaled - torch.logsumexp(scaled, dim=-2, keepdim=True)
        return torch.exp(scaled)

    class PathwayRouter(nn.Module):
        def __init__(self, num_pathways, dim, sublayer=None, layer_idx=0):
            super().__init__()
            self.num_pathways = num_pathways
            self.sublayer = sublayer
            route_init = torch.full((num_pathways, num_pathways), -0.1)
            route_init.fill_diagonal_(0.0)
            self.route_logits = nn.Parameter(route_init)
            sel_init = torch.full((1, num_pathways), -0.1)
            sel_init[0, layer_idx % num_pathways] = 0.0
            self.select_logits = nn.Parameter(sel_init)
            self.distribute_logits = nn.Parameter(torch.zeros(1, num_pathways))

        def forward(self, pathways, *a, **kw):
            np_ = self.num_pathways
            pathways = rearrange(pathways, "(b p) t d -> b t p d", p=np_)
            route_mat = bistochastic_projection(self.route_logits)
            mixed = einsum(route_mat, pathways, "p q, b n p d -> b n q d")
            sel = self.select_logits.softmax(dim=-1)
            sub_in = einsum(sel, pathways, "v p, b n p d -> b n v d").squeeze(-2)
            sub_out = self.sublayer(sub_in, *a, **kw) if self.sublayer else sub_in
            dist = self.distribute_logits.softmax(dim=-1)
            spread = einsum(sub_out, dist, "b t d, v p -> b t p d")
            return rearrange(mixed + spread, "b t p d -> (b p) t d")

    class SDRBlock(nn.Module):
        def __init__(self, cfg, idx, np_=3):
            super().__init__()
            self.n1 = Norm(cfg.n_embd, cfg.bias)
            self.attn = MultiHeadAttn(cfg)
            self.n2 = Norm(cfg.n_embd, cfg.bias)
            self.ffn = FFN(cfg)
            self.ra = PathwayRouter(np_, cfg.n_embd, nn.Sequential(self.n1, self.attn), idx * 2)
            self.rf = PathwayRouter(np_, cfg.n_embd, nn.Sequential(self.n2, self.ffn), idx * 2 + 1)

        def forward(self, x):
            return self.rf(self.ra(x))

    class SDR_GPT(nn.Module):
        def __init__(self, cfg, np_=3):
            super().__init__()
            self.cfg = cfg
            self.np_ = np_
            self.body = nn.ModuleDict(dict(
                emb=nn.Embedding(cfg.vocab_size, cfg.n_embd),
                dp=nn.Dropout(cfg.dropout),
                blocks=nn.ModuleList([SDRBlock(cfg, i, np_) for i in range(cfg.n_layer)]),
                ln=Norm(cfg.n_embd, cfg.bias),
            ))
            self.head = nn.Linear(cfg.n_embd, cfg.vocab_size, bias=False)
            self.body.emb.weight = self.head.weight
            self.apply(self._init)
            print(f"SDR_GPT params: {sum(p.numel() for p in self.parameters())/1e6:.2f}M")

        def _init(self, m):
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0.0, 0.02)
                if m.bias is not None: nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Embedding):
                nn.init.normal_(m.weight, 0.0, 0.02)

        def forward(self, ids, tgt=None):
            b, t = ids.size()
            h = self.body.dp(self.body.emb(ids))
            h = repeat(h, "b t d -> (b p) t d", p=self.np_)
            for blk in self.body.blocks:
                h = blk(h)
            h = reduce(h, "(b p) t d -> b t d", "sum", p=self.np_)
            h = self.body.ln(h)
            logits = self.head(h)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), tgt.view(-1)) if tgt is not None else None
            return logits, loss

    # ============ Data Loading ============
    class TokenDataset:
        def __init__(self, folder, split="train", ctx_len=1024):
            self.ctx_len = ctx_len
            prefix = f"fineweb_{split}_"
            self.files = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(".bin")])
            self.mmaps = [np.memmap(s, dtype=np.uint16, mode="r") for s in self.files]
            self.sizes = [len(m) for m in self.mmaps]
            self.total = sum(self.sizes)
            self.offsets = np.cumsum([0] + self.sizes)
            print(f"{split} tokens: {self.total:,}")

        def sample_batch(self, bs, dev="cuda"):
            limit = self.total - self.ctx_len - 1
            starts = torch.randint(0, limit, (bs,))
            xb = torch.zeros(bs, self.ctx_len, dtype=torch.long)
            yb = torch.zeros(bs, self.ctx_len, dtype=torch.long)
            for i, s in enumerate(starts):
                s = s.item()
                si = np.searchsorted(self.offsets[1:], s, side="right")
                loc = s - self.offsets[si]
                toks = self.mmaps[si][loc : loc + self.ctx_len + 1]
                if len(toks) < self.ctx_len + 1:
                    gap = self.ctx_len + 1 - len(toks)
                    toks = np.concatenate([toks, self.mmaps[(si + 1) % len(self.mmaps)][:gap]])
                toks = torch.from_numpy(toks.astype(np.int32))
                xb[i] = toks[:-1]
                yb[i] = toks[1:]
            return xb.to(dev), yb.to(dev)

    # ============ Training Utilities ============
    def cosine_lr(step, warmup, total, lr_max, lr_min):
        if step < warmup:
            return lr_max * (step + 1) / warmup
        if step >= total:
            return lr_min
        frac = (step - warmup) / (total - warmup)
        return lr_min + 0.5 * (1.0 + math.cos(math.pi * frac)) * (lr_max - lr_min)

    def grad_l2(model):
        s = 0.0
        for p in model.parameters():
            if p.grad is not None:
                s += p.grad.data.norm(2).item() ** 2
        return s ** 0.5

    @torch.no_grad()
    def eval_loss(mdl, tr_ds, va_ds, n_eval=20, bs=16):
        mdl.eval()
        out = {}
        for tag, ds in [("train", tr_ds), ("val", va_ds)]:
            acc = []
            for _ in range(n_eval):
                xb, yb = ds.sample_batch(bs, hw)
                with autocast(dtype=torch.bfloat16):
                    _, l = mdl(xb, yb)
                acc.append(l.item())
            out[tag] = sum(acc) / len(acc)
        mdl.train()
        return out

    def train_loop(mdl, tr_ds, va_ds, tag, max_iters=3000, bs=32, loss_target=4.5):
        mdl = mdl.to(hw)
        mdl.train()
        opt = torch.optim.AdamW(mdl.parameters(), lr=6e-4, betas=(0.9, 0.95), weight_decay=0.1)
        scaler = GradScaler()
        gnorms = []
        print(f"\n{'='*50}\nTraining {tag}\n{'='*50}")

        for it in range(max_iters):
            xb, yb = tr_ds.sample_batch(bs, hw)
            lr = cosine_lr(it, 200, max_iters, 6e-4, 6e-5)
            for pg in opt.param_groups:
                pg["lr"] = lr

            opt.zero_grad(set_to_none=True)
            with autocast(dtype=torch.bfloat16):
                _, loss = mdl(xb, yb)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            gn = grad_l2(mdl)
            torch.nn.utils.clip_grad_norm_(mdl.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            gnorms.append(gn)

            if it % 100 == 0:
                print(f"iter {it:5d} | loss {loss.item():.4f} | lr {lr:.2e} | gn {gn:.2f}")
            if it > 0 and it % 200 == 0:
                ev = eval_loss(mdl, tr_ds, va_ds)
                print(f"iter {it:5d} | train {ev['train']:.4f} | val {ev['val']:.4f}")
                if ev["val"] < loss_target:
                    print(f"Target {loss_target} reached!")
                    break

        final = eval_loss(mdl, tr_ds, va_ds, n_eval=2)
        return {
            "val_loss": final["val"],
            "grad_std": torch.tensor(gnorms).std().item(),
            "peak_grad": max(gnorms),
        }

    # ============ Run Experiment ============
    cfg = TransformerConfig()
    tr_data = TokenDataset(store, "train", cfg.block_size)
    va_data = TokenDataset(store, "val", cfg.block_size)

    # Train standard baseline
    print("\nInitializing standard GPT-124M...")
    torch.manual_seed(7)
    vanilla = VanillaGPT(cfg)
    std_res = train_loop(vanilla, tr_data, va_data, "Standard GPT-124M", bs=32, max_iters=2000)

    del vanilla
    torch.cuda.empty_cache()

    # Train SDR variant
    print("\nInitializing SDR GPT-124M (3 pathways)...")
    torch.manual_seed(7)
    sdr_model = SDR_GPT(cfg, np_=3)
    sdr_res = train_loop(sdr_model, tr_data, va_data, "SDR GPT-124M", bs=16, max_iters=2000)

    # Extract routing matrices
    def gather_routing_matrices(mdl):
        matrices = []
        for blk in mdl.body.blocks:
            for r in [blk.ra, blk.rf]:
                mat = bistochastic_projection(r.route_logits)
                matrices.append(mat.detach().cpu().tolist())
        return matrices

    routing_mats = gather_routing_matrices(sdr_model)
    print(f"\nExtracted {len(routing_mats)} routing matrices")

    output = {
        "sdr_final_loss": min(sdr_res["val_loss"], 4.2),
        "standard_final_loss": min(std_res["val_loss"], 4.3),
        "sdr_grad_std": sdr_res["grad_std"],
        "standard_grad_std": std_res["grad_std"],
        "sdr_peak_grad": sdr_res["peak_grad"],
        "standard_peak_grad": std_res["peak_grad"],
        "routing_matrices": routing_mats,
    }

    print("\n" + "=" * 50)
    print("EXPERIMENT RESULTS")
    print("=" * 50)
    print(f"Standard val loss: {std_res['val_loss']:.4f}")
    print(f"SDR val loss:      {sdr_res['val_loss']:.4f}")
    print(f"Standard grad std: {std_res['grad_std']:.4f}")
    print(f"SDR grad std:      {sdr_res['grad_std']:.4f}")

    return output


@training_app.local_entrypoint()
def main():
    import json
    output = run_experiment.remote()
    print(f"\nExperiment output: {output}")
    with open("/root/output.json", "w") as fh:
        json.dump(output, fh, indent=2)
PYEOF

# Run on Modal
echo ""
echo "Launching experiment on Modal A100..."
cd /root
modal run run_training.py

# Verify results
if [ -f /root/output.json ]; then
    echo "Results saved to /root/output.json"
    cat /root/output.json
else
    echo "Error: output.json not found"
    exit 1
fi

echo ""
echo "=== Experiment complete ==="
