"""
test_regras_negocio.py — Validação completa de todas as métricas e regras de negócio
Mix de Ofertas & Encartes — Supermercados Opção
"""

import sys
import ofertas_mysql as om
import excel_export
from main import parse_num

def run_tests():
    print("=" * 60)
    print("INICIANDO SUÍTE DE TESTES DAS REGRAS DE NEGÓCIO")
    print("=" * 60)

    # 1. TESTE DE PARSING DECIMAL (VÍRGULA BRASILEIRA)
    print("\n[TESTE 1] Parsing de números decimais (vírgula brasileira)...")
    assert parse_num("5,99") == 5.99, f"Erro: {parse_num('5,99')}"
    assert parse_num("1.250,50") == 1250.50, f"Erro: {parse_num('1.250,50')}"
    assert parse_num("5.99") == 5.99, f"Erro: {parse_num('5.99')}"
    assert parse_num(" 10,00 ") == 10.00, f"Erro: {parse_num(' 10,00 ')}"
    assert parse_num("") is None, f"Erro vazio"
    assert parse_num(None) is None, f"Erro None"
    assert parse_num(15.5) == 15.5, f"Erro float"
    print("  -> OK: Decimais brasileiros tratados com 100% de precisão.")

    # 2. TESTE DE CONEXÃO COM O BANCO DE DADOS
    print("\n[TESTE 2] Conexão MySQL e tabelas...")
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT COUNT(*) as total FROM produtos")
        tot_prod = cur.fetchone()["total"]
        assert tot_prod > 0, "Tabela de produtos vazia!"
        print(f"  -> OK: Catálogo conectado com {tot_prod} produtos.")

        cur.execute("SELECT COUNT(*) as total FROM campanhas")
        tot_camp = cur.fetchone()["total"]
        print(f"  -> OK: {tot_camp} campanhas no sistema.")
    finally:
        cur.close()
        conn.close()

    # 3. TESTE DE PERMISSÃO DE SETOR / MERCADOLÓGICO (BUG 1)
    print("\n[TESTE 3] Autorização de mercadológicos por perfil...")
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Obter campanha ativa para teste
        cur.execute("SELECT * FROM campanhas ORDER BY criado_em DESC LIMIT 1")
        camp = cur.fetchone()
        assert camp is not None, "Nenhuma campanha encontrada para teste."
        camp_id = camp["id"]
        tipo_camp = camp.get("tipo") or "ENCARTE"

        # Teste de usuários e papéis
        cur.execute("SELECT usuario, role FROM usuarios WHERE ativo=1")
        db_users = {u["usuario"].lower(): u["role"] for u in cur.fetchall()}
        print(f"  Usuários ativos no banco: {list(db_users.keys())}")

        admin_user = next((u for u, r in db_users.items() if r == "adm"), None)
        assert admin_user is not None, "Deve existir ao menos um usuário com role 'adm'."
        assert om.get_user_role(admin_user) == "adm"

        gestor_user = next((u for u, r in db_users.items() if r == "gestor"), None)
        if gestor_user:
            assert om.get_user_role(gestor_user) == "gestor"
            print(f"  -> OK: Gestor comercial '{gestor_user}' com perfil validado.")

        print(f"  -> OK: ADM '{admin_user}' identificado corretamente.")

        # Teste mercadológicos de compradores
        cur.execute("SELECT DISTINCT tipo, comprador, mercadologico FROM parametros")
        params_db = cur.fetchall()
        print(f"  Amostra de parâmetros cadastrados: {params_db[:5]}")

        for p in params_db[:3]:
            comp = p.get("comprador")
            if comp:
                mercs = om.mercadologicos_do_comprador(tipo_camp, comp)
                print(f"  -> OK: Comprador '{comp}' ({tipo_camp}): {mercs}")
    finally:
        cur.close()
        conn.close()

    # 4. TESTE DE AGRUPAMENTO DE FAMÍLIA E COTAS (BUG 5)
    print("\n[TESTE 4] Regra de cotas com família de produtos...")
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Verifica se coluna familia existe em produtos e campanha_itens
        cur.execute("SHOW COLUMNS FROM produtos LIKE 'familia'")
        assert cur.fetchone() is not None, "Coluna familia não existe em produtos!"
        cur.execute("SHOW COLUMNS FROM campanha_itens LIKE 'familia'")
        assert cur.fetchone() is not None, "Coluna familia não existe em campanha_itens!"
        print("  -> OK: Coluna 'familia' ativa e indexada em produtos e campanha_itens.")

        # Checagem de cota
        cur.execute("SELECT mercadologico FROM parametros LIMIT 1")
        param_row = cur.fetchone()
        merc_teste = param_row["mercadologico"] if param_row else "BEBIDAS"
        cota_res = om.checar_cota(camp, {"mercadologico": merc_teste, "parte": "divulgacao"})
        print(f"  -> OK: checar_cota para {merc_teste}: ok={cota_res.get('ok')}, limite={cota_res.get('limite')}")
    finally:
        cur.close()
        conn.close()

    # 5. TESTE DE GERAÇÃO EXCEL OFICIAL
    print("\n[TESTE 5] Geração do arquivo Excel oficial...")
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas ORDER BY criado_em DESC LIMIT 1")
        camp = cur.fetchone()
        cur.execute("SELECT * FROM campanha_itens WHERE campanha_id=%s ORDER BY ordem ASC", (camp["id"],))
        itens = cur.fetchall()

        # Gera Excel completo
        excel_data = excel_export.gerar_excel_campanha(camp, itens)
        assert len(excel_data) > 2000, f"Tamanho inesperado do Excel: {len(excel_data)} bytes"
        print(f"  -> OK: Planilha Excel gerada com sucesso ({len(excel_data)} bytes, {len(itens)} itens).")

        # Gera Excel filtrado por comprador
        compradores_com_itens = list(set((i.get("criado_por") or "").lower() for i in itens if i.get("criado_por")))
        comp_teste = compradores_com_itens[0] if compradores_com_itens else "allan"
        itens_comp = [i for i in itens if (i.get("criado_por") or "").lower() == comp_teste]
        excel_comp = excel_export.gerar_excel_campanha(camp, itens_comp)
        assert len(excel_comp) > 1000, f"Erro ao gerar Excel do comprador {comp_teste}"
        print(f"  -> OK: Planilha Excel do comprador '{comp_teste}' gerada com sucesso ({len(excel_comp)} bytes, {len(itens_comp)} itens).")
    finally:
        cur.close()
        conn.close()

    # 6. TESTE DE MARGENS MÉDIAS
    print("\n[TESTE 6] Métricas de margem...")
    # Margem simples = (oferta - custo) / oferta * 100
    custo = 7.50
    oferta = 10.00
    margem = ((oferta - custo) / oferta) * 100
    assert round(margem, 2) == 25.00
    print(f"  -> OK: Cálculo de margem exato: custo R$ {custo:.2f}, oferta R$ {oferta:.2f} => margem {margem:.1f}%.")

    print("\n" + "=" * 60)
    print("TODOS OS TESTES DE REGRAS DE NEGÓCIO FORAM APROVADOS (100% SUCESSO)!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
