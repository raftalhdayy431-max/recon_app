"""مولّد بيانات تجريبية — الاستخدام:  python tools/make_sample.py [مجلد_الإخراج]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.sample import make  # noqa: E402,F401

if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "sample_data"
    a, b = make(folder)
    print(a)
    print(b)
