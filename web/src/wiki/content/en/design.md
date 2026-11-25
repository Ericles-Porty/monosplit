# Experimental design

The study is a controlled *in vitro* experiment, without human participants, with one factor at three levels, blocking by application and pairing by the number of services *K*.

## Factor and levels

| Level | Method | Role |
|---|---|---|
| 1 | General-purpose large language model (LLM), without fine-tuning or a specialised framework, which generates the partition directly from the graph | Treatment |
| 2 | Agglomerative hierarchical clustering (AH), with the dendrogram cut into *K* clusters | Control |
| 3 | Random partition into *K* non-empty groups, with a recorded seed | Control |

The *K* of each comparison is the number of services the LLM chose in that run. Both controls are generated with the same *K*, from the same graph. The comparison therefore does not depend on the number of services, which affects every metric.

HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) chooses its own number of clusters and stays outside the pairing. It is a descriptive reference, because it was the clustering method with the most consistent aggregate results in the baseline article.

## Objects and blocks

The applications are JPetStore, AcmeAir, DayTrader and Plants, the same as in Weerasinghe et al. (2026), each pinned to a commit. Each application is a block: comparisons are paired within the application, and differences between applications do not enter the effect of the method.

| Application | Repository | Status |
|---|---|---|
| JPetStore | [mybatis/jpetstore-6](https://github.com/mybatis/jpetstore-6), unchanged copy in [Ericles-Porty/jpetstore-6](https://github.com/Ericles-Porty/jpetstore-6) | tag `monosplit-pin` of the copy, commit `ce8015b` of the release `jpetstore-6.3.0` |
| AcmeAir | [acmeair/acmeair](https://github.com/acmeair/acmeair), through the fork [Ericles-Porty/acmeair](https://github.com/Ericles-Porty/acmeair) | code of commit `f161227`, with the build updated in commit `95586ab` of the fork; graph extracted |
| DayTrader | [WASdev/sample.daytrader7](https://github.com/WASdev/sample.daytrader7), unchanged copy in [Ericles-Porty/sample.daytrader7](https://github.com/Ericles-Porty/sample.daytrader7) | commit `6df9bab`, the one pinned by MonoEmbed |
| Plants | [SteeleDesmond/sample.mono-to-ms.pbw-monolith](https://github.com/SteeleDesmond/sample.mono-to-ms.pbw-monolith), fork [Ericles-Porty/sample.mono-to-ms.pbw-monolith](https://github.com/Ericles-Porty/sample.mono-to-ms.pbw-monolith) | commit `e6f2a6a` (the version used by MonoEmbed); the fork only compiles it for Java 8 |

The repositories are those cited by Weerasinghe et al. (2026). The applications are registered on the Configuration page, each with its pinned commit. AcmeAir comes from a fork that updates only its build (Gradle 2.6 to 9.8.2), so that it runs on JDK (Java Development Kit) 21; the Java code is that of commit `f161227`. The monolith is the MongoDB deployment: the WebSphere eXtreme Scale data service is left out, because it depends on an IBM library that is not in a public repository.

## Unit of analysis and replication

The unit of analysis is the pair formed by an accepted LLM run and the control partition with the same *K*, in the same application. The plan has 10 accepted runs per application, that is, 40 pairs per metric for each control. Pairs from the same application are not independent of each other.

```
Application (block)
 └─ accepted LLM run i, with K_i services
     ├─ pair (LLM_i, AH cut at K_i)
     └─ pair (LLM_i, random partition with K_i)
```

## Variant with obfuscated names

The treatment is also applied with the class names replaced by C01, C02 and so on, in a seeded random order, over the same edges. The difference between the metrics with original and with obfuscated names indicates how much the decomposition depends on the model's prior knowledge of public applications.
