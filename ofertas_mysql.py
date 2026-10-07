"""
ofertas_mysql.py — Camada de Banco de Dados MySQL para o Sistema Mix de Ofertas
Banco: mix_ofertas | Servidor: localhost / 127.0.0.1 | Sem senha (root)
"""

import os
import re
import datetime
from datetime import date
from typing import Optional, Dict, Any, List, Tuple
import mysql.connector
from mysql.connector import Error

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "mix_ofertas")


def get_connection():
    """Retorna uma conexão aberta com o MySQL configurada (tenta localhost e fallback para 192.168.10.177)."""
    try:
        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            autocommit=False,
        )
    except Error:
        if DB_HOST in ("localhost", "127.0.0.1"):
            try:
                return mysql.connector.connect(
                    host="192.168.10.177",
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    charset="utf8mb4",
                    collation="utf8mb4_unicode_ci",
                    autocommit=False,
                )
            except Error:
                pass
        raise


def tipos_definidos() -> List[str]:
    """Lista os tipos de campanha definidos (uma linha por tipo em parametros_pool,
    mais qualquer tipo que só exista em parametros). É a fonte da verdade dos tipos."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT tipo FROM parametros_pool")
            tipos = [r[0] for r in cur.fetchall() if r and r[0]]
            cur.execute("SELECT DISTINCT tipo FROM parametros")
            for row in cur.fetchall():
                if row and row[0] and row[0] not in tipos:
                    tipos.append(row[0])
            return tipos
        finally:
            cur.close()
            conn.close()
    except Exception:
        return ["ENCARTE", "ALERTA", "FDS_SAZONAL"]


def tipo_param(t: str) -> str:
    """Resolve o tipo de campanha para a CHAVE de parâmetros existente.
    1) casa exatamente (ou sem diferenciar maiúsculas) com um tipo definido;
    2) senão, cai no mapeamento por palavra-chave (compatibilidade com o legado)."""
    if not t:
        return "ENCARTE"
    key = str(t).strip()
    try:
        tipos = tipos_definidos()
        for pt in tipos:              # casamento exato
            if pt == key:
                return pt
        for pt in tipos:              # sem diferenciar maiúsculas
            if str(pt).upper() == key.upper():
                return pt
    except Exception:
        pass
    t_upper = key.upper()
    if "FDS" in t_upper or "FIM DE SEMANA" in t_upper or "SAZONAL" in t_upper:
        return "FDS_SAZONAL"
    if "ALERTA" in t_upper:
        return "ALERTA"
    return "ENCARTE"


def init_mysql():
    """Garante que o banco mix_ofertas e suas tabelas existem."""
    print("Inicializando banco MySQL: mix_ofertas...")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS mix_ofertas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        cur.close()
        conn.close()
        print("  Banco 'mix_ofertas' verificado.")
    except Exception as e:
        print(f"  Aviso ao criar/verificar banco: {e}")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id VARCHAR(64) PRIMARY KEY,
            usuario VARCHAR(64) NOT NULL UNIQUE,
            nome VARCHAR(160) NOT NULL,
            senha VARCHAR(255) NOT NULL,
            cargo VARCHAR(120) DEFAULT 'Comprador',
            role VARCHAR(20) DEFAULT 'comprador',
            ativo TINYINT(1) DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parametros (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tipo VARCHAR(20) NOT NULL,
            mercadologico VARCHAR(160) NOT NULL,
            comprador VARCHAR(64) NOT NULL,
            meta_divulgacao INT NOT NULL DEFAULT 0,
            meta_interna INT NOT NULL DEFAULT 0,
            extra_div INT NOT NULL DEFAULT 0,
            extra_int INT NOT NULL DEFAULT 0,
            ordem INT NOT NULL DEFAULT 0,
            INDEX idx_tipo_merc (tipo, mercadologico)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parametros_pool (
            tipo VARCHAR(20) PRIMARY KEY,
            pool_interna INT NOT NULL DEFAULT 50,
            extra_pool INT NOT NULL DEFAULT 0,
            capa_max INT NOT NULL DEFAULT 16,
            app_max INT NOT NULL DEFAULT 5
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            codigo VARCHAR(64) PRIMARY KEY,
            descricao TEXT NOT NULL,
            mercadologico VARCHAR(160) DEFAULT 'Geral',
            preco_custo DECIMAL(12,2) DEFAULT NULL,
            preco_venda DECIMAL(12,2) DEFAULT NULL,
            familia VARCHAR(64) DEFAULT NULL,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_merc (mercadologico),
            INDEX idx_familia (familia)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS campanhas (
            id VARCHAR(64) PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            tipo VARCHAR(40) NOT NULL DEFAULT 'Encarte',
            status VARCHAR(20) NOT NULL DEFAULT 'ativa',
            periodo VARCHAR(160) DEFAULT '',
            data_inicio VARCHAR(40) DEFAULT '',
            data_fim VARCHAR(40) DEFAULT '',
            observacoes TEXT,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS campanha_itens (
            id VARCHAR(64) PRIMARY KEY,
            campanha_id VARCHAR(64) NOT NULL,
            tipo_linha VARCHAR(20) NOT NULL DEFAULT 'produto',
            nome_categoria VARCHAR(160) DEFAULT NULL,
            mercadologico VARCHAR(160) DEFAULT NULL,
            parte VARCHAR(20) NOT NULL DEFAULT 'divulgacao',
            ordem INT NOT NULL DEFAULT 0,
            linha INT NOT NULL DEFAULT 0,
            codigo VARCHAR(64) DEFAULT '',
            descricao TEXT,
            custo DECIMAL(12,2) DEFAULT NULL,
            preco_oferta DECIMAL(12,2) DEFAULT NULL,
            preco_app DECIMAL(12,2) DEFAULT NULL,
            observacao TEXT,
            destaque VARCHAR(20) DEFAULT NULL,
            classificacao_mix INT NOT NULL DEFAULT 2,
            familia VARCHAR(64) DEFAULT NULL,
            sellout VARCHAR(160) DEFAULT '',
            criado_por VARCHAR(64) DEFAULT '',
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_camp (campanha_id),
            INDEX idx_camp_prod (campanha_id, tipo_linha, codigo),
            INDEX idx_camp_fam (campanha_id, familia)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    # Migrações seguras (adiciona colunas novas se ainda não existirem)
    try:
        cur.execute("ALTER TABLE produtos ADD COLUMN familia VARCHAR(64) DEFAULT NULL")
        cur.execute("ALTER TABLE produtos ADD INDEX idx_familia (familia)")
        conn.commit()
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE campanha_itens ADD COLUMN familia VARCHAR(64) DEFAULT NULL")
        cur.execute("ALTER TABLE campanha_itens ADD INDEX idx_camp_fam (campanha_id, familia)")
        conn.commit()
    except Exception:
        pass

    # Autorização de cota: 'permanente'=1 soma no parâmetro global (todas as campanhas);
    # 'permanente'=0 (padrão) vale SÓ na campanha do pedido (somado em checar_cota).
    try:
        cur.execute("ALTER TABLE pedidos_autorizacao ADD COLUMN permanente TINYINT(1) NOT NULL DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    # Tipos de campanha editáveis: o nome do tipo é a chave. Alarga as colunas
    # para permitir nomes livres (ex.: "Fim de Semana", "Black Friday").
    for _alter in (
        "ALTER TABLE parametros MODIFY tipo VARCHAR(60) NOT NULL",
        "ALTER TABLE parametros_pool MODIFY tipo VARCHAR(60) NOT NULL",
        "ALTER TABLE campanhas MODIFY tipo VARCHAR(60) NOT NULL",
    ):
        try:
            cur.execute(_alter)
            conn.commit()
        except Exception:
            pass

    # Família agora só aparece na aba "Relação Completa": o consolidado/aba principal
    # mostram só o produto digitado. Colapsa grupos de família JÁ gravados, mantendo
    # apenas o cabeça (menor 'ordem') por (campanha, família, parte). Idempotente.
    try:
        cur.execute("""
            DELETE ci FROM campanha_itens ci
            JOIN campanha_itens keep
              ON keep.campanha_id = ci.campanha_id
             AND keep.familia = ci.familia
             AND keep.parte = ci.parte
             AND keep.classificacao_mix = 1
             AND keep.ordem < ci.ordem
            WHERE ci.classificacao_mix = 1
              AND ci.familia IS NOT NULL AND TRIM(ci.familia) <> ''
        """)
        conn.commit()
    except Exception:
        pass

    # Backfill de datas: campanhas antigas (e as criadas antes desta correção)
    # ficaram com data_inicio/data_fim vazios. Sem data_fim, a "virada de mês"
    # arquivava pela data de CRIAÇÃO — arquivando campanhas ainda VIGENTES.
    # Preenche as datas a partir do texto do período. Idempotente (só onde vazio).
    try:
        cur.execute("""
            SELECT id, periodo FROM campanhas
            WHERE (data_fim IS NULL OR data_fim = '')
              AND periodo IS NOT NULL AND periodo <> ''
        """)
        _pendentes = cur.fetchall()
        for _cid, _per in _pendentes:
            _di, _df = parse_periodo_datas(_per)
            if _di and _df:
                cur.execute(
                    "UPDATE campanhas SET data_inicio=%s, data_fim=%s WHERE id=%s",
                    (_di.isoformat(), _df.isoformat(), _cid),
                )
        conn.commit()
    except Exception as e:
        print(f"Aviso no backfill de datas das campanhas: {e}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_autorizacao (
            id VARCHAR(64) PRIMARY KEY,
            campanha_id VARCHAR(64) NOT NULL,
            tipo VARCHAR(20) NOT NULL,
            mercadologico VARCHAR(160) NOT NULL,
            parte VARCHAR(20) NOT NULL,
            comprador VARCHAR(64) NOT NULL,
            quantidade INT NOT NULL DEFAULT 3,
            status VARCHAR(20) NOT NULL DEFAULT 'pendente',
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_ped_camp (campanha_id, status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS notificacoes (
            id VARCHAR(64) PRIMARY KEY,
            destinatario VARCHAR(64) NOT NULL,
            remetente VARCHAR(64) DEFAULT '',
            campanha_id VARCHAR(64) DEFAULT '',
            item_id VARCHAR(64) DEFAULT '',
            item_desc VARCHAR(255) DEFAULT '',
            campo VARCHAR(40) DEFAULT '',
            valor_antes TEXT,
            valor_depois TEXT,
            tipo VARCHAR(20) NOT NULL DEFAULT 'edicao',
            mensagem TEXT NOT NULL,
            lida TINYINT(1) NOT NULL DEFAULT 0,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_dest (destinatario, lida, criado_em)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """)

    conn.commit()
    _seed(conn, cur)
    _ensure_gestor(conn, cur)
    executar_virada_de_mes(conn, cur)

    cur.close()
    conn.close()
    print("Banco MySQL 'mix_ofertas' inicializado com sucesso!\n")


