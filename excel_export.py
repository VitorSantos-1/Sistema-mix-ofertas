"""
excel_export.py — Gerador de Planilha Excel Oficial para Mix de Ofertas
Supermercados Opção

Estrutura aprovada:
- Divulgação em cima, separada por linha de mercadológico.
- Interno em baixo por último, com seus mercadológicos.
- Colunas completas: Código, Descrição, Oferta, App, Parte, Destaque, Tipo Mix, Família, Observação, Comprador.
"""

import io
from typing import List, Dict, Any
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Cores do tema Supermercados Opção
HEADER_FILL = PatternFill(start_color="E06666", end_color="E06666", fill_type="solid")
SUBHEADER_FILL = PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid")
SECTION_DIV_FILL = PatternFill(start_color="C2410C", end_color="C2410C", fill_type="solid")  # Laranja escuro / Opção
SECTION_INT_FILL = PatternFill(start_color="4B5563", end_color="4B5563", fill_type="solid")  # Cinza escuro elegante
MERC_DIV_FILL = PatternFill(start_color="FCE5CD", end_color="FCE5CD", fill_type="solid")     # Tom suave p/ setor
MERC_INT_FILL = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")     # Tom suave neutro
COL_HEAD_FILL = PatternFill(start_color="EA9999", end_color="EA9999", fill_type="solid")

THIN_SIDE = Side(style="thin", color="D1D5DB")
BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)

FONT_TITLE = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
FONT_SECTION = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
FONT_MERC = Font(name="Calibri", size=10, bold=True, color="1F2937")
FONT_HEAD = Font(name="Calibri", size=10, bold=True, color="1A1A1A")
FONT_DATA = Font(name="Calibri", size=10, color="000000")
FONT_BOLD = Font(name="Calibri", size=10, bold=True, color="000000")


def mix_texto(m: Any) -> str:
    if m == 1 or m == "1":
        return "1 - Em família"
    if m == 2 or m == "2":
        return "2 - Unitário"
    return "2 - Unitário"


def to_float(v: Any):
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
        return round(float(s), 2)
    except Exception:
        return None


