# ===========================================================================================================================================================
                                    ### Pipeline de Automação - Relatório de Criticidade de Faturamento. ###
# ===========================================================================================================================================================


# BIBLIOTECAS
import json
import logging
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import (
    ARQUIVO_BANCO,
    ARQUIVO_CATALOGO_DISTRIBUIDORAS,
    ARQUIVO_DADOS_BRUTOS_LEGADO,
    ARQUIVO_LOG,
    ARQUIVO_SQL_ALERTAS,
    ARQUIVO_SQL_KPIS,
    COLUNAS_ANEEL,
    COLUNAS_NUMERICAS,
    ID_RECURSO_ANEEL,
    MAXIMO_TENTATIVAS_API,
    NOMES_DAS_COLUNAS,
    PASTA_DE_DADOS,
    PASTA_DE_LOGS,
    PASTA_DE_SAIDAS,
    TAMANHO_DA_PAGINA,
    TEMPO_LIMITE_API,
    URL_API_ANEEL,
)


# -----------------------------------------------------------------------------
# PREPARAÇÃO DAS PASTAS E DO LOG
# -----------------------------------------------------------------------------

def preparar_ambiente() -> None:
    """Cria as pastas de trabalho e configura o arquivo de log."""

    PASTA_DE_DADOS.mkdir(parents=True, exist_ok=True)
    PASTA_DE_SAIDAS.mkdir(parents=True, exist_ok=True)
    PASTA_DE_LOGS.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=ARQUIVO_LOG,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
        force=True,
    )


def criar_nome_seguro(texto: str) -> str:
    """Converte um texto em um nome simples para utilizar em arquivos."""

    texto_normalizado = unicodedata.normalize("NFKD", texto)
    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_normalizado
        if not unicodedata.combining(caractere)
    )
    return re.sub(r"[^a-z0-9]+", "_", texto_sem_acentos.lower()).strip("_")


def obter_arquivo_dados_brutos(distribuidora: str) -> Path:
    """Informa o arquivo de dados brutos correspondente à distribuidora."""

    nome_seguro = criar_nome_seguro(distribuidora)
    return PASTA_DE_DADOS / f"dados_brutos_{nome_seguro}.json"


# -----------------------------------------------------------------------------
# CATÁLOGO DE DISTRIBUIDORAS
# -----------------------------------------------------------------------------

def consultar_api(parametros: dict) -> dict:
    """Envia uma consulta para a API da ANEEL e valida a resposta."""

    endereco_completo = URL_API_ANEEL + "?" + urllib.parse.urlencode(parametros)
    requisicao = urllib.request.Request(
        endereco_completo,
        headers={"User-Agent": "projeto-portfolio-faturamento/2.0"},
    )

    for tentativa in range(1, MAXIMO_TENTATIVAS_API + 1):
        try:
            with urllib.request.urlopen(
                requisicao,
                timeout=TEMPO_LIMITE_API,
            ) as resposta:
                conteudo = json.load(resposta)
            break

        except (TimeoutError, urllib.error.URLError) as erro:
            if tentativa == MAXIMO_TENTATIVAS_API:
                raise RuntimeError(
                    "A API da ANEEL não respondeu após três tentativas. "
                    "Os dados que já estavam salvos foram preservados."
                ) from erro

            tempo_de_espera = tentativa * 2
            logging.warning(
                "Falha temporária na API. Tentativa %s de %s. Nova tentativa em %s segundos.",
                tentativa,
                MAXIMO_TENTATIVAS_API,
                tempo_de_espera,
            )
            print(
                "      A API demorou para responder. "
                f"Nova tentativa em {tempo_de_espera} segundos..."
            )
            time.sleep(tempo_de_espera)

    if not conteudo.get("success"):
        raise RuntimeError("A API da ANEEL não retornou uma resposta válida.")

    return conteudo["result"]


def consultar_distribuidoras_da_api() -> pd.DataFrame:
    """Consulta e salva as distribuidoras disponíveis na base da ANEEL."""

    resultado = consultar_api(
        {
            "resource_id": ID_RECURSO_ANEEL,
            "limit": 1000,
            "fields": "SigAgente",
            "distinct": "true",
        }
    )

    distribuidoras = sorted(
        {
            registro["SigAgente"].strip()
            for registro in resultado["records"]
            if registro.get("SigAgente")
        }
    )

    catalogo = pd.DataFrame({"distribuidora": distribuidoras})
    catalogo.to_csv(
        ARQUIVO_CATALOGO_DISTRIBUIDORAS,
        index=False,
        sep=";",
        encoding="utf-8-sig",
    )

    logging.info("Catálogo atualizado com %s distribuidoras.", len(catalogo))
    return catalogo


def carregar_catalogo_distribuidoras(atualizar_online: bool = False) -> pd.DataFrame:
    """Carrega o catálogo local ou solicita sua atualização na API."""

    if atualizar_online or not ARQUIVO_CATALOGO_DISTRIBUIDORAS.exists():
        try:
            return consultar_distribuidoras_da_api()
        except Exception:
            if not ARQUIVO_CATALOGO_DISTRIBUIDORAS.exists():
                raise
            logging.exception(
                "Não foi possível atualizar o catálogo. O arquivo local será utilizado."
            )

    return pd.read_csv(
        ARQUIVO_CATALOGO_DISTRIBUIDORAS,
        sep=";",
        encoding="utf-8-sig",
    )


