"""Welcome card of Tiamat Network (1200x450 PNG): avatar, name, member number, brand art.

    python -m utils.tiamat_card <out.png> <name> [number] [avatar.png|-]     preview one card
"""
import datetime as dt, io, os, sys, unicodedata
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from fontTools.ttLib import TTFont

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "tiamat")
F = os.path.join(BASE, "fonts")
# fonts not shipped in the repo (big): looked up in the system (Docker installs the emoji one)
SYSTEM_FONTS = ["/usr/share/fonts/truetype/noto", "/usr/share/fonts/noto", "/usr/share/fonts/noto-cjk",
                "/usr/share/fonts/opentype/noto"]
W, H = 1200, 450
NIGHT = (14, 11, 22)
GOLD, GOLD_LT, GOLD_DK = (217, 162, 59), (242, 193, 78), (90, 63, 18)
PURPLE, PURPLE_LT = (106, 47, 168), (140, 63, 214)
TEAL, SAND_LT = (47, 181, 166), (236, 226, 200)
OPENING = dt.datetime(2026, 11, 1, 1, 30, tzinfo=dt.timezone.utc)  # 31/10 19:30 Mexico
SEASONAL_END = dt.datetime(2026, 11, 3, tzinfo=dt.timezone.utc)    # Halloween touch off after this

# fallback chain for display names: brand font first, then wide-coverage fonts, emoji last
CHAIN = ["Syne.ttf", "NotoSans-Bold.ttf", "NotoSansSymbols-Bold.ttf", "NotoSansSymbols2-Regular.ttf",
         "NotoSansCJK-Bold.ttc", "NotoColorEmoji.ttf"]
EMOJI = "NotoColorEmoji.ttf"
JOINERS = {0x200D, 0xFE0F, 0xFE0E, 0x20E3} | set(range(0x1F3FB, 0x1F400)) | set(range(0xE0020, 0xE0080))
_cmaps = {}


def path(name):
    for d in [F, *SYSTEM_FONTS]:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def cmap(name):
    if name not in _cmaps:
        p = path(name)
        _cmaps[name] = set(TTFont(p, fontNumber=0).getBestCmap()) if p else set()
    return _cmaps[name]


def font(name, size, weight=None):
    f = ImageFont.truetype(path(name), size, index=0)
    if weight:
        axes = f.get_variation_axes()
        f.set_variation_by_axes([weight if a["name"] == b"Weight" else a["default"] for a in axes])
    return f


def runs(text):
    """Split text into (font name, chunk) runs; unsupported chars are NFKC-folded or dropped."""
    out = []
    for i, ch in enumerate(text):
        cp = ord(ch)
        if cp in JOINERS and out and out[-1][0] == EMOJI:
            out[-1][1].append(ch)
            continue
        nxt = ord(text[i + 1]) if i + 1 < len(text) else 0
        wants_emoji = cp >= 0x1F000 or nxt in (0xFE0F, 0x20E3) or (out and out[-1][0] == EMOJI and out[-1][1][-1] == "\u200d")
        pick = EMOJI if wants_emoji and cp in cmap(EMOJI) else next((n for n in CHAIN if cp in cmap(n)), None)
        if pick in (None, *CHAIN[1:5]) and not unicodedata.category(ch).startswith("Z"):
            folded = unicodedata.normalize("NFKC", ch)
            if folded != ch and folded and all(ord(c) in cmap(CHAIN[0]) for c in folded):
                ch, pick = folded, CHAIN[0]
        if pick is None or unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cn"):
            continue
        if out and out[-1][0] == pick:
            out[-1][1].append(ch)
        else:
            out.append([pick, [ch]])
    return [(n, "".join(c)) for n, c in out]