def _ensure_gestor(conn, cur):
    """
    Define o gestor comercial (allan) uma única vez: promove allan de 'comprador' a 'gestor'
    apenas enquanto NÃO existir nenhum gestor no sistema. Depois disso, o ADM controla o papel
    de qualquer pessoa pela aba Equipe (não sobrescreve escolhas do ADM).
    O 'gestor' revisa preço e parte (interno/divulgação) de todos os itens, sem ser ADM.
    """
    try:
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE role='gestor'")
        if cur.fetchone()[0] == 0:
            cur.execute("UPDATE usuarios SET role='gestor', cargo='Gestor Comercial (Bebidas / Açougue)' WHERE LOWER(usuario)='allan' AND role='comprador'")
            conn.commit()
            print("  Papel de gestor comercial atribuído ao allan.")
    except Exception as e:
        print(f"  Aviso ao definir gestor: {e}")


def _seed(conn, cur):
    """
    Semente inicial: só insere dados se as tabelas estiverem 100% vazias.
    Isso respeita rigorosamente qualquer alteração ou deleção manual feita no MySQL.
    """
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] == 0:
        import bcrypt
        pwd = bcrypt.hashpw("123456".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        users = [
            ("usr_1", "vitor", "Vitor", pwd, "Administrador", "adm"),
            ("usr_2", "allan", "Allan", pwd, "Gestor Comercial (Bebidas / Açougue)", "gestor"),
            ("usr_3", "edna", "Edna", pwd, "Compradora (Mercearia Doce / Cereais / Higiene)", "comprador"),
            ("usr_4", "mario", "Mario", pwd, "Comprador (Mercearia Salgada / Limpeza / Bazar)", "comprador"),
            ("usr_5", "jhonne", "Jhonne", pwd, "Comprador (Frios / Peixaria)", "comprador"),
            ("usr_6", "ana", "Ana", pwd, "Compradora (Hortifruti / Padaria)", "comprador"),
        ]
        cur.executemany("INSERT INTO usuarios (id, usuario, nome, senha, cargo, role, ativo) VALUES (%s, %s, %s, %s, %s, %s, 1)", users)
        conn.commit()
        print("  Usuários padrão inseridos.")

    cur.execute("SELECT COUNT(*) FROM parametros")
    if cur.fetchone()[0] == 0:
        params_encarte = [
            ("ENCARTE", "BEBIDAS", "allan", 11, 0, 1),
            ("ENCARTE", "FRIOS | PEIXARIA", "jhonne", 11, 0, 2),
            ("ENCARTE", "MERC DOCE", "edna", 32, 0, 3),
            ("ENCARTE", "HIG E PERFUMARIA", "edna", 9, 0, 4),
            ("ENCARTE", "MERC SALGADA", "mario", 8, 0, 5),
            ("ENCARTE", "LIMPEZA", "mario", 7, 0, 6),
            ("ENCARTE", "BAZAR", "edna", 6, 0, 7),
            ("ENCARTE", "PET", "mario", 3, 0, 8),
            ("ENCARTE", "CEREAIS", "edna", 3, 0, 9),
            ("ENCARTE", "SAÚDE & ESTETICA", "mario", 7, 0, 10),
            ("ENCARTE", "HORTI | PADARIA", "ana", 2, 0, 11),
        ]
        cur.executemany("INSERT INTO parametros (tipo, mercadologico, comprador, meta_divulgacao, meta_interna, ordem) VALUES (%s, %s, %s, %s, %s, %s)", params_encarte)
        cur.execute("INSERT INTO parametros_pool (tipo, pool_interna, extra_pool, capa_max, app_max) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE pool_interna=VALUES(pool_interna)", ("ENCARTE", 50, 0, 16, 5))

        params_fds = [
            ("FDS_SAZONAL", "BEBIDAS", "allan", 8, 0, 1),
            ("FDS_SAZONAL", "FRIOS | PEIXARIA", "jhonne", 6, 0, 2),
            ("FDS_SAZONAL", "MERC DOCE", "edna", 12, 0, 3),
            ("FDS_SAZONAL", "HIG E PERFUMARIA", "edna", 6, 0, 4),
            ("FDS_SAZONAL", "MERC SALGADA", "mario", 6, 0, 5),
            ("FDS_SAZONAL", "LIMPEZA", "mario", 4, 0, 6),
            ("FDS_SAZONAL", "BAZAR", "edna", 2, 0, 7),
            ("FDS_SAZONAL", "PET", "mario", 2, 0, 8),
            ("FDS_SAZONAL", "CEREAIS", "edna", 2, 0, 9),
            ("FDS_SAZONAL", "SAÚDE & ESTETICA", "mario", 2, 0, 10),
            ("FDS_SAZONAL", "HORTI | PADARIA", "ana", 2, 0, 11),
        ]
        cur.executemany("INSERT INTO parametros (tipo, mercadologico, comprador, meta_divulgacao, meta_interna, ordem) VALUES (%s, %s, %s, %s, %s, %s)", params_fds)
        cur.execute("INSERT INTO parametros_pool (tipo, pool_interna, extra_pool, capa_max, app_max) VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE pool_interna=VALUES(pool_interna)", ("FDS_SAZONAL", 30, 0, 10, 4))

        conn.commit()
        print("  Parâmetros e metas padrão inseridos.")


def executar_virada_de_mes(conn=None, cur=None):
    """Mantém o status das campanhas em sincronia com a VIGÊNCIA do período.

    Uma oferta fica "No ar" enquanto está vigente e só é arquivada quando o
    período termina — ou seja, a partir do DIA SEGUINTE à data final
    (`data_fim < hoje`). Campanhas ainda vigentes (ou futuras) que, por algum
    motivo, ficaram arquivadas são reativadas. Campanhas sem `data_fim` (período
    não reconhecido) não são tocadas, para nunca arquivar algo por engano.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        cur = conn.cursor()
        should_close = True
    try:
        # Arquiva só o que JÁ venceu (hoje já passou da data final).
        cur.execute("""
            UPDATE campanhas SET status='arquivada', atualizado_em=CURRENT_TIMESTAMP
            WHERE status='ativa'
              AND data_fim IS NOT NULL AND data_fim <> ''
              AND STR_TO_DATE(data_fim, '%Y-%m-%d') < CURDATE()
        """)
        # Reativa o que ainda está vigente (ou é futuro) mas tinha sido arquivado.
        cur.execute("""
            UPDATE campanhas SET status='ativa', atualizado_em=CURRENT_TIMESTAMP
            WHERE status='arquivada'
              AND data_fim IS NOT NULL AND data_fim <> ''
              AND STR_TO_DATE(data_fim, '%Y-%m-%d') >= CURDATE()
        """)
        conn.commit()
    except Exception as e:
        print(f"Aviso na virada de mês: {e}")
    finally:
        if should_close:
            cur.close()
            conn.close()


def get_user_role(usuario: str) -> str:
    if not usuario:
        return "comprador"
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT role FROM usuarios WHERE LOWER(usuario)=LOWER(%s) AND ativo=1", (usuario.strip(),))
        row = cur.fetchone()
        return row["role"] if row else "comprador"
    finally:
        cur.close()
        conn.close()


# ─── Notificações ao comprador (avisos de edição feita pelo gestor/ADM) ────────
CAMPO_LABELS = {
    "codigo": "Código",
    "descricao": "Descrição",
    "custo": "Custo",
    "preco_oferta": "Preço de oferta",
    "preco_app": "Preço de app",
    "observacao": "Observação",
    "destaque": "Destaque",
    "classificacao_mix": "Tipo mix",
    "sellout": "Sellout",
    "mercadologico": "Mercadológico",
    "parte": "Parte",
}


def label_campo(campo: str) -> str:
    return CAMPO_LABELS.get(campo, campo or "")


def get_user_nome(usuario: str) -> str:
    """Nome amigável do usuário pelo login (fallback = o próprio login)."""
    if not usuario:
        return usuario
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT nome FROM usuarios WHERE LOWER(usuario)=LOWER(%s)", (usuario.strip(),))
        row = cur.fetchone()
        return (row or {}).get("nome") or usuario
    except Exception:
        return usuario
    finally:
        cur.close()
        conn.close()


def registrar_notificacao(cur, destinatario, remetente, campanha_id, item_id,
                          item_desc, campo, valor_antes, valor_depois, tipo, mensagem):
    """Insere uma notificação usando um cursor JÁ ABERTO (o commit é do chamador)."""
    import time as _t
    import uuid as _u
    destinatario = (destinatario or "").strip()
    if not destinatario:
        return None
    nid = f"ntf_{int(_t.time()*1000)}_{_u.uuid4().hex[:8]}"
    cur.execute(
        """
        INSERT INTO notificacoes
            (id, destinatario, remetente, campanha_id, item_id, item_desc, campo,
             valor_antes, valor_depois, tipo, mensagem, lida)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
        """,
        (
            nid, destinatario, (remetente or ""), (campanha_id or ""), (item_id or ""),
            (item_desc or "")[:255], (campo or ""),
            None if valor_antes is None else str(valor_antes),
            None if valor_depois is None else str(valor_depois),
            (tipo or "edicao"), mensagem,
        ),
    )
    return nid


def mercadologicos_do_comprador(tipo_campanha: str, usuario: str) -> List[str]:
    tp = tipo_param(tipo_campanha)
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT mercadologico, MIN(ordem) AS min_ord
            FROM parametros
            WHERE tipo=%s AND LOWER(TRIM(comprador))=LOWER(TRIM(%s))
            GROUP BY mercadologico
            ORDER BY min_ord
        """, (tp, (usuario or "").strip()))
        rows = cur.fetchall()
        res = [r["mercadologico"].strip() for r in rows if r.get("mercadologico")]
        if not res:
            # Fallback para ENCARTE se não tiver parâmetros cadastrados para o tipo (ex.: ALERTA)
            cur.execute("""
                SELECT mercadologico, MIN(ordem) AS min_ord
                FROM parametros
                WHERE tipo='ENCARTE' AND LOWER(TRIM(comprador))=LOWER(TRIM(%s))
                GROUP BY mercadologico
                ORDER BY min_ord
            """, ((usuario or "").strip(),))
            res = [r["mercadologico"].strip() for r in cur.fetchall() if r.get("mercadologico")]
        if not res:
            # Fallback geral para qualquer tipo onde o comprador esteja cadastrado
            cur.execute("""
                SELECT mercadologico, MIN(ordem) AS min_ord
                FROM parametros
                WHERE LOWER(TRIM(comprador))=LOWER(TRIM(%s))
                GROUP BY mercadologico
                ORDER BY min_ord
            """, ((usuario or "").strip(),))
            res = [r["mercadologico"].strip() for r in cur.fetchall() if r.get("mercadologico")]
        return res
    finally:
        cur.close()
        conn.close()


