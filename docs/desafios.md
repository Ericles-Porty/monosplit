# Desafios encontrados

Material para o artigo final: os problemas que apareceram ao construir os instrumentos e nos
pilotos, o que foi medido, o que foi feito e o que cada um implica para o artigo. Os detalhes e
as decisões completas estão em [decisions.md](decisions.md). Os itens marcados como **Desvio**
mudam uma frase do roteiro e devem ser declarados no artigo. Os números dos pilotos são
descritivos: não são resultados do experimento. Os dados dos pilotos estão no dump do
commit ff068b7; o banco foi limpo depois para o experimento final. Os *hashes* de commit
citados aqui são do repositório de desenvolvimento, que é privado; este pacote começa de uma
cópia dele.

Acrescente aqui os desafios que surgirem nas execuções do experimento completo. A replicação
com modelos locais foi abandonada (item 15).

## Objetos experimentais

### 1. As versões das aplicações não são as mesmas na literatura

- **O que aconteceu.** Cada aplicação tem mais de uma versão em uso, e os artigos contam
  números diferentes de classes. A JPetStore 6.4.0 trocou a camada web (Stripes por Spring MVC)
  e tem 25 classes; as tags 6.0.2 a 6.3.0 têm as 24 classes decompostas na literatura
  (Su et al., 2026). A AcmeAir do MonoEmbed (acmeair/acmeair) tem 86 classes, sem regra de
  contagem declarada; Su et al. (2026) usam outra base de código (blueperf/acmeair-monolithic-java,
  32 classes). A Plants usada pelo MonoEmbed é uma variante simplificada, sem componentes Java EE.
- **O que foi feito.** Cada aplicação foi fixada num commit citado pela literatura (JPetStore
  6.3.0; AcmeAir, DayTrader e Plants nos commits do MonoEmbed, cujo pacote foi executado por
  Weerasinghe et al., 2026). As quatro têm uma cópia (fork) com a tag `monosplit-pin` no commit
  fixado, para que um repositório removido ou reescrito não impeça a replicação.
- **Para o artigo.** Declarar commit e número de classes de cada aplicação. A comparação com
  valores publicados só vale para a mesma versão e a mesma regra de contagem (validade externa).

### 2. Builds antigos não compilam com as ferramentas atuais

- **O que aconteceu.** O build original da AcmeAir usa Gradle 2.6, que só roda no JDK 8 ou
  anterior; o Gradle atual rejeita o script. O pom raiz da Plants compila para Java 6, que o
  JDK 21 recusa. O pom pai da JPetStore traz plugins que reescrevem o código-fonte (formatação,
  ordem de imports, cabeçalhos de licença, OpenRewrite). O serviço WebSphere eXtreme Scale da
  AcmeAir (17 classes) depende de um cliente da IBM (objectgrid 8.6.0.2) que não está em
  repositório público.
- **O que foi feito.** Os forks mudam só o build (AcmeAir: Gradle 9.8.2 com `--release 8`;
  Plants: `source`/`target` 1.8), e o diff dos arquivos `.java` em relação ao original é vazio.
  Na JPetStore, os plugins que reescrevem código foram desligados, e a ferramenta falha se o
  build alterar um arquivo versionado. O monólito da AcmeAir é a implantação MongoDB do build
  original, sem o serviço WXS.
- **Para o artigo.** **Desvio:** AcmeAir sem o serviço WXS; Plants compilada para Java 8 em vez
  de Java 6, sem efeito no grafo de chamadas. Reproduzir um estudo sobre essas aplicações exige
  manter a toolchain, o que conta para o pacote de replicação.

### 3. O grafo estático não vê as chamadas feitas pelo framework

- **O que aconteceu.** O extrator lê o bytecode compilado (`javap`), em que o compilador já
  resolveu o tipo estático de cada chamada. Chamadas feitas em tempo de execução pelo framework
  (Stripes, mapeadores XML do MyBatis, expressões em JSP, injeção por anotação) não são chamadas
  estáticas entre classes. Daí as classes isoladas: 1 na JPetStore (`Category`, usada só pelas
  JSPs), 6 na AcmeAir (interfaces de constantes que o javac incorpora, classes encontradas pelo
  contêiner por anotação), 17 na DayTrader e 3 na Plants.
- **O que foi feito.** As classes isoladas ficam no grafo e todo método precisa atribuí-las a
  um serviço. Uma amostra de arestas é conferida à mão no código-fonte.
