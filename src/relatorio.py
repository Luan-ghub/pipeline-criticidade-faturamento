# BIBLIOTECAS
import logging

from datetime import datetime
from html import escape

import pandas as pd

from .config import (
    ARQUIVO_ALERTAS,
    ARQUIVO_KPIS,
    ARQUIVO_RELATORIO,
    PASTA_DE_SAIDAS,
)


# -----------------------------------------------------------------------------
# ETAPA 5. RELATÓRIO E EXPORTAÇÃO
# -----------------------------------------------------------------------------

def formatar_numero(valor: float | int | None, casas: int = 0) -> str:
    """Formata um número no padrão brasileiro."""

    if valor is None or pd.isna(valor):
        return "N/D"

    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor: float | int | None, casas: int = 2) -> str:
    """Formata uma taxa ou variação utilizando o símbolo de porcentagem."""

    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{formatar_numero(valor, casas)}%"


def formatar_variacao_pp(valor: float | int | None) -> str:
    """Formata a diferença entre duas taxas em pontos percentuais."""

    if valor is None or pd.isna(valor):
        return "N/D"

    valor = float(valor)
    numero = formatar_numero(abs(valor), 2)

    if valor > 0:
        return f'<span class="variacao-piora">↑ +{numero} p.p.</span>'

    if valor < 0:
        return f'<span class="variacao-melhora">↓ -{numero} p.p.</span>'

    return '<span class="variacao-estavel">→ 0,00 p.p.</span>'


def criar_grafico_barras(
    kpis_mensais: pd.DataFrame,
    coluna: str,
    cor: str,
) -> str:
    """Cria um gráfico HTML simples para os últimos 12 meses."""

    dados = kpis_mensais.head(12).iloc[::-1]
    maior_valor = max(float(dados[coluna].max() or 0), 0.01)
    linhas = []

    for _, linha in dados.iterrows():
        valor = float(linha[coluna] or 0)
        largura = max(2, 100 * valor / maior_valor)
        mes = str(linha["mes_referencia"])[2:7]
        linhas.append(
            f"""
            <div class="barra-linha">
                <span class="barra-mes">{escape(mes)}</span>
                <div class="barra-fundo">
                    <div class="barra-valor" style="width:{largura:.2f}%; background:{cor};"></div>
                </div>
                <span class="barra-numero">{formatar_percentual(valor)}</span>
            </div>
            """
        )

    return "".join(linhas)


def gerar_resumo_gerencial(
    kpis_mensais: pd.DataFrame,
    alertas_municipios: pd.DataFrame,
) -> list[str]:
    """Produz observações automáticas para apoiar a análise gerencial."""

    ultimo_mes = kpis_mensais.iloc[0]
    observacoes = []

    if len(kpis_mensais) > 1:
        mes_anterior = kpis_mensais.iloc[1]

        for coluna, nome in [
            ("taxa_refaturamento_pct", "A taxa de refaturamento"),
            ("taxa_sem_leitura_pct", "A taxa de faturas sem leitura"),
        ]:
            atual = float(ultimo_mes[coluna] or 0)
            anterior = float(mes_anterior[coluna] or 0)

            variacao_pp = atual - anterior

            if variacao_pp > 0:
                movimento = "aumentou"
            elif variacao_pp < 0:
                movimento = "reduziu"
            else:
                movimento = "permaneceu estável"

            observacoes.append(
                f"{formatar_variacao_pp(variacao_pp)} "
                f"{nome} {movimento} em relação ao mês anterior."
            )

    quantidade_criticos = int(
        (alertas_municipios.get("nivel_alerta") == "CRITICO").sum()
    ) if not alertas_municipios.empty else 0

    observacoes.append(
        f"Foram identificados {len(alertas_municipios)} municípios para análise, "
        f"sendo {quantidade_criticos} classificados como críticos."
    )

    if not alertas_municipios.empty:
        principal_alerta = alertas_municipios.iloc[0]
        observacoes.append(
            "O primeiro item da fila é o município IBGE "
            f"{principal_alerta['codigo_municipio']}, por "
            f"{principal_alerta['motivo_alerta'].lower()}."
        )

    observacoes.append(
        "Os alertas representam prioridades de investigação e não confirmam erro de faturamento."
    )
    return observacoes