def gerar_excel_campanha(campanha: Dict[str, Any], itens: List[Dict[str, Any]], itens_completos: List[Dict[str, Any]] = None) -> bytes:
    wb = Workbook()
    ws = wb.active

    nome_camp = str(campanha.get("nome") or "Campanha").strip()
    periodo = str(campanha.get("periodo") or "").strip()
    sheet_title = "".join(c for c in nome_camp[:31] if c not in r":\/?*[]") or "Mix_Ofertas"
    ws.title = sheet_title

    # Filtra produtos válidos
    itens_validos = [i for i in itens if i.get("tipo_linha") == "produto" or i.get("codigo") or i.get("descricao")]

    # Separa em DIVULGAÇÃO e INTERNO
    itens_div = [i for i in itens_validos if (i.get("parte") or "divulgacao").lower() != "interno"]
    itens_int = [i for i in itens_validos if (i.get("parte") or "").lower() == "interno"]

    def agrupar_por_merc(lista):
        grupos = {}
        for it in lista:
            merc = str(it.get("mercadologico") or "GERAL").strip().upper()
            grupos.setdefault(merc, []).append(it)
        # Ordena alfabeticamente os mercadológicos
        for m in grupos:
            grupos[m].sort(key=lambda x: (
                str(x.get("familia") or "ZZZ"),
                str(x.get("descricao") or "")
            ))
        return sorted(grupos.items(), key=lambda t: t[0])

    grupos_div = agrupar_por_merc(itens_div)
    grupos_int = agrupar_por_merc(itens_int)

    NUM_COLS = 9
    LAST_COL_LETTER = "I"

    headers = [
        "CÓDIGO", "DESCRIÇÃO DO PRODUTO", "PREÇO DE OFERTA", "PREÇO DE APP",
        "PARTE", "DESTAQUE", "TIPO MIX", "OBSERVAÇÃO", "COMPRADOR"
    ]

    money_format = '"R$" #,##0.00'

    # Linha 1: Título Supermercados Opção
    ws.merge_cells(f"A1:{LAST_COL_LETTER}1")
    cell_a1 = ws["A1"]
    cell_a1.value = "SUPERMERCADOS OPÇÃO — MIX DE OFERTAS & ENCARTES"
    cell_a1.font = FONT_TITLE
    cell_a1.fill = SECTION_DIV_FILL
    cell_a1.alignment = Alignment(horizontal="center", vertical="center")

    # Linha 2: Campanha e Vigência
    ws.merge_cells(f"A2:{LAST_COL_LETTER}2")
    cell_a2 = ws["A2"]
    sub_txt = f"CAMPANHA: {nome_camp.upper()}"
    if periodo:
        sub_txt += f"   |   VIGÊNCIA: {periodo.upper()}"
    cell_a2.value = sub_txt
    cell_a2.font = FONT_HEAD
    cell_a2.fill = SUBHEADER_FILL
    cell_a2.alignment = Alignment(horizontal="center", vertical="center")

    for col in range(1, NUM_COLS + 1):
        ws.cell(row=1, column=col).border = BORDER
        ws.cell(row=2, column=col).border = BORDER

    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 22

    current_row = 3

    def render_bloco(titulo_bloco, cor_banner, grupos, parte_nome, merc_fill):
        nonlocal current_row
        if not grupos:
            return

        # Banner da Seção (ex.: OFERTAS DE DIVULGAÇÃO)
        ws.merge_cells(f"A{current_row}:{LAST_COL_LETTER}{current_row}")
        c_banner = ws[f"A{current_row}"]
        c_banner.value = f"  {titulo_bloco}  ({sum(len(its) for _, its in grupos)} itens)"
        c_banner.font = FONT_SECTION
        c_banner.fill = cor_banner
        c_banner.alignment = Alignment(horizontal="left", vertical="center")
        for c in range(1, NUM_COLS + 1):
            ws.cell(row=current_row, column=c).border = BORDER
        ws.row_dimensions[current_row].height = 24
        current_row += 1

        # Cabeçalhos das Colunas
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col_idx, value=h)
            cell.font = FONT_HEAD
            cell.fill = COL_HEAD_FILL
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[current_row].height = 22
        current_row += 1

        # Para cada mercadológico
        for merc, items in grupos:
            # Linha de Mercadológico (sai da coluna e fica em uma linha própria!)
            ws.merge_cells(f"A{current_row}:{LAST_COL_LETTER}{current_row}")
            c_merc = ws[f"A{current_row}"]
            c_merc.value = f"▶  SETOR: {merc}  ({len(items)} produto{'s' if len(items) != 1 else ''})"
            c_merc.font = FONT_MERC
            c_merc.fill = merc_fill
            c_merc.alignment = Alignment(horizontal="left", vertical="center")
            for c in range(1, NUM_COLS + 1):
                ws.cell(row=current_row, column=c).border = BORDER
            ws.row_dimensions[current_row].height = 20
            current_row += 1

            # Produtos desse mercadológico
            for it in items:
                cod = str(it.get("codigo") or "").strip()
                desc = str(it.get("descricao") or "").strip()
                p_oferta = to_float(it.get("preco_oferta"))
                p_app = to_float(it.get("preco_app"))
                destaque = str(it.get("destaque") or "").strip() or "—"
                mix = mix_texto(it.get("classificacao_mix"))
                obs = str(it.get("observacao") or "").strip()
                comprador = str(it.get("criado_por") or "").strip()

                row_vals = [
                    cod, desc, p_oferta, p_app, parte_nome,
                    destaque, mix, obs, comprador
                ]

                for col_idx, val in enumerate(row_vals, 1):
                    cell = ws.cell(row=current_row, column=col_idx, value=val)
                    cell.font = FONT_DATA
                    cell.border = BORDER

                    if col_idx in (3, 4):  # Preços
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        if val is not None:
                            cell.number_format = money_format
                    elif col_idx in (1, 5, 6, 7):  # Código, parte, destaque, tipo mix
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                    elif col_idx == 2:  # Descrição
                        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                    else:  # Observação, Comprador
                        cell.alignment = Alignment(horizontal="left", vertical="center")

                ws.row_dimensions[current_row].height = 20
                current_row += 1

        # Linha em branco de respiro entre seções
        current_row += 1

    # 1. DIVULGAÇÃO EM CIMA
    render_bloco("📢  OFERTAS DE DIVULGAÇÃO", SECTION_DIV_FILL, grupos_div, "Divulgação", MERC_DIV_FILL)

    # 2. INTERNO EM BAIXO POR ÚLTIMO
    render_bloco("📦  OFERTAS INTERNAS", SECTION_INT_FILL, grupos_int, "Interno", MERC_INT_FILL)

    # Larguras otimizadas das colunas
    larguras = [
        15,  # A: Código
        48,  # B: Descrição
        18,  # C: Preço Oferta
        18,  # D: Preço App
        14,  # E: Parte
        14,  # F: Destaque
        16,  # G: Tipo Mix
        28,  # H: Observação
        16,  # I: Comprador
    ]
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Configuração de impressão A4 em paisagem
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    # ── ABA 2: RELAÇÃO COMPLETA DE PRODUTOS ──
    # Lista plana com TODOS os produtos (é AQUI que a família aparece inteira,
    # expandida a partir do catálogo). A aba principal fica só com o produto digitado.
    fonte_completa = itens_completos if itens_completos is not None else itens
    itens_completos_validos = [i for i in fonte_completa if i.get("tipo_linha") == "produto" or i.get("codigo") or i.get("descricao")]
    _render_relacao_completa(wb, campanha, itens_completos_validos, money_format)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def _render_relacao_completa(wb, campanha, itens_validos, money_format):
    ws2 = wb.create_sheet("Relação Completa")

    headers2 = [
        "CÓDIGO", "DESCRIÇÃO DO PRODUTO", "PARTE", "SETOR (MERCADOLÓGICO)",
        "PREÇO DE OFERTA", "PREÇO DE APP", "DESTAQUE", "TIPO MIX",
        "OBSERVAÇÃO", "COMPRADOR",
    ]
    ncols = len(headers2)
    last_letter = get_column_letter(ncols)

    nome_camp = str(campanha.get("nome") or "Campanha").strip()
    periodo = str(campanha.get("periodo") or "").strip()

    # Título
    ws2.merge_cells(f"A1:{last_letter}1")
    c1 = ws2["A1"]
    c1.value = "RELAÇÃO COMPLETA DE PRODUTOS — TODOS OS ITENS (INCLUI FAMÍLIAS)"
    c1.font = FONT_TITLE
    c1.fill = SECTION_DIV_FILL
    c1.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 26

    ws2.merge_cells(f"A2:{last_letter}2")
    c2 = ws2["A2"]
    sub = f"CAMPANHA: {nome_camp.upper()}"
    if periodo:
        sub += f"   |   VIGÊNCIA: {periodo.upper()}"
    sub += f"   |   TOTAL: {len(itens_validos)} produtos"
    c2.value = sub
    c2.font = FONT_HEAD
    c2.fill = SUBHEADER_FILL
    c2.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[2].height = 20
    for col in range(1, ncols + 1):
        ws2.cell(row=1, column=col).border = BORDER
        ws2.cell(row=2, column=col).border = BORDER

    # Cabeçalho das colunas (linha 3)
    head_row = 3
    for col_idx, h in enumerate(headers2, 1):
        cell = ws2.cell(row=head_row, column=col_idx, value=h)
        cell.font = FONT_HEAD
        cell.fill = COL_HEAD_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws2.row_dimensions[head_row].height = 26

    # Ordena: Divulgação antes de Interno, depois setor, família e descrição
    def parte_nome(it):
        return "Interno" if (it.get("parte") or "").lower() == "interno" else "Divulgação"

    itens_ord = sorted(
        itens_validos,
        key=lambda it: (
            0 if parte_nome(it) == "Divulgação" else 1,
            str(it.get("mercadologico") or "GERAL").upper(),
            str(it.get("familia") or "ZZZ"),
            str(it.get("descricao") or ""),
        ),
    )

    r = head_row + 1
    for it in itens_ord:
        row_vals = [
            str(it.get("codigo") or "").strip(),
            str(it.get("descricao") or "").strip(),
            parte_nome(it),
            str(it.get("mercadologico") or "GERAL").strip().upper(),
            to_float(it.get("preco_oferta")),
            to_float(it.get("preco_app")),
            str(it.get("destaque") or "").strip() or "—",
            mix_texto(it.get("classificacao_mix")),
            str(it.get("observacao") or "").strip(),
            str(it.get("criado_por") or "").strip(),
        ]
        for col_idx, val in enumerate(row_vals, 1):
            cell = ws2.cell(row=r, column=col_idx, value=val)
            cell.font = FONT_DATA
            cell.border = BORDER
            if col_idx in (5, 6):  # preços
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if val is not None:
                    cell.number_format = money_format
            elif col_idx == 2:  # descrição
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            elif col_idx in (9,):  # observação
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="center", vertical="center")
        ws2.row_dimensions[r].height = 18
        r += 1

    # Filtro do Excel + congela cabeçalho
    last_data_row = max(head_row, r - 1)
    ws2.auto_filter.ref = f"A{head_row}:{last_letter}{last_data_row}"
    ws2.freeze_panes = f"A{head_row + 1}"

    larguras2 = [14, 46, 13, 24, 16, 16, 14, 16, 26, 16]
    for i, w in enumerate(larguras2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    ws2.page_setup.orientation = ws2.ORIENTATION_LANDSCAPE
    ws2.page_setup.paperSize = ws2.PAPERSIZE_A4
    ws2.sheet_properties.pageSetUpPr.fitToPage = True
    ws2.page_setup.fitToWidth = 1
    ws2.page_setup.fitToHeight = 0
