# Grafo de chamadas

Os três métodos recebem o mesmo grafo estático de chamadas entre classes, extraído do código compilado de cada aplicação. O código da extração está em `src/monosplit/extraction/`.

## Extração

1. A aplicação é clonada e fixada num *commit*. A extração recusa uma cópia com mudanças locais.
2. O código é compilado com o Maven, pelo *wrapper* do projeto ou pelo Maven 3.9.16 que a ferramenta instala, ou com o *wrapper* do Gradle do projeto, no caso do AcmeAir. No JPetStore, ficam desligados os *plugins* do POM (*Project Object Model*) pai que reescrevem os fontes, e a ferramenta falha se a compilação alterar um arquivo versionado.
3. O `javap -v -p` do Eclipse Temurin 21, um JDK (*Java Development Kit*) instalado pela própria ferramenta, lê o *bytecode* de cada classe. O compilador já resolveu o tipo estático de cada chamada, que um analisador do código-fonte teria de aproximar.

## Regras de contagem

- **Nós:** classes de nível superior de `src/main/java`, incluindo interfaces, *enums* e classes abstratas; os testes ficam de fora. Classes aninhadas, internas e anônimas são somadas à classe de nível superior que as contém.
- **Chamada:** uma instrução de invocação (`invokevirtual`, `invokespecial`, `invokestatic`, `invokeinterface`) ou uma referência de método num `invokedynamic`, como `Item::getListPrice`, cujo alvo é outra classe da aplicação. Chamadas a construtores contam.
- **Alvo:** a classe que declara o membro invocado. Um método herdado é atribuído à superclasse ou interface da aplicação que o declara; membros declarados só em tipos de biblioteca são chamadas a bibliotecas.
- **Não contam:** chamadas dentro da própria classe, chamadas a bibliotecas, acessos a campos, referências de tipo sem chamada e chamadas feitas pelo *framework* em tempo de execução, como as do Stripes, as dos *mappers* do MyBatis em XML (*Extensible Markup Language*) e as expressões das páginas JSP (*JavaServer Pages*).
- **Aresta:** um par ordenado de classes com pelo menos uma chamada; o peso da aresta é o número de chamadas.
- **Classes isoladas** continuam no grafo e precisam ser atribuídas por todos os métodos. No JPetStore, `Category` é isolada: nenhum código Java chama seus métodos, só as páginas JSP a usam.

O JPetStore 6.3.0 tem 24 classes, 40 arestas, 159 chamadas e 1 classe isolada. A versão 6.4.0 trocou a camada web por Spring MVC e tem 25 classes; a 6.3.0 é a última com as 24 classes decompostas na literatura.

O AcmeAir, na implantação com MongoDB, tem 52 classes, 72 arestas, 220 chamadas e 6 classes isoladas: duas interfaces de constantes, cujos valores o compilador copia para quem os usa, e quatro classes que o *framework* ou o servidor encontram por anotações.

## Conferência manual

Uma amostra de 20 arestas, sorteada com semente na extração do grafo, é conferida no código-fonte na página [Dados](#/data?tab=edges). Para cada aresta, a página mostra até três locais da chamada (arquivo e linha); quem confere marca sim, quando as linhas contêm as chamadas, ou não, e pode deixar uma nota. O resultado fica no banco de dados, com o grafo, e cada alteração entra no registro de alterações.

## O que o grafo representa

O grafo é estático: conta os pontos do código em que uma classe invoca outra, e não quantas vezes isso acontece durante a execução. Dependências criadas pelo *framework* em tempo de execução ficam de fora. Essas escolhas valem igualmente para os três métodos, porque todos recebem o mesmo grafo e são medidos com os mesmos scripts.