def preparar_tabela_alertas(alertas_municipios: pd.DataFrame) -> str:
    """Organiza e formata a tabela gerencial de alertas."""

    if alertas_municipios.empty:
        return '<p class="sem-dados">Nenhum alerta foi encontrado no período mais recente.</p>'

    tabela = alertas_municipios.copy()
    tabela = tabela[
        [
            "nivel_alerta",
            "codigo_municipio",
            "motivo_alerta",
            "quantidade_faturas",
            "taxa_refaturamento_pct",
            "media_refaturamento_3_meses",
            "variacao_refaturamento_pp",
            "taxa_sem_leitura_pct",
            "media_sem_leitura_3_meses",
            "variacao_sem_leitura_pp",
        ]
    ]

    tabela["nivel_alerta"] = tabela["nivel_alerta"].map(
        {
            "CRITICO": '<span class="selo critico">CRÍTICO</span>',
            "ATENCAO": '<span class="selo atencao">ATENÇÃO</span>',
        }
    )
    tabela["quantidade_faturas"] = tabela["quantidade_faturas"].map(formatar_numero)

    for coluna in [
        "taxa_refaturamento_pct",
        "media_refaturamento_3_meses",
        "taxa_sem_leitura_pct",
        "media_sem_leitura_3_meses",
    ]:
        tabela[coluna] = tabela[coluna].map(formatar_percentual)

    for coluna in [
        "variacao_refaturamento_pp",
        "variacao_sem_leitura_pp",
    ]:
        tabela[coluna] = tabela[coluna].map(formatar_variacao_pp)

    tabela = tabela.rename(
        columns={
            "nivel_alerta": "Severidade",
            "codigo_municipio": "Município IBGE",
            "motivo_alerta": "Motivo",
            "quantidade_faturas": "Faturas",
            "taxa_refaturamento_pct": "Refaturamento atual",
            "media_refaturamento_3_meses": "Média refaturamento",
            "variacao_refaturamento_pp": "Variação refaturamento",
            "taxa_sem_leitura_pct": "Sem leitura atual",
            "media_sem_leitura_3_meses": "Média sem leitura",
            "variacao_sem_leitura_pp": "Variação sem leitura",
        }
    )

    return tabela.to_html(
        index=False,
        border=0,
        escape=False,
        table_id="tabela-alertas",
        classes="tabela-gerencial",
    )


