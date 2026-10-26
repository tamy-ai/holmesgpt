---
name: chamado-regras
description: "Regras gerais para criar ou editar qualquer chamado no Jira (projeto TA): titulo, prioridade, prazo, rotulos, descricao, duplicata. Carregue antes de criar qualquer chamado."
---

## Antes de criar
1. Busque duplicata no Jira (`text ~ "palavras do titulo"` nos ultimos 30 dias). Se existir, mostre e pergunte se e o mesmo.
2. Descubra o tipo (skill `chamado-<tipo>`): bug, incidente, melhoria, funcionalidade, suporte, acesso, duvida, tarefa. Na duvida, pergunte uma coisa so.
3. Faca so as perguntas que faltam. Nunca pergunte o que o fio ja responde. No maximo 3 perguntas por vez.

## Titulo
Uma linha, ate 100 caracteres: `Area: o que esta errado ou o que se pede`. Com o numero que mostra o problema, quando houver ("DRE: CMV sem embalagem"). Sem a palavra "bug", sem nome de cliente, sem prioridade.

## Prioridade e prazo (dias uteis de Sao Paulo)
- P0 producao quebrada (cliente nao consegue usar, dado errado sendo salvo, um cliente ve dado de outro): 1 dia.
- P1 cliente bloqueado sem contorno, ou muitos afetados: bug 3, suporte 2, acesso 1, melhoria 5.
- P2 funciona mal mas o cliente segue: bug 5, suporte 3, acesso 2, melhoria 10.
- P3 ideia, cosmetico, divida tecnica: sem prazo.
Na duvida entre duas, escolha a MENOS urgente e escreva o motivo numa frase. O desejo de quem pede ("urgente") e um sinal, nao a regra.

## Rotulos (sempre)
`origem-slack`, `tipo-<tipo>`, `sla-p<n>`, `canal-web|app|whatsapp` (quando souber), `area-<tela ou funcionalidade>` (quando souber).

## Descricao (texto wiki do Jira, API v2)
Ordem: `h3. Resumo`, `h3. Contexto` (tipo, prioridade e motivo, cliente, canal, area, pedido em DD/MM/AAAA, pedido por, link do fio), secoes do tipo, `h3. Criterios de aceite` (Dado/Quando/Entao, com a loja, a data e o valor do caso), `h3. Perguntas em aberto` (so o que ninguem respondeu). Datas sempre completas: "ontem" vira DD/MM/AAAA.

## Depois de criar
Responda no fio com a chave, o link, a prioridade e o prazo. Para bug e incidente, siga a skill `investigar-bug` e comente o resultado no chamado.
