"""محرك المطابقة والتسوية.

المراحل:
  1) مطابقة بالمرجع (مع معالجة المراجع المتكررة والعمليات المكررة)
  2) مطابقة بالمرجع المذكور داخل البيان / رقم السند
  3) مطابقة ذكية (مبلغ + تاريخ + اسم + تقارب المرجع) للعمليات المتبقية
  4) اكتشاف التكرار
  5) تصنيف المفقودات مع تلميحات تفسيرية

الفرق دائماً = (مبلغ المحاسب) - (مبلغ الصرافة بعد مواءمة الإشارة)
ومجموع كل الفروقات = إجمالي المحاسب - إجمالي الصرافة (تحقق حسابي مدمج).
"""
from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Callable, Optional

from .loader import Record
from .normalize import name_similarity, q2

# ---------------------------------------------------------------------------
STATUS_MATCHED = "متطابقة"
STATUS_DIFF = "مختلفة"
STATUS_MISSING_B = "مفقودة في الصرافة"
STATUS_MISSING_A = "مفقودة في ملف المحاسب"
STATUS_DUP = "مكررة"
STATUS_POSSIBLE = "محتملة المطابقة"

ALL_STATUSES = [STATUS_MATCHED, STATUS_DIFF, STATUS_POSSIBLE, STATUS_MISSING_B,
                STATUS_MISSING_A, STATUS_DUP]
STATUS_ORDER = {s: i for i, s in enumerate(
    [STATUS_DIFF, STATUS_MISSING_B, STATUS_MISSING_A, STATUS_DUP, STATUS_POSSIBLE, STATUS_MATCHED])}

SRC_A = "المحاسب"
SRC_B = "الصرافة"
SRC_BOTH = "الاثنان"

CAT_ROUND = "فروقات تقريب"
CAT_AMOUNT = "فروقات مبالغ (عمليات مرتبطة)"
CAT_FEE = "فروقات مفسّرة بالرسوم"
CAT_SIGN = "إشارة معكوسة (مدين/دائن)"
CAT_CUR = "اختلاف عملة"
CAT_POSSIBLE = "فروقات في المطابقات المحتملة"
CAT_MISS_B = "عمليات عند المحاسب وغير موجودة عند الصرافة"
CAT_MISS_A = "عمليات عند الصرافة وغير موجودة عند المحاسب"
CAT_DUP_A = "مكررة في ملف المحاسب"
CAT_DUP_B = "مكررة في ملف الصرافة"

BRIDGE_ORDER = [CAT_MISS_B, CAT_MISS_A, CAT_DUP_A, CAT_DUP_B, CAT_AMOUNT, CAT_FEE, CAT_SIGN,
                CAT_CUR, CAT_POSSIBLE, CAT_ROUND]


@dataclass
class Settings:
    amount_tol: Decimal = Decimal("0.01")     # تسامح المبلغ (عملة)
    date_tol_days: int = 3                   # فرق تاريخ مقبول للمرجع المتطابق
    fuzzy_days: int = 5                      # نافذة التاريخ للمطابقة الذكية
    possible_pct: float = 0.02               # أعلى نسبة فرق مقبولة للمطابقة المحتملة
    name_threshold: float = 0.80             # حد تشابه الأسماء
    sign_mode: str = "auto"                  # auto / same / opposite / ignore
    strict_currency: bool = True
    use_fuzzy: bool = True
    use_desc_ref: bool = True
    check_party: bool = True
    auto_accept: float = 0.92                # ثقة المطابقة الذكية التي تُعدّ "متطابقة"
    min_possible: float = 0.60               # أدنى ثقة تظهر كمحتملة
    detect_duplicates: bool = True

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["amount_tol"] = str(self.amount_tol)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Settings":
        s = Settings()
        for k, v in d.items():
            if hasattr(s, k):
                if k == "amount_tol":
                    v = Decimal(str(v))
                setattr(s, k, v)
        return s


@dataclass
class MatchRow:
    id: int = 0
    status: str = ""
    method: str = ""
    confidence: int = 0
    a: Optional[Record] = None
    b: Optional[Record] = None
    cur_a: str = ""
    cur_b: str = ""
    amt_a: Optional[Decimal] = None   # بعد المواءمة
    amt_b: Optional[Decimal] = None   # بعد المواءمة
    diff: Decimal = Decimal(0)
    reasons: list[str] = field(default_factory=list)
    action: str = ""
    priority: str = ""
    flags: set = field(default_factory=set)
    explained: bool = False
    source: str = ""
    contribs: list[tuple[str, str, Decimal]] = field(default_factory=list)  # (عملة, فئة, مبلغ)
    note: str = ""   # ملاحظة المراجع (تُحفظ لاحقاً)
    decision: str = ""  # قرار المراجع: "" / معتمد / مرفوض

    @property
    def currency(self) -> str:
        return self.cur_a or self.cur_b

    @property
    def ref(self) -> str:
        return (self.a.ref if self.a and self.a.ref else (self.b.ref if self.b else ""))

    @property
    def reason_text(self) -> str:
        return " · ".join(self.reasons)