def gerar_relatorio_html(
    kpis_mensais: pd.DataFrame,
    alertas_municipios: pd.DataFrame,
    distribuidora: str,
    modo_execucao: str,
    quantidade_registros: int,
) -> None:
    """Gera o relatório executivo com KPIs, tendências e filtros."""

    ultimo_mes = kpis_mensais.iloc[0]
    quantidade_criticos = int(
        (alertas_municipios.get("nivel_alerta") == "CRITICO").sum()
    ) if not alertas_municipios.empty else 0
    quantidade_atencao = len(alertas_municipios) - quantidade_criticos

    observacoes = gerar_resumo_gerencial(kpis_mensais, alertas_municipios)
    lista_observacoes = "".join(
        f"<li>{observacao}</li>" for observacao in observacoes
    )

    tabela_alertas = preparar_tabela_alertas(alertas_municipios)

    historico = kpis_mensais.head(12).copy()
    historico = historico[
        [
            "mes_referencia",
            "quantidade_faturas",
            "taxa_refaturamento_pct",
            "taxa_sem_leitura_pct",
            "taxa_acerto_pct",
            "cobertura_leitura_pct",
            "variacao_faturas_pct",
        ]
    ]
    historico["quantidade_faturas"] = historico["quantidade_faturas"].map(formatar_numero)

    for coluna in [
        "taxa_refaturamento_pct",
        "taxa_sem_leitura_pct",
        "taxa_acerto_pct",
        "cobertura_leitura_pct",
        "variacao_faturas_pct",
    ]:
        historico[coluna] = historico[coluna].map(formatar_percentual)

    historico = historico.rename(
        columns={
            "mes_referencia": "Mês",
            "quantidade_faturas": "Faturas",
            "taxa_refaturamento_pct": "Refaturamento",
            "taxa_sem_leitura_pct": "Sem leitura",
            "taxa_acerto_pct": "Acertos",
            "cobertura_leitura_pct": "Cobertura de leitura",
            "variacao_faturas_pct": "Variação de faturas",
        }
    )
    tabela_historico = historico.to_html(
        index=False,
        border=0,
        classes="tabela-gerencial",
    )

    grafico_refaturamento = criar_grafico_barras(
        kpis_mensais,
        "taxa_refaturamento_pct",
        "#0f766e",
    )
    grafico_sem_leitura = criar_grafico_barras(
        kpis_mensais,
        "taxa_sem_leitura_pct",
        "#d97706",
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório de Indicadores de Faturamento</title>
    <style>
        :root {{
            --azul:#0b3954; --azul-claro:#e6f4f7; --verde:#0f766e;
            --laranja:#d97706; --vermelho:#b42318; --cinza:#52606d;
            --borda:#d9e2ec; --fundo:#f5f8fa;
        }}
        * {{ box-sizing:border-box; }}
        body {{ margin:0; font-family:Arial, sans-serif; background:var(--fundo); color:#172b4d; }}
        header {{ background:linear-gradient(120deg,#083344,#0f766e); color:white; padding:32px 5vw; }}
        header h1 {{ margin:0 0 8px; font-size:30px; }}
        header p {{ margin:5px 0; opacity:.92; }}
        main {{ max-width:1280px; margin:auto; padding:24px; }}
        .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }}
        .card, section {{ background:white; border-radius:12px; box-shadow:0 3px 14px #102a4312; }}
        .card {{ padding:18px; border-top:4px solid var(--verde); }}
        .card small {{ color:var(--cinza); text-transform:uppercase; font-size:11px; font-weight:bold; }}
        .card strong {{ display:block; margin-top:9px; font-size:27px; color:var(--azul); }}
        section {{ margin-top:20px; padding:22px; overflow:auto; }}
        h2 {{ margin:0 0 14px; color:var(--azul); font-size:20px; }}
        h3 {{ color:var(--azul); font-size:15px; }}
        .resumo {{ border-left:5px solid var(--verde); background:#f0fdfa; }}
        .resumo li {{ margin:9px 0; line-height:1.45; }}
        .graficos {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
        .barra-linha {{ display:flex; align-items:center; gap:8px; margin:8px 0; font-size:12px; }}
        .barra-mes {{ width:42px; color:var(--cinza); }}
        .barra-fundo {{ height:11px; flex:1; border-radius:6px; background:#edf2f7; overflow:hidden; }}
        .barra-valor {{ height:100%; border-radius:6px; }}
        .barra-numero {{ width:58px; text-align:right; font-weight:bold; }}
        .filtros {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:15px; }}
        .filtros input, .filtros select {{ padding:9px; border:1px solid var(--borda); border-radius:7px; }}
        .tabela-gerencial {{ border-collapse:collapse; width:100%; min-width:850px; }}
        .tabela-gerencial th, .tabela-gerencial td {{ padding:10px; border-bottom:1px solid var(--borda); text-align:left; font-size:12px; }}
        .tabela-gerencial th {{ background:var(--azul-claro); color:var(--azul); position:sticky; top:0; }}
        .selo {{ color:white; border-radius:14px; padding:4px 8px; font-size:10px; font-weight:bold; }}
        .critico {{ background:var(--vermelho); }} .atencao {{ background:var(--laranja); }}
        .variacao-piora {{ color:#b42318; font-weight:bold; }}
        .variacao-melhora {{ color:#15803d; font-weight:bold; }}
        .variacao-estavel {{ color:var(--cinza); font-weight:bold; }}
        .metodologia {{ color:var(--cinza); line-height:1.55; }}
        .rodape {{ color:var(--cinza); font-size:12px; text-align:center; padding:20px; }}
        .sem-dados {{ color:var(--cinza); }}
        @media (max-width:800px) {{ .graficos {{ grid-template-columns:1fr; }} }}
    </style>
</head>
<body>
<header>
    <h1>Relatório de Indicadores de Faturamento</h1>
    <p><strong>Distribuidora:</strong> {escape(distribuidora)}</p>
    <p><strong>Período mais recente:</strong> {escape(str(ultimo_mes['mes_referencia']))}</p>
</header>
<main>
    <div class="cards">
        <div class="card"><small>Faturas</small><strong>{formatar_numero(ultimo_mes['quantidade_faturas'])}</strong></div>
        <div class="card"><small>Unidades ativas</small><strong>{formatar_numero(ultimo_mes['unidades_consumidoras_ativas'])}</strong></div>
        <div class="card"><small>Cobertura de leitura</small><strong>{formatar_percentual(ultimo_mes['cobertura_leitura_pct'])}</strong></div>
        <div class="card"><small>Taxa de refaturamento</small><strong>{formatar_percentual(ultimo_mes['taxa_refaturamento_pct'])}</strong></div>
        <div class="card"><small>Faturas sem leitura</small><strong>{formatar_percentual(ultimo_mes['taxa_sem_leitura_pct'])}</strong></div>
        <div class="card"><small>Alertas críticos</small><strong>{quantidade_criticos}</strong></div>
        <div class="card"><small>Alertas em atenção</small><strong>{quantidade_atencao}</strong></div>
    </div>

    <section class="resumo">
        <h2>Resumo executivo</h2>
        <ul>{lista_observacoes}</ul>
    </section>

    <section>
        <h2>Tendência dos últimos 12 meses</h2>
        <div class="graficos">
            <div><h3>Taxa de refaturamento</h3>{grafico_refaturamento}</div>
            <div><h3>Taxa de faturas sem leitura</h3>{grafico_sem_leitura}</div>
        </div>
    </section>

    <section>
        <h2>Fila de municípios para análise</h2>
        <div class="filtros">
            <input id="busca-alerta" type="text" placeholder="Buscar município ou motivo" oninput="filtrarAlertas()">
            <select id="filtro-severidade" onchange="filtrarAlertas()">
                <option value="">Todas as severidades</option>
                <option value="CRÍTICO">Crítico</option>
                <option value="ATENÇÃO">Atenção</option>
            </select>
            <select id="filtro-motivo" onchange="filtrarAlertas()">
                <option value="">Todos os motivos</option>
                <option value="REFATURAMENTO">Refaturamento</option>
                <option value="FATURAS SEM LEITURA">Faturas sem leitura</option>
            </select>
        </div>
        {tabela_alertas}
    </section>

    <section>
        <h2>Histórico mensal</h2>
        {tabela_historico}
    </section>

    <section class="metodologia">
        <h2>Critérios dos alertas</h2>
        <p><strong>Atenção:</strong> taxa atual pelo menos duas vezes maior que a média dos três meses anteriores e diferença mínima de 1%.</p>
        <p><strong>Crítico:</strong> taxa atual pelo menos três vezes maior que a média dos três meses anteriores e diferença mínima de 2%.</p>
        <p>São avaliados municípios com três meses completos de histórico e pelo menos 100 faturas no mês.</p>
        <p>As variações apresentadas indicam quanto a taxa atual aumentou ou reduziu em relação à média histórica.</p>
    </section>

    <div class="rodape">
        Fonte: ANEEL INDGER | Modo: {escape(modo_execucao)} | Registros processados: {formatar_numero(quantidade_registros)} | Gerado em {datetime.now():%d/%m/%Y %H:%M}
    </div>
</main>
<script>
function filtrarAlertas() {{
    const tabela = document.getElementById('tabela-alertas');
    if (!tabela) return;
    const busca = document.getElementById('busca-alerta').value.toUpperCase();
    const severidade = document.getElementById('filtro-severidade').value;
    const motivo = document.getElementById('filtro-motivo').value;
    const linhas = tabela.tBodies[0].rows;

    for (const linha of linhas) {{
        const texto = linha.innerText.toUpperCase();
        const atendeBusca = !busca || texto.includes(busca);
        const atendeSeveridade = !severidade || texto.includes(severidade);
        const atendeMotivo = !motivo || texto.includes(motivo);
        linha.style.display = atendeBusca && atendeSeveridade && atendeMotivo ? '' : 'none';
    }}
}}
</script>
</body>
</html>"""

    ARQUIVO_RELATORIO.write_text(html, encoding="utf-8")


def exportar_resultados(
    kpis_mensais: pd.DataFrame,
    alertas_municipios: pd.DataFrame,
    distribuidora: str,
    modo_execucao: str,
    quantidade_registros: int,
) -> None:
    """Exporta os CSVs e chama a geração do relatório HTML."""

    print("[5/6] Exportando os resultados...")

    kpis_mensais.to_csv(
        ARQUIVO_KPIS,
        index=False,
        sep=";",
        encoding="utf-8-sig",
    )
    alertas_municipios.to_csv(
        ARQUIVO_ALERTAS,
        index=False,
        sep=";",
        encoding="utf-8-sig",
    )

    gerar_relatorio_html(
        kpis_mensais,
        alertas_municipios,
        distribuidora,
        modo_execucao,
        quantidade_registros,
    )

    logging.info("Arquivos de saída atualizados em %s.", PASTA_DE_SAIDAS)

