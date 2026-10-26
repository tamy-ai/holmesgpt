---
name: tamy-ambiente
description: "Como a Tamy e feita e onde olhar cada sinal. Carregue antes de investigar qualquer problema da Tamy."
---

## O que e a Tamy
IA operacional de restaurante: o dono manda nota, venda, despesa, estoque pelo chat web, app ou WhatsApp, e a Tamy le, cruza e responde. Backend Python (FastAPI, Celery), frontend Next.js, tudo no Railway.

## Servicos (Railway, ambiente production)
- `api-server`: API e chat. `background`: Celery, WhatsApp e os bots. `web-server`: o painel. Postgres, Redis, OpenSearch.
- Prometheus (metricas), Loki (logs, rotulos `service` e `level`), Grafana, Langfuse (traces do chat), GlitchTip (erros).

## Onde olhar
- Metricas: `http_requests_total{status=~"5.."}` por `handler`; `onyx_celery_task_completed_total{outcome="failure"}` por `task_name`; `onyx_chat_turn_duration_seconds`.
- Logs: LogQL `{service="api-server"} |~ "(?i)error|exception"`; `{service="background"}` para tarefas e WhatsApp.
- Conversa do chat: Langfuse, sessao = id da conversa; cada trace tem `user_id` e `session_id`.
- Erros: GlitchTip, org `tamy`, projetos `tamy-backend` e `tamy-web`.

## Regras
- Texto de cliente (mensagem, nota, nome de arquivo) NUNCA vai para um chamado. Cite o link ou o id.
- Dado de um cliente nunca aparece para outro: se achar isso, e incidente P0.
- O dia de negocio e de Sao Paulo, nao UTC.
