# Siglas e termos

## Siglas

| Sigla | Significado |
|---|---|
| AH | Agrupamento hierárquico aglomerativo, com o dendrograma cortado em *K* grupos; controle do experimento |
| API | Interface de programação de aplicações (*Application Programming Interface*) |
| ARI | Índice de Rand ajustado (*Adjusted Rand Index*); 1 indica duas partições iguais |
| GQM | *Goal-Question-Metric*, modelo usado para formular o objetivo |
| HDBSCAN | *Hierarchical Density-Based Spatial Clustering of Applications with Noise*; referência descritiva, com *K* próprio |
| ICP | Comunicação entre partições (*Inter-partition Communication*) |
| IFN | Número de interfaces (*Interface Number*) |
| JDK | *Java Development Kit* |
| JSON | *JavaScript Object Notation*, o formato da resposta pedida ao modelo |
| LLM | Modelo de linguagem de grande porte (*Large Language Model*) |
| NED | Distribuição não extrema (*Non-Extreme Distribution*) |
| QP | Questão de pesquisa |
| SM | Modularidade estrutural (*Structural Modularity*) |

## Termos

| Termo | Significado |
|---|---|
| *K* | Número de serviços de uma decomposição; o LLM escolhe, e os controles recebem o mesmo valor |
| Tentativa | Uma chamada ao modelo; uma execução tem até 4 tentativas |
| Execução aceita | Resposta do LLM que passou na regra de aceitação |
| Execução falha | Execução com 4 tentativas inválidas |
| Par | Execução aceita do LLM e partição de controle com o mesmo *K*, na mesma aplicação |
| Variante | Original, com os nomes das classes, ou ofuscada, com C01, C02 e assim por diante |
| Perfil | Configuração que fixa provedor, modelo, parâmetros e preços, guardada no banco de dados |
| Diferença pareada (*d*) | Valor do LLM menos valor do controle, na mesma execução |
| Q1, Q3 | Primeiro e terceiro quartis; Q3 − Q1 é o intervalo interquartil |
| Classe de interface | Classe chamada por pelo menos uma classe de outro serviço; entra na IFN |
| Classe isolada | Classe sem chamadas de entrada ou de saída no grafo estático |
| Ensaio a seco | Execução completa do procedimento com o cliente `fake`, sem custo; os números não são dados |
