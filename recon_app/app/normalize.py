"""أدوات تطبيع البيانات: الأرقام العربية، المبالغ، التواريخ، العملات، المراجع، الأسماء."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬،", "01234567890123456789.,,")

# رموز وأسماء العملات الشائعة -> رمز ISO
CURRENCY_ALIASES = {
    "ر.س": "SAR", "ريال سعودي": "SAR", "سعودي": "SAR", "sar": "SAR", "sr": "SAR", "ر.س.": "SAR",
    "ر.ي": "YER", "ريال يمني": "YER", "يمني": "YER", "yer": "YER", "yr": "YER",
    "$": "USD", "دولار": "USD", "دولار امريكي": "USD", "دولار أمريكي": "USD", "usd": "USD",
    "€": "EUR", "يورو": "EUR", "eur": "EUR",
    "د.إ": "AED", "درهم": "AED", "درهم اماراتي": "AED", "درهم إماراتي": "AED", "aed": "AED",
    "ج.م": "EGP", "جنيه": "EGP", "جنيه مصري": "EGP", "egp": "EGP",
    "د.ك": "KWD", "دينار كويتي": "KWD", "kwd": "KWD",
    "ر.ع": "OMR", "ريال عماني": "OMR", "omr": "OMR",
    "ر.ق": "QAR", "ريال قطري": "QAR", "qar": "QAR",
    "د.ب": "BHD", "دينار بحريني": "BHD", "bhd": "BHD",
    "د.أ": "JOD", "دينار أردني": "JOD", "دينار اردني": "JOD", "jod": "JOD",
    "£": "GBP", "جنيه استرليني": "GBP", "gbp": "GBP",
    "ل.ت": "TRY", "ليرة": "TRY", "try": "TRY",
}

_AR_DIACRITICS = re.compile(r"[ً-ٰٟـ]")


def to_ascii_digits(s: str) -> str:
    return s.translate(_AR_DIGITS)


def clean_text(v) -> str:
    """نص منظّف: بدون تشكيل، همزات موحّدة، مسافات مفردة، أحرف صغيرة."""
    if v is None:
        return ""
    if isinstance(v, float) and v != v:  # NaN
        return ""
    s = str(v).strip()
    s = to_ascii_digits(s)
    s = _AR_DIACRITICS.sub("", s)
    s = (s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
          .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي"))
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def norm_ref(v) -> str:
    """تطبيع رقم مرجع/حوالة: أرقام وحروف فقط، بدون أصفار بادئة، بدون .0 الناتجة عن Excel."""
    if v is None:
        return ""
    if isinstance(v, float):
        if v != v:
            return ""
        if v.is_integer():
            v = int(v)
    s = to_ascii_digits(str(v)).strip().upper()
    s = re.sub(r"\.0+$", "", s)
    s = re.sub(r"[^0-9A-Zء-ي]", "", s)
    stripped = s.lstrip("0")
    return stripped if stripped else ("0" if s else "")


def parse_amount(v) -> Optional[Decimal]:
    """يحوّل أي تمثيل للمبلغ إلى Decimal. يدعم (123) كسالب، 123- ، فواصل الآلاف، الأرقام العربية."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int,)):
        return Decimal(v)
    if isinstance(v, float):
        if v != v:
            return None
        return Decimal(repr(v))
    if isinstance(v, Decimal):
        return v
    s = to_ascii_digits(str(v)).strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-") or s.startswith("−"):
        neg, s = True, s[1:]
    low = s.lower()
    if low.endswith("cr") or low.endswith("دائن"):
        s = re.sub(r"(?i)cr|دائن", "", s)
        neg = neg  # الدائن لا يقلب الإشارة هنا؛ يعالج عبر أعمدة مدين/دائن
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    # تحديد الفاصل العشري
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) in (1, 2) and len(parts) == 2:
            s = parts[0] + "." + parts[1]
        else:
            s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if neg else d


def q2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        # رقم تسلسلي من Excel
        if 20000 < float(v) < 80000:
            from datetime import timedelta
            return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
        return None
    s = to_ascii_digits(str(v)).strip()
    if not s:
        return None
    s = s.split(" ")[0] if re.match(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\s", s) else s
    fmts = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%m/%d/%Y", "%d/%m/%y", "%d-%m-%y", "%Y%m%d", "%d %b %Y", "%d-%b-%Y"]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None


def norm_currency(v, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, float) and v != v:
        return default
    s = clean_text(v).strip(". ")
    if not s:
        return default
    if s in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[s]
    for k, code in CURRENCY_ALIASES.items():
        if k == s.replace(".", ""):
            return code
    if re.fullmatch(r"[a-z]{3}", s):
        return s.upper()
    return s.upper()


def name_tokens(v) -> set[str]:
    s = clean_text(v)
    s = re.sub(r"[^\w\s]", " ", s)
    stop = {"بن", "ابن", "عبد", "ال", "bin", "al", "abd"}
    return {t for t in s.split() if t and t not in stop}


def name_similarity(a, b) -> float:
    """تشابه الأسماء 0..1 يعتمد على الكلمات المشتركة وrapidfuzz."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    try:
        from rapidfuzz import fuzz
        sa, sb = clean_text(a), clean_text(b)
        r = max(fuzz.token_set_ratio(sa, sb), fuzz.token_sort_ratio(sa, sb)) / 100.0
        return r
    except Exception:
        inter = len(ta & tb)
        return inter / max(len(ta), len(tb))
