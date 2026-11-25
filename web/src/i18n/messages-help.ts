// Explanations shown by <Term>: one entry per term of the interface. `wiki` is
// "<page>#<section id>" in the same language; a test checks that every target exists.
// English is typed from Portuguese, so a missing key fails the build.

export interface HelpEntry {
  title: string;
  text: string;
  wiki?: string;
}

const pt = {
  // ------------------------------------------------------------ study, runs and costs
  study: {
    title: "Estudo",
    text: "Combinação de experimento, aplicação e perfil de modelo que já tem execuções gravadas. Cada estudo tem as suas decomposições e métricas.",
  },
  experiment: {
    title: "Experimento",
    text: "Configuração que fixa a aplicação, o número de execuções, as variantes, a semente, o prompt e os controles. O nome do experimento identifica as suas execuções no banco de dados.",
    wiki: "tool#reprodutibilidade",
  },
  profile: {
    title: "Perfil de LLM",
    text: "Configuração que fixa provedor, modelo, parâmetros e preços. As execuções de cada perfil ficam separadas no banco de dados.",
    wiki: "treatment#modelo-e-perfis",
  },
  app: {
    title: "Aplicação",
    text: "Monólito Java estudado, fixado numa versão exata do código (commit). As comparações entre métodos são feitas dentro de cada aplicação.",
    wiki: "design#objetos-e-blocos",
  },
  modelConfig: {
    title: "Configuração do modelo",
    text: "Parâmetros enviados ao modelo, como o esforço de raciocínio e a temperatura, e a versão do prompt. \"Padrão da API\" significa que nenhum valor foi enviado.",
    wiki: "treatment#modelo-e-perfis",
  },
  model: {
    title: "Modelo",
    text: "Provedor e identificador do modelo de linguagem usado nas execuções.",
    wiki: "treatment#modelo-e-perfis",
  },
  modelReported: {
    title: "Modelo informado pela API",
    text: "Identificador do modelo que de fato respondeu, devolvido pelo provedor. Pode trazer a data da versão do modelo.",
  },
  variant: {
    title: "Variante",
    text: "Original: o prompt usa os nomes reais das classes. Ofuscada: as classes viram C01, C02…, para medir o quanto o modelo depende de já conhecer a aplicação.",
    wiki: "design#variante-com-nomes-ofuscados",
  },
  run: {
    title: "Execução",
    text: "Uma resposta aceita do LLM, isto é, uma decomposição completa da aplicação. Cada execução pode ter exigido até 4 tentativas.",
    wiki: "treatment#repeticoes",
  },
  attempt: {
    title: "Tentativa",
    text: "Uma chamada ao modelo. Se a resposta é inválida, o mesmo prompt é reenviado, sem retorno ao modelo, até 4 tentativas por execução.",
    wiki: "treatment#repeticoes",
  },
  accepted: {
    title: "Execuções aceitas",
    text: "Respostas que passaram na regra de aceitação: JSON válido, todas as classes enviadas, cada uma em exatamente um serviço, e pelo menos 2 serviços.",
    wiki: "treatment#regra-de-aceitacao",
  },
  invalid: {
    title: "Tentativas inválidas",
    text: "Respostas rejeitadas pela regra de aceitação. O motivo da rejeição fica registrado.",
    wiki: "treatment#regra-de-aceitacao",
  },
  reasons: {
    title: "Motivos de rejeição",
    text: "Primeira verificação que falhou: JSON inválido, formato fora do esquema, classe desconhecida, repetida ou ausente, menos de dois serviços ou recusa do provedor.",
    wiki: "treatment#regra-de-aceitacao",
  },
  apiErrors: {
    title: "Erros de API",
    text: "Falhas na comunicação com o provedor, como queda de rede ou limite de taxa. Não são respostas do modelo e não contam como tentativas.",
    wiki: "treatment#repeticoes",
  },
  kPerRun: {
    title: "K por execução",
    text: "Número de serviços que o LLM escolheu em cada execução aceita, na ordem das execuções.",
    wiki: "design#fator-e-niveis",
  },
  tokens: {
    title: "Tokens",
    text: "Unidades de texto cobradas pelo provedor. Entrada: o prompt. Saída: a resposta, incluindo o raciocínio interno quando o modelo o usa.",
  },
  latency: {
    title: "Tempo",
    text: "Duração das chamadas ao modelo, em segundos.",
  },
  cost: {
    title: "Custo (US$)",
    text: "Calculado com os tokens informados pela API e os preços do perfil do modelo.",
    wiki: "tool#chaves-e-custos",
  },
  evaluated: {
    title: "Controles calculados",
    text: "Indica se o AH, a partição aleatória, o HDBSCAN e as quatro métricas já foram calculados para as execuções do estudo.",
  },
  promptVersion: {
    title: "Prompt",
    text: "Versão do texto enviado ao modelo. Uma versão nunca é alterada; mudar o texto cria uma versão nova.",
    wiki: "treatment#prompt",
  },
  experimentConfig: {
    title: "Configuração do experimento",
    text: "Configuração (página Configuração) que grava este experimento neste banco de dados. Entre outras coisas, ela define se a análise é descritiva ou inferencial.",
  },

  // ------------------------------------------------------------ application and graph
  tag: {
    title: "Versão (tag)",
    text: "Rótulo de versão do repositório que aponta para o commit usado.",
    wiki: "graph#extracao",
  },
  commit: {
    title: "Commit",
    text: "Identificador da versão exata do código da aplicação. Fixar o commit torna a extração do grafo reproduzível.",
    wiki: "graph#extracao",
  },
  classes: {
    title: "Classes",
    text: "Classes Java de nível superior da aplicação, que são os nós do grafo. Classes internas e anônimas contam junto com a classe que as contém.",
    wiki: "graph#regras-de-contagem",
  },
  edges: {
    title: "Arestas",
    text: "Pares ordenados de classes A → B em que A chama B pelo menos uma vez.",
    wiki: "graph#regras-de-contagem",
  },
  calls: {
    title: "Chamadas",
    text: "Pontos do código em que uma classe invoca um método ou construtor de outra. A contagem é estática: não depende de quantas vezes o código executa.",
    wiki: "graph#regras-de-contagem",
  },
  isolated: {
    title: "Classes isoladas",
    text: "Classes sem chamadas de entrada nem de saída no grafo. Mesmo assim, todo método precisa colocá-las num serviço.",
    wiki: "graph#regras-de-contagem",
  },
  package: { title: "Pacote", text: "Pacote Java a que a classe pertence." },
  kind: { title: "Tipo", text: "Classe, interface, enum, classe abstrata ou outro tipo Java, lido do código compilado." },
  sourceFile: { title: "Arquivo", text: "Arquivo-fonte da classe, relativo à pasta da aplicação." },
  callsOut: {
    title: "Chama",
    text: "Classes que esta classe invoca, com o número de chamadas. ↔ marca chamadas para outro serviço em algum painel.",
  },
  calledBy: {
    title: "É chamada por",
    text: "Classes que invocam esta classe, com o número de chamadas. ↔ marca chamadas vindas de outro serviço em algum painel.",
  },

  // ------------------------------------------------------------ methods
  method: {
    title: "Método",
    text: "Como a decomposição foi gerada: pelo LLM (tratamento), pelo AH ou pela partição aleatória (controles com o mesmo K) ou pelo HDBSCAN (referência).",
    wiki: "design#fator-e-niveis",
  },
  llm: {
    title: "LLM",
    text: "Modelo de linguagem de grande porte (Large Language Model). É o tratamento: recebe a lista de classes e o grafo de chamadas e devolve a divisão das classes em serviços.",
    wiki: "treatment#modelo-e-perfis",
  },
  ah: {
    title: "AH · Agrupamento hierárquico",
    text: "Controle. Junta as classes mais próximas no grafo, passo a passo, até formar grupos, e corta o resultado no mesmo K que o LLM escolheu.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  ahSelected: {
    title: "AH selecionado",
    text: "Variante do AH usada como controle: a fixada na configuração do experimento (neighbors:complete no experimento final) ou, com a regra automática, a de maior mediana de SM nas execuções aceitas.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  ahVariant: {
    title: "Variante do AH",
    text: "Combinação de uma distância (chamadas ou vizinhos) com uma ligação (média, completa ou simples). São 6 variantes.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  otherAh: {
    title: "Outras variantes do AH",
    text: "Variantes do AH que não foram escolhidas como controle. Aparecem em cinza, só para comparação.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  random: {
    title: "Partição aleatória",
    text: "Controle. Divide as classes em K serviços por sorteio, com semente registrada. Serve de limite inferior: um bom método deve superá-la.",
    wiki: "controls#particao-aleatoria",
  },
  hdbscan: {
    title: "HDBSCAN",
    text: "Agrupamento por densidade que escolhe o próprio número de serviços. Fica fora da comparação pareada e aparece só como referência.",
    wiki: "controls#hdbscan",
  },
  treatment: { title: "Tratamento", text: "O método avaliado no experimento: o LLM.", wiki: "design#fator-e-niveis" },
  controls: {
    title: "Controles (mesmo K)",
    text: "Métodos de comparação gerados com o número de serviços que o LLM escolheu na execução: o AH e a partição aleatória.",
    wiki: "design#fator-e-niveis",
  },
  references: {
    title: "Referência (K próprio)",
    text: "Métodos que escolhem o próprio número de serviços, como o HDBSCAN. Servem só de referência descritiva.",
    wiki: "controls#hdbscan",
  },
  k: {
    title: "K · Número de serviços",
    text: "Quantos serviços (microsserviços) a decomposição tem. O LLM escolhe K em cada execução, e os controles usam o mesmo K.",
    wiki: "design#fator-e-niveis",
  },

  // ------------------------------------------------------------ metrics
  sm: {
    title: "SM · Modularidade estrutural",
    text: "Coesão dentro dos serviços menos acoplamento entre eles, contando as arestas do grafo. Vai de −1 a 1; maior é melhor.",
    wiki: "metrics#modularidade-estrutural-sm",
  },
  ifn: {
    title: "IFN · Número de interfaces",
    text: "Média, por serviço, de classes chamadas por outros serviços (as interfaces). Menor é melhor: menos pontos de contato entre serviços.",
    wiki: "metrics#numero-de-interfaces-ifn",
  },
  icp: {
    title: "ICP · Comunicação entre partições",
    text: "Fração das chamadas do grafo que ligam classes de serviços diferentes. Vai de 0 a 1; menor é melhor.",
    wiki: "metrics#comunicacao-entre-particoes-icp",
  },
  ned: {
    title: "NED · Distribuição não extrema",
    text: "Fração dos serviços com tamanho extremo: menos de 5 ou mais de 20 classes. Vai de 0 a 1; menor é melhor. Entra no critério de comparação adotado depois do piloto.",
    wiki: "metrics#distribuicao-nao-extrema-ned",
  },
  crossCalls: {
    title: "Chamadas entre serviços",
    text: "Chamadas de uma classe para outra de serviço diferente. Divididas pelo total de chamadas, dão a ICP.",
    wiki: "metrics#comunicacao-entre-particoes-icp",
  },
  interfaces: {
    title: "Interfaces",
    text: "Classes chamadas por pelo menos uma classe de outro serviço. No grafo, têm um anel escuro; a média por serviço é a IFN.",
    wiki: "metrics#numero-de-interfaces-ifn",
  },

  // ------------------------------------------------------------ decompositions page
  panel: {
    title: "Painel",
    text: "Cada painel desenha uma decomposição da execução escolhida. O seletor do painel escolhe o método.",
    wiki: "tool#paginas-da-interface",
  },
  layout: {
    title: "Layout",
    text: "Posições fixas: cada classe fica no mesmo lugar em todos os painéis, e a cor indica o serviço. Agrupado por serviço: cada serviço vira uma caixa, que pode ser recolhida.",
    wiki: "tool#paginas-da-interface",
  },
  compare: {
    title: "Comparar com",
    text: "Marca com contorno tracejado as classes que mudaram de serviço em relação a outra execução e mostra o ARI entre as duas partições.",
    wiki: "analysis#analise-descritiva",
  },
  labels: {
    title: "Rótulos",
    text: "Nome da classe ou nome que o modelo recebeu no prompt. Na variante ofuscada, o prompt usa códigos como C07.",
    wiki: "design#variante-com-nomes-ofuscados",
  },
  crossOnly: {
    title: "Só arestas entre serviços",
    text: "Esconde as chamadas internas dos serviços e deixa só as que cruzam serviços, que são as que aumentam a ICP.",
  },
  servicePerPane: { title: "Serviço em cada painel", text: "Serviço a que a classe pertence em cada um dos painéis." },
  promptName: {
    title: "Nome no prompt",
    text: "Como a classe apareceu para o modelo. Na variante ofuscada, é um código como C07, sorteado com semente.",
    wiki: "design#variante-com-nomes-ofuscados",
  },
  services: {
    title: "Serviços",
    text: "Serviços da decomposição deste painel, com o número de classes e de interfaces de cada um. Clique num serviço para destacá-lo no grafo.",
  },

  // ------------------------------------------------------------ results page
  set: {
    title: "Experimento e perfil",
    text: "Os resultados juntam todas as aplicações de um experimento rodadas com o mesmo perfil de modelo.",
  },
  scope: {
    title: "Aplicações",
    text: "Todas: junta os pares de todas as aplicações, como na análise planejada. Uma aplicação: usa só os pares dela.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  ahAll: {
    title: "Todas as variantes do AH",
    text: "Mostra também, em cinza, as variantes do AH que não foram escolhidas como controle.",
  },
  descriptive: {
    title: "Análise descritiva",
    text: "Medianas, quartis, diferenças e estabilidade, sem testes de hipótese. É a análise usada quando o arquivo do experimento desliga os testes.",
    wiki: "analysis#analise-descritiva",
  },
  inferential: {
    title: "Análise inferencial",
    text: "Testes de hipótese do experimento completo: normalidade, Wilcoxon ou t pareado, ajuste de Holm e delta de Cliff. Liga-se com [analysis] inferential no arquivo do experimento.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  metricsByMethod: {
    title: "Métricas por método",
    text: "Valores das quatro métricas para cada método. Cada ponto é uma execução; a faixa clara vai de Q1 a Q3, e o traço marca a mediana.",
    wiki: "analysis#analise-descritiva",
  },
  n: { title: "n", text: "Número de execuções, ou de pares, usadas no cálculo." },
  median: { title: "Mediana", text: "Valor do meio quando as execuções são ordenadas: metade fica acima e metade abaixo." },
  q1q3: {
    title: "Q1 e Q3",
    text: "Primeiro e terceiro quartis. Entre eles fica a metade central das execuções; a distância Q3 − Q1 é o intervalo interquartil.",
    wiki: "analysis#analise-descritiva",
  },
  minmax: { title: "Mínimo e máximo", text: "Menor e maior valor observado entre as execuções." },
  pairedDifference: {
    title: "Diferença pareada (d)",
    text: "Valor do LLM menos valor do controle, na mesma execução e com o mesmo K. Em SM, d > 0 favorece o LLM; em IFN, ICP e NED, d < 0 favorece o LLM.",
    wiki: "analysis#diferencas-pareadas",
  },
  signs: {
    title: "d > 0 / d < 0 / d = 0",
    text: "Quantas diferenças foram positivas, negativas e nulas.",
    wiki: "analysis#diferencas-pareadas",
  },
  control: {
    title: "Controle",
    text: "Método com que o LLM é comparado: o AH selecionado ou a partição aleatória, sempre com o mesmo K.",
    wiki: "design#fator-e-niveis",
  },
  stability: {
    title: "Estabilidade entre execuções",
    text: "Quanto as decomposições do LLM mudam de uma execução para outra, com o mesmo prompt e o mesmo modelo.",
    wiki: "analysis#analise-descritiva",
  },
  distinctPartitions: {
    title: "Partições distintas",
    text: "Quantas decomposições diferentes o LLM devolveu. 1 significa que todas as execuções foram iguais.",
  },
  groupsOfRuns: {
    title: "Grupos de execuções",
    text: "Execuções que devolveram a mesma partição, separadas por vírgula; os grupos são separados por barra.",
  },
  ari: {
    title: "ARI · Índice de Rand ajustado",
    text: "Semelhança entre duas partições das classes: 1 indica partições iguais; perto de 0, semelhança igual à do acaso.",
    wiki: "analysis#analise-descritiva",
  },
  ahSelection: {
    title: "Seleção da variante do AH",
    text: "Escolha da variante do AH usada como controle: a fixada na configuração do experimento ou, com a regra automática, a de maior mediana de SM nas execuções aceitas.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  medianSm: {
    title: "Mediana de SM",
    text: "Mediana da modularidade estrutural da variante nas execuções aceitas; com a regra automática, é o valor que decide a seleção.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  rule: {
    title: "Regra",
    text: "Como a variante foi escolhida: automaticamente, pela maior mediana de SM, ou fixada na configuração do experimento.",
  },
  shapiro: {
    title: "Shapiro-Wilk",
    text: "Teste de normalidade das diferenças. Com p < 0,05, a normalidade é rejeitada e entra o Wilcoxon; caso contrário, o teste t pareado.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  testUsed: {
    title: "Teste",
    text: "Wilcoxon pareado: compara a mediana das diferenças com zero, sem supor normalidade. t pareado: compara a média, quando as diferenças passam no teste de normalidade.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  statistic: { title: "Estatística", text: "Valor calculado pelo teste: W no Wilcoxon, t no teste t." },
  pValue: {
    title: "p",
    text: "Probabilidade de observar uma diferença pelo menos tão grande se não houvesse diferença real entre os métodos.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  pHolm: {
    title: "p (Holm)",
    text: "Valor-p corrigido pelo procedimento de Holm, porque são feitas oito comparações ao mesmo tempo. A diferença é significativa se ele ficar abaixo de 0,05.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  significant: { title: "Significativo", text: "Sim quando o p corrigido por Holm fica abaixo de α = 0,05." },
  location: { title: "Mediana ou média de d", text: "Mediana das diferenças quando o teste é o Wilcoxon, e média quando é o teste t." },
  cliff: {
    title: "δ de Cliff",
    text: "Tamanho do efeito, de −1 a 1: a chance de um valor do LLM ser maior que um do controle menos a chance de ser menor. 0 indica sobreposição completa.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  magnitude: {
    title: "Magnitude",
    text: "Leitura do δ de Cliff: desprezível abaixo de 0,147, pequeno abaixo de 0,33, médio abaixo de 0,474 e grande a partir daí.",
    wiki: "analysis#experimento-completo-testes-de-hipotese",
  },
  favours: {
    title: "Favorece",
    text: "Método favorecido pelo resultado, levando em conta a direção preferida da métrica: em SM, maior; nas outras, menor.",
    wiki: "variables#criterio-de-comparacao",
  },
  criterion: {
    title: "Critério de comparação",
    text: "Regra para considerar o LLM superior a um controle: SM significativamente melhor, efeito ao menos pequeno e nenhuma piora significativa em IFN, ICP e NED. A condição do NED foi acrescentada depois do piloto.",
    wiki: "variables#criterio-de-comparacao",
  },
  criterionRoteiro: {
    title: "Critério do roteiro",
    text: "O critério como escrito no roteiro, sem a condição do NED. É relatado ao lado do critério adotado, para mostrar o efeito da mudança.",
    wiki: "variables#criterio-de-comparacao",
  },
  export: {
    title: "Exportar",
    text: "CSV: todos os valores, com ponto decimal. LaTeX: tabela pronta para o artigo. SVG e PNG: a figura, no tema claro.",
    wiki: "analysis#exportacao",
  },

  // ------------------------------------------------------------ configuration page
  provider: {
    title: "Provedor",
    text: "Empresa ou servidor que hospeda o modelo: OpenAI, Anthropic, Google, um servidor compatível ou o Ollama, que roda modelos locais nesta máquina. Cada um tem o seu adaptador.",
    wiki: "treatment#modelo-e-perfis",
  },
  modelId: {
    title: "Modelo",
    text: "Identificador do modelo no provedor, como gpt-5.6-luna. O botão ao lado lista os modelos disponíveis na sua conta.",
  },
  temperature: {
    title: "Temperatura",
    text: "Controla a variação das respostas. Vazio: o valor não é enviado e vale o padrão do provedor; alguns modelos só aceitam o padrão.",
    wiki: "variables#variaveis-de-estado",
  },
  maxTokens: {
    title: "Limite de saída",
    text: "Número máximo de tokens que o modelo pode gerar por resposta, incluindo o raciocínio. Também limita o custo de cada tentativa.",
  },
  apiSeed: {
    title: "Semente da API",
    text: "Semente enviada ao provedor, quando ele aceita. Não garante respostas idênticas e é diferente da semente mestre do experimento. Nos modelos locais fica vazia: cada tentativa recebe uma semente derivada da semente mestre.",
    wiki: "treatment#modelos-locais",
  },
  requestOptions: {
    title: "Opções da requisição",
    text: "Parâmetros extras enviados em toda chamada, em JSON, como o esforço de raciocínio. Fazem parte da configuração controlada do modelo. Num modelo local, incluem a janela de contexto (options.num_ctx), que é obrigatória.",
    wiki: "treatment#modelo-e-perfis",
  },
  clientOptions: {
    title: "Opções do cliente",
    text: "Como a ferramenta se conecta ao provedor: variável da chave, tempo limite e, em servidores compatíveis, o endereço. Não mudam o que o modelo recebe.",
  },
  keyVariable: {
    title: "Variável da chave",
    text: "Nome da variável de ambiente que guarda a chave de API. A chave nunca fica em arquivo nem vai para o navegador.",
    wiki: "tool#chaves-e-custos",
  },
  timeout: {
    title: "Tempo limite (timeout_s)",
    text: "Segundos de espera por uma resposta do provedor antes de desistir da chamada. Modelos com raciocínio longo precisam de valores altos.",
  },
  baseUrl: {
    title: "Endereço do servidor (base_url)",
    text: "Endereço do servidor do modelo: o Ollama desta máquina em http://127.0.0.1:11434 (provedor ollama) ou a URL base de um servidor compatível com a API da OpenAI, terminada em /v1.",
  },
  apiKey: {
    title: "Chave de API",
    text: "Se a chave foi encontrada nas variáveis de ambiente. Sem ela, o perfil não consegue chamar o modelo.",
    wiki: "tool#chaves-e-custos",
  },
  price: {
    title: "Preço",
    text: "Dólares por milhão de tokens de entrada e de saída, copiados da página de preços do provedor. Entram no custo e na estimativa.",
    wiki: "tool#chaves-e-custos",
  },
  priceSource: {
    title: "Fonte e data do preço",
    text: "Página consultada e data da consulta, para que o custo registrado possa ser conferido depois.",
  },
  profileName: {
    title: "Nome do perfil",
    text: "Identifica o perfil e as suas execuções no banco de dados. Para testar outro modelo ou outros parâmetros, crie outro perfil.",
  },
  experimentId: {
    title: "Identificador",
    text: "Nome da configuração no banco de dados. É o que a linha de comando recebe em --experiment. Uma configuração pode ter um nome de experimento diferente do identificador.",
  },
  experimentName: {
    title: "Nome do experimento",
    text: "Nome que identifica as execuções e os resultados no banco de dados. Configurações com o mesmo nome e aplicações diferentes formam um experimento com várias aplicações.",
  },
  masterSeed: {
    title: "Semente mestre",
    text: "Número de que derivam todos os sorteios do experimento, como a ofuscação e as partições aleatórias. Com a mesma semente, os sorteios se repetem.",
    wiki: "tool#reprodutibilidade",
  },
  acceptedRuns: {
    title: "Execuções aceitas por variante",
    text: "Quantas respostas válidas do LLM o experimento precisa em cada variante. O plano prevê 10 por aplicação.",
    wiki: "design#unidade-de-analise-e-repeticoes",
  },
  maxRetries: {
    title: "Reenvios de saída inválida",
    text: "Quantas vezes uma resposta inválida é reenviada com o mesmo prompt, sem retorno ao modelo. Com 3, cada execução tem até 4 tentativas.",
    wiki: "treatment#repeticoes",
  },
  maxFailedRuns: {
    title: "Limite de execuções falhas",
    text: "A rodada para depois deste número de execuções falhas (todas as tentativas inválidas), para não gastar sem resultado.",
  },
  database: {
    title: "Banco de dados",
    text: "Banco do MongoDB onde ficam execuções e resultados. O banco monosplit guarda os dados do estudo, e a cópia legível dele (monosplit db dump) vai para o git; o ensaio a seco usa o monosplit_dry_run, que fica fora do dump.",
    wiki: "tool#armazenamento-dos-dados",
  },
  defaultProfile: { title: "Perfil padrão", text: "Perfil usado quando a rodada não escolhe outro." },
  ahVariants: {
    title: "Variantes de AH medidas",
    text: "Variantes do AH calculadas em cada execução. Todas entram na seleção; só a escolhida vira controle.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  ahPrimary: {
    title: "Controle AH",
    text: "Automático: vence a variante com a maior mediana de SM nas execuções aceitas, o que seleciona pela própria variável dependente. Para fixar uma variante, como no experimento final, escolha-a aqui.",
    wiki: "controls#agrupamento-hierarquico-ah",
  },
  hdbscanMin: {
    title: "Tamanho mínimo de grupo",
    text: "Menor grupo que o HDBSCAN aceita como serviço; cada classe que não entra em nenhum grupo vira um serviço próprio.",
    wiki: "controls#hdbscan",
  },
  placeholders: {
    title: "Marcadores",
    text: "Trechos como $class_list e $edge_list que a ferramenta troca pelos dados da aplicação antes de enviar o prompt.",
    wiki: "treatment#prompt",
  },
  sha: {
    title: "SHA-256",
    text: "Resumo do texto do prompt. Muda com qualquer alteração no texto e fica registrado em cada execução.",
  },
  usage: {
    title: "Estudos",
    text: "Estudos que já usam este item. Itens em uso ficam travados, para não mudar o que já foi executado.",
  },
  appId: { title: "Identificador", text: "Nome curto da aplicação, usado como chave no banco de dados." },
  repository: { title: "Repositório", text: "Endereço git de onde a aplicação é clonada.", wiki: "graph#extracao" },
  build: {
    title: "Build",
    text: "Como compilar a aplicação: com o Maven wrapper do próprio projeto (mvnw), com o Maven instalado pelo MonoSplit ou com o Gradle wrapper do projeto (gradlew). O Gradle precisa ser da versão 8.5 ou mais nova para rodar no JDK 21 do estudo.",
    wiki: "graph#extracao",
  },
  buildArgs: {
    title: "Argumentos do build",
    text: "Opções passadas ao Maven. No JPetStore, elas desligam os plugins que reescrevem o código-fonte, para que o código compilado corresponda ao commit.",
    wiki: "graph#extracao",
  },
  sourceRoots: {
    title: "Pastas de código-fonte",
    text: "Onde estão os arquivos .java da aplicação, como src/main/java. Os testes ficam de fora.",
  },
  classDirs: {
    title: "Pastas de classes compiladas",
    text: "Onde o build grava os arquivos .class que o javap lê, como target/classes.",
    wiki: "graph#extracao",
  },
  appStatus: { title: "Situação", text: "Se a aplicação já foi clonada e se o grafo de chamadas já foi extraído." },
  note: { title: "Observação", text: "Texto livre sobre a aplicação, como o motivo da versão escolhida." },

  // ------------------------------------------------------------ execution page
  operation: {
    title: "Operação",
    text: "Rodadas, controles e relatório: o procedimento inteiro. Só as rodadas: chama o modelo. Só controles: recalcula AH, partição aleatória, métricas e relatório, sem chamar o modelo.",
  },
  estimate: {
    title: "Estimativa",
    text: "Previsão de tokens e custo antes de rodar, com base nas tentativas anteriores ou em aproximações. O custo máximo supõe o pior caso.",
    wiki: "tool#chaves-e-custos",
  },
  missing: { title: "Faltam", text: "Execuções aceitas que ainda faltam para chegar ao número configurado." },
  tokensPerAttempt: {
    title: "Tokens por tentativa",
    text: "Tokens de entrada (prompt) e de saída (resposta) esperados em cada tentativa: observados nas tentativas anteriores ou aproximados.",
  },
  attemptsExpected: {
    title: "Tentativas esperadas e máximas",
    text: "Esperadas: com a taxa de aceitação observada. Máximas: as execuções que faltam usando todos os reenvios, até o limite de falhas.",
  },
  expectedCost: { title: "Custo esperado", text: "Custo provável da rodada, com os tokens e as tentativas esperados." },
  maxCost: {
    title: "Custo máximo",
    text: "Limite superior do custo: todas as tentativas usam o limite de saída, e as execuções falham até o limite configurado.",
  },
  secondsPerAttempt: {
    title: "Tempo por tentativa",
    text: "Média do tempo das tentativas anteriores desta variante, do envio do prompt ao fim da resposta. Num modelo local, inclui carregar o modelo na memória quando ele não está carregado.",
  },
  expectedTime: {
    title: "Tempo esperado",
    text: "Tentativas esperadas vezes o tempo médio por tentativa. Num modelo local nada é cobrado, e o tempo é o custo que conta.",
    wiki: "treatment#modelos-locais",
  },
  dryRun: {
    title: "Ensaio a seco",
    text: "Roda o procedimento inteiro com um cliente falso, que não chama nenhum modelo nem gasta dinheiro. Os números servem para testar a ferramenta, não são dados.",
    wiki: "glossary#termos",
  },
  extractGraph: {
    title: "Extração do grafo",
    text: "Clona a aplicação no commit fixado, compila o código e lê o resultado com o javap para montar o grafo de chamadas.",
    wiki: "graph#extracao",
  },
  jobs: {
    title: "Tarefas",
    text: "Operações enviadas ao servidor local. Rodam uma de cada vez; uma rodada cancelada continua do ponto em que parou quando é iniciada de novo.",
  },
  configNote: {
    title: "Notas",
    text: "Texto livre guardado com a configuração: por que ela existe, fontes consultadas e decisões. Não entra no prompt nem nos cálculos.",
    wiki: "tool#armazenamento-dos-dados",
  },

  // ------------------------------------------------------------ data page
  documents: {
    title: "Documentos por coleção",
    text: "Quantos registros o banco guarda em cada coleção: configuração, grafos, variantes, tentativas, avaliações, métricas, notas e registro de alterações.",
    wiki: "tool#armazenamento-dos-dados",
  },
  attemptStatus: {
    title: "Situação da tentativa",
    text: "Aceita: a resposta passou nas regras de aceitação e virou uma execução. Inválida: a resposta foi recusada e a execução reenvia o prompt. Erro de API: a chamada falhou e não conta como resposta.",
    wiki: "treatment#regra-de-aceitacao",
  },
  tryNumber: {
    title: "Tentativa na execução",
    text: "Posição da tentativa dentro da sua execução: 1 é o primeiro envio; os seguintes são reenvios depois de uma resposta inválida.",
    wiki: "treatment#repeticoes",
  },
  answerText: {
    title: "Texto da resposta",
    text: "O que o modelo respondeu, exatamente como chegou. A regra de aceitação procura nele o objeto JSON da decomposição.",
    wiki: "treatment#regra-de-aceitacao",
  },
  acceptedPartition: {
    title: "Partição aceita",
    text: "Serviço atribuído a cada classe, com os nomes reais das classes (na variante ofuscada, os códigos já foram traduzidos de volta).",
    wiki: "treatment#regra-de-aceitacao",
  },
  rawResponse: {
    title: "Resposta completa da API",
    text: "O documento devolvido pelo provedor, com identificador, motivo de término e contagem de tokens. Fica guardado para auditoria.",
    wiki: "tool#armazenamento-dos-dados",
  },
  edgeVerdict: {
    title: "Aresta confirmada",
    text: "Resultado da conferência manual: sim quando as linhas indicadas contêm as chamadas, não quando não contêm. Vazio: ainda não conferida.",
    wiki: "graph#conferencia-manual",
  },
  edgeNote: {
    title: "Notas da aresta",
    text: "Observação de quem conferiu, por exemplo a linha exata ou o motivo de uma aresta não confirmada.",
    wiki: "graph#conferencia-manual",
  },
  callSites: {
    title: "Locais no código",
    text: "Até três chamadas que formam a aresta, como arquivo:linha método -> classe.método, relativos à pasta da aplicação.",
    wiki: "graph#conferencia-manual",
  },
  studyNote: {
    title: "Nota do estudo",
    text: "Texto livre do pesquisador sobre o estudo. Fica no banco de dados e no dump, separado das execuções.",
    wiki: "tool#pagina-dados",
  },
  recompute: {
    title: "Recalcular",
    text: "Refaz controles, métricas e relatório a partir das execuções gravadas, com a configuração escolhida. Não chama o modelo.",
    wiki: "tool#pagina-dados",
  },
  deleteStudy: {
    title: "Excluir estudo",
    text: "Apaga todas as variantes, tentativas, avaliações, métricas e a nota do estudo, depois de gravar uma cópia completa do banco em work/backups/.",
    wiki: "tool#pagina-dados",
  },
  auditAction: {
    title: "Ação",
    text: "Tipo de alteração: criação, alteração, exclusão, importação de arquivos antigos, extração de grafo ou sorteio da amostra de arestas.",
    wiki: "tool#pagina-dados",
  },
  auditSource: {
    title: "Origem",
    text: "De onde veio a alteração: a interface, a linha de comando ou a importação dos arquivos de versões anteriores.",
    wiki: "tool#pagina-dados",
  },
  collection: {
    title: "Coleção",
    text: "Conjunto de documentos do banco de dados que recebeu a alteração, como perfis, experimentos ou grafos.",
    wiki: "tool#armazenamento-dos-dados",
  },
  protectedDefault: {
    title: "Padrão da ferramenta",
    text: "Item que vem com a ferramenta: o experimento dry_run, a aplicação jpetstore que ele usa, o perfil fake, o prompt decomposition_base e os modelos de perfil (nomes começados por _). Pode ser editado, mas não excluído. Os demais itens podem ser excluídos quando nada os usa.",
    wiki: "tool#armazenamento-dos-dados",
  },
} satisfies Record<string, HelpEntry>;

export type HelpKey = keyof typeof pt;
export type HelpMessages = Record<HelpKey, HelpEntry>;

export const ptHelp: HelpMessages = pt;

export const enHelp: HelpMessages = {
  study: {
    title: "Study",
    text: "A combination of experiment, application and model profile that already has recorded runs. Each study has its own decompositions and metrics.",
  },
  experiment: {
    title: "Experiment",
    text: "A configuration that fixes the application, the number of runs, the variants, the seed, the prompt and the controls. The experiment name identifies its runs in the database.",
    wiki: "tool#reproducibility",
  },
  profile: {
    title: "LLM profile",
    text: "A configuration that fixes provider, model, parameters and prices. The runs of each profile are kept apart in the database.",
    wiki: "treatment#model-and-profiles",
  },
  app: {
    title: "Application",
    text: "The Java monolith under study, pinned to an exact version of the code (commit). Methods are compared within each application.",
    wiki: "design#objects-and-blocks",
  },
  modelConfig: {
    title: "Model configuration",
    text: "Parameters sent to the model, such as the reasoning effort and the temperature, and the prompt version. \"API default\" means that no value was sent.",
    wiki: "treatment#model-and-profiles",
  },
  model: { title: "Model", text: "Provider and identifier of the language model used in the runs.", wiki: "treatment#model-and-profiles" },
  modelReported: {
    title: "Model reported by the API",
    text: "Identifier of the model that actually answered, returned by the provider. It may include the date of the model version.",
  },
  variant: {
    title: "Variant",
    text: "Original: the prompt uses the real class names. Obfuscated: classes become C01, C02…, to measure how much the model relies on already knowing the application.",
    wiki: "design#variant-with-obfuscated-names",
  },
  run: {
    title: "Run",
    text: "One accepted LLM answer, that is, one complete decomposition of the application. Each run may have needed up to 4 attempts.",
    wiki: "treatment#retries",
  },
  attempt: {
    title: "Attempt",
    text: "One call to the model. If the answer is invalid, the same prompt is sent again, without feedback to the model, up to 4 attempts per run.",
    wiki: "treatment#retries",
  },
  accepted: {
    title: "Accepted runs",
    text: "Answers that passed the acceptance rule: valid JSON, every class sent, each in exactly one service, and at least 2 services.",
    wiki: "treatment#acceptance-rule",
  },
  invalid: {
    title: "Invalid attempts",
    text: "Answers rejected by the acceptance rule. The rejection reason is recorded.",
    wiki: "treatment#acceptance-rule",
  },
  reasons: {
    title: "Rejection reasons",
    text: "The first check that failed: invalid JSON, schema mismatch, unknown, duplicated or missing class, fewer than two services, or a refusal by the provider.",
    wiki: "treatment#acceptance-rule",
  },
  apiErrors: {
    title: "API errors",
    text: "Failures talking to the provider, such as network errors or rate limits. They are not model answers and do not count as attempts.",
    wiki: "treatment#retries",
  },
  kPerRun: {
    title: "K per run",
    text: "Number of services the LLM chose in each accepted run, in run order.",
    wiki: "design#factor-and-levels",
  },
  tokens: {
    title: "Tokens",
    text: "Units of text billed by the provider. Input: the prompt. Output: the answer, including internal reasoning when the model uses it.",
  },
  latency: { title: "Time", text: "Duration of the calls to the model, in seconds." },
  cost: {
    title: "Cost (US$)",
    text: "Computed from the tokens reported by the API and the prices in the model profile.",
    wiki: "tool#keys-and-costs",
  },
  evaluated: {
    title: "Controls computed",
    text: "Whether AH, the random partition, HDBSCAN and the four metrics have been computed for the runs of the study.",
  },
  promptVersion: {
    title: "Prompt",
    text: "Version of the text sent to the model. A version is never changed; changing the text creates a new version.",
    wiki: "treatment#prompt",
  },
  experimentConfig: {
    title: "Experiment configuration",
    text: "The configuration (Configuration page) that writes this experiment into this database. Among other things, it sets whether the analysis is descriptive or inferential.",
  },
  tag: { title: "Version (tag)", text: "Version label of the repository that points to the commit used.", wiki: "graph#extraction" },
  commit: {
    title: "Commit",
    text: "Identifier of the exact version of the application code. Pinning the commit makes the graph extraction reproducible.",
    wiki: "graph#extraction",
  },
  classes: {
    title: "Classes",
    text: "Top-level Java classes of the application, which are the nodes of the graph. Inner and anonymous classes count with the class that contains them.",
    wiki: "graph#counting-rules",
  },
  edges: {
    title: "Edges",
    text: "Ordered pairs of classes A → B where A calls B at least once.",
    wiki: "graph#counting-rules",
  },
  calls: {
    title: "Calls",
    text: "Places in the code where one class invokes a method or constructor of another. The count is static: it does not depend on how often the code runs.",
    wiki: "graph#counting-rules",
  },
  isolated: {
    title: "Isolated classes",
    text: "Classes with no incoming or outgoing calls in the graph. Every method must still place them in a service.",
    wiki: "graph#counting-rules",
  },
  package: { title: "Package", text: "Java package the class belongs to." },
  kind: { title: "Kind", text: "Class, interface, enum, abstract class or other Java type, read from the compiled code." },
  sourceFile: { title: "File", text: "Source file of the class, relative to the application folder." },
  callsOut: {
    title: "Calls",
    text: "Classes this class invokes, with the number of calls. ↔ marks calls to another service in some panel.",
  },
  calledBy: {
    title: "Called by",
    text: "Classes that invoke this class, with the number of calls. ↔ marks calls from another service in some panel.",
  },
  method: {
    title: "Method",
    text: "How the decomposition was produced: by the LLM (treatment), by AH or the random partition (controls with the same K), or by HDBSCAN (reference).",
    wiki: "design#factor-and-levels",
  },
  llm: {
    title: "LLM",
    text: "Large language model. It is the treatment: it receives the list of classes and the call graph and returns the division of the classes into services.",
    wiki: "treatment#model-and-profiles",
  },
  ah: {
    title: "AH · Hierarchical clustering",
    text: "Control. It merges the closest classes of the graph step by step into groups and cuts the result at the K the LLM chose. AH is the Portuguese abbreviation used in the study.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  ahSelected: {
    title: "Selected AH",
    text: "The AH variant used as the control: the one fixed in the experiment configuration (neighbors:complete in the final experiment) or, with the automatic rule, the one with the highest median SM over the accepted runs.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  ahVariant: {
    title: "AH variant",
    text: "A distance (calls or neighbours) combined with a linkage (average, complete or single). There are 6 variants.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  otherAh: {
    title: "Other AH variants",
    text: "AH variants that were not chosen as the control. They appear in grey, for comparison only.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  random: {
    title: "Random partition",
    text: "Control. It divides the classes into K services at random, with a recorded seed. It is a lower bound: a good method should beat it.",
    wiki: "controls#random-partition",
  },
  hdbscan: {
    title: "HDBSCAN",
    text: "Density-based clustering that chooses its own number of services. It stays outside the paired comparison and appears only as a reference.",
    wiki: "controls#hdbscan",
  },
  treatment: { title: "Treatment", text: "The method under evaluation: the LLM.", wiki: "design#factor-and-levels" },
  controls: {
    title: "Controls (same K)",
    text: "Comparison methods generated with the number of services the LLM chose in the run: AH and the random partition.",
    wiki: "design#factor-and-levels",
  },
  references: {
    title: "Reference (own K)",
    text: "Methods that choose their own number of services, such as HDBSCAN. They are only a descriptive reference.",
    wiki: "controls#hdbscan",
  },
  k: {
    title: "K · Number of services",
    text: "How many services (microservices) the decomposition has. The LLM chooses K in each run, and the controls use the same K.",
    wiki: "design#factor-and-levels",
  },
  sm: {
    title: "SM · Structural modularity",
    text: "Cohesion inside the services minus coupling between them, counting the edges of the graph. It ranges from −1 to 1; higher is better.",
    wiki: "metrics#structural-modularity-sm",
  },
  ifn: {
    title: "IFN · Interface number",
    text: "Mean number, per service, of classes called by other services (the interfaces). Lower is better: fewer points of contact between services.",
    wiki: "metrics#interface-number-ifn",
  },
  icp: {
    title: "ICP · Inter-partition communication",
    text: "Share of the calls of the graph that link classes of different services. It ranges from 0 to 1; lower is better.",
    wiki: "metrics#inter-partition-communication-icp",
  },
  ned: {
    title: "NED · Non-extreme distribution",
    text: "Share of the services with an extreme size: fewer than 5 or more than 20 classes. It ranges from 0 to 1; lower is better. It is part of the comparison criterion adopted after the pilot.",
    wiki: "metrics#non-extreme-distribution-ned",
  },
  crossCalls: {
    title: "Calls between services",
    text: "Calls from a class to a class of another service. Divided by all calls, they give ICP.",
    wiki: "metrics#inter-partition-communication-icp",
  },
  interfaces: {
    title: "Interfaces",
    text: "Classes called by at least one class of another service. In the graph they have a dark ring; their mean per service is IFN.",
    wiki: "metrics#interface-number-ifn",
  },
  panel: {
    title: "Panel",
    text: "Each panel draws one decomposition of the chosen run. The panel's selector chooses the method.",
    wiki: "tool#interface-pages",
  },
  layout: {
    title: "Layout",
    text: "Fixed positions: each class keeps its place in every panel, and the colour is the service. Grouped by service: each service becomes a box, which can be collapsed.",
    wiki: "tool#interface-pages",
  },
  compare: {
    title: "Compare with",
    text: "Outlines with a dashed line the classes that moved to another service compared with another run, and gives the ARI between the two partitions.",
    wiki: "analysis#descriptive-analysis",
  },
  labels: {
    title: "Labels",
    text: "The class name or the name the model received in the prompt. In the obfuscated variant, the prompt uses codes such as C07.",
    wiki: "design#variant-with-obfuscated-names",
  },
  crossOnly: {
    title: "Edges between services only",
    text: "Hides the calls inside services and keeps only those that cross services, which are the ones that raise ICP.",
  },
  servicePerPane: { title: "Service in each panel", text: "The service the class belongs to in each panel." },
  promptName: {
    title: "Name in the prompt",
    text: "How the class appeared to the model. In the obfuscated variant it is a code such as C07, drawn with a seed.",
    wiki: "design#variant-with-obfuscated-names",
  },
  services: {
    title: "Services",
    text: "Services of this panel's decomposition, with the number of classes and interfaces of each. Click a service to highlight it in the graph.",
  },
  set: {
    title: "Experiment and profile",
    text: "The results bring together every application of an experiment run with the same model profile.",
  },
  scope: {
    title: "Applications",
    text: "All: pools the pairs of every application, as in the planned analysis. One application: uses only its own pairs.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  ahAll: { title: "Every AH variant", text: "Also shows, in grey, the AH variants that were not chosen as the control." },
  descriptive: {
    title: "Descriptive analysis",
    text: "Medians, quartiles, differences and stability, without hypothesis tests. It is the analysis used when the experiment file turns the tests off.",
    wiki: "analysis#descriptive-analysis",
  },
  inferential: {
    title: "Inferential analysis",
    text: "Hypothesis tests of the full experiment: normality, paired Wilcoxon or t, Holm adjustment and Cliff's delta. Turned on by [analysis] inferential in the experiment file.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  metricsByMethod: {
    title: "Metrics by method",
    text: "Values of the four metrics for each method. Each dot is a run; the light band spans Q1 to Q3, and the tick marks the median.",
    wiki: "analysis#descriptive-analysis",
  },
  n: { title: "n", text: "Number of runs, or of pairs, used in the calculation." },
  median: { title: "Median", text: "The middle value when the runs are sorted: half are above it and half below." },
  q1q3: {
    title: "Q1 and Q3",
    text: "First and third quartiles. The middle half of the runs lies between them; Q3 − Q1 is the interquartile range.",
    wiki: "analysis#descriptive-analysis",
  },
  minmax: { title: "Minimum and maximum", text: "The smallest and largest values observed among the runs." },
  pairedDifference: {
    title: "Paired difference (d)",
    text: "LLM value minus control value, in the same run and with the same K. For SM, d > 0 favours the LLM; for IFN, ICP and NED, d < 0 favours the LLM.",
    wiki: "analysis#paired-differences",
  },
  signs: { title: "d > 0 / d < 0 / d = 0", text: "How many differences were positive, negative and zero.", wiki: "analysis#paired-differences" },
  control: {
    title: "Control",
    text: "The method the LLM is compared with: the selected AH or the random partition, always with the same K.",
    wiki: "design#factor-and-levels",
  },
  stability: {
    title: "Run-to-run stability",
    text: "How much the LLM's decompositions change from one run to another, with the same prompt and the same model.",
    wiki: "analysis#descriptive-analysis",
  },
  distinctPartitions: {
    title: "Distinct partitions",
    text: "How many different decompositions the LLM returned. 1 means that every run was the same.",
  },
  groupsOfRuns: {
    title: "Groups of runs",
    text: "Runs that returned the same partition, separated by commas; groups are separated by slashes.",
  },
  ari: {
    title: "ARI · Adjusted Rand index",
    text: "Similarity between two partitions of the classes: 1 means equal partitions; near 0, no more similar than chance.",
    wiki: "analysis#descriptive-analysis",
  },
  ahSelection: {
    title: "AH variant selection",
    text: "Choice of the AH variant used as the control: the one fixed in the experiment configuration or, with the automatic rule, the one with the highest median SM over the accepted runs.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  medianSm: {
    title: "Median SM",
    text: "Median structural modularity of the variant over the accepted runs; with the automatic rule, this value decides the selection.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  rule: { title: "Rule", text: "How the variant was chosen: automatically, by the highest median SM, or fixed in the experiment configuration." },
  shapiro: {
    title: "Shapiro-Wilk",
    text: "Normality test of the differences. With p < 0.05, normality is rejected and Wilcoxon is used; otherwise, the paired t test.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  testUsed: {
    title: "Test",
    text: "Paired Wilcoxon: compares the median of the differences with zero, without assuming normality. Paired t: compares the mean, when the differences pass the normality test.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  statistic: { title: "Statistic", text: "Value computed by the test: W for Wilcoxon, t for the t test." },
  pValue: {
    title: "p",
    text: "Probability of observing a difference at least this large if there were no real difference between the methods.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  pHolm: {
    title: "p (Holm)",
    text: "p-value adjusted with the Holm procedure, because eight comparisons are made at once. The difference is significant when it is below 0.05.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  significant: { title: "Significant", text: "Yes when the Holm-adjusted p is below α = 0.05." },
  location: { title: "Median or mean of d", text: "Median of the differences when the test is Wilcoxon, and mean when it is the t test." },
  cliff: {
    title: "Cliff's δ",
    text: "Effect size, from −1 to 1: the chance that an LLM value is larger than a control value minus the chance that it is smaller. 0 means complete overlap.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  magnitude: {
    title: "Magnitude",
    text: "Reading of Cliff's δ: negligible below 0.147, small below 0.33, medium below 0.474 and large from there on.",
    wiki: "analysis#full-experiment-hypothesis-tests",
  },
  favours: {
    title: "Favours",
    text: "The method favoured by the result, given the metric's preferred direction: higher for SM, lower for the others.",
    wiki: "variables#comparison-criterion",
  },
  criterion: {
    title: "Comparison criterion",
    text: "Rule for considering the LLM superior to a control: significantly better SM, an effect at least small, and no significant worsening in IFN, ICP or NED. The NED condition was added after the pilot.",
    wiki: "variables#comparison-criterion",
  },
  criterionRoteiro: {
    title: "Roteiro's criterion",
    text: "The criterion as written in the roteiro, without the NED condition. It is reported beside the adopted criterion, to show the effect of the change.",
    wiki: "variables#comparison-criterion",
  },
  export: {
    title: "Export",
    text: "CSV: every value, with a decimal point. LaTeX: a table ready for the article. SVG and PNG: the figure, in the light theme.",
    wiki: "analysis#export",
  },
  provider: {
    title: "Provider",
    text: "The company or server that hosts the model: OpenAI, Anthropic, Google, a compatible server or Ollama, which runs local models on this machine. Each has its own adapter.",
    wiki: "treatment#model-and-profiles",
  },
  modelId: {
    title: "Model",
    text: "Identifier of the model at the provider, such as gpt-5.6-luna. The button beside it lists the models available to your account.",
  },
  temperature: {
    title: "Temperature",
    text: "Controls how much the answers vary. Empty: no value is sent and the provider's default applies; some models accept only the default.",
    wiki: "variables#state-variables",
  },
  maxTokens: {
    title: "Output limit",
    text: "Maximum number of tokens the model may generate per answer, including reasoning. It also caps the cost of each attempt.",
  },
  apiSeed: {
    title: "API seed",
    text: "A seed sent to the provider, when it accepts one. It does not guarantee identical answers and differs from the experiment's master seed. For local models it stays empty: each attempt gets a seed derived from the master seed.",
    wiki: "treatment#local-models",
  },
  requestOptions: {
    title: "Request options",
    text: "Extra parameters sent with every call, in JSON, such as the reasoning effort. They are part of the controlled model configuration. For a local model they include the context window (options.num_ctx), which is required.",
    wiki: "treatment#model-and-profiles",
  },
  clientOptions: {
    title: "Client options",
    text: "How the tool connects to the provider: key variable, timeout and, for compatible servers, the address. They do not change what the model receives.",
  },
  keyVariable: {
    title: "Key variable",
    text: "Name of the environment variable that holds the API key. The key is never stored in a file or sent to the browser.",
    wiki: "tool#keys-and-costs",
  },
  timeout: {
    title: "Timeout (timeout_s)",
    text: "Seconds to wait for an answer from the provider before giving up on the call. Models with long reasoning need high values.",
  },
  baseUrl: {
    title: "Server address (base_url)",
    text: "Address of the model server: the Ollama of this machine at http://127.0.0.1:11434 (provider ollama), or the base URL of a server compatible with the OpenAI API, ending in /v1.",
  },
  apiKey: {
    title: "API key",
    text: "Whether the key was found in the environment variables. Without it, the profile cannot call the model.",
    wiki: "tool#keys-and-costs",
  },
  price: {
    title: "Price",
    text: "Dollars per million input and output tokens, copied from the provider's pricing page. They feed the cost and the estimate.",
    wiki: "tool#keys-and-costs",
  },
  priceSource: { title: "Price source and date", text: "The page consulted and the date, so that the recorded cost can be checked later." },
  profileName: {
    title: "Profile name",
    text: "Identifies the profile and its runs in the database. To test another model or other parameters, create another profile.",
  },
  experimentId: {
    title: "Identifier",
    text: "Name of the configuration in the database. It is what the command line takes in --experiment. A configuration may have an experiment name different from its identifier.",
  },
  experimentName: {
    title: "Experiment name",
    text: "Name that identifies the runs and results in the database. Configurations with the same name and different applications form one experiment with several applications.",
  },
  masterSeed: {
    title: "Master seed",
    text: "The number every random draw of the experiment derives from, such as the obfuscation and the random partitions. The same seed repeats the draws.",
    wiki: "tool#reproducibility",
  },
  acceptedRuns: {
    title: "Accepted runs per variant",
    text: "How many valid LLM answers the experiment needs for each variant. The plan has 10 per application.",
    wiki: "design#unit-of-analysis-and-replication",
  },
  maxRetries: {
    title: "Re-sends of an invalid output",
    text: "How many times an invalid answer is sent again with the same prompt, without feedback to the model. With 3, each run has up to 4 attempts.",
    wiki: "treatment#retries",
  },
  maxFailedRuns: {
    title: "Failed-run limit",
    text: "The run stops after this many failed runs (all attempts invalid), so as not to spend without results.",
  },
  database: {
    title: "Database",
    text: "MongoDB database where runs and results are stored. The monosplit database holds the study data, and its readable copy (monosplit db dump) goes to git; the dry run uses monosplit_dry_run, which stays out of the dump.",
    wiki: "tool#data-storage",
  },
  defaultProfile: { title: "Default profile", text: "Profile used when the run does not choose another one." },
  ahVariants: {
    title: "AH variants measured",
    text: "AH variants computed for each run. All of them enter the selection; only the chosen one becomes the control.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  ahPrimary: {
    title: "AH control",
    text: "Automatic: the variant with the highest median SM over the accepted runs wins, which selects on the dependent variable itself. To fix a variant, as in the final experiment, choose it here.",
    wiki: "controls#hierarchical-clustering-ah",
  },
  hdbscanMin: {
    title: "Minimum cluster size",
    text: "The smallest group HDBSCAN accepts as a service; each class that fits no group becomes a service of its own.",
    wiki: "controls#hdbscan",
  },
  placeholders: {
    title: "Placeholders",
    text: "Pieces such as $class_list and $edge_list that the tool replaces with the application's data before sending the prompt.",
    wiki: "treatment#prompt",
  },
  sha: { title: "SHA-256", text: "Digest of the prompt text. It changes with any change to the text and is recorded with every run." },
  usage: {
    title: "Studies",
    text: "Studies that already use this item. Items in use are locked, so that what has already run does not change.",
  },
  appId: { title: "Identifier", text: "Short name of the application, used as its key in the database." },
  repository: { title: "Repository", text: "Git address the application is cloned from.", wiki: "graph#extraction" },
  build: {
    title: "Build",
    text: "How to compile the application: with the project's own Maven wrapper (mvnw), with the Maven installed by MonoSplit or with the project's Gradle wrapper (gradlew). Gradle must be 8.5 or later to run on the study's JDK 21.",
    wiki: "graph#extraction",
  },
  buildArgs: {
    title: "Build arguments",
    text: "Options passed to Maven. For JPetStore they turn off the plugins that rewrite sources, so that the compiled code matches the commit.",
    wiki: "graph#extraction",
  },
  sourceRoots: { title: "Source folders", text: "Where the application's .java files are, such as src/main/java. Tests are excluded." },
  classDirs: {
    title: "Compiled class folders",
    text: "Where the build writes the .class files that javap reads, such as target/classes.",
    wiki: "graph#extraction",
  },
  appStatus: { title: "Status", text: "Whether the application has been cloned and whether its call graph has been extracted." },
  note: { title: "Note", text: "Free text about the application, such as the reason for the chosen version." },
  operation: {
    title: "Operation",
    text: "Runs, controls and report: the whole procedure. Runs only: calls the model. Controls only: recomputes AH, the random partition, the metrics and the report, without calling the model.",
  },
  estimate: {
    title: "Estimate",
    text: "Forecast of tokens and cost before running, based on previous attempts or on approximations. The maximum cost assumes the worst case.",
    wiki: "tool#keys-and-costs",
  },
  missing: { title: "Missing", text: "Accepted runs still needed to reach the configured number." },
  tokensPerAttempt: {
    title: "Tokens per attempt",
    text: "Input (prompt) and output (answer) tokens expected in each attempt: observed in previous attempts or approximated.",
  },
  attemptsExpected: {
    title: "Expected and maximum attempts",
    text: "Expected: with the observed acceptance rate. Maximum: the missing runs using every re-send, up to the failure limit.",
  },
  expectedCost: { title: "Expected cost", text: "Likely cost of the run, with the expected tokens and attempts." },
  maxCost: {
    title: "Maximum cost",
    text: "Upper bound of the cost: every attempt uses the output limit, and runs fail up to the configured limit.",
  },
  secondsPerAttempt: {
    title: "Time per attempt",
    text: "Mean time of the earlier attempts of this variant, from sending the prompt to the end of the answer. For a local model it includes loading the model into memory when it is not loaded.",
  },
  expectedTime: {
    title: "Expected time",
    text: "Expected attempts times the mean time per attempt. A local model bills nothing, so time is the cost that counts.",
    wiki: "treatment#local-models",
  },
  dryRun: {
    title: "Dry run",
    text: "Runs the whole procedure with a fake client that calls no model and costs nothing. Its numbers test the tool; they are not data.",
    wiki: "glossary#terms",
  },
  extractGraph: {
    title: "Graph extraction",
    text: "Clones the application at the pinned commit, compiles the code and reads it with javap to build the call graph.",
    wiki: "graph#extraction",
  },
  jobs: {
    title: "Jobs",
    text: "Operations sent to the local server. They run one at a time; a cancelled run continues from where it stopped when started again.",
  },
  configNote: {
    title: "Notes",
    text: "Free text kept with the configuration: why it exists, sources consulted and decisions. It enters neither the prompt nor any computation.",
    wiki: "tool#data-storage",
  },
  documents: {
    title: "Documents per collection",
    text: "How many records the database holds in each collection: configuration, graphs, variants, attempts, evaluations, metrics, notes and change log.",
    wiki: "tool#data-storage",
  },
  attemptStatus: {
    title: "Attempt status",
    text: "Accepted: the answer passed the acceptance rule and became a run. Invalid: the answer was refused and the run re-sends the prompt. API error: the call failed and does not count as an answer.",
    wiki: "treatment#acceptance-rule",
  },
  tryNumber: {
    title: "Attempt in the run",
    text: "Position of the attempt within its run: 1 is the first sending; the next ones are re-sends after an invalid answer.",
    wiki: "treatment#retries",
  },
  answerText: {
    title: "Answer text",
    text: "What the model answered, exactly as it arrived. The acceptance rule looks for the JSON object of the decomposition in it.",
    wiki: "treatment#acceptance-rule",
  },
  acceptedPartition: {
    title: "Accepted partition",
    text: "The service assigned to each class, with the real class names (in the obfuscated variant, the codes are already translated back).",
    wiki: "treatment#acceptance-rule",
  },
  rawResponse: {
    title: "Full API response",
    text: "The document returned by the provider, with identifier, finish reason and token counts. It is kept for auditing.",
    wiki: "tool#data-storage",
  },
  edgeVerdict: {
    title: "Edge confirmed",
    text: "Result of the manual check: yes when the listed lines contain the calls, no when they do not. Empty: not checked yet.",
    wiki: "graph#manual-check",
  },
  edgeNote: {
    title: "Edge notes",
    text: "A remark by whoever checked it, for example the exact line or why an edge was not confirmed.",
    wiki: "graph#manual-check",
  },
  callSites: {
    title: "Places in the code",
    text: "Up to three calls that form the edge, as file:line method -> class.method, relative to the application folder.",
    wiki: "graph#manual-check",
  },
  studyNote: {
    title: "Note on the study",
    text: "The researcher's free text about the study. It is kept in the database and in the dump, apart from the runs.",
    wiki: "tool#data-page",
  },
  recompute: {
    title: "Recompute",
    text: "Redoes the controls, metrics and report from the stored runs, with the chosen configuration. It calls no model.",
    wiki: "tool#data-page",
  },
  deleteStudy: {
    title: "Delete study",
    text: "Deletes every variant, attempt, evaluation and metric of the study, and its note, after writing a full copy of the database to work/backups/.",
    wiki: "tool#data-page",
  },
  auditAction: {
    title: "Action",
    text: "Kind of change: creation, change, deletion, import of earlier files, graph extraction or drawing of the edge sample.",
    wiki: "tool#data-page",
  },
  auditSource: {
    title: "Source",
    text: "Where the change came from: the interface, the command line or the import of the files of earlier versions.",
    wiki: "tool#data-page",
  },
  collection: {
    title: "Collection",
    text: "The set of documents in the database that received the change, such as profiles, experiments or graphs.",
    wiki: "tool#data-storage",
  },
  protectedDefault: {
    title: "Default of the tool",
    text: "Item that comes with the tool: the dry_run experiment, the jpetstore application it uses, the fake profile, the decomposition_base prompt and the profile templates (names starting with _). It can be edited but not deleted. Other items can be deleted when nothing uses them.",
    wiki: "tool#data-storage",
  },
};
