---
name: chamado-bug
description: "Criar um chamado do tipo bug: algo que funcionava parou, ou da resultado errado. Use junto com chamado-regras."
---

Issuetype Jira: `Bug`. Rotulo `tipo-bug`.

## Perguntas (so as que faltam; as 4 primeiras sao obrigatorias)
Cliente (organizacao, loja ou e-mail) - Passos, um por linha - O que esperava - O que aconteceu (com os valores). Opcionais: quando (data e hora), so ele ou mais clientes, usuarios afetados (e-mails), contorno, tem print ou video, canal.

## Secoes da descricao
Impacto (alcance, quando, canal) - Passos para reproduzir (lista numerada) - Esperado - Obtido - Contorno - Usuarios afetados - Onde olhar primeiro (caminhos do codigo da area) - Evidencias (so a contagem de arquivos e os links, nunca o nome do arquivo) - Criterios de aceite - Perguntas em aberto.

## Criterio de aceite bom
"Dado a loja 3 em 25/10/2026, quando abrir Vendas, entao o total e R$ 1.300,00, igual ao PDV." Nunca generico. Inclua sempre: "existe um teste automatizado que falha sem o conserto".

## Depois
Rode a skill `investigar-bug` e cole o resultado como comentario.
