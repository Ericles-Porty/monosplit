# Análise dos dados

## Diferenças pareadas

Para cada execução aceita do modelo de linguagem de grande porte (LLM, *Large Language Model*), a diferença pareada é

$$
d = \text{valor do LLM} - \text{valor do controle},
$$

com o mesmo *K* e na mesma aplicação. Na modularidade estrutural (SM, *Structural Modularity*), $d > 0$ favorece o LLM. No número de interfaces (IFN, *Interface Number*), na comunicação entre partições (ICP, *Inter-partition Communication*) e na distribuição não extrema (NED, *Non-Extreme Distribution*), $d < 0$ favorece o LLM.

## Análise descritiva

Com a opção de testes de hipótese desligada na configuração do experimento (`inferential = false`), a página [Resultados](#/results) mostra:

- as métricas por método, com um ponto por execução, a mediana e o intervalo do primeiro ao terceiro quartil (Q1 a Q3, quartis com interpolação linear, como no `report.md`);
- as diferenças pareadas, com as contagens de $d$ positivo, negativo e nulo;
- a estabilidade entre execuções: o número de partições distintas e o índice de Rand ajustado (ARI, *Adjusted Rand Index*) entre pares de execuções, em que 1 indica a mesma partição.

Nesse modo, nenhum teste de hipótese é aplicado. Com poucas execuções por variante, o teste principal nem teria como rejeitar a hipótese nula; com cinco, por exemplo, o Wilcoxon bilateral não chega a $p < 0{,}05$, porque o menor valor possível é $2/2^5 = 0{,}0625$. O intervalo interquartil sozinho também pode esconder uma execução diferente das outras; os pontos individuais e o ARI mostram essa variação.

## Experimento completo: testes de hipótese

Com a opção ligada (`inferential = true`), a página Resultados aplica o plano do roteiro aos pares de todas as aplicações e, como referência, aos pares de cada aplicação:

1. teste de Shapiro-Wilk nas diferenças pareadas, com $\alpha = 0{,}05$;
2. normalidade rejeitada: teste de postos sinalizados de Wilcoxon para amostras pareadas, bilateral, com as diferenças nulas descartadas; normalidade não rejeitada: teste *t* pareado, bilateral;
3. ajuste de Holm sobre as oito comparações, quatro métricas e dois controles;
4. tamanho de efeito pelo delta de Cliff entre os valores do LLM ($X$) e os do controle ($Y$);
5. critério de comparação, descrito em [Variáveis e hipóteses](#/wiki?page=variables).

O delta de Cliff é

$$
\delta = P(X > Y) - P(X < Y),
$$

lido pelos limiares de Romano et al. (2006): desprezível para $\lvert \delta \rvert < 0{,}147$, pequeno para $\lvert \delta \rvert < 0{,}33$, médio para $\lvert \delta \rvert < 0{,}474$ e grande a partir desse valor.

No procedimento de Holm, os $m$ valores-p em ordem crescente, $p_{(1)} \leq \dots \leq p_{(m)}$, recebem

$$
\tilde{p}_{(k)} = \max_{j \leq k}\, \min\{1,\ (m - j + 1)\,p_{(j)}\},
$$

e uma comparação é significativa quando $\tilde{p}_{(k)} < \alpha$.

Quando todas as diferenças são iguais, a normalidade não é definida: diferenças todas nulas não têm teste ($p = 1$), e um deslocamento constante diferente de zero vai para o Wilcoxon. O lado favorecido por um teste é o sinal da sua localização, a mediana de $d$ no Wilcoxon e a média de $d$ no teste *t*, lido com a direção preferida da métrica.

O ensaio a seco (configuração `dry_run`) também liga os testes, só para conferir o código com os números do cliente `fake`. Esses números não são dados do experimento.

## Exportação

Cada figura da página Resultados é exportada em SVG (*Scalable Vector Graphics*) e PNG (*Portable Network Graphics*), no tema claro e com 900 pixels de largura, o que dá cerca de 8 pontos de fonte na largura do texto de um artigo. Cada tabela é exportada em CSV (*Comma-Separated Values*), com precisão completa e ponto decimal, e em LaTeX, com booktabs, no idioma da interface.
