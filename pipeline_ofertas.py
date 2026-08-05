import pandas as pd

# 1. Carrega os dados do CSV
dados = pd.read_csv("dados.csv", sep=";", encoding="latin-1")

# Renomeia as colunas para evitar os problemas de acentuação do arquivo original
dados.columns = [
    'Codigo', 'Descricao', 'Qtde_Venda', 'Preco_Oferta', 
    'Data_Inicio', 'Data_Termino', 'Custo_Imposto', 'Preco_Normal', 'Margem'
]

# 2. Conversão de colunas numéricas (substitui vírgula por ponto)
cols_num = ['Qtde_Venda', 'Preco_Oferta', 'Custo_Imposto', 'Preco_Normal', 'Margem']
for col in cols_num:
    dados[col] = pd.to_numeric(dados[col].astype(str).str.replace(',', '.'), errors='coerce')

# 3. Propagação (Fill Forward) de dados do Produto para as linhas das lojas
# As linhas de onde extraímos os dados do produto têm a coluna "Codigo" preenchida
eh_produto = dados['Codigo'].notna()
# Pega a descrição do produto e propaga para as linhas das lojas
dados['Produto'] = dados['Descricao'].where(eh_produto).ffill()
# Pega o preço normal do produto e propaga para as linhas das lojas
dados['Preco_Normal_Prod'] = dados['Preco_Normal'].where(eh_produto).ffill()
# Pega o preço de oferta do produto e propaga para as linhas das lojas
dados['Preco_Oferta_Prod'] = dados['Preco_Oferta'].where(eh_produto).ffill()
# Pega o custo do imposto do produto e propaga para as linhas das lojas
dados['Custo_Imposto_Prod'] = dados['Custo_Imposto'].where(eh_produto).ffill()

# 4. Filtra apenas as linhas das Lojas (a descrição contém "Lj")
dados_lojas = dados[dados['Descricao'].str.contains('Lj0', na=False, case=False)].copy()
dados_lojas = dados_lojas.rename(columns={'Descricao': 'Loja'})

# 5. Calcula o Valor (Qtde Vendida * Preço de Oferta do Produto)
dados_lojas['Valor'] = dados_lojas['Qtde_Venda'] * dados_lojas['Preco_Oferta_Prod']

# 6. Cria a Tabela Dinâmica colocando Lojas nas colunas
df_pivot = dados_lojas.pivot_table(
    index=['Produto', 'Custo_Imposto_Prod', 'Preco_Normal_Prod', 'Preco_Oferta_Prod'],
    columns='Loja',
    values=['Qtde_Venda', 'Margem', 'Valor'],
    aggfunc='sum'
)

# 7. Organiza os nomes das colunas
# Une as métricas com o nome da loja, ex: "Lj01-Centro - Margem"
df_pivot.columns = [f"{loja} - {metrica}" for metrica, loja in df_pivot.columns]
df_pivot = df_pivot.reset_index()

# Opcional: Arredonda valores decimais
df_pivot = df_pivot.round({'Custo_Imposto_Prod': 2, 'Preco_Normal_Prod': 2, 'Preco_Oferta_Prod': 2})

# 8. Exibe e salva o resultado final num Excel
print("Resumo das primeiras linhas da tabela organizada:\n")
print(df_pivot.head())

nome_arquivo_saida = "Relatorio_Organizacao_Lojas.xlsx"
try:
    df_pivot.to_excel(nome_arquivo_saida, index=False)
    print(f"\nSucesso! Planilha organizada gerada: '{nome_arquivo_saida}' na pasta atual.")
except ModuleNotFoundError:
    print("\nPara salvar em Excel, providencie o módulo rodando no terminal: pip install openpyxl")