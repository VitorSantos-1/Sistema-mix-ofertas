# Sistema de Ofertas e Mix de Produtos

Solução de apoio à gestão de ofertas e mix de produtos que combina um pipeline de dados em Python
(Pandas) — que limpa a base de ofertas, propaga informações de produto e calcula margens — com um
módulo em Google Apps Script que padroniza as frentes de venda e os eventos sazonais diretamente nas
planilhas usadas pela operação.

> **Nota de confidencialidade:** os dados presentes neste repositório são fictícios, gerados apenas
> para demonstração. Os dados reais da operação em que o projeto foi utilizado são confidenciais e
> estão protegidos — nenhum dado real, credencial ou informação de terceiros foi incluído aqui.

---

## Visão Geral

O projeto organiza duas pontas do trabalho de montar uma tabela de ofertas: o **tratamento do dado**
(limpeza, preenchimento de campos e cálculo de margem, em Python) e a **operação no dia a dia**
(padronização do mix e dos eventos nas planilhas, em Apps Script). Juntos, reduzem o retrabalho manual
e diminuem o risco de erro em uma rotina que impacta diretamente preço e margem.

## Contexto de Negócio

A definição das ofertas de um supermercado passa por planilhas que concentram centenas de itens,
preços, custos e períodos. Feito manualmente, esse processo é propenso a erros de digitação, a campos
incompletos e a margens calculadas de forma inconsistente — cada um deles com potencial de comprometer
a rentabilidade de uma campanha inteira. Automatizar a limpeza e o cálculo devolve confiabilidade e
velocidade a uma decisão comercial recorrente.

## O Problema que Resolve

- **Bases de ofertas sujas e incompletas:** campos de produto que faltam ao longo das linhas.
- **Cálculo de margem inconsistente**, feito à mão e sujeito a erro.
- **Falta de padronização** das frentes de venda e dos eventos sazonais entre planilhas.

## Público e Decisões Apoiadas

- **Comercial e Compras:** definem ofertas com margem calculada de forma confiável.
- **Operação de loja:** trabalha com um mix padronizado e consistente entre eventos.

## Impacto e Valor Gerado

- Elimina etapas manuais de limpeza e preenchimento da base de ofertas.
- Padroniza o cálculo de margem, reduzindo o risco de campanha no prejuízo.
- Uniformiza o mix e os eventos sazonais, acelerando a montagem das ofertas.

---

## Arquitetura e Abordagem Técnica

```text
CSV de ofertas
     |
     v
pipeline_ofertas.py (Pandas)
   - limpeza de dados
   - propagação de informações de produto (forward-fill)
   - cálculo de margem
     |
     v
Base tratada  ---->  mix_ofertas.gs (Google Apps Script)
                     padroniza frentes de venda e eventos sazonais nas planilhas
```

- **`pipeline_ofertas.py`** — ETL em Pandas: lê o CSV de ofertas, trata valores ausentes, propaga
  informações de produto ao longo das linhas (forward-fill) e calcula a margem por item.
- **`mix_ofertas.gs`** — automação em Google Apps Script que padroniza o mix de produtos e os eventos
  sazonais diretamente nas planilhas operacionais.

## Stack

Python - Pandas - ETL - Google Apps Script - Google Sheets.

## Como Rodar

```bash
pip install pandas
python pipeline_ofertas.py   # usa dados_exemplo.csv
```

## Estrutura do Projeto

```text
pipeline_ofertas.py   -> ETL do CSV de ofertas (limpeza, forward-fill, cálculo de margem)
mix_ofertas.gs        -> Automação em Apps Script (padronização de mix e eventos)
dados_exemplo.csv     -> Base de exemplo (fictícia)
```

## Autor

José Vitor Santos Pinheiro — Análise de Dados e Inteligência Comercial (Varejo e Supply Chain).
Contato: vytorsantt@gmail.com
