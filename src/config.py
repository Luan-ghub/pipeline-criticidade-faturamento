from pathlib import Path


# CONFIGURAÇÕES INICIAIS

### Projeto
PASTA_DO_PROJETO = Path(__file__).resolve().parents[1]  # pasta do projeto identificada de forma automática, ainda que mude de diretório

### Dados e consultas
PASTA_DE_DADOS = PASTA_DO_PROJETO / "data"
PASTA_DE_CONSULTAS = PASTA_DO_PROJETO / "sql"
PASTA_DE_SAIDAS = PASTA_DO_PROJETO / "outputs"
PASTA_DE_LOGS = PASTA_DO_PROJETO / "logs"

### Arquivos
ARQUIVO_DADOS_BRUTOS_LEGADO = PASTA_DE_DADOS / "dados_brutos_aneel.json"
ARQUIVO_CATALOGO_DISTRIBUIDORAS = PASTA_DE_DADOS / "distribuidoras_disponiveis.csv"
ARQUIVO_BANCO = PASTA_DE_DADOS / "indicadores_faturamento.db"
ARQUIVO_LOG = PASTA_DE_LOGS / "execucao_pipeline.log"
ARQUIVO_SQL_KPIS = PASTA_DE_CONSULTAS / "01_kpis_mensais.sql"
ARQUIVO_SQL_ALERTAS = PASTA_DE_CONSULTAS / "02_alertas_municipios.sql"
ARQUIVO_KPIS = PASTA_DE_SAIDAS / "kpis_mensais.csv"
ARQUIVO_ALERTAS = PASTA_DE_SAIDAS / "alertas_municipios.csv"
ARQUIVO_RELATORIO = PASTA_DE_SAIDAS / "relatorio_faturamento.html"

### Seleção da distribuidora
DISTRIBUIDORA = "Neoenergia Coelba"  # Atualizar se desejar outra distribuidora como padrão {distribuidoras_disponiveis.csv}.

### Modo de execução: "offline" ou "online"
# offline: utiliza o último arquivo salvo para a distribuidora.
# online: consulta novamente a API pública da ANEEL.
MODO_EXECUCAO = "offline"

### URL e identificador do conjunto de dados da ANEEL
URL_API_ANEEL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
ID_RECURSO_ANEEL = "fd10c9d4-cb76-4020-a322-e79afb13eaf7"

### Configurações da consulta à API
TAMANHO_DA_PAGINA = 3000
TEMPO_LIMITE_API = 90
MAXIMO_TENTATIVAS_API = 3

### Colunas da ANEEL obrigatórias para análise
COLUNAS_ANEEL = [
    "DatGeracaoConjuntoDados",
    "SigAgente",
    "DatReferenciaInformada",
    "CodMunicipioIBGE",
    "QtdUCAtiva",
    "QtdUCAtivaFat",
    "QtdFatura",
    "QtdFaturaSemLeitura",
    "QtdRefaturamento",
    "QtdFaturaAcerto",
    "QtdFaturaComLeitura",
]

### Dicionário para renomear e padronizar as colunas
NOMES_DAS_COLUNAS = {
    "DatGeracaoConjuntoDados": "data_geracao_dados",
    "SigAgente": "distribuidora",
    "DatReferenciaInformada": "mes_referencia",
    "CodMunicipioIBGE": "codigo_municipio",
    "QtdUCAtiva": "unidades_consumidoras_ativas",
    "QtdUCAtivaFat": "unidades_consumidoras_faturadas",
    "QtdFatura": "quantidade_faturas",
    "QtdFaturaSemLeitura": "faturas_sem_leitura",
    "QtdRefaturamento": "refaturamentos",
    "QtdFaturaAcerto": "faturas_de_acerto",
    "QtdFaturaComLeitura": "faturas_com_leitura",
}

COLUNAS_NUMERICAS = [
    "unidades_consumidoras_ativas",
    "unidades_consumidoras_faturadas",
    "quantidade_faturas",
    "faturas_sem_leitura",
    "refaturamentos",
    "faturas_de_acerto",
    "faturas_com_leitura",
]
