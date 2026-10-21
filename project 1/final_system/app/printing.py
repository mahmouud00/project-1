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


def _tr(*cells, style=""):
    """صف جدول من اليمين للشمال. Qt بيرسم أعمدة الجداول من الشمال لليمين حتى مع dir="rtl"،
    فبنكتب الخلايا بالعكس عشان أول خلية تطلع على اليمين."""
    return f"<tr{f' style={chr(34)}{style}{chr(34)}' if style else ''}>{''.join(reversed(cells))}</tr>"


def _header(company, logo, title):
    logo_html = ""
    if logo:
        mime = "image/png" if logo[:4] == b"\x89PNG" else "image/jpeg"
        logo_html = f'<img src="data:{mime};base64,{base64.b64encode(logo).decode()}" height="70">'
    contact = " — ".join(_e(x) for x in (company.get("phone"), company.get("address")) if x)
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" dir="rtl">{_tr(
        f'<td align="right" valign="middle"><span style="font-size:18pt; font-weight:bold;">'
        f'{_e(company.get("name"))}</span><br><span style="color:#555;">{contact}</span></td>',
        f'<td align="left" valign="middle">{logo_html}</td>')}</table>
    <hr>
    <p align="center" style="font-size:15pt; font-weight:bold;">{title}</p>
    """


def _doc(body):
    return f"""<html dir="rtl"><body dir="rtl" style="font-family: 'Segoe UI', Tahoma, Arial; font-size: 11pt;">
    {body}
    <p style="color:#888; font-size:8pt;" align="center">اتطبع {datetime.now():%d/%m/%Y %H:%M}</p>
    </body></html>"""


def _kv_table(rows, width="100%"):
    cells = "".join(_tr(f'<td style="color:#555;" width="30%">{_e(k)}</td>', f'<td><b>{v}</b></td>') for k, v in rows)
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
        cells = [f'<td align="center" style="padding:4px;"><span style="color:#555;">{_e(n)}</span><br>'
                 f'<b style="font-size:14pt;">{_e(v)}</b></td>' for n, v in items]
        out.append(f'<p style="font-weight:bold; margin-bottom:2px;">{_e(grp)}</p>'
                   f'<table width="100%" border="1" cellspacing="0" cellpadding="2" dir="rtl" '
                   f'style="border-collapse:collapse;">'
                   f'{_tr(*cells)}</table>')
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
    body += '<br><table width="100%" dir="rtl">' + _tr('<td align="right">توقيع العميل: ................</td>',
                                                      '<td align="left">توقيع المحل: ................</td>') + '</table>'
    return _doc(body)


# مراحل التصنيع بالترتيب: (المرحلة، عمود الوقت فى الطلب، كلمات بتميّز حدث المرحلة فى السجل)
PRODUCTION_STAGES = [
    ("استلام الطلب", "created_at", ("طلب جديد",)),
    ("تأكيد العربون", "deposit_confirmed_at", ("تأكيد العربون",)),
    ("القص", "cut_at", ("تم القص",)),
    ("الخياطة", "sewn_at", ("تم الخياطة",)),
    ("البروفة", "fitted_at", ("البروفة",)),
    ("التشطيب والكى", "finished_at", ("تم التشطيب",)),
    ("التسليم للعميل", "delivered_at", ("اتسلّم للعميل",)),
]


def _time(value):
    """'2026-10-21 18:25:03' ← '21/10/2026  6:25 م'."""
    try:
        d = datetime.strptime(str(value)[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return _e(value)
    hour = d.hour % 12 or 12
    return f"{d:%d/%m/%Y}&nbsp;&nbsp;{hour}:{d:%M} {'م' if d.hour >= 12 else 'ص'}"


def production_rows(order):
    """كل مرحلة خلصت إمتى ومين عملها (من سجل الطلب). البروفة لو اتعادت بتظهر كل مرة.
    المراحل اللى لسه مخلصتش بتظهر فاضية عشان تتكتب بالقلم."""
    events = order.get("events") or []
    done, pending = [], []
    for title, stamp, keys in PRODUCTION_STAGES:
        if title == "البروفة" and not order.get("needs_fitting"):
            continue
        matched = [e for e in events if any(k in e.get("action", "") for k in keys)]
        if matched:
            for e in matched:
                label = title if title != "البروفة" else (
                    "البروفة — تمام" if "تمام" in e["action"] else "البروفة — محتاجة تعديل")
                details = "" if stamp == "created_at" else (e.get("details") or "")   # من غير أسعار للمصنع
                done.append((e["created_at"], e["id"], label, details, e.get("user_name") or ""))
        elif order.get(stamp):
            done.append((order[stamp], 0, title, "", ""))
        else:
            pending.append((title, "", "", "", False))
    done.sort(key=lambda r: (str(r[0]), r[1]))      # بالترتيب اللى حصل (البروفة المتعادة فى مكانها)
    return [(label, _time(when), _e(details) if details else "", _e(user) if user else "", True)
            for when, _id, label, details, user in done] + pending


def _production_html(order):
    head = _tr('<th width="20%">المرحلة</th>', '<th width="22%">خلصت إمتى</th>', '<th>مين عملها / تفاصيل</th>',
               '<th width="15%">سجّلها</th>', style="background:#eee;")
    body = []
    for title, when, details, user, done in production_rows(order):
        if done:
            body.append(_tr(f"<td><b>✔ {title}</b></td>", f"<td align='center'>{when}</td>", f"<td>{details}</td>",
                            f"<td>{user}</td>"))
        else:
            body.append(_tr(f"<td style='color:#666;'>☐ {title}</td>", "<td align='center'>...../...../........</td>",
                            "<td>..............................</td>", "<td></td>"))
    return ('<table width="100%" border="1" cellspacing="0" cellpadding="6" dir="rtl" '
            f'style="border-collapse:collapse;">{head}{"".join(body)}</table>')


def workshop_ticket_html(order, company):
    style = order.get("style") or {}
    style_rows = "".join(_tr(f"<td style='color:#555;' width='30%'>{_e(k)}</td>", f"<td><b>{_e(v)}</b></td>")
                         for k, v in style.items())
    body = f"""
    <p align="center" style="font-size:22pt; font-weight:bold; margin:0;">طلب رقم {order['id']}</p>
    <p align="center" style="margin:0;"><b>{_e(company.get('name'))}</b> — ورقة شغل المصنع</p><hr>
    """ + _kv_table([
        ("العميل", _e(order.get("customer_name"))),
        ("النوع", f"{_e(order.get('garment_type'))} × {order.get('quantity', 1)}"),
        ("القماش", f"{FABRIC_SOURCES.get(order.get('fabric_source'), '')} — {_e(order.get('fabric_desc'))}"),
        ("ميعاد البروفة", _e(iso_to_display(order.get("fitting_date")))),
        ("ميعاد التسليم", f'<span style="font-size:13pt;">{_e(iso_to_display(order.get("due_date")))}</span>'),
        ("بروفة؟", "أيوه" if order.get("needs_fitting") else "لأ — من غير بروفة"),
    ]) + "<h3>📏 المقاسات</h3>" + _measurements_html(order.get("measurements")) + \
        (f"<h3>✂️ تفاصيل الموديل</h3><table width='100%' border='1' cellspacing='0' cellpadding='4' dir='rtl' "
         f"style='border-collapse:collapse;'>{style_rows}</table>" if style_rows else "") + \
        (f"<h3>📝 ملاحظات</h3><p style='font-size:12pt;'>{_e(order.get('notes'))}</p>" if order.get("notes") else "") + \
        (f"<p><b>📌 ملاحظة المتابعة:</b> {_e(order.get('note'))}</p>" if order.get("note") else "") + \
        "<h3>🧵 مراحل التصنيع</h3>" + _production_html(order)
    return _doc(body)


def sale_receipt_html(sale, company, logo=None):
    items = "".join(_tr(
        f"<td>{_e(i.get('name'))} {_e(i.get('size') or '')} {_e(i.get('color') or '')}</td>",
        f"<td align='center'>{i['qty']}</td>", f"<td align='center'>{money(i['price'])}</td>",
        f"<td align='center'>{money(i['qty'] * num(i['price']))}</td>") for i in sale.get("items", []))
    body = _header(company, logo, f"فاتورة بيع رقم #{sale['id']}") + f"""
    <p>التاريخ: {_e(iso_to_display(sale.get('created_at')))} — العميل: {_e(sale.get('customer_name'))}</p>
    <table width="100%" border="1" cellspacing="0" cellpadding="5" dir="rtl" style="border-collapse:collapse;">
      {_tr("<th>الصنف</th>", "<th>العدد</th>", "<th>السعر</th>", "<th>الإجمالى</th>", style="background:#eee;")}
      {items}
      {_tr('<td colspan="3"><b>الإجمالى</b></td>', f'<td align="center"><b>{money(sale.get("total"))}</b></td>')}
    </table>
    """
    if company.get("receipt_note"):
        body += f'<p style="color:#444;">{_e(company["receipt_note"])}</p>'
    return _doc(body)


def preview(parent, html_text, title="طباعة"):
    doc = QTextDocument()
    # الورق أبيض دايمًا: الكلام أسود حتى لو البرنامج على الوضع الداكن
    doc.setDefaultStyleSheet("body, p, td, th, span, li, h3, b { color: #000000; }")
    doc.setHtml(html_text)
    printer = QPrinter(QPrinter.HighResolution)
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle(title)
    dialog.paintRequested.connect(lambda p: doc.print_(p))
    dialog.resize(900, 900)
    dialog.exec()
