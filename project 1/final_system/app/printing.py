"""
printing.py — الطباعة
---------------------
- إيصال استلام الطلب للعميل (فيه الفلوس)
- ورقة شغل المصنع (المقاسات والموديل من غير أسعار) ← بتمشى مع القماش من القص للتسليم
- إيصال البيع الجاهز

كله HTML بيتعرض فى معاينة قبل الطباعة. من المعاينة تقدر تطبع على أى طابعة،
أو تختار "Microsoft Print to PDF" عشان تحفظه PDF وتبعته واتساب.
"""

import base64
import html
from datetime import datetime

from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter

from models import FABRIC_SOURCES, iso_to_display, num
from qt_widgets import money


def _e(value):
    return html.escape(str(value)) if value not in (None, "") else "—"


def _header(company, logo, title):
    logo_html = ""
    if logo:
        mime = "image/png" if logo[:4] == b"\x89PNG" else "image/jpeg"
        logo_html = f'<img src="data:{mime};base64,{base64.b64encode(logo).decode()}" height="70">'
    contact = " — ".join(_e(x) for x in (company.get("phone"), company.get("address")) if x)
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" dir="rtl"><tr>
      <td align="right" valign="middle"><span style="font-size:18pt; font-weight:bold;">{_e(company.get('name'))}</span>
        <br><span style="color:#555;">{contact}</span></td>
      <td align="left" valign="middle">{logo_html}</td>
    </tr></table>
    <hr>
    <p align="center" style="font-size:15pt; font-weight:bold;">{title}</p>
    """


def _doc(body):
    return f"""<html dir="rtl"><body dir="rtl" style="font-family: 'Segoe UI', Tahoma, Arial; font-size: 11pt;">
    {body}
    <p style="color:#888; font-size:8pt;" align="center">اتطبع {datetime.now():%d/%m/%Y %H:%M}</p>
    </body></html>"""


def _kv_table(rows, width="100%"):
    cells = "".join(f'<tr><td style="color:#555;" width="30%">{_e(k)}</td><td><b>{v}</b></td></tr>' for k, v in rows)
    return f'<table width="{width}" cellpadding="5" cellspacing="0" border="1" dir="rtl" ' \
           f'style="border-collapse:collapse; border-color:#bbb;">{cells}</table>'


def _measurements_html(values):
    groups = {}
    for key, v in (values or {}).items():
        grp, _, name = key.partition("|")
        groups.setdefault(grp, []).append((name, v))
    if not groups:
        return "<p>مفيش مقاسات متسجلة</p>"
    out = []
    for grp, items in groups.items():
        cells = "".join(f'<td align="center" style="padding:4px;"><span style="color:#555;">{_e(n)}</span><br>'
                        f'<b style="font-size:14pt;">{_e(v)}</b></td>' for n, v in items)
        out.append(f'<p style="font-weight:bold; margin-bottom:2px;">{_e(grp)}</p>'
                   f'<table border="1" cellspacing="0" cellpadding="2" dir="rtl" style="border-collapse:collapse;">'
                   f'<tr>{cells}</tr></table>')
    return "".join(out)


def order_receipt_html(order, company, logo=None):
    paid = num(order.get("deposit")) + (num(order.get("final_collected")) if order.get("status") == "completed" else 0)
    rows = [
        ("رقم الطلب", f"#{order['id']}"),
        ("التاريخ", _e(iso_to_display(order.get("created_at")))),
        ("العميل", _e(order.get("customer_name"))),
        ("الموبايل", _e(order.get("customer_mobile"))),
        ("النوع", f"{_e(order.get('garment_type'))} × {order.get('quantity', 1)}"),
        ("القماش", f"{FABRIC_SOURCES.get(order.get('fabric_source'), '')} — {_e(order.get('fabric_desc'))}"),
        ("ميعاد البروفة", _e(iso_to_display(order.get("fitting_date")))),
        ("ميعاد التسليم", _e(iso_to_display(order.get("due_date")))),
        ("السعر الإجمالى", money(order.get("price"))),
        ("المدفوع", money(paid)),
        ("المتبقى", f'<span style="font-size:14pt;">{money(num(order.get("price")) - paid)}</span>'),
    ]
    note = company.get("receipt_note")
    body = _header(company, logo, "إيصال استلام طلب تفصيل") + _kv_table(rows)
    if order.get("notes"):
        body += f"<p><b>ملاحظات:</b> {_e(order['notes'])}</p>"
    if note:
        body += f'<p style="color:#444;">{_e(note)}</p>'
    body += '<br><table width="100%" dir="rtl"><tr><td>توقيع العميل: ................</td>' \
            '<td align="left">توقيع المحل: ................</td></tr></table>'
    return _doc(body)


def workshop_ticket_html(order, company):
    style = order.get("style") or {}
    style_rows = "".join(f"<li>{_e(k)}: <b>{_e(v)}</b></li>" for k, v in style.items())
    body = f"""
    <table width="100%" dir="rtl"><tr>
      <td><span style="font-size:24pt; font-weight:bold;">طلب #{order['id']}</span></td>
      <td align="left"><b>{_e(company.get('name'))}</b><br>ورقة شغل المصنع</td>
    </tr></table><hr>
    """ + _kv_table([
        ("العميل", _e(order.get("customer_name"))),
        ("النوع", f"{_e(order.get('garment_type'))} × {order.get('quantity', 1)}"),
        ("القماش", f"{FABRIC_SOURCES.get(order.get('fabric_source'), '')} — {_e(order.get('fabric_desc'))}"),
        ("ميعاد البروفة", _e(iso_to_display(order.get("fitting_date")))),
        ("ميعاد التسليم", f'<span style="font-size:13pt;">{_e(iso_to_display(order.get("due_date")))}</span>'),
        ("بروفة؟", "أيوه" if order.get("needs_fitting") else "لأ — من غير بروفة"),
    ]) + "<h3>📏 المقاسات</h3>" + _measurements_html(order.get("measurements")) + \
        (f"<h3>✂️ تفاصيل الموديل</h3><ul>{style_rows}</ul>" if style_rows else "") + \
        (f"<h3>📝 ملاحظات</h3><p style='font-size:12pt;'>{_e(order.get('notes'))}</p>" if order.get("notes") else "") + \
        '<br><table width="100%" border="1" cellspacing="0" cellpadding="8" dir="rtl" style="border-collapse:collapse;">' \
        '<tr><td>القص: ..........</td><td>الخياطة: ..........</td><td>البروفة: ..........</td>' \
        '<td>التشطيب: ..........</td></tr></table>'
    return _doc(body)


def sale_receipt_html(sale, company, logo=None):
    items = "".join(
        f"<tr><td>{_e(i.get('name'))} {_e(i.get('size') or '')} {_e(i.get('color') or '')}</td>"
        f"<td align='center'>{i['qty']}</td><td align='center'>{money(i['price'])}</td>"
        f"<td align='center'>{money(i['qty'] * num(i['price']))}</td></tr>" for i in sale.get("items", []))
    body = _header(company, logo, f"فاتورة بيع رقم #{sale['id']}") + f"""
    <p>التاريخ: {_e(iso_to_display(sale.get('created_at')))} — العميل: {_e(sale.get('customer_name'))}</p>
    <table width="100%" border="1" cellspacing="0" cellpadding="5" dir="rtl" style="border-collapse:collapse;">
      <tr style="background:#eee;"><th>الصنف</th><th>العدد</th><th>السعر</th><th>الإجمالى</th></tr>
      {items}
      <tr><td colspan="3"><b>الإجمالى</b></td><td align="center"><b>{money(sale.get('total'))}</b></td></tr>
    </table>
    """
    if company.get("receipt_note"):
        body += f'<p style="color:#444;">{_e(company["receipt_note"])}</p>'
    return _doc(body)


def preview(parent, html_text, title="طباعة"):
    doc = QTextDocument()
    doc.setHtml(html_text)
    printer = QPrinter(QPrinter.HighResolution)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle(title)
    dialog.paintRequested.connect(lambda p: doc.print_(p))
    dialog.resize(900, 900)
    dialog.exec()
