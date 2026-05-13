# Coral Reef Fish School Clustering Optimization

## Task

Optimize DBSCAN hyperparameters to cluster citizen diver annotations of coral reef fish schools. Find the **Pareto frontier** of solutions that balance:

- **Maximize score** — F1 agreement between clustered annotations and marine biologist labels
- **Minimize offset** — average standard Euclidean distance between matched cluster centroids and biologist points

## Data

Located in `/root/data/`:

- `volunteer_obs.csv` — Volunteer diver annotations (columns: `dive_site`, `px`, `py`)
- `biologist_obs.csv` — Marine biologist annotations (columns: `dive_site`, `px`, `py`)

Use the `dive_site` column to match survey frames between the two datasets.

## Hyperparameter Search Space

Perform a grid search over all combinations of:
- `min_pts`: 2–7 (integers, i.e., 2, 3, 4, 5, 6, 7)
- `eps_radius`: 5-35 (step 5, i.e. 5, 10, 15, 20, 25, 30, 35) (integers)
- `stretch_factor`: 0.6–1.6 (step 0.1, i.e., 0.6, 0.7, 0.8, ..., 1.5, 1.6)

You may use parallelization to speed up the computation.

DBSCAN should use an anisotropic distance metric controlled by `stretch_factor` (s):

```
d(a, b) = sqrt((s * Δpx)² + ((2 - s) * Δpy)²)
```

When s=1, this equals standard Euclidean distance. Values s>1 attenuate py-distances; s<1 attenuate px-distances.

## Evaluation

For each hyperparameter combination:

1. Loop over unique dive sites (using `dive_site` to identify frames)
2. For each site, run DBSCAN on volunteer points and compute cluster centroids
3. Match cluster centroids to biologist annotations using greedy matching (closest pairs first, max distance 80 pixels) based on the standard Euclidean distance (not the anisotropic one)
4. Compute F1 score and average offset (average standard Euclidean distance, not the anisotropic one) for each site
5. Average score and offset across all sites
6. Only keep results with average score > 0.4 (meaningful clustering performance)

**Note:** When computing averages:
- Loop over all unique sites from the biologist dataset (not just sites that have volunteer annotations)
- If a site has no volunteer points, DBSCAN finds no clusters, or no matches are found, set score = 0.0 and offset = NaN for that site
- Include score = 0.0 values in the score average (all sites contribute to the average score)
- Exclude offset = NaN values from the offset average (only average over sites where matches were found)

Finally, identify all Pareto-optimal points from the filtered results.

## Output

Write to `/root/optimal_tradeoffs.csv`:

```csv
score,offset,min_pts,eps_radius,stretch_factor
```

Round `score` and `offset` to 5 decimal places, and `stretch_factor` to 1 decimal place. `min_pts` and `eps_radius` are integers.
