# Métricas

As quatro métricas seguem as definições reunidas por Weerasinghe et al. (2026). O módulo `src/monosplit/metrics.py` as calcula com frações exatas, sobre o grafo estático de chamadas entre classes descrito na página [Grafo de chamadas](#/wiki?page=graph).

Notação, para uma partição com $M$ serviços:

- $m_i$: número de classes do serviço $i$;
- $\mu_i$: número de arestas dirigidas distintas entre classes do serviço $i$;
- $\gamma_{i,j}$: número de arestas dirigidas distintas de uma classe do serviço $i$ para uma classe do serviço $j$, com $i \neq j$.

## Modularidade estrutural (SM)

$$
\mathrm{SM} = \frac{1}{M}\sum_{i=1}^{M}\frac{\mu_i}{m_i^{2}} \;-\; \frac{1}{M(M-1)/2}\sum_{i \neq j}\frac{\gamma_{i,j}}{2\,m_i m_j}
$$

O primeiro termo é a coesão média dos serviços, e o segundo, o acoplamento médio entre pares de serviços. Os denominadores $m_i^2$ e $2\,m_i m_j$ são os maiores números possíveis de arestas dirigidas dentro de um serviço e entre dois serviços; por isso cada termo é uma densidade, e a modularidade estrutural (SM, *Structural Modularity*) fica em $[-1, 1]$. A soma em $i \neq j$ percorre pares ordenados. A SM não é definida para um único serviço, e a regra de aceitação exige $K \geq 2$. Maior é melhor.

**Desvio em relação ao roteiro.** O roteiro diz que a contagem de chamadas é a entrada de $\mu_i$ e $\gamma_{i,j}$. O código conta arestas distintas: com chamadas, a SM ultrapassa 1 e deixa de ser comparável com os valores da literatura. A decisão está em `docs/decisions.md` e entra no próximo documento de planejamento.

## Número de interfaces (IFN)

$$
\mathrm{IFN} = \frac{1}{M}\sum_{i=1}^{M} \mathit{ifn}_i
$$

$\mathit{ifn}_i$ é o número de classes do serviço $i$ chamadas por pelo menos uma classe de outro serviço. Na página Decomposições, essas classes aparecem com um anel escuro. Para o número de interfaces (IFN, *Interface Number*), menor é melhor.

## Comunicação entre partições (ICP)

$$
\mathrm{ICP} = \frac{\text{chamadas entre classes de serviços diferentes}}{\text{total de chamadas do grafo}}
$$

A comunicação entre partições (ICP, *Inter-partition Communication*) conta chamadas, e não arestas: uma aresta A → B com 3 chamadas pesa 3. Menor é melhor.

## Distribuição não extrema (NED)

$$
\mathrm{NED} = 1 - \frac{n_{\mathrm{ne}}}{M}
$$

$n_{\mathrm{ne}}$ é o número de serviços não extremos, isto é, com 5 a 20 classes. Para a distribuição não extrema (NED, *Non-Extreme Distribution*), menor é melhor. Numa aplicação pequena, como o JPetStore com 24 classes, serviços com menos de 5 classes são comuns. Por isso o critério de comparação usa o NED só como diferença entre métodos no mesmo $K$, e não como valor absoluto (página [Variáveis e hipóteses](#/wiki?page=variables)).

## Exemplo calculado à mão

O exemplo também está em `docs/metrics_worked_example.md` e é conferido pelos testes automatizados e pelo relatório de cada estudo. O grafo tem seis classes, de A a F, 8 arestas e 15 chamadas.

| Aresta | Chamadas |
|---|---|
| A → B | 3 |
| B → A | 1 |
| A → C | 2 |
| C → D | 1 |
| D → E | 4 |
| E → F | 2 |
| F → D | 1 |
| B → E | 1 |

**Partição P1:** S1 = {A, B, C}, S2 = {D, E}, S3 = {F}; $M = 3$ e $m = (3, 2, 1)$.

- SM: arestas internas $\mu = (3, 1, 0)$, que são A → B, B → A e A → C em S1 e D → E em S2. Coesão $= (3/9 + 1/4 + 0/1)/3 = 7/36$. Arestas entre serviços: $\gamma_{1,2} = 2$ (C → D e B → E), $\gamma_{2,3} = 1$ (E → F) e $\gamma_{3,2} = 1$ (F → D). A soma das densidades é $2/12 + 1/4 + 1/4 = 2/3$, e o acoplamento, $(2/3)/3 = 2/9$. Logo, $\mathrm{SM} = 7/36 - 8/36 = -1/36 \approx -0{,}028$.
- IFN: são chamadas de outro serviço as classes D (por C e F), E (por B) e F (por E); $\mathit{ifn} = (0, 2, 1)$ e $\mathrm{IFN} = 3/3 = 1$.
- ICP: C → D (1), B → E (1), E → F (2) e F → D (1) somam 5 das 15 chamadas; $\mathrm{ICP} = 1/3$.
- NED: os tamanhos são 3, 2 e 1, nenhum entre 5 e 20; $\mathrm{NED} = 1$.

**Partição P2:** S1 = {A, B}, S2 = {C, D, E, F}; $M = 2$ e $m = (2, 4)$.

- SM: $\mu = (2, 4)$; coesão $= (2/4 + 4/16)/2 = 3/8$. Entre serviços, $\gamma_{1,2} = 2$ (A → C e B → E) e $\gamma_{2,1} = 0$; o acoplamento é $2/(2 \cdot 2 \cdot 4) = 1/8$. Logo, $\mathrm{SM} = 3/8 - 1/8 = 1/4$.
- IFN: C (chamada por A) e E (chamada por B); $\mathrm{IFN} = 2/2 = 1$.
- ICP: A → C (2) e B → E (1) somam 3 das 15 chamadas; $\mathrm{ICP} = 1/5$.
- NED: os tamanhos são 2 e 4; $\mathrm{NED} = 1$.

| Partição | SM | IFN | ICP | NED |
|---|---|---|---|---|
| P1 | −1/36 | 1 | 1/3 | 1 |
| P2 | 1/4 | 1 | 1/5 | 1 |

P2 tem serviços mais coesos e menos chamadas entre serviços, e as métricas registram a diferença: SM maior e ICP menor. IFN e NED não distinguem as duas partições neste grafo.
