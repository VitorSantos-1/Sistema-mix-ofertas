# Sistema de Ofertas e Mix de Produtos

Solucao de apoio a gestao de ofertas e mix de produtos que combina um pipeline de dados em Python
(Pandas) — que limpa a base de ofertas, propaga informacoes de produto e calcula margens — com um
modulo em Google Apps Script que padroniza as frentes de venda e os eventos sazonais diretamente nas
planilhas usadas pela operacao.

> **Nota de confidencialidade:** os dados presentes neste repositorio sao ficticios, gerados apenas
> para demonstracao. Os dados reais da operacao em que o projeto foi utilizado sao confidenciais e
> estao protegidos — nenhum dado real, credencial ou informacao de terceiros foi incluido aqui.

---

## Visao Geral

O projeto organiza duas pontas do trabalho de montar uma tabela de ofertas: o **tratamento do dado**
(limpeza, preenchimento de campos e calculo de margem, em Python) e a **operacao no dia a dia**
(padronizacao do mix e dos eventos nas planilhas, em Apps Script). Juntos, reduzem o retrabalho
manual e diminuem o risco de erro em uma rotina que impacta diretamente preco e margem.

## Contexto de Negocio

A definicao das ofertas de um supermercado passa por planilhas que concentram centenas de itens,
precos, custos e periodos. Feito manualmente, esse processo e propenso a erros de digitacao, a
campos incompletos e a margens calculadas de forma inconsistente — cada um deles com potencial de
comprometer a rentabilidade de uma campanha inteira. Automatizar a limpeza e o calculo devolve
confiabilidade e velocidade a uma decisao comercial recorrente.

## O Problema que Resolve

- **Bases de ofertas sujas e incompletas:** campos de produto que faltam ao longo das linhas.
- **Calculo de margem inconsistente**, feito a mao e sujeito a erro.
- **Falta de padronizacao** das frentes de venda e dos eventos sazonais entre planilhas.

## Publico e Decisoes Apoiadas

- **Comercial e Compras:** definem ofertas com margem calculada de forma confiavel.
- **Operacao de loja:** trabalha com um mix padronizado e consistente entre eventos.

## Impacto e Valor Gerado

- Elimina etapas manuais de limpeza e preenchimento da base de ofertas.
- Padroniza o calculo de margem, reduzindo o risco de campanha no prejuizo.
- Uniformiza o mix e os eventos sazonais, acelerando a montagem das ofertas.

---

## Arquitetura e Abordagem Tecnica

```text
CSV de ofertas
     |
     v
pipeline_ofertas.py (Pandas)
   - limpeza de dados
   - propagacao de informacoes de produto (forward-fill)
   - calculo de margem
     |
     v
Base tratada  ---->  mix_ofertas.gs (Google Apps Script)
                     padroniza frentes de venda e eventos sazonais nas planilhas
```

- **`pipeline_ofertas.py`** — ETL em Pandas: le o CSV de ofertas, trata valores ausentes, propaga
  informacoes de produto ao longo das linhas (forward-fill) e calcula a margem por item.
- **`mix_ofertas.gs`** — automacao em Google Apps Script que padroniza o mix de produtos e os eventos
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
pipeline_ofertas.py   -> ETL do CSV de ofertas (limpeza, forward-fill, calculo de margem)
mix_ofertas.gs        -> Automacao em Apps Script (padronizacao de mix e eventos)
dados_exemplo.csv     -> Base de exemplo (ficticia)
```

## Autor

Jose Vitor Santos Pinheiro — Analise de Dados e Inteligencia Comercial (Varejo e Supply Chain).
Contato: vytorsantt@gmail.com