def render_runs(rs, size, color):
    """Render runs to one RGBA strip of height ~1.4*size; returns image and baseline offset."""
    pieces, asc = [], int(size * 1.05)
    for name, chunk in rs:
        if name == EMOJI:
            f = ImageFont.truetype(path(EMOJI), 109)
            w = max(1, int(f.getlength(chunk)))
            im = Image.new("RGBA", (w, 136), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((0, 0), chunk, font=f, embedded_color=True)
            im = im.crop((0, 0, w, 128))
            s = size * 0.95 / 109
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            pieces.append((im, asc - int(size * 0.86)))
        else:
            f = font(name, size, 800 if name == "Syne.ttf" else None)
            a, _ = f.getmetrics()
            w = int(f.getlength(chunk)) + 2
            im = Image.new("RGBA", (w, int(size * 1.5)), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((0, 0), chunk, font=f, fill=color)
            pieces.append((im, asc - a))
    width = sum(p.width for p, _ in pieces) + 4 * max(0, len(pieces) - 1)
    strip = Image.new("RGBA", (max(1, width), int(size * 1.6)), (0, 0, 0, 0))
    x = 0
    for p, y in pieces:
        strip.alpha_composite(p, (x, max(0, y)))
        x += p.width + 4
    return strip


def _line(text, size):
    return render_runs(runs(text), size, (255, 255, 255))


def _stack(a, b, size):
    gap = int(size * 1.08)
    im = Image.new("RGBA", (max(a.width, b.width), gap + b.height), (0, 0, 0, 0))
    im.alpha_composite(a, (0, 0))
    im.alpha_composite(b, (0, gap))
    return im


def fit_name(name, maxw):
    """One line if it fits big enough, else two lines split at a space, else cut with an ellipsis."""
    name = " ".join(name.split()) or "Aventurero"
    if not runs(name):
        name = "Aventurero"
    for s in (76, 68, 60, 54):
        im = _line(name, s)
        if im.width <= maxw:
            return im, s
    words = name.split(" ")
    if len(words) > 1:
        for s in (54, 48, 42):
            best = None
            for i in range(1, len(words)):
                a, b = _line(" ".join(words[:i]), s), _line(" ".join(words[i:]), s)
                if max(a.width, b.width) <= maxw and (best is None or max(a.width, b.width) < best[0]):
                    best = (max(a.width, b.width), a, b)
            if best:
                return _stack(best[1], best[2], s), s
    for s in (48, 42, 38):
        im = _line(name, s)
        if im.width <= maxw:
            return im, s
    text = name
    while len(text) > 1:
        text = text[:-1].rstrip()
        im = _line(text + "…", 38)
        if im.width <= maxw:
            return im, 38
    return _line(text, 38), 38


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s + 0.5), int(img.height * s + 0.5)), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def hgrad(w, h, stops):
    """Horizontal alpha gradient of NIGHT; stops = [(x fraction, alpha 0-255)]."""
    row = []
    for x in range(w):
        f = x / (w - 1)
        for (f0, a0), (f1, a1) in zip(stops, stops[1:]):
            if f0 <= f <= f1:
                row.append(int(a0 + (a1 - a0) * ((f - f0) / (f1 - f0 or 1))))
                break
    mask = Image.new("L", (w, 1))
    mask.putdata(row)
    layer = Image.new("RGBA", (w, h), (*NIGHT, 255))
    layer.putalpha(mask.resize((w, h)))
    return layer