def listar_distribuidoras_no_banco() -> list[str]:
    """Lista as distribuidoras que já foram carregadas no banco SQLite."""

    if not ARQUIVO_BANCO.exists():
        return []

    with sqlite3.connect(ARQUIVO_BANCO) as conexao:
        tabela_existe = conexao.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table' AND name = 'indicadores_faturamento'
            """
        ).fetchone()[0]

        if not tabela_existe:
            return []

        linhas = conexao.execute(
            """
            SELECT DISTINCT distribuidora
            FROM indicadores_faturamento
            ORDER BY distribuidora
            """
        ).fetchall()

    return [linha[0] for linha in linhas]


# -----------------------------------------------------------------------------
# ETAPA 1. EXTRAÇÃO DOS DADOS
# -----------------------------------------------------------------------------

def consultar_pagina_da_api(
    posicao_inicial: int,
    distribuidora: str,
) -> dict:
    """Consulta uma página da API para a distribuidora selecionada."""

    filtros = json.dumps({"SigAgente": distribuidora}, ensure_ascii=False)

    return consultar_api(
        {
            "resource_id": ID_RECURSO_ANEEL,
            "limit": TAMANHO_DA_PAGINA,
            "offset": posicao_inicial,
            "filters": filtros,
            "fields": ",".join(COLUNAS_ANEEL),
        }
    )


def extrair_dados_online(distribuidora: str) -> list[dict]:
    """Baixa todos os registros da distribuidora em páginas."""

    registros = []
    posicao_inicial = 0
    total_de_registros = None

    print("[1/6] Consultando a API da ANEEL...")
    logging.info("Início da consulta online para %s.", distribuidora)

    while total_de_registros is None or len(registros) < total_de_registros:
        pagina = consultar_pagina_da_api(posicao_inicial, distribuidora)
        novos_registros = pagina["records"]
        total_de_registros = pagina["total"]

        registros.extend(novos_registros)
        posicao_inicial += len(novos_registros)

        print(f"      Registros recebidos: {len(registros)} de {total_de_registros}")

        if not novos_registros:
            break

    if not registros:
        raise ValueError(f"Nenhum registro foi encontrado para {distribuidora}.")

    conteudo_do_snapshot = {
        "metadata": {
            "fonte": "ANEEL INDGER - Dados Comerciais",
            "distribuidora": distribuidora,
            "extraido_em": datetime.now().isoformat(timespec="seconds"),
            "quantidade_registros": len(registros),
        },
        "records": registros,
    }

    arquivo_dados_brutos = obter_arquivo_dados_brutos(distribuidora)
    with arquivo_dados_brutos.open("w", encoding="utf-8") as arquivo:
        json.dump(conteudo_do_snapshot, arquivo, ensure_ascii=False)

    logging.info("Consulta online concluída com %s registros.", len(registros))
    return registros


def carregar_dados_offline(distribuidora: str) -> list[dict]:
    """Carrega o último snapshot salvo para a distribuidora."""

    print("[1/6] Carregando o arquivo offline da ANEEL...")
    arquivo_dados_brutos = obter_arquivo_dados_brutos(distribuidora)

    # Compatibilidade com o nome utilizado na primeira versão do projeto.
    if not arquivo_dados_brutos.exists() and ARQUIVO_DADOS_BRUTOS_LEGADO.exists():
        arquivo_dados_brutos = ARQUIVO_DADOS_BRUTOS_LEGADO

    if not arquivo_dados_brutos.exists():
        raise FileNotFoundError(
            f"Não existe snapshot offline para {distribuidora}. "
            "Execute uma vez no modo online para baixar os dados."
        )

    with arquivo_dados_brutos.open("r", encoding="utf-8") as arquivo:
        conteudo = json.load(arquivo)

    registros = conteudo["records"]
    distribuidoras_no_arquivo = {
        registro.get("SigAgente") for registro in registros if registro.get("SigAgente")
    }

    if distribuidora not in distribuidoras_no_arquivo:
        raise ValueError(
            f"O snapshot encontrado não contém dados de {distribuidora}. "
            "Utilize o modo online para esta seleção."
        )

    logging.info(
        "Arquivo offline de %s carregado com %s registros.",
        distribuidora,
        len(registros),
    )
    return registros


def extrair_dados(distribuidora: str, modo_execucao: str) -> list[dict]:
    """Escolhe a fonte dos dados de acordo com o modo de execução."""

    if modo_execucao == "online":
        return extrair_dados_online(distribuidora)

    if modo_execucao == "offline":
        return carregar_dados_offline(distribuidora)

    raise ValueError("O modo de execução deve ser 'online' ou 'offline'.")


# -----------------------------------------------------------------------------
# ETAPA 2. TRATAMENTO DOS DADOS
# -----------------------------------------------------------------------------

def tratar_dados(registros: list[dict], distribuidora: str) -> pd.DataFrame:
    """Transforma os registros brutos em uma tabela pronta para análise."""

    print("[2/6] Tratando e validando os dados...")
    dados = pd.DataFrame(registros)

    colunas_ausentes = [
        coluna for coluna in COLUNAS_ANEEL if coluna not in dados.columns
    ]

    if colunas_ausentes:
        raise ValueError(
            "As seguintes colunas não foram encontradas: "
            + ", ".join(colunas_ausentes)
        )

    dados = dados[COLUNAS_ANEEL].copy()
    dados = dados.rename(columns=NOMES_DAS_COLUNAS)
    dados = dados[dados["distribuidora"] == distribuidora].copy()

    if dados.empty:
        raise ValueError(f"Não existem registros de {distribuidora} após o filtro.")

    dados["data_geracao_dados"] = pd.to_datetime(
        dados["data_geracao_dados"], errors="coerce"
    )
    dados["mes_referencia"] = pd.to_datetime(
        dados["mes_referencia"], errors="coerce"
    )

    for coluna in COLUNAS_NUMERICAS:
        dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")
        dados[coluna] = dados[coluna].fillna(0).astype("int64")

    if (dados[COLUNAS_NUMERICAS] < 0).any().any():
        raise ValueError("Foram encontrados valores negativos nas colunas de volume.")

    for coluna in ["faturas_sem_leitura", "faturas_com_leitura"]:
        if (dados[coluna] > dados["quantidade_faturas"]).any():
            raise ValueError(
                f"A coluna {coluna} possui valores maiores que a quantidade de faturas."
            )

    dados = dados.dropna(subset=["mes_referencia", "codigo_municipio"])
    dados["codigo_municipio"] = dados["codigo_municipio"].astype("string")
    dados["data_geracao_dados"] = dados["data_geracao_dados"].dt.strftime("%Y-%m-%d")
    dados["mes_referencia"] = dados["mes_referencia"].dt.strftime("%Y-%m-%d")

    quantidade_antes = len(dados)
    dados = dados.drop_duplicates(
        subset=["distribuidora", "mes_referencia", "codigo_municipio"],
        keep="last",
    )
    duplicidades_removidas = quantidade_antes - len(dados)

    logging.info(
        "Tratamento concluído. Válidos: %s. Duplicidades removidas: %s.",
        len(dados),
        duplicidades_removidas,
    )

    return dados.reset_index(drop=True)


# -----------------------------------------------------------------------------
# ETAPA 3. CARGA NO BANCO DE DADOS
# -----------------------------------------------------------------------------

def salvar_no_banco(dados: pd.DataFrame, distribuidora: str) -> None:
    """Atualiza os registros da distribuidora no banco SQLite."""

    print("[3/6] Atualizando o banco de dados SQLite...")

    with sqlite3.connect(ARQUIVO_BANCO) as conexao:
        tabela_existe = conexao.execute(
            """
            SELECT COUNT(*)
            FROM sqlite_master
            WHERE type = 'table' AND name = 'indicadores_faturamento'
            """
        ).fetchone()[0]

        if tabela_existe:
            # Excluímos somente a distribuidora atual antes de inserir sua nova carga.
            conexao.execute(
                "DELETE FROM indicadores_faturamento WHERE distribuidora = ?",
                (distribuidora,),
            )
            dados.to_sql(
                name="indicadores_faturamento",
                con=conexao,
                if_exists="append",
                index=False,
            )
        else:
            dados.to_sql(
                name="indicadores_faturamento",
                con=conexao,
                if_exists="replace",
                index=False,
            )

        conexao.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_distribuidora_mes
            ON indicadores_faturamento(distribuidora, mes_referencia)
            """
        )

    logging.info("Banco atualizado com %s registros de %s.", len(dados), distribuidora)


