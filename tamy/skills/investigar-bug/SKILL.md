---
name: investigar-bug
description: "Investigar um bug ou incidente da Tamy: ler metricas, logs, traces do Langfuse e o codigo, e apontar a causa provavel com hipoteses, links e o que conferir. Use apos criar o chamado ou quando perguntarem \"por que\" algo quebrou."
---

## Objetivo
Entregar a quem vai trabalhar o chamado: onde provavelmente esta a causa, as evidencias e o que conferir. Hipotese, nao sentenca.

## Roteiro (carregue antes `tamy-ambiente`)
1. **Delimite**: area, loja ou cliente, data e hora, canal. Se faltar, leia o chamado e o fio.
2. **Metricas** (Prometheus), janela de 2 h antes do pedido: 5xx por rota, tarefas Celery que falharam, turno medio do chat. So afirme o que tem serie: serie ausente nao e "sem falha".
3. **Logs** (Loki): `{service="api-server"}` e `{service="background"}` com erro, na janela e perto do horario. Cite hora e a linha-chave, sem dado de cliente.
4. **Chat** (se envolver a Tamy respondendo): Langfuse, sessao da conversa; veja o trace que falhou, a ferramenta chamada e o erro.
5. **Codigo**: comece pelos caminhos da area (ver `tamy-ambiente`), ache a funcao que produz o numero ou a tela errada, leia, e compare o que ela faz com o que o chamado diz que deveria. Cite `arquivo:linha` que voce LEU. Nunca invente caminho.
6. **Duplicata**: busque no Jira chamados parecidos dos ultimos 60 dias.

## Entrega (um comentario no chamado, texto wiki)
`h3. Causa provavel (analise automatica)` com ate 3 hipoteses `arquivo:linha - por que`, **Confianca: alta|media|baixa**, `h3. Evidencias` (metrica e valor, linha de log com hora, link do trace, links do Grafana e GlitchTip), `h3. O que conferir` (passos para reproduzir ou confirmar), e a linha "Hipotese de um agente. Confirme antes de agir.". Sem causa clara: diga que nao achou e a confianca e baixa.

## Limites
So leitura na investigacao. Nada de dado de cliente no comentario. Escrever no Jira so com o clique de aprovacao.
