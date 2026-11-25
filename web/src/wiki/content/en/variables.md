# Variables and hypotheses

## Independent variable

The manipulated factor is the decomposition method, at three levels: a general-purpose large language model (LLM), the treatment; agglomerative hierarchical clustering (AH) cut into *K* clusters, the first control; and a random partition with the same *K*, the second control.

## Controlled variables and block

| Role | Variable | Rule |
|---|---|---|
| Controlled | Number of services *K* | The same value for the three methods in each comparison |
| Controlled | Input | The same call graph for the three methods |
| Controlled | LLM configuration | Model, request parameters and prompt fixed and recorded with every attempt |
| Block | Application | JPetStore, AcmeAir, DayTrader and Plants, pinned to a commit |

## Dependent variables

The theoretical variable is the structural quality of the decomposition. It is measured by four metrics, computed on the same static graph, with the same scripts, for the three methods. The definitions are on the [Metrics](#/wiki?page=metrics) page.

| Metric | What it measures | Preferred direction |
|---|---|---|
| Structural modularity (SM) | Cohesion inside the services minus coupling between them | Higher is better |
| Interface number (IFN) | Mean number of classes of each service called from another service | Lower is better |
| Inter-partition communication (ICP) | Share of the calls that cross services | Lower is better |
| Non-extreme distribution (NED) | Share of the services with an extreme size, below 5 or above 20 classes | Lower is better |

## Theoretical hypotheses

Each control has its pair of hypotheses, always in the same application and with the same *K*.

- **H0 (LLM and AH).** There is no difference in structural quality between the decompositions of the general-purpose LLM and those of hierarchical clustering. The observed difference is attributed to chance.
- **H1 (LLM and AH).** There is a difference in structural quality between the decompositions of the general-purpose LLM and those of hierarchical clustering.
- **H0 (LLM and random).** There is no difference in structural quality between the decompositions of the general-purpose LLM and those of the random partition. The observed difference is attributed to chance.
- **H1 (LLM and random).** There is a difference in structural quality between the decompositions of the general-purpose LLM and those of the random partition.

## Operational hypotheses

Each metric $M \in \{\mathrm{SM}, \mathrm{IFN}, \mathrm{ICP}, \mathrm{NED}\}$ is tested separately for each control, because a difference may appear in one metric and not in another. Let $d_M$ be the difference between the LLM value and the control value in the same run. When normality of the differences is rejected, the hypothesis is about the median $\tilde{d}_M$:

$$
H_0\colon\ \tilde{d}_M = 0 \qquad H_1\colon\ \tilde{d}_M \neq 0
$$

When normality is not rejected, the hypothesis is about the mean $\bar{d}_M$, with the paired *t* test. The final form is fixed in data validation, after the normality test. The tests are two-sided; the direction enters the reading of the result, together with the preferred direction of each metric.

## Comparison criterion

The LLM is considered superior to a control when four conditions hold:

1. a statistically significant difference in SM in favour of the LLM, after the Holm adjustment;
2. Cliff's delta in SM at least small, that is, $\lvert \delta \rvert \geq 0.147$;
3. no significant difference unfavourable to the LLM in IFN or in ICP;
4. no significant difference unfavourable to the LLM in NED.

Condition 4 was added after the pilot study and changes the roteiro, which left NED outside the criterion. The cohesion term of SM is the edge density of each service, $\mu_i / m_i^2$, with the same weight for every service. In sparse graphs this makes SM reward partitions with one large service and several services of two or three classes, which NED flags as extreme. Without condition 4, a control could meet the criterion with such a partition. The roteiro left NED out because the range of 5 to 20 classes penalises small services in small applications; the condition compares both methods on the same application and with the same $K$, so that penalty applies to both. The Results page shows the adopted criterion and, below it, the roteiro's criterion, with conditions 1 to 3 only. Condition 2 is about the magnitude of the effect; the Results page shows the sign of $\delta$ beside it.

## State variables

- The model configuration is fixed and recorded. The temperature is sent when the model accepts the parameter; otherwise the provider's default applies, and the record says that nothing was sent.
- Runs are repeated, so that the model's variation is measured.
- The prompt is written before the runs, checked before the runs and kept fixed.
- The acceptance rule makes the set of classes equal in the three partitions.
- The variant with obfuscated names separates the effect of the graph from the effect of the model already knowing the application.
