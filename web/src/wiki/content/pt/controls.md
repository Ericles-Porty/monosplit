# Controles

Os dois controles recebem o mesmo grafo e o *K* de cada execução aceita do modelo de linguagem de grande porte (LLM, *Large Language Model*). O código está em `src/monosplit/controls.py`.

## Agrupamento hierárquico (AH)

O agrupamento hierárquico aglomerativo do scikit-learn recebe uma matriz de distâncias pré-calculada, e o dendrograma é cortado em exatamente *K* grupos. Há duas distâncias entre as classes $a$ e $b$:

- **chamadas:** $d(a, b) = \dfrac{1}{1 + c_{ab} + c_{ba}}$, em que $c_{ab}$ é o número de chamadas de $a$ para $b$; classes sem chamadas entre si ficam à distância 1;
- **vizinhos:** distância de Jaccard entre as vizinhanças fechadas, $d(a, b) = 1 - \dfrac{\lvert N[a] \cap N[b] \rvert}{\lvert N[a] \cup N[b] \rvert}$, em que $N[a]$ contém $a$ e todas as classes que chamam $a$ ou são chamadas por ela.

As ligações são a média, a completa e a simples; a ligação de Ward exige coordenadas euclidianas e não se aplica a uma matriz de distâncias. As duas distâncias e as três ligações formam seis variantes.

**Escolha da variante.** A configuração do experimento fixa o controle AH (`ah_primary`). O experimento final usa `neighbors:complete`, escolhida depois do piloto: foi a variante selecionada no piloto do JPetStore e na maioria dos estudos do piloto. As seis variantes continuam calculadas e relatadas. A configuração também aceita `auto`, a regra fixada antes das execuções do piloto: a variante com a maior mediana de modularidade estrutural (SM, *Structural Modularity*) sobre as execuções aceitas do estudo vira o controle, e um empate fica com a primeira variante da lista. Essa regra foi substituída porque seleciona pela própria variável dependente, nas mesmas execuções, e assim favorece o controle em SM. A escolha usou dados do piloto, e o JPetStore também está no experimento final; por isso ela favorece o AH nessa aplicação, o que entra nas ameaças à validade. A página [Resultados](#/results) mostra a mediana de SM de cada variante e a usada.

## Partição aleatória

A partição é sorteada de modo uniforme entre todas as partições das classes em exatamente *K* serviços não vazios. O sorteio é exato e usa a recorrência dos números de Stirling de segunda espécie,

$$
S(n, k) = k\,S(n-1, k) + S(n-1, k-1),
$$

em que $S(n, k)$ conta as partições de $n$ classes em $k$ grupos não vazios. A partição aleatória funciona como limite inferior da comparação. Há uma partição por execução aceita; a semente deriva da semente mestre, da aplicação, do perfil, da variante e da execução, por SHA-256 (*Secure Hash Algorithm*), e fica registrada junto ao resultado.

## HDBSCAN

O HDBSCAN (*Hierarchical Density-Based Spatial Clustering of Applications with Noise*) é calculado uma vez para cada distância, com tamanho mínimo de grupo 2; cada classe classificada como ruído vira um serviço próprio. Ele escolhe o próprio número de grupos, fica fora do pareamento por *K* e aparece como referência descritiva. Ele não entra nos testes de hipótese.