# -----------------------------------------------------------------------------
# ETAPA 4. CONSULTAS SQL
# -----------------------------------------------------------------------------

def executar_consulta_sql(
    caminho_do_sql: Path,
    distribuidora: str,
) -> pd.DataFrame:
    """Executa um arquivo SQL para a distribuidora selecionada."""

    consulta = caminho_do_sql.read_text(encoding="utf-8")

    with sqlite3.connect(ARQUIVO_BANCO) as conexao:
        resultado = pd.read_sql_query(
            sql=consulta,
            con=conexao,
            params={"distribuidora": distribuidora},
        )

    return resultado


def calcular_indicadores(
    distribuidora: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula os KPIs mensais e os alertas municipais."""

    print("[4/6] Calculando KPIs e identificando alertas com SQL...")

    kpis_mensais = executar_consulta_sql(ARQUIVO_SQL_KPIS, distribuidora)
    alertas_municipios = executar_consulta_sql(ARQUIVO_SQL_ALERTAS, distribuidora)

    if kpis_mensais.empty:
        raise ValueError(f"O banco não possui indicadores para {distribuidora}.")

    logging.info(
        "Consultas concluídas. Períodos: %s. Alertas: %s.",
        len(kpis_mensais),
        len(alertas_municipios),
    )

    return kpis_mensais, alertas_municipios