- **Para o artigo.** O grafo subestima o acoplamento real, e as métricas medem a partição
  contra esse grafo, não contra o comportamento em execução (validade de construto).

## Métricas e controles

### 4. SM com contagem de chamadas sai do intervalo da literatura

- **O que aconteceu.** O roteiro usa a contagem de chamadas como entrada de μ_i e γ_ij. Os
  denominadores de SM (m_i² e 2·m_i·m_j) são o número máximo de arestas dirigidas, então cada
  termo é uma densidade de arestas; com contagem de chamadas, SM passa de 1 e deixa de ser
  comparável com os valores publicados.
- **O que foi feito.** SM conta arestas distintas; ICP continua com a contagem de chamadas.
- **Para o artigo.** **Desvio** a declarar, com a justificativa.

### 5. SM favorece partições desequilibradas em grafos esparsos

- **O que aconteceu.** O termo de coesão de SM é a densidade μ_i/m_i², com peso igual por
  serviço. Em grafos esparsos, isso premia um serviço grande e vários serviços de duas ou três
  classes. Uma busca local nos grafos do piloto, no K usual do LLM, achou SM de 0,21 a 0,25 com
  partições assim (NED de 0,75 a 1,00) e de 0,12 a 0,17 quando cada serviço tem de 5 a 20
  classes. O controle AH produziu partições desse tipo (AcmeAir: 38 a 45 das 52 classes num
  serviço, NED 1,00).
- **O que foi feito.** NED entrou no critério de comparação: o LLM só é superior se, além das
  três condições do roteiro, não houver diferença significativa desfavorável a ele em NED. Os
  resultados trazem os dois critérios lado a lado. A condição vale para os dois controles,
  embora a partição aleatória com o mesmo K espalhe as classes por igual e tenha NED baixo
  (no piloto da Plants, isso deu NED desfavorável ao LLM contra a partição aleatória).
- **Para o artigo.** **Desvio** a declarar. Discutir a escolha da métrica principal e o efeito
  do equilíbrio de tamanhos da partição aleatória na condição de NED (validade de construto).

### 6. A regra de escolha do controle AH escolhia pela variável dependente

- **O que aconteceu.** A regra fixada antes das execuções escolhia a variante de AH de maior
  SM mediano nas execuções aceitas. Aplicada por estudo (`auto`), ela seleciona pela própria
  variável dependente e favorece o controle em SM; num estudo do piloto (Plants, gpt-5.6-sol)
  escolheu outra variante.
- **O que foi feito.** O controle AH do experimento completo foi fixado em
  `neighbors:complete`, a variante escolhida no piloto da JPetStore e na maioria dos estudos do
  piloto. As seis variantes continuam medidas e relatadas.
- **Para o artigo.** A escolha usou dados do piloto, e a JPetStore também está no experimento
  completo: esse ajuste favorece o AH nela (validade interna).

## Tratamento: os modelos hospedados

### 7. A temperatura nem sempre pode ser fixada

- **O que aconteceu.** O roteiro fixa uma temperatura acima de zero. A versão da API da
  Anthropic usada pelo SDK (2026-10-21) rejeita `temperature`, `top_p` e `top_k` em todos os
  modelos, e modelos de raciocínio de outros provedores aceitam só o valor padrão.
- **O que foi feito.** Vale o padrão do provedor quando o modelo não aceita outro valor; o
  valor enviado, ou "não enviado", fica registrado em cada execução.
- **Para o artigo.** Relatar a temperatura efetiva de cada modelo, não a planejada.

### 8. O modelo escolhido não tem versão datada

- **O que aconteceu.** O modelo do experimento completo (gpt-6.1-sol, raciocínio high) não tem
  nome de snapshot datado: o provedor pode mudar o modelo por trás do mesmo nome.
- **O que foi feito.** Cada tentativa registra o modelo informado pela API e a data; não há
  troca automática de modelo.
- **Para o artigo.** Uma replicação futura pode não ter acesso ao mesmo modelo (confiabilidade
  e validade externa). Declarar as datas das execuções.

## Tratamento: os modelos locais (replicação com pesos abertos)

Servidor Ollama 0.40.15 na máquina do estudo: GPU RTX 4050 Laptop com 6 GB, Ryzen 7 7735HS,
31 GB de RAM, Windows 11. Modelos testados: gpt-oss:20b (MoE com 20,9 bilhões de parâmetros,
MXFP4) e qwen3.5:4b (4,2 bilhões, Q4_K_M).

### 9. O servidor corta o prompt sem avisar

