"""Where a problem lives: the channel the person used, and the screen or feature.

Both come from a closed list. The classifier picks from it, the ticket carries it
as a Jira label (`canal-whatsapp`, `area-dre`), and the description points to the
code and the dashboard of the area: the first places a developer opens.

Free text would split one problem into many spellings and point nowhere. A new
screen gets a line here, and a test checks that every pointer still exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DASHBOARD_API = "tamy-api-performance"
DASHBOARD_CHAT = "tamy-chat-performance"
DASHBOARD_BACKGROUND = "tamy-background-performance"


class Channel(StrEnum):
    WEB = "web"
    APP = "app"
    WHATSAPP = "whatsapp"


_CHANNEL_LABEL: dict[Channel, str] = {
    Channel.WEB: "Web, no navegador",
    Channel.APP: "App no celular",
    Channel.WHATSAPP: "WhatsApp",
}


@dataclass(frozen=True)
class Area:
    slug: str
    label: str
    # What the classifier reads to choose: the words an owner or a CS uses.
    hint: str
    # Repository paths, backend first. The first places to open.
    code_paths: tuple[str, ...]
    dashboard_uid: str = DASHBOARD_API


AREAS: tuple[Area, ...] = (
    Area(
        "painel-visao-geral",
        "Painel: visão geral",
        "primeira tela do painel, cartões de resumo, desempenho do dia",
        (
            "backend/onyx/server/features/tamy_painel",
            "web/src/views/painel/PanelOverviewView.tsx",
        ),
    ),
    Area(
        "vendas",
        "Vendas",
        "total de vendas, pedidos, canais de venda, comparação com o PDV",
        (
            "backend/onyx/server/features/tamy_sales",
            "backend/onyx/server/features/tamy_sales_breakdown",
            "web/src/app/painel/vendas",
        ),
    ),
    Area(
        "dre",
        "DRE",
        "demonstrativo de resultado, margem, CMV, lucro do mês",
        (
            "backend/onyx/server/features/tamy_dre",
            "web/src/views/painel/DreView.tsx",
        ),
    ),
    Area(
        "despesas",
        "Despesas",
        "contas a pagar, despesa lançada, categoria de despesa, recorrentes",
        (
            "backend/onyx/server/features/tamy_expenses",
            "backend/onyx/server/features/tamy_recurring",
            "web/src/views/painel/DespesasView.tsx",
        ),
    ),
    Area(
        "estoque",
        "Estoque e insumos",
        "saldo de estoque, contagem, perda, insumo, movimentação",
        (
            "backend/onyx/server/features/tamy_inventory",
            "web/src/views/painel/EstoqueView.tsx",
        ),
    ),
    Area(
        "produtos",
        "Produtos e fichas técnicas",
        "produto, ficha técnica, receita, preço, catálogo",
        (
            "backend/onyx/server/features/tamy_products",
            "web/src/views/painel/ProdutosView.tsx",
        ),
    ),
    Area(
        "fornecedores",
        "Fornecedores",
        "cadastro de fornecedor, compras de um fornecedor",
        (
            "backend/onyx/server/features/tamy_suppliers",
            "web/src/views/painel/FornecedoresView.tsx",
        ),
    ),
    Area(
        "funcionarios",
        "Funcionários",
        "equipe da loja, salário, folha, funcionário cadastrado",
        (
            "backend/onyx/server/features/tamy_employees",
            "web/src/views/painel/FuncionariosView.tsx",
        ),
    ),
    Area(
        "bancos",
        "Bancos e extratos",
        "conta bancária, extrato, conciliação, saldo do banco",
        (
            "backend/onyx/server/features/tamy_banking",
            "web/src/views/painel/BancosView.tsx",
        ),
    ),
    Area(
        "notas-fiscais",
        "Notas fiscais",
        "NF-e, nota de compra, leitura de nota, importação de nota",
        (
            "backend/onyx/server/features/tamy_fiscal",
            "backend/onyx/tamy/captura",
            "web/src/views/painel/importacao",
        ),
    ),
    Area(
        "receitas",
        "Receitas e faturamento",
        "receita, faturamento, bruto e líquido, taxa de plataforma",
        ("backend/onyx/server/features/tamy_revenues",),
    ),
    Area(
        "chat",
        "Chat com a Tamy",
        "conversa com a Tamy, resposta errada, a Tamy não entendeu, ferramenta do chat",
        (
            "backend/onyx/chat",
            "backend/onyx/tools/tool_implementations",
            "web/src/sections/chat",
        ),
        DASHBOARD_CHAT,
    ),
    Area(
        "whatsapp",
        "Tamy no WhatsApp",
        "mensagem no WhatsApp, número vinculado, template, áudio ou foto no WhatsApp",
        (
            "backend/onyx/onyxbot/whatsapp",
            "backend/onyx/server/features/tamy_whatsapp",
            "web/src/sections/whatsapp",
        ),
        DASHBOARD_CHAT,
    ),
    Area(
        "integracoes",
        "Integrações (iFood, Saipos, PDV)",
        "conexão com iFood, Saipos, Bob's, PDV, sincronização de vendas",
        (
            "backend/onyx/connectors/business_integrations",
            "backend/onyx/server/features/tamy_business_integrations",
            "web/src/sections/business-integrations",
        ),
        DASHBOARD_BACKGROUND,
    ),
    Area(
        "onboarding",
        "Cadastro e primeiros passos",
        "criar conta, cadastrar a empresa, ativação do novo usuário",
        (
            "backend/onyx/server/features/tamy_onboarding",
            "web/src/sections/onboarding",
        ),
    ),
    Area(
        "plano-e-cobranca",
        "Plano, créditos e cobrança",
        "plano, crédito, cupom, assinatura, pagamento, Asaas",
        (
            "backend/onyx/server/features/tamy_billing",
            "backend/onyx/server/features/tamy_plan",
            "web/src/sections/plan",
        ),
    ),
    Area(
        "avisos",
        "Avisos e notificações",
        "mensagem proativa da Tamy, push, e-mail, aviso de integração parada",
        (
            "backend/onyx/server/features/tamy_notifications",
            "backend/onyx/tamy/touch_delivery.py",
        ),
        DASHBOARD_BACKGROUND,
    ),
    Area(
        "conhecimento",
        "Conhecimento (documentos)",
        "documentos enviados, pastas de conhecimento, busca em documentos",
        (
            "backend/onyx/server/features/tamy_knowledge",
            "web/src/views/knowledge",
        ),
    ),
    Area(
        "metas-e-operacao",
        "Metas e operação",
        "meta de vendas, fechamento do dia, turno, operação da loja",
        ("backend/onyx/server/features/tamy_operation",),
    ),
    Area(
        "parceiros",
        "Parceiros e franqueados",
        "painel de parceiro, comissão, franqueado",
        (
            "backend/onyx/server/features/tamy_partners",
            "web/src/views/parceiros",
        ),
    ),
    Area(
        "backoffice",
        "Backoffice (time Tamy)",
        "tela do admin, fila de chamados, cliente 360, equipe do Backoffice",
        (
            "backend/onyx/server/features/tamy_backoffice",
            "web/src/views/admin",
        ),
    ),
    Area(
        "login-e-conta",
        "Login, convite e conta",
        "entrar, senha, convite, perfil, acesso de uma pessoa",
        ("backend/onyx/auth", "web/src/views/auth"),
    ),
    Area(
        "configuracoes",
        "Configurações",
        "tela de configurações, preferências da empresa e da loja",
        (
            "backend/onyx/server/features/tamy_settings",
            "web/src/views/settings",
        ),
    ),
    Area("outro", "Outro", "nenhuma das áreas acima", ()),
)

_BY_SLUG = {area.slug: area for area in AREAS}


def area_by_slug(slug: str) -> Area | None:
    return _BY_SLUG.get(slug)


def area_label(slug: str) -> str:
    area = _BY_SLUG.get(slug)
    return area.label if area else slug


def channel_label(channel: Channel) -> str:
    return _CHANNEL_LABEL[channel]


def clean_area(value: object) -> str | None:
    """The slug when `value` is exactly one of the list, else None. A model that
    answers a sentence gets no label, never a made-up one."""
    if not isinstance(value, str):
        return None
    slug = value.strip().lower()
    return slug if slug in _BY_SLUG else None


def clean_channel(value: object) -> Channel | None:
    if not isinstance(value, str):
        return None
    try:
        return Channel(value.strip().lower())
    except ValueError:
        return None


def classifier_catalog() -> str:
    """The areas as the classifier reads them: `slug = what it is`."""
    return "\n".join(f"- {area.slug}: {area.hint}" for area in AREAS)
