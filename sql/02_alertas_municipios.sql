-- Consulta comparativa de município x histórico.


-- Tabela temporária das taxas municipais
WITH taxas_municipais AS (
    SELECT
        mes_referencia,
        codigo_municipio,
        quantidade_faturas,
        100.0 * refaturamentos / NULLIF(quantidade_faturas, 0) AS taxa_refaturamento_pct,
        100.0 * faturas_sem_leitura / NULLIF(quantidade_faturas, 0) AS taxa_sem_leitura_pct
    FROM indicadores_faturamento
    WHERE distribuidora = :distribuidora
),

-- Tabela de comparação da média dos 3 meses anteriores
comparacao_historica AS (
    SELECT
        atual.mes_referencia,
        atual.codigo_municipio,
        atual.quantidade_faturas,
        atual.taxa_refaturamento_pct,
        atual.taxa_sem_leitura_pct,
        AVG(historico.taxa_refaturamento_pct) AS media_refaturamento_3_meses,
        AVG(historico.taxa_sem_leitura_pct) AS media_sem_leitura_3_meses,
        COUNT(historico.mes_referencia) AS meses_no_historico
    FROM taxas_municipais AS atual
    LEFT JOIN taxas_municipais AS historico
        ON historico.codigo_municipio = atual.codigo_municipio
       AND historico.mes_referencia >= DATE(atual.mes_referencia, '-3 months')
       AND historico.mes_referencia < atual.mes_referencia
    GROUP BY
        atual.mes_referencia,
        atual.codigo_municipio,
        atual.quantidade_faturas,
        atual.taxa_refaturamento_pct,
        atual.taxa_sem_leitura_pct
),

-- Tabela de classificação de acordo com a média
classificacao AS (
    SELECT
        *,
        -- Atenção: taxa atual pelo menos duas vezes maior que a média e diferença mínima de 1%. Se a média for zero, a taxa deve chegar a 1%.
        CASE
            WHEN media_refaturamento_3_meses > 0
             AND taxa_refaturamento_pct >= media_refaturamento_3_meses * 2
             AND taxa_refaturamento_pct - media_refaturamento_3_meses >= 1
                THEN 1
            WHEN media_refaturamento_3_meses = 0
             AND taxa_refaturamento_pct >= 1
                THEN 1
            ELSE 0
        END AS alerta_refaturamento,

        CASE
            WHEN media_sem_leitura_3_meses > 0
             AND taxa_sem_leitura_pct >= media_sem_leitura_3_meses * 2
             AND taxa_sem_leitura_pct - media_sem_leitura_3_meses >= 1
                THEN 1
            WHEN media_sem_leitura_3_meses = 0
             AND taxa_sem_leitura_pct >= 1
                THEN 1
            ELSE 0
        END AS alerta_sem_leitura,

        -- Crítico: taxa atual pelo menos três vezes maior que a média e diferença mínima de 2%. Se a média for zero, a taxa deve chegar a 2%.
        CASE
            WHEN media_refaturamento_3_meses > 0
             AND taxa_refaturamento_pct >= media_refaturamento_3_meses * 3
             AND taxa_refaturamento_pct - media_refaturamento_3_meses >= 2
                THEN 1
            WHEN media_refaturamento_3_meses = 0
             AND taxa_refaturamento_pct >= 2
                THEN 1
            ELSE 0
        END AS critico_refaturamento,

        CASE
            WHEN media_sem_leitura_3_meses > 0
             AND taxa_sem_leitura_pct >= media_sem_leitura_3_meses * 3
             AND taxa_sem_leitura_pct - media_sem_leitura_3_meses >= 2
                THEN 1
            WHEN media_sem_leitura_3_meses = 0
             AND taxa_sem_leitura_pct >= 2
                THEN 1
            ELSE 0
        END AS critico_sem_leitura

    FROM comparacao_historica
),

-- Tabela para geração de alertas
alertas AS (
    SELECT
        mes_referencia,
        codigo_municipio,
        quantidade_faturas,
        ROUND(taxa_refaturamento_pct, 2) AS taxa_refaturamento_pct,
        ROUND(media_refaturamento_3_meses, 2) AS media_refaturamento_3_meses,
        ROUND(taxa_refaturamento_pct - media_refaturamento_3_meses, 2) AS variacao_refaturamento_pp,
        ROUND(taxa_sem_leitura_pct, 2) AS taxa_sem_leitura_pct,
        ROUND(media_sem_leitura_3_meses, 2) AS media_sem_leitura_3_meses,
        ROUND(taxa_sem_leitura_pct - media_sem_leitura_3_meses, 2) AS variacao_sem_leitura_pp,
        CASE
            WHEN alerta_refaturamento = 1 AND alerta_sem_leitura = 1
                THEN 'Refaturamento e faturas sem leitura'
            WHEN alerta_refaturamento = 1
                THEN 'Refaturamento'
            ELSE 'Faturas sem leitura'
        END AS motivo_alerta,

        CASE
            WHEN critico_refaturamento = 1 OR critico_sem_leitura = 1
                THEN 'CRITICO'
            ELSE 'ATENCAO'
        END AS nivel_alerta

    FROM classificacao
    WHERE meses_no_historico >= 3
      AND quantidade_faturas >= 100
      AND (alerta_refaturamento = 1 OR alerta_sem_leitura = 1)
)

-- Consulta final
SELECT *
FROM alertas
WHERE mes_referencia = (
    SELECT MAX(mes_referencia)
    FROM indicadores_faturamento
    WHERE distribuidora = :distribuidora
)
ORDER BY
    CASE nivel_alerta WHEN 'CRITICO' THEN 1 ELSE 2 END,
    quantidade_faturas DESC;

