
# ===========================================================================================================================================================
                                    ### Dashboard interativo dos indicadores de faturamento da ANEEL. ###
# ===========================================================================================================================================================

# BIBLIOTECAS

import sqlite3
import altair as alt
import pandas as pd
import streamlit as st

from pipeline_aneel import executar
from src.config import ARQUIVO_BANCO, DISTRIBUIDORA
from src.processamento import (
    calcular_indicadores,
    carregar_catalogo_distribuidoras,
    listar_distribuidoras_no_banco,
    preparar_ambiente,
)
from src.relatorio import exportar_resultados


# CONFIGURAÇÃO DA PÁGINA

st.set_page_config(
    page_title="Painel de Faturamento ANEEL",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1450px;
            padding-top: 1.6rem;
            padding-bottom: 2.5rem;
        }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #dde5ec;
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 5px 18px rgba(21, 51, 76, 0.06);
        }
        [data-testid="stSidebar"] {
            background: #f4f7f9;
        }
        .cabecalho-painel {
            padding: 22px 26px;
            margin-bottom: 18px;
            border-radius: 14px;
            color: white;
            background: linear-gradient(120deg, #0b3d5c, #087f8c);
        }
        .cabecalho-painel h1 {
            margin: 0 0 6px 0;
            font-size: 2rem;
        }
        .cabecalho-painel p {
            margin: 0;
            color: #dceff1;
        }
        .caixa-informativa {
            padding: 14px 16px;
            margin: 8px 0 18px 0;
            border-left: 4px solid #087f8c;
            border-radius: 6px;
            background: #edf7f7;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# FUNÇÕES DE APOIO AO DASHBOARD
# =============================================================================


def formatar_numero(valor: float | int) -> str:
    """Formata números inteiros no padrão brasileiro."""

    return f"{valor:,.0f}".replace(",", ".")


def formatar_percentual(valor: float | int) -> str:
    """Formata indicadores e variações utilizando o símbolo de porcentagem."""

    return f"{valor:.2f}%".replace(".", ",")


def calcular_variacao_relativa(valor_atual: float, valor_anterior: float) -> float | None:
    """Compara dois valores e devolve a variação relativa em percentual."""

    if pd.isna(valor_anterior) or valor_anterior == 0:
        return None
    return 100 * (valor_atual - valor_anterior) / valor_anterior


def formatar_variacao(valor: float | None) -> str | None:
    """Prepara o texto que aparece abaixo dos indicadores do dashboard."""

    if valor is None or pd.isna(valor):
        return None
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{formatar_percentual(valor)} vs. mês anterior"


def obter_metadados(distribuidora: str) -> dict:
    """Busca no banco informações de cobertura e atualização da distribuidora."""

    consulta = """
        SELECT
            MIN(mes_referencia) AS primeiro_periodo,
            MAX(mes_referencia) AS ultimo_periodo,
            MAX(data_geracao_dados) AS data_geracao_dados,
            COUNT(DISTINCT mes_referencia) AS quantidade_periodos,
            COUNT(*) AS quantidade_registros
        FROM indicadores_faturamento
        WHERE distribuidora = :distribuidora
    """

    with sqlite3.connect(ARQUIVO_BANCO) as conexao:
        metadados = pd.read_sql_query(
            consulta,
            conexao,
            params={"distribuidora": distribuidora},
        ).iloc[0]

    return metadados.to_dict()


@st.cache_data
def carregar_dados_do_painel(distribuidora: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Carrega KPIs, alertas e metadados da distribuidora selecionada."""

    kpis, alertas = calcular_indicadores(distribuidora)
    metadados = obter_metadados(distribuidora)
    kpis["mes_referencia"] = pd.to_datetime(kpis["mes_referencia"])
    return kpis, alertas, metadados


# =============================================================================
# PREPARAÇÃO E SELEÇÃO DA DISTRIBUIDORA
# =============================================================================

preparar_ambiente()

try:
    catalogo = carregar_catalogo_distribuidoras(atualizar_online=False)
    distribuidoras_disponiveis = catalogo["distribuidora"].tolist()
except Exception:
    # Se o catálogo ainda não existir, o painel continua funcionando com o banco local.
    distribuidoras_disponiveis = listar_distribuidoras_no_banco() or [DISTRIBUIDORA]

distribuidoras_carregadas = listar_distribuidoras_no_banco()
indice_padrao = (
    distribuidoras_disponiveis.index(DISTRIBUIDORA)
    if DISTRIBUIDORA in distribuidoras_disponiveis
    else 0
)

with st.sidebar:
    st.title("Filtros do painel")
    st.caption("Base pública INDGER da ANEEL")

    distribuidora_selecionada = st.selectbox(
        "Distribuidora",
        distribuidoras_disponiveis,
        index=indice_padrao,
        help="A lista representa as distribuidoras disponíveis na base consultada.",
    )

    esta_carregada = distribuidora_selecionada in distribuidoras_carregadas
    situacao = "Disponível no banco local" if esta_carregada else "Ainda não carregada"
    st.caption(f"Situação: {situacao}")

    texto_botao = (
        "Atualizar dados pela ANEEL"
        if esta_carregada
        else "Baixar e processar distribuidora"
    )

    if st.button(texto_botao, type="primary", width="stretch"):
        try:
            with st.spinner("Consultando, tratando e gravando os dados..."):
                executar(distribuidora_selecionada, "online")
            st.cache_data.clear()
            st.success("Dados atualizados com sucesso.")
            st.rerun()
        except Exception as erro:
            st.error(f"Não foi possível concluir a atualização: {erro}")

    if st.button("Atualizar lista de distribuidoras", width="stretch"):
        try:
            with st.spinner("Consultando o catálogo da ANEEL..."):
                carregar_catalogo_distribuidoras(atualizar_online=True)
            st.success("Lista atualizada. Recarregando o painel.")
            st.rerun()
        except Exception as erro:
            st.error(f"Não foi possível atualizar a lista: {erro}")

    st.divider()
    st.caption(
        f"{len(distribuidoras_disponiveis)} distribuidoras no catálogo. "
        f"{len(distribuidoras_carregadas)} já carregadas no banco local."
    )


# =============================================================================
# CONTEÚDO PRINCIPAL
# =============================================================================

st.markdown(
    f"""
    <div class="cabecalho-painel">
        <h1>Painel gerencial de faturamento</h1>
        <p>{distribuidora_selecionada} | Monitoramento Mensal | Dados ANEEL </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if distribuidora_selecionada not in listar_distribuidoras_no_banco():
    st.info(
        "Utilize o botão de carga na barra lateral para atualizar o painel"
    )
    st.stop()

kpis, alertas, metadados = carregar_dados_do_painel(distribuidora_selecionada)
kpis_ordenados = kpis.sort_values("mes_referencia", ascending=False).reset_index(drop=True)
mes_atual = kpis_ordenados.iloc[0]
mes_anterior = kpis_ordenados.iloc[1] if len(kpis_ordenados) > 1 else None

periodo_atual = mes_atual["mes_referencia"].strftime("%m/%Y")
st.markdown(
    f"""
    <div class="caixa-informativa">
        Período analisado: <strong>{periodo_atual}</strong>. Os alertas servem para
        priorizar a investigação.
    </div>
    """,
    unsafe_allow_html=True,
)

aba_executiva, aba_tendencias, aba_alertas, aba_dados = st.tabs(
    ["Visão executiva", "Tendências", "Alertas municipais", "Dados e atualização"]
)


with aba_executiva:
    variacao_faturas = (
        calcular_variacao_relativa(
            mes_atual["quantidade_faturas"], mes_anterior["quantidade_faturas"]
        )
        if mes_anterior is not None
        else None
    )
    variacao_refaturamento = (
        calcular_variacao_relativa(
            mes_atual["taxa_refaturamento_pct"],
            mes_anterior["taxa_refaturamento_pct"],
        )
        if mes_anterior is not None
        else None
    )
    variacao_sem_leitura = (
        calcular_variacao_relativa(
            mes_atual["taxa_sem_leitura_pct"],
            mes_anterior["taxa_sem_leitura_pct"],
        )
        if mes_anterior is not None
        else None
    )
    variacao_cobertura = (
        calcular_variacao_relativa(
            mes_atual["cobertura_leitura_pct"],
            mes_anterior["cobertura_leitura_pct"],
        )
        if mes_anterior is not None
        else None
    )

    col_faturas, col_refaturamento, col_sem_leitura, col_cobertura = st.columns(4)
    col_faturas.metric(
        "Faturas emitidas",
        formatar_numero(mes_atual["quantidade_faturas"]),
        formatar_variacao(variacao_faturas),
    )
    col_refaturamento.metric(
        "Taxa de refaturamento",
        formatar_percentual(mes_atual["taxa_refaturamento_pct"]),
        formatar_variacao(variacao_refaturamento),
        delta_color="inverse",
    )
    col_sem_leitura.metric(
        "Faturas sem leitura",
        formatar_percentual(mes_atual["taxa_sem_leitura_pct"]),
        formatar_variacao(variacao_sem_leitura),
        delta_color="inverse",
    )
    col_cobertura.metric(
        "Cobertura com leitura",
        formatar_percentual(mes_atual["cobertura_leitura_pct"]),
        formatar_variacao(variacao_cobertura),
    )

    st.subheader("Prioridades do período")
    criticos = int((alertas["nivel_alerta"] == "CRITICO").sum()) if not alertas.empty else 0
    atencao = int((alertas["nivel_alerta"] == "ATENCAO").sum()) if not alertas.empty else 0
    volume_alertado = int(alertas["quantidade_faturas"].sum()) if not alertas.empty else 0

    col_criticos, col_atencao, col_volume = st.columns(3)
    col_criticos.metric("Alertas críticos", criticos)
    col_atencao.metric("Alertas de atenção", atencao)
    col_volume.metric("Faturas em municípios alertados", formatar_numero(volume_alertado))


with aba_tendencias:
    historico = (
        kpis.sort_values("mes_referencia")
        .tail(12)
        .copy()
    )
    historico["periodo"] = historico["mes_referencia"].dt.strftime("%m/%Y")
    ordem_dos_periodos = historico["periodo"].tolist()

    st.subheader("Evolução das taxas nos últimos 12 meses")

    taxas = historico.melt(
        id_vars=["periodo"],
        value_vars=[
            "taxa_refaturamento_pct",
            "taxa_sem_leitura_pct",
            "taxa_acerto_pct",
        ],
        var_name="indicador",
        value_name="valor",
    )
    taxas["indicador"] = taxas["indicador"].replace(
        {
            "taxa_refaturamento_pct": "Refaturamento",
            "taxa_sem_leitura_pct": "Faturas sem leitura",
            "taxa_acerto_pct": "Faturas de acerto",
        }
    )

    grafico_taxas = (
        alt.Chart(taxas)
        .mark_line(point=alt.OverlayMarkDef(filled=True, size=55), strokeWidth=2.5)
        .encode(
            x=alt.X(
                "periodo:N",
                sort=ordem_dos_periodos,
                title="Mês/Ano",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y(
                "valor:Q",
                title="Taxa (%)",
                scale=alt.Scale(zero=False),
                axis=alt.Axis(format=".2f"),
            ),
            color=alt.Color(
                "indicador:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Refaturamento",
                        "Faturas sem leitura",
                        "Faturas de acerto",
                    ],
                    range=["#2563eb", "#dc2626", "#0f766e"],
                ),
            ),
            tooltip=[
                alt.Tooltip("periodo:N", title="Mês"),
                alt.Tooltip("indicador:N", title="Indicador"),
                alt.Tooltip("valor:Q", title="Taxa", format=".2f"),
            ],
        )
        .properties(height=340)
    )
    st.altair_chart(grafico_taxas, width="stretch")

    coluna_grafico_1, coluna_grafico_2 = st.columns(2)
    with coluna_grafico_1:
        st.subheader("Evolução do volume de faturas")

        grafico_volume = (
            alt.Chart(historico)
            .mark_line(
                point=alt.OverlayMarkDef(filled=True, size=60),
                color="#2563eb",
                strokeWidth=2.5,
            )
            .encode(
                x=alt.X(
                    "periodo:N",
                    sort=ordem_dos_periodos,
                    title="Mês/Ano",
                    axis=alt.Axis(labelAngle=-45),
                ),
                y=alt.Y(
                    "quantidade_faturas:Q",
                    title="Faturas",
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(format="~s"),
                ),
                tooltip=[
                    alt.Tooltip("periodo:N", title="Mês"),
                    alt.Tooltip(
                        "quantidade_faturas:Q",
                        title="Faturas",
                        format=",.0f",
                    ),
                    alt.Tooltip(
                        "variacao_faturas_pct:Q",
                        title="Variação (%)",
                        format=".2f",
                    ),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(grafico_volume, width="stretch")

    with coluna_grafico_2:
        st.subheader("Cobertura com leitura")

        grafico_cobertura = (
            alt.Chart(historico)
            .mark_line(
                point=alt.OverlayMarkDef(filled=True, size=60),
                color="#0f766e",
                strokeWidth=2.5,
            )
            .encode(
                x=alt.X(
                    "periodo:N",
                    sort=ordem_dos_periodos,
                    title="Mês/Ano",
                    axis=alt.Axis(labelAngle=-45),
                ),
                y=alt.Y(
                    "cobertura_leitura_pct:Q",
                    title="Cobertura (%)",
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(format=".2f"),
                ),
                tooltip=[
                    alt.Tooltip("periodo:N", title="Mês"),
                    alt.Tooltip(
                        "cobertura_leitura_pct:Q",
                        title="Cobertura",
                        format=".2f",
                    ),
                ],
            )
            .properties(height=300)
        )
        st.altair_chart(grafico_cobertura, width="stretch")


with aba_alertas:
    st.subheader("Municípios priorizados para investigação")

    if alertas.empty:
        st.success("Nenhum município atendeu aos critérios de alerta no último período.")
    else:
        col_severidade, col_motivo, col_volume_minimo = st.columns([1, 1.5, 1])
        niveis = col_severidade.multiselect(
            "Severidade",
            sorted(alertas["nivel_alerta"].unique()),
            default=sorted(alertas["nivel_alerta"].unique()),
        )
        motivos = col_motivo.multiselect(
            "Motivo",
            sorted(alertas["motivo_alerta"].unique()),
            default=sorted(alertas["motivo_alerta"].unique()),
        )
        volume_minimo = col_volume_minimo.number_input(
            "Mínimo de faturas",
            min_value=0,
            value=100,
            step=100,
        )

        alertas_filtrados = alertas[
            alertas["nivel_alerta"].isin(niveis)
            & alertas["motivo_alerta"].isin(motivos)
            & (alertas["quantidade_faturas"] >= volume_minimo)
        ].copy()

        colunas_exibidas = {
            "codigo_municipio": "Código IBGE",
            "nivel_alerta": "Severidade",
            "motivo_alerta": "Motivo",
            "quantidade_faturas": "Faturas",
            "taxa_refaturamento_pct": "Refaturamento atual",
            "media_refaturamento_3_meses": "Média anterior",
            "taxa_sem_leitura_pct": "Sem leitura atual",
            "media_sem_leitura_3_meses": "Média anterior sem leitura",
        }
        tabela = alertas_filtrados[list(colunas_exibidas)].rename(columns=colunas_exibidas)

        st.dataframe(
            tabela,
            width="stretch",
            hide_index=True,
            column_config={
                "Refaturamento atual": st.column_config.NumberColumn(format="%.2f%%"),
                "Média anterior": st.column_config.NumberColumn(format="%.2f%%"),
                "Sem leitura atual": st.column_config.NumberColumn(format="%.2f%%"),
                "Média anterior sem leitura": st.column_config.NumberColumn(format="%.2f%%"),
                "Faturas": st.column_config.NumberColumn(format="%d"),
            },
        )

        st.download_button(
            "Baixar alertas filtrados em CSV",
            data=alertas_filtrados.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="alertas_municipios_filtrados.csv",
            mime="text/csv",
        )


with aba_dados:
    st.subheader("Cobertura e atualização")
    col_primeiro_periodo, col_ultimo_periodo, col_meses, col_distribuidoras = st.columns(4)
    col_primeiro_periodo.metric("Primeiro período", str(metadados["primeiro_periodo"])[:7])
    col_ultimo_periodo.metric("Último período", str(metadados["ultimo_periodo"])[:7])
    col_meses.metric("Meses disponíveis", int(metadados["quantidade_periodos"]))
    col_distribuidoras.metric("Distribuidoras carregadas", len(listar_distribuidoras_no_banco()))

    st.caption(f"Data de geração informada pela fonte: {metadados['data_geracao_dados']}")

    st.subheader("Histórico mensal")
    historico_exibicao = kpis_ordenados.copy()
    historico_exibicao["mes_referencia"] = historico_exibicao[
        "mes_referencia"
    ].dt.strftime("%m/%Y")
    st.dataframe(historico_exibicao, width="stretch", hide_index=True)

    if st.button("Gerar relatório HTML desta distribuidora"):
        exportar_resultados(
            kpis,
            alertas,
            distribuidora_selecionada,
            "banco local",
            int(metadados["quantidade_registros"]),
        )
        st.success("Relatório atualizado na pasta de saídas do projeto.")

    st.download_button(
        "Baixar histórico mensal em CSV",
        data=kpis_ordenados.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="kpis_mensais.csv",
        mime="text/csv",
    )

