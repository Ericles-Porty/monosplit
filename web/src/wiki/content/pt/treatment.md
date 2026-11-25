# Tratamento: o LLM

## Modelo e perfis

O tratamento é um modelo de linguagem de grande porte (LLM, *Large Language Model*) de uso geral, sem ajuste fino e sem arcabouço especializado. Cada modelo é descrito por um perfil, guardado no banco de dados e editado na página Configuração, com provedor, modelo, parâmetros da requisição (por exemplo, o esforço de raciocínio) e preços. As execuções de cada perfil ficam separadas no banco de dados, identificadas pelo nome do perfil.

O experimento final usou o modelo `gpt-6.1-sol` da OpenAI com `reasoning_effort` high (perfil `gpt-6.1-sol-high`), escolhido depois das execuções do piloto. A temperatura não é enviada: vale o padrão da API, e o registro de cada tentativa diz isso.

A camada `src/monosplit/llm/` define uma interface comum e um adaptador por provedor: OpenAI, Anthropic, Google, servidores compatíveis com a API (*Application Programming Interface*) da OpenAI e o Ollama, que roda modelos de pesos abertos nesta máquina (seção Modelos locais, abaixo). Testar outro modelo exige só um perfil novo.

O modelo é uma variável controlada. Não há troca automática de modelo pelo provedor, e o modelo informado pela API fica registrado em cada tentativa.

## Prompt

O prompt `decomposition_base`, guardado no banco de dados, foi escrito antes das execuções do piloto, com o nome `decomposition_v1`. Ele envia os nomes completos das classes e a lista de arestas com o número de chamadas, pede que cada classe fique em exatamente um serviço, deixa o modelo escolher *K* (no mínimo 2) e pede só um objeto JSON (*JavaScript Object Notation*). O prompt não cita nenhuma métrica nem faixa de tamanho, para que o tratamento não seja ajustado às variáveis dependentes.

Uma versão de prompt nunca é sobrescrita. A página Configuração cria `decomposition_v2`, `decomposition_v3` e assim por diante, e cada execução registra o resumo criptográfico do texto exato que foi enviado.

## Regra de aceitação

Uma resposta é aceita quando:

1. contém um objeto JSON, puro, num bloco de código ou cercado de texto;
2. o objeto segue o formato `{"microservices": [{"name": "...", "classes": ["..."]}]}`;
3. cada nome de classe é uma das classes enviadas no prompt;
4. nenhuma classe aparece mais de uma vez;
5. todas as classes enviadas aparecem;
6. há pelo menos dois serviços não vazios.

Serviços sem classes são descartados e contados, sem rejeitar a resposta. A primeira verificação que falha é o motivo da rejeição: `invalid_json`, `invalid_schema`, `unknown_class`, `duplicate_class`, `missing_class` ou `too_few_services`; uma recusa do provedor é registrada como `refusal`.

## Repetições

Uma saída inválida é reenviada com o mesmo prompt, sem retorno ao modelo, até 3 vezes, o que dá até 4 tentativas por execução. Assim, cada saída aceita é uma amostra sem exemplos (*zero-shot*). Uma execução com 4 tentativas inválidas é uma execução falha, e todas as tentativas entram na contagem. Erros da API, como falhas de rede ou limite de taxa, não são saídas do modelo: ficam registrados e interrompem a rodada, que continua do ponto em que parou quando é iniciada de novo.

## Variante com nomes ofuscados

As classes são renomeadas para C01, C02 e assim por diante, numa ordem aleatória com semente, que não segue os pacotes. As arestas e o modelo do prompt são os mesmos da variante original. A página Decomposições mostra os nomes que o modelo recebeu.

## Registro

Cada tentativa grava o prompt exatamente como enviado, a resposta bruta, o modelo informado pela API, os tokens de entrada e de saída, o tempo e o custo calculado com os preços do perfil. Uma variante iniciada com uma configuração (modelo, parâmetros, prompt e grafo) recusa ser retomada com outra.

## Modelos locais

Um modelo de pesos abertos foi planejado como replicação separada, fora do fator principal, como o roteiro admite: o mesmo prompt, as mesmas aplicações e variantes e a mesma regra de aceitação, com um perfil próprio. A replicação foi pilotada com o gpt-oss:20b e o qwen3.5:4b e depois abandonada: nesta máquina, com 6 GB de memória de vídeo, uma tentativa levou de 6 a 57 minutos, e no AcmeAir e no DayTrader a maioria das respostas não passou na regra de aceitação. O estudo relata isso como limitação. A ferramenta continua rodando modelos locais, como descrito abaixo. O provedor `ollama` chama o Ollama desta máquina pela API nativa do servidor. A API compatível com a da OpenAI, que o Ollama também oferece, não serve para o estudo: ela não deixa fixar a janela de contexto por requisição, e o padrão do servidor (4.096 tokens com menos de 24 GB de memória de vídeo) corta sem aviso os prompts maiores, como o do DayTrader, com cerca de 10 mil tokens.

- **Janela de contexto.** O perfil fixa `options.num_ctx`, enviado em toda requisição. O servidor recusa um prompt que não cabe, em vez de cortá-lo, e a ferramenta recusa a configuração quando o prompt e o limite de saída, somados, não cabem no contexto. Essa recusa é um erro de configuração: interrompe a rodada e não conta como tentativa.
- **Semente.** Com a mesma semente e o mesmo prompt, o Ollama pode devolver a mesma resposta em todas as tentativas. Por isso cada tentativa recebe uma semente própria, derivada da semente mestre, do nome do experimento, da aplicação, do perfil, da variante e do número da tentativa, e gravada com ela, de modo que as execuções variam entre si. Nos testes com dois modelos, repetir uma tentativa com a sua semente deu a mesma resposta num deles. No outro, a parte do prompt que o servidor reaproveita do cache entre as tentativas muda a cada chamada, e a resposta muda com ela.
- **Identidade do modelo.** Uma tag do Ollama pode passar a apontar para outros pesos. Cada variante grava o resumo criptográfico (*digest*) dos pesos, a quantização, os parâmetros padrão do modelo e a versão do servidor, e não continua com outros pesos. Cada tentativa grava a versão do servidor, o contexto alocado e a parte do modelo na memória da GPU. Modelos da nuvem do Ollama, que não rodam nesta máquina, são recusados.
- **Temperatura e raciocínio.** Sem temperatura no perfil, vale o padrão do próprio modelo, que fica gravado. O nível de raciocínio, quando o modelo tem, vai nas opções da requisição (`think`). O texto do raciocínio fica na resposta bruta; só a resposta final passa pela regra de aceitação.
- **Formato da saída.** A saída estruturada do Ollama, que restringe a geração a um esquema JSON, não é usada: o tratamento é o mesmo prompt enviado aos modelos hospedados.
- **Custo.** Nada é cobrado. A página Execução começa a rodada sem confirmação e mostra o tempo esperado no lugar do custo.
