"""تصدير تقرير Excel موحّد (RTL، قابل للفرز والتصفية، بألوان الحالات)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

import xlsxwriter

from . import APP_NAME
from .engine import (ALL_STATUSES, BRIDGE_ORDER, SRC_A, SRC_B, STATUS_DIFF, STATUS_DUP,
                     STATUS_MATCHED, STATUS_MISSING_A, STATUS_MISSING_B, STATUS_POSSIBLE,
                     MatchRow, ReconResult)
from .loader import RawTable, SkippedRow
from .normalize import q2

STATUS_COLORS = {
    STATUS_MATCHED: ("#E3F5EA", "#14693A"),
    STATUS_DIFF: ("#FFF1CF", "#8A5A00"),
    STATUS_POSSIBLE: ("#E0EBFF", "#1F4FAE"),
    STATUS_MISSING_B: ("#FDE3E1", "#A1261C"),
    STATUS_MISSING_A: ("#FDE3E1", "#A1261C"),
    STATUS_DUP: ("#EDE2FA", "#6B2FB3"),
}
NAVY = "#14213D"
ACCENT = "#2A6F97"
GRID = "#D5DBE3"


def _f(d) -> Optional[float]:
    if d is None:
        return None
    return float(q2(Decimal(d)))


def export_report(path: str, res: ReconResult, table_a: Optional[RawTable] = None,
                  table_b: Optional[RawTable] = None, skipped: Optional[list[SkippedRow]] = None,
                  file_names: tuple[str, str] = ("", "")) -> str:
    skipped = skipped or []
    wb = xlsxwriter.Workbook(path, {"default_date_format": "yyyy-mm-dd"})
    wb.set_properties({"title": "تقرير المطابقة والتسوية المالية", "author": APP_NAME,
                       "comments": "تم إنشاؤه آلياً"})

    base = {"font_name": "Segoe UI", "font_size": 10, "valign": "vcenter", "reading_order": 2}
    fmt = lambda **kw: wb.add_format({**base, **kw})
    F = {
        "title": fmt(bold=True, font_size=18, font_color=NAVY),
        "sub": fmt(font_size=10, font_color="#5B6472"),
        "h": fmt(bold=True, font_color="#FFFFFF", bg_color=NAVY, align="center", border=1,
                 border_color=GRID, text_wrap=True),
        "h2": fmt(bold=True, font_color="#FFFFFF", bg_color=ACCENT, align="center", border=1,
                  border_color=GRID, text_wrap=True),
        "sec": fmt(bold=True, font_size=12, font_color=NAVY, bottom=2, bottom_color=ACCENT),
        "t": fmt(border=1, border_color=GRID),
        "tw": fmt(border=1, border_color=GRID, text_wrap=True, valign="top"),
        "tc": fmt(border=1, border_color=GRID, align="center"),
        "n": fmt(border=1, border_color=GRID, num_format="#,##0.00;[Red]-#,##0.00"),
        "nb": fmt(border=1, border_color=GRID, num_format="#,##0.00;[Red]-#,##0.00", bold=True,
                  bg_color="#F2F5F9"),
        "int": fmt(border=1, border_color=GRID, num_format="#,##0", align="center"),
        "intb": fmt(border=1, border_color=GRID, num_format="#,##0", align="center", bold=True,
                    bg_color="#F2F5F9"),
        "pct": fmt(border=1, border_color=GRID, num_format="0.0%", align="center", bold=True),
        "d": fmt(border=1, border_color=GRID, num_format="yyyy-mm-dd", align="center"),
        "lbl": fmt(border=1, border_color=GRID, bold=True, bg_color="#F2F5F9"),
        "ok": fmt(bold=True, font_color="#14693A", bg_color="#E3F5EA", border=1, border_color=GRID),
        "bad": fmt(bold=True, font_color="#A1261C", bg_color="#FDE3E1", border=1, border_color=GRID),
        "edit": fmt(border=1, border_color=GRID, bg_color="#FFFBEA", text_wrap=True),
        "grp": fmt(bold=True, align="center", font_color=NAVY, bg_color="#DCE6F2", border=1,
                   border_color=GRID),
    }
    st_fmt = {s: fmt(bold=True, align="center", border=1, border_color=GRID,
                     bg_color=bg, font_color=fg) for s, (bg, fg) in STATUS_COLORS.items()}
    prio_fmt = {
        "عالية": fmt(bold=True, align="center", border=1, border_color=GRID, font_color="#A1261C"),
        "متوسطة": fmt(bold=True, align="center", border=1, border_color=GRID, font_color="#8A5A00"),
        "منخفضة": fmt(align="center", border=1, border_color=GRID, font_color="#14693A"),
        "—": fmt(align="center", border=1, border_color=GRID, font_color="#98A1AE"),
    }

    S_SUM, S_MATCH, S_DIFF, S_REV = "الملخص", "جدول المطابقة", "جدول الفروقات", "للمراجعة"
    S_A, S_B = "بيانات المحاسب", "بيانات الصرافة"
    ws_sum = wb.add_worksheet(S_SUM)
    ws_m = wb.add_worksheet(S_MATCH)
    ws_d = wb.add_worksheet(S_DIFF)
    ws_r = wb.add_worksheet(S_REV)
    ws_a = wb.add_worksheet(S_A) if table_a else None
    ws_b = wb.add_worksheet(S_B) if table_b else None
    for w in (ws_sum, ws_m, ws_d, ws_r, ws_a, ws_b):
        if w:
            w.right_to_left()
            w.hide_gridlines(2)
    ws_sum.set_tab_color(NAVY)
    ws_m.set_tab_color(ACCENT)
    ws_d.set_tab_color("#E09F3E")
    ws_r.set_tab_color("#C0392B")

    rows = res.rows
    q = lambda s: "'" + s + "'"

    # =================================================================== جدول المطابقة
    headers = ["#", "الحالة", "الأولوية", "طريقة المطابقة", "الثقة %", "المصدر",
               "صف المحاسب", "مرجع المحاسب", "تاريخ المحاسب", "اسم (المحاسب)", "عملة المحاسب", "مبلغ المحاسب",
               "صف الصرافة", "مرجع الصرافة", "تاريخ الصرافة", "اسم (الصرافة)", "عملة الصرافة", "مبلغ الصرافة",
               "الفرق (محاسب − صرافة)", "التفسير", "الإجراء المقترح", "قرار المراجع", "ملاحظات المراجع"]
    widths = [6, 18, 9, 16, 8, 10, 9, 15, 12, 20, 9, 14, 9, 15, 12, 20, 9, 14, 16, 58, 52, 14, 30]
    ws_m.write(0, 0, "جدول المطابقة التفصيلي", F["title"])
    ws_m.write(1, 0, "كل عملية مع مصدرها ونتيجة مطابقتها — استخدم أزرار التصفية في العناوين للفرز والبحث.", F["sub"])
    HR = 3
    ws_m.merge_range(HR - 1, 6, HR - 1, 11, "ملف المحاسب", F["grp"])
    ws_m.merge_range(HR - 1, 12, HR - 1, 17, "ملف الصرافة", F["grp"])
    for j, h in enumerate(headers):
        ws_m.write(HR, j, h, F["h"])
        ws_m.set_column(j, j, widths[j])
    ws_m.set_row(HR, 32)
    for i, r in enumerate(rows):
        x = HR + 1 + i
        a, b = r.a, r.b
        ws_m.write_number(x, 0, r.id, F["int"])
        ws_m.write(x, 1, r.status, st_fmt[r.status])
        ws_m.write(x, 2, r.priority, prio_fmt.get(r.priority, F["tc"]))
        ws_m.write(x, 3, r.method, F["tc"])
        ws_m.write_number(x, 4, r.confidence, F["int"])
        ws_m.write(x, 5, r.source, F["tc"])
        ws_m.write(x, 6, a.row if a else "", F["int"])
        ws_m.write(x, 7, a.ref if a else "", F["tc"])
        if a and a.date:
            ws_m.write_datetime(x, 8, datetime.combine(a.date, datetime.min.time()), F["d"])
        else:
            ws_m.write(x, 8, "", F["d"])
        ws_m.write(x, 9, a.party if a else "", F["t"])
        ws_m.write(x, 10, r.cur_a if a else "", F["tc"])
        ws_m.write(x, 11, _f(a.amount) if a else "", F["n"])
        ws_m.write(x, 12, b.row if b else "", F["int"])
        ws_m.write(x, 13, b.ref if b else "", F["tc"])
        if b and b.date:
            ws_m.write_datetime(x, 14, datetime.combine(b.date, datetime.min.time()), F["d"])
        else:
            ws_m.write(x, 14, "", F["d"])
        ws_m.write(x, 15, b.party if b else "", F["t"])
        ws_m.write(x, 16, r.cur_b if b else "", F["tc"])
        ws_m.write(x, 17, _f(b.amount) if b else "", F["n"])
        ws_m.write_number(x, 18, _f(r.diff), F["nb"])
        ws_m.write(x, 19, r.reason_text, F["tw"])
        ws_m.write(x, 20, r.action, F["tw"])
        ws_m.write(x, 21, r.decision, F["edit"])
        ws_m.write(x, 22, r.note, F["edit"])
    last = HR + len(rows)
    if rows:
        ws_m.autofilter(HR, 0, last, len(headers) - 1)
        ws_m.data_validation(HR + 1, 21, last, 21,
                             {"validate": "list", "source": ["معتمد", "مرفوض", "قيد المراجعة"]})
    ws_m.freeze_panes(HR + 1, 2)
    ws_m.set_landscape()
    ws_m.fit_to_pages(1, 0)
    ws_m.repeat_rows(HR)

    # =================================================================== جدول الفروقات
    ws_d.write(0, 0, "جدول الفروقات المالية", F["title"])
    ws_d.write(1, 0, "كل فرق مالي مع فئته. مجموع هذا الجدول لكل عملة = إجمالي المحاسب − إجمالي الصرافة.", F["sub"])
    dh = ["#", "الحالة", "المرجع", "العملة", "مبلغ المحاسب", "مبلغ الصرافة", "قيمة الفرق", "فئة الفرق", "التفسير"]
    dw = [6, 18, 16, 9, 15, 15, 15, 38, 70]
    DHR = 3
    for j, h in enumerate(dh):
        ws_d.write(DHR, j, h, F["h"])
        ws_d.set_column(j, j, dw[j])
    x = DHR + 1
    for r in rows:
        for cur, cat, amt in r.contribs:
            if amt == 0:
                continue
            ws_d.write_number(x, 0, r.id, F["int"])
            ws_d.write(x, 1, r.status, st_fmt[r.status])
            ws_d.write(x, 2, r.ref, F["tc"])
            ws_d.write(x, 3, cur, F["tc"])
            ws_d.write(x, 4, _f(r.amt_a) if r.amt_a is not None else "", F["n"])
            ws_d.write(x, 5, _f(r.amt_b) if r.amt_b is not None else "", F["n"])
            ws_d.write_number(x, 6, _f(amt), F["nb"])
            ws_d.write(x, 7, cat, F["t"])
            ws_d.write(x, 8, r.reason_text, F["tw"])
            x += 1
    if x > DHR + 1:
        ws_d.autofilter(DHR, 0, x - 1, len(dh) - 1)
    ws_d.freeze_panes(DHR + 1, 0)
    d_last = x - 1

    # =================================================================== للمراجعة
    ws_r.write(0, 0, "العمليات التي تحتاج إلى مراجعة", F["title"])
    ws_r.write(1, 0, "مرتبة حسب الأولوية. سجّل قرارك وملاحظتك في الأعمدة الصفراء.", F["sub"])
    rh = ["#", "الأولوية", "الحالة", "المصدر", "المرجع", "العملة", "قيمة الفرق", "ما المشكلة؟", "الإجراء المقترح",
          "قرار المراجع", "ملاحظات المراجع"]
    rw = [6, 10, 18, 10, 16, 9, 15, 62, 52, 14, 30]
    RHR = 3
    for j, h in enumerate(rh):
        ws_r.write(RHR, j, h, F["h"])
        ws_r.set_column(j, j, rw[j])
    prio_rank = {"عالية": 0, "متوسطة": 1, "منخفضة": 2}
    review = [r for r in rows if r.status != STATUS_MATCHED or r.priority == "منخفضة"]
    review.sort(key=lambda r: (prio_rank.get(r.priority, 3), -abs(r.diff)))
    for i, r in enumerate(review):
        x = RHR + 1 + i
        ws_r.write_number(x, 0, r.id, F["int"])
        ws_r.write(x, 1, r.priority, prio_fmt.get(r.priority, F["tc"]))
        ws_r.write(x, 2, r.status, st_fmt[r.status])
        ws_r.write(x, 3, r.source, F["tc"])
        ws_r.write(x, 4, r.ref, F["tc"])
        ws_r.write(x, 5, r.currency, F["tc"])
        ws_r.write_number(x, 6, _f(r.diff), F["nb"])
        ws_r.write(x, 7, r.reason_text, F["tw"])
        ws_r.write(x, 8, r.action, F["tw"])
        ws_r.write(x, 9, r.decision, F["edit"])
        ws_r.write(x, 10, r.note, F["edit"])
    if review:
        ws_r.autofilter(RHR, 0, RHR + len(review), len(rh) - 1)
        ws_r.data_validation(RHR + 1, 9, RHR + len(review), 9,
                             {"validate": "list", "source": ["معتمد", "مرفوض", "قيد المراجعة"]})
    ws_r.freeze_panes(RHR + 1, 0)

    # =================================================================== بيانات المصدر مع النتيجة
    by_a = {r.a.row: r for r in rows if r.a}
    by_b = {r.b.row: r for r in rows if r.b}

    def write_source(ws, table: RawTable, lookup, skipped_rows, side_title):
        ws.write(0, 0, side_title, F["title"])
        ws.write(1, 0, f"الملف: {table.name} — ورقة: {table.sheet}. العمودان الأولان يوضحان نتيجة مطابقة كل صف.", F["sub"])
        hh = ["نتيجة المطابقة", "# في جدول المطابقة"] + table.columns
        HR2 = 3
        for j, h in enumerate(hh):
            ws.write(HR2, j, h, F["h2"] if j < 2 else F["h"])
            ws.set_column(j, j, 20 if j < 2 else max(12, min(32, len(str(h)) + 6)))
        sk = {s.row: s for s in skipped_rows}
        for i, (xl_row, vals) in enumerate(table.rows):
            x = HR2 + 1 + i
            r = lookup.get(xl_row)
            if r:
                ws.write(x, 0, r.status, st_fmt[r.status])
                ws.write_number(x, 1, r.id, F["int"])
            else:
                ws.write(x, 0, "مُهمل: " + sk[xl_row].reason if xl_row in sk else "—", F["t"])
                ws.write(x, 1, "", F["t"])
            for j, v in enumerate(vals):
                if hasattr(v, "year"):
                    ws.write_datetime(x, j + 2, datetime.combine(v, datetime.min.time())
                                      if not isinstance(v, datetime) else v, F["d"])
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    ws.write_number(x, j + 2, v, F["n"] if isinstance(v, float) else F["t"])
                else:
                    ws.write(x, j + 2, "" if v is None else str(v), F["t"])
        ws.autofilter(HR2, 0, HR2 + len(table.rows), len(hh) - 1)
        ws.freeze_panes(HR2 + 1, 2)

    if table_a:
        write_source(ws_a, table_a, by_a, [s for s in skipped if s.side == "A"], "بيانات ملف المحاسب مع نتيجة المطابقة")
    if table_b:
        write_source(ws_b, table_b, by_b, [s for s in skipped if s.side == "B"], "بيانات ملف الصرافة مع نتيجة المطابقة")

    # =================================================================== الملخص
    ws = ws_sum
    ws.set_column(0, 0, 3)
    ws.set_column(1, 1, 46)
    ws.set_column(2, 8, 17)
    ws.write(0, 1, "تقرير المطابقة والتسوية المالية", F["title"])
    ws.write(1, 1, f"أُنشئ في {datetime.now():%Y-%m-%d %H:%M}  ·  {APP_NAME}", F["sub"])
    ws.set_row(0, 30)

    r0 = 3
    ws.write(r0, 1, "الملفات", F["sec"])
    info = [("ملف المحاسب", file_names[0] or (table_a.name if table_a else "")),
            ("ملف الصرافة", file_names[1] or (table_b.name if table_b else "")),
            ("عدد عمليات المحاسب", res.count_a), ("عدد عمليات الصرافة", res.count_b),
            ("فترة المحاسب", _rng(res.range_a)), ("فترة الصرافة", _rng(res.range_b)),
            ("اتجاه الإشارات", res.rel_note)]
    for i, (k, v) in enumerate(info, 1):
        ws.write(r0 + i, 1, k, F["lbl"])
        if isinstance(v, int):
            ws.write_number(r0 + i, 2, v, F["intb"])
        else:
            ws.merge_range(r0 + i, 2, r0 + i, 6, str(v), F["t"])

    r1 = r0 + len(info) + 2
    ws.write(r1, 1, "نتائج المطابقة", F["sec"])
    ws.write(r1 + 1, 1, "الحالة", F["h"])
    ws.write(r1 + 1, 2, "العدد", F["h"])
    ws.write(r1 + 1, 3, "النسبة من الأكبر", F["h"])
    denom = max(res.count_a, res.count_b, 1)
    status_rng = f"{q(S_MATCH)}!$B${HR + 2}:$B${max(last + 1, HR + 2)}"
    for i, s in enumerate(ALL_STATUSES):
        rr = r1 + 2 + i
        ws.write(rr, 1, s, st_fmt[s])
        ws.write_formula(rr, 2, f"=COUNTIF({status_rng},B{rr + 1})", F["intb"], res.counts.get(s, 0))
        ws.write_formula(rr, 3, f"=C{rr + 1}/{denom}", F["pct"], res.counts.get(s, 0) / denom)
    rr = r1 + 2 + len(ALL_STATUSES)
    ws.write(rr, 1, "إجمالي الصفوف في جدول المطابقة", F["lbl"])
    ws.write_formula(rr, 2, f"=SUM(C{r1 + 3}:C{rr})", F["intb"], len(rows))
    chart_status_first = r1 + 2

    # الفروقات والجسر الحسابي لكل عملة
    r2 = rr + 3
    ws.write(r2, 1, "الفروقات المالية وتحليلها (لكل عملة)", F["sec"])
    cur_list = res.currencies or [""]
    ws.write(r2 + 1, 1, "البند", F["h"])
    for j, c in enumerate(cur_list):
        ws.write(r2 + 1, 2 + j, c or "غير محدد", F["h"])
    lines = [("إجمالي ملف المحاسب", lambda c: res.total_a.get(c, Decimal(0))),
             ("إجمالي ملف الصرافة (بعد مواءمة الإشارة)", lambda c: res.total_b.get(c, Decimal(0))),
             ("الفرق الصافي (محاسب − صرافة)", lambda c: res.net_diff(c))]
    row_ix = r2 + 2
    for name, fn in lines:
        bold = name.startswith("الفرق")
        ws.write(row_ix, 1, name, F["lbl"] if not bold else F["lbl"])
        for j, c in enumerate(cur_list):
            ws.write_number(row_ix, 2 + j, _f(fn(c)), F["nb"] if bold else F["n"])
        row_ix += 1
    row_ix += 1
    ws.write(row_ix, 1, "تحليل الفرق الصافي حسب السبب", F["h2"])
    for j, c in enumerate(cur_list):
        ws.write(row_ix, 2 + j, c or "غير محدد", F["h2"])
    row_ix += 1
    bridge_first = row_ix
    for cat in BRIDGE_ORDER:
        if not any(cat in res.bridge.get(c, {}) for c in cur_list):
            continue
        ws.write(row_ix, 1, cat, F["t"])
        for j, c in enumerate(cur_list):
            ws.write_number(row_ix, 2 + j, _f(res.bridge.get(c, {}).get(cat, Decimal(0))), F["n"])
        row_ix += 1
    bridge_last = row_ix - 1
    ws.write(row_ix, 1, "مجموع الأسباب", F["lbl"])
    for j, c in enumerate(cur_list):
        col = chr(ord("C") + j)
        ws.write_formula(row_ix, 2 + j, f"=SUM({col}{bridge_first + 1}:{col}{bridge_last + 1})", F["nb"],
                         _f(sum(res.bridge.get(c, {}).values(), Decimal(0))))
    row_ix += 1
    ws.write(row_ix, 1, "التحقق الحسابي (يجب أن يساوي صفراً)", F["lbl"])
    for j, c in enumerate(cur_list):
        okv = res.integrity.get(c, Decimal(0)) == 0
        ws.write(row_ix, 2 + j, "✔ مغلق" if okv else f"✖ فرق {res.integrity.get(c)}",
                 F["ok"] if okv else F["bad"])
    row_ix += 2

    if res.warnings or skipped:
        ws.write(row_ix, 1, "ملاحظات", F["sec"])
        row_ix += 1
        for w in res.warnings:
            ws.merge_range(row_ix, 1, row_ix, 6, "• " + w, F["tw"])
            row_ix += 1
        if skipped:
            ws.merge_range(row_ix, 1, row_ix, 6,
                           f"• تم إهمال {len(skipped)} صفاً (إجماليات/بلا مبلغ) ولم تدخل في المطابقة — تظهر في ورقتي البيانات.",
                           F["tw"])
            row_ix += 1
        row_ix += 1

    ws.write(row_ix, 1, "الإعدادات المستخدمة", F["sec"])
    S = res.settings
    cfg = [("تسامح المبلغ", f"{S.amount_tol}"), ("تسامح التاريخ (بالمرجع)", f"{S.date_tol_days} يوم"),
           ("نافذة التاريخ للمطابقة الذكية", f"{S.fuzzy_days} يوم"),
           ("أعلى نسبة فرق للمطابقة المحتملة", f"{S.possible_pct * 100:.1f}%"),
           ("المطابقة الذكية", "مفعّلة" if S.use_fuzzy else "معطّلة"),
           ("صرامة العملة", "مفعّلة" if S.strict_currency else "معطّلة")]
    for i, (k, v) in enumerate(cfg, 1):
        ws.write(row_ix + i, 1, k, F["lbl"])
        ws.write(row_ix + i, 2, v, F["t"])

    # رسوم بيانية
    ch = wb.add_chart({"type": "doughnut"})
    ch.add_series({
        "name": "نتائج المطابقة",
        "categories": [S_SUM, chart_status_first, 1, chart_status_first + len(ALL_STATUSES) - 1, 1],
        "values": [S_SUM, chart_status_first, 2, chart_status_first + len(ALL_STATUSES) - 1, 2],
        "points": [{"fill": {"color": c}} for c in
                   ("#2E9E5B", "#E6A100", "#3B7DDD", "#D64535", "#B2362B", "#8E4FD1")],
        "data_labels": {"value": True},
    })
    ch.set_title({"name": "توزيع نتائج المطابقة", "name_font": {"size": 12}})
    ch.set_legend({"position": "bottom"})
    ch.set_size({"width": 430, "height": 320})
    ws.insert_chart(r0, 8, ch)

    if bridge_last >= bridge_first:
        bc = wb.add_chart({"type": "bar"})
        for j, c in enumerate(cur_list):
            bc.add_series({
                "name": c or "غير محدد",
                "categories": [S_SUM, bridge_first, 1, bridge_last, 1],
                "values": [S_SUM, bridge_first, 2 + j, bridge_last, 2 + j],
            })
        bc.set_title({"name": "أسباب الفرق الصافي", "name_font": {"size": 12}})
        bc.set_legend({"position": "bottom"})
        bc.set_size({"width": 430, "height": 320})
        ws.insert_chart(r0 + 17, 8, bc)

    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.activate()
    wb.close()
    return path


def _rng(rg) -> str:
    lo, hi = rg
    return f"{lo:%Y-%m-%d} → {hi:%Y-%m-%d}" if lo and hi else "غير متوفرة"
