-- Consulta resume os dados municipais em indicadores mensais da distribuidora.

-- Tabela temporária de resumo mensal
WITH resumo_mensal AS (
    SELECT
        mes_referencia,
        SUM(unidades_consumidoras_ativas) AS unidades_consumidoras_ativas,
        SUM(unidades_consumidoras_faturadas) AS unidades_consumidoras_faturadas,
        SUM(quantidade_faturas) AS quantidade_faturas,
        SUM(faturas_sem_leitura) AS faturas_sem_leitura,
        SUM(refaturamentos) AS refaturamentos,
        SUM(faturas_de_acerto) AS faturas_de_acerto,
        SUM(faturas_com_leitura) AS faturas_com_leitura
    FROM indicadores_faturamento
    WHERE distribuidora = :distribuidora
    GROUP BY mes_referencia
),

-- Tabela temporária comparativa com volume de faturas do mês anterior
comparacao_mensal AS (
    SELECT
        *,
        LAG(quantidade_faturas) OVER (ORDER BY mes_referencia) AS faturas_mes_anterior
    FROM resumo_mensal
)

-- Tabela relacional final
SELECT
    mes_referencia,
    unidades_consumidoras_ativas,
    unidades_consumidoras_faturadas,
    quantidade_faturas,
    faturas_sem_leitura,
    refaturamentos,
    faturas_de_acerto,
    faturas_com_leitura,
    ROUND(100.0 * refaturamentos / NULLIF(quantidade_faturas, 0), 2) AS taxa_refaturamento_pct,
    ROUND(100.0 * faturas_sem_leitura / NULLIF(quantidade_faturas, 0), 2) AS taxa_sem_leitura_pct,
    ROUND(100.0 * faturas_de_acerto / NULLIF(quantidade_faturas, 0), 2) AS taxa_acerto_pct,
    ROUND(100.0 * faturas_com_leitura / NULLIF(quantidade_faturas, 0), 2) AS cobertura_leitura_pct,
    ROUND(100.0 * (quantidade_faturas - faturas_mes_anterior) / NULLIF(faturas_mes_anterior, 0), 2) AS variacao_faturas_pct
FROM comparacao_mensal
ORDER BY mes_referencia DESC;

