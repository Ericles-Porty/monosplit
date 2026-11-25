# Controls

Both controls receive the same graph and the *K* of each accepted run of the large language model (LLM). The code is in `src/monosplit/controls.py`.

## Hierarchical clustering (AH)

Agglomerative hierarchical clustering from scikit-learn receives a precomputed distance matrix, and the dendrogram is cut into exactly *K* clusters. There are two distances between classes $a$ and $b$:

- **calls:** $d(a, b) = \dfrac{1}{1 + c_{ab} + c_{ba}}$, where $c_{ab}$ is the number of calls from $a$ to $b$; classes with no calls between them are at distance 1;
- **neighbours:** Jaccard distance between the closed neighbourhoods, $d(a, b) = 1 - \dfrac{\lvert N[a] \cap N[b] \rvert}{\lvert N[a] \cup N[b] \rvert}$, where $N[a]$ holds $a$ and every class that calls $a$ or is called by it.

The linkages are average, complete and single; Ward linkage needs Euclidean coordinates and does not apply to a distance matrix. Two distances and three linkages make six variants.

**Choice of the variant.** The experiment configuration fixes the AH control (`ah_primary`). The final experiment uses `neighbors:complete`, chosen after the pilot: it was the variant selected in the JPetStore pilot and in most pilot studies. The six variants are still computed and reported. The configuration also accepts `auto`, the rule fixed before the pilot runs: the variant with the highest median structural modularity (SM) over the accepted runs of the study becomes the control, and a tie goes to the variant listed first. That rule was replaced because it selects on the dependent variable itself, with the same runs, and so favours the control in SM. The choice used pilot data, and JPetStore is also in the final experiment, so it favours AH on that application, which goes to the threats to validity. The [Results](#/results) page shows the median SM of each variant and the one used.

## Random partition

The partition is drawn uniformly from all partitions of the classes into exactly *K* non-empty services. The draw is exact and uses the recurrence of the Stirling numbers of the second kind,

$$
S(n, k) = k\,S(n-1, k) + S(n-1, k-1),
$$

where $S(n, k)$ counts the partitions of $n$ classes into $k$ non-empty groups. The random partition is the lower bound of the comparison. There is one partition per accepted run; its seed is derived from the master seed, the application, the profile, the variant and the run with SHA-256 (Secure Hash Algorithm), and is recorded next to the result.

## HDBSCAN

HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) is computed once for each distance, with a minimum cluster size of 2; each class labelled as noise becomes a service of its own. It chooses its own number of clusters, stays outside the pairing by *K* and appears as a descriptive reference. It does not enter the hypothesis tests.
