---
name: chamado-incidente
description: "Criar um chamado de incidente: producao machucando clientes agora e a causa nao e conhecida (fora do ar, lento, dado errado sendo salvo, um cliente vendo dado de outro)."
---

Issuetype Jira: `Bug`. Rotulo `tipo-incidente`. Prioridade P0 ou P1; prazo 1 dia util.
Um dado errado para UMA loja e bug, nao incidente.

## Perguntas
O que esta fora do ar ou errado e quem nao consegue usar - desde quando (data e hora) - quantos clientes ou lojas - ha dado errado sendo salvo, ou dado de um cliente a mostra para outro - usuarios afetados (e-mails) - contorno.

## Secoes
O que esta acontecendo - Impacto (desde, alcance, risco para o dado) - Contorno - Usuarios afetados - Onde olhar primeiro - Evidencias - Criterios de aceite (volta a funcionar para todos, os afetados sao avisados, causa e prevencao registradas).

## Depois
Rode `investigar-bug` na hora e comente o resultado. Em risco de vazamento entre clientes, avise o time no canal e diga que e P0.
