from PIL import Image, ImageDraw, ImageOps
import os

# 設定
INPUT_DIR = '.'  # カレントディレクトリ
OUTPUT_DIR = './converted'
SIZE = (64, 64)  # キャラ画像の標準サイズ
SHADOW_OFFSET = (0, 8)
SHADOW_RADIUS = 22

os.makedirs(OUTPUT_DIR, exist_ok=True)

def add_shadow(base_img, offset=SHADOW_OFFSET, radius=SHADOW_RADIUS):
    shadow = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    cx, cy = base_img.size[0] // 2 + offset[0], base_img.size[1] // 2 + offset[1]
    draw.ellipse((cx - radius, cy - radius//2, cx + radius, cy + radius//2), fill=(0, 0, 0, 70))
    return Image.alpha_composite(shadow, base_img)

def convert_image(path):
    img = Image.open(path).convert('RGBA')
    # 画像を左下向きに回転（必要なら）
    # img = img.rotate(45, expand=True)  # 必要に応じて調整
    # サイズ統一
    img = ImageOps.fit(img, SIZE, method=Image.BICUBIC, centering=(0.5, 0.7))
    # 影を合成
    img = add_shadow(img)
    # 保存
    out_path = os.path.join(OUTPUT_DIR, os.path.basename(path))
    img.save(out_path)
    print(f'変換: {path} → {out_path}')

if __name__ == '__main__':
    for fname in os.listdir(INPUT_DIR):
        if fname.lower().endswith('.png'):
            convert_image(os.path.join(INPUT_DIR, fname))