def cotas_da_campanha(campanha: Dict[str, Any]) -> Dict[str, Any]:
    tp = tipo_param(campanha.get("tipo", ""))
    camp_id = campanha.get("id")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM parametros WHERE tipo=%s ORDER BY ordem", (tp,))
        params = cur.fetchall()
        if not params:
            cur.execute("SELECT * FROM parametros WHERE tipo='ENCARTE' ORDER BY ordem")
            params = cur.fetchall()

        cur.execute("SELECT * FROM parametros_pool WHERE tipo=%s", (tp,))
        pool = cur.fetchone() or {"pool_interna": 50, "extra_pool": 0, "capa_max": 16, "app_max": 5}

        # Agrupa itens em família como 1 vaga de cota
        cur.execute("""
            SELECT mercadologico, parte,
                   COUNT(DISTINCT CASE WHEN classificacao_mix=1 AND familia IS NOT NULL AND TRIM(familia) != '' THEN familia ELSE id END) as n 
            FROM campanha_itens 
            WHERE campanha_id=%s AND tipo_linha='produto' 
            GROUP BY mercadologico, parte
        """, (camp_id,))
        usados = cur.fetchall()

        uso_div = {}
        uso_int = {}
        pool_usado = 0
        for u in usados:
            key = (u["mercadologico"] or "").upper().strip()
            if u["parte"] == "interno":
                uso_int[key] = u["n"]
                pool_usado += u["n"]
            else:
                uso_div[key] = u["n"]

        linhas = []
        for p in params:
            key = p["mercadologico"].upper().strip()
            linhas.append({
                "id": p["id"],
                "mercadologico": p["mercadologico"],
                "comprador": p["comprador"],
                "meta_divulgacao": p["meta_divulgacao"],
                "extra_div": p["extra_div"],
                "usado_divulgacao": uso_div.get(key, 0),
                "meta_interna": p["meta_interna"],
                "extra_int": p["extra_int"],
                "usado_interna": uso_int.get(key, 0),
            })

        cur.execute("""
            SELECT destaque, COUNT(*) as n 
            FROM campanha_itens 
            WHERE campanha_id=%s AND tipo_linha='produto' AND destaque IN ('Capa','App') 
            GROUP BY destaque
        """, (camp_id,))
        dcount = cur.fetchall()

        usado_capa = 0
        usado_app = 0
        for d in dcount:
            if d["destaque"] == "Capa":
                usado_capa = d["n"]
            elif d["destaque"] == "App":
                usado_app = d["n"]

        pool_data = {
            "pool_interna": pool.get("pool_interna", 50),
            "extra_pool": pool.get("extra_pool", 0),
            "usado": pool_usado,
        } if pool.get("pool_interna") is not None else None

        return {
            "tipo": tp,
            "linhas": linhas,
            "pool": pool_data,
            "destaque": {
                "capa_max": pool.get("capa_max", 16),
                "app_max": pool.get("app_max", 5),
                "usado_capa": usado_capa,
                "usado_app": usado_app,
            }
        }
    finally:
        cur.close()
        conn.close()