@dataclass
class ReconResult:
    rows: list[MatchRow]
    settings: Settings
    rel: int
    rel_note: str
    count_a: int
    count_b: int
    total_a: dict[str, Decimal]
    total_b: dict[str, Decimal]
    bridge: dict[str, dict[str, Decimal]]     # عملة -> فئة -> مبلغ
    integrity: dict[str, Decimal]             # عملة -> الفرق بين الجسر والفرق الفعلي (يجب = 0)
    counts: dict[str, int]
    warnings: list[str]
    range_a: tuple[Optional[date], Optional[date]]
    range_b: tuple[Optional[date], Optional[date]]

    @property
    def currencies(self) -> list[str]:
        cs = set(self.total_a) | set(self.total_b)
        return sorted(cs)

    @property
    def match_rate(self) -> float:
        n = max(self.count_a, self.count_b, 1)
        return self.counts.get(STATUS_MATCHED, 0) / n

    def net_diff(self, cur: str) -> Decimal:
        return self.total_a.get(cur, Decimal(0)) - self.total_b.get(cur, Decimal(0))


# ---------------------------------------------------------------------------
def _eff(rec: Record, rel: int, mode: str) -> Decimal:
    if mode == "ignore":
        return abs(rec.amount)
    return rec.amount if rec.side == "A" else rec.amount * rel


def _days(a: Optional[date], b: Optional[date]) -> Optional[int]:
    if a is None or b is None:
        return None
    return abs((a - b).days)


def _fmt(d: Decimal) -> str:
    return f"{q2(d):,.2f}"


def _digits_key(d: Decimal) -> str:
    return str(q2(abs(d))).replace(".", "")


def _explain_amount(mag: Decimal, a: Record, b: Record, S: Settings) -> tuple[list[str], bool, set]:
    """تفسير فرق المبلغ. mag = |A| - |B|."""
    reasons: list[str] = []
    flags: set = set()
    explained = False
    am = abs(mag)
    if mag > 0:
        reasons.append(f"مبلغ المحاسب أكبر من مبلغ الصرافة بمقدار {_fmt(am)}")
    else:
        reasons.append(f"مبلغ الصرافة أكبر من مبلغ المحاسب بمقدار {_fmt(am)}")

    for who, fee in (("الصرافة", b.fee), ("المحاسب", a.fee)):
        if fee and fee > 0 and abs(am - fee) <= S.amount_tol:
            reasons.append(f"الفرق يساوي الرسوم/العمولة المسجلة في ملف {who} ({_fmt(fee)})")
            explained = True
            flags.add("fee")
            break

    if not explained:
        lo, hi = sorted([abs(a.amount), abs(b.amount)])
        if lo > 0:
            ratio = hi / lo
            for r in (10, 100, 1000):
                if abs(ratio - r) / r < Decimal("0.0005"):
                    reasons.append("احتمال خطأ في موضع الفاصلة العشرية (النسبة بين المبلغين "
                                   f"{r}×)")
                    flags.add("decimal")
                    break
            sa, sb = _digits_key(a.amount), _digits_key(b.amount)
            if "decimal" not in flags and sa != sb and len(sa) >= 2 and sorted(sa) == sorted(sb):
                reasons.append("احتمال تبديل أرقام عند الإدخال (نفس الأرقام بترتيب مختلف)")
                flags.add("transpose")
            if "decimal" not in flags and "transpose" not in flags:
                p = am / hi
                if am < 1:
                    reasons.append("فرق تقريب صغير")
                    flags.add("rounding")
                elif p <= Decimal("0.03"):
                    reasons.append(f"الفرق يمثل {float(p) * 100:.2f}% من المبلغ — قد يكون عمولة أو "
                                   "سعر صرف غير موثّق")
                    flags.add("pct")
                else:
                    reasons.append("فرق غير مفسّر بالبيانات المتاحة")
                    flags.add("unexplained")
    return reasons, explained, flags


