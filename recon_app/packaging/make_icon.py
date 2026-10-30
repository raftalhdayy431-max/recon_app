"""يولّد أيقونة البرنامج (icon.ico و icon.png) برمجياً. تشغيل: python packaging/make_icon.py"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent
N = 1024


def draw() -> Image.Image:
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    # خلفية متدرّجة (أخضر مزرق)
    grad = Image.new("RGBA", (N, N))
    gp = grad.load()
    c1, c2 = (14, 148, 136), (63, 110, 181)
    for y in range(N):
        for x in range(N):
            t = (x + y) / (2 * N)
            gp[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,)
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, N - 40, N - 40), radius=230, fill=255)
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    w = 74
    white = (255, 255, 255, 255)

    def line(p, q):
        d.line([p, q], fill=white, width=w)
        for pt in (p, q):
            d.ellipse((pt[0] - w // 2, pt[1] - w // 2, pt[0] + w // 2, pt[1] + w // 2), fill=white)

    # سهمان متقابلان (رمز المطابقة)
    line((260, 400), (770, 400)); line((770, 400), (640, 270)); line((770, 400), (640, 530))
    line((764, 640), (254, 640)); line((254, 640), (384, 510)); line((254, 640), (384, 770))
    return im


if __name__ == "__main__":
    img = draw()
    img.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
    img.save(OUT / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)])
    print("icon.ico / icon.png OK")
