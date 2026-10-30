"""مولّد بيانات تجريبية: ملف المحاسب وملف الصرافة بسيناريوهات متنوعة.

الاستخدام:  python tools/make_sample.py [مجلد_الإخراج]
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

NAMES = ["محمد علي الحداد", "أحمد صالح الشرعبي", "عبدالله ناصر القاضي", "خالد يحيى المقطري",
         "سعيد عمر باوزير", "فهد حسن العولقي", "نبيل أحمد السقاف", "ياسر محمد الزبيدي",
         "علي عبدالرحمن الكاف", "وليد صادق الأهدل", "منير قاسم العمري", "هشام جميل البكري"]
CURS = ["SAR", "USD", "YER"]


def make(out_dir: str, n: int = 60, seed: int = 7) -> tuple[str, str]:
    rnd = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = date(2026, 9, 1)

    ops = []
    for i in range(n):
        ops.append(dict(
            ref=str(70000000 + rnd.randint(1000, 999999)),
            d=base + timedelta(days=rnd.randint(0, 27)),
            amt=round(rnd.choice([500, 1000, 1500, 2500, 4000, 7500, 12000, 25000]) + rnd.randint(0, 99) * 1.0, 2),
            cur=rnd.choices(CURS, [6, 3, 1])[0],
            name=rnd.choice(NAMES),
            fee=rnd.choice([0, 0, 5, 10, 15]),
        ))

    A, B = [], []  # (ref, date, debit, credit, cur, name, desc, voucher)
    for k, o in enumerate(ops):
        a = dict(ref=o["ref"], d=o["d"], amt=o["amt"], cur=o["cur"], name=o["name"],
                 desc=f"حوالة صادرة إلى {o['name']}", v=f"V-{1000 + k}")
        b = dict(ref=o["ref"], d=o["d"], amt=o["amt"], cur=o["cur"], name=o["name"], fee=o["fee"])
        A.append(a)
        B.append(b)

    # ---- سيناريوهات مقصودة ----
    # 1) مفقودة في الصرافة (عند المحاسب فقط)
    for idx in (3, 17):
        B[idx] = None
    # 2) مفقودة في ملف المحاسب
    for idx in (8, 31):
        A[idx] = None
    # 3) فرق مبلغ بسبب الرسوم
    for idx in (5, 12, 22):
        if B[idx]:
            B[idx]["fee"] = 10
            B[idx]["amt"] = round(B[idx]["amt"] - 10, 2)
    # 4) تبديل أرقام
    if B[40]:
        s = f"{int(B[40]['amt'])}"
        B[40]["amt"] = float(s[:-2] + s[-1] + s[-2]) + 0.0 if len(s) > 2 and s[-1] != s[-2] else B[40]["amt"] + 90
    # 5) خطأ فاصلة عشرية
    if B[45]:
        B[45]["amt"] = round(B[45]["amt"] * 10, 2)
    # 6) فرق تاريخ كبير
    if B[10]:
        B[10]["d"] = B[10]["d"] + timedelta(days=9)
    # 7) اختلاف عملة
    if B[14]:
        B[14]["cur"] = "USD" if B[14]["cur"] != "USD" else "SAR"
    # 8) عملية بدون مرجع في الصرافة (تُطابق ذكياً)
    for idx in (20, 25):
        if B[idx] and A[idx]:
            B[idx]["ref"] = ""
    # 9) مرجع بخطأ طباعي
    if B[28]:
        r = B[28]["ref"]
        B[28]["ref"] = r[:-2] + r[-1] + r[-2]
    # 10) تكرار عند المحاسب وتكرار عند الصرافة
    dupA = dict(A[2])
    dupA["v"] = "V-DUP"
    A.append(dupA)
    if B[50]:
        B.append(dict(B[50]))
    # 11) مرجع داخل البيان فقط عند المحاسب
    if A[35] and B[35]:
        A[35]["desc"] = f"تسوية حوالة رقم {A[35]['ref']}"
        A[35]["ref"] = ""
    # 12) مبلغ مسجل بفارق صغير جداً (تقريب)
    if B[1]:
        B[1]["amt"] = round(B[1]["amt"] + 0.004, 3)
    # 13) فرق عادي غير مفسَّر
    if B[55]:
        B[55]["amt"] = round(B[55]["amt"] - 137.25, 2)

    A = [x for x in A if x]
    B = [x for x in B if x]
    rnd.shuffle(B)

    # ---- ملف المحاسب (مدين/دائن، مع صفوف ترويسة وإجماليات) ----
    pa = out / "ملف_المحاسب.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "كشف الحساب"
    ws.sheet_view.rightToLeft = True
    ws.append(["شركة النور للتجارة"])
    ws.append(["كشف حساب الحوالات - سبتمبر 2026"])
    ws.append([])
    ws.append(["رقم السند", "التاريخ", "البيان", "رقم الحوالة", "اسم العميل", "العملة", "مدين", "دائن"])
    tot = {}
    for x in sorted(A, key=lambda x: x["d"]):
        ws.append([x["v"], x["d"], x["desc"], x["ref"] or None, x["name"], x["cur"], x["amt"], None])
        tot[x["cur"]] = tot.get(x["cur"], 0) + x["amt"]
    ws.append([])
    ws.append(["", "", "إجمالي", "", "", "", sum(tot.values()), ""])
    for c in ws[4]:
        c.font = Font(bold=True)
    wb.save(pa)

    # ---- ملف الصرافة (مبلغ واحد + رسوم، بصيغة مختلفة وأرقام عربية في بعض الصفوف) ----
    pb = out / "ملف_الصرافة.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Transfers"
    ws.append(["Reference", "Value Date", "Beneficiary", "Currency", "Amount", "Commission"])
    for x in B:
        ws.append([x["ref"] or None, x["d"], x["name"], x["cur"], x["amt"], x["fee"] or None])
    wb.save(pb)
    return str(pa), str(pb)


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "sample_data"
    a, b = make(folder)
    print(a)
    print(b)
