# Resultados do experimento final

Material para o artigo: os resultados do experimento final, com os números da análise
planejada no roteiro. O experimento é `final`, com o perfil `gpt-6.1-sol-high` (OpenAI
`gpt-6.1-sol`, `reasoning_effort` high, temperatura padrão da API), prompt
`decomposition_base` e semente mestra 1793933766, executado em 2026-11-06. Os dados estão no
dump do commit fa56258, e os mesmos números aparecem na página de Resultados (experimento
`final`, perfil `gpt-6.1-sol-high`). As decisões de método estão em
[decisions.md](decisions.md) e os problemas encontrados em [desafios.md](desafios.md).

Convenções:

- d = valor do LLM − valor do controle, na mesma execução e com o mesmo K. SM: maior é melhor.
  IFN, ICP e NED: menor é melhor.
- AH é o agrupamento hierárquico com a variante `neighbors:complete`, fixada na configuração.
  O aleatório é uma partição aleatória com o mesmo K.
- NED = 1 − (serviços com 5 a 20 classes) / K. NED = 1 quer dizer que nenhum serviço tem entre
  5 e 20 classes.
- Células descritivas: mediana [Q1; Q3].
- Testes: Shapiro-Wilk em d; Wilcoxon pareado se a normalidade for rejeitada, t pareado se
  não for; bilaterais, alfa 0,05; Holm sobre as 8 comparações de cada escopo; tamanho de
  efeito pelo delta de Cliff (desprezível < 0,147 ≤ pequeno < 0,33 ≤ médio < 0,474 ≤ grande).
  "n.s." = não significativo após Holm.
- Critério de superioridade, por controle: SM difere a favor do LLM após Holm, Cliff de SM
  pelo menos pequeno, e nenhuma diferença significativa a favor do controle em IFN ou ICP. O
  critério "com NED" exige também que nenhuma diferença significativa favoreça o controle em
  NED (desvio declarado em decisions.md); o critério "roteiro" é o original, sem essa condição.
- A análise principal é a variante com nomes originais e as quatro aplicações juntas (40
  pares por comparação), como no roteiro. A variante ofuscada mede o quanto o resultado
  depende do conhecimento prévio do modelo. Os testes por aplicação (10 pares) são
  complementares.

## Execução

| Aplicação | Classes | Arestas | Variante | Tentativas | Aceitas | K das execuções | Partições distintas | ARI médio | ARI mínimo | Custo (US$) |
|---|---|---|---|---|---|---|---|---|---|---|
| JPetStore | 24 | 40 | original | 10 | 10 | 3 3 3 3 3 3 4 3 3 3 | 2 | 0,93 | 0,63 | 0,10 |
| JPetStore | 24 | 40 | ofuscada | 10 | 10 | 4 3 4 4 4 4 4 4 4 4 | 9 | 0,66 | 0,36 | 0,20 |
| AcmeAir | 52 | 72 | original | 10 | 10 | 4 3 3 4 4 3 3 4 3 3 | 4 | 0,87 | 0,73 | 0,22 |
| AcmeAir | 52 | 72 | ofuscada | 10 | 10 | 8 7 7 5 7 7 7 8 6 6 | 10 | 0,61 | 0,31 | 0,38 |
| Plants | 36 | 62 | original | 10 | 10 | 4 5 4 5 3 5 4 5 5 4 | 7 | 0,72 | 0,42 | 0,20 |
| Plants | 36 | 62 | ofuscada | 10 | 10 | 8 8 9 8 6 8 8 8 8 4 | 5 | 0,83 | 0,47 | 0,30 |
| DayTrader | 108 | 231 | original | 10 | 10 | 4 4 4 4 4 4 4 4 4 4 | 3 | 0,95 | 0,88 | 0,53 |
| DayTrader | 108 | 231 | ofuscada | 10 | 10 | 8 8 8 7 9 7 8 7 7 8 | 10 | 0,61 | 0,32 | 0,71 |

As 80 execuções foram aceitas na primeira tentativa, sem resposta inválida nem erro de API.
O custo total foi de US$ 2,65, e a soma dos tempos de resposta foi de cerca de 65 minutos.

## Respostas às questões de pesquisa