class Engine:
    def __init__(self, settings: Optional[Settings] = None,
                 progress: Optional[Callable[[int, str], None]] = None):
        self.S = settings or Settings()
        self.progress = progress or (lambda p, m: None)
        self.rel = 1

    # ------------------------------------------------------------------ عام
    def eff(self, rec: Record) -> Decimal:
        return _eff(rec, self.rel, self.S.sign_mode)

    def _row_from_pair(self, a: Record, b: Record, method: str, conf: int) -> MatchRow:
        S = self.S
        ea, eb = self.eff(a), self.eff(b)
        row = MatchRow(a=a, b=b, method=method, confidence=conf,
                       cur_a=a.currency, cur_b=b.currency, amt_a=ea, amt_b=eb,
                       diff=ea - eb, source=SRC_BOTH)
        flags: set = set()
        reasons: list[str] = []

        sign_flag = (S.sign_mode != "ignore" and ea != 0 and eb != 0 and (ea > 0) != (eb > 0))
        if sign_flag:
            flags.add("sign")
            reasons.append("إشارة العملية معكوسة بين الملفين (مدين/دائن)")

        mag = abs(a.amount) - abs(b.amount)
        explained = False
        if abs(mag) > S.amount_tol:
            flags.add("amount")
            r, explained, f2 = _explain_amount(mag, a, b, S)
            reasons.extend(r)
            flags |= f2

        if S.strict_currency and a.currency and b.currency and a.currency != b.currency:
            flags.add("currency")
            reasons.append(f"اختلاف العملة: المحاسب {a.currency} مقابل الصرافة {b.currency}")

        d = _days(a.date, b.date)
        if d is not None and d > S.date_tol_days:
            flags.add("date")
            reasons.append(f"فرق التاريخ {d} يوم (المحاسب {a.date:%Y-%m-%d} / الصرافة {b.date:%Y-%m-%d})")

        if S.check_party and a.party and b.party:
            sim = name_similarity(a.party, b.party)
            if sim < 0.35:
                flags.add("party")
                reasons.append("تنبيه: اسم الطرف مختلف بين الملفين")

        hard = flags & {"amount", "sign", "currency", "date"}
        row.flags = flags
        row.explained = explained and (flags & {"sign", "currency", "date"}) == set()
        if hard:
            row.status = STATUS_DIFF
        else:
            row.status = STATUS_MATCHED
            if not reasons:
                reasons.append("تطابق تام" if method.startswith("المرجع") else "تطابق تام في البيانات المتاحة")
        row.reasons = reasons

        # مساهمة الجسر الحسابي
        cur = a.currency or b.currency
        if "currency" in flags:
            row.contribs = [(a.currency, CAT_CUR, ea), (b.currency, CAT_CUR, -eb)]
        else:
            if "sign" in flags:
                cat = CAT_SIGN
            elif "amount" in flags and row.explained and "fee" in flags:
                cat = CAT_FEE
            elif "amount" in flags:
                cat = CAT_AMOUNT
            else:
                cat = CAT_ROUND
            if method == "مطابقة ذكية" and row.status != STATUS_MATCHED:
                cat = CAT_POSSIBLE
            row.contribs = [(cur, cat, row.diff)]
        return row

    # ------------------------------------------------------------------ التشغيل
    def run(self, recs_a: list[Record], recs_b: list[Record]) -> ReconResult:
        S = self.S
        warnings: list[str] = []
        self.progress(5, "تجهيز السجلات")

        unmatched_a: dict[str, Record] = {r.uid: r for r in recs_a}
        unmatched_b: dict[str, Record] = {r.uid: r for r in recs_b}
        rows: list[MatchRow] = []
        raw_pairs: list[tuple[Record, Record, str, int]] = []
        dup_rows: list[MatchRow] = []

        # ---- المرحلة 1: المرجع ----
        self.progress(15, "المطابقة بالمرجع")
        ga: dict[str, list[Record]] = defaultdict(list)
        gb: dict[str, list[Record]] = defaultdict(list)
        for r in recs_a:
            if r.ref_norm:
                ga[r.ref_norm].append(r)
        for r in recs_b:
            if r.ref_norm:
                gb[r.ref_norm].append(r)

        group_leftovers: list[tuple[str, list[Record], list[Record]]] = []
        for key, la in ga.items():
            lb = gb.get(key)
            if not lb:
                continue
            cands = []
            for i, a in enumerate(la):
                for j, b in enumerate(lb):
                    cur_mis = 1 if (a.currency and b.currency and a.currency != b.currency) else 0
                    dd = _days(a.date, b.date)
                    cands.append((cur_mis, abs(abs(a.amount) - abs(b.amount)),
                                  dd if dd is not None else 9999, i, j))
            cands.sort()
            ua, ub = set(), set()
            for cm, ad, dd, i, j in cands:
                if i in ua or j in ub:
                    continue
                ua.add(i)
                ub.add(j)
                raw_pairs.append((la[i], lb[j], "المرجع", 100))
            group_leftovers.append((key, [la[i] for i in range(len(la)) if i not in ua],
                                    [lb[j] for j in range(len(lb)) if j not in ub]))

        for a, b, m, c in raw_pairs:
            unmatched_a.pop(a.uid, None)
            unmatched_b.pop(b.uid, None)

        # ---- تحديد علاقة الإشارة ----
        self._decide_sign(raw_pairs, warnings)

        for a, b, m, c in raw_pairs:
            row = self._row_from_pair(a, b, m, c)
            if row.status == STATUS_DIFF:
                row.confidence = 95
            rows.append(row)

        # ---- تكرار ضمن مجموعات المرجع ----
        if S.detect_duplicates:
            for key, la, lb in group_leftovers:
                all_a = ga[key]
                all_b = gb[key]
                for r in la:
                    if self._is_dup_of(r, [x for x in all_a if x.uid != r.uid]):
                        dup_rows.append(self._dup_row(r, f"نفس المرجع والمبلغ والتاريخ مسجّل أكثر من مرة في ملف المحاسب"))
                        unmatched_a.pop(r.uid, None)
                for r in lb:
                    if self._is_dup_of(r, [x for x in all_b if x.uid != r.uid]):
                        dup_rows.append(self._dup_row(r, f"نفس المرجع والمبلغ والتاريخ مسجّل أكثر من مرة في ملف الصرافة"))
                        unmatched_b.pop(r.uid, None)

        # ---- المرحلة 2: المرجع داخل البيان / السند ----
        if S.use_desc_ref:
            self.progress(35, "البحث عن المراجع داخل البيانات")
            self._desc_ref_stage(unmatched_a, unmatched_b, rows)

        # ---- المرحلة 3: المطابقة الذكية ----
        if S.use_fuzzy and unmatched_a and unmatched_b:
            self.progress(55, "المطابقة الذكية (مبلغ + تاريخ + اسم)")
            self._fuzzy_stage(unmatched_a, unmatched_b, rows)

        # ---- المرحلة 4: تكرار بلا مرجع + المفقودات ----
        self.progress(80, "تصنيف المفقودات والمكررات")
        if S.detect_duplicates:
            self._dups_unmatched(unmatched_a, rows, dup_rows, "A")
            self._dups_unmatched(unmatched_b, rows, dup_rows, "B")
        rows.extend(dup_rows)

        range_a = self._range(recs_a)
        range_b = self._range(recs_b)
        self._missing_rows(unmatched_a, unmatched_b, rows, range_a, range_b)

        # ---- إجراءات وأولويات ----
        for r in rows:
            self._finalize(r)
        rows.sort(key=lambda r: (STATUS_ORDER[r.status],
                                 -(abs(r.diff)),
                                 (r.a.row if r.a else 10**9), (r.b.row if r.b else 10**9)))
        for i, r in enumerate(rows, 1):
            r.id = i

        self.progress(92, "حساب الفروقات والتحقق الحسابي")
        res = self._summarize(rows, recs_a, recs_b, warnings, range_a, range_b)
        self.progress(100, "اكتملت المطابقة")
        return res

    # ------------------------------------------------------------------ مساعدات
    @staticmethod
    def _range(recs: list[Record]):
        ds = [r.date for r in recs if r.date]
        return (min(ds), max(ds)) if ds else (None, None)

    def _decide_sign(self, pairs, warnings):
        S = self.S
        if S.sign_mode == "same":
            self.rel, self.rel_note = 1, "اتجاه الإشارة: نفس الاتجاه في الملفين (إعداد يدوي)"
        elif S.sign_mode == "opposite":
            self.rel, self.rel_note = -1, "اتجاه الإشارة: معكوس بين الملفين (إعداد يدوي)"
        elif S.sign_mode == "ignore":
            self.rel, self.rel_note = 1, "تجاهل الإشارات: المقارنة بالقيمة المطلقة"
        else:
            same = opp = 0
            for a, b, *_ in pairs:
                if a.amount == 0 or b.amount == 0:
                    continue
                if (a.amount > 0) == (b.amount > 0):
                    same += 1
                else:
                    opp += 1
            if opp > same:
                self.rel = -1
                self.rel_note = (f"اكتُشف تلقائياً أن إشارات الصرافة معكوسة عن المحاسب "
                                 f"({opp} عملية معكوسة مقابل {same})")
            else:
                self.rel = 1
                self.rel_note = (f"اكتُشف تلقائياً أن الإشارات بنفس الاتجاه "
                                 f"({same} مقابل {opp} معكوسة)" if (same or opp)
                                 else "لا توجد عمليات مرجعية كافية لتحديد الإشارة؛ افتُرض نفس الاتجاه")

    def _is_dup_of(self, r: Record, others: list[Record]) -> bool:
        for o in others:
            if (abs(o.amount - r.amount) <= self.S.amount_tol and o.currency == r.currency
                    and (o.date == r.date or o.date is None or r.date is None)):
                return True
        return False

    def _dup_row(self, r: Record, why: str) -> MatchRow:
        e = self.eff(r)
        row = MatchRow(status=STATUS_DUP, method="كشف التكرار", confidence=90,
                       cur_a=r.currency if r.side == "A" else "",
                       cur_b=r.currency if r.side == "B" else "",
                       reasons=[why])
        if r.side == "A":
            row.a, row.amt_a, row.diff, row.source = r, e, e, SRC_A
            row.contribs = [(r.currency, CAT_DUP_A, e)]
        else:
            row.b, row.amt_b, row.diff, row.source = r, e, -e, SRC_B
            row.contribs = [(r.currency, CAT_DUP_B, -e)]
        return row

    def _dups_unmatched(self, un: dict[str, Record], rows, dup_rows, side):
        """تكرار بين السجلات غير المطابقة (أو مماثلة لسجل مطابَق) بلا مرجع."""
        matched_recs = [getattr(r, "a" if side == "A" else "b") for r in rows
                        if getattr(r, "a" if side == "A" else "b") is not None]
        def key(r: Record):
            return (r.ref_norm, q2(abs(r.amount)), r.currency, r.date,
                    re.sub(r"\s+", " ", r.party.strip().lower()))
        seen: dict = {}
        for m in matched_recs:
            if m.ref_norm or m.party:
                seen.setdefault(key(m), m)
        for uid, r in sorted(un.items(), key=lambda kv: kv[1].row):
            if not (r.ref_norm or r.party):
                continue
            k = key(r)
            if k in seen:
                side_name = "المحاسب" if side == "A" else "الصرافة"
                dup_rows.append(self._dup_row(
                    r, f"تطابق كامل (المرجع/المبلغ/التاريخ/الاسم) مع العملية في الصف {seen[k].row} من ملف {side_name}"))
                un[uid] = None  # علامة للحذف
            else:
                seen[k] = r
        for uid in [u for u, v in un.items() if v is None]:
            del un[uid]

    # ---- المرجع داخل البيان ----
    def _desc_ref_stage(self, ua, ub, rows):
        tok = re.compile(r"[A-Za-z0-9]{6,}")
        from .normalize import norm_ref
        idx_b = defaultdict(list)
        for r in ub.values():
            if r.ref_norm:
                idx_b[r.ref_norm].append(r)
        idx_a = defaultdict(list)
        for r in ua.values():
            if r.ref_norm:
                idx_a[r.ref_norm].append(r)

        def tokens(r: Record):
            out = set()
            for t in tok.findall((r.desc or "") + " " + (r.ref2 or "")):
                n = norm_ref(t)
                if len(n) >= 6:
                    out.add(n)
            if r.ref2:
                n = norm_ref(r.ref2)
                if len(n) >= 4:
                    out.add(n)
            return out

        for a in list(ua.values()):
            for t in tokens(a):
                if t == a.ref_norm:
                    continue
                cands = [b for b in idx_b.get(t, []) if b.uid in ub]
                if len(cands) == 1:
                    b = cands[0]
                    row = self._row_from_pair(a, b, "المرجع داخل البيان", 90)
                    row.reasons.insert(0, f"رُبطت العمليتان لأن رقم المرجع {t} مذكور في بيان/سند المحاسب")
                    rows.append(row)
                    ua.pop(a.uid, None)
                    ub.pop(b.uid, None)
                    break
        for b in list(ub.values()):
            for t in tokens(b):
                if t == b.ref_norm:
                    continue
                cands = [a for a in idx_a.get(t, []) if a.uid in ua]
                if len(cands) == 1:
                    a = cands[0]
                    row = self._row_from_pair(a, b, "المرجع داخل البيان", 90)
                    row.reasons.insert(0, f"رُبطت العمليتان لأن رقم المرجع {t} مذكور في بيان الصرافة")
                    rows.append(row)
                    ua.pop(a.uid, None)
                    ub.pop(b.uid, None)
                    break

    # ---- المطابقة الذكية ----
    def _score(self, a: Record, b: Record) -> Optional[float]:
        S = self.S
        if S.strict_currency and a.currency and b.currency and a.currency != b.currency:
            return None
        ma = abs(a.amount) - abs(b.amount)
        am = abs(ma)
        hi = max(abs(a.amount), abs(b.amount))
        if am <= S.amount_tol:
            amt_s = 1.0
        else:
            fee_ok = any(f and f > 0 and abs(am - f) <= S.amount_tol for f in (a.fee, b.fee))
            if fee_ok:
                amt_s = 0.85
            else:
                p = float(am / hi) if hi else 1.0
                if p > S.possible_pct:
                    return None
                amt_s = max(0.3, 0.7 * (1 - p / max(S.possible_pct, 1e-9)))

        # المرجع
        ref_sim = None
        if a.ref_norm and b.ref_norm and len(a.ref_norm) >= 4 and len(b.ref_norm) >= 4:
            try:
                from rapidfuzz import fuzz
                ref_sim = fuzz.ratio(a.ref_norm, b.ref_norm) / 100.0
            except Exception:
                ref_sim = 1.0 if a.ref_norm == b.ref_norm else 0.0

        d = _days(a.date, b.date)
        if d is None:
            date_s = 0.5
        elif d > S.fuzzy_days:
            if ref_sim is not None and ref_sim >= 0.85 and amt_s >= 0.85:
                date_s = 0.2
            else:
                return None
        else:
            date_s = 1 - d / (S.fuzzy_days + 1)

        if a.party and b.party:
            sim = name_similarity(a.party, b.party)
            name_s = sim
        else:
            name_s = 0.5

        ref_s = 0.5 if ref_sim is None else ref_sim
        conf = 0.40 * amt_s + 0.25 * date_s + 0.25 * name_s + 0.10 * ref_s
        if ref_sim is not None:
            if ref_sim < 0.6:
                conf *= 0.6
            elif ref_sim >= 0.85:
                conf = min(1.0, conf + 0.10)
        return conf

    def _fuzzy_stage(self, ua, ub, rows):
        S = self.S
        b_list = sorted(ub.values(), key=lambda r: abs(r.amount))
        b_keys = [abs(r.amount) for r in b_list]
        max_fee_b = max((r.fee for r in b_list), default=Decimal(0))

        edges = []
        for a in ua.values():
            x = abs(a.amount)
            pad = x * Decimal(str(S.possible_pct)) + a.fee + max_fee_b + S.amount_tol
            lo = bisect_left(b_keys, x - pad)
            hi = bisect_right(b_keys, x + pad)
            for b in b_list[lo:hi]:
                c = self._score(a, b)
                if c is not None and c >= S.min_possible:
                    edges.append((c, a.uid, b.uid))
        edges.sort(key=lambda e: -e[0])

        by_a, by_b = defaultdict(list), defaultdict(list)
        for c, au, bu in edges:
            by_a[au].append(c)
            by_b[bu].append(c)

        used_a, used_b = set(), set()
        for c, au, bu in edges:
            if au in used_a or bu in used_b:
                continue
            a, b = ua[au], ub[bu]
            # غموض: مرشح آخر قريب في الثقة
            alt_a = sorted(by_a[au], reverse=True)
            alt_b = sorted(by_b[bu], reverse=True)
            ambiguous = (len(alt_a) > 1 and alt_a[1] >= c - 0.03) or (len(alt_b) > 1 and alt_b[1] >= c - 0.03)
            conf = min(c, 0.98) * (0.9 if ambiguous else 1.0)
            row = self._row_from_pair(a, b, "مطابقة ذكية", int(round(conf * 100)))
            refs_conflict = bool(a.ref_norm and b.ref_norm and a.ref_norm != b.ref_norm)
            if row.status == STATUS_MATCHED and conf >= S.auto_accept and not refs_conflict and not ambiguous:
                row.reasons = ["مطابقة ذكية: تطابق المبلغ والتاريخ والاسم بدون مرجع مشترك"]
            else:
                row.status = STATUS_POSSIBLE
                row.contribs = [(cc, CAT_POSSIBLE if cat in (CAT_ROUND, CAT_AMOUNT, CAT_FEE, CAT_SIGN) else cat, m)
                                for cc, cat, m in row.contribs]
                notes = []
                if refs_conflict:
                    from rapidfuzz import fuzz
                    sim = fuzz.ratio(a.ref_norm, b.ref_norm)
                    if sim >= 85:
                        notes.append(f"المرجعان متقاربان جداً ({a.ref} ↔ {b.ref}) — احتمال خطأ طباعي")
                    else:
                        notes.append(f"المرجعان مختلفان ({a.ref} ↔ {b.ref}) رغم تقارب باقي البيانات")
                elif not a.ref_norm or not b.ref_norm:
                    notes.append("لا يوجد مرجع في أحد الطرفين؛ الاعتماد على المبلغ والتاريخ والاسم")
                if ambiguous:
                    notes.append("يوجد أكثر من مرشح بنفس الدرجة تقريباً — يلزم اختيار يدوي")
                row.reasons = notes + [r for r in row.reasons if not r.startswith("تطابق تام")]
            rows.append(row)
            used_a.add(au)
            used_b.add(bu)
        for u in used_a:
            ua.pop(u, None)
        for u in used_b:
            ub.pop(u, None)

    # ---- المفقودات ----
    def _missing_rows(self, ua, ub, rows, range_a, range_b):
        def hints(r: Record, others: dict[str, Record], other_range, other_name):
            out = []
            for o in others.values():
                if (abs(abs(o.amount) - abs(r.amount)) <= self.S.amount_tol
                        and (not r.currency or not o.currency or r.currency == o.currency)):
                    d = _days(r.date, o.date)
                    extra = f" بفارق {d} يوم" if d is not None else ""
                    out.append(f"يوجد في ملف {other_name} عملية بنفس المبلغ (الصف {o.row}) لكن لم تُربط{extra}")
                    break
            lo, hi = other_range
            if r.date and lo and hi and (r.date < lo or r.date > hi):
                out.append(f"تاريخ العملية خارج الفترة التي يغطيها ملف {other_name} "
                           f"({lo:%Y-%m-%d} → {hi:%Y-%m-%d}) — قد تكون ضمن فترة مختلفة")
            return out

        for r in ua.values():
            e = self.eff(r)
            row = MatchRow(status=STATUS_MISSING_B, method="لا يوجد مقابل", confidence=0, a=r,
                           cur_a=r.currency, amt_a=e, diff=e, source=SRC_A,
                           reasons=["غير موجودة في ملف الصرافة"] + hints(r, ub, range_b, "الصرافة"),
                           contribs=[(r.currency, CAT_MISS_B, e)])
            rows.append(row)
        for r in ub.values():
            e = self.eff(r)
            row = MatchRow(status=STATUS_MISSING_A, method="لا يوجد مقابل", confidence=0, b=r,
                           cur_b=r.currency, amt_b=e, diff=-e, source=SRC_B,
                           reasons=["غير موجودة في ملف المحاسب"] + hints(r, ua, range_a, "المحاسب"),
                           contribs=[(r.currency, CAT_MISS_A, -e)])
            rows.append(row)

    # ---- الإجراء والأولوية ----
    def _finalize(self, r: MatchRow):
        f = r.flags
        if r.status == STATUS_MATCHED:
            r.priority = "—"
            r.action = "لا إجراء مطلوب"
            if "party" in f:
                r.priority = "منخفضة"
                r.action = "تأكد من أن اختلاف الاسم مقصود (مثلاً اسم الحساب مقابل المستفيد)"
        elif r.status == STATUS_DIFF:
            acts = []
            if "sign" in f:
                acts.append("راجع اتجاه العملية (مدين/دائن) في الملفين")
            if "currency" in f:
                acts.append("تحقق من عملة العملية في المستند الأصلي")
            if "fee" in f and r.explained:
                acts.append("اعتمد الفرق كرسوم/عمولة وسجّل قيد الرسوم إن لم يكن مسجلاً")
            elif "decimal" in f or "transpose" in f:
                acts.append("راجع المستند الأصلي — الخطأ على الأرجح في الإدخال لأحد الطرفين")
            elif "amount" in f:
                acts.append("راجع المستند الأصلي وصحّح المبلغ في الملف الخاطئ")
            if "date" in f:
                acts.append("راجع تاريخ القيد (قد تكون العملية مُرحّلة لفترة أخرى)")
            r.action = "؛ ".join(acts) or "راجع الفروقات"
            if r.explained:
                r.priority = "منخفضة"
            elif abs(r.diff) >= Decimal(1000) or "sign" in f or "currency" in f:
                r.priority = "عالية"
            else:
                r.priority = "متوسطة"
        elif r.status == STATUS_POSSIBLE:
            r.priority = "متوسطة"
            r.action = "راجع المطابقة المقترحة ثم اعتمدها أو ارفضها"
        elif r.status == STATUS_MISSING_B:
            r.priority = "عالية"
            r.action = ("اسأل الصرافة: هل نُفذت العملية؟ إن لم تُنفَّذ فصحّح قيد المحاسب، "
                        "وإن نُفذت فاطلب كشفاً مصحّحاً")
        elif r.status == STATUS_MISSING_A:
            r.priority = "عالية"
            r.action = "تحقق من مستند العملية ثم سجّلها في دفاتر المحاسب إن كانت سليمة"
        elif r.status == STATUS_DUP:
            r.priority = "عالية"
            r.action = "تحقق من التكرار؛ إن كان خطأً فاعكس القيد المكرر وصحّح الإجمالي"

    # ---- الملخص والتحقق الحسابي ----
    def _summarize(self, rows, recs_a, recs_b, warnings, range_a, range_b) -> ReconResult:
        total_a: dict[str, Decimal] = defaultdict(Decimal)
        total_b: dict[str, Decimal] = defaultdict(Decimal)
        for r in recs_a:
            total_a[r.currency] += self.eff(r)
        for r in recs_b:
            total_b[r.currency] += self.eff(r)

        bridge: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for row in rows:
            for cur, cat, amt in row.contribs:
                bridge[cur][cat] += amt
        integrity = {}
        for cur in set(total_a) | set(total_b) | set(bridge):
            actual = total_a.get(cur, Decimal(0)) - total_b.get(cur, Decimal(0))
            integrity[cur] = q2(sum(bridge[cur].values(), Decimal(0)) - actual)

        counts = {s: 0 for s in ALL_STATUSES}
        for r in rows:
            counts[r.status] += 1

        if any(v != 0 for v in integrity.values()):
            warnings.append("تنبيه: التحقق الحسابي لم يغلق على صفر — راجع القواعد أو أبلغ المطوّر.")

        return ReconResult(
            rows=rows, settings=self.S, rel=self.rel, rel_note=self.rel_note,
            count_a=len(recs_a), count_b=len(recs_b),
            total_a=dict(total_a), total_b=dict(total_b),
            bridge={c: dict(v) for c, v in bridge.items()},
            integrity=integrity, counts=counts, warnings=warnings,
            range_a=range_a, range_b=range_b)


