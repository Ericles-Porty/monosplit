# Uso da ferramenta

## Páginas da interface

| Página | Uso |
|---|---|
| Wiki | Estas páginas |
| Visão geral | Estudos encontrados no banco de dados, custo das execuções e grafos das aplicações |
| Configuração | Perfis de modelo, versões de prompt, aplicações e experimentos; só na versão local |
| Execução | Extração do grafo, rodadas do modelo, controles e relatório, com estimativa de custo; só na versão local |
| Decomposições | Grafo de cada decomposição, com até três métodos lado a lado, comparação entre execuções e resposta do modelo |
| Resultados | Métricas por método, diferenças pareadas, testes de hipótese (no experimento completo), seleção do AH e estabilidade, com exportação de figuras e tabelas |
| Dados | Estudos, tentativas e respostas do modelo só para leitura, conferência das arestas, notas, exclusão de estudos e registro de alterações; só na versão local |

Na página Decomposições, cada classe fica na mesma posição em todos os painéis, e a cor indica o serviço. Os painéis 2 e 3 repetem a cor do serviço do painel 1 com maior sobreposição de classes. A paleta só distingue todos os pares de cores até 3 serviços; a partir de 4, o número do serviço acompanha o nome da classe.

## Linha de comando

Os comandos rodam na pasta `experimento/`:

```
docker compose up -d                           # inicia o MongoDB (compose.yaml)
uv run python -m monosplit db status            # conexão e documentos por coleção
uv run python -m monosplit jdk install          # instala o JDK fixado (Temurin 21)
uv run python -m monosplit app fetch jpetstore  # clona a aplicação no commit fixado
uv run python -m monosplit extract jpetstore    # compila e extrai o grafo de chamadas
uv run python -m monosplit edge-sample jpetstore
uv run python -m monosplit prompt --experiment <configuração> --variant obfuscated
uv run python -m monosplit all --experiment <configuração> --llm <perfil>
uv run python -m monosplit web serve --open     # interface em http://127.0.0.1:8765/
uv run python -m monosplit web export           # site estático em work/site/
uv run python -m monosplit db dump dump         # cópia legível do banco em dump/monosplit/
uv run python -m monosplit db restore dump      # recria o banco num servidor vazio
```

Os experimentos e os perfis são chamados pelos nomes que têm na página Configuração.

## Armazenamento dos dados

A configuração, os grafos, as execuções e os resultados ficam num banco MongoDB local, que é o registro principal do estudo. O arquivo `compose.yaml` sobe o servidor no Docker; a variável de ambiente `MONOSPLIT_MONGO_URI` aponta para outro servidor, se for o caso. A configuração e os grafos ficam no banco `monosplit`. Cada experimento grava as execuções no banco indicado no seu campo `database`: o estudo usa o `monosplit`, e o ensaio a seco usa o `monosplit_dry_run`.

| Coleção | Um documento por |
|---|---|
| `apps` | aplicação: repositório, *commit* fixado e forma de compilar |
| `profiles` | perfil de modelo; os nomes que começam com `_` são modelos de perfil |
| `prompts` | versão do prompt, nunca sobrescrita |
| `experiments` | configuração de experimento |
| `graphs` | aplicação: classes, arestas, pontos de chamada e conferência manual das arestas |
| `variants` | variante de um estudo: configuração da rodada, prompt enviado e mapa de nomes |
| `attempts` | tentativa: registro, resposta completa e, se aceita, a partição |
| `evaluations` | estudo avaliado: seleção do AH, diferenças pareadas, partições medidas e relatório |
| `metrics` | linha de métrica da avaliação atual |
| `notes` | estudo com nota do pesquisador |
| `audit` | alteração feita pela interface ou pela linha de comando |

Os itens que vêm com a ferramenta não podem ser excluídos, mas podem ser editados: o experimento `dry_run`, a aplicação `jpetstore` que ele usa, o perfil `fake`, o prompt `decomposition_base` e os modelos de perfil. Os demais podem ser excluídos quando nenhuma execução ou configuração os usa. Os padrões ficam também no código da ferramenta, que recria os que faltarem quando um comando abre o banco.

Cada configuração tem um campo de notas, de texto livre. Os comentários dos arquivos de configuração das versões anteriores viraram essas notas na importação (`db import-config`).

Cada tentativa é gravada de uma vez, e um índice único impede gravar duas vezes a mesma tentativa ao retomar uma rodada. Uma avaliação nova grava suas linhas antes de substituir a anterior, de modo que a interface nunca mostra duas avaliações misturadas.

O comando `db dump` grava o banco em arquivos JSON Lines (um documento JSON por linha, *JavaScript Object Notation*), com ordem fixa, na pasta `dump/`, que fica no git e forma o pacote de replicação. O comando `db restore` recria o banco a partir dessa cópia num servidor vazio.

## Página Dados

A página Dados mostra o conteúdo de cada banco. As tentativas, as respostas do modelo, as partições aceitas e as métricas aparecem só para leitura: são a evidência do experimento e só a execução e a avaliação as gravam. A página permite três tipos de alteração:

- a conferência manual das arestas de cada aplicação, com o resultado (sim ou não) e uma nota por aresta;
- a nota de um estudo, em texto livre;
- a exclusão de um estudo inteiro, por exemplo uma rodada feita com a configuração errada. Antes da exclusão, uma cópia completa do banco vai para `work/backups/`, fora do git.

O recálculo de controles, métricas e relatório também pode ser pedido nessa página; ele não chama o modelo.

Cada alteração, inclusive as feitas na página Configuração, gera um documento na coleção `audit` do banco alterado, com data, ação, origem e os valores antes e depois. A aba Registro de alterações lista esses documentos, que também entram no dump.

## Reprodutibilidade

- Cada aplicação fica fixada num *commit*; a extração recusa uma cópia com mudanças locais.
- Os metadados do grafo registram as versões do JDK (*Java Development Kit*) e do `javap` e as regras de contagem.
- Cada passo aleatório tem uma semente derivada da semente mestre do experimento, registrada junto ao resultado.
- Cada tentativa registra o modelo informado pela API (*Application Programming Interface*), os tokens, o tempo, o custo e a resposta completa; o prompt fica gravado exatamente como enviado.
- As versões das dependências ficam em `uv.lock`, para o Python, e em `web/package-lock.json`, para a interface.

## Chaves e custos

As chaves de API são lidas de variáveis de ambiente e nunca são enviadas ao navegador. Antes de uma rodada paga, a página Execução mostra a estimativa de tokens e de custo e pede confirmação; o servidor recusa a rodada se a estimativa mudar depois de exibida. Um modelo local, no Ollama, não precisa de chave nem de confirmação: a estimativa mostra o tempo esperado, medido nas tentativas anteriores, e avisa quando o Ollama não está no ar ou o modelo não foi baixado (`ollama pull <modelo>`). As rotas que gravam no banco de dados aceitam só pedidos da própria interface, numa origem local.

## Site estático

O comando `web export` gera uma cópia só de leitura da interface, com os dados embutidos, que funciona em qualquer servidor de arquivos estáticos ou subpasta. Essa cópia não tem as páginas Configuração, Execução e Dados. As exportações da página Resultados funcionam nela, porque são feitas no próprio navegador.