- **O que aconteceu.** O endpoint compatível com a API da OpenAI não permite fixar a janela de
  contexto por requisição, e o padrão do servidor depende da memória da GPU (4.096 tokens nesta
  máquina). Num teste com contexto de 2.048 tokens, o prompt do DayTrader (10.141 tokens) foi
  cortado para 1.026, e o modelo respondeu mesmo assim, com HTTP 200 e o início de um objeto
  JSON.
- **O que foi feito.** A ferramenta usa a API nativa do Ollama, com a janela de contexto fixada
  no perfil (49.152 tokens) e o corte desligado: o servidor recusa um prompt que não cabe. A
  ferramenta também confere, em cada resposta, que o prompt e o limite de saída couberam no
  contexto alocado.
- **Para o artigo.** Sem essa verificação, uma resposta a um prompt truncado passaria como
  amostra válida. É uma armadilha para qualquer estudo com modelos locais (validade de construto).

### 10. A mesma semente dá a mesma resposta em todas as tentativas

- **O que aconteceu.** Com a semente do perfil enviada em toda tentativa, como nos modelos
  hospedados, o qwen3.5:4b devolveu a mesma resposta byte a byte em todas as chamadas. As
  execuções deixariam de ser amostras independentes.
- **O que foi feito.** Cada tentativa recebe uma semente própria, derivada da semente mestra, do
  experimento, da aplicação, do perfil, da variante e do número da tentativa (SHA-256), e
  registrada com ela.
- **Para o artigo.** Descrever a regra das sementes. É o que garante que as execuções diferem
  e podem ser refeitas.

### 11. Reprodutibilidade depende do modelo

- **O que aconteceu.** No qwen3.5:4b, repetir uma tentativa com a sua semente deu a mesma
  resposta, também num processo novo. No gpt-oss:20b, não: o servidor reaproveita do cache um
  token a menos do prompt a cada chamada (1.386, 1.385, 1.384 de 1.387), e a amostragem muda.
  Descarregar o modelo antes de cada tentativa daria o mesmo ponto de partida, mas recarregar o
  gpt-oss:20b logo após descarregá-lo derrubou o processo do modelo nas 2 tentativas (HTTP 500,
  erro de CUDA).
- **O que foi feito.** O cache ficou ligado e falhas do servidor são tentadas de novo. Cada
  variante registra o digest dos pesos, a quantização, os parâmetros padrão e a versão do
  servidor, e não continua com outros pesos.
- **Para o artigo.** Ameaça à confiabilidade da replicação. Os resultados descrevem builds
  quantizados específicos, identificados pelo digest. A versão do Ollama precisa ficar fixa
  (no Windows, o aplicativo se atualiza sozinho).

### 12. O hardware disponível torna as execuções lentas

- **O que aconteceu.** Com 6 GB de memória de vídeo, só 22 a 24 % do gpt-oss:20b e 68 % do
  qwen3.5:4b (com contexto de 49k) ficam na GPU; o resto roda na CPU. No piloto, uma tentativa
  levou de 5,7 a 9,4 min (gpt-oss) e de 15,6 a 21,0 min (qwen) na JPetStore, e de 46,4 a
  57,3 min (gpt-oss) e de 20,4 a 32,5 min (qwen) no DayTrader. Os modelos hospedados levam menos de 1 min. A replicação
  com o qwen (4 aplicações, 2 variantes, 10 execuções) foi estimada em cerca de 30 h.
- **O que foi feito.** Os pilotos rodaram em sequência, sem dividir a GPU, com o Windows
  impedido de suspender durante as execuções. A estimativa de tempo aparece na página de
  Execução.
- **Para o artigo.** Declarar o hardware: tempo e viabilidade dependem dele, e o desempenho de
  um modelo local maior pode ser limitado pela máquina, não pelo modelo (validade externa).

### 13. Os modelos locais raciocinam muito mais

- **O que aconteceu.** Com raciocínio ligado, os modelos locais geraram de 5.508 a 32.000
  tokens de saída por tentativa; os hospedados, de 472 a 3.780. Sem raciocínio, o qwen3.5:4b
  responde em cerca de 20 s, mas errou 11 de 12 tentativas (classes duplicadas, ausentes ou
  inexistentes).
- **O que foi feito.** Raciocínio ligado nos perfis locais, como nos hospedados (nível high
  quando o modelo tem níveis), e limite de saída igual ao dos hospedados (32.000 tokens).
- **Para o artigo.** O raciocínio é parte do tratamento e decide a taxa de respostas válidas
  dos modelos pequenos.

