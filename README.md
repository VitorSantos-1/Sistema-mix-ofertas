# 🏷️ Sistema de Ofertas e Mix de Produtos

Gestão de **ofertas e mix de produtos** combinando um **pipeline em Python (Pandas)** que limpa dados de CSV,
propaga informações de produto (*forward-fill*) e calcula margens, com um módulo em **Google Apps Script** que
padroniza frentes de venda e eventos sazonais.

> ⚠️ **Aviso sobre os dados**
> Os dados neste repositório são **fictícios**, gerados apenas para demonstração. Os dados reais da
> operação em que o projeto foi usado são **confidenciais e estão protegidos** — nada real, credencial
> ou informação de terceiros foi incluído aqui.

## 🎯 Componentes
- `pipeline_ofertas.py` — ETL do CSV de ofertas (limpeza, propagação, cálculo de margem).
- `mix_ofertas.gs` — automação em Apps Script (v9.2) para padronizar o mix nas planilhas.

## ▶️ Como rodar
```bash
pip install pandas
python pipeline_ofertas.py   # usa dados_exemplo.csv
```

---

### 🧰 Competências demonstradas
`Python` · `Pandas` · `ETL` · `Google Apps Script` · `Google Sheets`

### 👤 Autor
**José Vitor Santos Pinheiro** — Analista de Dados / BI / Ciência de Dados · vytorsantt@gmail.com
