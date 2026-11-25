# Visão geral

Esta wiki descreve o experimento controlado *in vitro* que compara decomposições de monólitos Java em microsserviços geradas por um modelo de linguagem de grande porte (LLM, *Large Language Model*) de uso geral com as decomposições do agrupamento hierárquico (AH) e as de uma partição aleatória com o mesmo número de serviços *K*. As páginas acompanham o código do pacote `monosplit` e o roteiro experimental de 31/10/2026.

O experimento final foi executado em 06/11/2026 com o modelo `gpt-6.1-sol` (perfil `gpt-6.1-sol-high`), nas quatro aplicações e nas duas variantes. Os resultados estão na página [Resultados](#/results) (experimento `final`). Estas páginas descrevem o projeto, os instrumentos e as decisões tomadas no caminho; elas não discutem os resultados. O ensaio a seco com o cliente `fake`, que não chama nenhum modelo, só confere os instrumentos: seus números não são dados.

## Objetivo

O objetivo segue o modelo GQM (*Goal-Question-Metric*).

| Elemento | Definição |
|---|---|
| Analisar | decomposições de aplicações monolíticas em microsserviços geradas por um LLM de uso geral |
| com o propósito de | avaliá-las em comparação com o agrupamento hierárquico (AH) e com uma partição aleatória |
| com respeito à | qualidade estrutural, medida por modularidade estrutural (SM, *Structural Modularity*), número de interfaces (IFN, *Interface Number*), comunicação entre partições (ICP, *Inter-partition Communication*) e distribuição não extrema (NED, *Non-Extreme Distribution*) |
| do ponto de vista do | arquiteto de software responsável pela migração |
| no contexto de | quatro aplicações Java de código aberto usadas como referência na literatura, em experimento *in vitro* |

## Questões de pesquisa

- **QP1.** Decomposições geradas por um LLM de uso geral têm qualidade estrutural superior à do agrupamento hierárquico?
- **QP2.** Decomposições geradas por um LLM de uso geral têm qualidade estrutural superior à de uma partição aleatória com o mesmo número de serviços?

## Fluxo do experimento

```
Monólito Java, fixado num commit
   │  compilação e leitura do bytecode (javap)
   ▼
Grafo estático de chamadas entre classes
   │
   ├──────────────────────┬────────────────────────┐
   ▼                      ▼                        ▼
LLM (escolhe K)     AH cortado em K        Partição aleatória com K
   │                      │                        │
   └──────────────────────┴────────────────────────┘
   │  mesmo grafo, mesmos scripts
   ▼
SM, IFN, ICP e NED de cada partição
   │
   ▼
Diferenças pareadas LLM − controle  →  análise estatística
```

O artigo de base é Weerasinghe et al. (2026), que comparou nove abordagens de decomposição nas mesmas quatro aplicações e com as mesmas métricas, sem teste de hipótese nem relato da variação entre execuções.

## Páginas

- [Desenho experimental](#/wiki?page=design): fator, níveis, blocos, pareamento por *K* e unidade de análise.
- [Variáveis e hipóteses](#/wiki?page=variables): variáveis independentes e dependentes, hipóteses e critério de comparação.
- [Métricas](#/wiki?page=metrics): definições e exemplo calculado à mão.
- [Grafo de chamadas](#/wiki?page=graph): extração do bytecode e regras de contagem.
- [Tratamento: o LLM](#/wiki?page=treatment): prompt, regra de aceitação e repetições.
- [Controles](#/wiki?page=controls): AH, partição aleatória e HDBSCAN.
- [Análise dos dados](#/wiki?page=analysis): análise descritiva e testes de hipótese.
- [Uso da ferramenta](#/wiki?page=tool): páginas da interface, comandos e reprodutibilidade.
- [Siglas e termos](#/wiki?page=glossary)
