# Acronyms and terms

## Acronyms

| Acronym | Meaning |
|---|---|
| AH | Agglomerative hierarchical clustering, with the dendrogram cut into *K* clusters; a control of the experiment (from the Portuguese *agrupamento hierárquico*) |
| API | Application Programming Interface |
| ARI | Adjusted Rand Index; 1 means two equal partitions |
| GQM | Goal-Question-Metric, the template used to state the goal |
| HDBSCAN | Hierarchical Density-Based Spatial Clustering of Applications with Noise; descriptive reference with its own *K* |
| ICP | Inter-partition Communication |
| IFN | Interface Number |
| JDK | Java Development Kit |
| JSON | JavaScript Object Notation, the format of the answer requested from the model |
| LLM | Large Language Model |
| NED | Non-Extreme Distribution |
| RQ | Research question |
| SM | Structural Modularity |

## Terms

| Term | Meaning |
|---|---|
| *K* | Number of services of a decomposition; the LLM chooses it, and the controls receive the same value |
| Attempt | One call to the model; a run has up to 4 attempts |
| Accepted run | An LLM answer that passed the acceptance rule |
| Failed run | A run with 4 invalid attempts |
| Pair | An accepted LLM run and the control partition with the same *K*, in the same application |
| Variant | Original, with the class names, or obfuscated, with C01, C02 and so on |
| Profile | The configuration that fixes provider, model, parameters and prices, stored in the database |
| Paired difference (*d*) | LLM value minus control value, in the same run |
| Q1, Q3 | First and third quartiles; Q3 − Q1 is the interquartile range |
| Interface class | A class called by at least one class of another service; it counts in IFN |
| Isolated class | A class with no incoming or outgoing calls in the static graph |
| Dry run | A full run of the procedure with the `fake` client, at no cost; its numbers are not data |
