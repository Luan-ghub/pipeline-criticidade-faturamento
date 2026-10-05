# ===========================================================================================================================================================
                                    ### Pipeline de Automação - Relatório de Criticidade de Faturamento. ###
# ===========================================================================================================================================================


# BIBLIOTECAS
import argparse
import logging

from src.config import ARQUIVO_RELATORIO, DISTRIBUIDORA, MODO_EXECUCAO
from src.processamento import (
    calcular_indicadores,
    carregar_catalogo_distribuidoras,
    extrair_dados,
    preparar_ambiente,
    salvar_no_banco,
    tratar_dados,
)
from src.relatorio import exportar_resultados


# =============================================================================
# SUMÁRIO DAS FUNÇÕES
# =============================================================================

# ## PREPARAÇÃO E LOG
# ### - preparar_ambiente: Cria as pastas de trabalho e configura o arquivo de log
# ### - criar_nome_seguro: Converte o nome da distribuidora em um nome seguro para arquivo
# ### - obter_arquivo_dados_brutos: Informa o snapshot correspondente à distribuidora

# ## CATÁLOGO DE DISTRIBUIDORAS
# ### - consultar_api: Envia uma consulta para a API da ANEEL e valida a resposta
# ### - consultar_distribuidoras_da_api: Consulta e salva as distribuidoras disponíveis na base
# ### - carregar_catalogo_distribuidoras: Carrega o catálogo local ou solicita sua atualização
# ### - listar_distribuidoras_no_banco: Lista as distribuidoras que já foram carregadas no SQLite

# ## EXTRAÇÃO DOS DADOS
# ### - consultar_pagina_da_api: Consulta uma página da API para a distribuidora selecionada
# ### - extrair_dados_online: Baixa todos os registros em páginas de tamanho configurável
# ### - carregar_dados_offline: Carrega o último snapshot salvo para a distribuidora
# ### - extrair_dados: Escolhe a fonte de acordo com o modo online ou offline

# ## TRATAMENTO DOS DADOS
# ### - tratar_dados: Transforma os registros brutos em uma tabela pronta para análise

# ## BANCO DE DADOS
# ### - salvar_no_banco: Atualiza os registros da distribuidora no banco SQLite

# ## CONSULTAS SQL
# ### - executar_consulta_sql: Executa um arquivo SQL para a distribuidora selecionada
# ### - calcular_indicadores: Calcula os KPIs mensais e os alertas municipais

# ## RELATÓRIO GERENCIAL
# ### - formatar_numero: Formata números no padrão brasileiro.
# ### - formatar_percentual: Formata taxas e variações com o símbolo de porcentagem
# ### - criar_grafico_barras: Cria um gráfico HTML simples para os últimos 12 meses
# ### - gerar_resumo_gerencial: Produz observações automáticas para apoiar a análise
# ### - preparar_tabela_alertas: Organiza e formata a tabela gerencial de alertas
# ### - gerar_relatorio_html: Gera o relatório executivo com KPIs, tendências e filtros
# ### - exportar_resultados: Exporta os CSVs e chama a geração do relatório HTML

# ## EXECUÇÃO
# ### - executar: Executa todas as etapas da automação na ordem correta
# ### - ler_argumentos: Lê distribuidora e modo informados no terminal


# -----------------------------------------------------------------------------
# ETAPA 6. EXECUÇÃO COMPLETA
# -----------------------------------------------------------------------------

def executar(
    distribuidora: str = DISTRIBUIDORA,
    modo_execucao: str = MODO_EXECUCAO,
) -> dict:
    """Executa todas as etapas da automação na ordem correta."""

    preparar_ambiente()
    modo_execucao = modo_execucao.lower().strip()

    print("=" * 60)
    print("PIPELINE DE INDICADORES DE FATURAMENTO DA ANEEL")
    print(f"Distribuidora: {distribuidora}")
    print(f"Modo de execução: {modo_execucao}")
    print("=" * 60)

    logging.info(
        "Pipeline iniciado. Distribuidora: %s. Modo: %s.",
        distribuidora,
        modo_execucao,
    )

    try:
        if modo_execucao == "online":
            carregar_catalogo_distribuidoras(atualizar_online=True)

        registros = extrair_dados(distribuidora, modo_execucao)
        dados_tratados = tratar_dados(registros, distribuidora)
        salvar_no_banco(dados_tratados, distribuidora)
        kpis_mensais, alertas_municipios = calcular_indicadores(distribuidora)
        exportar_resultados(
            kpis_mensais,
            alertas_municipios,
            distribuidora,
            modo_execucao,
            len(dados_tratados),
        )

        print("[6/6] Processo concluído com sucesso.")
        print(f"      Registros tratados: {len(dados_tratados)}")
        print(f"      Períodos analisados: {len(kpis_mensais)}")
        print(f"      Alertas no último mês: {len(alertas_municipios)}")
        print(f"      Relatório: {ARQUIVO_RELATORIO}")

        logging.info("Pipeline concluído com sucesso.")
        return {
            "dados": dados_tratados,
            "kpis": kpis_mensais,
            "alertas": alertas_municipios,
            "relatorio": ARQUIVO_RELATORIO,
        }

    except Exception as erro:
        logging.exception("O pipeline foi encerrado com erro.")
        print(f"O processo não foi concluído: {erro}")
        raise


def ler_argumentos() -> argparse.Namespace:
    """Lê distribuidora e modo informados no terminal."""

    parser = argparse.ArgumentParser(
        description="Pipeline de indicadores comerciais da ANEEL."
    )
    parser.add_argument(
        "--distribuidora",
        default=DISTRIBUIDORA,
        help="Nome da distribuidora conforme o catálogo da ANEEL.",
    )
    parser.add_argument(
        "--modo",
        choices=["offline", "online"],
        default=MODO_EXECUCAO,
        help="Origem dos dados utilizada na execução.",
    )
    parser.add_argument(
        "--listar-distribuidoras",
        action="store_true",
        help="Atualiza e exibe o catálogo de distribuidoras da ANEEL.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    argumentos = ler_argumentos()
    preparar_ambiente()

    if argumentos.listar_distribuidoras:
        catalogo = carregar_catalogo_distribuidoras(atualizar_online=True)
        print(f"Distribuidoras disponíveis: {len(catalogo)}")
        print(catalogo.to_string(index=False))
    else:
        executar(
            distribuidora=argumentos.distribuidora,
            modo_execucao=argumentos.modo,
        )

