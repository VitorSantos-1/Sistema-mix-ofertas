"""
main.py — Mix de Ofertas & Encartes (FastAPI + Socket.IO + MySQL Standalone)
Supermercados Opção
"""

import os
import sys
import time
import uuid
import socket
import datetime
from typing import Optional, List, Dict, Any

# Correção crítica para saídas nulas quando empacotado com PyInstaller
class DummyStream:
    def write(self, *a, **k): return 0
    def writelines(self, *a, **k): pass
    def flush(self, *a, **k): pass
    def isatty(self): return False

if sys.stdout is None: sys.stdout = DummyStream()
if sys.stderr is None: sys.stderr = DummyStream()

import bcrypt
import socketio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import ofertas_mysql as om
import excel_export


def parse_num(v) -> Optional[float]:
    """Converte números brasileiros ou americanos para float com 2 casas decimais sem erro."""
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (int, float)):
            return round(float(v), 2)
        s = str(v).strip().replace("R$", "").replace(" ", "")
        if "," in s and "." in s:
            if s.index(".") < s.index(","):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        val = float(s)
        return round(val, 2)
    except Exception:
        return None


# ─── Inicialização da Aplicação FastAPI e Socket.IO ───────────────────────────
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI(title="Mix de Ofertas API", version="4.5.0")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


async def _broadcast_cotas():
    """Parâmetros/metas mudaram → avisa TODOS os editores abertos a recarregarem as
    cotas. O Editor escuta 'cotas-changed' e refaz o contexto com os valores novos,
    então campanhas já abertas ('No ar') se atualizam na hora, sem reabrir."""
    try:
        await sio.emit("cotas-changed", {})
    except Exception:
        pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Diretório de distribuição estática do React
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    DIST_DIR = os.path.join(sys._MEIPASS, "dist")
else:
    DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")

