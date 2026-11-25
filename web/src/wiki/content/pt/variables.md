# Variáveis e hipóteses

## Variável independente

O fator manipulado é o método de decomposição, com três níveis: modelo de linguagem de grande porte (LLM, *Large Language Model*) de uso geral, que é o tratamento; agrupamento hierárquico (AH) aglomerativo com corte em *K* grupos, primeiro controle; e partição aleatória com o mesmo *K*, segundo controle.

## Variáveis controladas e bloco

| Papel | Variável | Regra |
|---|---|---|
| Controlada | Número de serviços *K* | O mesmo valor para os três métodos em cada comparação |
| Controlada | Entrada | O mesmo grafo de chamadas para os três métodos |
| Controlada | Configuração do LLM | Modelo, parâmetros da requisição e prompt fixos e registrados em cada tentativa |
| Bloco | Aplicação | JPetStore, AcmeAir, DayTrader e Plants, com *commit* fixado |

## Variáveis dependentes

A variável teórica é a qualidade estrutural da decomposição. Ela é medida por quatro métricas, calculadas sobre o mesmo grafo estático, com os mesmos scripts, para os três métodos. As definições estão na página [Métricas](#/wiki?page=metrics).

| Métrica | O que mede | Direção preferida |
|---|---|---|
| Modularidade estrutural (SM, *Structural Modularity*) | Coesão interna dos serviços menos o acoplamento entre eles | Maior é melhor |
| Número de interfaces (IFN, *Interface Number*) | Número médio de classes de cada serviço chamadas por outro serviço | Menor é melhor |
| Comunicação entre partições (ICP, *Inter-partition Communication*) | Proporção das chamadas que cruzam serviços | Menor é melhor |
| Distribuição não extrema (NED, *Non-Extreme Distribution*) | Fração dos serviços com tamanho extremo, abaixo de 5 ou acima de 20 classes | Menor é melhor |

## Hipóteses teóricas

Cada controle tem o seu par de hipóteses, sempre na mesma aplicação e com o mesmo *K*.

- **H0 (LLM e AH).** Não há diferença de qualidade estrutural entre as decomposições do LLM de uso geral e as do agrupamento hierárquico. A diferença observada é atribuída ao acaso.
- **H1 (LLM e AH).** Há diferença de qualidade estrutural entre as decomposições do LLM de uso geral e as do agrupamento hierárquico.
- **H0 (LLM e aleatória).** Não há diferença de qualidade estrutural entre as decomposições do LLM de uso geral e as da partição aleatória. A diferença observada é atribuída ao acaso.
- **H1 (LLM e aleatória).** Há diferença de qualidade estrutural entre as decomposições do LLM de uso geral e as da partição aleatória.

## Hipóteses operacionais

Cada métrica $M \in \{\mathrm{SM}, \mathrm{IFN}, \mathrm{ICP}, \mathrm{NED}\}$ é testada em separado, para cada controle, porque uma diferença pode aparecer numa métrica e estar ausente em outra. Seja $d_M$ a diferença entre o valor do LLM e o valor do controle na mesma execução. Quando a normalidade das diferenças é rejeitada, a hipótese é sobre a mediana $\tilde{d}_M$:

$$
H_0\colon\ \tilde{d}_M = 0 \qquad H_1\colon\ \tilde{d}_M \neq 0
$$

Quando a normalidade não é rejeitada, a hipótese passa a ser sobre a média $\bar{d}_M$, com o teste *t* pareado. A forma final é fechada na validação dos dados, depois do teste de normalidade. Os testes são bilaterais; a direção entra na leitura do resultado, junto com a direção preferida de cada métrica.

## Critério de comparação

O LLM é considerado superior a um controle quando quatro condições são observadas:

1. diferença estatisticamente significativa em SM a favor do LLM, depois do ajuste de Holm;
2. delta de Cliff ao menos pequeno em SM, isto é, $\lvert \delta \rvert \geq 0{,}147$;
3. ausência de diferença significativa desfavorável ao LLM em IFN e em ICP;
4. ausência de diferença significativa desfavorável ao LLM em NED.

A condição 4 foi acrescentada depois do estudo piloto e altera o roteiro, que deixava o NED fora do critério. O termo de coesão do SM é a densidade de arestas de cada serviço, $\mu_i / m_i^2$, com o mesmo peso para todos os serviços. Em grafos esparsos, isso faz o SM premiar partições com um serviço grande e vários serviços de duas ou três classes, que o NED identifica como extremas. Sem a condição 4, um controle poderia cumprir o critério com uma partição desse tipo. O roteiro deixava o NED de fora porque a faixa de 5 a 20 classes penaliza serviços pequenos em aplicações pequenas; a condição compara os dois métodos na mesma aplicação e com o mesmo $K$, de modo que essa penalidade vale para ambos. A página Resultados mostra o critério adotado e, abaixo dele, o critério do roteiro, só com as condições 1 a 3. A condição 2 trata da magnitude do efeito; a página Resultados mostra o sinal de $\delta$ ao lado dela.

## Variáveis de estado

- A configuração do modelo é fixa e registrada. A temperatura é enviada quando o modelo aceita o parâmetro; quando não aceita, vale o padrão do provedor, e o registro indica que nada foi enviado.
- As execuções são repetidas, para que a variação do modelo seja medida.
- O prompt é escrito antes da execução, conferido antes das execuções e mantido fixo.
- A regra de aceitação da saída iguala o conjunto de classes das três partições.
- A variante com nomes ofuscados separa o efeito do grafo do efeito de o modelo já conhecer a aplicação.
