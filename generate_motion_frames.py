from PIL import Image, ImageDraw, ImageOps
import os

# 設定
INPUT_DIR = '.'  # キャラ立ち絵のあるディレクトリ
OUTPUT_DIR = './motion_frames'
SIZE = (64, 64)
SHADOW_OFFSET = (0, 8)
SHADOW_RADIUS = 22
FRAME_COUNT = 4  # 各モーションのフレーム数

os.makedirs(OUTPUT_DIR, exist_ok=True)

def add_shadow(base_img, offset=SHADOW_OFFSET, radius=SHADOW_RADIUS):
    shadow = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    cx, cy = base_img.size[0] // 2 + offset[0], base_img.size[1] // 2 + offset[1]
    draw.ellipse((cx - radius, cy - radius//2, cx + radius, cy + radius//2), fill=(0, 0, 0, 70))
    return Image.alpha_composite(shadow, base_img)

def make_motion_frames(img, motion, base_name):
    for i in range(FRAME_COUNT):
        frame = img.copy()
        # --- 簡易モーション例 ---
        if motion == 'idle':
            # 待機: 体を上下にゆらす
            offset = int(3 * (i % 2))
            frame = ImageOps.fit(frame, SIZE, method=Image.BICUBIC, centering=(0.5, 0.7-offset/32))
        elif motion == 'walk':
            # 歩き: 左右に少し傾ける
            angle = (-10 if i%2==0 else 10) if i<2 else (5 if i==2 else -5)
            frame = frame.rotate(angle, resample=Image.BICUBIC, expand=0)
            frame = ImageOps.fit(frame, SIZE, method=Image.BICUBIC, centering=(0.5, 0.7))
        elif motion == 'attack':
            # 攻撃: 少し拡大＋上にジャンプ
            scale = 1.1 if i%2==0 else 1.0
            jump = -8 if i%2==0 else 0
            w, h = frame.size
            frame = frame.resize((int(w*scale), int(h*scale)), resample=Image.BICUBIC)
            frame = ImageOps.fit(frame, SIZE, method=Image.BICUBIC, centering=(0.5, 0.7 + jump/64))
        # 影を合成
        frame = add_shadow(frame)
        out_name = f"{base_name}_{motion}_{i}.png"
        frame.save(os.path.join(OUTPUT_DIR, out_name))
        print(f"生成: {out_name}")

def main():
    for fname in os.listdir(INPUT_DIR):
        if fname.lower().endswith('.png'):
            img = Image.open(os.path.join(INPUT_DIR, fname)).convert('RGBA')
            base_name = os.path.splitext(fname)[0]
            for motion in ['idle', 'walk', 'attack']:
                make_motion_frames(img, motion, base_name)

if __name__ == '__main__':
    main()