### 14. Na aplicação maior, os modelos locais perdem a lista de classes

- **O que aconteceu.** O DayTrader tem 108 classes, e 54 delas estão em `web.prims` (servlets
  e beans `Ping*` com nomes parecidos). O gpt-oss:20b não acertou nenhuma das 4 tentativas: duas
  bateram no limite de 32.000 tokens antes de fechar o JSON, e duas terminaram sozinhas, mas
  deixaram de fora 11 e 5 classes. O qwen3.5:4b acertou 1 de 5 (com K = 2); as outras erraram a
  grafia do pacote de todas as classes (`daytrada`), inventaram nomes de classes ou deixaram
  classes de fora. Fora a grafia errada do pacote, toda classe esquecida ou inventada estava em
  `web.prims`, exceto `util.WebSocketJMSMessage`. Na JPetStore (24 classes), os dois acertaram
  3 de 3. Os modelos hospedados acertaram 7 de 7 no DayTrader.
- **O que foi feito.** Perfis e regras continuam iguais em todas as aplicações, e as falhas
  entram como resultado: aumentar o limite de saída ou baixar o raciocínio depois de ver as
  respostas ajustaria o tratamento ao modelo e à aplicação. O gpt-oss:20b saiu da replicação;
  fica só o qwen3.5:4b. No DayTrader, a replicação para na primeira execução falha de cada
  variante.
- **Para o artigo.** A taxa de falha cresce com o tamanho da aplicação e com nomes parecidos;
  é um resultado sobre os modelos pequenos, não só uma limitação. O qwen3.5:4b também escolheu
  K = 2 em 3 das suas 4 respostas aceitas; os modelos hospedados, em 1 de 22 nas mesmas duas
  aplicações (K de 2 a 5). K pequeno afeta SM e NED.

### 15. A replicação local foi abandonada

- **O que aconteceu.** A replicação com o qwen3.5:4b começou pelo AcmeAir (52 classes). Das 4
  tentativas, 1 foi aceita (com K = 2) e 3 foram inválidas: uma deixou de fora duas classes
  (`CustomerImpl` e `MongoConnectionManager`), outra inventou um pacote para uma classe
  existente (`com.acmeair.config.AcmeAirConstants` em vez de `com.acmeair.AcmeAirConstants`) e
  deixou de fora outras duas, e a última deixou de fora cinco. Cada tentativa levou de 17 a 21
  minutos. Uma execução falha depois de 4 tentativas inválidas. Com 1 tentativa aceita
  em 3 ou 4, cerca de 20 % a 30 % das execuções falhariam, e o AcmeAir precisaria de 60 a 80
  tentativas para as suas 20 execuções aceitas, de 19 a 25 horas só nessa aplicação. No mesmo dia, o modelo hospedado teve 80 de 80 tentativas aceitas nas quatro
  aplicações, em menos de 1h30.
- **O que foi feito.** A replicação foi cancelada e o estudo usa só o modelo hospedado. As
  tentativas do qwen foram apagadas do banco (cópia em `work/backups/`, fora do git); as
  configurações da replicação estão no dump do commit d01d05f e os pilotos dos dois modelos
  locais no dump do commit ff068b7. A ferramenta continua aceitando modelos locais.
- **Para o artigo.** Declarar que a replicação com pesos abertos foi planejada, pilotada e
  abandonada, e por quê. Com o hardware disponível, um modelo local pequeno não gerou partições
  válidas com regularidade nas aplicações maiores, e um modelo maior não cabe na GPU. A amostra
  é pequena (4 tentativas no AcmeAir, 5 no DayTrader, 3 na JPetStore), então isso é uma
  observação, não um resultado. Fica como limitação (validade externa: os resultados valem para
  um modelo hospedado) e como trabalho futuro.

## Processo e ferramenta

### 16. Configurações apagadas por engano pela interface

- **O que aconteceu.** Ao apagar entradas pela página de Configuração, a configuração do dry
  run foi apagada junto com experimentos, um prompt e um perfil.
- **O que foi feito.** Os padrões da ferramenta ficam no pacote e não podem ser apagados; toda
  mudança de configuração vai para uma coleção de auditoria com os valores antes e depois; apagar
  um estudo exige digitar o nome e grava antes uma cópia completa do banco.
- **Para o artigo.** Lição sobre ferramentas de pesquisa: o registro do experimento precisa
  ser protegido contra o próprio pesquisador. O dump determinístico do banco no git é o pacote
  de replicação.
