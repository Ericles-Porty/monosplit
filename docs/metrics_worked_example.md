# Metrics: worked example

The metric code is checked against this hand calculation (pilot criterion: the scripts
reproduce the values computed by hand). `tests/test_metrics.py` and the self-check in
the pilot report use the same graph and partitions. Check each step by hand before the
pilot runs.

Definitions are in `src/monosplit/metrics.py`. In short, for M services with m_i classes:

- SM = (1/M) Σ_i μ_i / m_i² − (1 / (M(M−1)/2)) Σ_{i≠j} γ_ij / (2 m_i m_j), where μ_i counts
  the distinct directed edges inside service i and γ_ij the distinct directed edges from
  service i to service j (ordered pairs).
- IFN = (1/M) Σ_i ifn_i, where ifn_i counts the classes of service i called by a class of
  another service.
- ICP = calls between services / all calls.
- NED = 1 − n_ne / M, where n_ne counts the services with 5 to 20 classes.

SM counts edges, ICP counts calls: in the graph below, A → B has 3 calls but is one edge.

## Graph

Six classes, A to F; 8 edges, 15 calls.

| Edge | Calls |
|---|---|
| A → B | 3 |
| B → A | 1 |
| A → C | 2 |
| C → D | 1 |
| D → E | 4 |
| E → F | 2 |
| F → D | 1 |
| B → E | 1 |

## Partition P1: S1 = {A, B, C}, S2 = {D, E}, S3 = {F}

M = 3; m = (3, 2, 1).

**SM.** Edges inside each service: μ1 = 3 (A→B, B→A, A→C), μ2 = 1 (D→E), μ3 = 0.

cohesion = (3/9 + 1/4 + 0/1) / 3 = (1/3 + 1/4) / 3 = 7/36

Edges between services: γ12 = 2 (C→D, B→E), γ23 = 1 (E→F), γ32 = 1 (F→D); all others 0.

Σ γ_ij / (2 m_i m_j) = 2/(2·3·2) + 1/(2·2·1) + 1/(2·1·2) = 1/6 + 1/4 + 1/4 = 2/3

coupling = (2/3) / (3·2/2) = 2/9 = 8/36

**SM = 7/36 − 8/36 = −1/36 ≈ −0.0278**

**IFN.** Classes called from another service: D (by C and F), E (by B), F (by E).
ifn = (0, 2, 1). **IFN = 3/3 = 1**

**ICP.** Calls between services: C→D 1 + B→E 1 + E→F 2 + F→D 1 = 5 of 15. **ICP = 1/3 ≈ 0.333**

**NED.** Sizes 3, 2, 1; none has 5 to 20 classes. **NED = 1 − 0/3 = 1**

## Partition P2: S1 = {A, B}, S2 = {C, D, E, F}

M = 2; m = (2, 4).

**SM.** μ1 = 2 (A→B, B→A); μ2 = 4 (C→D, D→E, E→F, F→D).

cohesion = (2/4 + 4/16) / 2 = (1/2 + 1/4) / 2 = 3/8

γ12 = 2 (A→C, B→E); γ21 = 0. Σ γ_ij / (2 m_i m_j) = 2/(2·2·4) = 1/8

coupling = (1/8) / (2·1/2) = 1/8

**SM = 3/8 − 1/8 = 1/4 = 0.25**

**IFN.** Classes called from another service: C (by A), E (by B). ifn = (0, 2). **IFN = 2/2 = 1**

**ICP.** Calls between services: A→C 2 + B→E 1 = 3 of 15. **ICP = 1/5 = 0.2**

**NED.** Sizes 2 and 4. **NED = 1**

## Summary

| Partition | SM | IFN | ICP | NED |
|---|---|---|---|---|
| P1 | −1/36 | 1 | 1/3 | 1 |
| P2 | 1/4 | 1 | 1/5 | 1 |

Additional cases in `tests/test_metrics.py`: SM unchanged when call counts change but
edges do not; ICP weighted by calls; SM = −1 for two singleton services with edges in
both directions; NED = 0.5 for service sizes 5, 20, 21 and 4; SM undefined for one service.