if os.path.exists(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")


# ─── Modelos Pydantic para Requisições ─────────────────────────────────────────
class LoginRequest(BaseModel):
    usuario: str
    senha: str

class UserCreateRequest(BaseModel):
    usuario: str
    nome: str
    senha: str
    cargo: str = "Comprador"
    role: str = "comprador"

class UserUpdateRequest(BaseModel):
    nome: Optional[str] = None
    cargo: Optional[str] = None
    role: Optional[str] = None
    ativo: Optional[int] = None

class PasswordChangeRequest(BaseModel):
    senha: str

class ProductSaveRequest(BaseModel):
    codigo: str
    descricao: str
    mercadologico: Optional[str] = "Geral"
    preco_custo: Optional[float] = None
    preco_venda: Optional[float] = None
    familia: Optional[str] = None

class ProductBatchImportRequest(BaseModel):
    produtos: List[Dict[str, Any]]

class CampaignCreateRequest(BaseModel):
    nome: str
    tipo: Optional[str] = "Encarte"
    status: Optional[str] = "ativa"
    periodo: Optional[str] = ""
    data_inicio: Optional[str] = ""
    data_fim: Optional[str] = ""
    observacoes: Optional[str] = ""

class CampaignUpdateRequest(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    status: Optional[str] = None
    periodo: Optional[str] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    observacoes: Optional[str] = None

class ParametroCreateRequest(BaseModel):
    tipo: str
    mercadologico: str
    comprador: Optional[str] = None
    meta_divulgacao: Optional[int] = 0
    meta_interna: Optional[int] = 0

class ParametroUpdateRequest(BaseModel):
    mercadologico: Optional[str] = None
    comprador: Optional[str] = None
    meta_divulgacao: Optional[int] = None
    meta_interna: Optional[int] = None
    extra_div: Optional[int] = None
    extra_int: Optional[int] = None
    ordem: Optional[int] = None

class PoolUpdateRequest(BaseModel):
    pool_interna: Optional[int] = None
    extra_pool: Optional[int] = None
    capa_max: Optional[int] = None
    app_max: Optional[int] = None

class TipoCreateRequest(BaseModel):
    nome: str
    usa_pool: Optional[bool] = False
    pool_interna: Optional[int] = 50
    extra_pool: Optional[int] = 0
    capa_max: Optional[int] = 16
    app_max: Optional[int] = 5

class TipoRenameRequest(BaseModel):
    novo_nome: str


# ─── Dependências de Autenticação / Autorização ────────────────────────────────
def get_actor(request: Request) -> str:
    # Frontend envia x-usuario (nd() em Ce API client)
    user = request.headers.get("x-usuario") or request.headers.get("x-user") or ""
    return user.strip()

def require_adm(request: Request) -> str:
    user = get_actor(request)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não autenticado.")
    role = om.get_user_role(user)
    if role != "adm":
        raise HTTPException(status_code=403, detail="Acesso restrito ao administrador.")
    return user


# ─── Endpoints de Autenticação e Usuários ─────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "Mix de Ofertas & Encartes",
        "version": "4.5.0",
        "db": "MySQL (mix_ofertas)",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.post("/api/auth/login")
def login(req: LoginRequest):
    usuario = req.usuario.strip() if req.usuario else ""
    senha = req.senha if req.senha is not None else ""
    if not usuario or not senha:
        raise HTTPException(status_code=400, detail="Informe usuário e senha.")

    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT id, usuario, nome, cargo, role, senha 
            FROM usuarios 
            WHERE (LOWER(usuario)=LOWER(%s) OR LOWER(nome) LIKE LOWER(%s)) AND ativo=1
        """, (usuario, f"%{usuario}%"))
        cands = cur.fetchall()

        matched_user = None
        for c in cands:
            stored_hash = c["senha"].encode("utf-8") if isinstance(c["senha"], str) else c["senha"]
            try:
                if bcrypt.checkpw(senha.encode("utf-8"), stored_hash):
                    matched_user = c
                    break
            except Exception:
                continue

        if not matched_user:
            raise HTTPException(status_code=401, detail="Usuário ou senha incorretos.")

        token = f"tok_{matched_user['id']}_{int(time.time()*1000)}"
        user_data = {
            "id": matched_user["id"],
            "usuario": matched_user["usuario"],
            "nome": matched_user["nome"],
            "cargo": matched_user["cargo"],
            "role": matched_user["role"],
        }
        return {
            "success": True,
            "token": token,
            "usuario": user_data
        }
    finally:
        cur.close()
        conn.close()

@app.get("/api/auth/usuarios")
def list_users():
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, usuario, nome, cargo, role, ativo FROM usuarios ORDER BY nome")
        rows = cur.fetchall()
        return {"usuarios": rows}
    finally:
        cur.close()
        conn.close()

@app.post("/api/auth/usuarios")
def create_user(item: UserCreateRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM usuarios WHERE LOWER(usuario)=LOWER(%s)", (item.usuario.strip(),))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Nome de usuário já existe.")

        uid = f"usr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        pwd_hash = bcrypt.hashpw(item.senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cur.execute("""
            INSERT INTO usuarios (id, usuario, nome, senha, cargo, role, ativo)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
        """, (uid, item.usuario.strip(), item.nome.strip(), pwd_hash, item.cargo.strip(), item.role.strip()))
        conn.commit()
        return {"success": True, "id": uid, "usuario": item.usuario, "nome": item.nome, "cargo": item.cargo, "role": item.role, "ativo": 1}
    finally:
        cur.close()
        conn.close()

@app.put("/api/auth/usuarios/{usuario}")
def update_user(usuario: str, item: UserUpdateRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        fields = []
        params = []
        if item.nome is not None:
            fields.append("nome=%s")
            params.append(item.nome.strip())
        if item.cargo is not None:
            fields.append("cargo=%s")
            params.append(item.cargo.strip())
        if item.role is not None:
            fields.append("role=%s")
            params.append(item.role.strip())
        if item.ativo is not None:
            fields.append("ativo=%s")
            params.append(item.ativo)

        if not fields:
            return {"success": True}

        params.append(usuario.strip())
        sql = f"UPDATE usuarios SET {', '.join(fields)} WHERE LOWER(usuario)=LOWER(%s)"
        cur.execute(sql, tuple(params))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        return {"success": True}
    finally:
        cur.close()
        conn.close()

@app.put("/api/auth/usuarios/{usuario}/senha")
def set_user_password(usuario: str, item: PasswordChangeRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        pwd_hash = bcrypt.hashpw(item.senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cur.execute("UPDATE usuarios SET senha=%s WHERE LOWER(usuario)=LOWER(%s)", (pwd_hash, usuario.strip()))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        return {"success": True}
    finally:
        cur.close()
        conn.close()


# ─── Endpoints de Produtos (Catálogo) ─────────────────────────────────────────
@app.get("/api/produtos")
def search_products(search: str = "", limit: int = 50):
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        lim = min(max(1, limit), 200)
        t = search.strip()
        if not t:
            cur.execute("SELECT * FROM produtos ORDER BY descricao LIMIT %s", (lim,))
            rows = cur.fetchall()
            return {"produtos": rows, "total": len(rows)}

        if t.isdigit() and len(t) <= 14:
            cur.execute("SELECT * FROM produtos WHERE codigo LIKE %s ORDER BY codigo LIMIT %s", (f"{t}%", lim))
            rows = cur.fetchall()
            if rows:
                return {"produtos": rows, "total": len(rows)}

        terms = [x for x in t.split() if x]
        where_clauses = []
        params = []
        for term in terms:
            where_clauses.append("(codigo LIKE %s OR descricao LIKE %s OR mercadologico LIKE %s)")
            p = f"%{term}%"
            params.extend([p, p, p])

        where_sql = " AND ".join(where_clauses)
        params.append(lim)
        cur.execute(f"SELECT * FROM produtos WHERE {where_sql} ORDER BY descricao LIMIT %s", tuple(params))
        rows = cur.fetchall()
        return {"produtos": rows, "total": len(rows)}
    finally:
        cur.close()
        conn.close()

@app.get("/api/produtos/{codigo}/ultima-oferta")
def ultima_oferta_produto(codigo: str, exclude: Optional[str] = None):
    """Preço da última oferta deste produto em outra campanha (para precificação)."""
    row = om.ultima_oferta(codigo, exclude)
    return row or {}


@app.get("/api/produtos/{codigo}")
def get_product(codigo: str):
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM produtos WHERE codigo=%s", (codigo.strip(),))
        prod = cur.fetchone()
        if not prod:
            raise HTTPException(status_code=404, detail="Produto não encontrado no catálogo.")
        return prod
    finally:
        cur.close()
        conn.close()

@app.post("/api/produtos")
def save_product(item: ProductSaveRequest):
    if not item.codigo or not item.descricao:
        raise HTTPException(status_code=400, detail="Código e descrição são obrigatórios.")
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        fam = (item.familia or "").strip() or None
        custo = parse_num(item.preco_custo)
        venda = parse_num(item.preco_venda)
        cur.execute("""
            INSERT INTO produtos (codigo, descricao, mercadologico, preco_custo, preco_venda, familia)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                descricao=VALUES(descricao),
                mercadologico=VALUES(mercadologico),
                preco_custo=VALUES(preco_custo),
                preco_venda=VALUES(preco_venda),
                familia=VALUES(familia)
        """, (
            item.codigo.strip(),
            item.descricao.strip(),
            (item.mercadologico or "Geral").strip(),
            custo,
            venda,
            fam
        ))
        conn.commit()
        return {"success": True, "codigo": item.codigo, "message": "Produto salvo com sucesso."}
    finally:
        cur.close()
        conn.close()

@app.post("/api/produtos/importar-lote")
def import_products_batch(item: ProductBatchImportRequest):
    if not item.produtos:
        raise HTTPException(status_code=400, detail="Nenhum produto fornecido.")
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        inseridos = 0
        chunk_size = 500
        for i in range(0, len(item.produtos), chunk_size):
            chunk = item.produtos[i:i+chunk_size]
            dados = []
            for p in chunk:
                cod = str(p.get("codigo") or "").strip()
                desc = str(p.get("descricao") or "").strip()
                if not cod or not desc:
                    continue
                merc = str(p.get("mercadologico") or "Geral").strip()
                custo = parse_num(p.get("preco_custo"))
                venda = parse_num(p.get("preco_venda"))
                fam = str(p.get("familia") or p.get("cod_familia") or p.get("codfamilia") or "").strip() or None
                dados.append((cod, desc, merc, custo, venda, fam))

            if dados:
                cur.executemany("""
                    INSERT INTO produtos (codigo, descricao, mercadologico, preco_custo, preco_venda, familia)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        descricao=VALUES(descricao),
                        mercadologico=VALUES(mercadologico),
                        preco_custo=VALUES(preco_custo),
                        preco_venda=VALUES(preco_venda),
                        familia=COALESCE(VALUES(familia), familia)
                """, dados)
                inseridos += len(dados)
        conn.commit()
        return {"success": True, "inseridos": inseridos, "total": inseridos, "message": f"{inseridos} produtos importados."}
    finally:
        cur.close()
        conn.close()


# ─── Endpoints de Campanhas ───────────────────────────────────────────────────
@app.get("/api/campanhas")
def list_campaigns(status: Optional[str] = None, tipo: Optional[str] = None):
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Mantém o status em dia com a vigência SEM depender de reiniciar o app:
        # arquiva o que já venceu (dia seguinte ao fim) e reativa o que voltou a
        # estar vigente. Barato (UPDATE por índice de status) e sempre atual.
        om.executar_virada_de_mes(conn, cur)
        sql = "SELECT * FROM campanhas"
        where = []
        params = []
        if status:
            where.append("status=%s")
            params.append(status)
        if tipo:
            where.append("tipo=%s")
            params.append(tipo)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY criado_em DESC"
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        if rows:
            # Calcular total_itens e margem_media para o dashboard do frontend
            ids = tuple(r["id"] for r in rows)
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"""
                SELECT campanha_id,
                       COUNT(*) as total_itens,
                       AVG(CASE WHEN custo > 0 AND preco_oferta > 0
                           THEN (preco_oferta - custo) / preco_oferta * 100.0
                           ELSE NULL END) as margem_media,
                       SUM(destaque='Capa') as total_capa,
                       SUM(destaque='App') as total_app,
                       SUM(destaque='Dezão') as total_dezao
                FROM campanha_itens WHERE campanha_id IN ({placeholders})
                AND tipo_linha='produto'
                GROUP BY campanha_id
            """, ids)
            stats = {r["campanha_id"]: r for r in cur.fetchall()}

            # Limites de destaque (Capa/App) resolvidos pelo TIPO atual de cada
            # campanha — assim o card do painel segue o MÁX. CAPA / MÁX. APP vigente
            # nos Parâmetros (não um número fixo). Resolve só por tipo distinto.
            cur.execute("SELECT tipo, capa_max, app_max FROM parametros_pool")
            pools = {r["tipo"]: r for r in cur.fetchall()}
            limites_por_tipo = {}
            for t in {row.get("tipo") for row in rows}:
                pl = pools.get(om.tipo_param(t or "")) or pools.get("ENCARTE") or {}
                cmax = pl.get("capa_max"); amax = pl.get("app_max")
                limites_por_tipo[t] = (cmax if cmax is not None else 16,
                                       amax if amax is not None else 5)

            for row in rows:
                st = stats.get(row["id"], {})
                row["total_itens"] = st.get("total_itens") or 0
                row["margem_media"] = float(st.get("margem_media") or 0)
                row["total_capa"] = st.get("total_capa") or 0
                row["total_app"] = st.get("total_app") or 0
                row["total_dezao"] = st.get("total_dezao") or 0
                cmax, amax = limites_por_tipo.get(row.get("tipo"), (16, 5))
                row["capa_max"] = cmax
                row["app_max"] = amax
        # Frontend espera {campanhas: [...]}
        return {"campanhas": rows}
    finally:
        cur.close()
        conn.close()

class ArchiveRequest(BaseModel):
    dias: Optional[int] = 30

@app.post("/api/campanhas/manutencao/arquivar-antigas")
async def archive_old_campaigns(request: Request):
    require_adm(request)
    # "Virada de mês": arquiva apenas campanhas cujo período JÁ terminou
    # (a partir do dia seguinte à data final). Campanhas vigentes continuam no ar.
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE campanhas SET status='arquivada', atualizado_em=CURRENT_TIMESTAMP
            WHERE status='ativa'
              AND data_fim IS NOT NULL AND data_fim <> ''
              AND STR_TO_DATE(data_fim, '%Y-%m-%d') < CURDATE()
        """)
        conn.commit()
        n = cur.rowcount
        return {"success": True, "arquivadas": n, "message": f"{n} campanha(s) encerrada(s) arquivada(s)."}
    finally:
        cur.close()
        conn.close()

@app.get("/api/campanhas/{id}")
def get_campaign_detail(id: str):
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")

        cur.execute("SELECT * FROM campanha_itens WHERE campanha_id=%s ORDER BY ordem ASC, criado_em ASC", (id,))
        itens = cur.fetchall()
        camp["itens"] = itens
        return {"campanha": camp, "itens": itens, **camp}
    finally:
        cur.close()
        conn.close()

@app.get("/api/campanhas/{id}/contexto")
def get_campaign_context(id: str, request: Request, usuario: Optional[str] = None):
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")

        # Frontend envia usuario na query string E no header x-usuario
        usuario = usuario or get_actor(request)
        role = om.get_user_role(usuario)
        cotas = om.cotas_da_campanha(camp)
        tp = om.tipo_param(camp.get("tipo", ""))

        if role == "adm":
            meus = [l["mercadologico"] for l in cotas["linhas"]]
        else:
            meus = om.mercadologicos_do_comprador(camp.get("tipo", ""), usuario)

        cur.execute("SELECT * FROM pedidos_autorizacao WHERE campanha_id=%s AND status='pendente' ORDER BY criado_em DESC", (id,))
        pedidos = cur.fetchall()

        return {
            "campanha": camp,
            "cotas": cotas,
            "meus_mercadologicos": meus,
            "pedidos": pedidos,
            "role": role,
            "usuario": usuario,
            "tipo_param": tp,
        }
    finally:
        cur.close()
        conn.close()

@app.get("/api/campanhas/conflitos/verificar")
def verificar_conflito_global(codigo: str, campanha_id: Optional[str] = None):
    return om.checar_conflito_produto(campanha_id, codigo)

@app.get("/api/campanhas/{id}/checar-conflito")
def checar_conflito_campanha(id: str, codigo: str):
    return om.checar_conflito_produto(id, codigo)

@app.get("/api/campanhas/{id}/comparativo")
def comparativo_campanha(id: str, compare: Optional[str] = None):
    """Margens por comprador da atual x uma campanha de comparação.
    `compare` escolhe explicitamente a campanha comparada; sem ele, usa a
    equivalente anterior (mesmo tipo). `opcoes` lista as campanhas que podem
    ser escolhidas (mesmo tipo primeiro), pra o usuário trocar a comparação."""
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")
        tp = om.tipo_param(camp.get("tipo", ""))

        # Opções de comparação: todas as outras campanhas, mesmo tipo primeiro, recentes antes.
        cur.execute("SELECT id, nome, periodo, tipo FROM campanhas WHERE id<>%s ORDER BY criado_em DESC", (id,))
        opcoes = [{
            "id": c["id"], "nome": c["nome"], "periodo": c.get("periodo"),
            "tipo": c.get("tipo"), "mesmo_tipo": om.tipo_param(c.get("tipo", "")) == tp,
        } for c in cur.fetchall()]
        opcoes.sort(key=lambda o: (not o["mesmo_tipo"],))  # mesmo tipo primeiro (sort estável)

        alvo = None
        if compare:
            cur.execute("SELECT * FROM campanhas WHERE id=%s", (compare,))
            alvo = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    if not alvo:
        alvo = om.campanha_anterior(camp)

    atual = om.margens_por_comprador(id)
    anterior = None
    if alvo and alvo.get("id") != id:
        anterior = {
            "id": alvo["id"],
            "nome": alvo.get("nome"),
            "periodo": alvo.get("periodo"),
            "margens": om.margens_por_comprador(alvo["id"]),
        }
    return {"atual": atual, "anterior": anterior, "opcoes": opcoes}

@app.post("/api/campanhas")
def create_campaign(item: CampaignCreateRequest, request: Request):
    require_adm(request)
    camp_id = f"camp_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    # Deriva as datas do texto do período quando o front não as envia. Sem elas
    # a campanha não teria vigência e a "virada de mês" não saberia quando encerrá-la.
    data_inicio = item.data_inicio or ""
    data_fim = item.data_fim or ""
    if (not data_inicio or not data_fim) and (item.periodo or ""):
        _di, _df = om.parse_periodo_datas(item.periodo)
        if _di and _df:
            data_inicio = data_inicio or _di.isoformat()
            data_fim = data_fim or _df.isoformat()
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO campanhas (id, nome, tipo, status, periodo, data_inicio, data_fim, observacoes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            camp_id,
            item.nome.strip(),
            item.tipo or "Encarte",
            item.status or "ativa",
            item.periodo or "",
            data_inicio,
            data_fim,
            item.observacoes or ""
        ))
        conn.commit()
        return {"success": True, "id": camp_id, "nome": item.nome, "tipo": item.tipo, "status": item.status}
    finally:
        cur.close()
        conn.close()

