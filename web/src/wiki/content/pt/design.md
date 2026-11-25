# Desenho experimental

O estudo é um experimento controlado *in vitro*, sem participantes humanos, com um fator de três níveis, bloco por aplicação e pareamento pelo número de serviços *K*.

## Fator e níveis

| Nível | Método | Papel |
|---|---|---|
| 1 | Modelo de linguagem de grande porte (LLM, *Large Language Model*) de uso geral, sem ajuste fino e sem arcabouço especializado, que gera a partição diretamente a partir do grafo | Tratamento |
| 2 | Agrupamento hierárquico (AH) aglomerativo, com o dendrograma cortado em *K* grupos | Controle |
| 3 | Partição aleatória em *K* grupos não vazios, com semente registrada | Controle |

O *K* de cada comparação é o número de serviços que o LLM escolheu naquela execução. Os dois controles são gerados com esse mesmo *K*, a partir do mesmo grafo. Assim, a comparação não depende do número de serviços, que afeta todas as métricas.

O HDBSCAN (*Hierarchical Density-Based Spatial Clustering of Applications with Noise*) escolhe o próprio número de grupos e fica fora do pareamento. Ele entra como referência descritiva, porque foi o método de agrupamento com os resultados agregados mais consistentes no artigo de base.

## Objetos e blocos

As aplicações são JPetStore, AcmeAir, DayTrader e Plants, as mesmas de Weerasinghe et al. (2026), cada uma fixada num *commit*. Cada aplicação é um bloco: as comparações são pareadas dentro da aplicação, e as diferenças entre aplicações não entram no efeito do método.

| Aplicação | Repositório | Situação |
|---|---|---|
| JPetStore | [mybatis/jpetstore-6](https://github.com/mybatis/jpetstore-6), cópia sem alterações em [Ericles-Porty/jpetstore-6](https://github.com/Ericles-Porty/jpetstore-6) | *tag* `monosplit-pin` da cópia, *commit* `ce8015b` da versão `jpetstore-6.3.0` |
| AcmeAir | [acmeair/acmeair](https://github.com/acmeair/acmeair), pelo *fork* [Ericles-Porty/acmeair](https://github.com/Ericles-Porty/acmeair) | código do *commit* `f161227`, com a compilação atualizada no *commit* `95586ab` do *fork*; grafo extraído |
| DayTrader | [WASdev/sample.daytrader7](https://github.com/WASdev/sample.daytrader7), cópia sem alterações em [Ericles-Porty/sample.daytrader7](https://github.com/Ericles-Porty/sample.daytrader7) | *commit* `6df9bab`, o fixado pelo MonoEmbed |
| Plants | [SteeleDesmond/sample.mono-to-ms.pbw-monolith](https://github.com/SteeleDesmond/sample.mono-to-ms.pbw-monolith), *fork* [Ericles-Porty/sample.mono-to-ms.pbw-monolith](https://github.com/Ericles-Porty/sample.mono-to-ms.pbw-monolith) | *commit* `e6f2a6a` (a versão usada pelo MonoEmbed); o *fork* só a compila para Java 8 |

Os repositórios são os citados por Weerasinghe et al. (2026). As aplicações ficam registradas na página Configuração, cada uma com o *commit* fixado. O AcmeAir vem de um *fork* que atualiza só a compilação (Gradle 2.6 para 9.8.2), para que ela rode no JDK (*Java Development Kit*) 21; o código Java é o mesmo do *commit* `f161227`. O monólito é a implantação com MongoDB: o serviço de dados do WebSphere eXtreme Scale fica de fora, porque depende de uma biblioteca da IBM que não está num repositório público.

## Unidade de análise e repetições

A unidade de análise é o par formado por uma execução aceita do LLM e a partição de controle com o mesmo *K*, na mesma aplicação. O plano prevê 10 execuções aceitas por aplicação, isto é, 40 pares por métrica em cada controle. Os pares de uma mesma aplicação não são independentes entre si.

```
Aplicação (bloco)
 └─ execução aceita i do LLM, com K_i serviços
     ├─ par (LLM_i, AH cortado em K_i)
     └─ par (LLM_i, partição aleatória com K_i)
```

## Variante com nomes ofuscados

O tratamento também é aplicado com os nomes das classes trocados por C01, C02 e assim por diante, numa ordem aleatória com semente, sobre as mesmas arestas. A diferença entre as métricas com nomes originais e com nomes ofuscados indica o quanto a decomposição depende de conhecimento prévio do modelo sobre aplicações públicas.
