"""
キャラクター画像の背景除去 + 64x64スプライト生成スクリプト
出力先: converted/ ディレクトリ

使い方:
  python prepare_sprites.py          # 全スプライト処理
  python prepare_sprites.py knight   # knight だけ再処理
"""
from PIL import Image, ImageFilter
import numpy as np
import os
import sys
from collections import deque

INPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(INPUT_DIR, "converted")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SPRITE_SIZE = 64

# 元ファイル名 → (出力ファイル名, 背景除去モード, tolerance)
# mode:
#   "threshold"  単純距離閾値（白背景など均一な場合）
#   "floodfill"  四隅BFS（白/均一な背景）
#   "chroma"     RGBのstd閾値（グレー背景に色付きキャラ）
#   "oval"       キャラbbox中心を楕円マスクで切り抜き（背景除去困難な場合）
FILES = {
    "knight.png":        ("knight.png",        "oval",       8),
    "mage.png":          ("mage.png",           "floodfill",  40),
    "warior.png":        ("knight_old.png",     "floodfill",  50),
    "sennshi.png":       ("warior.png",          "oval",        8),
    "masician.png":      ("mage_old.png",       "threshold",  40),
    "rogue.png":         ("rogue.png",          "threshold",  40),
    "pest.png":          ("plague_doctor.png",  "threshold",  40),
    "lightning_mage.png":("lightning_mage.png", "threshold",  40),
    "valley_wraith.png": ("valley_wraith.png",  "threshold",  40),
}


# ─── 背景色の推定 ────────────────────────────────────────────
def _estimate_bg(data: np.ndarray) -> np.ndarray:
    """4辺のピクセル中央値を背景色として返す。"""
    h, w = data.shape[:2]
    border = np.concatenate([
        data[0,   :, :3].reshape(-1, 3),
        data[h-1, :, :3].reshape(-1, 3),
        data[:,   0, :3].reshape(-1, 3),
        data[:, w-1, :3].reshape(-1, 3),
    ])
    return np.median(border, axis=0)


# ─── 方法0: 楕円マスク（背景除去が難しい場合のフォールバック）──────
def remove_bg_oval(img: Image.Image, std_threshold: float = 8.0) -> Image.Image:
    """
    colored pixel（RGBのstd > std_threshold）のbboxを検出し、
    その中心に楕円マスクを適用する。背景除去ではなく形状クロップ。
    """
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)
    std = data[:, :, :3].std(axis=2)
    mask = std > std_threshold
    ys, xs = np.where(mask)
    if len(xs) == 0:
        cx, cy = img.width // 2, img.height // 2
        rx, ry = img.width // 2, img.height // 2
    else:
        cx = int(xs.mean()); cy = int(ys.mean())
        half = max(xs.max() - xs.min(), ys.max() - ys.min()) // 2 + 20
        rx = ry = half

    # 正方形クロップ
    left  = max(0, cx - rx)
    top   = max(0, cy - ry)
    right = min(img.width,  cx + rx)
    bot   = min(img.height, cy + ry)
    cropped = img.crop((left, top, right, bot))

    # 楕円マスク生成（numpy ベクトル化）
    cw, ch = cropped.size
    xs2 = (np.arange(cw) - cw / 2) / (cw / 2)
    ys2 = (np.arange(ch) - ch / 2) / (ch / 2)
    xx, yy = np.meshgrid(xs2, ys2)
    d = xx*xx + yy*yy
    alpha = np.clip((1.0 - d) * 2.2, 0.0, 1.0)
    alpha_u8 = (alpha * 255).astype(np.uint8)
    alpha_img = Image.fromarray(alpha_u8, "L").filter(ImageFilter.GaussianBlur(radius=2))

    r, g, b, _ = cropped.split()
    return Image.merge("RGBA", (r, g, b, alpha_img))