@app.put("/api/campanhas/{id}")
def update_campaign(id: str, item: CampaignUpdateRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        fields = []
        params = []
        if item.nome is not None:
            fields.append("nome=%s")
            params.append(item.nome.strip())
        if item.tipo is not None:
            fields.append("tipo=%s")
            params.append(item.tipo)
        if item.status is not None:
            fields.append("status=%s")
            params.append(item.status)
        if item.periodo is not None:
            fields.append("periodo=%s")
            params.append(item.periodo)
            # Período mudou e as datas não vieram explícitas → recalcula a vigência.
            if item.data_inicio is None and item.data_fim is None and item.periodo:
                _di, _df = om.parse_periodo_datas(item.periodo)
                if _di and _df:
                    fields.append("data_inicio=%s"); params.append(_di.isoformat())
                    fields.append("data_fim=%s"); params.append(_df.isoformat())
        if item.data_inicio is not None:
            fields.append("data_inicio=%s")
            params.append(item.data_inicio)
        if item.data_fim is not None:
            fields.append("data_fim=%s")
            params.append(item.data_fim)
        if item.observacoes is not None:
            fields.append("observacoes=%s")
            params.append(item.observacoes)

        if not fields:
            return {"success": True}

        params.append(id)
        cur.execute(f"UPDATE campanhas SET {', '.join(fields)} WHERE id=%s", tuple(params))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")
        return {"success": True}
    finally:
        cur.close()
        conn.close()

@app.delete("/api/campanhas/{id}")
def delete_campaign(id: str, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM campanha_itens WHERE campanha_id=%s", (id,))
        cur.execute("DELETE FROM pedidos_autorizacao WHERE campanha_id=%s", (id,))
        cur.execute("DELETE FROM campanhas WHERE id=%s", (id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")
        return {"success": True}
    finally:
        cur.close()
        conn.close()

@app.post("/api/campanhas/{id}/duplicar")
def duplicate_campaign(id: str, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (id,))
        orig = cur.fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="Campanha original não encontrada.")

        new_id = f"camp_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        new_nome = f"{orig['nome']} (Cópia)"

        dup_inicio = orig.get("data_inicio", "") or ""
        dup_fim = orig.get("data_fim", "") or ""
        if (not dup_inicio or not dup_fim) and orig.get("periodo"):
            _di, _df = om.parse_periodo_datas(orig["periodo"])
            if _di and _df:
                dup_inicio = dup_inicio or _di.isoformat()
                dup_fim = dup_fim or _df.isoformat()

        cur.execute("""
            INSERT INTO campanhas (id, nome, tipo, status, periodo, data_inicio, data_fim, observacoes)
            VALUES (%s, %s, %s, 'ativa', %s, %s, %s, %s)
        """, (
            new_id,
            new_nome,
            orig["tipo"],
            orig.get("periodo", ""),
            dup_inicio,
            dup_fim,
            orig.get("observacoes", "")
        ))

        cur.execute("SELECT * FROM campanha_itens WHERE campanha_id=%s", (id,))
        itens = cur.fetchall()
        for it in itens:
            item_id = f"item_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
            cur.execute("""
                INSERT INTO campanha_itens (
                    id, campanha_id, tipo_linha, nome_categoria, mercadologico, parte,
                    ordem, linha, codigo, descricao, custo, preco_oferta, preco_app,
                    observacao, destaque, classificacao_mix, familia, sellout, criado_por
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                item_id, new_id, it["tipo_linha"], it.get("nome_categoria"),
                it.get("mercadologico"), it["parte"], it["ordem"], it["linha"],
                it.get("codigo", ""), it.get("descricao", ""), it.get("custo"),
                it.get("preco_oferta"), it.get("preco_app"), it.get("observacao", ""),
                it.get("destaque"), it.get("classificacao_mix", 2),
                it.get("familia"), it.get("sellout", ""), it.get("criado_por", "")
            ))

        conn.commit()
        return {"success": True, "id": new_id, "nome": new_nome}
    finally:
        cur.close()
        conn.close()


# ─── Endpoints de Parâmetros e Metas ──────────────────────────────────────────
@app.get("/api/parametros")
def get_parametros():
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Tipos dinâmicos: união de parametros_pool e parametros. Mantém a ordem
        # dos 3 tipos base primeiro (compatibilidade), depois os criados pelo usuário.
        cur.execute("SELECT tipo FROM parametros_pool")
        tipos = [r["tipo"] for r in cur.fetchall() if r.get("tipo")]
        cur.execute("SELECT DISTINCT tipo FROM parametros")
        for r in cur.fetchall():
            if r.get("tipo") and r["tipo"] not in tipos:
                tipos.append(r["tipo"])
        base = ["ENCARTE", "ALERTA", "FDS_SAZONAL"]
        tipos = [t for t in base if t in tipos] + [t for t in tipos if t not in base]

        out = {"_tipos": tipos}
        for tipo in tipos:
            cur.execute("SELECT * FROM parametros WHERE tipo=%s ORDER BY ordem, id", (tipo,))
            params = cur.fetchall()
            cur.execute("SELECT * FROM parametros_pool WHERE tipo=%s", (tipo,))
            pool = cur.fetchone() or {"tipo": tipo, "pool_interna": None, "extra_pool": 0, "capa_max": 16, "app_max": 5}
            out[tipo] = {"params": params, "pool": pool, "linhas": params}
        return out
    finally:
        cur.close()
        conn.close()

@app.post("/api/parametros")
async def create_parametro(item: ParametroCreateRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(MAX(ordem),0)+1 FROM parametros WHERE tipo=%s", (item.tipo,))
        ordem = cur.fetchone()[0]
        comprador = (item.comprador or "").strip().lower() or None
        cur.execute("""
            INSERT INTO parametros (tipo, mercadologico, comprador, meta_divulgacao, meta_interna, ordem)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (item.tipo, item.mercadologico.strip().upper(), comprador, item.meta_divulgacao, item.meta_interna, ordem))
        conn.commit()
        novo_id = cur.lastrowid
    finally:
        cur.close()
        conn.close()
    await _broadcast_cotas()
    return {"success": True, "id": novo_id, "mercadologico": item.mercadologico}

@app.put("/api/parametros/{id}")
async def update_parametro(id: int, item: ParametroUpdateRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        fields = []
        params = []
        if item.mercadologico is not None:
            fields.append("mercadologico=%s")
            params.append(item.mercadologico.strip().upper())
        if item.comprador is not None:
            fields.append("comprador=%s")
            params.append((item.comprador or "").strip().lower() or None)
        if item.meta_divulgacao is not None:
            fields.append("meta_divulgacao=%s")
            params.append(item.meta_divulgacao)
        if item.meta_interna is not None:
            fields.append("meta_interna=%s")
            params.append(item.meta_interna)
        if item.extra_div is not None:
            fields.append("extra_div=%s")
            params.append(item.extra_div)
        if item.extra_int is not None:
            fields.append("extra_int=%s")
            params.append(item.extra_int)
        if item.ordem is not None:
            fields.append("ordem=%s")
            params.append(item.ordem)

        if not fields:
            return {"success": True}

        params.append(id)
        cur.execute(f"UPDATE parametros SET {', '.join(fields)} WHERE id=%s", tuple(params))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    await _broadcast_cotas()
    return {"success": True}

@app.delete("/api/parametros/{id}")
async def delete_parametro(id: int, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM parametros WHERE id=%s", (id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    await _broadcast_cotas()
    return {"success": True}

@app.put("/api/parametros/pool/{tipo}")
async def update_pool(tipo: str, item: PoolUpdateRequest, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        # Upsert direto (o frontend envia o estado completo do pool). pool_interna
        # pode ser NULL quando o tipo NÃO usa pool compartilhado na parte interna.
        # Respeita o 0 explícito: usar `x or default` transformava 0 em 16/5
        # (ex.: "Máx. App Clube = 0" voltava para 5). Só cai no padrão se vier None.
        capa_max = item.capa_max if item.capa_max is not None else 16
        app_max = item.app_max if item.app_max is not None else 5
        extra_pool = item.extra_pool if item.extra_pool is not None else 0
        cur.execute("""
            INSERT INTO parametros_pool (tipo, pool_interna, extra_pool, capa_max, app_max)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pool_interna=VALUES(pool_interna),
                extra_pool=VALUES(extra_pool),
                capa_max=VALUES(capa_max),
                app_max=VALUES(app_max)
        """, (
            tipo, item.pool_interna, extra_pool, capa_max, app_max
        ))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    await _broadcast_cotas()
    return {"success": True}


# ─── Tipos de campanha (editáveis) ─────────────────────────────────────────────
@app.post("/api/parametros/tipos")
def create_tipo(item: TipoCreateRequest, request: Request):
    require_adm(request)
    nome = (item.nome or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome do tipo.")
    if len(nome) > 60:
        raise HTTPException(status_code=400, detail="Nome do tipo muito longo (máx. 60).")
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Não pode existir outro tipo com o mesmo nome (ignora maiúsculas)
        cur.execute("SELECT tipo FROM parametros_pool WHERE UPPER(tipo)=UPPER(%s)", (nome,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f'Já existe um tipo chamado "{nome}".')
        cur.execute("SELECT DISTINCT tipo FROM parametros WHERE UPPER(tipo)=UPPER(%s)", (nome,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f'Já existe um tipo chamado "{nome}".')
        pool_interna = item.pool_interna if item.usa_pool else None
        capa_max = item.capa_max if item.capa_max is not None else 16
        app_max = item.app_max if item.app_max is not None else 5
        extra_pool = item.extra_pool if item.extra_pool is not None else 0
        cur.execute("""
            INSERT INTO parametros_pool (tipo, pool_interna, extra_pool, capa_max, app_max)
            VALUES (%s, %s, %s, %s, %s)
        """, (nome, pool_interna, extra_pool, capa_max, app_max))
        conn.commit()
        return {"success": True, "tipo": nome}
    finally:
        cur.close()
        conn.close()


@app.post("/api/parametros/tipos/{tipo}/rename")
async def rename_tipo(tipo: str, item: TipoRenameRequest, request: Request):
    require_adm(request)
    novo = (item.novo_nome or "").strip()
    if not novo:
        raise HTTPException(status_code=400, detail="Informe o novo nome.")
    if len(novo) > 60:
        raise HTTPException(status_code=400, detail="Nome do tipo muito longo (máx. 60).")
    if novo.upper() == tipo.upper():
        # Apenas troca de caixa: aplica mesmo assim
        pass
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # o novo nome não pode colidir com outro tipo já existente
        cur.execute("SELECT tipo FROM parametros_pool WHERE UPPER(tipo)=UPPER(%s) AND UPPER(tipo)<>UPPER(%s)", (novo, tipo))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail=f'Já existe um tipo chamado "{novo}".')
        # cascata: parametros, parametros_pool e campanhas que usam este tipo
        cur.execute("UPDATE parametros SET tipo=%s WHERE tipo=%s", (novo, tipo))
        cur.execute("UPDATE parametros_pool SET tipo=%s WHERE tipo=%s", (novo, tipo))
        cur.execute("UPDATE campanhas SET tipo=%s WHERE tipo=%s", (novo, tipo))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    await _broadcast_cotas()
    return {"success": True, "tipo": novo}


@app.delete("/api/parametros/tipos/{tipo}")
def delete_tipo(tipo: str, request: Request):
    require_adm(request)
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Bloqueia exclusão se houver campanhas usando o tipo (segurança)
        cur.execute("SELECT COUNT(*) AS n FROM campanhas WHERE tipo=%s", (tipo,))
        n = cur.fetchone()["n"]
        if n > 0:
            raise HTTPException(status_code=409, detail=f'Não dá para excluir: {n} campanha(s) usam o tipo "{tipo}". Renomeie ou mova essas campanhas antes.')
        cur.execute("DELETE FROM parametros WHERE tipo=%s", (tipo,))
        cur.execute("DELETE FROM parametros_pool WHERE tipo=%s", (tipo,))
        conn.commit()
        return {"success": True}
    finally:
        cur.close()
        conn.close()


# ─── Exportação Excel ─────────────────────────────────────────────────────────
@app.get("/api/exportar/excel/{id}")
def export_excel(id: str, usuario: Optional[str] = None, comprador: Optional[str] = None):
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")

        cur.execute("SELECT * FROM campanha_itens WHERE campanha_id=%s ORDER BY ordem ASC, criado_em ASC", (id,))
        itens = cur.fetchall()

        # Se for comprador comum, filtra automaticamente seus itens
        if usuario:
            role = om.get_user_role(usuario)
            if role not in ("adm", "gestor"):
                itens = [i for i in itens if (i.get("criado_por") or "").strip().lower() == usuario.strip().lower()]

        # Se tiver filtro explícito de comprador
        if comprador and comprador.strip():
            itens = [i for i in itens if (i.get("criado_por") or "").strip().lower() == comprador.strip().lower()]

        itens_completos = om.expandir_familias(itens)
        excel_bytes = excel_export.gerar_excel_campanha(camp, itens, itens_completos=itens_completos)
        camp_clean = "".join(c for c in (camp.get("nome") or "campanha") if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        sufixo = ""
        if comprador and comprador.strip():
            sufixo = f"_{comprador.strip().lower()}"
        elif usuario and om.get_user_role(usuario) not in ("adm", "gestor"):
            sufixo = f"_{usuario.strip().lower()}"
        filename = f"Mix_Ofertas_{camp_clean}{sufixo}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    finally:
        cur.close()
        conn.close()


@app.get("/api/exportar/excel-salvar/{id}")
def export_excel_salvar(id: str, usuario: Optional[str] = None, comprador: Optional[str] = None):
    """Gera a planilha e SALVA na pasta Downloads do PC (servidor).
    Usado pela janela nativa (WebView2), que não baixa arquivos por link.
    Retorna JSON com o nome/caminho do arquivo salvo."""
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campanha não encontrada.")

        cur.execute("SELECT * FROM campanha_itens WHERE campanha_id=%s ORDER BY ordem ASC, criado_em ASC", (id,))
        itens = cur.fetchall()

        # Se for comprador comum, filtra automaticamente seus itens
        if usuario:
            role = om.get_user_role(usuario)
            if role not in ("adm", "gestor"):
                itens = [i for i in itens if (i.get("criado_por") or "").strip().lower() == usuario.strip().lower()]

        # Se tiver filtro explícito de comprador
        if comprador and comprador.strip():
            itens = [i for i in itens if (i.get("criado_por") or "").strip().lower() == comprador.strip().lower()]

        itens_completos = om.expandir_familias(itens)
        excel_bytes = excel_export.gerar_excel_campanha(camp, itens, itens_completos=itens_completos)
        camp_clean = "".join(c for c in (camp.get("nome") or "campanha") if c.isalnum() or c in (" ", "-", "_")).strip().replace(" ", "_")
        sufixo = ""
        if comprador and comprador.strip():
            sufixo = f"_{comprador.strip().lower()}"
        elif usuario and om.get_user_role(usuario) not in ("adm", "gestor"):
            sufixo = f"_{usuario.strip().lower()}"
        filename = f"Mix_Ofertas_{camp_clean}{sufixo}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        pasta = os.path.join(os.path.expanduser("~"), "Downloads")
        try:
            os.makedirs(pasta, exist_ok=True)
        except Exception:
            pasta = os.path.expanduser("~")
        caminho = os.path.join(pasta, filename)
        with open(caminho, "wb") as f:
            f.write(excel_bytes)

        return {"ok": True, "arquivo": filename, "pasta": pasta, "caminho": caminho}
    finally:
        cur.close()
        conn.close()


# ─── Socket.IO: Tempo Real & Lançamento Seguro ─────────────────────────────────
connected_operators: Dict[str, Dict[str, Any]] = {}
OPERATOR_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6", "#14B8A6", "#F97316"]


def _fmt_valor(v):
    """Formata um valor para exibição no aviso 'antes → depois'."""
    if v is None or v == "":
        return "(vazio)"
    try:
        from decimal import Decimal
        if isinstance(v, (float, Decimal)):
            return f"{float(v):.2f}"
    except Exception:
        pass
    return str(v)


def _destinatarios_aviso(dono, admins, editor):
    """Lista de quem recebe o aviso: comprador dono + ADM(s), sem duplicar e sem
    incluir quem fez a edição (o gestor)."""
    out = []
    for d in [dono] + list(admins or []):
        dl = (d or "").strip()
        if not dl:
            continue
        if editor and dl.lower() == str(editor).lower():
            continue
        if dl.lower() in [x.lower() for x in out]:
            continue
        out.append(dl)
    return out

@sio.event
async def connect(sid, environ):
    pass

@sio.event
async def disconnect(sid):
    op = connected_operators.pop(sid, None)
    if op:
        camp_id = op.get("campaignId") or op.get("campanha_id")
        if camp_id:
            room = f"camp_{camp_id}"
            ops_in_room = [o for o in connected_operators.values() if o.get("campaignId") == camp_id or o.get("campanha_id") == camp_id]
            await sio.emit("operators-updated", ops_in_room, room=room)
            await sio.emit("operators-update", ops_in_room, room=room)

@sio.on("join-campaign")
@sio.on("join_campaign")
async def join_campaign(sid, data):
    camp_id = data.get("campaignId")
    usuario = data.get("usuario") or ""
    user_name = data.get("nome") or data.get("userName") or usuario or "Operador"
    role = om.get_user_role(usuario)

    room = f"camp_{camp_id}"
    await sio.enter_room(sid, room)

    color_index = len(connected_operators) % len(OPERATOR_COLORS)
    connected_operators[sid] = {
        "socketId": sid,
        "sid": sid,
        "campaignId": camp_id,
        "campanha_id": camp_id,
        "usuario": usuario,
        "userName": user_name,
        "nome": user_name,
        "role": role,
        "color": OPERATOR_COLORS[color_index],
        "joinedAt": datetime.datetime.now().isoformat(),
        "joined_at": datetime.datetime.now().isoformat(),
    }

    ops_in_room = [o for o in connected_operators.values() if o.get("campaignId") == camp_id or o.get("campanha_id") == camp_id]
    await sio.emit("operators-updated", ops_in_room, room=room)
    await sio.emit("operators-update", ops_in_room, room=room)

@sio.on("fast-add-product")
@sio.on("fast_add_product")
async def fast_add_product(sid, data):
    camp_id = data.get("campaignId")
    item = data.get("item")
    operator_name = data.get("operatorName")

    if not camp_id or not item:
        return

    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (camp_id,))
        camp = cur.fetchone()
        if not camp:
            await sio.emit("action-blocked", {"message": "Campanha não encontrada."}, room=sid)
            return

        usuario = connected_operators.get(sid, {}).get("usuario") or item.get("usuario") or ""
        role = om.get_user_role(usuario)

        merc = str(item.get("mercadologico") or "").strip()
        parte = "interno" if item.get("parte") == "interno" else "divulgacao"
        cod_produto = str(item.get("codigo") or "").strip()
        desc_produto = str(item.get("descricao") or "").strip()
        preco_oferta = item.get("preco_oferta")
        preco_custo = item.get("custo")

        # 1. Validação básica de código e descrição
        if not cod_produto or not desc_produto:
            await sio.emit("action-blocked", {"message": "Código e Descrição do produto são obrigatórios."}, room=sid)
            return

        # 2. Validação obrigatória de setor mercadológico (não existe "Geral").
        if not merc or merc.strip().lower() == "geral":
            await sio.emit("action-blocked", {
                "message": 'Selecione um setor mercadológico válido para lançar o produto (não existe "Geral"). Escolha o mercadológico na lista.'
            }, room=sid)
            return

        # 3. Validação do produto no catálogo (garantia de cadastro)
        cur.execute("SELECT * FROM produtos WHERE codigo=%s", (cod_produto,))
        prod_catalogo = cur.fetchone()
        if not prod_catalogo:
            await sio.emit("action-blocked", {"message": f"Produto código {cod_produto} não está cadastrado no catálogo!"}, room=sid)
            return

        # Usa a descrição oficial do catálogo para evitar alteração humana manual
        desc_produto = prod_catalogo.get("descricao") or desc_produto

        # 4. Validação de Preço de Oferta
        preco_oferta_num = parse_num(preco_oferta)
        if preco_oferta_num is None or preco_oferta_num <= 0:
            await sio.emit("action-blocked", {"message": "O Preço de Oferta é obrigatório e deve ser maior que zero."}, room=sid)
            return

        # 5. Validação de Preço App quando destaque for App
        destaque = item.get("destaque") or None
        preco_app_num = parse_num(item.get("preco_app"))
        if destaque == "App":
            if preco_app_num is None or preco_app_num <= 0:
                await sio.emit("action-blocked", {"message": "Para produtos em destaque App, o Preço App é obrigatório."}, room=sid)
                return

        # 6. Conflito de período com outras campanhas ativas
        conflito = om.checar_conflito_produto(camp_id, cod_produto)
        if conflito.get("conflito"):
            await sio.emit("action-blocked", {"message": conflito.get("motivo"), "conflito": True}, room=sid)
            return

        # 7. Compradores só lançam em seus próprios mercadológicos (ADM e Gestor podem lançar em qualquer setor)
        if role not in ("adm", "gestor"):
            meus = [m.upper().strip() for m in om.mercadologicos_do_comprador(camp.get("tipo", ""), usuario)]
            norm_merc = merc.upper().strip()
            if meus and norm_merc not in meus:
                match = any(m == norm_merc or m.replace(" ", "") == norm_merc.replace(" ", "") or m.split("|")[0].strip() == norm_merc for m in meus)
                if not match:
                    await sio.emit("action-blocked", {"message": f'"{merc}" não é um mercadológico atribuído a você.'}, room=sid)
                    return

        # 8. REGRA RÍGIDA DE COTA: APLICA-SE A TODOS, INCLUSIVE ADM (ZERO ERRO)
        cota = om.checar_cota(camp, {**item, "mercadologico": merc, "parte": parte})
        if not cota.get("ok"):
            await sio.emit("action-blocked", {
                "message": cota.get("motivo"),
                "quota": True,
                "mercadologico": merc,
                "parte": parte
            }, room=sid)
            return

        # 9. REGRA RÍGIDA DE DESTAQUE: APLICA-SE A TODOS, INCLUSIVE ADM (Capa / App)
        if destaque in ("Capa", "App"):
            d = om.checar_destaque(camp, destaque)
            if not d.get("ok"):
                await sio.emit("action-blocked", {
                    "message": d.get("motivo"),
                    "quota": True
                }, room=sid)
                return

        # 10. Lançamento. A FAMÍLIA fica registrada no item (familia + mix=1), mas
        # NÃO gravamos os irmãos: só o produto digitado ("cabeça") entra na campanha.
        # A família completa é expandida apenas na aba "Relação Completa" do Excel.
        classificacao_mix = int(item.get("classificacao_mix") or 2)
        cod_familia = str(item.get("familia") or prod_catalogo.get("familia") or "").strip() or None

        produtos_para_lancar = [prod_catalogo]  # sempre só o cabeça

        cur.execute("SELECT COALESCE(MAX(ordem),0) as next_ord FROM campanha_itens WHERE campanha_id=%s", (camp_id,))
        last_order = cur.fetchone()["next_ord"]

        for idx, prod in enumerate(produtos_para_lancar):
            last_order += 1
            it_id = f"item_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}" if idx > 0 else (item.get("id") or f"item_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}")
            custo_item = parse_num(prod.get("preco_custo")) if preco_custo in (None, "") else parse_num(preco_custo)

            row = {
                "id": it_id,
                "campanha_id": camp_id,
                "tipo_linha": "produto",
                "nome_categoria": None,
                "mercadologico": merc or None,
                "parte": parte,
                "ordem": last_order,
                "linha": last_order,
                "codigo": prod["codigo"],
                "descricao": prod.get("descricao") or desc_produto,
                "custo": custo_item,
                "preco_oferta": preco_oferta_num,
                "preco_app": preco_app_num,
                "observacao": item.get("observacao") or "",
                "destaque": destaque,
                "classificacao_mix": classificacao_mix,
                "familia": cod_familia,
                "sellout": item.get("sellout") or "",
                "criado_por": usuario,
            }

            cur.execute("""
                INSERT INTO campanha_itens (
                    id, campanha_id, tipo_linha, nome_categoria, mercadologico, parte,
                    ordem, linha, codigo, descricao, custo, preco_oferta, preco_app,
                    observacao, destaque, classificacao_mix, familia, sellout, criado_por
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row["id"], row["campanha_id"], row["tipo_linha"], row["nome_categoria"],
                row["mercadologico"], row["parte"], row["ordem"], row["linha"],
                row["codigo"], row["descricao"], row["custo"], row["preco_oferta"],
                row["preco_app"], row["observacao"], row["destaque"],
                row["classificacao_mix"], row["familia"], row["sellout"], row["criado_por"]
            ))

            await sio.emit("product-added-live", {
                "item": row,
                "operatorName": operator_name or usuario
            }, room=f"camp_{camp_id}")

        conn.commit()
        await sio.emit("cotas-changed", {}, room=f"camp_{camp_id}")

    finally:
        cur.close()
        conn.close()

@sio.on("update-item-field")
@sio.on("update_item_field")
async def update_item_field(sid, data):
    camp_id = data.get("campaignId")
    item_id = data.get("itemId")
    field = data.get("field")
    value = data.get("value")

    allowed_fields = [
        "mercadologico", "parte", "preco_oferta", "preco_app", "custo",
        "observacao", "destaque", "classificacao_mix", "familia", "sellout", "descricao"
    ]
    if not camp_id or not item_id or field not in allowed_fields:
        return

    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanha_itens WHERE id=%s", (item_id,))
        item = cur.fetchone()
        if not item:
            return

        usuario = connected_operators.get(sid, {}).get("usuario") or ""
        role = om.get_user_role(usuario)

        cur.execute("SELECT * FROM campanhas WHERE id=%s", (camp_id,))
        camp = cur.fetchone()

        # Validação de destaque
        if field == "destaque" and value in ("Capa", "App"):
            if role in ("adm", "gestor"):
                d = om.checar_destaque(camp, value)
                if not d.get("ok"):
                    await sio.emit("action-blocked", {"message": d.get("motivo"), "quota": True}, room=sid)
                    return

        # Formatação de valores numéricos e campos
        clean_value = value
        if field in ("custo", "preco_oferta", "preco_app"):
            clean_value = parse_num(value)
        elif field == "classificacao_mix":
            clean_value = int(value) if value not in (None, "") else 1

        cur.execute(f"UPDATE campanha_itens SET {field}=%s WHERE id=%s", (clean_value, item_id))
        conn.commit()

        await sio.emit("item-field-updated-live", {
            "itemId": item_id,
            "field": field,
            "value": clean_value
        }, room=f"camp_{camp_id}")

        if field in ("mercadologico", "parte", "destaque"):
            await sio.emit("cotas-changed", {}, room=f"camp_{camp_id}")

        # Aviso: SOMENTE quando o GESTOR (ex.: allan) altera o produto de OUTRA pessoa.
        # Recebem o comprador dono e o(s) ADM(s). Quando o próprio ADM edita, NÃO avisa ninguém.
        try:
            dono = (item.get("criado_por") or "").strip()
            if role == "gestor" and dono and dono.lower() != (usuario or "").lower():
                lbl = om.label_campo(field)
                desc_item = item.get("descricao") or item.get("codigo") or "produto"
                nome_dono = om.get_user_nome(dono)
                nome_gestor = om.get_user_nome(usuario)
                antes_txt = _fmt_valor(item.get(field))
                depois_txt = _fmt_valor(clean_value)
                cur.execute("SELECT usuario FROM usuarios WHERE role='adm' AND ativo=1")
                admins = [r["usuario"] for r in cur.fetchall()]
                destinatarios = _destinatarios_aviso(dono, admins, usuario)
                for d in destinatarios:
                    if d.lower() == dono.lower():
                        msg = (f'O gestor alterou {lbl} do seu produto "{desc_item}": '
                               f'de {antes_txt} para {depois_txt}.')
                    else:
                        msg = (f'O gestor {nome_gestor} alterou {lbl} do produto de {nome_dono} '
                               f'("{desc_item}"): de {antes_txt} para {depois_txt}.')
                    om.registrar_notificacao(cur, d, usuario, camp_id, item_id, desc_item,
                                             field, item.get(field), clean_value, "edicao", msg)
                conn.commit()
        except Exception as _e:
            print(f"[notificacoes] aviso ao gravar (edicao): {_e}")
    finally:
        cur.close()
        conn.close()

@sio.on("delete-item")
@sio.on("delete_item")
async def delete_item(sid, data):
    camp_id = data.get("campaignId")
    item_id = data.get("itemId")
    if not camp_id or not item_id:
        return

    usuario = connected_operators.get(sid, {}).get("usuario") or ""
    role = om.get_user_role(usuario)

    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanha_itens WHERE id=%s AND campanha_id=%s", (item_id, camp_id))
        item = cur.fetchone()

        cur.execute("DELETE FROM campanha_itens WHERE id=%s AND campanha_id=%s", (item_id, camp_id))
        conn.commit()
        await sio.emit("item-deleted-live", {"itemId": item_id}, room=f"camp_{camp_id}")
        await sio.emit("cotas-changed", {}, room=f"camp_{camp_id}")

        # Aviso: SOMENTE quando o GESTOR remove o produto de OUTRA pessoa (ADM não dispara).
        try:
            dono = (item.get("criado_por") or "").strip() if item else ""
            if item and role == "gestor" and dono and dono.lower() != (usuario or "").lower():
                desc_item = item.get("descricao") or item.get("codigo") or "produto"
                nome_dono = om.get_user_nome(dono)
                nome_gestor = om.get_user_nome(usuario)
                cur.execute("SELECT usuario FROM usuarios WHERE role='adm' AND ativo=1")
                admins = [r["usuario"] for r in cur.fetchall()]
                destinatarios = _destinatarios_aviso(dono, admins, usuario)
                for d in destinatarios:
                    if d.lower() == dono.lower():
                        msg = f'O gestor removeu o seu produto "{desc_item}" da campanha.'
                    else:
                        msg = f'O gestor {nome_gestor} removeu o produto de {nome_dono} ("{desc_item}") da campanha.'
                    om.registrar_notificacao(cur, d, usuario, camp_id, item_id, desc_item,
                                             "", None, None, "remocao", msg)
                conn.commit()
        except Exception as _e:
            print(f"[notificacoes] aviso ao gravar (remocao): {_e}")
    finally:
        cur.close()
        conn.close()

@sio.on("pedir-autorizacao")
@sio.on("pedir_autorizacao")
async def pedir_autorizacao(sid, data):
    camp_id = data.get("campaignId")
    merc = data.get("mercadologico")
    parte = data.get("parte") or "divulgacao"
    qtd = int(data.get("quantidade") or 3)
    usuario = connected_operators.get(sid, {}).get("usuario") or ""

    if not camp_id or not merc or not usuario:
        return

    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM campanhas WHERE id=%s", (camp_id,))
        camp = cur.fetchone()
        tp = om.tipo_param(camp.get("tipo", "")) if camp else "ENCARTE"

        pid = f"ped_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        cur.execute("""
            INSERT INTO pedidos_autorizacao (id, campanha_id, tipo, mercadologico, parte, comprador, quantidade, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pendente')
        """, (pid, camp_id, tp, merc, parte, usuario, qtd))
        conn.commit()

        pedido = {
            "id": pid,
            "campanha_id": camp_id,
            "tipo": tp,
            "mercadologico": merc,
            "parte": parte,
            "comprador": usuario,
            "quantidade": qtd,
            "status": "pendente",
        }
        await sio.emit("pedido-autorizacao", pedido, room=f"camp_{camp_id}")
        await sio.emit("action-blocked", {
            "message": f"Pedido de autorização para {merc} enviado ao ADM.",
            "info": True
        }, room=sid)
    finally:
        cur.close()
        conn.close()

@sio.on("resolver-autorizacao")
@sio.on("resolver_autorizacao")
async def resolver_autorizacao(sid, data):
    camp_id = data.get("campaignId")
    pedido_id = data.get("pedidoId")
    aprovar = bool(data.get("aprovar"))
    permanente = bool(data.get("permanente"))
    qtd = int(data.get("quantidade") or 3)

    usuario = connected_operators.get(sid, {}).get("usuario") or ""
    role = om.get_user_role(usuario)
    if role != "adm":
        return

    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM pedidos_autorizacao WHERE id=%s", (pedido_id,))
        ped = cur.fetchone()
        if not ped:
            return

        # permanente=1 → soma no parâmetro global (vale p/ todas as campanhas);
        # permanente=0 (padrão) → o pedido aprovado conta como extra SÓ nesta campanha (checar_cota soma).
        perm_flag = 1 if (aprovar and permanente) else 0
        cur.execute("UPDATE pedidos_autorizacao SET status=%s, permanente=%s WHERE id=%s",
                    ("aprovado" if aprovar else "negado", perm_flag, pedido_id))

        if aprovar and permanente:
            cur.execute("SELECT * FROM campanhas WHERE id=%s", (camp_id,))
            camp = cur.fetchone()
            tp = om.tipo_param(camp["tipo"]) if camp else ped["tipo"]

            if ped["parte"] == "divulgacao":
                cur.execute("""
                    UPDATE parametros SET extra_div=extra_div+%s
                    WHERE tipo=%s AND UPPER(mercadologico)=UPPER(%s)
                """, (qtd, tp, ped["mercadologico"]))
            else:
                cur.execute("""
                    UPDATE parametros_pool SET extra_pool=extra_pool+%s
                    WHERE tipo=%s AND pool_interna IS NOT NULL
                """, (qtd, tp))
                cur.execute("""
                    UPDATE parametros SET extra_int=extra_int+%s
                    WHERE tipo=%s AND UPPER(mercadologico)=UPPER(%s)
                """, (qtd, tp, ped["mercadologico"]))

        conn.commit()

        await sio.emit("autorizacao-resolvida", {
            "aprovado": aprovar,
            "mercadologico": ped["mercadologico"],
            "parte": ped["parte"]
        }, room=f"camp_{camp_id}")

        await sio.emit("cotas-changed", {}, room=f"camp_{camp_id}")
    finally:
        cur.close()
        conn.close()


# ─── Notificações (avisos de edição do gestor) ─────────────────────────────────
@app.get("/api/notificacoes")
def listar_notificacoes(usuario: str = "", nao_lidas: int = 1, limit: int = 50):
    usuario = (usuario or "").strip()
    if not usuario:
        return {"notificacoes": []}
    lim = max(1, min(int(limit or 50), 200))
    conn = om.get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        filtro_lida = "AND lida=0" if nao_lidas else ""
        cur.execute(
            f"""SELECT id, remetente, campanha_id, item_id, item_desc, campo,
                       valor_antes, valor_depois, tipo, mensagem, lida, criado_em
                FROM notificacoes
                WHERE LOWER(destinatario)=LOWER(%s) {filtro_lida}
                ORDER BY lida ASC, criado_em DESC
                LIMIT {lim}""",
            (usuario,),
        )
        rows = cur.fetchall()
        for r in rows:
            if r.get("criado_em") is not None:
                r["criado_em"] = str(r["criado_em"])
        return {"notificacoes": rows}
    finally:
        cur.close()
        conn.close()


@app.post("/api/notificacoes/{nid}/lida")
def marcar_notificacao_lida(nid: str):
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE notificacoes SET lida=1 WHERE id=%s", (nid,))
        conn.commit()
        return {"success": True}
    finally:
        cur.close()
        conn.close()


@app.post("/api/notificacoes/marcar-todas-lidas")
def marcar_todas_notificacoes_lidas(usuario: str = ""):
    usuario = (usuario or "").strip()
    if not usuario:
        return {"success": False}
    conn = om.get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE notificacoes SET lida=1 WHERE LOWER(destinatario)=LOWER(%s)", (usuario,))
        conn.commit()
        return {"success": True, "afetadas": cur.rowcount}
    finally:
        cur.close()
        conn.close()


# ─── Servir SPA (React) ───────────────────────────────────────────────────────
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Endpoint não encontrado.")
    index_path = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Mix de Ofertas 2.0</h1><p>Front-end em compilação.</p>")


# ─── Utilitários de Inicialização Desktop ──────────────────────────────────────
def find_free_port(start_port=3001):
    for port in range(start_port, start_port + 50):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            pass
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


if __name__ == "__main__":
    import uvicorn
    om.init_mysql()
    port = int(os.environ.get("PORT", "3001"))
    print(f"Iniciando Servidor Mix de Ofertas na porta {port}...")
    uvicorn.run(socket_app, host="0.0.0.0", port=port, log_level="warning")