- **QP1 (LLM contra AH):** com as quatro aplicações juntas, o LLM **não** é superior ao AH,
  pelos dois critérios. Com nomes originais, o AH tem SM maior, com diferença significativa e
  efeito grande. O LLM é melhor em ICP e NED, com efeito grande, e não há diferença em IFN.
  Só na JPetStore, a menor aplicação, o LLM é superior ao AH.
- **QP2 (LLM contra aleatório):** com nomes originais, o LLM é superior à partição aleatória,
  pelos dois critérios, nas quatro aplicações juntas e em cada uma delas, com efeito grande em
  SM, IFN e ICP.

## Teste principal: nomes originais, quatro aplicações (40 pares)

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 40 | Wilcoxon | -0,075 | < 0,001 | -0,74 | grande | controle |
| AH | IFN | 40 | Wilcoxon | -0,250 | 1,000 (n.s.) | -0,08 | desprezível | – |
| AH | ICP | 40 | Wilcoxon | -0,050 | < 0,001 | -0,62 | grande | LLM |
| AH | NED | 40 | Wilcoxon | -0,500 | < 0,001 | -0,97 | grande | LLM |
| aleatório | SM | 40 | Wilcoxon | 0,080 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 40 | t pareado | -3,583 | < 0,001 | -0,97 | grande | LLM |
| aleatório | ICP | 40 | t pareado | -0,472 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 40 | Wilcoxon | 0,000 | 1,000 (n.s.) | 0,20 | pequeno | – |

Critério por escopo:

| Escopo | Contra o AH (com NED) | Contra o AH (roteiro) | Contra o aleatório (com NED) | Contra o aleatório (roteiro) |
|---|---|---|---|---|
| Todas | não superior | não superior | superior | superior |
| JPetStore | superior | superior | superior | superior |
| AcmeAir | não superior | não superior | superior | superior |
| Plants | não superior | não superior | superior | superior |
| DayTrader | não superior | não superior | superior | superior |

O AH ganha em SM com partições desequilibradas: seu NED é 1 no AcmeAir e no DayTrader
(nenhum serviço com 5 a 20 classes), contra 0,333 e 0,500 do LLM. É o viés de SM descrito no
desafio 5 de [desafios.md](desafios.md), que motivou o NED no critério. Mesmo com essa
condição, o critério exige vitória em SM, que o LLM não teve.

## Variante com nomes ofuscados (40 pares)

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 40 | Wilcoxon | 0,009 | 0,882 (n.s.) | 0,06 | desprezível | – |
| AH | IFN | 40 | Wilcoxon | -0,625 | < 0,001 | -0,34 | médio | LLM |
| AH | ICP | 40 | Wilcoxon | -0,201 | < 0,001 | -0,88 | grande | LLM |
| AH | NED | 40 | Wilcoxon | -0,500 | < 0,001 | -0,87 | grande | LLM |
| aleatório | SM | 40 | t pareado | 0,138 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 40 | t pareado | -2,292 | < 0,001 | -0,99 | grande | LLM |
| aleatório | ICP | 40 | Wilcoxon | -0,585 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 40 | t pareado | 0,000 | 0,467 (n.s.) | 0,11 | desprezível | – |

Critério por escopo:

| Escopo | Contra o AH (com NED) | Contra o AH (roteiro) | Contra o aleatório (com NED) | Contra o aleatório (roteiro) |
|---|---|---|---|---|
| Todas | não superior | não superior | superior | superior |
| JPetStore | superior | superior | superior | superior |
| AcmeAir | não superior | não superior | superior | superior |
| Plants | não superior | não superior | superior | superior |
| DayTrader | não superior | não superior | não superior | superior |

Sem os nomes, a diferença de SM contra o AH desaparece (efeito desprezível), e o LLM passa a
ser melhor também em IFN. O critério continua "não superior", porque exige vitória em SM. No
DayTrader, o aleatório é melhor em NED, o que tira a superioridade do LLM sobre o aleatório no
critério com NED; pelo critério do roteiro, o LLM continua superior.

## Valores descritivos por aplicação

Nomes originais:

| Aplicação | Método | K | SM | IFN | ICP | NED |
|---|---|---|---|---|---|---|
| JPetStore | LLM | 3 [3; 3] | 0,121 [0,121; 0,121] | 2,000 [2,000; 2,000] | 0,277 [0,277; 0,277] | 0,333 [0,333; 0,333] |
| JPetStore | AH | 3 [3; 3] | 0,075 [0,075; 0,075] | 3,000 [3,000; 3,000] | 0,327 [0,327; 0,327] | 0,667 [0,667; 0,667] |
| JPetStore | Aleatório | 3 [3; 3] | -0,018 [-0,025; -0,001] | 5,333 [5,083; 5,917] | 0,686 [0,623; 0,747] | 0,000 [0,000; 0,312] |
| AcmeAir | LLM | 3 [3; 4] | 0,059 [0,058; 0,063] | 3,000 [2,562; 3,000] | 0,152 [0,150; 0,195] | 0,333 [0,000; 0,333] |
| AcmeAir | AH | 3 [3; 4] | 0,133 [0,133; 0,156] | 1,667 [1,500; 1,667] | 0,191 [0,191; 0,209] | 1,000 [1,000; 1,000] |
| AcmeAir | Aleatório | 3 [3; 4] | -0,005 [-0,013; 0,004] | 8,333 [8,062; 9,417] | 0,709 [0,641; 0,770] | 0,000 [0,000; 0,250] |
| Plants | LLM | 4,50 [4; 5] | 0,106 [0,105; 0,107] | 2,550 [2,425; 2,600] | 0,183 [0,170; 0,189] | 0,200 [0,200; 0,237] |
| Plants | AH | 4,50 [4; 5] | 0,154 [0,135; 0,173] | 2,600 [2,600; 3,250] | 0,407 [0,381; 0,433] | 0,600 [0,500; 0,600] |
| Plants | Aleatório | 4,50 [4; 5] | -0,011 [-0,017; -0,004] | 4,900 [4,600; 5,438] | 0,764 [0,708; 0,821] | 0,000 [0,000; 0,200] |
| DayTrader | LLM | 4 [4; 4] | 0,041 [0,039; 0,041] | 4,250 [4,250; 4,438] | 0,309 [0,309; 0,312] | 0,500 [0,500; 0,500] |
| DayTrader | AH | 4 [4; 4] | 0,121 [0,121; 0,121] | 4,500 [4,500; 4,500] | 0,468 [0,468; 0,468] | 1,000 [1,000; 1,000] |
| DayTrader | Aleatório | 4 [4; 4] | 0,000 [-0,000; 0,000] | 7,875 [7,562; 8,000] | 0,741 [0,643; 0,819] | 1,000 [0,750; 1,000] |

Nomes ofuscados:

| Aplicação | Método | K | SM | IFN | ICP | NED |
|---|---|---|---|---|---|---|
| JPetStore | LLM | 4 [4; 4] | 0,150 [0,148; 0,153] | 2,292 [2,250; 2,500] | 0,233 [0,228; 0,264] | 0,000 [0,000; 0,000] |
| JPetStore | AH | 4 [4; 4] | 0,100 [0,100; 0,100] | 3,500 [3,500; 3,500] | 0,434 [0,434; 0,434] | 0,500 [0,500; 0,500] |
| JPetStore | Aleatório | 4 [4; 4] | -0,015 [-0,022; -0,000] | 4,500 [4,312; 4,875] | 0,752 [0,708; 0,780] | 0,250 [0,062; 0,250] |
| AcmeAir | LLM | 7 [6,25; 7] | 0,115 [0,110; 0,122] | 1,646 [1,571; 1,714] | 0,173 [0,168; 0,185] | 0,134 [0,031; 0,143] |
| AcmeAir | AH | 7 [6,25; 7] | 0,200 [0,199; 0,200] | 1,586 [1,571; 1,667] | 0,300 [0,297; 0,300] | 0,845 [0,808; 0,857] |
| AcmeAir | Aleatório | 7 [6,25; 7] | -0,006 [-0,015; -0,004] | 4,702 [4,446; 5,000] | 0,898 [0,793; 0,917] | 0,143 [0,129; 0,277] |
| Plants | LLM | 8 [8; 8] | 0,116 [0,116; 0,126] | 1,000 [1,000; 1,306] | 0,122 [0,122; 0,139] | 0,625 [0,625; 0,625] |
| Plants | AH | 8 [8; 8] | 0,107 [0,107; 0,119] | 1,625 [1,625; 1,625] | 0,455 [0,455; 0,455] | 0,750 [0,750; 0,750] |
| Plants | Aleatório | 8 [8; 8] | -0,020 [-0,029; -0,010] | 2,812 [2,750; 3,000] | 0,865 [0,813; 0,913] | 0,500 [0,406; 0,542] |
| DayTrader | LLM | 8 [7; 8] | 0,134 [0,123; 0,139] | 2,000 [1,906; 2,143] | 0,365 [0,327; 0,405] | 0,375 [0,344; 0,375] |
| DayTrader | AH | 8 [7; 8] | 0,123 [0,123; 0,139] | 2,500 [2,500; 2,857] | 0,558 [0,558; 0,558] | 0,875 [0,857; 0,875] |
| DayTrader | Aleatório | 8 [7; 8] | -0,002 [-0,004; -0,001] | 4,250 [4,156; 4,714] | 0,872 [0,809; 0,891] | 0,000 [0,000; 0,138] |