def reconcile(recs_a: list[Record], recs_b: list[Record], settings: Optional[Settings] = None,
              progress: Optional[Callable[[int, str], None]] = None) -> ReconResult:
    return Engine(settings, progress).run(recs_a, recs_b)


# ---------------------------------------------------------------------------
# تعديلات المراجع بعد التشغيل
# ---------------------------------------------------------------------------
def refresh_result(res: ReconResult) -> None:
    """يعيد حساب العدادات والجسر الحسابي والتحقق بعد أي تعديل على الصفوف."""
    bridge: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    counts = {s: 0 for s in ALL_STATUSES}
    for row in res.rows:
        counts[row.status] += 1
        for cur, cat, amt in row.contribs:
            bridge[cur][cat] += amt
    res.counts = counts
    res.bridge = {c: dict(v) for c, v in bridge.items()}
    res.integrity = {}
    for cur in set(res.total_a) | set(res.total_b) | set(bridge):
        actual = res.total_a.get(cur, Decimal(0)) - res.total_b.get(cur, Decimal(0))
        res.integrity[cur] = q2(sum(bridge[cur].values(), Decimal(0)) - actual)


def manual_link(res: ReconResult, row_a: MatchRow, row_b: MatchRow) -> MatchRow:
    """ربط يدوي بين صف «مفقود في الصرافة» وصف «مفقود في ملف المحاسب»."""
    if not (row_a.status == STATUS_MISSING_B and row_a.a and row_b.status == STATUS_MISSING_A and row_b.b):
        raise ValueError("الربط اليدوي ممكن فقط بين عملية «مفقودة في الصرافة» وعملية «مفقودة في ملف المحاسب».")
    eng = Engine(res.settings)
    eng.rel = res.rel
    new = eng._row_from_pair(row_a.a, row_b.b, "ربط يدوي", 100)
    new.reasons = ["ربط يدوي بواسطة المراجع"] + [r for r in new.reasons if not r.startswith("تطابق تام")]
    eng._finalize(new)
    new.decision = "معتمد"
    res.rows = [r for r in res.rows if r is not row_a and r is not row_b]
    new.id = max((r.id for r in res.rows), default=0) + 1
    res.rows.append(new)
    refresh_result(res)
    return new