def pill(img, x, y, text, fnt, fg, fill=None, outline=None, grad=None, pad=(16, 9), emoji=None):
    d = ImageDraw.Draw(img)
    tw = int(fnt.getlength(text))
    em = None
    if emoji:
        em = render_runs([(EMOJI, emoji)], int(fnt.size * 1.15), fg)
        em = em.crop(em.getbbox())
    ew = em.width + 8 if em else 0
    h = fnt.size + pad[1] * 2
    w = tw + ew + pad[0] * 2
    box = (x, y, x + w, y + h)
    if grad:
        g = Image.new("RGBA", (w, h))
        gd = ImageDraw.Draw(g)
        for i in range(w):
            t = i / max(1, w - 1)
            gd.line([(i, 0), (i, h)], fill=tuple(int(a + (b - a) * t) for a, b in zip(*grad)) + (255,))
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=255)
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle((x + 4, y + 10, x + w - 4, y + h + 6), radius=h // 2,
                                               fill=(*PURPLE_LT, 110))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(12)))
        img.paste(g, (x, y), m)
    else:
        d.rounded_rectangle(box, radius=h // 2, fill=fill, outline=outline, width=2)
    tx = x + pad[0]
    if em:
        img.alpha_composite(em, (tx, y + (h - em.height) // 2))
        tx += ew
    d.text((tx, y + h // 2), text, font=fnt, fill=fg, anchor="lm")
    return w


def avatar_disc(raw, size):
    try:
        av = Image.open(io.BytesIO(raw)).convert("RGBA") if raw else None
    except Exception:
        av = None
    if av is None:                                     # no image at all: brand disc with the dragon
        av = Image.open(os.path.join(BASE, "emblem.png")).convert("RGBA")
    av = cover(av, size, size)
    big = size * 4
    m = Image.new("L", (big, big), 0)
    ImageDraw.Draw(m).ellipse((0, 0, big - 1, big - 1), fill=255)
    av.putalpha(m.resize((size, size), Image.LANCZOS))
    return av


def card(name, number, avatar=None, now=None, halloween=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    halloween = now < SEASONAL_END if halloween is None else halloween
    img = Image.new("RGBA", (W, H), (*NIGHT, 255))
    bg = cover(Image.open(os.path.join(BASE, "background.jpg")).convert("RGBA"), W, H)
    img.alpha_composite(bg)
    img.alpha_composite(hgrad(W, H, [(0, 40), (0.2, 70), (0.36, 200), (0.46, 242), (1, 248)]))
    vg = Image.new("L", (1, H))
    vg.putdata([int(150 * max(0, (y / H) - 0.45) / 0.55) for y in range(H)])
    shade = Image.new("RGBA", (W, H), (*NIGHT, 255))
    shade.putalpha(vg.resize((W, H)))
    img.alpha_composite(shade)

    # avatar: purple glow, gold ring, picture
    cx, cy, r = 250, 225, 128
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - r - 30, cy - r - 30, cx + r + 30, cy + r + 30), fill=(*PURPLE_LT, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(34)))
    ring = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    R = r * 2
    rd.ellipse((cx * 2 - R - 18, cy * 2 - R - 18, cx * 2 + R + 18, cy * 2 + R + 18), fill=GOLD_DK)
    rd.ellipse((cx * 2 - R - 14, cy * 2 - R - 14, cx * 2 + R + 14, cy * 2 + R + 14), fill=GOLD)
    rd.ellipse((cx * 2 - R - 14, cy * 2 - R - 14, cx * 2 + R + 14, cy * 2 + R + 6), outline=GOLD_LT, width=3)
    rd.ellipse((cx * 2 - R - 2, cy * 2 - R - 2, cx * 2 + R + 2, cy * 2 + R + 2), fill=NIGHT)
    img.alpha_composite(ring.resize((W, H), Image.LANCZOS))
    img.alpha_composite(avatar_disc(avatar, r * 2), (cx - r, cy - r))

    # number badge on the ring, like a seal
    d = ImageDraw.Draw(img)
    nf = font("Inter.ttf", 22, 800)
    label = f"Nº {number:,}".replace(",", ".") if number else "NUEVO"
    lw = int(nf.getlength(label)) + 34
    bx, by = cx - lw // 2, cy + r - 4
    d.rounded_rectangle((bx - 3, by - 3, bx + lw + 3, by + 41), radius=22, fill=NIGHT)
    d.rounded_rectangle((bx, by, bx + lw, by + 38), radius=19, fill=GOLD, outline=GOLD_LT, width=2)
    d.text((cx, by + 19), label, font=nf, fill=NIGHT, anchor="mm")

    # text column, laid out top-down and centred on the avatar
    x0, maxw = 455, W - 455 - 60
    nm, size = fit_name(name, maxw)
    bbox = nm.getbbox() or (0, 0, nm.width, nm.height)
    nm = nm.crop((0, bbox[1], bbox[2], bbox[3]))
    kick_h, gap1, sub_h, gap2, chip_h = 20, 26, 30, 30, 40
    total = kick_h + gap1 + nm.height + 26 + sub_h + gap2 + chip_h
    y = cy - total // 2 - 6
    kf = font("Inter.ttf", 17, 700)
    tx = x0
    for ch in "TE DAMOS LA BIENVENIDA A TIAMAT NETWORK":   # letter-spaced kicker
        d.text((tx, y), ch, font=kf, fill=TEAL)
        tx += kf.getlength(ch) + 2.4
    y += kick_h + gap1
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.alpha_composite(nm, (x0, y + 4))
    black = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    black.putalpha(shadow.split()[3].point(lambda a: int(a * 0.6)).filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(black)
    img.alpha_composite(nm, (x0, y))
    y += nm.height + 26
    sf = font("Inter.ttf", 25, 600)
    d.text((x0 + 2, y), "Red de servidores de Minecraft en español.", font=sf, fill=(233, 228, 243))
    y += sub_h + gap2

    # chips: opening date (seasonal) and the address
    cf = font("Inter.ttf", 19, 700)
    x = x0
    if now < OPENING:
        x += pill(img, x, y, "Abrimos el 31 de octubre", cf, (255, 255, 255),
                  grad=(PURPLE_LT, PURPLE), emoji="🎃" if halloween else "🐉") + 14
    x += pill(img, x, y, "play.tiamatmc.net", cf, (243, 226, 182), fill=(14, 11, 22, 140),
              outline=(*GOLD, 200)) + 14
    pill(img, x, y, "Java", cf, (243, 226, 182), fill=(14, 11, 22, 140), outline=(*GOLD, 200))

    # brand emblem, bottom right
    em = Image.open(os.path.join(BASE, "emblem.png")).convert("RGBA").resize((120, 120), Image.LANCZOS)
    eg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(eg).ellipse((W - 160, 20, W - 30, 150), fill=(*PURPLE_LT, 90))
    img.alpha_composite(eg.filter(ImageFilter.GaussianBlur(22)))
    img.alpha_composite(em, (W - 155, 25))

    # frame: thin gold line inside the edge
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fr).rounded_rectangle((10, 10, W - 11, H - 11), radius=18, outline=(*GOLD, 110), width=2)
    img.alpha_composite(fr)
    out = img.convert("RGB")
    m = Image.new("L", (W * 2, H * 2), 0)                # rounded outer corners
    ImageDraw.Draw(m).rounded_rectangle((0, 0, W * 2 - 1, H * 2 - 1), radius=56, fill=255)
    final = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    final.paste(out, (0, 0), m.resize((W, H), Image.LANCZOS))
    buf = io.BytesIO()
    final.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def coverage(name):
    """Share of the visible characters of `name` the card can draw (0..1)."""
    chars = [c for c in name if not c.isspace()]
    drawn = sum(len(c.replace(" ", "")) for _, c in runs(name))
    return drawn / len(chars) if chars else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    raw = open(a[3], "rb").read() if len(a) > 3 and a[3] != "-" else None
    open(a[0], "wb").write(card(a[1], int(a[2]) if len(a) > 2 else 7, raw))
    print(a[0])