## Estabilidade entre execuções

A tabela da seção Execução mostra quantas partições distintas o LLM produziu em 10 execuções
e o ARI entre pares de execuções (1 = mesma partição).

- Com nomes originais, as partições se repetem: de 2 a 4 partições distintas e ARI médio de
  0,87 a 0,95 na JPetStore, no AcmeAir e no DayTrader. O Plants varia mais (7 partições
  distintas, ARI médio de 0,72).
- Com nomes ofuscados, o modelo escolhe cerca do dobro de serviços no AcmeAir, no Plants e no
  DayTrader (K mediano de 7 a 8, contra 3 a 4,5), e as partições variam mais: de 9 a 10 partições
  distintas e ARI médio de 0,61 a 0,66 na JPetStore, no AcmeAir e no DayTrader. O Plants é a
  exceção (5 partições distintas, ARI médio de 0,83).

## Pontos para a discussão

1. O LLM é claramente melhor que o acaso, mas não supera um agrupamento hierárquico simples
   em SM, exceto na menor aplicação. O resultado contra o AH depende de SM ser a métrica
   decisiva: em ICP e NED, o LLM ganha com efeito grande nas duas variantes.
2. Os nomes originais parecem levar o modelo a poucos serviços grandes e estáveis. Sem eles, o
   modelo escolhe mais serviços, empata com o AH em SM e fica mais instável. Isso conversa com
   a hipótese de conhecimento prévio do roteiro, mas K muda entre as variantes e o controle
   acompanha o K do LLM. Por isso, a comparação direta das métricas entre as variantes mistura
   o efeito dos nomes com o efeito de K; a comparação válida é a de cada variante contra o seu
   controle, como nas tabelas acima.
3. Os testes por aplicação têm só 10 pares, e em várias comparações todos os 10 têm o mesmo
   sinal (Cliff de ±1). Os p-valores mínimos ficam limitados pelo tamanho da amostra.
4. O resultado vale para um modelo hospedado e quatro aplicações. A replicação com um modelo
   local foi abandonada (desafio 15 de [desafios.md](desafios.md)).

## Apêndice: testes por aplicação (10 pares)

### JPetStore, nomes originais

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | 0,046 | 0,010 | 1,00 | grande | LLM |
| AH | IFN | 10 | Wilcoxon | -1,000 | 0,010 | -1,00 | grande | LLM |
| AH | ICP | 10 | Wilcoxon | -0,050 | 0,092 (n.s.) | -0,80 | grande | – |
| AH | NED | 10 | Wilcoxon | -0,333 | 0,010 | -1,00 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,138 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -3,333 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,384 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | Wilcoxon | 0,333 | 0,062 (n.s.) | 0,66 | grande | – |

### JPetStore, nomes ofuscados

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | 0,050 | 0,008 | 1,00 | grande | LLM |
| AH | IFN | 10 | Wilcoxon | -1,125 | 0,008 | -1,00 | grande | LLM |
| AH | ICP | 10 | t pareado | -0,186 | < 0,001 | -1,00 | grande | LLM |
| AH | NED | 10 | Wilcoxon | -0,500 | 0,008 | -1,00 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,158 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -2,000 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,500 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | Wilcoxon | -0,125 | 0,062 (n.s.) | -0,54 | grande | – |

