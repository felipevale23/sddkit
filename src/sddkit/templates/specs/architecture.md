# Arquitetura

[PREENCHER — visão geral do sistema; apague este marcador quando preencher.]

Fonte da verdade da arquitetura. Atualize no mesmo commit da mudança que a altera (o `/sdd-change` cobra isso)
e mantenha alinhado com `.specify/memory/constitution.md`.

## Visão geral
Serviços/pacotes, quem fala com quem e por qual canal (HTTP, fila, socket, eventos). Um diagrama mermaid ajuda.

## Componentes
Para cada serviço/pacote: responsabilidade, pasta, tecnologia, dependências.

## Mapa do código
Pontos de entrada por área, para o agente não redescobrir o código a cada sessão. Uma linha por área, só caminhos
(o `sddkit doctor` acusa caminho que deixou de existir); detalhe fica em Componentes. Exemplo:
- api — entrada `<app>/src/index.ts` · rotas `<app>/src/routes/` · testes `<app>/test/`

## Fluxos críticos
Sequências que atravessam serviços (ex.: processamento assíncrono, autenticação).

## Dados
Coleções/tabelas e donos de cada uma; filas, tópicos e caches.

## Implantação
Ambientes, containers, proxy, segredos (onde ficam, nunca o valor).
