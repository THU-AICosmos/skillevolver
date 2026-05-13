#!/usr/bin/env python3
"""
Reference solution for coral reef fish school clustering optimization task.
Uses DBSCAN with anisotropic distance, grid search, and Pareto frontier identification.
"""

from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from paretoset import paretoset
from scipy.spatial import distance_matrix
from sklearn.cluster import DBSCAN


class AnisotropicDBSCAN:
    """Helper class for running DBSCAN with a stretch-weighted metric."""

    @staticmethod
    def pairwise_distances(coords, s_factor):
        delta = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        weights = np.array([s_factor, 2.0 - s_factor])
        return np.sqrt(((delta * weights) ** 2).sum(axis=2))

    @staticmethod
    def find_clusters(coords, eps_r, min_p, s_factor):
        if len(coords) == 0:
            return np.array([]), np.array([])
        dm = AnisotropicDBSCAN.pairwise_distances(coords, s_factor)
        model = DBSCAN(eps=eps_r, min_samples=min_p, metric="precomputed")
        assignments = model.fit_predict(dm)
        cluster_ids = sorted(set(assignments) - {-1})
        if not cluster_ids:
            return np.array([]), assignments
        centers = np.array([coords[assignments == cid].mean(axis=0) for cid in cluster_ids])
        return centers, assignments


def nearest_pair_matching(predicted, ground_truth, threshold=80):
    """Greedy nearest-pair matching between predicted centroids and ground truth."""
    if predicted.size == 0 or ground_truth.size == 0:
        return 0, predicted.shape[0] if predicted.size else 0, ground_truth.shape[0] if ground_truth.size else 0, []

    dists = distance_matrix(predicted, ground_truth)
    paired = []

    while dists.size > 0:
        loc = np.unravel_index(np.argmin(dists), dists.shape)
        d = dists[loc]
        if d >= threshold:
            break
        paired.append((loc[0], loc[1], d))
        dists[loc[0], :] = np.inf
        dists[:, loc[1]] = np.inf

    n_tp = len(paired)
    n_fp = len(predicted) - n_tp
    n_fn = len(ground_truth) - n_tp
    return n_tp, n_fp, n_fn, paired


def site_level_metrics(vol_coords, bio_coords, mp, er, sf):
    """Compute F1 and mean offset for a single dive site."""
    if len(vol_coords) == 0:
        return 0.0, np.nan

    centers, _ = AnisotropicDBSCAN.find_clusters(vol_coords, er, mp, sf)

    if centers.size == 0:
        return 0.0, np.nan

    tp, fp, fn, paired = nearest_pair_matching(centers, bio_coords)

    if tp == 0:
        return 0.0, np.nan

    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    f1_val = 2.0 * prec * rec / (prec + rec)
    mean_dist = np.mean([p[2] for p in paired])
    return f1_val, mean_dist


def run_single_config(config_tuple, all_site_arrays):
    """Evaluate one (min_pts, eps_radius, stretch_factor) configuration."""
    mp, er, sf = config_tuple

    scores = []
    offsets = []

    for v_arr, b_arr in all_site_arrays:
        s, o = site_level_metrics(v_arr, b_arr, mp, er, sf)
        scores.append(s)
        if not np.isnan(o):
            offsets.append(o)

    avg_score = np.mean(scores)
    avg_offset = np.mean(offsets) if offsets else np.inf

    if avg_score > 0.4 and not np.isinf(avg_offset):
        return {
            "score": avg_score,
            "offset": avg_offset,
            "min_pts": mp,
            "eps_radius": er,
            "stretch_factor": round(sf, 1),
        }
    return None


def main():
    base = Path("/root/data")
    vol_df = pd.read_csv(base / "volunteer_obs.csv")
    bio_df = pd.read_csv(base / "biologist_obs.csv")

    print(f"Loaded {len(vol_df)} volunteer and {len(bio_df)} biologist observations")

    # Group by dive_site — iterate over biologist sites (some may lack volunteer data)
    all_bio_sites = bio_df["dive_site"].unique()
    grouped = []
    for ds in all_bio_sites:
        v = vol_df[vol_df["dive_site"] == ds][["px", "py"]].values
        b = bio_df[bio_df["dive_site"] == ds][["px", "py"]].values
        grouped.append((v, b))

    print(f"Evaluating across {len(grouped)} dive sites")

    # Build parameter grid
    mp_vals = list(range(2, 8))
    er_vals = list(range(5, 36, 5))
    sf_vals = list(np.arange(0.6, 1.7, 0.1))
    configs = list(product(mp_vals, er_vals, sf_vals))
    print(f"Total configurations: {len(configs)}")

    # Parallel evaluation
    raw_results = Parallel(n_jobs=-1, verbose=10)(
        delayed(run_single_config)(cfg, grouped) for cfg in configs
    )

    valid = [r for r in raw_results if r is not None]
    print(f"Configurations passing threshold: {len(valid)}")

    df = pd.DataFrame(valid)

    # Pareto frontier: maximize score, minimize offset
    mask = paretoset(df[["score", "offset"]], sense=["max", "min"])
    frontier = df[mask].copy()

    frontier = frontier.sort_values("score", ascending=False)
    frontier["score"] = frontier["score"].round(5)
    frontier["offset"] = frontier["offset"].round(5)
    frontier["stretch_factor"] = frontier["stretch_factor"].round(1)

    # Remove any remaining dominated points after rounding (ties can create domination)
    keep_idx = []
    vals = frontier[["score", "offset"]].values
    for i in range(len(vals)):
        dominated = False
        for j in range(len(vals)):
            if i == j:
                continue
            if vals[j, 0] >= vals[i, 0] and vals[j, 1] <= vals[i, 1]:
                if vals[j, 0] > vals[i, 0] or vals[j, 1] < vals[i, 1]:
                    dominated = True
                    break
        if not dominated:
            keep_idx.append(frontier.index[i])
    frontier = frontier.loc[keep_idx]

    print(f"\nPareto-optimal configurations: {len(frontier)}")
    print(frontier.to_string(index=False))

    out = Path("/root/optimal_tradeoffs.csv")
    frontier.to_csv(out, index=False)
    print(f"\nWritten to {out}")


if __name__ == "__main__":
    main()
