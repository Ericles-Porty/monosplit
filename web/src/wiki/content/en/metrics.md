# Metrics

The four metrics follow the definitions collected by Weerasinghe et al. (2026). The module `src/monosplit/metrics.py` computes them with exact fractions, on the static call graph between classes described on the [Call graph](#/wiki?page=graph) page.

Notation, for a partition with $M$ services:

- $m_i$: number of classes of service $i$;
- $\mu_i$: number of distinct directed edges between classes of service $i$;
- $\gamma_{i,j}$: number of distinct directed edges from a class of service $i$ to a class of service $j$, with $i \neq j$.

## Structural modularity (SM)

$$
\mathrm{SM} = \frac{1}{M}\sum_{i=1}^{M}\frac{\mu_i}{m_i^{2}} \;-\; \frac{1}{M(M-1)/2}\sum_{i \neq j}\frac{\gamma_{i,j}}{2\,m_i m_j}
$$

The first term is the mean cohesion of the services, and the second, the mean coupling between pairs of services. The denominators $m_i^2$ and $2\,m_i m_j$ are the largest possible numbers of directed edges inside a service and between two services, so each term is a density and structural modularity (SM) lies in $[-1, 1]$. The sum over $i \neq j$ runs over ordered pairs. SM is undefined for a single service, and the acceptance rule requires $K \geq 2$. Higher is better.

**Deviation from the roteiro.** The roteiro says that the call count is the input of $\mu_i$ and $\gamma_{i,j}$. The code counts distinct edges: with calls, SM exceeds 1 and is no longer comparable with the values in the literature. The decision is in `docs/decisions.md` and goes into the next planning document.

## Interface number (IFN)

$$
\mathrm{IFN} = \frac{1}{M}\sum_{i=1}^{M} \mathit{ifn}_i
$$

$\mathit{ifn}_i$ is the number of classes of service $i$ called by at least one class of another service. On the Decompositions page these classes have a dark ring. For the interface number (IFN), lower is better.

## Inter-partition communication (ICP)

$$
\mathrm{ICP} = \frac{\text{calls between classes of different services}}{\text{all calls in the graph}}
$$

Inter-partition communication (ICP) counts calls, not edges: an edge A → B with 3 calls weighs 3. Lower is better.

## Non-extreme distribution (NED)

$$
\mathrm{NED} = 1 - \frac{n_{\mathrm{ne}}}{M}
$$

$n_{\mathrm{ne}}$ is the number of non-extreme services, that is, services with 5 to 20 classes. For the non-extreme distribution (NED), lower is better. In a small application such as JPetStore, with 24 classes, services with fewer than 5 classes are common. This is why the comparison criterion uses NED only as a difference between methods at the same $K$, not as an absolute value ([Variables and hypotheses](#/wiki?page=variables)).

## Hand-calculated example

The example is also in `docs/metrics_worked_example.md`, and the automated tests and the report of each study check it. The graph has six classes, A to F, 8 edges and 15 calls.

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

**Partition P1:** S1 = {A, B, C}, S2 = {D, E}, S3 = {F}; $M = 3$ and $m = (3, 2, 1)$.

- SM: internal edges $\mu = (3, 1, 0)$, namely A → B, B → A and A → C in S1 and D → E in S2. Cohesion $= (3/9 + 1/4 + 0/1)/3 = 7/36$. Edges between services: $\gamma_{1,2} = 2$ (C → D and B → E), $\gamma_{2,3} = 1$ (E → F) and $\gamma_{3,2} = 1$ (F → D). The densities add up to $2/12 + 1/4 + 1/4 = 2/3$, and the coupling is $(2/3)/3 = 2/9$. Hence $\mathrm{SM} = 7/36 - 8/36 = -1/36 \approx -0.028$.
- IFN: the classes called from another service are D (by C and F), E (by B) and F (by E); $\mathit{ifn} = (0, 2, 1)$ and $\mathrm{IFN} = 3/3 = 1$.
- ICP: C → D (1), B → E (1), E → F (2) and F → D (1) make 5 of the 15 calls; $\mathrm{ICP} = 1/3$.
- NED: the sizes are 3, 2 and 1, none from 5 to 20; $\mathrm{NED} = 1$.

**Partition P2:** S1 = {A, B}, S2 = {C, D, E, F}; $M = 2$ and $m = (2, 4)$.

- SM: $\mu = (2, 4)$; cohesion $= (2/4 + 4/16)/2 = 3/8$. Between services, $\gamma_{1,2} = 2$ (A → C and B → E) and $\gamma_{2,1} = 0$; the coupling is $2/(2 \cdot 2 \cdot 4) = 1/8$. Hence $\mathrm{SM} = 3/8 - 1/8 = 1/4$.
- IFN: C (called by A) and E (called by B); $\mathrm{IFN} = 2/2 = 1$.
- ICP: A → C (2) and B → E (1) make 3 of the 15 calls; $\mathrm{ICP} = 1/5$.
- NED: the sizes are 2 and 4; $\mathrm{NED} = 1$.

| Partition | SM | IFN | ICP | NED |
|---|---|---|---|---|
| P1 | −1/36 | 1 | 1/3 | 1 |
| P2 | 1/4 | 1 | 1/5 | 1 |

P2 has more cohesive services and fewer calls between services, and the metrics record the difference: higher SM and lower ICP. IFN and NED do not tell the two partitions apart on this graph.
