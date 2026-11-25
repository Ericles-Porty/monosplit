# Data analysis

## Paired differences

For each accepted run of the large language model (LLM), the paired difference is

$$
d = \text{LLM value} - \text{control value},
$$

with the same *K* and in the same application. For structural modularity (SM), $d > 0$ favours the LLM. For interface number (IFN), inter-partition communication (ICP) and non-extreme distribution (NED), $d < 0$ favours the LLM.

## Descriptive analysis

With the hypothesis tests turned off in the experiment configuration (`inferential = false`), the [Results](#/results) page shows:

- the metrics by method, with one dot per run, the median and the range from the first to the third quartile (Q1 to Q3, quartiles with linear interpolation, as in `report.md`);
- the paired differences, with the counts of positive, negative and zero $d$;
- run-to-run stability: the number of distinct partitions and the adjusted Rand index (ARI) between pairs of runs, where 1 means the same partition.

In this mode no hypothesis test is applied. With few runs per variant, the main test could not reject the null hypothesis anyway; with five, for example, the two-sided Wilcoxon test cannot reach $p < 0.05$, because the smallest possible value is $2/2^5 = 0.0625$. The interquartile range alone can also hide a run that differs from the others; the individual dots and the ARI show that variation.

## Full experiment: hypothesis tests

With them turned on (`inferential = true`), the Results page applies the plan of the roteiro to the pairs of all applications pooled and, for reference, to the pairs of each application:

1. Shapiro-Wilk test on the paired differences, with $\alpha = 0.05$;
2. normality rejected: Wilcoxon signed-rank test for paired samples, two-sided, with zero differences dropped; normality not rejected: paired *t* test, two-sided;
3. Holm adjustment over the eight comparisons, four metrics and two controls;
4. effect size by Cliff's delta between the LLM values ($X$) and the control values ($Y$);
5. the comparison criterion, described in [Variables and hypotheses](#/wiki?page=variables).

Cliff's delta is

$$
\delta = P(X > Y) - P(X < Y),
$$

read with the thresholds of Romano et al. (2006): negligible for $\lvert \delta \rvert < 0.147$, small for $\lvert \delta \rvert < 0.33$, medium for $\lvert \delta \rvert < 0.474$ and large from that value on.

In the Holm procedure, the $m$ p-values in increasing order, $p_{(1)} \leq \dots \leq p_{(m)}$, become

$$
\tilde{p}_{(k)} = \max_{j \leq k}\, \min\{1,\ (m - j + 1)\,p_{(j)}\},
$$

and a comparison is significant when $\tilde{p}_{(k)} < \alpha$.

When every difference is equal, normality is undefined: differences that are all zero have no test ($p = 1$), and a constant non-zero shift goes to Wilcoxon. The side favoured by a test is the sign of its location, the median of $d$ for Wilcoxon and the mean of $d$ for the *t* test, read with the metric's preferred direction.

The dry run (configuration `dry_run`) also turns the tests on, only to check the code with the numbers of the `fake` client. Those numbers are not experimental data.

## Export

Every figure of the Results page exports to SVG (Scalable Vector Graphics) and PNG (Portable Network Graphics), in the light theme and 900 pixels wide, which gives about 8-point text at the text width of an article. Every table exports to CSV (Comma-Separated Values), with full precision and a decimal point, and to LaTeX, with booktabs, in the interface language.