# ─── 方法0: クロマキー（RGBの偏差でグレー背景を除去）────────────
def remove_bg_chroma(img: Image.Image, std_threshold: float = 12.0) -> Image.Image:
    """
    各ピクセルの R/G/B 標準偏差が小さい（グレーに近い）ほど透明にする。
    グレー背景に色付きキャラクターが描かれた画像向け。
    """
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)
    std = data[:, :, :3].std(axis=2)               # 0≒グレー、高い≒有彩色
    feather = std_threshold * 0.8
    raw_alpha = np.clip((std - (std_threshold - feather)) * (255.0 / feather), 0, 255)
    result = np.array(img)
    result[:, :, 3] = raw_alpha.astype(np.uint8)
    out = Image.fromarray(result)
    r, g, b, a = out.split()
    a = a.filter(ImageFilter.GaussianBlur(radius=max(1, img.width // 512)))
    return Image.merge("RGBA", (r, g, b, a))


# ─── 方法1: 単純距離閾値 ─────────────────────────────────────
def remove_bg_threshold(img: Image.Image, tolerance: float = 40.0) -> Image.Image:
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)
    bg = _estimate_bg(data)
    dist = np.sqrt(((data[:, :, :3] - bg) ** 2).sum(axis=2))
    feather = 18.0
    raw_alpha = np.clip((dist - (tolerance - feather)) * (255.0 / feather), 0, 255)
    result = np.array(img)
    result[:, :, 3] = raw_alpha.astype(np.uint8)
    out = Image.fromarray(result)
    r, g, b, a = out.split()
    a = a.filter(ImageFilter.GaussianBlur(radius=1))
    return Image.merge("RGBA", (r, g, b, a))


# ─── 方法2: BFS flood fill（四隅から連結した背景を除去）────────
def remove_bg_floodfill(img: Image.Image, tolerance: float = 50.0,
                        work_size: int = 256) -> Image.Image:
    """
    四隅から BFS でつながる「背景色に近いピクセル」を透明化。
    work_size px の中間サイズで BFS・クロップ・アルファ適用を完結させる。
    """
    orig_w, orig_h = img.size

    # 中間サイズにリサイズ（長辺 work_size px）
    scale = work_size / max(orig_w, orig_h)
    bfs_w = max(1, int(orig_w * scale))
    bfs_h = max(1, int(orig_h * scale))
    small = img.convert("RGBA").resize((bfs_w, bfs_h), Image.LANCZOS)
    data_s = np.array(small, dtype=np.float32)
    bg = _estimate_bg(data_s)

    # BFS マスク（True = 背景）
    mask = np.zeros((bfs_h, bfs_w), dtype=bool)
    queue = deque()

    def _try_seed(x, y):
        if not mask[y, x]:
            d = float(np.sqrt(((data_s[y, x, :3] - bg) ** 2).sum()))
            if d < tolerance:
                mask[y, x] = True
                queue.append((x, y))

    for x in range(bfs_w):
        _try_seed(x, 0); _try_seed(x, bfs_h - 1)
    for y in range(bfs_h):
        _try_seed(0, y); _try_seed(bfs_w - 1, y)

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < bfs_w and 0 <= ny < bfs_h and not mask[ny, nx]:
                d = float(np.sqrt(((data_s[ny, nx, :3] - bg) ** 2).sum()))
                if d < tolerance:
                    mask[ny, nx] = True
                    queue.append((nx, ny))

    # 背景マスクを 1px 膨張させてエッジを綺麗に
    from PIL import ImageFilter as _IF
    alpha_raw = np.where(mask, np.uint8(0), np.uint8(255))
    alpha_img = Image.fromarray(alpha_raw, "L").filter(_IF.GaussianBlur(radius=1))

    r, g, b, _ = small.split()
    return Image.merge("RGBA", (r, g, b, alpha_img))


# ─── 正方形クロップ ──────────────────────────────────────────
def crop_to_content(img: Image.Image, margin: int = 6) -> Image.Image:
    bbox = img.getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    side = max(x1 - x0, y1 - y0) + margin * 2
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    left  = max(0, cx - side // 2)
    top   = max(0, cy - side // 2)
    right = min(img.width,  left + side)
    bot   = min(img.height, top  + side)
    return img.crop((left, top, right, bot))


# ─── メイン処理 ──────────────────────────────────────────────
def process(src_name: str, dst_name: str, mode: str, tolerance: float):
    src = os.path.join(INPUT_DIR, src_name)
    dst = os.path.join(OUTPUT_DIR, dst_name)
    if not os.path.exists(src):
        print(f"  [SKIP] {src_name} not found")
        return

    print(f"  {src_name} → {dst_name} (mode={mode}, tol={tolerance}) ...", end=" ", flush=True)
    img = Image.open(src).convert("RGBA")

    if mode == "floodfill":
        img = remove_bg_floodfill(img, tolerance=tolerance)
    elif mode == "chroma":
        img = remove_bg_chroma(img, std_threshold=tolerance)
    elif mode == "oval":
        img = remove_bg_oval(img, std_threshold=tolerance)
    else:
        img = remove_bg_threshold(img, tolerance=tolerance)

    if mode != "oval":
        img = crop_to_content(img, margin=6)
    img = img.resize((SPRITE_SIZE, SPRITE_SIZE), Image.LANCZOS)
    img.save(dst)
    print("OK")


if __name__ == "__main__":
    target = sys.argv[1].lower() if len(sys.argv) > 1 else None
    print("=== キャラスプライト生成 ===")
    for src, (dst, mode, tol) in FILES.items():
        key = src.replace(".png", "")
        if target and target not in (key, dst.replace(".png", "")):
            continue
        process(src, dst, mode, tol)
    print("完了 →", OUTPUT_DIR)