def _extra_camp(cur, camp_id, parte, merc=None):
    """Extra de cota concedido por autorização válido SÓ nesta campanha
    (pedidos aprovados com permanente=0). Os permanentes já entram no parâmetro global."""
    if merc is None:
        cur.execute("SELECT COALESCE(SUM(quantidade),0) s FROM pedidos_autorizacao "
                    "WHERE campanha_id=%s AND parte=%s AND status='aprovado' AND permanente=0", (camp_id, parte))
    else:
        cur.execute("SELECT COALESCE(SUM(quantidade),0) s FROM pedidos_autorizacao "
                    "WHERE campanha_id=%s AND parte=%s AND status='aprovado' AND permanente=0 "
                    "AND UPPER(mercadologico)=UPPER(%s)", (camp_id, parte, merc))
    try:
        return int(cur.fetchone()["s"] or 0)
    except Exception:
        return 0


def checar_cota(campanha: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    tp = tipo_param(campanha.get("tipo", ""))
    camp_id = campanha.get("id")
    merc = str(item.get("mercadologico") or "").strip()
    if not merc:
        return {"ok": False, "motivo": "Selecione o mercadológico antes de lançar."}

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM parametros WHERE tipo=%s AND UPPER(mercadologico)=UPPER(%s)", (tp, merc))
        param = cur.fetchone()
        if not param:
            # Fallback para ENCARTE se não tiver parâmetros para o tipo atual
            cur.execute("SELECT * FROM parametros WHERE tipo='ENCARTE' AND UPPER(mercadologico)=UPPER(%s)", (merc,))
            param = cur.fetchone()
        if not param:
            # Se não está nos parâmetros, permite com aviso caso não haja restrição estrita
            return {"ok": True, "parte": item.get("parte") or "divulgacao"}

        parte = "interno" if item.get("parte") == "interno" else "divulgacao"
        familia_item = str(item.get("familia") or "").strip()
        is_familia = int(item.get("classificacao_mix") or 2) == 1 and bool(familia_item)

        if parte == "divulgacao":
            # Se é um produto de família e a família já está presente, não consome cota extra
            if is_familia:
                cur.execute("""
                    SELECT COUNT(*) as n FROM campanha_itens
                    WHERE campanha_id=%s AND tipo_linha='produto' AND parte='divulgacao'
                      AND UPPER(mercadologico)=UPPER(%s) AND familia=%s
                """, (camp_id, merc, familia_item))
                if cur.fetchone()["n"] > 0:
                    return {"ok": True, "parte": "divulgacao"}

            cur.execute("""
                SELECT COUNT(DISTINCT CASE WHEN classificacao_mix=1 AND familia IS NOT NULL AND TRIM(familia) != '' THEN familia ELSE id END) as n 
                FROM campanha_itens 
                WHERE campanha_id=%s AND tipo_linha='produto' AND parte='divulgacao' AND UPPER(mercadologico)=UPPER(%s)
            """, (camp_id, merc))
            used = cur.fetchone()["n"]
            limite = param["meta_divulgacao"] + (param.get("extra_div") or 0) + _extra_camp(cur, camp_id, "divulgacao", merc)
            if used >= limite:
                return {
                    "ok": False,
                    "parte": "divulgacao",
                    "motivo": f"Divulgação de {merc} no limite ({used}/{limite}). Peça autorização ao ADM."
                }
            return {"ok": True, "parte": "divulgacao"}

        # parte == 'interno'
        cur.execute("SELECT * FROM parametros_pool WHERE tipo=%s", (tp,))
        pool = cur.fetchone()
        if not pool:
            cur.execute("SELECT * FROM parametros_pool WHERE tipo='ENCARTE'")
            pool = cur.fetchone()

        if pool and pool.get("pool_interna") is not None and pool["pool_interna"] > 0:
            if is_familia:
                cur.execute("""
                    SELECT COUNT(*) as n FROM campanha_itens
                    WHERE campanha_id=%s AND tipo_linha='produto' AND parte='interno' AND familia=%s
                """, (camp_id, familia_item))
                if cur.fetchone()["n"] > 0:
                    return {"ok": True, "parte": "interno"}

            cur.execute("""
                SELECT COUNT(DISTINCT CASE WHEN classificacao_mix=1 AND familia IS NOT NULL AND TRIM(familia) != '' THEN familia ELSE id END) as n 
                FROM campanha_itens 
                WHERE campanha_id=%s AND tipo_linha='produto' AND parte='interno'
            """, (camp_id,))
            used = cur.fetchone()["n"]
            limite = pool["pool_interna"] + (pool.get("extra_pool") or 0) + _extra_camp(cur, camp_id, "interno")
            if used >= limite:
                return {
                    "ok": False,
                    "parte": "interno",
                    "motivo": f"Parte interna (EXTRA) esgotada ({used}/{limite}). Peça autorização ao ADM."
                }
            return {"ok": True, "parte": "interno"}
        else:
            if is_familia:
                cur.execute("""
                    SELECT COUNT(*) as n FROM campanha_itens
                    WHERE campanha_id=%s AND tipo_linha='produto' AND parte='interno'
                      AND UPPER(mercadologico)=UPPER(%s) AND familia=%s
                """, (camp_id, merc, familia_item))
                if cur.fetchone()["n"] > 0:
                    return {"ok": True, "parte": "interno"}

            cur.execute("""
                SELECT COUNT(DISTINCT CASE WHEN classificacao_mix=1 AND familia IS NOT NULL AND TRIM(familia) != '' THEN familia ELSE id END) as n 
                FROM campanha_itens 
                WHERE campanha_id=%s AND tipo_linha='produto' AND parte='interno' AND UPPER(mercadologico)=UPPER(%s)
            """, (camp_id, merc))
            used = cur.fetchone()["n"]
            limite = param["meta_interna"] + (param.get("extra_int") or 0) + _extra_camp(cur, camp_id, "interno", merc)
            if used >= limite:
                return {
                    "ok": False,
                    "parte": "interno",
                    "motivo": f"Parte interna de {merc} no limite ({used}/{limite}). Peça autorização ao ADM."
                }
            return {"ok": True, "parte": "interno"}
    finally:
        cur.close()
        conn.close()


def checar_destaque(campanha: Dict[str, Any], destaque: Optional[str]) -> Dict[str, Any]:
    if not destaque or destaque not in ("Capa", "App"):
        return {"ok": True}

    tp = tipo_param(campanha.get("tipo", ""))
    camp_id = campanha.get("id")

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT capa_max, app_max FROM parametros_pool WHERE tipo=%s", (tp,))
        pool = cur.fetchone() or {}
        if destaque == "Capa":
            max_limit = pool.get("capa_max") or 16
        else:
            max_limit = pool.get("app_max") or 5

        cur.execute("""
            SELECT COUNT(*) as n FROM campanha_itens 
            WHERE campanha_id=%s AND tipo_linha='produto' AND destaque=%s
        """, (camp_id, destaque))
        used = cur.fetchone()["n"]

        if used >= max_limit:
            return {"ok": False, "motivo": f"Limite de {destaque} atingido ({used}/{max_limit})."}
        return {"ok": True}
    finally:
        cur.close()
        conn.close()


def ultima_oferta(codigo: str, exclude_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Última vez que este produto foi ofertado (em qualquer outra campanha),
    com o preço praticado — para o comprador se guiar ao precificar."""
    cod = str(codigo or "").strip()
    if not cod:
        return None
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT ci.preco_oferta, ci.preco_app, ci.custo, ci.criado_em AS item_em,
                   c.id AS campanha_id, c.nome AS campanha_nome, c.periodo, c.tipo,
                   c.criado_em AS camp_em
            FROM campanha_itens ci
            JOIN campanhas c ON c.id = ci.campanha_id
            WHERE ci.codigo=%s AND ci.tipo_linha='produto' AND ci.preco_oferta IS NOT NULL
              AND (%s IS NULL OR ci.campanha_id <> %s)
            ORDER BY c.criado_em DESC, ci.criado_em DESC
            LIMIT 1
        """, (cod, exclude_id, exclude_id))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def margens_por_comprador(campanha_id: str) -> Dict[str, Any]:
    """Margem média por comprador (e geral) de uma campanha."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT criado_por, preco_oferta, custo
            FROM campanha_itens
            WHERE campanha_id=%s AND tipo_linha='produto'
        """, (campanha_id,))
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    por = {}
    todos = []
    for r in rows:
        try:
            o = float(r["preco_oferta"]) if r["preco_oferta"] is not None else 0
            c = float(r["custo"]) if r["custo"] is not None else 0
        except (TypeError, ValueError):
            continue
        if o > 0 and c > 0:
            m = (o - c) / o * 100.0
            dono = (r["criado_por"] or "").strip().lower()
            por.setdefault(dono, []).append(m)
            todos.append(m)

    def avg(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    return {
        "geral": avg(todos),
        "por": {k: {"margem": avg(v), "qtd": len(v)} for k, v in por.items()},
    }


def campanha_anterior(campanha: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Campanha equivalente do período ANTERIOR (mesmo tipo resolvido, outra campanha).
    Prefere a mais recente que seja MAIS ANTIGA que a atual; senão a outra mais recente."""
    tp = tipo_param(campanha.get("tipo", ""))
    atual_id = campanha.get("id")
    atual_em = campanha.get("criado_em")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id<>%s ORDER BY criado_em DESC", (atual_id,))
        mesmas = [c for c in cur.fetchall() if tipo_param(c.get("tipo", "")) == tp]
        if not mesmas:
            return None
        if atual_em is not None:
            anteriores = [c for c in mesmas if c.get("criado_em") is not None and c["criado_em"] < atual_em]
            if anteriores:
                return anteriores[0]
        return mesmas[0]
    finally:
        cur.close()
        conn.close()


def expandir_familias(itens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Para a aba 'Relação Completa': cada item Mix=1 com família vira VÁRIAS linhas —
    todos os irmãos do catálogo (incluindo o próprio), herdando os valores da oferta
    lançada (preço, parte, destaque, comprador...), trocando só código e descrição.
    Itens sem família (ou Mix=2) passam direto."""
    if not itens:
        return itens or []
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        out = []
        cache = {}
        for it in itens:
            fam = str(it.get("familia") or "").strip()
            is_fam = int(it.get("classificacao_mix") or 2) == 1 and bool(fam)
            if not is_fam:
                out.append(it)
                continue
            if fam not in cache:
                cur.execute(
                    "SELECT codigo, descricao FROM produtos WHERE familia=%s ORDER BY (codigo=%s) DESC, codigo ASC",
                    (fam, str(it.get("codigo") or "")),
                )
                cache[fam] = cur.fetchall()
            irmaos = cache[fam]
            if not irmaos:
                out.append(it)
                continue
            for irmao in irmaos:
                novo = dict(it)
                novo["codigo"] = irmao["codigo"]
                novo["descricao"] = irmao.get("descricao") or it.get("descricao")
                out.append(novo)
        return out
    finally:
        cur.close()
        conn.close()


MESES_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def parse_periodo_datas(texto: str, ref_year: Optional[int] = None) -> Tuple[Optional[date], Optional[date]]:
    """Extrai data_inicio e data_fim a partir de textos como '05 a 09 de setembro de 2026'."""
    if not texto:
        return None, None
    t = texto.lower().strip()
    year = ref_year or datetime.datetime.now().year

    m_ano = re.search(r"\b(202\d)\b", t)
    if m_ano:
        year = int(m_ano.group(1))

    # Formatos dd/mm a dd/mm ou dd/mm/yyyy
    m_barras = re.findall(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", t)
    if len(m_barras) >= 2:
        try:
            d1, m1, y1 = int(m_barras[0][0]), int(m_barras[0][1]), int(m_barras[0][2]) if m_barras[0][2] else year
            d2, m2, y2 = int(m_barras[1][0]), int(m_barras[1][1]), int(m_barras[1][2]) if m_barras[1][2] else year
            if y1 < 100: y1 += 2000
            if y2 < 100: y2 += 2000
            return date(y1, m1, d1), date(y2, m2, d2)
        except Exception:
            pass

    # Nome do mês
    mes_num = None
    for nome_mes, num in MESES_PT.items():
        if nome_mes in t:
            mes_num = num
            break

    if mes_num:
        m_dias = [int(d) for d in re.findall(r"\b(\d{1,2})\b", t) if 1 <= int(d) <= 31 and int(d) != year]
        if len(m_dias) >= 2:
            dias = sorted(m_dias[:2])
            try:
                return date(year, mes_num, dias[0]), date(year, mes_num, dias[1])
            except Exception:
                pass
        elif len(m_dias) == 1:
            try:
                d_inicio = date(year, mes_num, m_dias[0])
                d_fim = date(year, mes_num, 30 if mes_num in (4, 6, 9, 11) else (28 if mes_num == 2 else 31))
                return d_inicio, d_fim
            except Exception:
                pass

    return None, None


def periodos_conflitam(periodo_a: str, periodo_b: str) -> bool:
    """Retorna True se dois períodos têm sobreposição de datas."""
    if not periodo_a or not periodo_b:
        return True
    s1, e1 = parse_periodo_datas(periodo_a)
    s2, e2 = parse_periodo_datas(periodo_b)
    if not s1 or not e1 or not s2 or not e2:
        return periodo_a.strip().lower() == periodo_b.strip().lower()
    return max(s1, s2) <= min(e1, e2)


def checar_conflito_produto(campanha_id: Optional[str], codigo: str) -> Dict[str, Any]:
    """
    Verifica se o produto — OU QUALQUER PRODUTO DA MESMA FAMÍLIA — já foi lançado
    em outra campanha ativa cujo período se sobreponha ao da campanha atual.
    Vale mesmo quando numa campanha o item está como unidade e na outra como
    família: a família não pode se repetir em datas que conflitam.
    Se as ofertas estiverem em gaps/datas diferentes, NÃO há conflito.
    """
    cod = str(codigo or "").strip()
    if not cod:
        return {"conflito": False}

    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        periodo_atual = ""
        if campanha_id:
            cur.execute("SELECT periodo, data_inicio, data_fim FROM campanhas WHERE id=%s", (campanha_id,))
            camp_atual = cur.fetchone()
            if camp_atual:
                periodo_atual = camp_atual.get("periodo") or ""

        # Família do produto que está sendo lançado (vem do catálogo).
        cur.execute("SELECT familia FROM produtos WHERE codigo=%s", (cod,))
        _pr = cur.fetchone()
        familia_alvo = str((_pr or {}).get("familia") or "").strip() or None

        # Candidatos em OUTRAS campanhas ativas: mesmo código OU mesma família
        # (resolvendo a família tanto pelo que está gravado quanto pelo catálogo).
        query = """
            SELECT c.id as campanha_id, c.nome as campanha_nome, c.tipo, c.periodo,
                   i.preco_oferta, i.descricao, i.codigo, i.familia as item_familia,
                   p.familia as cat_familia, i.criado_em as item_criado_em
            FROM campanha_itens i
            JOIN campanhas c ON i.campanha_id = c.id
            LEFT JOIN produtos p ON TRIM(p.codigo) = TRIM(i.codigo)
            WHERE c.status = 'ativa'
              AND i.tipo_linha = 'produto'
        """
        cond = ["TRIM(i.codigo) = %s"]
        params = [cod]
        if familia_alvo:
            cond.append("TRIM(COALESCE(i.familia,'')) = %s")
            params.append(familia_alvo)
            cond.append("TRIM(COALESCE(p.familia,'')) = %s")
            params.append(familia_alvo)
        query += " AND (" + " OR ".join(cond) + ")"
        if campanha_id:
            query += " AND c.id != %s"
            params.append(campanha_id)
        query += " ORDER BY i.criado_em ASC"

        cur.execute(query, tuple(params))
        candidatos = cur.fetchall()

        for conflito in candidatos:
            periodo_outro = conflito.get("periodo") or ""
            if periodos_conflitam(periodo_atual, periodo_outro):
                outro_cod = str(conflito.get("codigo") or "").strip()
                por_familia = outro_cod != cod  # bateu pela família, não pelo próprio código
                p_oferta = conflito.get("preco_oferta")
                p_oferta_txt = f" por R$ {float(p_oferta):.2f}" if p_oferta is not None else ""
                periodo_txt = f" ({periodo_outro})" if periodo_outro else ""
                fam_txt = (familia_alvo or str(conflito.get("item_familia") or conflito.get("cat_familia") or "").strip() or "") if por_familia else None
                if por_familia:
                    desc_outro = conflito.get("descricao") or outro_cod
                    fam_info = f" {fam_txt}" if fam_txt else ""
                    msg = (f"Conflito de família{fam_info}: o produto {outro_cod} - {desc_outro} "
                           f"(mesma família) já está na campanha '{conflito.get('campanha_nome')}'"
                           f"{periodo_txt}{p_oferta_txt}. A mesma família não pode se repetir em "
                           f"campanhas com datas sobrepostas.")
                else:
                    msg = (f"Conflito de período: o produto {cod} já está lançado na campanha "
                           f"'{conflito.get('campanha_nome')}'{periodo_txt}{p_oferta_txt}.")
                return {
                    "conflito": True,
                    "campanha_id": conflito.get("campanha_id"),
                    "campanha_nome": conflito.get("campanha_nome"),
                    "periodo": periodo_outro,
                    "preco_oferta": p_oferta,
                    "codigo_conflitante": outro_cod,
                    "descricao_conflitante": conflito.get("descricao"),
                    "familia": fam_txt,
                    "por_familia": por_familia,
                    "motivo": msg,
                }

        return {"conflito": False}
    finally:
        cur.close()
        conn.close()