### AcmeAir, nomes originais

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | -0,075 | 0,010 | -1,00 | grande | controle |
| AH | IFN | 10 | Wilcoxon | 1,333 | 0,010 | 1,00 | grande | controle |
| AH | ICP | 10 | Wilcoxon | -0,039 | 0,010 | -0,52 | grande | LLM |
| AH | NED | 10 | Wilcoxon | -0,667 | 0,010 | -1,00 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,065 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -5,500 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,557 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | Wilcoxon | 0,000 | 0,250 (n.s.) | 0,30 | pequeno | – |

### AcmeAir, nomes ofuscados

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | t pareado | -0,086 | < 0,001 | -1,00 | grande | controle |
| AH | IFN | 10 | t pareado | 0,000 | 0,592 (n.s.) | 0,13 | desprezível | – |
| AH | ICP | 10 | Wilcoxon | -0,127 | 0,008 | -1,00 | grande | LLM |
| AH | NED | 10 | t pareado | -0,714 | < 0,001 | -1,00 | grande | LLM |
| aleatório | SM | 10 | Wilcoxon | 0,121 | 0,008 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -3,146 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,714 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | t pareado | 0,000 | 0,592 (n.s.) | -0,29 | pequeno | – |

### Plants, nomes originais

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | -0,046 | 0,010 | -1,00 | grande | controle |
| AH | IFN | 10 | Wilcoxon | -0,200 | 0,250 (n.s.) | -0,45 | médio | – |
| AH | ICP | 10 | Wilcoxon | -0,228 | 0,012 | -0,80 | grande | LLM |
| AH | NED | 10 | Wilcoxon | -0,400 | 0,010 | -1,00 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,117 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -2,325 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,575 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | Wilcoxon | 0,000 | 0,250 (n.s.) | 0,52 | grande | – |

### Plants, nomes ofuscados

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | 0,009 | 0,121 (n.s.) | 0,36 | médio | – |
| AH | IFN | 10 | t pareado | -0,625 | 0,002 | -0,75 | grande | LLM |
| AH | ICP | 10 | Wilcoxon | -0,333 | 0,010 | -1,00 | grande | LLM |
| AH | NED | 10 | Wilcoxon | -0,125 | 0,010 | -0,82 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,138 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | Wilcoxon | -1,812 | 0,010 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,739 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | t pareado | 0,125 | 0,121 (n.s.) | 0,39 | médio | – |

### DayTrader, nomes originais

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | -0,080 | 0,010 | -1,00 | grande | controle |
| AH | IFN | 10 | Wilcoxon | -0,250 | 0,016 | -0,70 | grande | LLM |
| AH | ICP | 10 | Wilcoxon | -0,160 | 0,010 | -1,00 | grande | LLM |
| AH | NED | 10 | Wilcoxon | -0,500 | 0,010 | -1,00 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,041 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -3,625 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,432 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | Wilcoxon | -0,500 | 0,010 | -1,00 | grande | LLM |

### DayTrader, nomes ofuscados

| Controle | Métrica | n | Teste | Mediana de d | p (Holm) | Cliff | Efeito | Favorece |
|---|---|---|---|---|---|---|---|---|
| AH | SM | 10 | Wilcoxon | 0,008 | 0,492 (n.s.) | 0,10 | desprezível | – |
| AH | IFN | 10 | t pareado | -0,571 | < 0,001 | -0,96 | grande | LLM |
| AH | ICP | 10 | t pareado | -0,193 | < 0,001 | -1,00 | grande | LLM |
| AH | NED | 10 | Wilcoxon | -0,500 | 0,004 | -1,00 | grande | LLM |
| aleatório | SM | 10 | t pareado | 0,135 | < 0,001 | 1,00 | grande | LLM |
| aleatório | IFN | 10 | t pareado | -2,312 | < 0,001 | -1,00 | grande | LLM |
| aleatório | ICP | 10 | t pareado | -0,491 | < 0,001 | -1,00 | grande | LLM |
| aleatório | NED | 10 | t pareado | 0,354 | < 0,001 | 0,98 | grande | controle |
