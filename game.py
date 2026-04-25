import pygame
import math
import random
import sys
import os
import array as arr
import numpy as np

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
pygame.key.stop_text_input()  # IMEによるキー横取りを無効化

W, H = 1280, 720
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Vampire Survivors Like  [3D ISO]")
clock = pygame.time.Clock()

WHITE  = (255, 255, 255)
BLACK  = (0,   0,   0)
RED    = (220, 50,  50)
GREEN  = (50,  200, 80)
BLUE   = (50,  100, 220)
YELLOW = (255, 220, 0)
PURPLE = (180, 50,  220)
GRAY   = (120, 120, 120)
DARK   = (6,   6,   10)     # near-black bg
ORANGE = (255, 140, 0)
CYAN   = (0,   200, 220)
GOLD   = (255, 200, 0)
LIME   = (130, 255, 50)

# ─────────────────────────────────────────────
# Terrain system
# ─────────────────────────────────────────────
TERRAIN_GRASS    = 0
TERRAIN_MAGMA    = 1
TERRAIN_ICE      = 2
TERRAIN_SWAMP    = 3
TERRAIN_VALLEY   = 4
TERRAIN_MOUNTAIN = 5

TILE_STEP    = 80
ZONE_SIZE    = 5   # tiles per zone side
TERRAIN_WEIGHTS = [48, 10, 12, 10, 3, 17]

TERRAIN_COLS = {
    TERRAIN_GRASS:    [(28, 75, 28),   (22, 60, 22)],
    TERRAIN_MAGMA:    [(170, 45,  0),  (210, 70,  5)],
    TERRAIN_ICE:      [(105,175,225),  (130,200,250)],
    TERRAIN_SWAMP:    [(62,  46, 28),  (50,  36, 20)],
    TERRAIN_VALLEY:   [(14,  11, 20),  ( 9,   7, 14)],
    TERRAIN_MOUNTAIN: [(72,  66, 56),  (92,  86, 72)],
}

# 3D box wall heights (pixels) and face colors per terrain type
TERRAIN_WALL_H = {
    TERRAIN_GRASS:    12,
    TERRAIN_MAGMA:    16,
    TERRAIN_ICE:      10,
    TERRAIN_SWAMP:     8,
}
# (left_face_color, right_face_color)  ← left is more shadowed
TERRAIN_WALL_COLS = {
    TERRAIN_GRASS:  ((14, 42, 14),   (20, 58, 20)),
    TERRAIN_MAGMA:  ((100, 22,  0),  (135, 32,  0)),
    TERRAIN_ICE:    ((60, 110, 160), (80, 140, 195)),
    TERRAIN_SWAMP:  ((30, 22, 10),   (42, 32, 16)),
}

TERRAIN_LABELS = {
    TERRAIN_GRASS:    "草原",
    TERRAIN_MAGMA:    "マグマ  HP減少 / 敵増加！",
    TERRAIN_ICE:      "氷地帯  滑る！",
    TERRAIN_SWAMP:    "沼地  速度低下",
    TERRAIN_VALLEY:   "谷  落下中...",
    TERRAIN_MOUNTAIN: "山岳  通行不可",
}

TERRAIN_HUD_COLS = {
    TERRAIN_GRASS:    (80, 200, 80),
    TERRAIN_MAGMA:    (255, 100, 0),
    TERRAIN_ICE:      (150, 210, 255),
    TERRAIN_SWAMP:    (80, 160, 60),
    TERRAIN_VALLEY:   (160, 90, 255),
    TERRAIN_MOUNTAIN: (180, 160, 130),
}

class TerrainMap:
    def __init__(self, seed=None):
        self._cache = {}
        self._seed  = seed if seed is not None else random.randint(0, 999999)

    def _zone_type(self, zx, zy):
        key = (zx, zy)
        if key not in self._cache:
            if abs(zx)<=1 and abs(zy)<=1:   # starting area is always grass
                self._cache[key] = TERRAIN_GRASS
            else:
                rng = random.Random(self._seed ^ (zx * 73856093 & 0x7FFFFFFF) ^ (zy * 19349663 & 0x7FFFFFFF))
                w = list(TERRAIN_WEIGHTS)
                # 隣接ゾーンが確定済みの場合、valley↔mountain の直接隣接を防ぐ
                for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
                    nb = self._cache.get((zx+dx, zy+dy))
                    if nb == TERRAIN_VALLEY:   w[TERRAIN_MOUNTAIN] = 0
                    elif nb == TERRAIN_MOUNTAIN: w[TERRAIN_VALLEY]  = 0
                if sum(w) == 0: w = list(TERRAIN_WEIGHTS)
                self._cache[key] = rng.choices(range(6), weights=w)[0]
        return self._cache[key]

    def get(self, gx, gy):
        return self._zone_type(gx // ZONE_SIZE, gy // ZONE_SIZE)

    def world_to_tile(self, wx, wy):
        return int(math.floor(wx / TILE_STEP)), int(math.floor(wy / TILE_STEP))

    def at(self, wx, wy):
        return self.get(*self.world_to_tile(wx, wy))

# Underground UI palette
UI_BG    = (10,  8,  18)    # panel background
UI_MID   = (20, 16,  32)    # panel mid-tone
UI_GRID  = (18, 14,  28)    # grid lines
NEON_P   = (155,  0, 245)   # neon purple
NEON_G   = (0,  210,  80)   # acid green
NEON_R   = (215, 15,  50)   # blood red
NEON_B   = (0,  180, 255)   # electric blue
NEON_Y   = (255,185,   0)   # amber gold

# ── Global volume state ──────────────────────
_vol_bgm = 0.55   # 0.0 – 1.0
_vol_sfx = 0.80

# Kenney voxel tile images, loaded by build_sprites()
_TERRAIN_TILES: dict = {}   # terrain_id → scaled pygame.Surface
_AXE_IMG: pygame.Surface | None = None    # ax_transparent.png, loaded by build_sprites()
_KYONSI_IMG: pygame.Surface | None = None # kyonsi_t.png, loaded by build_sprites()

# ── 炎動画フレーム ──────────────────────────────
FLAME_FRAMES: list = []   # pygame.Surface list (SRCALPHA, brightness-as-alpha)
FLAME_FPS: float  = 24.0

# ── 魔法弾動画フレーム ──────────────────────────
BULLET_FRAMES: list = []  # pygame.Surface list (SRCALPHA, brightness-as-alpha)
BULLET_FPS: float   = 30.0
GUN_BULLET_IMG = None   # bullet.jpg を背景透過して保持
_FLAME_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "nc471870_【フルHDループ素材】炎がメラメラ燃えるエフェクト素材用のテクスチャ背景動画（ループ素材）.mp4")
_BULLET_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "nc131866_弾_弾道_銃弾_エフェクト_閃光.mp4")

# ── 光の雨動画フレーム ──────────────────────────
RAIN_FRAMES: list = []
RAIN_FPS: float   = 30.0
_RAIN_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "nc268423_「光の雨」_素材_モーション_エフェクト_CG.mp4")

def _load_video_frames(path, size, max_sec=None, srcalpha_brightness=True):
    """共通: MP4フレームをサーフェスリストとして返す。戻り値は (fps, frames)。
    srcalpha_brightness=True のとき明るさをアルファに変換（炎用）。"""
    import cv2
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    max_frames = int(fps * max_sec) if max_sec else None
    frames = []
    while True:
        if max_frames and len(frames) >= max_frames:
            break
        ret, bgr = cap.read()
        if not ret:
            break
        rgb   = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb   = cv2.resize(rgb, size, interpolation=cv2.INTER_LINEAR)
        rgb_t = rgb.swapaxes(0, 1)
        if srcalpha_brightness:
            brightness = np.max(rgb_t, axis=2).astype(np.uint8)
            srf = pygame.Surface(size, pygame.SRCALPHA)
            srf.blit(pygame.surfarray.make_surface(rgb_t), (0, 0))
            av = pygame.surfarray.pixels_alpha(srf)
            av[:] = brightness
            del av
        else:
            srf = pygame.Surface(size)
            srf.blit(pygame.surfarray.make_surface(rgb_t), (0, 0))
        frames.append(srf)
    cap.release()
    return fps, frames

def _load_flame_video():
    global FLAME_FRAMES, FLAME_FPS
    try:
        FLAME_FPS, FLAME_FRAMES = _load_video_frames(_FLAME_VIDEO, (256, 144))
    except Exception as e:
        print(f"[flame video] load error: {e}")

def _load_bullet_video():
    global BULLET_FRAMES, BULLET_FPS
    try:
        # 縦型 480x540 → 64x72 で読み込み（進行方向に回転して使用）
        BULLET_FPS, BULLET_FRAMES = _load_video_frames(_BULLET_VIDEO, (64, 72))
    except Exception as e:
        print(f"[bullet video] load error: {e}")

def _load_gun_bullet_image():
    """bullet.jpg を読み込んで白背景を透過処理し、先端が右を向くよう回転後スケールしてキャッシュ。"""
    global GUN_BULLET_IMG
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bullet.jpg")
        raw = pygame.image.load(path).convert()
        w, h = raw.get_size()
        # SRCALPHA サーフェスに変換して白/明るい背景をアルファ0にする
        result = pygame.Surface((w, h), pygame.SRCALPHA)
        raw_arr = pygame.surfarray.pixels3d(raw)
        brightness = (raw_arr[:, :, 0].astype(np.int32)
                      + raw_arr[:, :, 1].astype(np.int32)
                      + raw_arr[:, :, 2].astype(np.int32))
        alpha_arr = np.zeros((w, h), dtype=np.uint8)
        alpha_arr[brightness < 630] = 255   # 弾丸本体（暗いピクセル）は不透明
        alpha_arr[brightness >= 630] = 0    # 白背景（明るいピクセル）は透明
        dst = pygame.surfarray.pixels_alpha(result)
        dst[:] = alpha_arr
        del dst
        rgb_dst = pygame.surfarray.pixels3d(result)
        rgb_dst[:] = raw_arr
        del rgb_dst
        # bullet.jpg は縦向き（先端が下）なので 90° 反時計回り回転 → 先端が右を向く
        # pygame.transform.rotate(surf, 90) = 90° CCW: 下→右 になる
        rotated = pygame.transform.rotate(result, 90)
        # ゲーム内表示サイズにスケール（横長の弾丸）
        GUN_BULLET_IMG = pygame.transform.smoothscale(rotated, (20, 7))
        print("[gun bullet] image loaded OK")
    except Exception as e:
        print(f"[gun bullet image] load error: {e}")

def _load_rain_video():
    global RAIN_FRAMES, RAIN_FPS
    try:
        RAIN_FPS, RAIN_FRAMES = _load_video_frames(_RAIN_VIDEO, (320, 320), srcalpha_brightness=False)
    except Exception as e:
        print(f"[rain video] load error: {e}")

KNIFE_SPRITE = None   # ローグSP用ナイフスプライト
_KNIFE_SIZE  = 52     # 表示基本サイズ(px)

def _load_knife_sprite():
    global KNIFE_SPRITE
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nife.webp")
        raw  = pygame.image.load(path).convert_alpha()
        # 白背景を透過処理（RGB全て220以上のピクセルをアルファ0に）
        rgb_arr = pygame.surfarray.pixels3d(raw)
        alp_arr = pygame.surfarray.pixels_alpha(raw)
        white_mask = (rgb_arr[:,:,0] > 220) & (rgb_arr[:,:,1] > 220) & (rgb_arr[:,:,2] > 220)
        alp_arr[white_mask] = 0
        del rgb_arr, alp_arr
        KNIFE_SPRITE = pygame.transform.smoothscale(raw, (_KNIFE_SIZE, _KNIFE_SIZE))
    except Exception as e:
        print(f"[knife sprite] load error: {e}")

WARRIOR_SP_FRAMES: list = []
WARRIOR_SP_FPS: float = 30.0
_WARRIOR_SP_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "戦士SP技.mp4")

_WARRIOR_SP_LOAD_SIZE = (640, 360)  # メモリ節約のため縮小して読み込み

def _load_warrior_sp_video():
    global WARRIOR_SP_FRAMES, WARRIOR_SP_FPS
    try:
        import cv2
        cap = cv2.VideoCapture(_WARRIOR_SP_VIDEO)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        WARRIOR_SP_FPS = fps
        max_frames = int(fps * 2.5)  # 最大2.5秒分
        lw, lh = _WARRIOR_SP_LOAD_SIZE
        frames = []
        while len(frames) < max_frames:
            ret, bgr = cap.read()
            if not ret: break
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (lw, lh), interpolation=cv2.INTER_LINEAR)
            rgb_t = rgb.swapaxes(0, 1)
            srf = pygame.Surface((lw, lh), pygame.SRCALPHA)
            srf.blit(pygame.surfarray.make_surface(rgb_t), (0, 0))
            frames.append(srf)
        cap.release()
        WARRIOR_SP_FRAMES = frames
        print(f"[warrior SP video] {len(frames)} frames loaded at {lw}x{lh}")
    except Exception as e:
        print(f"[warrior SP video] load error: {e}")

# ── 魔法使いSP動画 ──────────────────────────────────────────
MAGE_METEOR_FRAMES: list = []
MAGE_METEOR_FPS: float = 30.0
_MAGE_METEOR_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "nc274695_CGの隕石アニメーション_その３.mp4")

MAGE_IMPACT_FRAMES: list = []
MAGE_IMPACT_FPS: float = 30.0
_MAGE_IMPACT_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "nc129933_衝撃波・インパクト・爆風系アニメーション【斜め視点バージョン】_1080hd.mp4")

# ── ガンマンSP レティクル動画 ────────────────────────────────
RETICLE_FRAMES: list = []
RETICLE_FPS: float = 30.0
_RETICLE_VIDEO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "nc470868_狙撃用レティクル.mp4")

def _load_reticle_video():
    global RETICLE_FRAMES, RETICLE_FPS
    try:
        RETICLE_FPS, RETICLE_FRAMES = _load_video_frames(
            _RETICLE_VIDEO, (W, H), srcalpha_brightness=False)
        print(f"[reticle video] {len(RETICLE_FRAMES)} frames loaded")
    except Exception as e:
        print(f"[reticle video] load error: {e}")

def _load_mage_sp_videos():
    global MAGE_METEOR_FRAMES, MAGE_METEOR_FPS, MAGE_IMPACT_FRAMES, MAGE_IMPACT_FPS
    try:
        MAGE_METEOR_FPS, MAGE_METEOR_FRAMES = _load_video_frames(
            _MAGE_METEOR_VIDEO, (640, 360), max_sec=4.0, srcalpha_brightness=False)
    except Exception as e:
        print(f"[mage meteor video] load error: {e}")
    try:
        MAGE_IMPACT_FPS, MAGE_IMPACT_FRAMES = _load_video_frames(
            _MAGE_IMPACT_VIDEO, (400, 225), max_sec=3.0, srcalpha_brightness=False)
    except Exception as e:
        print(f"[mage impact video] load error: {e}")

_YU_GOTH_B = "C:/Windows/Fonts/YuGothB.ttc"
font_large = pygame.font.Font(_YU_GOTH_B, 52)
font_med   = pygame.font.Font(_YU_GOTH_B, 28)
font_small = pygame.font.Font(_YU_GOTH_B, 18)
font_tiny  = pygame.font.Font(_YU_GOTH_B, 14)


def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def norm(dx, dy):
    d = math.hypot(dx, dy)
    return (dx/d, dy/d) if d else (0.0, 0.0)


# ─────────────────────────────────────────────
# Isometric 3D projection helpers
# ─────────────────────────────────────────────
ISO_SX = 0.65    # horizontal spread per world unit
ISO_SY = 0.325   # vertical compression per world unit (2:1 classic iso)

def iso_pos(wx, wy, wz, ox, oy):
    """World (wx,wy,wz) → screen (sx,sy) via isometric projection."""
    dx, dy = wx - ox, wy - oy
    sx = int((dx - dy) * ISO_SX + W / 2)
    sy = int((dx + dy) * ISO_SY + H / 2 - wz)
    return sx, sy

def apply_3d_shading(spr: pygame.Surface) -> pygame.Surface:
    """スプライトに右側シェーディング・スペキュラー・底部AO を焼き込む（起動時1回）。"""
    sw, sh = spr.get_size()
    out = spr.copy()

    # 右側シェーディング（等角光源：左上から）
    shade = pygame.Surface((sw, sh), pygame.SRCALPHA)
    shade.fill((255, 255, 255, 255))          # 白=変化なし
    for x in range(sw):
        t = x / max(sw - 1, 1)
        if t > 0.30:
            v = int(255 * (1.0 - 0.50 * ((t - 0.30) / 0.70) ** 1.6))
            pygame.draw.line(shade, (v, v, v, 255), (x, 0), (x, sh))
    out.blit(shade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # スペキュラーハイライト（左上の小さな明るい楕円）
    hl = pygame.Surface((sw, sh), pygame.SRCALPHA)
    hr = max(sw // 7, 3)
    pygame.draw.ellipse(hl, (255, 255, 255, 75),
                        (sw // 4 - hr, sh // 6 - hr // 2, hr * 2, hr))
    out.blit(hl, (0, 0))

    # 底部アンビエントオクルージョン（足元を暗く）
    # ※ BLEND_RGBA_MULT は (0,0,0,0) でアルファを消してしまうため白で初期化必須
    ao = pygame.Surface((sw, sh), pygame.SRCALPHA)
    ao.fill((255, 255, 255, 255))
    for y in range(sh // 3):
        t = y / (sh // 3)
        v = int(255 * (1.0 - 0.35 * (1 - t) ** 1.4))
        pygame.draw.line(ao, (v, v, v, 255), (0, sh - 1 - y), (sw - 1, sh - 1 - y))
    out.blit(ao, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    return out


_enemy_outline_cache: dict = {}   # sprite_key → outline surface


def get_enemy_outline(key: str, spr: pygame.Surface) -> pygame.Surface:
    """スプライトの輪郭線（暗いシルエット）をキャッシュして返す。"""
    if key not in _enemy_outline_cache:
        ol = spr.copy()
        ol.fill((15, 10, 20, 255), special_flags=pygame.BLEND_RGBA_MULT)
        _enemy_outline_cache[key] = ol
    return _enemy_outline_cache[key]


def draw_shadow(surf, wx, wy, ox, oy, r, alpha=60):
    """Draw an elliptical ground shadow at world position (wx,wy)."""
    sx, sy = iso_pos(wx, wy, 0, ox, oy)
    sw = max(4, int(r * 1.6))
    sh = max(2, int(r * 0.55))
    ss = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.ellipse(ss, (0, 0, 0, alpha), (0, 0, sw, sh))
    surf.blit(ss, (sx - sw // 2, sy - sh // 2))


# ─────────────────────────────────────────────
# Sprite generation
# ─────────────────────────────────────────────
def _draw_knight(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0,0,0,55), (cx-18,size-12,36,10))
    pygame.draw.rect(s, (45,60,150),  (cx-13,40,11,16), border_radius=3)
    pygame.draw.rect(s, (45,60,150),  (cx+2, 40,11,16), border_radius=3)
    pygame.draw.rect(s, (38,28,18),   (cx-14,50,13,10), border_radius=2)
    pygame.draw.rect(s, (38,28,18),   (cx+1, 50,13,10), border_radius=2)
    pygame.draw.rect(s, (70,95,190),  (cx-15,22,30,22), border_radius=5)
    pygame.draw.rect(s, (115,148,230),(cx-9,24,18,12),  border_radius=3)
    pygame.draw.rect(s, (45,60,150),  (cx-15,22,30,22), 2, border_radius=5)
    pts = [(cx-22,24),(cx-27,29),(cx-25,41),(cx-18,45),(cx-16,41),(cx-16,24)]
    pygame.draw.polygon(s, (210,182,45), pts)
    pygame.draw.polygon(s, (160,135,22), pts, 2)
    pygame.draw.circle(s, (160,135,22), (cx-21,34), 3)
    pygame.draw.rect(s, (195,200,215),(cx+19,11,5,30))
    pygame.draw.rect(s, (145,115,42), (cx+15,27,13,5))
    pygame.draw.rect(s, (105,78,28),  (cx+17,32,9,8))
    pygame.draw.rect(s, (185,165,60), (cx+19,39,5,4))
    pygame.draw.line(s, (230,238,255),(cx+21,12),(cx+21,26),1)
    pygame.draw.ellipse(s,(70,95,190),(cx-13,5,26,22))
    pygame.draw.rect(s, (22,32,80),  (cx-9,14,18,8), border_radius=2)
    pygame.draw.line(s, (14,22,60),  (cx-9,18),(cx+9,18),1)
    pygame.draw.ellipse(s,(120,155,235),(cx-8,7,9,6))
    pygame.draw.ellipse(s,(45,60,150),(cx-13,5,26,22),2)
    return s

def _draw_mage(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s,(0,0,0,55),(cx-16,size-12,32,10))
    robe = [(cx-14,22),(cx+14,22),(cx+18,58),(cx-18,58)]
    pygame.draw.polygon(s,(115,42,168),robe)
    pygame.draw.polygon(s,(145,62,198),[(cx-6,22),(cx+6,22),(cx+4,44),(cx-4,44)])
    pygame.draw.polygon(s,(88,25,132), robe, 2)
    pygame.draw.polygon(s,(205,165,52),[(cx-18,54),(cx+18,54),(cx+18,58),(cx-18,58)])
    pygame.draw.rect(s,(102,72,32),(cx+15,8,5,50))
    pygame.draw.circle(s,(52,205,255),(cx+17,8),8)
    pygame.draw.circle(s,(155,235,255),(cx+15,6),4)
    pygame.draw.circle(s,(0,155,225),(cx+17,8),8,2)
    pygame.draw.ellipse(s,(242,205,162),(cx-10,13,20,18))
    pygame.draw.circle(s,(82,42,125),(cx-4,19),3)
    pygame.draw.circle(s,(82,42,125),(cx+4,19),3)
    pygame.draw.circle(s,(205,225,255),(cx-3,18),1)
    pygame.draw.circle(s,(205,225,255),(cx+5,18),1)
    hat = [(cx,0),(cx-13,15),(cx+13,15)]
    pygame.draw.polygon(s,(115,42,168),hat)
    pygame.draw.polygon(s,(88,25,132),hat,2)
    pygame.draw.ellipse(s,(135,52,185),(cx-16,12,32,8))
    pygame.draw.ellipse(s,(88,25,132),(cx-16,12,32,8),2)
    pygame.draw.circle(s,YELLOW,(cx+3,7),3)
    return s

def _draw_lightning_mage(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0,0,0,55), (cx-16, size-12, 32, 10))
    robe = [(cx-14,22),(cx+14,22),(cx+18,58),(cx-18,58)]
    pygame.draw.polygon(s, (22,55,165), robe)
    pygame.draw.polygon(s, (35,80,210), [(cx-6,22),(cx+6,22),(cx+4,44),(cx-4,44)])
    pygame.draw.polygon(s, (12,35,120), robe, 2)
    pygame.draw.polygon(s, (0,210,255), [(cx-18,54),(cx+18,54),(cx+18,58),(cx-18,58)])
    pygame.draw.rect(s, (75,58,28), (cx+15,10,4,48))
    bolt = [(cx+17,4),(cx+24,13),(cx+17,13),(cx+24,22),(cx+12,12),(cx+19,12),(cx+12,4)]
    pygame.draw.polygon(s, YELLOW, bolt)
    pygame.draw.polygon(s, (0,220,255), bolt, 1)
    gs2 = pygame.Surface((22,22), pygame.SRCALPHA)
    pygame.draw.circle(gs2, (0,170,255,60), (11,11), 11)
    s.blit(gs2, (cx+6, 2))
    pygame.draw.line(s, (0,220,255), (cx-10,32), (cx-7,40), 1)
    pygame.draw.line(s, (0,220,255), (cx,36), (cx+4,44), 1)
    pygame.draw.line(s, (0,220,255), (cx+8,30), (cx+6,38), 1)
    pygame.draw.ellipse(s, (242,205,162), (cx-10,13,20,18))
    pygame.draw.circle(s, (0,180,255), (cx-4,19), 3)
    pygame.draw.circle(s, (0,180,255), (cx+4,19), 3)
    pygame.draw.circle(s, WHITE, (cx-3,18), 1)
    pygame.draw.circle(s, WHITE, (cx+5,18), 1)
    hat = [(cx,0),(cx-13,15),(cx+13,15)]
    pygame.draw.polygon(s, (22,50,148), hat)
    pygame.draw.polygon(s, (0,190,255), hat, 2)
    pygame.draw.ellipse(s, (32,68,178), (cx-16,12,32,8))
    pygame.draw.ellipse(s, (0,190,255), (cx-16,12,32,8), 2)
    pygame.draw.circle(s, YELLOW, (cx+3,7), 3)
    gs3 = pygame.Surface((size,size), pygame.SRCALPHA)
    pygame.draw.circle(gs3, (0,140,255,16), (cx,cx), cx-2)
    s.blit(gs3, (0,0))
    return s

def _draw_valley_wraith(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    gs = pygame.Surface((size,size), pygame.SRCALPHA)
    pygame.draw.circle(gs, (110,0,200,20), (cx,cx), cx-2)
    s.blit(gs, (0,0))
    body = [(cx-13,24),(cx+13,24),(cx+15,46),(cx+7,58),(cx-7,58),(cx-15,46)]
    pygame.draw.polygon(s, (50,0,90,200), body)
    pygame.draw.polygon(s, (130,0,200,160), body, 2)
    for i in range(5):
        t = i / 4
        alpha = int(180 - t * 160)
        y = 45 + int(t * 14)
        hw = int(10 - t * 6)
        ws = pygame.Surface((hw*2+2, 5), pygame.SRCALPHA)
        pygame.draw.ellipse(ws, (90,0,150,alpha), (0,0,hw*2+2,5))
        s.blit(ws, (cx-hw-1, y))
    cape = [(cx-15,18),(cx+15,18),(cx+17,30),(cx-17,30)]
    pygame.draw.polygon(s, (18,0,38,210), cape)
    pygame.draw.polygon(s, (110,0,175,180), cape, 1)
    pygame.draw.circle(s, (28,0,55,240), (cx,16), 14)
    pygame.draw.circle(s, (75,0,130,120), (cx,16), 14, 2)
    pygame.draw.circle(s, (170,0,255), (cx-5,15), 4)
    pygame.draw.circle(s, (170,0,255), (cx+5,15), 4)
    gs2 = pygame.Surface((12,12), pygame.SRCALPHA)
    pygame.draw.circle(gs2, (200,100,255,80), (6,6), 6)
    s.blit(gs2, (cx-11,9)); s.blit(gs2, (cx-1,9))
    pygame.draw.circle(s, WHITE, (cx-5,15), 2)
    pygame.draw.circle(s, WHITE, (cx+5,15), 2)
    return s

def _draw_rogue(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s,(0,0,0,55),(cx-15,size-12,30,10))
    pygame.draw.rect(s,(32,26,44),(cx-12,40,10,18),border_radius=3)
    pygame.draw.rect(s,(32,26,44),(cx+2, 40,10,18),border_radius=3)
    pygame.draw.rect(s,(52,36,22),(cx-13,50,12,10),border_radius=2)
    pygame.draw.rect(s,(52,36,22),(cx+1, 50,12,10),border_radius=2)
    pygame.draw.rect(s,(42,32,58),(cx-13,22,26,22),border_radius=4)
    pygame.draw.rect(s,(225,122,22),(cx-13,30,26,5))
    pygame.draw.rect(s,(30,22,46),(cx-13,22,26,22),2,border_radius=4)
    pygame.draw.rect(s,(185,190,205),(cx-21,26,4,18))
    pygame.draw.rect(s,(132,102,32),(cx-23,32,8,4))
    pygame.draw.rect(s,(102,76,26),(cx-22,36,6,6))
    pygame.draw.line(s,(222,228,242),(cx-20,27),(cx-20,33),1)
    pygame.draw.rect(s,(185,190,205),(cx+17,26,4,18))
    pygame.draw.rect(s,(132,102,32),(cx+15,32,8,4))
    pygame.draw.rect(s,(102,76,26),(cx+16,36,6,6))
    pygame.draw.line(s,(222,228,242),(cx+18,27),(cx+18,33),1)
    pygame.draw.ellipse(s,(202,162,122),(cx-9,14,18,16))
    pygame.draw.circle(s,ORANGE,(cx-3,20),3)
    pygame.draw.circle(s,ORANGE,(cx+3,20),3)
    pygame.draw.circle(s,(255,222,152),(cx-2,19),1)
    pygame.draw.circle(s,(255,222,152),(cx+4,19),1)
    hood = [(cx-15,12),(cx,4),(cx+15,12),(cx+13,22),(cx-13,22)]
    pygame.draw.polygon(s,(52,40,72),hood)
    pygame.draw.polygon(s,(225,122,22),hood,2)
    gs = pygame.Surface((22,14),pygame.SRCALPHA)
    pygame.draw.ellipse(gs,(40,30,56,115),(0,0,22,14))
    s.blit(gs,(cx-11,10))
    return s

def _draw_coronavirus(size, body_col, spike_col, tip_col, outline_col, n_spikes, spike_len, tip_r):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = cy = size // 2
    r = size // 2 - spike_len - 1
    pygame.draw.ellipse(s,(0,0,0,50),(cx-r,size-5,r*2,5))
    for i in range(n_spikes):
        a = i * math.pi * 2 / n_spikes
        sx = cx + math.cos(a)*(r-1); sy = cy + math.sin(a)*(r-1)
        tx = cx + math.cos(a)*(r+spike_len); ty = cy + math.sin(a)*(r+spike_len)
        pygame.draw.line(s, spike_col, (int(sx),int(sy)), (int(tx),int(ty)), 2)
        pygame.draw.circle(s, tip_col, (int(tx),int(ty)), tip_r)
    pygame.draw.circle(s, body_col, (cx,cy), r)
    hi=(min(body_col[0]+40,255),min(body_col[1]+40,255),min(body_col[2]+40,255))
    pygame.draw.circle(s, hi, (cx-r//3,cy-r//3), r//2)
    pygame.draw.circle(s, outline_col, (cx,cy), r, 2)
    return s

def _draw_enemy_normal(size=40):
    return _draw_coronavirus(size,
        body_col=(195,185,215), spike_col=(200,55,75), tip_col=(240,110,120),
        outline_col=(150,110,175), n_spikes=12, spike_len=9, tip_r=3)

def _draw_enemy_fast(size=32):
    return _draw_coronavirus(size,
        body_col=(225,75,95), spike_col=(170,25,45), tip_col=(255,130,140),
        outline_col=(150,35,55), n_spikes=9, spike_len=7, tip_r=2)

def _draw_virus_influenza(size=40):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=cy=size//2; r=size//2-11
    pygame.draw.ellipse(s,(0,0,0,50),(cx-r,size-5,r*2,5))
    for i in range(10):
        a=i*math.pi*2/10
        sx2=cx+math.cos(a)*(r-1); sy2=cy+math.sin(a)*(r-1)
        tx=cx+math.cos(a)*(r+8); ty=cy+math.sin(a)*(r+8)
        pygame.draw.line(s,(160,80,180),(int(sx2),int(sy2)),(int(tx),int(ty)),2)
        # Mushroom-cap hemagglutinin tip
        lx=int(tx-math.cos(a+math.pi/2)*3); ly=int(ty-math.sin(a+math.pi/2)*3)
        rx=int(tx+math.cos(a+math.pi/2)*3); ry=int(ty+math.sin(a+math.pi/2)*3)
        pygame.draw.line(s,(210,130,230),(lx,ly),(rx,ry),3)
    pygame.draw.circle(s,(215,200,75),(cx,cy),r)
    pygame.draw.circle(s,(240,230,130),(cx-r//3,cy-r//3),r//2)
    pygame.draw.circle(s,(175,155,35),(cx,cy),r,2)
    return s

def _draw_virus_hiv(size=40):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=cy=size//2; r=size//2-10
    pygame.draw.ellipse(s,(0,0,0,50),(cx-r,size-5,r*2,5))
    for i in range(7):
        a=i*math.pi*2/7
        sx2=cx+math.cos(a)*(r-1); sy2=cy+math.sin(a)*(r-1)
        tx=cx+math.cos(a)*(r+9); ty=cy+math.sin(a)*(r+9)
        pygame.draw.line(s,(110,55,160),(int(sx2),int(sy2)),(int(tx),int(ty)),2)
        for da in (-0.35,0,0.35):
            ex=int(tx+math.cos(a+da)*3); ey=int(ty+math.sin(a+da)*3)
            pygame.draw.circle(s,(160,90,210),(ex,ey),2)
    pygame.draw.circle(s,(175,55,80),(cx,cy),r)
    # Visible conical core
    pygame.draw.polygon(s,(110,25,50),[(cx,cy-r//2),(cx-r//3,cy+r//3),(cx+r//3,cy+r//3)])
    pygame.draw.circle(s,(205,95,110),(cx-2,cy-2),r//3)
    pygame.draw.circle(s,(130,30,55),(cx,cy),r,2)
    return s

def _draw_virus_ebola(size=52):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    pts=[]
    for i in range(24):
        t=i/23
        x=int(6+t*(size-12))
        y=int(size//2+math.sin(t*math.pi*1.8)*13)
        pts.append((x,y))
    if len(pts)>=2:
        pygame.draw.lines(s,(40,110,40),False,pts,10)
        pygame.draw.lines(s,(70,165,70),False,pts,7)
        pygame.draw.lines(s,(100,210,100),False,pts,3)
    pygame.draw.circle(s,(70,165,70),(pts[0][0],pts[0][1]),5)
    pygame.draw.circle(s,(70,165,70),(pts[-1][0],pts[-1][1]),5)
    for i in range(0,len(pts),3):
        pygame.draw.circle(s,(40,100,40),(pts[i][0],pts[i][1]),2)
    return s

def _draw_virus_rabies(size=44):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=size//2; bw=18; bh=30; bx=cx-bw//2; by=size//2-bh//2
    pygame.draw.ellipse(s,(0,0,0,50),(bx,by+bh+2,bw,5))
    pygame.draw.rect(s,(140,140,195),(bx,by+bh//3,bw,bh*2//3))
    pygame.draw.ellipse(s,(140,140,195),(bx,by,bw,bh//2))
    for i in range(7):
        a=i*math.pi/(6); r2=bw//2+1
        sx2=int(cx+math.cos(a)*r2); sy2=int(by+bh//3+math.sin(a)*(bh//3))
        tx=int(cx+math.cos(a)*(r2+6)); ty=int(sy2+math.sin(a)*5)
        if 0<=tx<size and 0<=ty<size:
            pygame.draw.line(s,(95,95,175),(sx2,sy2),(tx,ty),2)
            pygame.draw.circle(s,(155,155,220),(tx,ty),2)
    pygame.draw.rect(s,(100,100,160),(bx,by+bh//3,bw,bh*2//3),2)
    pygame.draw.ellipse(s,(100,100,160),(bx,by,bw,bh//2),2)
    pygame.draw.ellipse(s,(190,190,230),(bx+3,by+4,bw//3,bh//5))
    return s

def _draw_virus_plague(size=40):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    rng=random.Random(7331)
    cx=size//2; bw=10; bh=26; bx=cx-bw//2; by=size//2-bh//2
    pygame.draw.ellipse(s,(0,0,0,50),(bx,by+bh+2,bw,5))
    pygame.draw.rect(s,(175,115,55),(bx,by+5,bw,bh-10))
    pygame.draw.ellipse(s,(175,115,55),(bx,by,bw,10))
    pygame.draw.ellipse(s,(175,115,55),(bx,by+bh-10,bw,10))
    for fidx in range(4):
        fx=cx; fy=by+bh//2+fidx*2-3
        px2,py2=fx,fy
        for j in range(9):
            nx=int(fx+j*5+rng.randint(-4,4)); ny=int(fy+j*3+rng.randint(-3,3))
            pygame.draw.line(s,(130,70,25),(px2,py2),(nx,ny),1)
            px2,py2=nx,ny
    pygame.draw.rect(s,(130,70,25),(bx,by+5,bw,bh-10),2)
    pygame.draw.ellipse(s,(130,70,25),(bx,by,bw,10),2)
    pygame.draw.ellipse(s,(130,70,25),(bx,by+bh-10,bw,10),2)
    pygame.draw.ellipse(s,(210,162,100),(bx+2,by+7,bw//3,bh//4))
    return s

def _draw_virus_phage(size=72):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=size//2
    lc=(60,85,120); fc=(185,205,230); dc=(100,125,160)
    # === Icosahedral head (flat-top hexagon + triangulation) ===
    hr=17; hcy=5+hr
    hpts=[(int(cx+math.cos(i*math.pi/3)*hr),
           int(hcy+math.sin(i*math.pi/3)*hr)) for i in range(6)]
    pygame.draw.polygon(s,fc,hpts)
    # Facet lines from center to each vertex + between vertices
    for i in range(6):
        pygame.draw.line(s,dc,(cx,hcy),(hpts[i][0],hpts[i][1]),1)
        pygame.draw.line(s,dc,hpts[i],hpts[(i+1)%6],1)
    # Inner mid-band (connects mid-edge left-right)
    pygame.draw.line(s,dc,
        ((hpts[3][0]+hpts[4][0])//2,(hpts[3][1]+hpts[4][1])//2),
        ((hpts[0][0]+hpts[1][0])//2,(hpts[0][1]+hpts[1][1])//2),1)
    pygame.draw.polygon(s,lc,hpts,2)
    head_bot=hcy+hr
    # === Collar ===
    pygame.draw.rect(s,dc,(cx-11,head_bot,22,5))
    pygame.draw.rect(s,lc,(cx-11,head_bot,22,5),1)
    # === Helical tail sheath (spring coil look) ===
    tail_top=head_bot+5; tail_h=24; tw=9
    pygame.draw.line(s,lc,(cx-tw,tail_top),(cx-tw,tail_top+tail_h),1)
    pygame.draw.line(s,lc,(cx+tw,tail_top),(cx+tw,tail_top+tail_h),1)
    n_rings=8
    for i in range(n_rings):
        ry=tail_top+i*tail_h//n_rings
        rh=4
        pygame.draw.ellipse(s,fc,(cx-tw,ry,tw*2,rh))
        pygame.draw.ellipse(s,dc,(cx-tw,ry,tw*2,rh),1)
    # === Base plate (hexagonal) ===
    bp_y=tail_top+tail_h; bpr=13
    bppts=[(int(cx+math.cos(i*math.pi/3)*bpr),
            int(bp_y+3+math.sin(i*math.pi/3)*5)) for i in range(6)]
    pygame.draw.polygon(s,dc,bppts)
    pygame.draw.polygon(s,lc,bppts,1)
    bp_cy=bp_y+3
    # === Tail fibers — 6 long bent legs ===
    for i in range(6):
        a=i*math.pi/3
        # Root at base plate edge
        rx=int(cx+math.cos(a)*bpr*0.7); ry2=bp_cy+int(math.sin(a)*3)
        # First segment: outward
        kx=int(rx+math.cos(a)*14); ky=int(ry2+8)
        # Second segment: downward
        fx2=int(kx+math.cos(a)*5); fy2=int(ky+12)
        pygame.draw.line(s,lc,(rx,ry2),(kx,ky),1)
        pygame.draw.line(s,lc,(kx,ky),(fx2,fy2),1)
        # Foot pin
        pygame.draw.circle(s,dc,(fx2,fy2),2)
        pygame.draw.line(s,lc,(fx2,fy2),(fx2,fy2+4),1)
    return s

def _draw_virus_smallpox(size=44):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=cy=size//2; w=30; h=22
    pygame.draw.ellipse(s,(0,0,0,50),(cx-w//2,cy+h//2,w,5))
    pygame.draw.ellipse(s,(155,95,55),(cx-w//2,cy-h//2,w,h))
    for i in range(4):
        for j in range(3):
            tx=int(cx-w//2+5+i*7); ty=int(cy-h//2+4+j*6)
            if tx<cx+w//2-2 and ty<cy+h//2-2:
                pygame.draw.circle(s,(115,65,30),(tx,ty),2)
    pygame.draw.ellipse(s,(110,60,25),(cx-w//2,cy-h//2,w,h),2)
    pygame.draw.ellipse(s,(195,145,95),(cx-w//3,cy-h//3,w//3,h//3))
    return s

def _draw_virus_measles(size=40):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=cy=size//2; r=size//2-10
    pygame.draw.ellipse(s,(0,0,0,50),(cx-r,size-5,r*2,5))
    for i in range(14):
        a=i*math.pi*2/14
        sx2=cx+math.cos(a)*(r-1); sy2=cy+math.sin(a)*(r-1)
        tx=cx+math.cos(a)*(r+6); ty=cy+math.sin(a)*(r+6)
        pygame.draw.line(s,(190,70,50),(int(sx2),int(sy2)),(int(tx),int(ty)),1)
        pygame.draw.circle(s,(220,100,80),(int(tx),int(ty)),2)
    pygame.draw.circle(s,(210,110,85),(cx,cy),r)
    pygame.draw.circle(s,(235,155,130),(cx-r//3,cy-r//3),r//2)
    pygame.draw.circle(s,(165,65,40),(cx,cy),r,2)
    return s

def _draw_virus_dengue(size=38):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=cy=size//2; r=size//2-10
    pygame.draw.ellipse(s,(0,0,0,50),(cx-r,size-5,r*2,5))
    # Icosahedral facets hint
    for i in range(5):
        a=i*math.pi*2/5
        px2=int(cx+math.cos(a)*r*0.6); py2=int(cy+math.sin(a)*r*0.6)
        px3=int(cx+math.cos(a+math.pi*2/5)*r*0.6); py3=int(cy+math.sin(a+math.pi*2/5)*r*0.6)
        pygame.draw.line(s,(180,120,30),(px2,py2),(px3,py3),1)
        pygame.draw.line(s,(180,120,30),(cx,cy),(px2,py2),1)
    pygame.draw.circle(s,(215,165,50),(cx,cy),r)
    pygame.draw.circle(s,(240,200,100),(cx-r//3,cy-r//3),r//2)
    pygame.draw.circle(s,(160,110,20),(cx,cy),r,2)
    return s

# Virus pool: unlocks over time
VIRUS_STAGES=[
    {"time":0,   "key":"virus_corona",    "name":"SARS-CoV-2",    "hp":1.0,"spd":1.0,"dmg":1.0,"r":14},
    {"time":80,  "key":"virus_influenza", "name":"インフルエンザ",  "hp":0.85,"spd":1.25,"dmg":0.9,"r":13},
    {"time":160, "key":"virus_hiv",       "name":"HIV",             "hp":1.3,"spd":0.8,"dmg":1.5,"r":13},
    {"time":240, "key":"virus_ebola",     "name":"エボラ",          "hp":1.5,"spd":1.1,"dmg":1.8,"r":14},
    {"time":320, "key":"virus_rabies",    "name":"狂犬病",          "hp":1.1,"spd":1.5,"dmg":1.3,"r":12},
    {"time":400, "key":"virus_plague",    "name":"ペスト菌",        "hp":1.4,"spd":1.0,"dmg":1.6,"r":11},
    {"time":460, "key":"virus_measles",   "name":"麻疹",            "hp":0.9,"spd":1.3,"dmg":1.0,"r":13},
    {"time":510, "key":"virus_dengue",    "name":"デング熱",        "hp":1.1,"spd":1.2,"dmg":1.2,"r":13},
    {"time":555, "key":"virus_smallpox",  "name":"天然痘",          "hp":1.8,"spd":0.7,"dmg":2.0,"r":14},
    {"time":580, "key":"virus_phage",     "name":"バクテリオファージ","hp":0.7,"spd":1.8,"dmg":0.8,"r":13},
]

def _draw_plague_doctor(size=64):
    s=pygame.Surface((size,size),pygame.SRCALPHA)
    cx=size//2
    # Shadow
    pygame.draw.ellipse(s,(0,0,0,55),(cx-18,size-12,36,10))
    # Long flowing coat
    coat=[(cx-13,26),(cx+13,26),(cx+17,62),(cx-17,62)]
    pygame.draw.polygon(s,(26,18,36),coat)
    pygame.draw.polygon(s,(16,10,24),coat,1)
    # Coat fold lines
    pygame.draw.line(s,(18,12,26),(cx-2,28),(cx-5,60),1)
    pygame.draw.line(s,(18,12,26),(cx+5,28),(cx+8,60),1)
    # Wide sleeves
    pygame.draw.polygon(s,(26,18,36),[(cx+10,28),(cx+22,40),(cx+22,50),(cx+14,46)])
    pygame.draw.polygon(s,(26,18,36),[(cx-10,28),(cx-22,42),(cx-22,52),(cx-14,48)])
    # Leather gloves
    pygame.draw.circle(s,(72,52,28),(cx+22,50),4)
    pygame.draw.circle(s,(72,52,28),(cx-22,52),4)
    # Walking cane (held in right glove, angled upward)
    pygame.draw.line(s,(85,62,32),(cx+22,50),(cx+30,8),2)
    pygame.draw.circle(s,(100,75,40),(cx+30,8),3)
    pygame.draw.line(s,(65,48,24),(cx+28,11),(cx+33,11),2)  # cross-piece
    # Neck
    pygame.draw.rect(s,(28,20,40),(cx-5,18,10,10))
    # Head (profile - slightly turned LEFT)
    pygame.draw.ellipse(s,(32,24,44),(cx-11,7,20,16))
    # === BEAK MASK - SIDEWAYS pointing LEFT ===
    bx=cx-8; by=14  # beak root (left side of head)
    beak=[(bx, by-5),(bx-22, by),(bx, by+5)]
    pygame.draw.polygon(s,(185,162,110),beak)       # cream leather
    pygame.draw.polygon(s,(140,115,72),beak,1)      # outline
    # Beak centre seam
    pygame.draw.line(s,(140,115,72),(bx,by),(bx-19,by),1)
    # Nostril holes
    pygame.draw.circle(s,(95,72,42),(bx-8,by-1),1)
    pygame.draw.circle(s,(95,72,42),(bx-13,by),1)
    # Goggle (front-facing side, now LEFT)
    pygame.draw.circle(s,(60,48,20),(cx-2,11),4)
    pygame.draw.circle(s,(42,32,12),(cx-2,11),4,1)
    pygame.draw.circle(s,(12,8,18),(cx-2,11),2)
    pygame.draw.circle(s,(110,88,44),(cx-1,10),1)   # glint
    # Wide-brim hat (angled - wider right side faces camera)
    pygame.draw.ellipse(s,(10,7,16),(cx-15,5,32,9)) # brim
    pygame.draw.rect(s,(10,7,16),(cx-9,0,18,8),border_radius=2)  # crown
    pygame.draw.ellipse(s,(22,16,30),(cx-15,5,32,9),1)  # brim rim
    pygame.draw.rect(s,(22,16,30),(cx-9,0,18,8),1,border_radius=2)
    # Purple aura glow
    gs=pygame.Surface((size,size),pygame.SRCALPHA)
    pygame.draw.circle(gs,(140,0,220,26),(cx,cx),cx-2)
    s.blit(gs,(0,0))
    return s


def _draw_boss_phage(size=160):
    """ボス用ダークオメガファージ — 立体感・暗黒配色・大型。"""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    # ── 多重グロー（紫・赤） ──
    for gr, gc, ga in [
        (cx-2,  (180, 0, 255), 22),
        (cx-10, (140, 0, 220), 14),
        (cx-20, (100, 0, 180), 8),
        (cx-30, (60,  0, 120), 5),
    ]:
        gs = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*gc, ga), (cx, cx), gr)
        s.blit(gs, (0, 0))

    # ── カプシドヘッド（正十二面体風 / 3D シェーディング）──
    HR  = 32          # 頂点半径
    hcy = 10 + HR     # ヘッド中心 y

    # カラーパレット
    C_BASE  = (28,  18,  48)    # 本体ベース（暗紫）
    C_MID   = (55,  30,  95)    # 中間面
    C_HI    = (100, 55, 160)    # ハイライト面
    C_EDGE  = (160, 60, 255)    # 輝くエッジ
    C_DARK  = (12,   6,  22)    # 影面

    # 頂点（6角）
    hpts = [(int(cx + math.cos(i*math.pi/3 - math.pi/6)*HR),
             int(hcy + math.sin(i*math.pi/3 - math.pi/6)*HR)) for i in range(6)]
    # 外周外面（影として少し大きく）
    hpts_outer = [(int(cx + math.cos(i*math.pi/3 - math.pi/6)*(HR+3)),
                   int(hcy + math.sin(i*math.pi/3 - math.pi/6)*(HR+3))) for i in range(6)]

    # 面ごとに3D塗り（6三角）
    FACE_COLS = [C_HI, C_HI, C_MID, C_DARK, C_DARK, C_MID]  # top lit, bottom dark
    for i in range(6):
        tri = [(cx, hcy), hpts[i], hpts[(i+1)%6]]
        pygame.draw.polygon(s, FACE_COLS[i], tri)

    # ベースカラー輪郭
    pygame.draw.polygon(s, C_MID, hpts)

    # 内側の細かい面（正六角を中心から放射状に区切る）
    for i in range(6):
        pygame.draw.line(s, C_EDGE, (cx, hcy), hpts[i], 1)
        pygame.draw.line(s, C_EDGE, hpts[i], hpts[(i+1)%6], 2)
    pygame.draw.polygon(s, C_EDGE, hpts, 2)

    # 外周ハロ（輝く縁）
    pygame.draw.polygon(s, (200, 80, 255), hpts_outer, 1)

    # ── 中心グロー目（赤い眼） ──
    pygame.draw.circle(s, (80,   0,  0),  (cx, hcy), 10)
    pygame.draw.circle(s, (200,  20, 20), (cx, hcy), 7)
    pygame.draw.circle(s, (255,  80, 40), (cx, hcy), 4)
    pygame.draw.circle(s, (255, 220,180), (cx, hcy), 2)
    # 瞳孔光（ハイライト）
    pygame.draw.circle(s, (255, 255, 255), (cx-2, hcy-2), 1)

    # ── ネック + リベットカラー ──
    neck_y = hcy + HR
    C_NECK  = (35, 20, 60)
    C_NBORD = (160, 60, 255)
    pygame.draw.rect(s, C_NECK,  (cx-16, neck_y,     32, 10))
    pygame.draw.rect(s, C_NBORD, (cx-16, neck_y,     32, 10), 1)
    # ハイライト帯
    pygame.draw.rect(s, (80, 40, 130), (cx-16, neck_y, 32, 3))
    # リベット
    for bx in (cx-10, cx-3, cx+4, cx+11):
        pygame.draw.circle(s, C_NBORD, (bx, neck_y+5), 2)
        pygame.draw.circle(s, (220,150,255), (bx, neck_y+5), 1)

    # ── テールシース（六角柱 + 回路パターン）──
    tail_top = neck_y + 10
    tail_h   = 36
    tw       = 13
    C_BODY   = (22, 12, 40)
    C_BODY_H = (60, 30, 100)
    C_STRIP  = (100, 40, 180)

    # 左右の影面
    pygame.draw.rect(s, C_DARK,  (cx - tw,     tail_top, tw,   tail_h))
    # 右ハイライト
    pygame.draw.rect(s, C_BODY,  (cx,          tail_top, tw,   tail_h))
    pygame.draw.rect(s, C_BODY_H,(cx,          tail_top, 5,    tail_h))  # 左縁
    # バンド（ヘキサゴンリング）
    for i in range(8):
        ry2 = tail_top + i * tail_h // 8
        pygame.draw.ellipse(s, C_STRIP, (cx-tw, ry2, tw*2, 5))
        pygame.draw.ellipse(s, C_NBORD, (cx-tw, ry2, tw*2, 5), 1)
    pygame.draw.rect(s, C_NBORD, (cx-tw, tail_top, tw*2, tail_h), 1)
    # 左縁に回路ライン
    for i in range(3):
        ly = tail_top + 6 + i*12
        pygame.draw.line(s, C_STRIP, (cx-tw+2, ly), (cx-tw+8, ly), 1)
        pygame.draw.circle(s, C_NBORD, (cx-tw+8, ly), 2)

    # ── ベースプレート（八角形） ──
    bp_y  = tail_top + tail_h
    bpr   = 18
    n_bp  = 8
    bppts = [(int(cx + math.cos(i*math.pi*2/n_bp)*bpr),
              int(bp_y + 5 + math.sin(i*math.pi*2/n_bp)*6)) for i in range(n_bp)]
    pygame.draw.polygon(s, C_BODY,  bppts)
    pygame.draw.polygon(s, C_STRIP, bppts, 1)
    pygame.draw.polygon(s, C_NBORD, bppts, 1)
    bp_cy = bp_y + 5

    # ── テールファイバー（6本・三関節・暗金色） ──
    GOLD_DK  = (100,  60,   5)
    GOLD     = (180, 110,  15)
    GOLD_HI  = (255, 190,  50)
    GOLD_TIP = (255, 240, 100)

    for i in range(6):
        a = i * math.pi / 3
        # 根本
        rx   = int(cx + math.cos(a) * bpr * 0.8)
        ry_r = int(bp_cy + math.sin(a) * 5)

        # 第1関節（外側へ広がる）
        k1x = int(rx + math.cos(a) * 32)
        k1y = int(ry_r + 18)

        # 第2関節（さらに外側・下方）
        k2x = int(k1x + math.cos(a) * 22)
        k2y = int(k1y + 16)

        # 足先（爪）
        k3x = int(k2x + math.cos(a - 0.3) * 12)
        k3y = int(k2y + 10)
        k3bx= int(k2x + math.cos(a + 0.3) * 10)
        k3by= int(k2y + 8)

        # 影線（太め・暗）
        for pts in [((rx,ry_r),(k1x,k1y)),((k1x,k1y),(k2x,k2y)),((k2x,k2y),(k3x,k3y))]:
            pygame.draw.line(s, GOLD_DK, pts[0], pts[1], 5)
        # 本体線
        pygame.draw.line(s, GOLD,   (rx,ry_r),   (k1x,k1y), 3)
        pygame.draw.line(s, GOLD,   (k1x,k1y),   (k2x,k2y), 3)
        pygame.draw.line(s, GOLD,   (k2x,k2y),   (k3x,k3y), 2)
        # ハイライト
        pygame.draw.line(s, GOLD_HI,(rx,ry_r),   (k1x,k1y), 1)

        # 関節球
        for jx, jy, jr in [(k1x,k1y,5),(k2x,k2y,4)]:
            pygame.draw.circle(s, GOLD_DK, (jx,jy), jr)
            pygame.draw.circle(s, GOLD,    (jx,jy), jr-1)
            pygame.draw.circle(s, GOLD_HI, (jx-1,jy-1), 1)

        # 二叉の爪先
        pygame.draw.line(s, GOLD,    (k2x,k2y),(k3x,k3y),  2)
        pygame.draw.line(s, GOLD,    (k2x,k2y),(k3bx,k3by),2)
        pygame.draw.circle(s, GOLD_TIP,(k3x,k3y),  2)
        pygame.draw.circle(s, GOLD_TIP,(k3bx,k3by),2)

    # ── 頭頂部スパイク（上方）──
    for angle, h_spike in [(-math.pi/2, 20), (-math.pi/2-0.5, 13), (-math.pi/2+0.5, 13)]:
        tip_x = int(cx + math.cos(angle)*h_spike*0.5)
        tip_y = int(hcy - HR - h_spike + 4)
        base_x = cx; base_y = hcy - HR + 4
        pts_sp = [
            (base_x-4, base_y),
            (base_x+4, base_y),
            (tip_x, tip_y),
        ]
        pygame.draw.polygon(s, C_MID,  pts_sp)
        pygame.draw.polygon(s, C_EDGE, pts_sp, 1)
        pygame.draw.circle(s, (255,100,255), (tip_x,tip_y), 2)

    return s

_SPRITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "converted")

def _load_png(filename, size):
    """converted/ からPNGを読み込んでスケールして返す。失敗時はNone。"""
    path = os.path.join(_SPRITE_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        spr = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(spr, (size, size))
    except Exception:
        return None

def build_sprites():
    def _pc(fname, size, fallback_fn):
        return _load_png(fname, size) or fallback_fn(size)

    def _load_big_png(fname, target_h, crop_w):
        """大きなPNGを target_h の高さにスケールし、中央 crop_w px に切り抜く。"""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        if not os.path.exists(path): return None
        try:
            img = pygame.image.load(path).convert_alpha()
            ow, oh = img.get_size()
            tw = int(ow * target_h / oh)
            img = pygame.transform.smoothscale(img, (tw, target_h))
            cx  = tw // 2
            out = pygame.Surface((crop_w, target_h), pygame.SRCALPHA)
            out.blit(img, (-(cx - crop_w//2), 0))
            return out
        except Exception:
            return None

    raw = {
        "knight":         _pc("knight.png",        64, _draw_knight),
        "warior":         _pc("warior.png",        64, _draw_knight),
        "mage":           _pc("mage.png",           64, _draw_mage),
        "rogue":          _pc("rogue.png",           64, _draw_rogue),
        "plague_doctor":  _pc("plague_doctor.png",  64, _draw_plague_doctor),
        "lightning_mage": _pc("lightning_mage.png", 64, _draw_lightning_mage),
        "valley_wraith":  _pc("valley_wraith.png",  64, _draw_valley_wraith),
        "necromancer":    _load_big_png("necro1_t.png", 80, 72) or _draw_mage(64),
        "gunman":         _load_big_png("generated-image-t.png", 80, 72) or _draw_rogue(64),
        "enemy_normal":   _draw_enemy_normal(40),
        "enemy_fast":     _draw_enemy_fast(32),
        "virus_corona":   _draw_enemy_normal(40),
        "virus_influenza":_draw_virus_influenza(40),
        "virus_hiv":      _draw_virus_hiv(40),
        "virus_ebola":    _draw_virus_ebola(52),
        "virus_rabies":   _draw_virus_rabies(44),
        "virus_plague":   _draw_virus_plague(40),
        "virus_measles":  _draw_virus_measles(40),
        "virus_dengue":   _draw_virus_dengue(38),
        "virus_smallpox": _draw_virus_smallpox(44),
        "virus_phage":    _draw_virus_phage(72),
        "boss":           _draw_boss_phage(160),
        "godzilla":       _draw_godzilla(160),
    }
    # ax_transparent.png を読み込み
    global _AXE_IMG
    _ax_path = os.path.join(os.path.dirname(__file__), "ax_transparent.png")
    if os.path.exists(_ax_path):
        try:
            _ax = pygame.image.load(_ax_path).convert_alpha()
            _AXE_IMG = pygame.transform.smoothscale(_ax, (56, 60))
        except Exception:
            pass

    # kyonsi_t.png (ミニオンスプライト)
    global _KYONSI_IMG
    _ks_path = os.path.join(os.path.dirname(__file__), "kyonsi_t.png")
    if os.path.exists(_ks_path):
        try:
            _ks = pygame.image.load(_ks_path).convert_alpha()
            kw, kh = _ks.get_size()
            th = 50; tw = int(kw * th / kh)
            _ks = pygame.transform.smoothscale(_ks, (tw, th))
            cx = tw // 2; cw = 46
            out = pygame.Surface((cw, th), pygame.SRCALPHA)
            out.blit(_ks, (-(cx - cw//2), 0))
            _KYONSI_IMG = out
        except Exception:
            pass

    # gozila_transparent.png があればリアル画像で上書き
    _gz_path = os.path.join(os.path.dirname(__file__), "gozila_transparent.png")
    if os.path.exists(_gz_path):
        try:
            _gz_img = pygame.image.load(_gz_path).convert_alpha()
            # ゲームサイズに合わせてスケール (160x160)
            _gz_img = pygame.transform.smoothscale(_gz_img, (480, 480))
            raw["godzilla"] = _gz_img
        except Exception:
            pass  # ロード失敗時はプロシージャル版を使う
    # 敵・ボス系スプライトに3Dシェーディングを事前適用
    _enemy_keys = {k for k in raw if k not in
                   ("knight","mage","rogue","plague_doctor","lightning_mage","valley_wraith",
                    "necromancer","gunman","godzilla")}   # godzilla は写真調なのでシェーディング不要
    for k in _enemy_keys:
        if raw[k] is not None:
            raw[k] = apply_3d_shading(raw[k])

    # ── SBS realistic terrain tiles (flat isometric diamonds 256×144) ────────
    _sbs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "tilesets", "sbs_tiles")
    # iso diamond: width=104px, height=52px (TILE_STEP*2*ISO_SX/SY)
    _TW = 104; _TH = 52
    _tile_files = {
        TERRAIN_GRASS:  "forest_00.png",  # 緑草地
        TERRAIN_ICE:    "t2_00.png",      # 灰石（青味tint）
        TERRAIN_SWAMP:  "t1_00.png",      # 茶色泥・沼
        # TERRAIN_MAGMA=1: procedural glow kept (no red/lava tile in pack)
        TERRAIN_VALLEY: "t3_00.png",      # 暗灰岩
    }
    global _TERRAIN_TILES
    import numpy as _np
    for tid, fname in _tile_files.items():
        path = os.path.join(_sbs_dir, fname)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.smoothscale(img, (_TW, _TH))
                # ICE: add blue tint
                if tid == TERRAIN_ICE:
                    tint = pygame.Surface((_TW, _TH), pygame.SRCALPHA)
                    tint.fill((60, 120, 220, 60))
                    img.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
                # Clip to diamond shape: zero alpha outside diamond boundary
                # surfarray is (x, y) order; diamond: |x/W*2-1| + |y/H*2-1| <= 1
                arr = pygame.surfarray.pixels_alpha(img)
                xi = (_np.arange(_TW).reshape(_TW, 1) / _TW * 2 - 1)
                yi = (_np.arange(_TH).reshape(1, _TH) / _TH * 2 - 1)
                arr[_np.abs(xi) + _np.abs(yi) > 1.0] = 0
                del arr  # unlock surface
                _TERRAIN_TILES[tid] = img
            except Exception:
                pass

    return raw


# ─────────────────────────────────────────────
# Sound Manager
# ─────────────────────────────────────────────
def _sine_buf(freq, dur, vol=0.3, rate=44100):
    n = int(rate*dur); period = max(1,int(rate/max(freq,1)))
    one = [math.sin(2*math.pi*i/period)*vol for i in range(period)]
    tiled = (one*(n//period+2))[:n]
    fade = min(int(0.02*rate),n//4)
    buf = arr.array('h',[0]*n*2)
    for i,v in enumerate(tiled):
        s=int(v*32767)
        if i<fade: s=int(s*i/fade)
        if i>=n-fade: s=int(s*(n-i)/max(fade,1))
        buf[i*2]=s; buf[i*2+1]=s
    return buf

def _sweep_buf(f1,f2,dur,vol=0.3,rate=44100):
    n=int(rate*dur); fade=min(int(0.02*rate),n//4)
    buf=arr.array('h',[0]*n*2); phase=0.0
    for i in range(n):
        phase+=2*math.pi*(f1+(f2-f1)*i/n)/rate
        s=int(math.sin(phase)*32767*vol)
        if i<fade: s=int(s*i/fade)
        if i>=n-fade: s=int(s*(n-i)/max(fade,1))
        buf[i*2]=s; buf[i*2+1]=s
    return buf

def _chord_buf(freqs,dur,vol=0.25,rate=44100):
    n=int(rate*dur); pv=vol/len(freqs)
    fade=min(int(0.05*rate),n//4)
    buf=arr.array('h',[0]*n*2); phases=[0.0]*len(freqs)
    for i in range(n):
        s=0
        for j,f in enumerate(freqs):
            phases[j]+=2*math.pi*f/rate; s+=math.sin(phases[j])*32767*pv
        s=int(max(-32767,min(32767,s)))
        if i<fade: s=int(s*i/fade)
        if i>=n-fade: s=int(s*(n-i)/max(fade,1))
        buf[i*2]=s; buf[i*2+1]=s
    return buf

def _noise_buf(dur,vol=0.18,rate=44100):
    n=int(rate*dur); fade=min(int(0.01*rate),n//4)
    buf=arr.array('h',[0]*n*2)
    for i in range(n):
        s=int((random.random()*2-1)*32767*vol)
        if i<fade: s=int(s*i/fade)
        if i>=n-fade: s=int(s*(n-i)/max(fade,1))
        buf[i*2]=s; buf[i*2+1]=s
    return buf

def _bgm_buf(rate=44100):
    bars=[(110.00,220.00,329.63),(87.31,174.61,261.63),
          (130.81,261.63,392.00),(98.00,196.00,293.66)]
    total=int(rate*1.6*len(bars))
    buf=arr.array('h',[0]*total*2); idx=0
    for bass,mid,top in bars:
        seg=int(rate*1.6); phases=[0.0]*3; freqs=[bass,mid,top]; vols=[0.14,0.08,0.04]
        fade=int(0.04*rate)
        for i in range(seg):
            s=0
            for j in range(3):
                phases[j]+=2*math.pi*freqs[j]/rate; s+=math.sin(phases[j])*32767*vols[j]
            s=int(max(-32767,min(32767,s)))
            if i<fade: s=int(s*i/fade)
            if i>=seg-fade: s=int(s*(seg-i)/max(fade,1))
            buf[(idx+i)*2]=s; buf[(idx+i)*2+1]=s
        idx+=seg
    return buf

class SoundManager:
    def __init__(self):
        self.muted=False; self.sfx={}; self._build()

    def _build(self):
        _base = os.path.dirname(os.path.abspath(__file__))

        def _load_se(path, fallback):
            if os.path.exists(path) and os.path.getsize(path)>0:
                try: return pygame.mixer.Sound(path)
                except Exception: pass
            return fallback

        self.sfx["shoot"]    = pygame.mixer.Sound(buffer=_sine_buf(700,0.05,0.18))
        self.sfx["axe"]      = _load_se(os.path.join(_base,"nc437374_剣を振る・ジャンプする・風切り音.wav"),
                                        pygame.mixer.Sound(buffer=_sweep_buf(500,250,0.12,0.25)))
        self.sfx["hit"]      = pygame.mixer.Sound(buffer=_sine_buf(380,0.07,0.2))
        self.sfx["kill"]     = pygame.mixer.Sound(buffer=_sweep_buf(500,150,0.14,0.25))
        self.sfx["levelup"]  = _load_se(os.path.join(_base,"nc387503_【効果音】レベルアップその1・ファンファーレ・レトロ・8bit.mp3"),
                                        pygame.mixer.Sound(buffer=_chord_buf([523,659,784,1046],0.45,0.22)))
        self.sfx["boss"]     = pygame.mixer.Sound(buffer=_chord_buf([60,80,55],0.7,0.3))
        self.sfx["chest"]    = pygame.mixer.Sound(buffer=_chord_buf([523,659,784],0.3,0.2))
        self.sfx["hurt"]     = pygame.mixer.Sound(buffer=_sweep_buf(300,150,0.09,0.35))
        self.sfx["cross"]    = pygame.mixer.Sound(buffer=_chord_buf([400,600],0.1,0.2))
        # 外部SE: 火炎魔法 / 雷魔法
        self.sfx["flame"]    = _load_se(os.path.join(_base,"se_flame.wav"),
                                        pygame.mixer.Sound(buffer=_noise_buf(0.18,0.22)))
        _light = _load_se(os.path.join(_base,"se_lightning.wav"),
                          pygame.mixer.Sound(buffer=_sweep_buf(1400,600,0.08,0.28)))
        self.sfx["lightning"] = _light
        self.sfx["scatter"]   = _light   # 同じ雷SE
        self.sfx["necro_summon"] = _load_se(os.path.join(_base,"se_necro.wav"),
                                            pygame.mixer.Sound(buffer=_chord_buf([200,280,160],0.4,0.3)))
        bgm = pygame.mixer.Sound(buffer=_bgm_buf())
        bgm.set_volume(0.4); self.sfx["bgm"] = bgm
        # 外部BGMファイル
        self._bgm_file = None
        for _ext in ("ogg","mp3","wav"):
            _p = os.path.join(_base, f"bgm.{_ext}")
            if os.path.exists(_p) and os.path.getsize(_p)>0:
                self._bgm_file = _p; break
        self._apply_sfx_vol()

    def _apply_sfx_vol(self):
        for k, s in self.sfx.items():
            if k != "bgm":
                s.set_volume(_vol_sfx)

    def set_sfx_volume(self, v):
        global _vol_sfx
        _vol_sfx = max(0.0, min(1.0, v))
        self._apply_sfx_vol()

    def set_bgm_volume(self, v):
        global _vol_bgm
        _vol_bgm = max(0.0, min(1.0, v))
        pygame.mixer.music.set_volume(_vol_bgm)
        self.sfx["bgm"].set_volume(_vol_bgm * 0.4)

    def play(self, name):
        if not self.muted and name in self.sfx:
            self.sfx[name].play()

    def start_bgm(self):
        if self.muted: return
        if self._bgm_file:
            try:
                pygame.mixer.music.load(self._bgm_file)
                pygame.mixer.music.set_volume(_vol_bgm)
                pygame.mixer.music.play(loops=-1)
                return
            except Exception: pass
        self.sfx["bgm"].play(loops=-1)

    def stop_bgm(self):
        pygame.mixer.music.stop()
        self.sfx["bgm"].stop()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            pygame.mixer.music.pause()
            pygame.mixer.pause()
        else:
            if self._bgm_file:
                try:
                    if not pygame.mixer.music.get_busy():
                        pygame.mixer.music.play(loops=-1)
                    else:
                        pygame.mixer.music.unpause()
                    return
                except Exception: pass
            pygame.mixer.unpause()
            self.sfx["bgm"].play(loops=-1)


# ─────────────────────────────────────────────
# Visual effects
# ─────────────────────────────────────────────
class Particle:
    __slots__=("x","y","z","vx","vy","vz","life","max_life","color","r","alive")
    def __init__(self,x,y,color):
        a=random.uniform(0,math.pi*2); v=random.uniform(60,200)
        self.x,self.y=x,y; self.vx,self.vy=math.cos(a)*v,math.sin(a)*v
        self.z=10.0; self.vz=random.uniform(80,200)
        self.life=self.max_life=random.uniform(0.3,0.7)
        self.color=color; self.r=random.randint(3,7); self.alive=True
    def update(self,dt):
        self.x+=self.vx*dt; self.vx*=0.92
        self.y+=self.vy*dt; self.vy*=0.92
        self.vz-=300*dt; self.z=max(0,self.z+self.vz*dt)
        self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        alpha=int(255*self.life/self.max_life)
        sx,sy=iso_pos(self.x,self.y,self.z,ox,oy)
        s=pygame.Surface((self.r*2,self.r*2),pygame.SRCALPHA)
        r,g,b=self.color; pygame.draw.circle(s,(r,g,b,alpha),(self.r,self.r),self.r)
        surf.blit(s,(sx-self.r,sy-self.r))


class RingEffect:
    """Expanding ring — used for muzzle flash, impact, garlic shockwave, etc."""
    def __init__(self,x,y,color,max_r,width=2,life=0.3):
        self.x,self.y=x,y; self.color=color
        self.max_r=max_r; self.width=width
        self.life=self.max_life=life; self.alive=True
    def update(self,dt):
        self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        prog=1-self.life/self.max_life
        r=max(1,int(self.max_r*prog))
        alpha=int(255*self.life/self.max_life)
        sx,sy=iso_pos(self.x,self.y,3,ox,oy)
        rw=max(2,int(r*2.0)); rh=max(1,int(r*0.7))
        s=pygame.Surface((rw+4,rh+4),pygame.SRCALPHA)
        cr,cg,cb=self.color
        pygame.draw.ellipse(s,(cr,cg,cb,alpha),(0,0,rw+4,rh+4),self.width)
        surf.blit(s,(sx-rw//2-2,sy-rh//2-2))


class ScreenFlash:
    """Full-screen color overlay for SP ultimate activation."""
    def __init__(self, color, life=0.55, max_alpha=180):
        self.color = color
        self.life = self.max_life = life
        self.max_alpha = max_alpha
        self.alive = True
    def update(self, dt):
        self.life -= dt
        if self.life <= 0: self.alive = False
    def draw(self, surf):
        prog = self.life / self.max_life
        alpha = int(self.max_alpha * prog ** 0.6)
        s = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        r, g, b = self.color
        s.fill((r, g, b, alpha))
        surf.blit(s, (0, 0))


class ScreenShake:
    def __init__(self): self.timer=0.0; self.strength=0.0
    def shake(self,strength,duration=0.25):
        self.strength=max(self.strength,strength); self.timer=max(self.timer,duration)
    def update(self,dt):
        self.timer=max(0,self.timer-dt)
        if self.timer>0:
            s=self.strength*(self.timer/0.25)
            return random.randint(-int(s),int(s)),random.randint(-int(s),int(s))
        self.strength=0; return 0,0


# ─────────────────────────────────────────────
# Bullet with trails and styled drawing
# ─────────────────────────────────────────────
class Bullet:
    def __init__(self,x,y,dx,dy,speed,damage,radius,color,lifetime=2.0,pierce=1,style="circle"):
        self.x,self.y=x,y; self.dx,self.dy=dx,dy
        self.speed=speed; self.damage=damage; self.radius=radius
        self.color=color; self.life=lifetime; self.pierce=pierce
        self.style=style; self.hit_ids=set(); self.alive=True
        self.trail=[]; self._anim_t=0.0

    def update(self,dt):
        self._anim_t+=dt
        self.trail.append((self.x,self.y))
        if len(self.trail)>8: self.trail=self.trail[-8:]
        self.x+=self.dx*self.speed*dt; self.y+=self.dy*self.speed*dt
        self.life-=dt
        if self.life<=0: self.alive=False

    def _draw_trail(self,surf,ox,oy):
        n=len(self.trail)
        if n==0: return
        cr,cg,cb=self.color
        for i,(tx,ty) in enumerate(self.trail):
            ratio=(i+1)/n
            r=max(1,int(self.radius*ratio*0.65))
            tsx,tsy=iso_pos(tx,ty,26,ox,oy)
            ts=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
            pygame.draw.circle(ts,(cr,cg,cb,int(90*ratio)),(r+1,r+1),r)
            surf.blit(ts,(tsx-r-1,tsy-r-1))

    def draw(self,surf,ox,oy):
        self._draw_trail(surf,ox,oy)
        sx,sy=iso_pos(self.x,self.y,26,ox,oy)
        cr,cg,cb=self.color
        r=self.radius

        if self.style=="orb":          # Wand — 魔法オーブ
            fade = min(1.0, self.life * 3)
            # 外側グロー
            gs = r + 10; gsurf = pygame.Surface((gs*2, gs*2), pygame.SRCALPHA)
            pygame.draw.circle(gsurf, (cr, cg, cb, int(40 * fade)), (gs, gs), gs)
            pygame.draw.circle(gsurf, (cr, cg, cb, int(70 * fade)), (gs, gs), gs - 4)
            surf.blit(gsurf, (sx - gs, sy - gs))
            # コア
            pygame.draw.circle(surf, (min(cr+60,255), min(cg+60,255), min(cb+60,255)), (sx, sy), r+2)
            pygame.draw.circle(surf, self.color, (sx, sy), r)
            pygame.draw.circle(surf, WHITE, (sx, sy), max(2, r // 2))
            # スパーク（進行方向の反対に光跡）
            trail_len = 12
            tx = int(sx - self.dx * trail_len); ty = int(sy - self.dy * trail_len)
            tsurf = pygame.Surface((abs(tx-sx)*2+4, abs(ty-sy)*2+4), pygame.SRCALPHA)
            pygame.draw.line(tsurf, (cr, cg, cb, int(120 * fade)),
                             (abs(tx-sx) if tx<sx else 2, abs(ty-sy) if ty<sy else 2),
                             (abs(tx-sx)+2 if tx>sx else 2, abs(ty-sy)+2 if ty>sy else 2), max(2, r//2))
            pygame.draw.circle(surf, (cr, cg, min(cb+80,255)), (sx, sy), r+2, 1)

        elif self.style=="cross":      # Cross — + shape
            pygame.draw.rect(surf,self.color,(sx-r,sy-2,r*2,4))
            pygame.draw.rect(surf,self.color,(sx-2,sy-r,4,r*2))
            gs=r+4; gsurf=pygame.Surface((gs*2,gs*2),pygame.SRCALPHA)
            pygame.draw.circle(gsurf,(cr,cg,cb,45),(gs,gs),gs)
            surf.blit(gsurf,(sx-gs,sy-gs))
            pygame.draw.circle(surf,WHITE,(sx,sy),3)

        else:                          # Default circle
            pygame.draw.circle(surf,self.color,(sx,sy),r)


class AxeBullet(Bullet):
    """Rotating axe blade projectile."""
    def __init__(self,x,y,dx,dy,speed,damage):
        super().__init__(x,y,dx,dy,speed,damage,radius=28,
                         color=ORANGE,lifetime=0.9,pierce=99,style="axe")
        self.angle=math.atan2(dy,dx); self.spin=9.0

    def update(self,dt):
        self.trail.append((self.x,self.y))
        if len(self.trail)>8: self.trail=self.trail[-8:]
        self.x+=self.dx*self.speed*dt; self.y+=self.dy*self.speed*dt
        self.angle+=self.spin*dt; self.life-=dt
        if self.life<=0: self.alive=False

    def draw(self,surf,ox,oy):
        # Orange trail
        n=len(self.trail)
        for i,(tx,ty) in enumerate(self.trail):
            ratio=(i+1)/max(n,1); tr=max(1,int(self.radius*ratio*0.4))
            tsx,tsy=iso_pos(tx,ty,26,ox,oy)
            ts=pygame.Surface((tr*2+2,tr*2+2),pygame.SRCALPHA)
            pygame.draw.circle(ts,(255,140,0,int(60*ratio)),(tr+1,tr+1),tr)
            surf.blit(ts,(tsx-tr-1,tsy-tr-1))
        sx,sy=iso_pos(self.x,self.y,26,ox,oy)
        if _AXE_IMG is not None:
            # 画像を回転して描画
            rotated = pygame.transform.rotate(_AXE_IMG, -math.degrees(self.angle)-45)
            rw, rh = rotated.get_size()
            surf.blit(rotated, (sx - rw//2, sy - rh//2))
        else:
            # フォールバック: プロシージャル斧
            r=self.radius
            bl=r*1.65; bw=r*0.72
            pts=[(sx+math.cos(self.angle)*bl,       sy+math.sin(self.angle)*bl),
                 (sx+math.cos(self.angle+1.8)*bw,   sy+math.sin(self.angle+1.8)*bw),
                 (sx-math.cos(self.angle)*r*0.45,    sy-math.sin(self.angle)*r*0.45),
                 (sx+math.cos(self.angle-1.8)*bw,   sy+math.sin(self.angle-1.8)*bw)]
            pts=[(int(x),int(y)) for x,y in pts]
            pygame.draw.polygon(surf,ORANGE,pts)
            pygame.draw.polygon(surf,(255,200,80),pts,2)


class GunBullet(Bullet):
    """ガンマン用高速銃弾。真鍮ケーシング + 尖頭弾頭。"""
    _BULLET_SURF = None   # 事前レンダリングキャッシュ

    def __init__(self, x, y, dx, dy, damage):
        super().__init__(x, y, dx, dy, speed=950, damage=damage,
                         radius=5, color=(200,160,60), lifetime=1.1, pierce=1, style="gun")
        self._angle = math.atan2(dy, dx)

    @classmethod
    def _make_bullet_surf(cls):
        """bullet.jpg（背景透過済み）または手描きで弾丸サーフェスを生成してキャッシュ。先端は右向き。"""
        if cls._BULLET_SURF is not None:
            return cls._BULLET_SURF
        if GUN_BULLET_IMG is not None:
            cls._BULLET_SURF = GUN_BULLET_IMG
            return cls._BULLET_SURF
        # フォールバック: 手描き弾丸
        W2, H2 = 26, 10
        s = pygame.Surface((W2, H2), pygame.SRCALPHA)
        cy = H2 // 2
        case_len = 14
        pygame.draw.rect(s, (160, 110, 30), (0, cy-3, case_len, 6), border_radius=2)
        pygame.draw.rect(s, (200, 155, 60), (0, cy-2, case_len, 4), border_radius=2)
        pygame.draw.rect(s, (100, 70, 15), (0, cy-3, 3, 6))
        pygame.draw.rect(s, (140, 100, 25), (0, cy-2, 2, 4))
        tip_x = case_len
        tip_pts = [(tip_x, cy-3), (tip_x, cy+3), (W2-1, cy)]
        pygame.draw.polygon(s, (180, 130, 80), tip_pts)
        pygame.draw.polygon(s, (220, 180, 120), tip_pts, 1)
        pygame.draw.line(s, (240, 200, 150), (tip_x+1, cy-2), (W2-3, cy), 1)
        pygame.draw.line(s, (230, 185, 90), (2, cy-2), (case_len-2, cy-2), 1)
        cls._BULLET_SURF = s
        return s

    def draw(self, surf, ox, oy):
        sx, sy = iso_pos(self.x, self.y, 26, ox, oy)
        fade = min(1.0, self.life * 3.5)

        # 煙・火薬の光跡
        for i, (tx, ty) in enumerate(self.trail[-5:]):
            ratio = (i + 1) / 5
            tsx, tsy = iso_pos(tx, ty, 26, ox, oy)
            tr_s = pygame.Surface((8, 8), pygame.SRCALPHA)
            tr_col = (255, 220, 100, int(80 * ratio * fade))
            pygame.draw.circle(tr_s, tr_col, (4, 4), int(3 * ratio + 1))
            surf.blit(tr_s, (tsx - 4, tsy - 4))

        # 弾丸本体を回転して描画
        bsrf = self._make_bullet_surf()
        deg = -math.degrees(self._angle)
        rotated = pygame.transform.rotate(bsrf, deg)
        rotated.set_alpha(int(255 * fade))
        surf.blit(rotated, (sx - rotated.get_width()//2, sy - rotated.get_height()//2))

        # 先端グロー
        gsurf = pygame.Surface((14, 14), pygame.SRCALPHA)
        pygame.draw.circle(gsurf, (255, 230, 160, int(100 * fade)), (7, 7), 7)
        surf.blit(gsurf, (sx - 7, sy - 7))


# ─────────────────────────────────────────────
# FlameZone / Lightning (enhanced)
# ─────────────────────────────────────────────
class FlameZone:
    def __init__(self,x,y,radius,damage,lifetime):
        self.x,self.y=x,y; self.radius=radius; self.damage=damage
        self.life=self.max_life=lifetime; self.hit_ids=set()
        self.tick=0.3; self.timer=0.0; self.alive=True
        self._anim_t = 0.0   # アニメーション経過時間

    def update(self,dt,enemies,floats):
        self._anim_t += dt
        self.life-=dt
        if self.life<=0: self.alive=False; return
        self.timer+=dt
        if self.timer>=self.tick: self.timer=0.0; self.hit_ids.clear()
        for e in enemies:
            if id(e) in self.hit_ids: continue
            if dist((self.x,self.y),(e.x,e.y))<self.radius+e.radius:
                e.hp-=self.damage; e.hit_flash=0.1; self.hit_ids.add(id(e))
                floats.append(FloatText(e.x,e.y-20,str(int(self.damage)),ORANGE,0.5))

    def draw(self,surf,ox,oy):
        r  = self.radius
        sx, sy = iso_pos(self.x, self.y, 2, ox, oy)
        rw = max(4, int(r * 2.2))
        rh = max(2, int(r * 0.78))
        lifetime_ratio = max(0.0, self.life / self.max_life)

        if FLAME_FRAMES:
            fi      = int(self._anim_t * FLAME_FPS) % len(FLAME_FRAMES)
            scaled  = pygame.transform.scale(FLAME_FRAMES[fi], (rw, rh))

            # アルファ × ライフタイムフェード × 楕円グラデマスク
            alpha_view = pygame.surfarray.pixels_alpha(scaled)
            W_s, H_s   = alpha_view.shape
            xs = np.linspace(-1.0, 1.0, W_s, dtype=np.float32)
            ys = np.linspace(-1.0, 1.0, H_s, dtype=np.float32)
            XX, YY = np.meshgrid(xs, ys, indexing='ij')
            ell_mask = np.clip(1.3 - np.sqrt(XX**2 + YY**2) * 1.3, 0.0, 1.0)
            alpha_view[:] = (alpha_view * ell_mask * lifetime_ratio).astype(np.uint8)
            del alpha_view

            surf.blit(scaled, (sx - rw // 2, sy - rh // 2),
                      special_flags=pygame.BLEND_ADD)
        else:
            # フォールバック（動画なし）
            alpha = int(180 * lifetime_ratio)
            s = pygame.Surface((rw, rh), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 100, 0, alpha), (0, 0, rw, rh))
            pygame.draw.ellipse(s, (255, 200, 0, alpha // 2),
                                (rw // 4, rh // 4, rw // 2, rh // 2))
            surf.blit(s, (sx - rw // 2, sy - rh // 2))


def _jitter_pts(p1,p2,segs=5,jitter=12):
    pts=[p1]
    for i in range(1,segs):
        t=i/segs
        mx=p1[0]+(p2[0]-p1[0])*t+random.uniform(-jitter,jitter)
        my=p1[1]+(p2[1]-p1[1])*t+random.uniform(-jitter,jitter)
        pts.append((mx,my))
    pts.append(p2); return pts

class LightningBolt:
    def __init__(self,pts,life=0.15):
        self.life=self.max_life=life; self.alive=True
        self.segs=[]; self.forks=[]
        for i in range(len(pts)-1):
            self.segs.append(_jitter_pts(pts[i],pts[i+1]))
            if random.random()<0.7:
                d=dist(pts[i],pts[i+1])
                t=random.uniform(0.3,0.7)
                mid=(pts[i][0]+(pts[i+1][0]-pts[i][0])*t,
                     pts[i][1]+(pts[i+1][1]-pts[i][1])*t)
                angle=math.atan2(pts[i+1][1]-pts[i][1],pts[i+1][0]-pts[i][0])
                angle+=random.uniform(-1.3,1.3)
                fend=(mid[0]+math.cos(angle)*d*0.4,mid[1]+math.sin(angle)*d*0.4)
                self.forks.append(_jitter_pts(mid,fend,3,5))
    def update(self,dt):
        self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        for seg in self.segs:
            spts=[iso_pos(p[0],p[1],28,ox,oy) for p in seg]
            if len(spts)>=2:
                pygame.draw.lines(surf,CYAN,False,spts,3)
                pygame.draw.lines(surf,WHITE,False,spts,1)
        for fork in self.forks:
            spts=[iso_pos(p[0],p[1],28,ox,oy) for p in fork]
            if len(spts)>=2:
                pygame.draw.lines(surf,(80,190,255),False,spts,1)


class Aura:
    def __init__(self,player):
        self.player=player; self.radius=80; self.damage=8
        self.tick=0.5; self.timer=0.0; self.hit_ids=set()
    def update(self,dt,enemies,rings):
        self.timer+=dt
        if self.timer>=self.tick:
            self.timer=0.0; self.hit_ids.clear()
            rings.append(RingEffect(self.player.x,self.player.y,
                                    (200,50,50),self.radius,2,0.45))
        for e in enemies:
            if id(e) in self.hit_ids: continue
            if dist((self.player.x,self.player.y),(e.x,e.y))<=self.radius+e.radius:
                e.hp-=self.damage; self.hit_ids.add(id(e))
    def draw(self,surf,ox,oy):
        r=self.radius; sx,sy=iso_pos(self.player.x,self.player.y,2,ox,oy)
        rw=max(2,int(r*2.0)); rh=max(1,int(r*0.7))
        s=pygame.Surface((rw,rh),pygame.SRCALPHA)
        pygame.draw.ellipse(s,(200,50,50,48),(0,0,rw,rh))
        surf.blit(s,(sx-rw//2,sy-rh//2))


# ─────────────────────────────────────────────
# Gem / Chest / Capsule / FloatText
# ─────────────────────────────────────────────

# Capsule (回復アイテム)
class Capsule:
    def __init__(self, x, y, heal=30):
        self.x = x
        self.y = y
        self.radius = 14
        self.heal = heal
        self.alive = True
        self.bob = random.uniform(0, math.pi * 2)
    def update(self, dt):
        self.bob += dt * 2
    def draw(self, surf, ox, oy):
        # カプセルの簡易グラフィック（赤青の薬カプセル風）
        sx, sy = iso_pos(self.x, self.y, 30, ox, oy)
        sy += int(math.sin(self.bob) * 6)
        pygame.draw.ellipse(surf, (220, 40, 40), (sx-14, sy-7, 28, 14))
        pygame.draw.ellipse(surf, (40, 80, 220), (sx-14, sy-7, 14, 14))
        pygame.draw.ellipse(surf, (255,255,255), (sx-14, sy-7, 28, 14), 2)
        # ハイライト
        pygame.draw.ellipse(surf, (255,255,255,120), (sx-8, sy-5, 8, 4))

class Gem:
    ATTRACT_RANGE = 140   # この距離内でプレイヤーに引き寄せられ始める
    ATTRACT_ACCEL = 900   # 加速度 (px/s²)
    MAX_SPEED     = 480   # 最大速度

    def __init__(self, x, y, value=5):
        self.x, self.y = x, y
        self.value = value
        self.radius = 6 if value <= 5 else (8 if value <= 20 else 10)
        self.alive = True
        self._bob   = random.uniform(0, math.pi*2)
        self._vx = self._vy = 0.0
        self._attracting = False

    def update(self, dt, px, py):
        self._bob += dt * 2.4
        d = dist((self.x, self.y), (px, py))
        if d < self.ATTRACT_RANGE and d > 1:
            self._attracting = True
            # 距離が近いほど強く引き寄せる
            strength = self.ATTRACT_ACCEL * (1.0 + (self.ATTRACT_RANGE - d) / self.ATTRACT_RANGE * 2.5)
            nx, ny = norm(px - self.x, py - self.y)
            self._vx += nx * strength * dt
            self._vy += ny * strength * dt
            spd = math.hypot(self._vx, self._vy)
            if spd > self.MAX_SPEED:
                self._vx = self._vx / spd * self.MAX_SPEED
                self._vy = self._vy / spd * self.MAX_SPEED
        else:
            self._attracting = False
            self._vx *= max(0.0, 1.0 - dt * 4)
            self._vy *= max(0.0, 1.0 - dt * 4)
        self.x += self._vx * dt
        self.y += self._vy * dt

    def draw(self, surf, ox, oy):
        r = self.radius
        hover = math.sin(self._bob) * (4 if not self._attracting else 1)

        # ── 色セット（価値によって変化） ──
        if self.value >= 40:           # ボスドロップ：金紫
            base  = (200,  90, 255)
            light = (230, 160, 255)
            dark  = (100,  20, 160)
            glow  = (200,  90, 255)
        elif self.value >= 10:         # 中級：水色
            base  = ( 60, 200, 255)
            light = (160, 235, 255)
            dark  = ( 10,  90, 170)
            glow  = ( 80, 210, 255)
        else:                          # 通常：シアン
            base  = ( 30, 170, 220)
            light = (130, 220, 255)
            dark  = (  5,  70, 140)
            glow  = ( 50, 190, 240)

        # 地面影（吸引中は影を引き伸ばす）
        draw_shadow(surf, self.x, self.y, ox, oy,
                    r + (4 if self._attracting else 2), 45)

        sx, sy = iso_pos(self.x, self.y, 8 + hover, ox, oy)

        # ── 外周グロー（小さい SRCALPHA サーフェス） ──
        gr = r + 5
        gs = pygame.Surface((gr*2, gr*2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*glow, 40), (gr, gr), gr)
        surf.blit(gs, (sx - gr, sy - gr))

        # ── 球体本体（多層円で立体感） ──
        pygame.draw.circle(surf, dark,  (sx, sy), r + 1)      # 暗い縁取り
        pygame.draw.circle(surf, base,  (sx, sy), r)            # 基本色
        # 内側をやや明るく（球体の中心光）
        inner_r = max(r - 2, 1)
        pygame.draw.circle(surf, light, (sx - r//4, sy - r//4), inner_r * 2 // 3)

        # ── スペキュラーハイライト（楕円＋点） ──
        hl_x = sx - r // 2;  hl_y = sy - r // 2
        hl_w = max(r // 2, 2); hl_h = max(r // 3, 1)
        hs = pygame.Surface((hl_w, hl_h), pygame.SRCALPHA)
        pygame.draw.ellipse(hs, (255, 255, 255, 180), (0, 0, hl_w, hl_h))
        surf.blit(hs, (hl_x, hl_y))
        pygame.draw.circle(surf, WHITE, (sx - r//3, sy - r//3), max(1, r//4))

        # ── 吸引中の軌跡パーティクル風リング（小さい白リング） ──
        if self._attracting:
            pulse = abs(math.sin(self._bob * 4))
            ring_r = int(r + 3 + pulse * 4)
            rs = pygame.Surface((ring_r*2, ring_r*2), pygame.SRCALPHA)
            pygame.draw.circle(rs, (*glow, int(80*pulse)), (ring_r, ring_r), ring_r, 1)
            surf.blit(rs, (sx - ring_r, sy - ring_r))

CHEST_REWARDS=[
    {"name":"HP回復",    "desc":"+60 HP",       "key":"hp"},
    {"name":"魔杖Lv+",   "desc":"魔法弾強化",   "key":"wand"},
    {"name":"斧",        "desc":"斧強化",       "key":"axe"},
    {"name":"雷",        "desc":"雷強化",       "key":"lightning"},
    {"name":"炎",        "desc":"炎強化",       "key":"flame"},
    {"name":"XP爆発",    "desc":"+50 XP",       "key":"xp"},
]

# ─────────────────────────────────────────────
# SP Orb (Special Power drop from enemies)
# ─────────────────────────────────────────────
class SPOrb:
    ATTRACT_RANGE = 160
    ATTRACT_ACCEL = 1100
    MAX_SPEED     = 520

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.radius = 8
        self.alive = True
        self._bob   = random.uniform(0, math.pi*2)
        self._vx = self._vy = 0.0
        self._attracting = False

    def update(self, dt, px, py):
        self._bob += dt * 3.0
        d = dist((self.x, self.y), (px, py))
        if d < self.ATTRACT_RANGE and d > 1:
            self._attracting = True
            strength = self.ATTRACT_ACCEL * (1.0 + (self.ATTRACT_RANGE - d) / self.ATTRACT_RANGE * 2.0)
            nx, ny = norm(px - self.x, py - self.y)
            self._vx += nx * strength * dt
            self._vy += ny * strength * dt
            spd = math.hypot(self._vx, self._vy)
            if spd > self.MAX_SPEED:
                self._vx = self._vx / spd * self.MAX_SPEED
                self._vy = self._vy / spd * self.MAX_SPEED
        else:
            self._attracting = False
            self._vx *= max(0.0, 1.0 - dt * 4)
            self._vy *= max(0.0, 1.0 - dt * 4)
        self.x += self._vx * dt
        self.y += self._vy * dt

    def draw(self, surf, ox, oy):
        r = self.radius
        hover = math.sin(self._bob) * (3 if not self._attracting else 1)
        sx, sy = iso_pos(self.x, self.y, int(hover), ox, oy)
        # Glow aura
        glow_r = r + 6 + int(abs(math.sin(self._bob*2))*4)
        gs = pygame.Surface((glow_r*2, glow_r*2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (255, 200, 0, 50), (glow_r, glow_r), glow_r)
        surf.blit(gs, (sx-glow_r, sy-glow_r))
        # Dark rim
        pygame.draw.circle(surf, (120, 80, 0), (sx, sy), r+2)
        # Body: gold-yellow
        pygame.draw.circle(surf, (255, 180, 0), (sx, sy), r)
        # Inner bright
        pygame.draw.circle(surf, (255, 240, 120), (sx-r//3, sy-r//3), max(r//3, 2))
        # Specular
        pygame.draw.circle(surf, WHITE, (sx-r//3+1, sy-r//3+1), max(r//5, 1))
        # "SP" label
        sp_s = font_tiny.render("SP", True, (80, 40, 0))
        surf.blit(sp_s, (sx - sp_s.get_width()//2, sy - sp_s.get_height()//2))

class Chest:
    def __init__(self,x,y):
        self.x,self.y=x,y; self.radius=18; self.alive=True
        self.bob=random.uniform(0,math.pi*2); self.reward=random.choice(CHEST_REWARDS)
    def update(self,dt): self.bob+=dt*2
    def draw(self,surf,ox,oy):
        zbob=6+math.sin(self.bob)*6
        draw_shadow(surf,self.x,self.y,ox,oy,18,55)
        sx,sy=iso_pos(self.x,self.y,zbob,ox,oy)
        r=pygame.Rect(sx-14,sy-24,28,20)
        pygame.draw.rect(surf,GOLD,r,border_radius=3)
        pygame.draw.rect(surf,ORANGE,r,2,border_radius=3)
        pygame.draw.rect(surf,(200,160,0),(sx-14,sy-28,28,8),border_radius=3)
        pygame.draw.rect(surf,ORANGE,(sx-14,sy-28,28,8),2,border_radius=3)
        pygame.draw.circle(surf,BLACK,(sx,sy-16),3)
        gs=pygame.Surface((60,60),pygame.SRCALPHA)
        pygame.draw.circle(gs,(255,200,0,38),(30,30),30)
        surf.blit(gs,(sx-30,sy-44))

class Ladder:
    def __init__(self,x,y):
        self.x,self.y=x,y; self.radius=24; self.alive=True
        self.bob=0.0; self.pulse=0.0
    def update(self,dt): self.bob+=dt*1.2; self.pulse+=dt*2.2
    def draw(self,surf,ox,oy):
        bv=math.sin(self.bob)*4
        sx,sy=iso_pos(self.x,self.y,0,ox,oy)
        pulse=abs(math.sin(self.pulse))
        N=12          # 段数
        TOTAL_H=130   # 総高さ（px）

        # ── 石段（下から上へ、遠近法で収束）───────────────────
        for i in range(N):
            t=i/(N-1)                         # 0=最下段, 1=最上段
            step_y=sy - int(t*TOTAL_H)
            hw=int(34*(1-t*0.68))             # 横幅（上で細く）
            sh=max(2,int(9*(1-t*0.5)))        # 段の高さ（上で薄く）
            # 明度：上ほど明るい（光源が上）
            br=int(100+t*110+pulse*18*t)
            stone_top =(br,    br-8,  br-18)
            stone_side=(br-45, br-55, br-65)
            stone_edge=(br-70, br-80, br-90)
            # 段上面
            top_pts=[(sx-hw,step_y),(sx+hw,step_y),
                     (sx+hw+5,step_y+sh),(sx-hw-5,step_y+sh)]
            pygame.draw.polygon(surf,stone_top,top_pts)
            pygame.draw.polygon(surf,stone_edge,top_pts,1)
            # 段前面（立ち上がり部分）
            if i>0:
                prev_t=(i-1)/(N-1)
                prev_y=sy-int(prev_t*TOTAL_H)
                prev_hw=int(34*(1-prev_t*0.68))
                prev_sh=max(2,int(9*(1-prev_t*0.5)))
                front_pts=[(sx-hw-5,step_y+sh),(sx+hw+5,step_y+sh),
                           (sx+prev_hw+5,prev_y+prev_sh),(sx-prev_hw-5,prev_y+prev_sh)]
                pygame.draw.polygon(surf,stone_side,front_pts)
                pygame.draw.polygon(surf,stone_edge,front_pts,1)
            # 石目テクスチャ（横線）
            if hw>8:
                tx_br=br-55
                pygame.draw.line(surf,(tx_br,tx_br-8,tx_br-18),
                                 (sx-hw+4,step_y+sh//2),(sx+hw-4,step_y+sh//2),1)

        # ── 最上段の光源グロー ────────────────────────────────
        top_y=sy-TOTAL_H+int(bv)
        glow_layers=[
            (60,int(12+8*pulse),(255,245,200)),
            (42,int(22+14*pulse),(255,240,180)),
            (26,int(45+30*pulse),(255,250,210)),
            (14,int(80+50*pulse),(255,255,240)),
            ( 6,int(180+70*pulse),(255,255,255)),
        ]
        for gr,ga,gc in glow_layers:
            gs=pygame.Surface((gr*3,gr*2),pygame.SRCALPHA)
            pygame.draw.ellipse(gs,(*gc,ga),(0,0,gr*3,gr*2))
            surf.blit(gs,(sx-gr*3//2,top_y-gr+4))

        # ── 光条（ゴッドレイ）────────────────────────────────
        n_rays=7
        for ri in range(n_rays):
            angle=math.radians(-30+ri*(60/(n_rays-1)))
            ray_len=int(45+20*pulse)
            rx2=int(sx+math.sin(angle)*ray_len)
            ry2=int(top_y+12+math.cos(angle)*ray_len*0.4)
            ra=int(35+20*pulse)*(1-abs(ri-n_rays//2)/(n_rays//2+1))
            ray_s=pygame.Surface((2,ray_len),pygame.SRCALPHA)
            for rl in range(ray_len):
                a_fade=int(ra*(1-rl/ray_len)**1.5)
                pygame.draw.line(ray_s,(255,240,180,a_fade),(1,rl),(1,rl))
            ang_deg=math.degrees(angle)-90
            rot_ray=pygame.transform.rotate(ray_s,ang_deg)
            surf.blit(rot_ray,(sx-rot_ray.get_width()//2,top_y+8))

        # ── 足元の石台（地面の穴口）────────────────────────────
        pygame.draw.ellipse(surf,(25,20,35),(sx-38,sy-14,76,22))
        pygame.draw.ellipse(surf,(60,50,80),(sx-38,sy-14,76,22),2)
        pygame.draw.ellipse(surf,(5,3,10),(sx-28,sy-10,56,16))

        # ── ラベル ────────────────────────────────────────────
        lc=(int(200+55*pulse),255,int(180+70*pulse))
        lbl=font_small.render("▲ 地上へ",True,lc)
        surf.blit(lbl,(sx-lbl.get_width()//2,top_y-22+int(bv)))

class FloatText:
    def __init__(self,x,y,text,color,life=1.0,big=False):
        self.x,self.y=x,y; self.text=text; self.color=color
        self.life=self.max_life=life; self.alive=True
        self._pop_t=0.0   # elapsed since spawn, for pop-in
        self._big=big     # scale-up for big numbers
        # auto-scale pop for large damage numbers
        try:
            v=int(text)
            if v>=200: self._big=True
            if v>=500: self.color=(255,80,0)    # orange-red for huge
            elif v>=200: self.color=(255,200,0) # gold for big
        except (ValueError,TypeError): pass
    def update(self,dt):
        prog=1.0-self.life/self.max_life
        speed=70-50*min(prog*2,1.0)   # fast start, slows to 20
        self.y-=speed*dt; self.life-=dt; self._pop_t+=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        fade=self.life/self.max_life
        alpha=int(255*min(fade*3.0,1.0))   # stay bright, fade tail
        pop_prog=min(self._pop_t/0.1,1.0)
        base_scale=1.4 if self._big else 1.0
        scale=(1.5-0.5*pop_prog)*base_scale   # pop-in then settle
        sx,sy=iso_pos(self.x,self.y,50,ox,oy)
        fnt=font_med if self._big else font_small
        s=fnt.render(self.text,True,self.color)
        if scale>1.01 or scale<0.99:
            nw=max(1,int(s.get_width()*scale)); nh=max(1,int(s.get_height()*scale))
            s=pygame.transform.smoothscale(s,(nw,nh))
        # drop-shadow
        shad=s.copy(); shad.fill((0,0,0,150),special_flags=pygame.BLEND_RGBA_MULT)
        shad.set_alpha(alpha//2)
        surf.blit(shad,(sx-s.get_width()//2+2,sy+2))
        s.set_alpha(alpha)
        surf.blit(s,(sx-s.get_width()//2,sy))


class BigFloatText:
    """Large scale-in skill name text — for SP ultimate announcements."""
    def __init__(self, x, y, text, color, life=2.8):
        self.x, self.y = x, y
        self.text = text; self.color = color
        self.life = self.max_life = life; self.alive = True
        self._scale = 0.05
    def update(self, dt):
        self.y -= 18 * dt
        self._scale = min(1.0, self._scale + dt * 7)
        self.life -= dt
        if self.life <= 0: self.alive = False
    def draw(self, surf, ox, oy):
        prog = self.life / self.max_life
        alpha = int(255 * min(1.0, prog * 2.5))
        sx, sy = iso_pos(self.x, self.y, 90, ox, oy)
        base = font_large.render(self.text, True, self.color)
        w = max(1, int(base.get_width() * self._scale))
        h = max(1, int(base.get_height() * self._scale))
        scaled = pygame.transform.smoothscale(base, (w, h))
        shadow = font_large.render(self.text, True, (0, 0, 0))
        shadow_s = pygame.transform.smoothscale(shadow, (w, h))
        shadow_s.set_alpha(alpha // 2)
        scaled.set_alpha(alpha)
        surf.blit(shadow_s, (sx - w // 2 + 3, sy - h // 2 + 3))
        surf.blit(scaled, (sx - w // 2, sy - h // 2))


# ─────────────────────────────────────────────
# Enemy / Boss
# ─────────────────────────────────────────────
class Enemy:
    def __init__(self,x,y,hp,speed,damage,radius,color,xp,sprite_key="enemy_normal"):
        self.x,self.y=x,y; self.hp=self.max_hp=hp; self.speed=speed
        self.damage=damage; self.radius=radius; self.color=color; self.xp=xp
        self.alive=True; self.hit_flash=0.0; self.sprite_key=sprite_key
        self._hphase=random.uniform(0,math.pi*2)
    def update(self,dt,px,py,_b=None,_f=None):
        dx,dy=norm(px-self.x,py-self.y)
        self.x+=dx*self.speed*dt; self.y+=dy*self.speed*dt
        if self.hit_flash>0: self.hit_flash-=dt
    def draw(self,surf,ox,oy,sprites):
        hover=math.sin(pygame.time.get_ticks()*0.003+self._hphase)*4
        # 二重影で立体感（地面AO + 浮遊影）
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,90)
        draw_shadow(surf,self.x,self.y+self.radius*0.3,ox,oy,int(self.radius*0.7),40)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        spr=sprites.get(self.sprite_key)
        if spr:
            blit_dy=gsy-spr.get_height()-int(hover); blit_dx=gsx-spr.get_width()//2
            # ISO 3D 奥行きクローン（左斜め後ろに暗いシルエットで厚みを演出）
            _dp=spr.copy(); _dp.fill((22,18,12,200),special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(_dp,(blit_dx-4,blit_dy+2))
            # 輪郭線（暗シルエットを4方向にずらしてから本体）
            ol=get_enemy_outline(self.sprite_key,spr)
            for odx,ody in ((-2,0),(2,0),(0,-2),(0,2)):
                surf.blit(ol,(blit_dx+odx,blit_dy+ody))
            if self.hit_flash>0:
                ws=spr.copy(); ws.fill((255,255,255,160),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws,(blit_dx,blit_dy))
            else:
                surf.blit(spr,(blit_dx,blit_dy))
            bw=self.radius*2; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-self.radius,blit_dy-8,bw,5))
            pygame.draw.rect(surf,GREEN,(gsx-self.radius,blit_dy-8,int(bw*ratio),5))
        else:
            # スプライト無し時：球体ルックで描画
            sy2=int(gsy-self.radius-hover)
            r=self.radius; cr,cg,cb=self.color
            pygame.draw.circle(surf,(max(cr-40,0),max(cg-40,0),max(cb-40,0)),(gsx,sy2),r+2)
            pygame.draw.circle(surf,self.color,(gsx,sy2),r)
            pygame.draw.circle(surf,(min(cr+80,255),min(cg+80,255),min(cb+80,255)),
                               (gsx-r//3,sy2-r//3),max(r//4,2))
            bw=self.radius*2; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-self.radius,sy2-r-8,bw,5))
            pygame.draw.rect(surf,GREEN,(gsx-self.radius,sy2-r-8,int(bw*ratio),5))

class Boss(Enemy):
    CHARGE_INTERVAL=5.0
    def __init__(self,x,y,level):
        hp=800+level*300; spd=70+level*10
        super().__init__(x,y,hp=hp,speed=spd,damage=25,radius=36,
                         color=PURPLE,xp=80+level*20,sprite_key="boss")
        self.level=level; self.base_speed=spd
        self.charge_timer=self.CHARGE_INTERVAL
        self.charge_dir=(0.0,0.0); self.charging=False
        self.charge_time=0.0; self.telegraph=0.0
        self.name=f"BOSS Lv{level}"
    def update(self,dt,px,py,_b=None,_f=None):
        if self.hit_flash>0: self.hit_flash-=dt
        if self.telegraph>0:
            self.telegraph-=dt
            if self.telegraph<=0: self.charging=True; self.charge_time=0.8
            return
        if self.charging:
            self.charge_time-=dt
            self.x+=self.charge_dir[0]*420*dt; self.y+=self.charge_dir[1]*420*dt
            if self.charge_time<=0: self.charging=False
            return
        dx,dy=norm(px-self.x,py-self.y)
        self.x+=dx*self.speed*dt; self.y+=dy*self.speed*dt
        self.charge_timer-=dt
        if self.charge_timer<=0:
            self.charge_timer=self.CHARGE_INTERVAL
            self.charge_dir=norm(px-self.x,py-self.y); self.telegraph=0.6
    def _draw_boss_hp(self, surf, cx, top_y):
        bw=130; bh=11; ratio=max(0,self.hp/self.max_hp)
        t_ms=pygame.time.get_ticks()
        pulse=abs(math.sin(t_ms*0.005))
        # background
        pygame.draw.rect(surf,(10,5,20),(cx-bw//2-2,top_y-2,bw+4,bh+4),border_radius=5)
        pygame.draw.rect(surf,(35,20,60),(cx-bw//2,top_y,bw,bh),border_radius=4)
        # fill — color by hp ratio
        fw=max(0,int(bw*ratio))
        if ratio>0.6: fc=(180,40,255)
        elif ratio>0.3: fc=(255,80,30)
        else:
            fc=(255,int(20+pulse*50),int(10+pulse*20))
        if fw>0:
            pygame.draw.rect(surf,fc,(cx-bw//2,top_y,fw,bh),border_radius=4)
        # highlight strip
        pygame.draw.rect(surf,(255,255,255,60),(cx-bw//2,top_y,fw,3),border_radius=3)
        # border glow
        bc=(200,60,255) if ratio>0.3 else (255,int(60+pulse*80),0)
        pygame.draw.rect(surf,bc,(cx-bw//2-1,top_y-1,bw+2,bh+2),border_radius=5,width=1)
        # segment marks
        for p in (0.25,0.5,0.75):
            tx=cx-bw//2+int(bw*p)
            pygame.draw.line(surf,(20,10,35),(tx,top_y+1),(tx,top_y+bh-1),1)

    def draw(self,surf,ox,oy,sprites):
        t_ms=pygame.time.get_ticks()
        hover=math.sin(t_ms*0.002+self._hphase)*8
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius+12,120)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)

        # ── 回転するアウターリング ──
        ring_r=self.radius+22; pulse=abs(math.sin(t_ms*0.003))
        rot_angle=t_ms*0.001
        for seg in range(8):
            a0=rot_angle+seg*math.pi/4; a1=a0+math.pi/8
            rw2=int(ring_r*2.2); rh2=int(ring_r*0.8)
            p1=(int(gsx+math.cos(a0)*ring_r*1.1), int(gsy+math.sin(a0)*ring_r*0.4))
            p2=(int(gsx+math.cos(a1)*ring_r*1.1), int(gsy+math.sin(a1)*ring_r*0.4))
            alpha=int(80+pulse*80) if seg%2==0 else int(30+pulse*30)
            pygame.draw.line(surf, (180,60,255,alpha), p1, p2, 2)

        # ── チャージ予兆（赤い危険エリア）──
        if self.telegraph>0:
            flicker=abs(math.sin(self.telegraph*25))
            r=self.radius+int(flicker*30)+20
            rw=max(2,int(r*2.2)); rh=max(1,int(r*0.8))
            ws=pygame.Surface((rw,rh),pygame.SRCALPHA)
            pygame.draw.ellipse(ws,(255,30,30,int(60+flicker*120)),(0,0,rw,rh))
            pygame.draw.ellipse(ws,(255,100,0,int(100+flicker*80)),(0,0,rw,rh),3)
            surf.blit(ws,(gsx-rw//2,gsy-rh//2))
            warn=font_small.render("CHARGE!",True,(255,80,0))
            warn.set_alpha(int(200*flicker+55))
            surf.blit(warn,(gsx-warn.get_width()//2,gsy-r-22))

        spr=sprites.get("boss")
        if spr:
            blit_dy=gsy-spr.get_height()-int(hover)
            blit_dx=gsx-spr.get_width()//2
            # outline glow
            ol=get_enemy_outline("boss",spr)
            glow_a=int(120+pulse*100)
            for odx,ody in ((-4,0),(4,0),(0,-4),(0,4),(-3,-3),(3,-3),(-3,3),(3,3)):
                gl=ol.copy(); gl.set_alpha(glow_a//2)
                surf.blit(gl,(blit_dx+odx,blit_dy+ody))
            if self.hit_flash>0:
                ws2=spr.copy(); ws2.fill((255,255,255,200),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws2,(blit_dx,blit_dy))
            else:
                surf.blit(spr,(blit_dx,blit_dy))
            top_y=blit_dy-18
            pass  # HP bar / name hidden
        else:
            sy2=int(gsy-self.radius-hover)
            pygame.draw.circle(surf,PURPLE,(gsx,sy2),self.radius)


# ─────────────────────────────────────────────
# Godzilla – final boss at 90 sec remaining
# ─────────────────────────────────────────────
def _draw_godzilla(size=160):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    # Ground shadow
    pygame.draw.ellipse(s, (0,0,0,70), (cx-52, size-22, 104, 26))

    # Tail (behind body)
    tail_pts = [(cx+30,size-28),(cx+52,size-50),(cx+68,size-74),(cx+58,size-90),
                (cx+40,size-78),(cx+26,size-55),(cx+20,size-30)]
    pygame.draw.polygon(s, (28,52,18), tail_pts)
    pygame.draw.polygon(s, (20,38,12), tail_pts, 2)

    # Hind legs
    for side,lx in ((-1, cx-28),(1, cx+14)):
        leg = [(lx,size-28),(lx+side*8,size-10),(lx+side*20,size-8),(lx+side*22,size-28)]
        pygame.draw.polygon(s, (22,45,14), leg)
        # claws
        for ci in range(3):
            cx2 = lx+side*(10+ci*4); cy2 = size-8
            pygame.draw.ellipse(s, (80,70,40), (cx2-3,cy2-2,6,6))

    # Body – massive barrel torso
    body_col   = (34,62,22)
    belly_col  = (60,90,38)
    pygame.draw.ellipse(s, body_col,  (cx-40, size-100, 80, 80))
    pygame.draw.ellipse(s, belly_col, (cx-20, size-90, 38, 58))   # lighter belly

    # Dorsal spines (back plates)
    spine_xs = [-22,-12,0,12,22]
    spine_hs  = [ 32, 44,52,42,30]
    for sx2,sh in zip(spine_xs, spine_hs):
        spine_pts = [(cx+sx2-6, size-98),
                     (cx+sx2,   size-98-sh),
                     (cx+sx2+6, size-98)]
        pygame.draw.polygon(s, (14,110,80), spine_pts)
        pygame.draw.polygon(s, (0,160,110), spine_pts, 1)
        # glow on spines
        glow_s = pygame.Surface((14,sh), pygame.SRCALPHA)
        for gi in range(sh):
            a2 = int(120*(1-gi/sh)**1.5)
            pygame.draw.line(glow_s, (0,220,150,a2), (3,gi),(10,gi))
        s.blit(glow_s, (cx+sx2-6, size-98-sh))

    # Arms
    for side,ax in ((-1,cx-38),(1,cx+24)):
        arm_pts = [(ax, size-80),(ax+side*18,size-64),(ax+side*22,size-50),
                   (ax+side*14,size-44),(ax+side*2,size-58),(ax-side*4,size-72)]
        pygame.draw.polygon(s, (28,52,18), arm_pts)
        # claws
        for ci in range(3):
            cxa = ax+side*(12+ci*3); cya = size-44
            pygame.draw.ellipse(s, (80,70,40), (cxa-3,cya-2,6,8))

    # Neck
    pygame.draw.polygon(s, (34,62,22), [(cx-16,size-98),(cx+16,size-98),
                                         (cx+12,size-118),(cx-12,size-118)])

    # Head
    pygame.draw.ellipse(s, (34,62,22), (cx-22, size-136, 44, 38))
    # Snout / jaw
    pygame.draw.ellipse(s, (28,52,18), (cx-18, size-118, 36, 22))
    # Lower jaw open
    pygame.draw.ellipse(s, (18,38,10), (cx-14, size-110, 28, 16))
    pygame.draw.ellipse(s, (180,40,30),(cx-12, size-108, 24, 10))  # mouth red inside
    # Teeth
    for ti in range(5):
        tx2 = cx-10+ti*5
        pygame.draw.polygon(s, WHITE, [(tx2,size-108),(tx2+2,size-100),(tx2+4,size-108)])
    # Eyes (glowing orange)
    pygame.draw.circle(s, (20,40,12),   (cx-8, size-130), 7)
    pygame.draw.circle(s, (255,160,0),  (cx-8, size-130), 5)
    pygame.draw.circle(s, (255,220,80), (cx-8, size-130), 2)
    pygame.draw.circle(s, WHITE,        (cx-6, size-132), 1)
    # Nostrils
    pygame.draw.circle(s, (14,30,8), (cx-6,  size-122), 2)
    pygame.draw.circle(s, (14,30,8), (cx+2,  size-122), 2)
    # Brow ridges
    pygame.draw.arc(s, (20,40,12), (cx-14,size-136,12,8), 0.2, math.pi-0.2, 2)

    # Outline glow (nuclear blue-green)
    gl = pygame.Surface((size,size), pygame.SRCALPHA)
    pygame.draw.ellipse(gl, (0,220,120,18), (cx-46,size-104,92,88))
    s.blit(gl,(0,0))

    return apply_3d_shading(s)


class GodzillaBeam:
    """ゴジラの放射熱線。プレイヤーにも敵にも当たる。"""
    DAMAGE_PLAYER = 60   # per second
    DAMAGE_ENEMY  = 800  # per second
    WIDTH         = 24   # ビーム幅 (world units)
    RANGE         = 1600 # ビームの射程

    def __init__(self, gx, gy, target_angle):
        self.gx = gx; self.gy = gy
        self.angle = target_angle     # 固定角度（追尾しない）
        self.alive = True
        self.duration = 2.0           # ビーム持続時間
        self.timer = self.duration
        self.tick_cd = 0.0            # damage tick

    def update(self, dt, px, py, enemies, player, floats, rings, particles):
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False
            return
        # 角度固定（追尾しない）
        # ビーム軸ベクトル
        bx = math.cos(self.angle); by = math.sin(self.angle)
        self.tick_cd -= dt

        def _in_beam(ex, ey):
            # 点がビームの扇型ライン内にあるか
            dx2 = ex - self.gx; dy2 = ey - self.gy
            along = dx2*bx + dy2*by
            if along < 0 or along > self.RANGE: return False
            perp = abs(dx2*by - dy2*bx)
            return perp < self.WIDTH * 0.5 + 4

        if self.tick_cd <= 0:
            self.tick_cd = 0.1  # 0.1秒ごとにダメージ
            # プレイヤーへのダメージ
            if _in_beam(player.x, player.y) and player.alive:
                player.hp -= self.DAMAGE_PLAYER * 0.1
                player.hurt_flash = 0.18
                rings.append(RingEffect(player.x, player.y, (0,220,120), 30, 2, 0.12))
            # 敵へのダメージ
            for e in enemies:
                if not isinstance(e, GodzillaEnemy) and _in_beam(e.x, e.y):
                    e.hp -= self.DAMAGE_ENEMY * 0.1
                    e.hit_flash = 0.1
                    particles.append(Particle(e.x, e.y, (0,255,150)))

    def draw(self, surf, ox, oy):
        t_ms = pygame.time.get_ticks()
        fade = min(1.0, self.timer / 0.4)
        pulse = 0.5 + 0.5 * math.sin(t_ms * 0.018)
        bx = math.cos(self.angle); by2 = math.sin(self.angle)
        nx2 = -by2; ny2 = bx

        STEPS = 24
        step_r = self.RANGE / STEPS
        w_start = self.WIDTH * 2.2
        w_end   = self.WIDTH * 0.4

        # ── Layer definitions: (width_mult, color, base_alpha)
        # 外→内の順に描画して立体感を出す
        layers = [
            (3.5, (0, 180, 80),   38),   # 最外郭：広い暗緑グロー
            (2.2, (0, 230, 120),  55),   # 中間グロー
            (1.3, (60, 255, 160), 90),   # 内側明グロー
            (0.7, (180, 255, 210),140),  # コア手前
        ]

        beam_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for w_mult, col, base_a in layers:
            for i in range(STEPS):
                t0 = i / STEPS; t1 = (i+1) / STEPS
                r0 = step_r * i;  r1 = step_r * (i+1)
                w0 = w_start * w_mult * (1-t0) + w_end * w_mult * t0
                w1 = w_start * w_mult * (1-t1) + w_end * w_mult * t1
                seg_fade = fade * (1 - t0 * 0.55) * (0.85 + 0.15 * pulse)
                alpha = int(base_a * seg_fade)
                if alpha < 4: continue
                pts_w = [
                    (self.gx+bx*r0+nx2*w0*0.5, self.gy+by2*r0+ny2*w0*0.5),
                    (self.gx+bx*r1+nx2*w1*0.5, self.gy+by2*r1+ny2*w1*0.5),
                    (self.gx+bx*r1-nx2*w1*0.5, self.gy+by2*r1-ny2*w1*0.5),
                    (self.gx+bx*r0-nx2*w0*0.5, self.gy+by2*r0-ny2*w0*0.5),
                ]
                pts_s = [iso_pos(wx, wy, 30, ox, oy) for wx, wy in pts_w]
                pygame.draw.polygon(beam_surf, (*col, alpha), pts_s)
        surf.blit(beam_surf, (0, 0))

        # ── エッジハイライト（ビームの上辺・下辺を明るく = 立体感）
        edge_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for sign in (1, -1):
            prev_s = None
            for i in range(STEPS + 1):
                t0 = i / STEPS
                r0 = step_r * i
                w0 = (w_start * 0.6 * (1-t0) + w_end * 0.6 * t0)
                wx = self.gx + bx*r0 + nx2*w0*0.5*sign
                wy = self.gy + by2*r0 + ny2*w0*0.5*sign
                cur_s = iso_pos(wx, wy, 32, ox, oy)
                if prev_s and i > 0:
                    a_edge = int(200 * fade * (1 - t0 * 0.7))
                    pygame.draw.line(edge_surf, (220, 255, 230, a_edge), prev_s, cur_s, 2)
                prev_s = cur_s
        surf.blit(edge_surf, (0, 0))

        # ── 中心核心：白熱ライン
        core_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        tip_s = iso_pos(self.gx + bx*18,  self.gy + by2*18,  36, ox, oy)
        end_s = iso_pos(self.gx + bx*self.RANGE*0.92, self.gy + by2*self.RANGE*0.92, 30, ox, oy)
        w_core = max(3, int(6 * fade * (1 + 0.25 * pulse)))
        pygame.draw.line(core_surf, (200, 255, 220, int(230*fade)), tip_s, end_s, w_core)
        pygame.draw.line(core_surf, (255, 255, 255, int(200*fade)), tip_s, end_s, max(1, w_core//2))
        surf.blit(core_surf, (0, 0))

        # ── 起点フレア（ゴジラの口元）
        flare_r = int((18 + 10*pulse) * fade)
        if flare_r > 2:
            flare_s = pygame.Surface((flare_r*4, flare_r*4), pygame.SRCALPHA)
            fc = (flare_r*2, flare_r*2)
            pygame.draw.circle(flare_s, (0, 255, 140, int(120*fade)), fc, flare_r*2)
            pygame.draw.circle(flare_s, (200, 255, 220, int(180*fade)), fc, flare_r)
            pygame.draw.circle(flare_s, (255, 255, 255, int(220*fade)), fc, max(2, flare_r//2))
            fx, fy = iso_pos(self.gx + bx*10, self.gy + by2*10, 34, ox, oy)
            surf.blit(flare_s, (fx - flare_r*2, fy - flare_r*2))


class GodzillaEnemy(Boss):
    SPRITE_SIZE = 480   # 3× original 160

    def __init__(self, x, y):
        hp = 12000
        spd = 38   # ゆっくり迫る
        Enemy.__init__(self, x, y, hp=hp, speed=spd, damage=80, radius=270,
                       color=(30,80,20), xp=800, sprite_key="godzilla")
        self.level = 0; self.base_speed = spd
        self.name = "GODZILLA"
        # ビーム関連
        self.beam_cd = 4.0     # 最初のビームまでの待機
        self.beam_charging = False
        self.beam_charge_t = 0.0
        self.beam_angle = 0.0
        self.beam_lock_px = 0.0   # ロックオン時のプレイヤー位置
        self.beam_lock_py = 0.0
        self.active_beam = None   # GodzillaBeamインスタンス
        # telegraph フィールド（Boss互換）
        self.telegraph = 0.0
        self.charging  = False
        self.charge_time = 0.0
        self.charge_timer = 9999

    def update(self, dt, px, py, _b=None, _f=None):
        if self.hit_flash > 0: self.hit_flash -= dt
        # ゆっくりプレイヤーに近づく
        dx, dy = norm(px-self.x, py-self.y)
        self.x += dx*self.speed*dt; self.y += dy*self.speed*dt
        # ビームチャージ
        self.beam_cd -= dt
        if self.beam_cd <= 0 and not self.beam_charging and self.active_beam is None:
            self.beam_charging = True
            self.beam_charge_t = 1.2  # ロックオン警告時間
            # ロックオン時にプレイヤー位置と角度を確定
            self.beam_angle = math.atan2(py-self.y, px-self.x)
            self.beam_lock_px = px
            self.beam_lock_py = py
        if self.beam_charging:
            self.beam_charge_t -= dt
            if self.beam_charge_t <= 0:
                self.beam_charging = False
                # 発射方向はロックオン時に確定した角度で固定
                self.active_beam = GodzillaBeam(self.x, self.y, self.beam_angle)
                self.beam_cd = random.uniform(6.0, 10.0)

    def update_beam(self, dt, px, py, enemies, player, floats, rings, particles):
        """ビームの更新（run_gameから別途呼ぶ）"""
        if self.active_beam:
            self.active_beam.gx = self.x
            self.active_beam.gy = self.y
            self.active_beam.update(dt, px, py, enemies, player, floats, rings, particles)
            if not self.active_beam.alive:
                self.active_beam = None

    def draw(self, surf, ox, oy, sprites):
        hover = math.sin(pygame.time.get_ticks()*0.001+self._hphase)*10
        draw_shadow(surf, self.x, self.y, ox, oy, self.radius, 150)
        draw_shadow(surf, self.x, self.y+self.radius*0.4, ox, oy,
                    int(self.radius*0.7), 70)
        gsx, gsy = iso_pos(self.x, self.y, 0, ox, oy)
        # ビームチャージ：目が光る演出
        if self.beam_charging:
            t_ms = pygame.time.get_ticks()
            charge_r = int(self.radius * 0.5 * (1 - self.beam_charge_t/2.5))
            pulse = abs(math.sin(t_ms*0.012))
            cs = pygame.Surface((charge_r*4, charge_r*4), pygame.SRCALPHA)
            pygame.draw.circle(cs, (0,255,120, int(80*pulse)), (charge_r*2,charge_r*2), charge_r*2)
            pygame.draw.circle(cs, (200,255,160, int(140*pulse)), (charge_r*2,charge_r*2), charge_r)
            surf.blit(cs, (gsx-charge_r*2, gsy-self.radius-charge_r*2))
        spr = sprites.get("godzilla")
        if spr:
            # 480×480 表示のためスケーリング
            if spr.get_width() != self.SPRITE_SIZE:
                spr = pygame.transform.smoothscale(spr, (self.SPRITE_SIZE, self.SPRITE_SIZE))
            blit_dy = gsy - spr.get_height() - int(hover)
            blit_dx = gsx - spr.get_width()//2
            ol = get_enemy_outline("godzilla", spr)
            for odx, ody in ((-6,0),(6,0),(0,-6),(0,6)):
                surf.blit(ol, (blit_dx+odx, blit_dy+ody))
            if self.hit_flash > 0:
                ws = spr.copy()
                ws.fill((255,255,255,200), special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws, (blit_dx, blit_dy))
            else:
                surf.blit(spr, (blit_dx, blit_dy))
            bar_y = blit_dy - 20
        else:
            bar_y = gsy - self.radius - 20
        # HP bar (wide)
        bw = 300; ratio = max(0, self.hp/self.max_hp)
        pygame.draw.rect(surf, (40,0,0),   (gsx-150, bar_y, bw, 14))
        pygame.draw.rect(surf, (20,200,40),(gsx-150, bar_y, int(bw*ratio), 14))
        pygame.draw.rect(surf, (0,255,90), (gsx-150, bar_y, int(bw*ratio), 5))
        t_ms2 = pygame.time.get_ticks()


# ─────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────
CHARACTERS=[
    {"name":"ナイト",       "desc":["高HP・高防御","斧装備でスタート"],
     "color":BLUE,  "hp":200,"speed":175,"sprite":"warior",
     "weapons":{"wand":0,"axe":1,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0},"wand_cd":0.8},
    {"name":"魔法使い",     "desc":["高速魔法攻撃","魔杖Lv2でスタート"],
     "color":PURPLE,"hp":90, "speed":230,"sprite":"mage",
     "weapons":{"wand":2,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0},"wand_cd":0.38},
    {"name":"ローグ",       "desc":["超高速・機敏","聖十字装備でスタート"],
     "color":ORANGE,"hp":110,"speed":290,"sprite":"rogue",
     "weapons":{"wand":0,"axe":0,"cross":1,"garlic":0,"lightning":0,"flame":0,"plague":0},"wand_cd":0.8},
    {"name":"疫病医師",     "desc":["即死オーラ","1タイル以内の敵を消滅"],
     "color":(160,0,220),"hp":150,"speed":210,"sprite":"plague_doctor",
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":1,"scatter":0},"wand_cd":0.8,
     "magma_immune":True},
    {"name":"雷魔道士",     "desc":["拡散雷撃","ランダム複数同時攻撃"],
     "color":(0,200,255),"hp":80,"speed":240,"sprite":"lightning_mage",
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0,"scatter":2},"wand_cd":0.8},
    {"name":"谷の亡霊",     "desc":["谷地形を無視","谷でスピードUP"],
     "color":(160,0,255),"hp":130,"speed":260,"sprite":"valley_wraith",
     "weapons":{"wand":1,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0,"scatter":0},"wand_cd":0.6,
     "valley_immune":True},
    {"name":"死霊使い",     "desc":["死霊を召喚して戦う","他の武器は使えない"],
     "color":(130,0,220),"hp":110,"speed":205,"sprite":"necromancer",
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0,"scatter":0},
     "wand_cd":0.8, "necro_only":True},
    {"name":"ガンマン",     "desc":["高速連射で制圧","SP: 全画面狙撃"],
     "color":(220,180,50),"hp":130,"speed":255,"sprite":"gunman",
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0,"scatter":0,"gun":1},
     "wand_cd":0.8},
]


# ─────────────────────────────────────────────
# Minion (死霊使いの召喚物)
# ─────────────────────────────────────────────
class Minion:
    BASE_SPEED  = 175
    BASE_DMG    = 120
    ATTACK_RANGE = 60   # world units (melee)
    ATTACK_CD   = 0.4
    FOLLOW_DIST = 110

    def __init__(self, x, y, player_max_hp, necro_lv=0):
        self.x = x; self.y = y
        hp_mult  = 1.0 + necro_lv * 0.5
        dmg_mult = 1.0 + necro_lv * 0.3
        self.max_hp = int(player_max_hp * 3 * hp_mult)
        self.hp     = self.max_hp
        self.dmg    = int(self.BASE_DMG * dmg_mult)
        self.speed  = self.BASE_SPEED
        self.alive  = True
        self.atk_cd = 0.0
        self.facing = 0.0
        self.hurt_flash = 0.0

    def update(self, dt, enemies, player, all_minions=None, idx=0):
        if not self.alive: return
        if self.atk_cd  > 0: self.atk_cd   -= dt
        if self.hurt_flash > 0: self.hurt_flash -= dt
        # 分散ターゲット: インデックスごとに異なる敵を狙う
        live = sorted([e for e in enemies if e.alive],
                      key=lambda e: math.hypot(e.x-self.x, e.y-self.y))
        if live:
            target = live[idx % len(live)]
            dx = target.x - self.x; dy = target.y - self.y
            d  = math.hypot(dx, dy) or 1
            self.facing = math.atan2(dy, dx)
            if d > self.ATTACK_RANGE:
                self.x += dx/d * self.speed * dt
                self.y += dy/d * self.speed * dt
            elif self.atk_cd <= 0:
                target.hp -= self.dmg
                self.atk_cd = self.ATTACK_CD
        else:
            # 扇形に分散してプレイヤー周囲を囲む
            angle = (idx / max(len(all_minions) if all_minions else 1, 1)) * math.pi * 2
            tx = player.x + math.cos(angle) * self.FOLLOW_DIST * 0.7
            ty = player.y + math.sin(angle) * self.FOLLOW_DIST * 0.7
            dx = tx - self.x; dy = ty - self.y
            d  = math.hypot(dx, dy) or 1
            if d > 20:
                self.x += dx/d * self.speed * dt
                self.y += dy/d * self.speed * dt
        # ミニオン同士の反発（重なり防止）
        if all_minions:
            for other in all_minions:
                if other is self: continue
                sx = self.x - other.x; sy = self.y - other.y
                sd = math.hypot(sx, sy) or 1
                if sd < 55:
                    push = (55 - sd) / 55 * 180
                    self.x += sx/sd * push * dt
                    self.y += sy/sd * push * dt

    def draw(self, surf, ox, oy):
        sx, sy = iso_pos(self.x, self.y, 0, ox, oy)
        draw_shadow(surf, self.x, self.y, ox, oy, 18, 55)
        if _KYONSI_IMG is not None:
            iw, ih = _KYONSI_IMG.get_size()
            img = pygame.transform.flip(_KYONSI_IMG, math.cos(self.facing) < 0, False)
            if self.hurt_flash > 0:
                img = img.copy()
                img.fill((255,80,80, int(160*min(self.hurt_flash/0.15,1))),
                         special_flags=pygame.BLEND_RGBA_ADD)
            surf.blit(img, (sx - iw//2, sy - ih))
            bar_y = sy - ih - 5
        else:
            pygame.draw.circle(surf, (100, 160, 220), (sx, sy-22), 18)
            bar_y = sy - 44
        bw = 36; hp_r = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surf, (60, 0, 0),    (sx - bw//2, bar_y, bw, 4))
        pygame.draw.rect(surf, (0, 200, 110), (sx - bw//2, bar_y, int(bw*hp_r), 4))


MINION_MAX = 35  # 最大召喚数上限

def minion_cap(level):
    """Lv1=1, 2倍ずつ増加、上限20体"""
    return min(2 ** (level - 1), MINION_MAX)


# ─────────────────────────────────────────────
# Player
# ─────────────────────────────────────────────
class Player:
    PICKUP_RANGE=120
    def __init__(self,char_data,sprites):
        self.x=self.y=0.0; self.max_hp=char_data["hp"]; self.hp=self.max_hp
        self.speed=char_data["speed"]; self.char_color=char_data["color"]
        self.radius=16; self.alive=True; self.hurt_sound_cd=0.0
        self.bob=0.0; self.ice_dir=(0.0,0.0); self.hurt_flash=0.0; self.facing=1  # 1=右, -1=左
        self.vel_x=0.0; self.vel_y=0.0   # smoothed velocity for sprite lean
        self.squash=1.0                   # vertical scale: <1 squash, >1 stretch
        self.sprite=sprites.get(char_data["sprite"])
        self.char_name=char_data["name"]
        self.sp=0.0; self.sp_max=200.0; self.sp_ready=False
        self.weapons={
            "wand":     {"level":char_data["weapons"]["wand"],     "timer":0.0,"cooldown":char_data["wand_cd"]},
            "axe":      {"level":char_data["weapons"]["axe"],      "timer":0.0,"cooldown":1.5},
            "cross":    {"level":char_data["weapons"]["cross"],    "timer":0.0,"cooldown":3.0},
            "garlic":   {"level":char_data["weapons"]["garlic"]},
            "lightning":{"level":char_data["weapons"]["lightning"],"timer":0.0,"cooldown":2.0},
            "flame":    {"level":char_data["weapons"]["flame"],    "timer":0.0,"cooldown":4.0},
            "plague":   {"level":char_data["weapons"].get("plague",0)},
            "scatter":  {"level":char_data["weapons"].get("scatter",0),"timer":0.0,"cooldown":2.2},
            "rain":     {"level":char_data["weapons"].get("rain",0),   "timer":0.0,"cooldown":3.5},
            "gun":      {"level":char_data["weapons"].get("gun",0),    "timer":0.0,"cooldown":0.5},
        }
        self.aura=None
        self.valley_immune=char_data.get("valley_immune",False)
        self.magma_immune=char_data.get("magma_immune",False)
        self.necro_only=char_data.get("necro_only",False)
        self.necro_level=0
        self.accessories=set()
        self.evolutions=set()

    def update(self,dt,keys,enemies,bullets,floats,flames,bolts,rings,particles,snd,shake,terrain_map=None,rain_zones=None):
        dx=dy=0
        if keys[pygame.K_w] or keys[pygame.K_UP]:   dy-=1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy+=1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx-=1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx+=1
        ndx,ndy=norm(dx,dy)
        if dx != 0: self.facing = 1 if dx > 0 else -1  # 左右移動で向きを更新

        cur_t=terrain_map.at(self.x,self.y) if terrain_map else TERRAIN_GRASS
        if cur_t==TERRAIN_ICE:
            if dx or dy:
                self.ice_dir=(self.ice_dir[0]*0.88+ndx*0.12,
                              self.ice_dir[1]*0.88+ndy*0.12)
                il=math.hypot(*self.ice_dir)
                if il>0: self.ice_dir=(self.ice_dir[0]/il,self.ice_dir[1]/il)
            mdx,mdy=self.ice_dir; eff_speed=self.speed
        elif cur_t==TERRAIN_SWAMP:
            mdx,mdy=ndx,ndy; eff_speed=self.speed*0.35
            self.ice_dir=(0.0,0.0)
        elif cur_t==TERRAIN_VALLEY and self.valley_immune:
            mdx,mdy=ndx,ndy; eff_speed=self.speed*1.35
            self.ice_dir=(0.0,0.0)
        else:
            mdx,mdy=ndx,ndy; eff_speed=self.speed
            if dx or dy: self.ice_dir=(ndx,ndy)
            else:        self.ice_dir=(0.0,0.0)

        new_x=self.x+mdx*eff_speed*dt; new_y=self.y+mdy*eff_speed*dt
        if terrain_map:
            if terrain_map.at(new_x,new_y)==TERRAIN_MOUNTAIN:
                if terrain_map.at(new_x,self.y)!=TERRAIN_MOUNTAIN: self.x=new_x
                if terrain_map.at(self.x,new_y)!=TERRAIN_MOUNTAIN: self.y=new_y
            else:
                self.x,self.y=new_x,new_y
        else:
            self.x,self.y=new_x,new_y

        self.bob+=dt*(5 if (dx or dy) else 1.5)
        self.hurt_sound_cd=max(0,self.hurt_sound_cd-dt)
        self.hurt_flash=max(0,self.hurt_flash-dt)
        # smoothed velocity for lean/squash
        target_vx=mdx*eff_speed; target_vy=mdy*eff_speed
        self.vel_x+=(target_vx-self.vel_x)*min(dt*12,1.0)
        self.vel_y+=(target_vy-self.vel_y)*min(dt*12,1.0)
        spd_ratio=math.hypot(self.vel_x,self.vel_y)/max(self.speed,1)
        # stretch when moving, squash when idle bob peaks
        bob_phase=math.sin(self.bob)
        if spd_ratio>0.1:
            self.squash=1.0+0.12*spd_ratio
        else:
            self.squash=1.0-0.08*max(0,bob_phase)   # slight squash on bob bottom

        target=min(enemies,key=lambda e:dist((self.x,self.y),(e.x,e.y)),default=None)

        # Global evolution multipliers (S7/S8)
        _g_dmg=(1.5 if "evo_armageddon" in self.evolutions else 1.0)*\
               (1.3 if "evo_ragnarok"   in self.evolutions else 1.0)*\
               (2.0 if "evo_genesis"    in self.evolutions else 1.0)
        _g_aoe=(1.2 if "evo_armageddon" in self.evolutions else 1.0)*\
               (1.5 if "evo_ragnarok"   in self.evolutions else 1.0)*\
               (2.0 if "evo_genesis"    in self.evolutions else 1.0)

        # ── Wand ──
        w=self.weapons["wand"]
        if w["level"]>=1:
            w["timer"]+=dt
            cd_mult=0.6 if "evo_genesis" in self.evolutions else 1.0
            if w["timer"]>=w["cooldown"]*cd_mult and target:
                w["timer"]=0.0
                ev=self.evolutions
                s4="evo_arcane"  in ev; s5="evo_arcane2"  in ev
                s6a="evo_arcane_storm" in ev; s6b="evo_thunder_gen" in ev
                count=(1+(w["level"]-1)//2
                       +(2 if s4 else 0)+(2 if s5 else 0)
                       +(2 if s6a else 0)+(3 if s6b else 0))
                pierce=1+w["level"]//3+(99 if s4 else 0)
                base_dmg=20+w["level"]*5
                if s5:  base_dmg+=25
                if s6a: base_dmg+=40
                if s6b: base_dmg+=60
                dmg=int(base_dmg*_g_dmg)
                spd=420+(80 if s4 else 0)+(60 if s5 else 0)
                sp=math.radians(8 if s5 else 10 if s4 else 12)
                col=(100,220,255) if s6b else (150,200,255) if s5 else (180,220,255) if s4 else BLUE
                rad=6+(2 if s4 else 0)+(2 if s5 else 0)
                base=math.atan2(target.y-self.y,target.x-self.x)
                for i in range(count):
                    a=base+sp*(i-(count-1)/2)
                    bullets.append(Bullet(self.x,self.y,math.cos(a),math.sin(a),
                        spd,dmg,rad,col,1.5,pierce,style="orb"))
                # S6b: Thunder Genesis also fires bolts
                if s6b and enemies:
                    pool2=sorted(enemies,key=lambda e:dist((self.x,self.y),(e.x,e.y)))[:3]
                    for t2 in pool2:
                        t2.hp-=int(dmg*0.5); t2.hit_flash=0.1
                        bolts.append(LightningBolt([(self.x,self.y),(t2.x,t2.y)]))
                rings.append(RingEffect(self.x,self.y,col,int(38*_g_aoe),2,0.18))
                rings.append(RingEffect(self.x,self.y,(150,200,255),22,2,0.12))
                snd.play("shoot")

        # ── Axe ──
        w=self.weapons["axe"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                ev=self.evolutions
                s4="evo_scythe"  in ev; s5="evo_scythe2" in ev
                s6a="evo_apocalypse" in ev; s6b="evo_doom" in ev
                base_dmg=40+w["level"]*10
                if s4:  base_dmg*=3
                if s5:  base_dmg=int(base_dmg*1.8)
                if s6a: base_dmg=int(base_dmg*1.5)
                if s6b: base_dmg=int(base_dmg*2.0)
                dmg=int(base_dmg*_g_dmg)
                cnt=w["level"]+(4 if s4 else 0)+(2 if s5 else 0)+(2 if s6b else 0)
                spd=400 if s4 else 360
                if s4 or s5:
                    for i in range(cnt):
                        a=math.radians(i*(360/cnt))
                        bullets.append(AxeBullet(self.x,self.y,math.cos(a),math.sin(a),spd,dmg))
                else:
                    # 近い敵TOP3からランダムに選んで狙う
                    pool=sorted(enemies,key=lambda e:dist((self.x,self.y),(e.x,e.y)))[:3]
                    for i in range(cnt):
                        t2=random.choice(pool) if pool else None
                        if t2:
                            base_a=math.atan2(t2.y-self.y,t2.x-self.x)
                        else:
                            base_a=random.uniform(0,math.pi*2)
                        a=base_a+random.uniform(-0.15,0.15)
                        bullets.append(AxeBullet(self.x,self.y,math.cos(a),math.sin(a),360,dmg))
                # S6a: Apocalypse - spawn flame zone on each axe launch
                if s6a:
                    for _ in range(2):
                        a2=random.uniform(0,math.pi*2); r2=random.uniform(80,200)
                        flames.append(FlameZone(self.x+math.cos(a2)*r2,
                                                self.y+math.sin(a2)*r2,
                                                int(80*_g_aoe),int(30*_g_dmg),2.0))
                col=(255,0,255) if s6b else (220,60,255) if s5 else (200,80,255) if s4 else ORANGE
                rings.append(RingEffect(self.x,self.y,col,int((60 if s4 else 42)*_g_aoe),3,0.2))
                snd.play("axe")

        # ── Cross ──
        w=self.weapons["cross"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                for ddx,ddy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    bullets.append(Bullet(self.x,self.y,ddx,ddy,
                        300,30+w["level"]*8,8,YELLOW,2.0,3+w["level"],style="cross"))
                # Cross explosion ring
                rings.append(RingEffect(self.x,self.y,YELLOW,60,3,0.28))
                rings.append(RingEffect(self.x,self.y,(255,255,150),35,2,0.18))
                for _ in range(6):
                    particles.append(Particle(self.x,self.y,YELLOW))
                snd.play("cross")

        # ── Garlic ──
        if self.weapons["garlic"]["level"]>=1 and self.aura is None:
            self.aura=Aura(self)
        if self.aura:
            self.aura.radius=80+self.weapons["garlic"]["level"]*20
            self.aura.damage=5+self.weapons["garlic"]["level"]*3
            self.aura.update(dt,enemies,rings)

        # ── Lightning ──
        w=self.weapons["lightning"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"] and target:
                w["timer"]=0.0
                ev=self.evolutions
                s4="evo_storm"  in ev; s5="evo_storm2"     in ev
                s6a="evo_arcane_storm" in ev; s6b="evo_thunder_gen" in ev
                base_dmg=55+w["level"]*15
                if s4:  base_dmg+=40
                if s5:  base_dmg+=60
                if s6a: base_dmg+=50
                if s6b: base_dmg+=80
                dmg=int(base_dmg*_g_dmg)
                chains=1+w["level"]+(len(enemies) if (s4 or s5) else 0)
                max_dist=99999 if s4 else 350
                target.hp-=dmg; target.hit_flash=0.1
                floats.append(FloatText(target.x,target.y-20,str(dmg),CYAN,0.6))
                pts=[(self.x,self.y),(target.x,target.y)]
                prev=target; hit=[target]
                for _ in range(chains-1):
                    nearby=sorted([e for e in enemies if e not in hit],
                                  key=lambda e:dist((prev.x,prev.y),(e.x,e.y)))
                    if not nearby or dist((prev.x,prev.y),(nearby[0].x,nearby[0].y))>max_dist: break
                    nxt=nearby[0]; nxt.hp-=int(dmg*0.6); nxt.hit_flash=0.1
                    floats.append(FloatText(nxt.x,nxt.y-20,str(int(dmg*0.6)),CYAN,0.5))
                    pts.append((nxt.x,nxt.y)); hit.append(nxt); prev=nxt
                    # S5: Omega Storm - AOE pulse at each chain point
                    if s5:
                        rings.append(RingEffect(nxt.x,nxt.y,CYAN,int(55*_g_aoe),2,0.15))
                bolts.append(LightningBolt(pts))
                col=(0,255,255) if s6b else (0,255,200) if s5 else CYAN
                rings.append(RingEffect(self.x,self.y,col,int((50+(20 if s4 else 0))*_g_aoe),3,0.18))
                rings.append(RingEffect(self.x,self.y,WHITE,25,2,0.12))
                snd.play("lightning"); shake.shake(int((4+(3 if s4 else 0))*min(_g_dmg,2)))

        # ── Flame ──
        w=self.weapons["flame"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                ev=self.evolutions
                s4="evo_inferno"  in ev; s5="evo_inferno2" in ev
                s6a="evo_apocalypse" in ev; s6b="evo_doom" in ev
                base_r=70+w["level"]*20
                base_d=12+w["level"]*6
                if s4:  base_r*=2;   base_d*=2
                if s5:  base_r=int(base_r*1.5); base_d=int(base_d*1.5)
                if s6a: base_r=int(base_r*1.3)
                if s6b: base_d=int(base_d*2)
                dur=3.0*(2.0 if s4 else 1.0)*(1.5 if s5 else 1.0)
                zone_count=3 if s5 else 1
                for zi in range(zone_count):
                    ox,oy=(0,0)
                    if zone_count>1:
                        ang=math.radians(zi*(360/zone_count))
                        ox=math.cos(ang)*80; oy=math.sin(ang)*80
                    flames.append(FlameZone(self.x+ox,self.y+oy,
                        int(base_r*_g_aoe),int(base_d*_g_dmg),dur))
                col=(255,0,0) if s6b else (255,50,0) if s5 else (255,60,0) if s4 else ORANGE
                for _ in range(12+(8 if s4 else 0)+(8 if s5 else 0)):
                    p=Particle(self.x+random.uniform(-30,30),self.y+random.uniform(-15,15),
                               random.choice([col,(255,60,0),(255,200,0)]))
                    p.vy=-abs(p.vy)-100; p.vx*=0.4
                    particles.append(p)
                rings.append(RingEffect(self.x,self.y,col,int((55+(25 if s4 else 0))*_g_aoe),3,0.22))
                snd.play("flame")

        # ── Scatter Lightning ──
        w=self.weapons["scatter"]
        if w["level"]>=1 and enemies:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                count=2+w["level"]
                pool=list(enemies); random.shuffle(pool)
                targets=pool[:min(count,len(pool))]
                dmg=35+w["level"]*12
                for t in targets:
                    t.hp-=dmg; t.hit_flash=0.1
                    floats.append(FloatText(t.x,t.y-20,str(dmg),(0,230,255),0.5))
                    bolts.append(LightningBolt([(self.x,self.y),(t.x,t.y)]))
                rings.append(RingEffect(self.x,self.y,(0,220,255),65,3,0.24))
                rings.append(RingEffect(self.x,self.y,WHITE,32,2,0.14))
                for _ in range(6+w["level"]*2):
                    particles.append(Particle(self.x,self.y,(0,200,255)))
                snd.play("lightning"); shake.shake(3+w["level"])

        # ── Rain of Light ──
        w=self.weapons["rain"]
        if w["level"]>=1 and rain_zones is not None:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                ev=self.evolutions
                s4="evo_lightrain"  in ev
                s5="evo_solarrain"  in ev
                base_r  = 90 + w["level"]*22
                base_dmg= 10 + w["level"]*4
                dur     = 2.5 + w["level"]*0.2
                if s4: base_r=int(base_r*1.6);  base_dmg=int(base_dmg*1.8); dur+=0.5
                if s5: base_r=int(base_r*1.5);  base_dmg=int(base_dmg*1.6); dur+=0.5
                zone_count = 1 + (2 if s4 else 0) + (2 if s5 else 0)
                # ターゲット候補：近い敵の位置 or プレイヤー周囲ランダム
                targets=sorted(enemies,key=lambda e:dist((self.x,self.y),(e.x,e.y)))[:zone_count]
                positions=[(e.x+random.uniform(-20,20), e.y+random.uniform(-20,20)) for e in targets]
                while len(positions)<zone_count:
                    a=random.uniform(0,math.pi*2); r2=random.uniform(60,200)
                    positions.append((self.x+math.cos(a)*r2, self.y+math.sin(a)*r2))
                for i,(px2,py2) in enumerate(positions[:zone_count]):
                    rain_zones.append(RainZone(px2, py2,
                                               int(base_r*_g_aoe),
                                               int(base_dmg*_g_dmg), dur))
                col=(255,255,160) if s5 else (180,220,255) if s4 else (150,200,255)
                rings.append(RingEffect(self.x,self.y,col,int(55*_g_aoe),3,0.22))
                for _ in range(14+(8 if s4 else 0)):
                    particles.append(Particle(self.x,self.y,col))

        # ── Gun weapon ──
        wg = self.weapons.get("gun", {})
        glv = wg.get("level", 0)
        if glv >= 1 and target is not None:
            wg["timer"] = wg.get("timer", 0.0) - dt
            # 連射間隔: Lv1はゆっくり単発、レベルで連射化
            _gun_cds = [0.0, 1.1, 0.85, 0.62, 0.42, 0.28, 0.18, 0.11]
            _gun_cd  = _gun_cds[min(glv, len(_gun_cds)-1)]
            if wg["timer"] <= 0:
                wg["timer"] = _gun_cd
                # バースト弾数: Lv1-2=1発, Lv3-4=2発, Lv5-6=3発, Lv7+=4発
                burst = 1 if glv < 3 else (2 if glv < 5 else (3 if glv < 7 else 4))
                dmg = int(30 + glv * 10)
                base_a = math.atan2(target.y - self.y, target.x - self.x)
                for i in range(burst):
                    spread = 0.0 if burst == 1 else (i - (burst-1)/2) * 0.12
                    a2 = base_a + spread + random.uniform(-0.04, 0.04)
                    bullets.append(GunBullet(self.x, self.y, math.cos(a2), math.sin(a2), dmg))
                # マズルフラッシュパーティクル
                for _ in range(4):
                    p = Particle(self.x, self.y, (255, 220, 100))
                    p.vx = math.cos(base_a)*random.uniform(60,180) + random.uniform(-40,40)
                    p.vy = math.sin(base_a)*random.uniform(60,180) + random.uniform(-40,40) - 40
                    p.life = p.max_life = random.uniform(0.06, 0.14)
                    particles.append(p)

        # ── Contact damage (continuous DPS) ──
        for e in enemies:
            if dist((self.x,self.y),(e.x,e.y))<self.radius+e.radius:
                self.hp-=e.damage*dt
                self.hurt_flash=0.22
                if self.hurt_sound_cd<=0:
                    snd.play("hurt"); self.hurt_sound_cd=0.5
                    # 血しぶきパーティクル
                    for _ in range(8):
                        ang=random.uniform(0,math.pi*2)
                        spd=random.uniform(60,200)
                        p=Particle(self.x+random.uniform(-8,8),
                                   self.y+random.uniform(-8,8),
                                   random.choice([(180,0,0),(220,20,20),(140,0,0),(255,40,40)]))
                        p.vx=math.cos(ang)*spd; p.vy=math.sin(ang)*spd-60
                        p.life=p.max_life=random.uniform(0.25,0.55)
                        particles.append(p)
        if self.hp<=0: self.alive=False

    def _draw_hp_bar(self,surf,cx,top_y):
        bw=84; bh=9; ratio=max(0,self.hp/self.max_hp)
        # color: green→yellow→red
        if ratio>0.6: bar_col=(40,220,80)
        elif ratio>0.3: bar_col=(220,200,30)
        else:
            pulse=abs(math.sin(pygame.time.get_ticks()*0.006))
            bar_col=(255,int(30+pulse*40),int(20+pulse*30))
        # background + border
        pygame.draw.rect(surf,(20,15,25),(cx-bw//2-1,top_y-1,bw+2,bh+2),border_radius=4)
        pygame.draw.rect(surf,(50,40,60),(cx-bw//2,top_y,bw,bh),border_radius=3)
        # fill
        fw=max(0,int(bw*ratio))
        if fw>0:
            pygame.draw.rect(surf,bar_col,(cx-bw//2,top_y,fw,bh),border_radius=3)
        # segment ticks at 25/50/75%
        for pct in (0.25,0.5,0.75):
            tx=cx-bw//2+int(bw*pct)
            pygame.draw.line(surf,(20,15,25),(tx,top_y),(tx,top_y+bh),1)
        # glow when low
        if ratio<=0.3:
            gsurf=pygame.Surface((bw+8,bh+8),pygame.SRCALPHA)
            pulse=abs(math.sin(pygame.time.get_ticks()*0.006))
            pygame.draw.rect(gsurf,(255,60,60,int(50+pulse*60)),(0,0,bw+8,bh+8),border_radius=5)
            surf.blit(gsurf,(cx-bw//2-4,top_y-4))
        # SP-ready indicator: golden top border
        if self.sp>=self.sp_max:
            pulse2=abs(math.sin(pygame.time.get_ticks()*0.005))
            gc=(255,int(180+pulse2*75),0)
            pygame.draw.rect(surf,gc,(cx-bw//2,top_y,bw,2),border_radius=2)

    def draw(self,surf,ox,oy):
        hover=5+math.sin(self.bob)*5
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,70)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        # lean angle: tilt by horizontal velocity
        lean_angle=max(-10,min(10,-self.vel_x/max(self.speed,1)*10))
        if self.sprite:
            spr = pygame.transform.flip(self.sprite, self.facing < 0, False)
            # squash/stretch: scale height by self.squash
            ow,oh=spr.get_width(),spr.get_height()
            new_h=max(1,int(oh*self.squash)); new_w=max(1,int(ow*(2.0-self.squash)*0.5+ow*0.5))
            if abs(new_h-oh)>1 or abs(new_w-ow)>1:
                spr=pygame.transform.smoothscale(spr,(new_w,new_h))
            if abs(lean_angle)>0.5:
                spr=pygame.transform.rotate(spr,lean_angle)
            dy=gsy-spr.get_height()-int(hover)
            dx=gsx-spr.get_width()//2
            # ISO 3D 奥行きクローン（左斜め後ろに暗いシルエットで厚みを演出）
            _dp=spr.copy(); _dp.fill((22,18,12,200),special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(_dp,(dx-4,dy+2))
            if self.hurt_flash>0:
                flash_spr=spr.copy()
                alpha=int(200*min(self.hurt_flash/0.18,1.0))
                flash_spr.fill((255,0,0,alpha),special_flags=pygame.BLEND_RGBA_MULT)
                flash_spr.fill((120,0,0,alpha//2),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(flash_spr,(dx,dy))
            else:
                surf.blit(spr,(dx,dy))
            self._draw_hp_bar(surf,gsx,dy-16)
        else:
            sy2=int(gsy-self.radius-hover)
            col=self.char_color
            if self.hurt_flash>0:
                t=min(self.hurt_flash/0.18,1.0)
                col=(int(col[0]+(255-col[0])*t*0.8),
                     int(col[1]*( 1-t*0.7)),
                     int(col[2]*(1-t*0.7)))
            pygame.draw.circle(surf,col,(gsx,sy2),self.radius)
            self._draw_hp_bar(surf,gsx,sy2-self.radius-16)
        # SP-full golden ring aura
        if self.sp>=self.sp_max:
            t_ms=pygame.time.get_ticks()
            pulse=abs(math.sin(t_ms*0.004))
            gr=self.radius+14+int(pulse*6); gsx3,gsy3=iso_pos(self.x,self.y,0,ox,oy)
            grw=int(gr*2.2); grh=int(gr*0.8)
            gs=pygame.Surface((grw+8,grh+8),pygame.SRCALPHA)
            gc=(255,int(180+pulse*75),0,int(80+pulse*80))
            pygame.draw.ellipse(gs,gc,(0,0,grw+8,grh+8))
            gc2=(255,int(200+pulse*55),0,int(140+pulse*100))
            pygame.draw.ellipse(gs,gc2,(2,2,grw+4,grh+4),2)
            surf.blit(gs,(gsx3-grw//2-4,gsy3-grh//2-4))
        if self.aura: self.aura.draw(surf,ox,oy)
        if self.weapons.get("plague",{}).get("level",0)>=1:
            r=80+self.radius; gsx2,gsy2=iso_pos(self.x,self.y,2,ox,oy)
            rw=max(2,int(r*2.0)); rh=max(1,int(r*0.7))
            ps=pygame.Surface((rw,rh),pygame.SRCALPHA)
            pa=int(18+14*abs(math.sin(pygame.time.get_ticks()*0.003)))
            pygame.draw.ellipse(ps,(140,0,220,pa),(0,0,rw,rh))
            surf.blit(ps,(gsx2-rw//2,gsy2-rh//2))


# ─────────────────────────────────────────────
# Upgrade system / Spawn / HUD / Screens
# ─────────────────────────────────────────────
UPGRADES=[
    {"name":"魔杖Lv+",     "desc":"速く・強い魔法弾",       "key":"wand"},
    {"name":"斧",          "desc":"敵を貫く斧",             "key":"axe"},
    {"name":"聖十字",      "desc":"4方向に十字発射",         "key":"cross"},
    {"name":"ガーリック",  "desc":"周囲にダメージオーラ",   "key":"garlic"},
    {"name":"雷",          "desc":"連鎖雷撃",               "key":"lightning"},
    {"name":"炎",          "desc":"燃焼ゾーン展開",         "key":"flame"},
    {"name":"拡散弾",      "desc":"ランダム多目標雷",       "key":"scatter"},
    {"name":"光の雨",      "desc":"局所的な光の雨でダメージ","key":"rain"},
    {"name":"ガン強化",   "desc":"連射速度UP・ダメージUP",  "key":"gun"},
    {"name":"スピードUP",  "desc":"移動速度+15%",           "key":"speed"},
    {"name":"最大HPアップ","desc":"最大HP+30・回復30",      "key":"maxhp"},
    {"name":"死霊強化",   "desc":"死霊HP+50%・攻撃力+30%","key":"necro_upgrade"},
]

# T1 accessories (unlock first evolution per weapon)
# T2 accessories (unlock second evolution per weapon)
ACCESSORIES=[
    {"name":"魔導書",      "desc":"魔杖S4: アルカンボルト",    "key":"acc_tome",   "color":(100,150,255), "tier":1},
    {"name":"戦士の指輪",  "desc":"斧S4: デスサイズ",         "key":"acc_ring",   "color":(255,160,40),  "tier":1},
    {"name":"雷の杖",      "desc":"雷S4: チェインストーム",   "key":"acc_rod",    "color":(0,220,255),   "tier":1},
    {"name":"地獄炎石",    "desc":"炎S4: インフェルノ",       "key":"acc_ember",  "color":(255,80,30),   "tier":1},
    {"name":"水晶球",      "desc":"魔杖S5: アルカンバレッジ", "key":"acc_crystal","color":(200,230,255), "tier":2},
    {"name":"死神の刃",    "desc":"斧S5: ソウルリーパー",     "key":"acc_reaper", "color":(180,50,255),  "tier":2},
    {"name":"嵐の王冠",    "desc":"雷S5: オメガストーム",     "key":"acc_crown",  "color":(50,255,220),  "tier":2},
    {"name":"深淵核",      "desc":"炎S5: ドラゴンファイア",   "key":"acc_abyss",  "color":(255,50,0),    "tier":2},
    {"name":"光のプリズム","desc":"光の雨S4: 光の豪雨",       "key":"acc_prism",  "color":(200,240,255), "tier":1},
    {"name":"オーロラ石",  "desc":"光の雨S5: 太陽雨",        "key":"acc_aurora", "color":(255,240,120), "tier":2},
]

# Each node: key, name, color, stage, requirements (list of dicts)
# req types: {"w":key,"lv":n}  {"acc":key}  {"evo":key}
EVOLUTION_NODES=[
    # ── Stage 4 (weapon Lv5 + T1 acc) ───────────────────────
    {"key":"evo_arcane",  "name":"アルカンボルト",   "color":(120,180,255),"stage":4,
     "req":[{"w":"wand","lv":5},      {"acc":"acc_tome"}]},
    {"key":"evo_scythe",  "name":"デスサイズ",      "color":(200,80,255), "stage":4,
     "req":[{"w":"axe","lv":5},       {"acc":"acc_ring"}]},
    {"key":"evo_storm",   "name":"チェインストーム","color":(0,240,255),  "stage":4,
     "req":[{"w":"lightning","lv":5}, {"acc":"acc_rod"}]},
    {"key":"evo_inferno", "name":"インフェルノ",    "color":(255,120,20), "stage":4,
     "req":[{"w":"flame","lv":5},     {"acc":"acc_ember"}]},
    {"key":"evo_lightrain","name":"光の豪雨",        "color":(180,230,255),"stage":4,
     "req":[{"w":"rain","lv":5},      {"acc":"acc_prism"}]},

    # ── Stage 5 (S4 evo + T2 acc + weapon Lv7) ───────────────
    {"key":"evo_arcane2",  "name":"アルカンバレッジ","color":(80,140,255), "stage":5,
     "req":[{"evo":"evo_arcane"},  {"w":"wand","lv":7},      {"acc":"acc_crystal"}]},
    {"key":"evo_scythe2",  "name":"ソウルリーパー", "color":(220,60,255), "stage":5,
     "req":[{"evo":"evo_scythe"},  {"w":"axe","lv":7},       {"acc":"acc_reaper"}]},
    {"key":"evo_storm2",   "name":"オメガストーム",  "color":(0,255,180),  "stage":5,
     "req":[{"evo":"evo_storm"},   {"w":"lightning","lv":7}, {"acc":"acc_crown"}]},
    {"key":"evo_inferno2", "name":"ドラゴンファイア","color":(255,50,0),   "stage":5,
     "req":[{"evo":"evo_inferno"}, {"w":"flame","lv":7},     {"acc":"acc_abyss"}]},
    {"key":"evo_solarrain","name":"太陽雨",           "color":(255,240,100),"stage":5,
     "req":[{"evo":"evo_lightrain"},{"w":"rain","lv":7},{"acc":"acc_aurora"}]},

    # ── Stage 6 (two S4 evos fused) ──────────────────────────
    {"key":"evo_arcane_storm","name":"アルカンストーム",    "color":(180,240,255),"stage":6,
     "req":[{"evo":"evo_arcane"},{"evo":"evo_storm"}]},
    {"key":"evo_apocalypse",  "name":"アポカリプス",        "color":(200,30,30),  "stage":6,
     "req":[{"evo":"evo_scythe"},{"evo":"evo_inferno"}]},
    {"key":"evo_thunder_gen", "name":"サンダージェネシス",  "color":(0,255,255),  "stage":6,
     "req":[{"evo":"evo_arcane2"},{"evo":"evo_storm2"}]},
    {"key":"evo_doom",        "name":"ドゥームブリンガー",  "color":(150,0,200),  "stage":6,
     "req":[{"evo":"evo_scythe2"},{"evo":"evo_inferno2"}]},

    # ── Stage 7 (S5+S6 cross-fusions) ────────────────────────
    {"key":"evo_armageddon","name":"アルマゲドン",  "color":(255,110,30),"stage":7,
     "req":[{"evo":"evo_arcane_storm"},{"evo":"evo_doom"}]},
    {"key":"evo_ragnarok",  "name":"ラグナロク",    "color":(255,40,100),"stage":7,
     "req":[{"evo":"evo_thunder_gen"},{"evo":"evo_apocalypse"}]},

    # ── Stage 8 (GENESIS) ─────────────────────────────────────
    {"key":"evo_genesis","name":"★ ジェネシス ★","color":(255,215,0),"stage":8,
     "req":[{"evo":"evo_armageddon"},{"evo":"evo_ragnarok"}]},
]

def check_evolutions(player):
    new_evos=[]
    for node in EVOLUTION_NODES:
        if node["key"] in player.evolutions: continue
        if all(
            (player.weapons[r["w"]]["level"]>=r["lv"] if "w" in r else
             r["acc"] in player.accessories          if "acc" in r else
             r["evo"] in player.evolutions)
            for r in node["req"]
        ):
            player.evolutions.add(node["key"]); new_evos.append(node["name"])
    return new_evos

def pick_upgrades(player,n=3):
    if player.necro_only:
        pool = [
            {"name":"死霊強化",   "desc":"死霊HP+50%・攻撃力+30%","key":"necro_upgrade"},
            {"name":"最大HPアップ","desc":"最大HP+30・回復30",      "key":"maxhp"},
            {"name":"スピードUP", "desc":"移動速度+15%",            "key":"speed"},
        ]
        random.shuffle(pool); return pool[:n]
    pool=[u for u in UPGRADES if u["key"]!="necro_upgrade"
          and not (u["key"]=="wand"    and player.weapons["wand"]["level"]>=8)
          and not (u["key"]=="scatter" and player.weapons["scatter"]["level"]>=8)
          and not (u["key"]=="rain"    and player.weapons["rain"]["level"]>=8)
          and not (u["key"]=="gun"     and player.weapons["gun"]["level"]>=8)]
    for acc in ACCESSORIES:
        if acc["key"] not in player.accessories:
            pool.append(acc)
    random.shuffle(pool); return pool[:n]

def apply_upgrade(player,key):
    if key.startswith("acc_"):
        player.accessories.add(key); return check_evolutions(player)
    if key in ("wand","axe","cross","garlic","lightning","flame","scatter","rain","gun"):
        w=player.weapons[key]; w["level"]=w.get("level",0)+1
        if key=="wand":      w["cooldown"]=max(0.2, 0.8 -w["level"]*0.07)
        if key=="axe":       w["cooldown"]=max(0.5, 1.5 -w["level"]*0.10)
        if key=="lightning": w["cooldown"]=max(0.6, 2.0 -w["level"]*0.15)
        if key=="flame":     w["cooldown"]=max(1.5, 4.0 -w["level"]*0.30)
        if key=="scatter":   w["cooldown"]=max(0.8, 2.2 -w["level"]*0.18)
        if key=="rain":      w["cooldown"]=max(1.2, 3.5 -w["level"]*0.22)
        # gun cooldown is managed dynamically by level table in update
        return check_evolutions(player)
    elif key=="speed":        player.speed*=1.15
    elif key=="maxhp":        player.max_hp+=30; player.hp=min(player.hp+30,player.max_hp)
    elif key=="necro_upgrade": player.necro_level+=1
    return []

def apply_chest_reward(player,key):
    if key=="hp":  player.hp=min(player.max_hp,player.hp+60)
    elif key=="xp": return 50
    elif key in ("wand","axe","lightning","flame"): apply_upgrade(player,key)
    return 0

def spawn_enemy(px,py,elapsed):
    a=random.uniform(0,math.pi*2); r=700
    x=px+math.cos(a)*r; y=py+math.sin(a)*r; diff=min(elapsed/60,5)
    pool=[v for v in VIRUS_STAGES if v["time"]<=elapsed]
    v=random.choice(pool)
    if random.random()<0.18:
        return Enemy(x,y,hp=(28+diff*8)*v["hp"],speed=(175+diff*22)*v["spd"],
                     damage=8*v["dmg"],radius=max(8,v["r"]-3),
                     color=(255,72,72),xp=3,sprite_key=v["key"])
    return Enemy(x,y,hp=(60+diff*25)*v["hp"],speed=(90+diff*10)*v["spd"],
                 damage=15*v["dmg"],radius=v["r"],color=RED,xp=5,sprite_key=v["key"])

def maybe_spawn(px,py,elapsed,since_last,enemies,underground=False):
    # 0-3min: rate 1.5→0.7, count 1-6
    # 3-5min: rate 0.35→0.15, count 8-16  (大増殖フェーズ)
    if elapsed < 180:
        rate  = max(0.7, 1.5 - elapsed/120)
        count = min(1+int(elapsed//30), 6)
    else:
        # 3分以降: 急激に増加
        t2    = elapsed - 180
        rate  = max(0.12, 0.7 - t2/60)
        count = min(8+int(t2//10), 20)
    if underground: count *= 10
    if since_last >= rate:
        for _ in range(count):
            enemies.append(spawn_enemy(px,py,elapsed))
        return 0.0
    return since_last

def spawn_boss(px,py,level):
    a=random.uniform(0,math.pi*2)
    return Boss(px+math.cos(a)*700,py+math.sin(a)*700,level)

def spawn_magma_enemy(px,py,elapsed):
    diff=min(elapsed/60,5)
    col=random.choice([(255,80,0),(210,45,0),(255,130,20),(180,50,0)])
    return Enemy(px,py,hp=50+diff*18,speed=105+diff*12,damage=20,
                 radius=13,color=col,xp=7,sprite_key="enemy_normal")

# ─────────────────────────────────────────────
# Underground UI helpers
# ─────────────────────────────────────────────
def _ang_panel(surf, x, y, w, h, bg, border, cut=8, bw=2):
    c = cut
    pts = [(x+c,y),(x+w-c,y),(x+w,y+c),(x+w,y+h-c),
           (x+w-c,y+h),(x+c,y+h),(x,y+h-c),(x,y+c)]
    pygame.draw.polygon(surf, bg, pts)
    pygame.draw.polygon(surf, border, pts, bw)

def _seg_bar(surf, x, y, w, h, ratio, color, dim=(18,13,28), seg=9, gap=2):
    segs   = max(1, w//(seg+gap))
    filled = int(segs * max(0.0, min(1.0, ratio)))
    for i in range(segs):
        sx = x + i*(seg+gap)
        c  = color if i < filled else dim
        pygame.draw.rect(surf, c, (sx, y, seg, h))
        if i < filled:  # bright tip on filled
            pygame.draw.rect(surf, (min(color[0]+60,255),min(color[1]+60,255),min(color[2]+60,255)),
                             (sx, y, 2, h))

def _brackets(surf, x, y, w, h, color, size=10, bw=2):
    for cx,cy,sx2,sy2 in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
        pygame.draw.line(surf, color, (cx, cy), (cx+sx2*size, cy), bw)
        pygame.draw.line(surf, color, (cx, cy), (cx, cy+sy2*size), bw)

def _divider(surf, x, y, w, color):
    pygame.draw.line(surf, color, (x, y), (x+w, y), 1)
    pygame.draw.rect(surf, color, (x, y-1, 4, 3))
    pygame.draw.rect(surf, color, (x+w-4, y-1, 4, 3))


def draw_hud(surf, player, level, xp, xp_next, elapsed, kills, boss_warn, victory_time=300):
    t_ms = pygame.time.get_ticks()

    # ── Bottom XP panel ──
    bar_h = 26
    _ang_panel(surf, 0, H-bar_h, W, bar_h, UI_BG, NEON_P, cut=0, bw=1)
    lv_s = font_small.render(f"LV.{level:02d}", True, NEON_G)
    surf.blit(lv_s, (6, H-bar_h+4))
    _seg_bar(surf, 68, H-bar_h+5, W-280, bar_h-10, xp/xp_next, NEON_G)
    xp_s = font_tiny.render(f"{xp}/{xp_next} XP", True, (80,75,100))
    surf.blit(xp_s, (68+(W-280-xp_s.get_width())-6, H-bar_h+6))

    # SP gauge (bottom right)
    sp_ratio = player.sp / player.sp_max
    sp_full  = player.sp >= player.sp_max
    sp_col   = (255,200,0) if sp_full else (200,140,0)
    sp_x = W - 268; sp_w = 260; sp_y = H - bar_h + 3; sp_h = bar_h - 6
    _ang_panel(surf, sp_x-4, H-bar_h, sp_w+8, bar_h, (15,12,5), sp_col, cut=0, bw=1)
    _seg_bar(surf, sp_x, sp_y, sp_w, sp_h, sp_ratio, sp_col)
    sp_lbl = font_tiny.render("SP  [SPACE]" if sp_full else f"SP {int(player.sp)}/{int(player.sp_max)}", True, sp_col)
    surf.blit(sp_lbl, (sp_x+4, H-bar_h+6))
    if sp_full:
        pulse = abs(math.sin(t_ms/200))
        gsp = pygame.Surface((sp_w+8, bar_h), pygame.SRCALPHA)
        gsp.fill((255,200,0, int(30+pulse*40)))
        surf.blit(gsp, (sp_x-4, H-bar_h))

    # ── Countdown Timer (top center) ──
    remaining = max(0, int(victory_time - elapsed))
    m2, s2 = divmod(remaining, 60)
    t_str  = f"[ {m2:02d}:{s2:02d} ]"
    danger = remaining <= 30
    t_col  = (255,60,60) if danger else (200,200,210)
    t_surf = font_med.render(t_str, True, t_col)
    tw = t_surf.get_width()+28
    border_c = NEON_R if danger else NEON_P
    _ang_panel(surf, W//2-tw//2, 4, tw, 38, UI_BG, border_c, cut=7, bw=2)
    surf.blit(t_surf, (W//2-t_surf.get_width()//2, 9))
    if danger:
        pulse2 = abs(math.sin(t_ms/180))
        t_surf.set_alpha(int(180+pulse2*75))
        surf.blit(t_surf, (W//2-t_surf.get_width()//2, 9))

    # ── Kill counter (top right) ──
    k_s = font_small.render(f"撃破:{kills:04d}", True, NEON_R)
    kw  = k_s.get_width()+18
    _ang_panel(surf, W-kw-4, 4, kw, 30, UI_BG, NEON_R, cut=5, bw=1)
    surf.blit(k_s, (W-k_s.get_width()-10, 9))

    # ── Weapon chips (top left) ──
    WCOLORS = {"wand":NEON_B,"axe":ORANGE,"cross":YELLOW,
               "garlic":NEON_R,"lightning":CYAN,"flame":ORANGE,"scatter":(0,230,255),
               "rain":(180,220,255),"gun":(255,210,60)}
    wx = 6
    for name, w in player.weapons.items():
        lv = w.get("level", 0)
        if lv == 0: continue
        c   = WCOLORS.get(name, WHITE)
        lbl = font_tiny.render(f"{name[:3].upper()}|{lv}", True, c)
        cw2 = lbl.get_width()+14
        _ang_panel(surf, wx, 6, cw2, 22, UI_BG, c, cut=4, bw=1)
        surf.blit(lbl, (wx+7, 9))
        wx += cw2+4

    # ── Accessory slots (top left, second row) ──
    ACC_COLOR = (220, 180, 60)  # gold
    CHIP_SZ = 24
    ax = 6
    # Empty slots for all accessories
    for acc in ACCESSORIES:
        owned = acc["key"] in player.accessories
        bg  = (28, 22, 8) if owned else (14, 11, 5)
        brd = ACC_COLOR if owned else (60, 50, 20)
        _ang_panel(surf, ax, 32, CHIP_SZ, CHIP_SZ, bg, brd, cut=3, bw=1)
        if owned:
            ic = _make_icon(acc["key"], CHIP_SZ - 4)
            surf.blit(ic, (ax + 2, 34))
        else:
            # empty slot — dim lock mark
            lock = font_tiny.render("?", True, (50, 42, 18))
            surf.blit(lock, (ax + CHIP_SZ//2 - lock.get_width()//2, 34))
        # tooltip on hover
        mx2, my2 = pygame.mouse.get_pos()
        if pygame.Rect(ax, 32, CHIP_SZ, CHIP_SZ).collidepoint(mx2, my2):
            tip_text = acc["name"] if owned else f"{acc['name']} (未取得)"
            tip = font_tiny.render(tip_text, True, ACC_COLOR if owned else (80, 65, 25))
            tip_x = min(ax, W - tip.get_width() - 4)
            _ang_panel(surf, tip_x - 2, 58, tip.get_width() + 6, 18, (10,8,2), ACC_COLOR if owned else (50,40,15), cut=2, bw=1)
            surf.blit(tip, (tip_x, 59))
        ax += CHIP_SZ + 3

    # ── Mute hint ──
    surf.blit(font_tiny.render("[M]ミュート  [ESC]ポーズ", True, (45,40,65)), (W-160, H-bar_h-16))

    # boss_warn UI removed


def levelup_screen(surf, options):
    t_ms = pygame.time.get_ticks()
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 195))
    surf.blit(overlay, (0, 0))
    # Scanlines on overlay
    for row in range(0, H, 4):
        pygame.draw.line(surf, (0, 0, 0, 18), (0, row), (W, row))

    # Title
    title = font_large.render("// パワーサージ //", True, NEON_G)
    _ang_panel(surf, W//2-title.get_width()//2-20, 70,
               title.get_width()+40, title.get_height()+16, UI_BG, NEON_G, cut=10, bw=2)
    _brackets(surf, W//2-title.get_width()//2-20, 70,
              title.get_width()+40, title.get_height()+16, NEON_G, size=12)
    surf.blit(title, (W//2-title.get_width()//2, 78))

    sub = font_small.render("スキル選択  [ 1 ]  [ 2 ]  [ 3 ]", True, (100,95,130))
    surf.blit(sub, (W//2-sub.get_width()//2, 158))

    cw, ch = 330, 130
    total_w = len(options)*cw + (len(options)-1)*22
    sx0 = W//2 - total_w//2
    mx, my = pygame.mouse.get_pos()
    rects = []
    WCOLORS2 = {"wand":NEON_B,"axe":ORANGE,"cross":YELLOW,"garlic":NEON_R,
                "lightning":CYAN,"flame":ORANGE,"scatter":(0,230,255),"speed":NEON_G,"maxhp":NEON_R}

    for i, opt in enumerate(options):
        rx = sx0 + i*(cw+22); ry = 210
        rect = pygame.Rect(rx, ry, cw, ch); rects.append(rect)
        hover = rect.collidepoint(mx, my)
        is_acc = opt["key"].startswith("acc_")
        c     = opt.get("color") or WCOLORS2.get(opt["key"], WHITE)
        if is_acc:
            bg  = (28, 22, 6) if not hover else (40, 32, 8)
            c   = opt.get("color", (220, 180, 60))
        else:
            bg  = (22, 16, 36) if not hover else (32, 22, 52)
        _ang_panel(surf, rx, ry, cw, ch, bg, c, cut=10, bw=2)
        _brackets(surf, rx, ry, cw, ch, c, size=10, bw=1)
        _scan_overlay(surf, (rx, ry, cw, ch), 22)
        # Number badge
        badge = font_small.render(f"[{i+1}]", True, c)
        surf.blit(badge, (rx+10, ry+10))
        # ACC badge for accessories
        if is_acc:
            acc_tag = font_tiny.render("★ アクセサリー", True, (220, 180, 60))
            tag_bg = pygame.Surface((acc_tag.get_width()+8, acc_tag.get_height()+4), pygame.SRCALPHA)
            tag_bg.fill((60, 45, 10, 180))
            surf.blit(tag_bg, (rx+cw-acc_tag.get_width()-12, ry+6))
            surf.blit(acc_tag, (rx+cw-acc_tag.get_width()-8, ry+8))
        # Icon for all items
        ic = _make_icon(opt["key"], 40)
        surf.blit(ic, (rx+cw-50, ry+ch//2-20))
        # Name
        nm = font_med.render(opt["name"], True, WHITE)
        surf.blit(nm, (rx+12, ry+38))
        # Divider
        _divider(surf, rx+10, ry+72, cw-20, c)
        # Desc
        desc = font_tiny.render(opt["desc"], True, (140,135,160))
        surf.blit(desc, (rx+12, ry+80))
        # Hover glow
        if hover:
            gsurf = pygame.Surface((cw, ch), pygame.SRCALPHA)
            _ang_panel(gsurf, 0, 0, cw, ch, (0,0,0,0), (*c, 60), cut=10, bw=4)
            surf.blit(gsurf, (rx, ry))
    return rects


def character_select(surf, sprites):
    t_start = pygame.time.get_ticks()
    selected = None; char_rects = []
    while selected is None:
        clock.tick(60)
        t_ms = pygame.time.get_ticks() - t_start
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_KP1): selected = 0
                if event.key in (pygame.K_2, pygame.K_KP2): selected = 1
                if event.key in (pygame.K_3, pygame.K_KP3): selected = 2
                if event.key in (pygame.K_4, pygame.K_KP4) and len(CHARACTERS)>3: selected = 3
                if event.key in (pygame.K_5, pygame.K_KP5) and len(CHARACTERS)>4: selected = 4
                if event.key in (pygame.K_6, pygame.K_KP6) and len(CHARACTERS)>5: selected = 5
                if event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx2, my2 = pygame.mouse.get_pos()
                for i, rect in enumerate(char_rects):
                    if rect.collidepoint(mx2, my2): selected = i

        # Background
        surf.fill(DARK)
        step = 80
        for gx in range(-1, W//step+2):
            pygame.draw.line(surf, UI_GRID, (gx*step, 0), (gx*step, H))
        for gy in range(-1, H//step+2):
            pygame.draw.line(surf, UI_GRID, (0, gy*step), (W, gy*step))
        for gx in range(-1, W//step+2):
            for gy in range(-1, H//step+2):
                pygame.draw.circle(surf, (38, 28, 60), (gx*step, gy*step), 2)

        # Header panel
        title_str = "//  キャラクター選択  //"
        title_s   = font_large.render(title_str, True, NEON_P)
        th = title_s.get_height()
        _ang_panel(surf, W//2-title_s.get_width()//2-24, 30,
                   title_s.get_width()+48, th+16, UI_BG, NEON_P, cut=12, bw=2)
        _brackets(surf, W//2-title_s.get_width()//2-24, 30,
                  title_s.get_width()+48, th+16, NEON_P, size=14)
        surf.blit(title_s, (W//2-title_s.get_width()//2, 38))

        sub_s = font_small.render("[ 1 ] - [ 6 ] またはクリックで選択", True, (80,75,110))
        surf.blit(sub_s, (W//2-sub_s.get_width()//2, 120))

        mx, my = pygame.mouse.get_pos()
        ch2=295; gap=18
        cw2=min(304,(W-40-(len(CHARACTERS)-1)*gap)//len(CHARACTERS))
        total_w=len(CHARACTERS)*cw2+(len(CHARACTERS)-1)*gap
        sx0=W//2-total_w//2
        char_rects = []

        for i, cd in enumerate(CHARACTERS):
            rx = sx0 + i*(cw2+gap); ry = 155
            rect = pygame.Rect(rx, ry, cw2, ch2); char_rects.append(rect)
            hover = rect.collidepoint(mx, my)
            c     = cd["color"]
            pulse = abs(math.sin(t_ms/600 + i)) * 0.4 + 0.6
            border_c = tuple(int(v*pulse) for v in c)
            bg    = (18, 13, 30) if not hover else (26, 18, 42)
            _ang_panel(surf, rx, ry, cw2, ch2, bg, border_c, cut=12, bw=2)
            _brackets(surf, rx, ry, cw2, ch2, c, size=14, bw=2)
            _scan_overlay(surf, (rx, ry, cw2, ch2), 20)

            # Index badge
            badge = font_large.render(f"{i+1}", True, c)
            surf.blit(badge, (rx+10, ry+8))

            # Sprite preview
            spr = sprites.get(cd["sprite"])
            if spr:
                sc  = pygame.transform.scale(spr, (88, 88))
                surf.blit(sc, (rx+cw2//2-44, ry+42))
            else:
                pygame.draw.circle(surf, c, (rx+cw2//2, ry+86), 36)

            # Divider
            _divider(surf, rx+10, ry+138, cw2-20, c)

            # Name
            nm = font_med.render(cd["name"].upper(), True, WHITE)
            surf.blit(nm, (rx+cw2//2-nm.get_width()//2, ry+148))

            # Stats
            stats = [
                (f"HP   {cd['hp']:>4}", NEON_R),
                (f"SPD  {cd['speed']:>4}", NEON_G),
            ]
            for j, (st, sc2) in enumerate(stats):
                s2 = font_small.render(st, True, sc2)
                surf.blit(s2, (rx+16, ry+182+j*22))

            # Divider 2
            _divider(surf, rx+10, ry+232, cw2-20, (40,35,60))

            # Desc
            for j, line in enumerate(cd["desc"]):
                dl = font_tiny.render(line, True, (120,115,150))
                surf.blit(dl, (rx+16, ry+242+j*18))

            # Hover glow outline
            if hover:
                gs2 = pygame.Surface((cw2, ch2), pygame.SRCALPHA)
                _ang_panel(gs2, 0, 0, cw2, ch2, (0,0,0,0), (*c, 70), cut=12, bw=5)
                surf.blit(gs2, (rx, ry))

        pygame.display.flip()
    return CHARACTERS[selected]


def _make_icon(key, size=30):
    """Draw a unique icon Surface for an accessory or evolution key."""
    s=size; h=s//2
    ic=pygame.Surface((s,s),pygame.SRCALPHA)
    def circ(col,cx,cy,r,w=0): pygame.draw.circle(ic,col,(cx,cy),r,w)
    def line(col,x1,y1,x2,y2,w=1): pygame.draw.line(ic,col,(x1,y1),(x2,y2),w)
    def poly(col,pts,w=0): pygame.draw.polygon(ic,col,pts,w)
    def rect(col,x,y,ww,hh,r=0,w=0): pygame.draw.rect(ic,col,(x,y,ww,hh),w,border_radius=r)
    def arc(col,rx,ry,rw,rh,a1,a2,w=2):
        pygame.draw.arc(ic,col,(rx,ry,rw,rh),a1,a2,w)
    def star_pts(n,r1,r2,cx,cy,off=0):
        pts=[]
        for i in range(n*2):
            r=r1 if i%2==0 else r2
            a=math.radians(i*180/n+off)
            pts.append((int(cx+math.cos(a)*r),int(cy+math.sin(a)*r)))
        return pts

    if key=="acc_tome":       # 魔法書
        rect((60,90,180),3,4,s-6,s-8,2)
        line((100,140,255),h,4,h,s-4,1)
        for yy in range(7,s-4,4):
            line((150,190,255),5,yy,h-2,yy)
            line((150,190,255),h+2,yy,s-5,yy)
        rect((120,160,255),3,4,s-6,s-8,2,1)
        circ((255,220,80),h,5,3)
    elif key=="acc_ring":     # リング
        circ((200,130,20),h,h,h-2,4)
        circ((255,210,80),h,h+1,h-2,2)
        for a in range(0,360,60):
            ex=int(h+math.cos(math.radians(a))*(h-2))
            ey=int(h+math.sin(math.radians(a))*(h-2))
            circ((255,200,60),ex,ey,2)
    elif key=="acc_rod":      # 雷杖
        line((160,140,90),h,2,h-2,s-2,2)
        pts=[(h+2,3),(h-3,h-1),(h+2,h-1),(h-3,s-3)]
        pygame.draw.lines(ic,(0,220,255),False,pts,2)
        circ((0,180,255),h+2,3,3)
    elif key=="acc_ember":    # 炎の核
        pts=[(h,2),(h+7,h+2),(h+4,h+8),(h,s-2),(h-4,h+8),(h-7,h+2)]
        poly((220,60,10),pts)
        pts2=[(h,7),(h+3,h+2),(h,h+8),(h-3,h+2)]
        poly((255,200,50),pts2)
        circ((255,240,100),h,h,3)
    elif key=="acc_crystal":  # 水晶球
        circ((140,190,255),h,h,h-2)
        circ((220,240,255),h-4,h-4,5)
        circ((180,215,255),h,h,h-2,2)
        circ((255,255,255),h-5,h-5,2)
    elif key=="acc_reaper":   # 鎌の刃
        line((160,140,170),h+5,s-1,h-5,1,2)
        arc((200,60,255),0,0,s-4,s-4,math.pi*0.8,math.pi*1.9,3)
        circ((180,40,220),h-5,2,3)
    elif key=="acc_crown":    # 嵐の王冠
        pts=[(3,s-4),(3,h),(h-5,3),(h,h-4),(h+5,3),(s-3,h),(s-3,s-4)]
        poly((30,200,180),pts)
        poly((0,240,200),pts,1)
        for cx2,cy2 in [(4,h-1),(h,3),(s-4,h-1)]:
            circ((100,255,230),cx2,cy2,2)
    elif key=="acc_abyss":    # 深淵核
        circ((20,0,40),h,h,h-1)
        for a in range(0,360,45):
            ex=int(h+math.cos(math.radians(a))*(h-3))
            ey=int(h+math.sin(math.radians(a))*(h-3))
            line((100,0,150),h,h,ex,ey)
        circ((200,0,100),h,h,5)
        circ((255,50,150),h,h,2)
        circ((80,0,120),h,h,h-1,2)
    elif key=="acc_prism":    # 光のプリズム
        pts=[(h,2),(h+8,h-2),(h+5,s-3),(h-5,s-3),(h-8,h-2)]
        poly((160,220,255),pts)
        poly((220,240,255),pts,1)
        line((255,255,255),h,2,h-8,h+6); line((200,230,255),h,2,h+8,h+6)
        circ((255,255,255),h,h,3)
    elif key=="acc_aurora":   # オーロラ石
        for i,col_a in enumerate([(255,200,80),(100,255,200),(200,150,255)]):
            arc(col_a,3+i*2,3+i*2,s-6-i*4,s-6-i*4,math.pi*0.2+i*0.3,math.pi*0.9+i*0.3,2)
        circ((255,240,120),h,h,4)
        circ((255,255,200),h,h,2)
    elif key=="rain":          # 光の雨武器
        for i in range(5):
            rx2=h-4+i*2; ry_start=3+i*2
            line((180,220,255),rx2,ry_start,rx2-3,s-4,1)
        circ((255,255,200),h,3,3)
        circ((220,240,255),h,3,2)
        line((200,230,255),3,h,s-3,h,1)

    # ─── S4 evolutions ────────────────────────────────────────
    elif key=="evo_arcane":   # 魔法弾
        circ((80,130,255),h,h,7)
        circ((200,220,255),h,h,3)
        for a in range(0,360,45):
            ex=int(h+math.cos(math.radians(a))*(h-2))
            ey=int(h+math.sin(math.radians(a))*(h-2))
            line((120,170,255),h,h,ex,ey)
    elif key=="evo_scythe":   # 死神の鎌
        line((180,60,255),h+5,s-1,h-6,1,2)
        arc((210,80,255),1,1,s-5,s-5,math.pi*1.15,math.pi*1.95,3)
        circ((220,80,255),h-6,2,3)
    elif key=="evo_storm":    # チェイン雷
        pts=[(h+2,2),(h-2,h-1),(h+2,h-1),(h-2,s-2)]
        pygame.draw.lines(ic,(0,220,255),False,pts,2)
        circ((0,170,220),4,h,3,1)
        circ((0,170,220),s-4,h,3,1)
        line((0,180,220),7,h,s-7,h)
    elif key=="evo_inferno":  # 炎柱
        for a in range(0,360,60):
            ex=int(h+math.cos(math.radians(a))*(h-1))
            ey=int(h+math.sin(math.radians(a))*(h-1))
            line((255,60,0),h,h,ex,ey,2)
        circ((255,150,0),h,h,6)
        circ((255,230,50),h,h,3)

    # ─── S5 evolutions ────────────────────────────────────────
    elif key=="evo_arcane2":  # 魔法連射
        for ox,oy,r in [(-7,-3,3),(1,-8,4),(7,-2,3),(0,6,5)]:
            circ((70,120,240),h+ox,h+oy,r)
            circ((200,220,255),h+ox,h+oy,max(1,r-2))
    elif key=="evo_scythe2":  # 魂の刈り手（髑髏）
        pygame.draw.ellipse(ic,(190,50,240),(3,2,s-6,h+4))
        rect((190,50,240),7,h+3,s-14,7)
        circ((15,0,25),h-5,h-2,3)
        circ((15,0,25),h+5,h-2,3)
        line((190,50,240),h,h+7,h,s-1,2)
    elif key=="evo_storm2":   # オメガ嵐
        circ((0,220,170),h,h-2,h-3,3)
        line((0,230,180),3,s-4,9,s-4,2)
        line((0,230,180),s-3,s-4,s-9,s-4,2)
        for a in range(0,360,90):
            ex=int(h+math.cos(math.radians(a))*(h-1))
            ey=int(h+math.sin(math.radians(a))*(h-1))
            circ((0,255,200),ex,ey,2)
    elif key=="evo_inferno2": # 龍炎
        poly((220,40,0),[(3,h+5),(h-3,2),(s-3,h),(h+4,s-1),(3,s-3)])
        circ((255,200,50),h-2,h-2,4)
        circ((255,250,100),h-2,h-2,2)
        line((255,100,0),h+4,h+2,s-2,h+4,2)
    elif key=="evo_lightrain": # 光の豪雨
        for i in range(7):
            rx2=3+i*5; ry_s=2+i%3*3
            line((150,210,255),rx2,ry_s,rx2-4,s-3,1)
        circ((255,255,180),h,2,4)
        circ((255,255,255),h,2,2)
        circ((180,220,255),h,h,h-2,2)
    elif key=="evo_solarrain":  # 太陽雨
        circ((255,220,60),h,h,h-2)
        circ((255,255,100),h,h,h-5)
        for i in range(6):
            rx2=3+i*6; ry_s=4
            line((255,240,120),rx2,ry_s,rx2-3,s-2,2)
        circ((255,255,200),h,h,4)

    # ─── S6 fusions ───────────────────────────────────────────
    elif key=="evo_arcane_storm":
        circ((120,180,255),h-3,h-3,6)
        pts=[(h+4,2),(h,h-2),(h+4,h-2),(h,s-2)]
        pygame.draw.lines(ic,(180,240,255),False,pts,2)
    elif key=="evo_apocalypse":
        circ((200,30,30),h,h,6)
        for a in range(0,360,45):
            r1,r2=7,h-1
            x1=int(h+math.cos(math.radians(a))*r1)
            y1=int(h+math.sin(math.radians(a))*r1)
            x2=int(h+math.cos(math.radians(a))*r2)
            y2=int(h+math.sin(math.radians(a))*r2)
            line((220,50,50),x1,y1,x2,y2,2)
    elif key=="evo_thunder_gen":
        line((0,210,255),h,1,h,s-1,2)
        line((0,210,255),1,h,s-1,h,2)
        pts=[(h+3,2),(h-2,h-2),(h+3,h-2),(h-2,s-2)]
        pygame.draw.lines(ic,(180,255,255),False,pts,2)
    elif key=="evo_doom":
        for r2 in range(h-2,1,-4):
            a2=(h-r2)*70
            circ((int(80+r2*6),0,int(150+r2*5)),h,h,r2,1)
        circ((200,0,255),h,h,3)

    # ─── S7 ───────────────────────────────────────────────────
    elif key=="evo_armageddon":
        pts=star_pts(4,h-1,5,h,h,-90)
        poly((255,120,30),pts)
        poly((255,210,100),pts,1)
        circ((255,240,150),h,h,3)
    elif key=="evo_ragnarok":
        line((255,40,100),h,1,h,s-1,3)
        line((255,40,100),1,h-5,s-1,h-5,3)
        line((255,100,160),h-7,h+5,h+7,h+5,2)
        circ((255,80,130),h,h-5,4)

    # ─── S8 GENESIS ───────────────────────────────────────────
    elif key=="evo_genesis":
        pts=star_pts(8,h-1,6,h,h,-90)
        poly((255,215,0),pts)
        poly((255,255,180),pts,1)
        circ((255,255,255),h,h,5)
        circ((255,240,100),h,h,2)

    # ─── Weapons ──────────────────────────────────────────────
    elif key=="wand":         # 魔法杖
        line((160,140,90),h+4,s-2,h-2,4,2)
        circ((80,130,255),h-2,4,5)
        circ((180,210,255),h-2,4,2)
        for a2 in range(0,360,90):
            ex=int(h-2+math.cos(math.radians(a2))*6)
            ey=int(4+math.sin(math.radians(a2))*6)
            circ((100,160,255),ex,ey,1)
    elif key=="axe":          # 斧
        pts=[(h-1,2),(h+8,h),(h+4,h+2),(h+4,s-2),(h-4,s-2),(h-4,h+2),(h-8,h)]
        poly((200,120,30),pts)
        poly((255,180,60),pts,1)
        line((160,130,80),h,h+2,h,s-2,2)
    elif key=="cross":        # 十字架
        rect((220,200,50),h-3,2,6,s-4,1)
        rect((220,200,50),2,h-3,s-4,6,1)
        circ((255,240,100),h,h,4)
    elif key=="garlic":       # ニンニク
        circ((230,220,180),h,h+3,h-4)
        for ox2,oy2 in [(-4,-5),(4,-5),(0,-8)]:
            circ((210,200,160),h+ox2,h+oy2,4)
        circ((255,240,200),h,h+3,h-4,1)
        line((100,140,60),h,s-3,h,h+7,1)
    elif key=="lightning":    # 雷
        pts=[(h+3,2),(h-2,h),(h+3,h),(h-3,s-2)]
        pygame.draw.lines(ic,(0,200,255),False,pts,3)
        pygame.draw.lines(ic,(180,240,255),False,pts,1)
    elif key=="flame":        # 炎
        pts=[(h,2),(h+8,h+2),(h+5,h+7),(h,s-2),(h-5,h+7),(h-8,h+2)]
        poly((220,60,10),pts)
        pts2=[(h,7),(h+4,h+3),(h,h+9),(h-4,h+3)]
        poly((255,200,50),pts2)
    elif key=="scatter":      # 散弾雷
        for ox2,oy2 in [(-7,2),(0,-1),(7,2)]:
            pts=[(h+ox2,oy2),(h+ox2-2,h+oy2),(h+ox2+2,h+oy2),(h+ox2,s-2+oy2)]
            pygame.draw.lines(ic,(0,220,255),False,pts,2)
    elif key=="speed":        # 速度
        for i2 in range(3):
            ox2=i2*5-5
            pygame.draw.polygon(ic,(80,220,120),
                [(h+ox2,h-7),(h+ox2+7,h),(h+ox2,h+7),(h+ox2-2,h)])
    elif key=="maxhp":        # 最大HP
        rect((220,60,60),h-3,3,6,s-6,1)
        rect((220,60,60),3,h-3,s-6,6,1)
        circ((255,100,100),h,h,4)
    else:
        circ((100,90,120),h,h,h-2)
        circ((140,130,160),h,h,h-2,1)
    return ic


def draw_evolution_tree(surf, player):
    t_ms=pygame.time.get_ticks()
    overlay=pygame.Surface((W,H),pygame.SRCALPHA)
    overlay.fill((0,0,0,210)); surf.blit(overlay,(0,0))
    for row in range(0,H,8): pygame.draw.line(surf,(0,0,0,30),(0,row),(W,row))

    # Title bar
    title=font_large.render("// 進化ツリー //",True,(255,215,0))
    pulse=abs(math.sin(t_ms*0.0015))
    tw=title.get_width()+50
    _ang_panel(surf,W//2-tw//2,4,tw,36,UI_BG,(255,215,0),cut=10,bw=2)
    surf.blit(title,(W//2-title.get_width()//2,8))

    # ── Layout ───────────────────────────────────────────────────────────────
    LANES=[W//2-560,W//2-280,W//2,W//2+280,W//2+560]
    # Y centers per stage row
    SY={
        "acc1":52,"acc2":98,
        "s4":158,"s5":232,"s6":316,"s7":405,"s8":490
    }
    ICON=28          # icon size
    NW,NH=172,62     # node card w/h
    AW,AH=160,42     # accessory card w/h
    node_pos={}      # key→(cx,cy) bottom-center for connectors

    def _wire(x1,y1,x2,y2,col,w=1):
        pygame.draw.line(surf,col,(x1,y1),(x2,y2),w)

    def _acc_card(acc,cx,cy):
        owned=acc["key"] in player.accessories
        c=acc["color"] if owned else (52,48,70)
        bg=(30,22,50) if owned else (14,11,22)
        _ang_panel(surf,cx-AW//2,cy-AH//2,AW,AH,bg,c,cut=8,bw=2)
        if owned:
            glo=pygame.Surface((AW,AH),pygame.SRCALPHA)
            _ang_panel(glo,0,0,AW,AH,(0,0,0,0),(*c,int(40+30*pulse)),cut=8,bw=3)
            surf.blit(glo,(cx-AW//2,cy-AH//2))
        # Icon
        ic=_make_icon(acc["key"],ICON)
        if not owned: ic.set_alpha(80)
        surf.blit(ic,(cx-AW//2+6,cy-ICON//2))
        # Tier badge
        tier_col=(255,200,60) if acc["tier"]==1 else (200,180,255)
        tb=font_tiny.render("T"+str(acc["tier"]),True,tier_col if owned else (60,55,80))
        surf.blit(tb,(cx-AW//2+6+ICON+3,cy-AH//2+3))
        # Name
        nm=font_small.render(acc["name"],True,WHITE if owned else (65,60,85))
        surf.blit(nm,(cx-AW//2+6+ICON+3,cy-5))
        # Desc
        ds=font_tiny.render(acc["desc"],True,c if owned else (50,45,70))
        surf.blit(ds,(cx-AW//2+6+ICON+3,cy+10))
        node_pos[acc["key"]]=(cx,cy+AH//2)

    def _evo_card(node,cx,cy):
        unlocked=node["key"] in player.evolutions
        c=node["color"] if unlocked else (52,48,70)
        bg=(28,18,48) if unlocked else (14,11,24)
        # Shadow glow
        if unlocked:
            for spread in (10,6,3):
                gs=pygame.Surface((NW+spread*2,NH+spread*2),pygame.SRCALPHA)
                a2=int(15+10*pulse)
                pygame.draw.rect(gs,(*c,a2),(0,0,NW+spread*2,NH+spread*2),
                                 border_radius=8+spread)
                surf.blit(gs,(cx-NW//2-spread,cy-NH//2-spread))
        _ang_panel(surf,cx-NW//2,cy-NH//2,NW,NH,bg,c,cut=9,bw=2)
        if unlocked:
            glo=pygame.Surface((NW,NH),pygame.SRCALPHA)
            _ang_panel(glo,0,0,NW,NH,(0,0,0,0),(*c,int(50+35*pulse)),cut=9,bw=4)
            surf.blit(glo,(cx-NW//2,cy-NH//2))
        # Icon (large, left side)
        ic=_make_icon(node["key"],38)
        if not unlocked: ic.set_alpha(70)
        surf.blit(ic,(cx-NW//2+7,cy-19))
        # Stage badge
        stg_col=(255,215,0) if node["stage"]==8 else \
                (255,110,30) if node["stage"]==7 else \
                (150,0,200) if node["stage"]==6 else \
                (0,200,255) if node["stage"]==5 else c
        sb=font_tiny.render(f"S{node['stage']}",True,stg_col if unlocked else (55,50,75))
        surf.blit(sb,(cx-NW//2+53,cy-NH//2+4))
        # Name
        star="★ " if unlocked else "○ "
        nm=font_small.render(star+node["name"],True,WHITE if unlocked else (70,65,90))
        surf.blit(nm,(cx-NW//2+53,cy-10))
        # Condition
        cond=_evo_cond(node,player)
        ct=font_tiny.render(cond,True,c if unlocked else (55,50,75))
        surf.blit(ct,(cx-NW//2+53,cy+12))
        node_pos[node["key"]]=(cx,cy+NH//2)
        return (cx,cy-NH//2)  # top center for incoming wires

    def _evo_cond(node,player):
        parts=[]
        for r in node["req"]:
            if "w" in r:
                lv=player.weapons[r["w"]]["level"]
                ok="✓" if lv>=r["lv"] else f"{lv}/{r['lv']}"
                parts.append(f"Lv{ok}")
            elif "acc" in r:
                ok="✓" if r["acc"] in player.accessories else "✗"
                aname=next((a["name"] for a in ACCESSORIES if a["key"]==r["acc"]),"?")
                parts.append(f"{aname[:6]}{ok}")
            elif "evo" in r:
                ok="✓" if r["evo"] in player.evolutions else "✗"
                en=next((n["name"] for n in EVOLUTION_NODES if n["key"]==r["evo"]),"?")
                parts.append(f"{en[:6]}{ok}")
        return "  ".join(parts)

    # ── Stage labels on left margin ───────────────────────────────────────────
    for label,cy in [("T1アクセサリ",SY["acc1"]),("T2アクセサリ",SY["acc2"]),
                     ("ステージIV",SY["s4"]),("ステージV",SY["s5"]),
                     ("ステージVI",SY["s6"]),("ステージVII",SY["s7"]),("ステージVIII",SY["s8"])]:
        sl=font_tiny.render(label,True,(70,65,90))
        surf.blit(sl,(6,cy-7))
        pygame.draw.line(surf,(40,38,55),(90,cy),(LANES[0]-NW//2-6,cy))

    # ── Accessories ───────────────────────────────────────────────────────────
    t1=[a for a in ACCESSORIES if a["tier"]==1]
    t2=[a for a in ACCESSORIES if a["tier"]==2]
    for i,acc in enumerate(t1): _acc_card(acc,LANES[i],SY["acc1"])
    for i,acc in enumerate(t2): _acc_card(acc,LANES[i],SY["acc2"])

    # Wire acc T1→T2
    for i in range(5):
        _wire(LANES[i],SY["acc1"]+AH//2,LANES[i],SY["acc2"]-AH//2,(60,56,80))

    # ── S4 nodes ──────────────────────────────────────────────────────────────
    for i,node in enumerate(EVOLUTION_NODES[:5]):
        cx=LANES[i]
        top=_evo_card(node,cx,SY["s4"])
        # Wire from T2 acc bottom
        _wire(cx,SY["acc2"]+AH//2,cx,top[1],(60,56,80))

    # ── S5 nodes ──────────────────────────────────────────────────────────────
    for i,node in enumerate(EVOLUTION_NODES[5:10]):
        cx=LANES[i]
        top=_evo_card(node,cx,SY["s5"])
        s4key=next(r["evo"] for r in node["req"] if "evo" in r)
        if s4key in node_pos:
            px2,py2=node_pos[s4key]
            col=node["color"] if s4key in player.evolutions else (60,56,80)
            _wire(px2,py2,cx,top[1],col)

    # ── S6 nodes ──────────────────────────────────────────────────────────────
    S6_CX=[W//2-420,W//2-140,W//2+140,W//2+420]
    for j,node in enumerate(EVOLUTION_NODES[10:14]):
        cx=S6_CX[j]
        top=_evo_card(node,cx,SY["s6"])
        for r in node["req"]:
            if "evo" in r and r["evo"] in node_pos:
                px2,py2=node_pos[r["evo"]]
                col=node["color"] if r["evo"] in player.evolutions else (60,56,80)
                _wire(px2,py2,cx,top[1],col)

    # ── S7 nodes ──────────────────────────────────────────────────────────────
    S7_CX=[W//2-215,W//2+215]
    for j,node in enumerate(EVOLUTION_NODES[14:16]):
        cx=S7_CX[j]
        top=_evo_card(node,cx,SY["s7"])
        for r in node["req"]:
            if "evo" in r and r["evo"] in node_pos:
                px2,py2=node_pos[r["evo"]]
                col=node["color"] if r["evo"] in player.evolutions else (60,56,80)
                _wire(px2,py2,cx,top[1],col,2)

    # ── S8 GENESIS ────────────────────────────────────────────────────────────
    node8=EVOLUTION_NODES[16]; cx8=W//2
    top8=_evo_card(node8,cx8,SY["s8"])
    for r in node8["req"]:
        if "evo" in r and r["evo"] in node_pos:
            px2,py2=node_pos[r["evo"]]
            col=(255,215,0) if r["evo"] in player.evolutions else (80,70,40)
            _wire(px2,py2,cx8,top8[1],col,2)

    # ── Hint ──────────────────────────────────────────────────────────────────
    hint=font_tiny.render("[ESC]/[T] ポーズへ戻る          ✓=解放済み   ✗=未解放",
                          True,(70,65,90))
    surf.blit(hint,(W//2-hint.get_width()//2,H-18))
    return {}


def _draw_vol_slider(surf, lbl, x, y, w, h, vol, col, hover_bar):
    """音量スライダーを描画して bar rect を返す。"""
    # ラベル
    ls = font_small.render(lbl, True, col)
    surf.blit(ls, (x, y + h//2 - ls.get_height()//2))
    lw = ls.get_width() + 12
    # ← ボタン
    lbtn = pygame.Rect(x+lw, y, h, h)
    pygame.draw.rect(surf, (30,24,50), lbtn, border_radius=4)
    pygame.draw.rect(surf, col, lbtn, 1, border_radius=4)
    arr = font_small.render("◀", True, col)
    surf.blit(arr, (lbtn.x + lbtn.w//2 - arr.get_width()//2,
                    lbtn.y + lbtn.h//2 - arr.get_height()//2))
    # バー本体
    bar_x = x + lw + h + 8; bar_w = w - lw - h*2 - 20
    bar = pygame.Rect(bar_x, y + h//2 - 6, bar_w, 12)
    pygame.draw.rect(surf, (20,16,32), bar, border_radius=6)
    fill_w = int(bar_w * vol)
    if fill_w > 0:
        fill_col = col if not hover_bar else tuple(min(255,c+40) for c in col)
        pygame.draw.rect(surf, fill_col, (bar_x, y+h//2-6, fill_w, 12), border_radius=6)
    # ハンドル
    hx = bar_x + fill_w
    pygame.draw.circle(surf, WHITE, (hx, y+h//2), 9)
    pygame.draw.circle(surf, col,   (hx, y+h//2), 7)
    # % 表示
    pct = font_small.render(f"{int(vol*100):3d}%", True, (160,155,190))
    surf.blit(pct, (bar_x + bar_w + 10, y + h//2 - pct.get_height()//2))
    # → ボタン
    rbtn = pygame.Rect(bar_x + bar_w + 10 + pct.get_width() + 8, y, h, h)
    pygame.draw.rect(surf, (30,24,50), rbtn, border_radius=4)
    pygame.draw.rect(surf, col, rbtn, 1, border_radius=4)
    arr2 = font_small.render("▶", True, col)
    surf.blit(arr2, (rbtn.x + rbtn.w//2 - arr2.get_width()//2,
                     rbtn.y + rbtn.h//2 - arr2.get_height()//2))
    return bar, lbtn, rbtn


def pause_screen(surf):
    """ポーズ画面を描画。rects に音量バー・ボタンも含める。"""
    t_ms = pygame.time.get_ticks()

    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    surf.blit(overlay, (0, 0))
    for row in range(0, H, 4):
        pygame.draw.line(surf, (0, 0, 0, 20), (0, row), (W, row))

    title = font_large.render("//  一時停止  //", True, NEON_P)
    pulse = abs(math.sin(t_ms / 600))
    title.set_alpha(int(180 + pulse * 75))
    tw = title.get_width() + 48
    _ang_panel(surf, W//2 - tw//2, 60, tw, title.get_height() + 20, UI_BG, NEON_P, cut=12, bw=2)
    _brackets(surf, W//2 - tw//2, 60, tw, title.get_height() + 20, NEON_P, size=14)
    surf.blit(title, (W//2 - title.get_width()//2, 68))

    ITEMS = [
        {"label":"再開",           "key":"resume",      "color":NEON_G,        "hint":"[ESC]"},
        {"label":"進化ツリー",     "key":"tree",        "color":(255,215,0),   "hint":"[T]"},
        {"label":"キャラ選択",     "key":"char_select", "color":NEON_P,        "hint":"[C]"},
        {"label":"ゲーム終了",     "key":"quit",        "color":NEON_R,        "hint":"[Q]"},
    ]
    iw, ih, gap = 420, 54, 12
    total_h = len(ITEMS)*ih + (len(ITEMS)-1)*gap
    iy0 = 155
    mx, my = pygame.mouse.get_pos()
    rects = {}
    for i, item in enumerate(ITEMS):
        rx = W//2 - iw//2; ry = iy0 + i*(ih+gap)
        rect = pygame.Rect(rx, ry, iw, ih)
        rects[item["key"]] = rect
        hover = rect.collidepoint(mx, my)
        c = item["color"]
        bg = (28,20,44) if not hover else (40,28,62)
        _ang_panel(surf, rx, ry, iw, ih, bg, c, cut=10, bw=2)
        if hover:
            gs = pygame.Surface((iw, ih), pygame.SRCALPHA)
            _ang_panel(gs, 0, 0, iw, ih, (0,0,0,0), (*c,55), cut=10, bw=4)
            surf.blit(gs, (rx, ry))
        _brackets(surf, rx, ry, iw, ih, c, size=10, bw=1)
        hint_s = font_small.render(item["hint"], True, c)
        surf.blit(hint_s, (rx+14, ry+ih//2 - hint_s.get_height()//2))
        lbl = font_med.render(item["label"], True, WHITE if not hover else c)
        surf.blit(lbl, (W//2 - lbl.get_width()//2, ry+ih//2 - lbl.get_height()//2))

    # ── Volume section ──────────────────────────
    vol_y = iy0 + len(ITEMS)*(ih+gap) + 18
    vol_w = 560; vol_x = W//2 - vol_w//2; vol_h = 38

    _ang_panel(surf, vol_x-14, vol_y-10, vol_w+28, vol_h*2+42, (12,9,22), NEON_Y, cut=8, bw=1)
    cap = font_small.render("音量", True, NEON_Y)
    surf.blit(cap, (W//2 - cap.get_width()//2, vol_y - 6))

    bgm_bar, bgm_lbtn, bgm_rbtn = _draw_vol_slider(
        surf, "BGM", vol_x, vol_y+16, vol_w, vol_h, _vol_bgm, NEON_Y,
        pygame.Rect(vol_x+60, vol_y+16+vol_h//2-6, vol_w-100, 12).collidepoint(mx,my))
    sfx_bar, sfx_lbtn, sfx_rbtn = _draw_vol_slider(
        surf, "SFX", vol_x, vol_y+16+vol_h+10, vol_w, vol_h, _vol_sfx, NEON_B,
        pygame.Rect(vol_x+60, vol_y+16+vol_h+10+vol_h//2-6, vol_w-100, 12).collidepoint(mx,my))

    rects["bgm_bar"]  = bgm_bar
    rects["sfx_bar"]  = sfx_bar
    rects["bgm_lbtn"] = bgm_lbtn; rects["bgm_rbtn"] = bgm_rbtn
    rects["sfx_lbtn"] = sfx_lbtn; rects["sfx_rbtn"] = sfx_rbtn

    hint2 = font_tiny.render("ESC:再開  T:ツリー  C:キャラ選択  Q:終了  |  スライダーをドラッグまたは◀▶クリックで音量調整",
                              True, (60,55,85))
    surf.blit(hint2, (W//2 - hint2.get_width()//2, H-38))

    return rects


def game_over_screen(surf, elapsed, kills, victory, score=0):
    surf.fill(DARK)
    # Background grid
    for gx in range(-1, W//80+2):
        pygame.draw.line(surf, UI_GRID, (gx*80, 0), (gx*80, H))
    for gy in range(-1, H//80+2):
        pygame.draw.line(surf, UI_GRID, (0, gy*80), (W, gy*80))

    t_ms = pygame.time.get_ticks()
    if victory:
        title_c = NEON_G;  title_t = "// ミッション完了 //"
        border_c = NEON_G
    else:
        title_c = NEON_R;  title_t = "//  ゲームオーバー  //"
        border_c = NEON_R

    title = font_large.render(title_t, True, title_c)
    pulse = abs(math.sin(t_ms/500))
    title.set_alpha(int(180 + pulse*75))

    # Main panel
    pw, ph = 520, 340
    _ang_panel(surf, W//2-pw//2, H//2-ph//2-20, pw, ph, UI_BG, border_c, cut=16, bw=2)
    _brackets(surf, W//2-pw//2, H//2-ph//2-20, pw, ph, border_c, size=18, bw=2)
    _scan_overlay(surf, (W//2-pw//2, H//2-ph//2-20, pw, ph), 25)

    surf.blit(title, (W//2-title.get_width()//2, H//2-ph//2))
    _divider(surf, W//2-pw//2+20, H//2-ph//2+title.get_height()+8,
             pw-40, border_c)

    m2, s2 = divmod(int(elapsed), 60)
    stats = [
        f"タイム    {m2:02d}:{s2:02d}",
        f"撃破数    {kills:04d}",
        f"スコア    {score:07d}",
    ]
    for i, line in enumerate(stats):
        c2 = GOLD if line.startswith("スコア") else (200,195,220)
        ls = font_med.render(line, True, c2)
        surf.blit(ls, (W//2-ls.get_width()//2, H//2-ph//2+title.get_height()+28+i*38))

    _divider(surf, W//2-pw//2+20, H//2+ph//2-56, pw-40, (40,35,60))
    hint = font_small.render("[ENTER] リスタート    [ESC] 終了", True, (80,75,110))
    surf.blit(hint, (W//2-hint.get_width()//2, H//2+ph//2-46))


def _scan_overlay(surf, rect, alpha=18):
    x, y, w, h = rect
    for row in range(0, h, 3):
        s = pygame.Surface((w, 1), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        surf.blit(s, (x, y+row))


def draw_bg(surf, ox, oy, terrain_map=None, underground=False, player_wx=0.0, player_wy=0.0):
    surf.fill((4,3,8) if underground else DARK)
    step = TILE_STEP
    RANGE = 13
    t = pygame.time.get_ticks() * 0.001
    cam_gx = int(ox / step); cam_gy = int(oy / step)
    tiles = []
    for gx in range(cam_gx - RANGE, cam_gx + RANGE + 1):
        for gy in range(cam_gy - RANGE, cam_gy + RANGE + 1):
            tiles.append((gx + gy, gx, gy))
    tiles.sort()
    for _, gx, gy in tiles:
        wx, wy = gx * step, gy * step
        p0 = iso_pos(wx,      wy,      0, ox, oy)
        p1 = iso_pos(wx+step, wy,      0, ox, oy)
        p2 = iso_pos(wx+step, wy+step, 0, ox, oy)
        p3 = iso_pos(wx,      wy+step, 0, ox, oy)
        pts = [p0, p1, p2, p3]
        if max(p[0] for p in pts)<0 or min(p[0] for p in pts)>W: continue
        if max(p[1] for p in pts)<0 or min(p[1] for p in pts)>H: continue

        if underground:
            tile_col=(18,12,22) if (gx+gy)%2==0 else (13,9,16)
            grid_col=(28,20,36); tt=-1
        elif terrain_map:
            tt=terrain_map.get(gx,gy)
            cols=TERRAIN_COLS[tt]; tile_col=cols[(gx+gy)%2]
            grid_col=tuple(min(c+8,255) for c in tile_col)
        else:
            tt=-1
            tile_col=(14,11,24) if (gx+gy)%2==0 else (10,8,18)
            grid_col=UI_GRID

        if tt==TERRAIN_MOUNTAIN:
            # ── 山描画 ─────────────────────────────────────────
            # このゾーンに隣接するvalleyゾーンがあれば平坦に描画（境界を自然に）
            if terrain_map:
                _zx,_zy=gx//ZONE_SIZE,gy//ZONE_SIZE
                _adj_val=any(terrain_map._zone_type(_zx+_dx,_zy+_dy)==TERRAIN_VALLEY
                             for _dx,_dy in ((-1,0),(1,0),(0,-1),(0,1)))
                if _adj_val:
                    pygame.draw.polygon(surf,tile_col,pts)
                    pygame.draw.polygon(surf,grid_col,pts,1)
                    continue
            H_WALL=24      # 基部壁の高さ
            H_PEAK=72      # 地面からピークまでの総高さ
            # 基部（ひし形の4辺壁）
            wall_top=[(p[0],p[1]-H_WALL) for p in pts]
            # 壁左面（pts[2]→pts[3]→wall_top[3]→wall_top[2]）
            face_l=[pts[2],pts[3],wall_top[3],wall_top[2]]
            # 壁右面（pts[1]→pts[2]→wall_top[2]→wall_top[1]）
            face_r=[pts[1],pts[2],wall_top[2],wall_top[1]]
            # ピーク座標（壁頂ひし形の中心から更に上へ）
            wt_cx=sum(p[0] for p in wall_top)//4
            wt_cy=sum(p[1] for p in wall_top)//4
            peak=(wt_cx, wt_cy-(H_PEAK-H_WALL))
            def _snow_pts(pk,wt,r=0.18):
                return [pk,
                        (int(pk[0]+(wt[0][0]-pk[0])*r),int(pk[1]+(wt[0][1]-pk[1])*r)),
                        (int(pk[0]+(wt[1][0]-pk[0])*r),int(pk[1]+(wt[1][1]-pk[1])*r)),
                        (int(pk[0]+(wt[2][0]-pk[0])*r),int(pk[1]+(wt[2][1]-pk[1])*r)),
                        (int(pk[0]+(wt[3][0]-pk[0])*r),int(pk[1]+(wt[3][1]-pk[1])*r))]

            # 手前になるときに透過するか判定
            p_sort=int(player_wx/step)+int(player_wy/step)
            m_sort=gx+gy
            player_sx,player_sy=iso_pos(player_wx,player_wy,0,ox,oy)
            bbox_left=min(p[0] for p in pts)-4
            bbox_right=max(p[0] for p in pts)+4
            bbox_top=peak[1]-4
            bbox_bot=max(p[1] for p in pts)+4
            occluding=(m_sort>p_sort and
                       bbox_left<=player_sx<=bbox_right and
                       bbox_top<=player_sy<=bbox_bot)

            if occluding:
                mw=bbox_right-bbox_left+1; mh=bbox_bot-bbox_top+1
                if mw>0 and mh>0:
                    ms=pygame.Surface((mw,mh),pygame.SRCALPHA)
                    def _mp(poly): return [(p[0]-bbox_left,p[1]-bbox_top) for p in poly]
                    def _mpt(pt):  return (pt[0]-bbox_left,pt[1]-bbox_top)
                    # 壁
                    pygame.draw.polygon(ms,(45,40,33,130),_mp(face_l))
                    pygame.draw.polygon(ms,(58,52,44,130),_mp(face_r))
                    # 基部頂面
                    pygame.draw.polygon(ms,(*tile_col,130),_mp(wall_top))
                    # 山体4面（各辺→ピーク）
                    _pk=_mpt(peak)
                    pygame.draw.polygon(ms,(88,80,68,120),[_mpt(wall_top[0]),_mpt(wall_top[1]),_pk])
                    pygame.draw.polygon(ms,(70,64,55,120),[_mpt(wall_top[1]),_mpt(wall_top[2]),_pk])
                    pygame.draw.polygon(ms,(55,50,42,120),[_mpt(wall_top[2]),_mpt(wall_top[3]),_pk])
                    pygame.draw.polygon(ms,(75,68,58,120),[_mpt(wall_top[3]),_mpt(wall_top[0]),_pk])
                    # 雪キャップ（ひし形ポリゴン）
                    _swt=[_mpt(p) for p in wall_top]
                    _spts=_snow_pts(_pk,_swt)
                    if len(_spts)>=3: pygame.draw.polygon(ms,(240,248,255,120),_spts)
                    # 輪郭
                    pygame.draw.line(ms,(100,95,88,100),_mpt(wall_top[2]),_pk,1)
                    pygame.draw.line(ms,(100,95,88,100),_mpt(wall_top[3]),_pk,1)
                    surf.blit(ms,(bbox_left,bbox_top))
            else:
                # 壁
                pygame.draw.polygon(surf,(45,40,33),face_l)
                pygame.draw.polygon(surf,(58,52,44),face_r)
                # 基部頂面
                pygame.draw.polygon(surf,tile_col,wall_top)
                # 山体4面
                pygame.draw.polygon(surf,(88,80,68),[wall_top[0],wall_top[1],peak])
                pygame.draw.polygon(surf,(70,64,55),[wall_top[1],wall_top[2],peak])
                pygame.draw.polygon(surf,(55,50,42),[wall_top[2],wall_top[3],peak])
                pygame.draw.polygon(surf,(75,68,58),[wall_top[3],wall_top[0],peak])
                # 岩肌テクスチャ線
                mid_r=((wall_top[2][0]+peak[0])//2,(wall_top[2][1]+peak[1])//2)
                pygame.draw.line(surf,(100,95,88),wall_top[3],peak,1)
                pygame.draw.line(surf,(100,95,88),wall_top[2],peak,1)
                pygame.draw.line(surf,(80,75,65),wall_top[3],mid_r,1)
                # 雪キャップ（ひし形ポリゴン）
                spts=_snow_pts(peak,wall_top)
                pygame.draw.polygon(surf,(240,248,255),spts)
                pygame.draw.polygon(surf,(200,225,248),spts,1)
                # 外縁
                pygame.draw.polygon(surf,(30,26,22),face_l,1)
                pygame.draw.polygon(surf,(30,26,22),face_r,1)
        else:
            # ── 3D box walls (left face + right face) ─────────────
            if underground:
                hw = 6
                wlc, wrc = (10, 7, 16), (14, 10, 22)
            else:
                hw = TERRAIN_WALL_H.get(tt, 0)
                wlc, wrc = TERRAIN_WALL_COLS.get(tt, ((40, 40, 40), (55, 55, 55)))
            if hw > 0:
                p1_b = (p1[0], p1[1] + hw)
                p2_b = (p2[0], p2[1] + hw)
                p3_b = (p3[0], p3[1] + hw)
                pygame.draw.polygon(surf, wlc, [p3, p2, p2_b, p3_b])
                pygame.draw.polygon(surf, wrc, [p1, p2, p2_b, p1_b])
                # エッジライン（面の境界を引き締める）
                edge_l = tuple(max(0, c - 12) for c in wlc)
                edge_r = tuple(max(0, c - 12) for c in wrc)
                pygame.draw.line(surf, edge_l, p3, p3_b, 1)
                pygame.draw.line(surf, edge_r, p1, p1_b, 1)
                pygame.draw.line(surf, edge_r, p2, p2_b, 1)
            # ── 上面（壁の上に乗る） ──────────────────────────────
            tile_img = None if underground else _TERRAIN_TILES.get(tt)
            if tile_img:
                # center the flat diamond tile on the diamond's screen center
                cx_t = (p0[0] + p2[0]) // 2
                cy_t = (p0[1] + p2[1]) // 2
                tw2, th2 = tile_img.get_size()
                surf.blit(tile_img, (cx_t - tw2 // 2, cy_t - th2 // 2))
            else:
                pygame.draw.polygon(surf, tile_col, pts)
                pygame.draw.polygon(surf, grid_col, pts, 1)
            if tt==TERRAIN_MAGMA:
                cx=sum(p[0] for p in pts)//4; cy=sum(p[1] for p in pts)//4
                # ── メインパルス光 ──
                lv=int(190+50*abs(math.sin(t*2.5+gx*0.7+gy*0.5)))
                pygame.draw.circle(surf,(lv,lv//5,0),(cx,cy),6)
                pygame.draw.line(surf,(lv,lv//4,0),pts[0],(cx,cy),1)
                pygame.draw.line(surf,(lv,lv//4,0),pts[1],(cx,cy),1)
                # ── 流れるクラック（横断する輝線） ──
                crack_x=int(math.sin(t*1.7+gx*0.5+gy*0.4)*4)
                lv2=int(220+30*math.sin(t*4.1+gx*0.6+gy*0.8))
                pygame.draw.line(surf,(lv2,lv2//4,0),
                                 (pts[3][0]+crack_x,pts[3][1]),
                                 (pts[1][0]+crack_x,pts[1][1]),1)
                # ── 泡立ちバブル（タイル固有位置・点滅） ──
                for bi in range(3):
                    bph=gx*1.31+gy*0.87+bi*2.09
                    br=int(1+2.5*abs(math.sin(t*3.3+bph)))
                    if br<1: continue
                    bx=cx+int((gx*17+gy*11+bi*7)%15)-7
                    by=cy+int((gx*13+gy*19+bi*5)%9)-4
                    bcol=(255,max(40,int(lv*0.35+bi*10)),0)
                    pygame.draw.circle(surf,bcol,(bx,by),br)
                    # バブルハイライト（中心明点）
                    if br>=2:
                        pygame.draw.circle(surf,(255,220,100),(bx-1,by-1),max(1,br//2))
            elif tt==TERRAIN_GRASS:
                cx=sum(p[0] for p in pts)//4; cy=sum(p[1] for p in pts)//4
                # ── 草葉（タイル固有の3〜4本、揺れアニメ） ──
                _gr=random.Random(gx*8191^gy*6271)
                sway=math.sin(t*2.3+gx*0.37+gy*0.53)
                for _ in range(3):
                    bx=cx+_gr.randint(-11,11)
                    by=cy+_gr.randint(-3,5)
                    h=_gr.randint(4,7)
                    lean=_gr.uniform(-0.25,0.25)
                    tx=int(bx+(sway*1.6+lean))
                    ty=by-h
                    gcol=(28+_gr.randint(0,20),80+_gr.randint(0,26),18+_gr.randint(0,16))
                    tcol=(min(gcol[0]+20,255),min(gcol[1]+22,255),min(gcol[2]+15,255))
                    pygame.draw.line(surf,gcol,(bx,by),(tx,ty))
                    pygame.draw.circle(surf,tcol,(tx,ty),1)
            elif tt==TERRAIN_ICE:
                cx=sum(p[0] for p in pts)//4; cy=sum(p[1] for p in pts)//4

                # ── フレネル縁取り（上2辺を明るく、下2辺を暗く） ──
                pygame.draw.line(surf,(210,245,255),pts[0],pts[1],2)
                pygame.draw.line(surf,(210,245,255),pts[0],pts[3],2)
                pygame.draw.line(surf,(70,120,170),pts[2],pts[1],1)
                pygame.draw.line(surf,(70,120,170),pts[2],pts[3],1)

                # ── 亀裂（決定論的・2本＋分岐） ──
                _ir=random.Random(gx*9173^gy*3571)
                for ci in range(2):
                    a1=_ir.uniform(0,math.pi*2)
                    a2=a1+_ir.uniform(0.5,1.3)
                    r1=_ir.randint(2,6); r2=_ir.randint(5,10)
                    x1=cx+int(math.cos(a1)*r1); y1=cy+int(math.sin(a1)*r1*0.5)
                    x2=cx+int(math.cos(a2)*r2); y2=cy+int(math.sin(a2)*r2*0.5)
                    pygame.draw.line(surf,(110,170,210),(x1,y1),(x2,y2),1)
                    if ci==0:
                        a3=a2+_ir.uniform(0.4,0.9)
                        r3=_ir.randint(2,5)
                        x3=cx+int(math.cos(a3)*r3); y3=cy+int(math.sin(a3)*r3*0.5)
                        pygame.draw.line(surf,(125,185,220),(x2,y2),(x3,y3),1)

                # ── 主スペキュラー（ゆっくり脈動する楕円グロー） ──
                shine=int(60+55*abs(math.sin(t*1.1+gx*0.22+gy*0.31)))
                hs=pygame.Surface((22,9),pygame.SRCALPHA)
                pygame.draw.ellipse(hs,(255,255,255,shine),(0,0,22,9))
                surf.blit(hs,(cx-16,cy-7))

                # ── 副スペキュラー（固定輝点、くっきり） ──
                pygame.draw.circle(surf,(200,240,255),(cx-5,cy-3),2)
                pygame.draw.circle(surf,(255,255,255),(cx-5,cy-3),1)

                # ── 微細キラキラ（sin位相をずらした瞬間輝点） ──
                for si,(sx_o,sy_o) in enumerate(((4,-1),(-3,2),(6,3))):
                    sp=abs(math.sin(t*3.5+gx*0.4+gy*0.6+si*1.8))
                    if sp>0.75:
                        sc=int((sp-0.75)/0.25*255)
                        pygame.draw.circle(surf,(sc,sc,255),(cx+sx_o,cy+sy_o),1)

    # ── Zone-level overlays: valley=unified pit, swamp=unified wetland ──
    if not underground and terrain_map:
        vis_zones={}
        for gx in range(cam_gx-RANGE,cam_gx+RANGE+1):
            for gy in range(cam_gy-RANGE,cam_gy+RANGE+1):
                zx,zy=gx//ZONE_SIZE,gy//ZONE_SIZE
                if (zx,zy) not in vis_zones:
                    vis_zones[(zx,zy)]=terrain_map._zone_type(zx,zy)
        for (zx,zy),tt in sorted(vis_zones.items(),key=lambda kv:kv[0][0]+kv[0][1]):
            if tt not in (TERRAIN_VALLEY,TERRAIN_SWAMP): continue
            ws=ZONE_SIZE*step
            wx0=zx*ws; wy0=zy*ws
            zp=[iso_pos(wx0,wy0,0,ox,oy),iso_pos(wx0+ws,wy0,0,ox,oy),
                iso_pos(wx0+ws,wy0+ws,0,ox,oy),iso_pos(wx0,wy0+ws,0,ox,oy)]
            if max(p[0] for p in zp)<0 or min(p[0] for p in zp)>W: continue
            if max(p[1] for p in zp)<0 or min(p[1] for p in zp)>H: continue
            zsc=((zp[0][0]+zp[2][0])//2,(zp[0][1]+zp[2][1])//2)
            def zring(r): return [(int(zsc[0]+(p[0]-zsc[0])*r),int(zsc[1]+(p[1]-zsc[1])*r)) for p in zp]

            if tt==TERRAIN_VALLEY:
                tv=pygame.time.get_ticks()*0.001

                # ── Helper: 縁から中心への補間座標 ──────────────
                def qpt(rv,et):
                    seg=int(et)%4; fr=et-int(et)
                    pa=zp[seg]; pb=zp[(seg+1)%4]
                    ex=pa[0]+(pb[0]-pa[0])*fr; ey=pa[1]+(pb[1]-pa[1])*fr
                    return (int(zsc[0]+(ex-zsc[0])*rv),int(zsc[1]+(ey-zsc[1])*rv))

                # ── 1. 同心グラデーション（外:水面 → 内:漆黒深淵）──
                # 外縁は水面のグレー/青みがかった色、内に向かって漆黒
                VLAYERS=[
                    (1.00,(78, 95,105)),  # 外縁：暗い水面
                    (0.93,(62, 76, 88)),
                    (0.86,(50, 62, 76)),  # 落ち込む縁
                    (0.80,(38, 50, 62)),
                    (0.73,(28, 38, 52)),
                    (0.66,(22, 30, 44)),  # 穴の内壁（上部）
                    (0.59,(18, 24, 38)),
                    (0.52,(15, 20, 32)),  # 内壁中部
                    (0.44,(11, 15, 25)),
                    (0.36,( 8, 11, 18)),  # 内壁下部
                    (0.27,( 5,  7, 12)),
                    (0.18,( 2,  3,  7)),
                    (0.10,( 0,  0,  0)),  # 底部の漆黒
                ]
                for vr,vc in VLAYERS:
                    pygame.draw.polygon(surf,vc,zring(vr))

                # ── 2. 外縁の白い縁取り（水が落ちる淵）────────────
                # 実際の glory hole は縁が白く泡立つ
                lip_s=pygame.Surface((W,H),pygame.SRCALPHA)
                for li,la in [(0,(200,210,215,80)),(1,(180,190,195,55)),(2,(240,248,252,40))]:
                    lip_outer=zring(0.98-li*0.03)
                    lip_inner=zring(0.91-li*0.03)
                    for si in range(4):
                        pts=[lip_outer[si],lip_outer[(si+1)%4],
                             lip_inner[(si+1)%4],lip_inner[si]]
                        pygame.draw.polygon(lip_s,la,pts)
                surf.blit(lip_s,(0,0))

                # ── 3. 内壁を流れ落ちる水のストリーク ────────────
                # 流水は縁(0.90)から中心(0.15)へ向かって流れ落ちる
                n_streams=40
                for si in range(n_streams):
                    et=si*4.0/n_streams
                    # アニメーション：各ストリークが時間で内側へ移動
                    phase=(tv*0.55+si*0.07)%1.0
                    r_head=0.88-phase*0.70          # 先端（内側へ進む）
                    r_tail=min(0.88,r_head+0.18)    # 末端（後に続く）
                    if r_head<0.12: continue
                    head=qpt(max(0.12,r_head),et)
                    tail=qpt(r_tail,et)
                    # 外側ほど明るい（光が当たる）
                    brightness=int(55+35*(r_tail-0.12)/0.76)
                    pygame.draw.line(surf,(brightness,brightness+4,brightness+8),tail,head,1)

                # ── 4. 縁の霧（水しぶき）──────────────────────────
                mist=random.Random(zx*997+zy*1777+int(tv*4))
                for _ in range(12):
                    rv_m=mist.uniform(0.84,0.97)
                    et_m=mist.uniform(0,4)
                    sp=qpt(rv_m,et_m)
                    a_m=mist.randint(25,70)
                    sw=mist.randint(5,12); sh2=max(1,sw//2)
                    ms=pygame.Surface((sw,sh2),pygame.SRCALPHA)
                    pygame.draw.ellipse(ms,(210,220,225,a_m),(0,0,sw,sh2))
                    surf.blit(ms,(sp[0]-sw//2,sp[1]-sh2//2))

                # ── 5. 同心リング（壁の奥行きライン）────────────────
                ring_s=pygame.Surface((W,H),pygame.SRCALPHA)
                for ri,ra2 in [(0.78,50),(0.65,40),(0.52,32),(0.40,24),(0.28,16)]:
                    phase=(tv*0.35+(1-ri)*1.8)%1.0
                    alpha=int(ra2*math.sin(phase*math.pi))
                    if alpha>2:
                        pygame.draw.polygon(ring_s,(50,65,75,alpha),zring(ri),1)
                surf.blit(ring_s,(0,0))

                # ── 6. 漆黒の底（中心の完全な闇）────────────────────
                pygame.draw.polygon(surf,(0,0,0),zring(0.10))
                # ごく微かに青光り（深淵の底）
                void_s=pygame.Surface((W,H),pygame.SRCALPHA)
                av=int(8+5*math.sin(tv*0.8))
                pygame.draw.polygon(void_s,(2,4,15,av),zring(0.08))
                surf.blit(void_s,(0,0))

            elif tt==TERRAIN_SWAMP:
                # Scattered stones on muddy brown ground
                rng_z=random.Random(zx*2311+zy*1777)
                for _ in range(30):
                    rt=rng_z.uniform(0.04,0.96); rs=rng_z.uniform(0.04,0.96)
                    rsx2,rsy2=iso_pos(wx0+rt*ws,wy0+rs*ws,0,ox,oy)
                    sw=rng_z.randint(5,14); sh=max(3,sw//2+rng_z.randint(-1,1))
                    sv=rng_z.randint(68,105)
                    sc=(sv,int(sv*0.82),int(sv*0.62))
                    pygame.draw.ellipse(surf,sc,(rsx2-sw//2,rsy2-sh//2,sw,sh))
                    # Highlight
                    hv=min(sv+30,255)
                    pygame.draw.ellipse(surf,(hv,int(hv*0.85),int(hv*0.68)),
                                        (rsx2-sw//2,rsy2-sh//2,max(2,sw//2),max(1,sh//2)))

    dot_col=(42,30,68) if not underground else (30,22,42)
    for gx in range(cam_gx - RANGE, cam_gx + RANGE + 1):
        for gy in range(cam_gy - RANGE, cam_gy + RANGE + 1):
            px, py = iso_pos(gx * step, gy * step, 0, ox, oy)
            if 0 <= px <= W and 0 <= py <= H:
                pygame.draw.circle(surf, dot_col, (px, py), 2)


# ─────────────────────────────────────────────
# SP Ultimate visual effect classes
# ─────────────────────────────────────────────

class MeteorEffect:
    """Fireball falling from sky → impact explosion. For Mage SP."""
    def __init__(self, x, y, particles, rings):
        self.x = x + random.uniform(-160, 160)
        self.y = y + random.uniform(-160, 160)
        self.z = random.uniform(420, 600)
        self.vz = -random.uniform(340, 480)
        self.life = self.max_life = 2.0
        self.alive = True
        self.exploded = False
        self._exp_life = 0.0
        self._particles = particles
        self._rings = rings
        self.trail = []

    def update(self, dt):
        if self.exploded:
            self._exp_life -= dt
            if self._exp_life <= 0: self.alive = False
            return
        self.z += self.vz * dt
        self.trail.append((self.x, self.y, max(0, self.z)))
        if len(self.trail) > 14: self.trail = self.trail[-14:]
        if self.z <= 0:
            self.z = 0
            self.exploded = True
            self._exp_life = 0.45
            for _ in range(50): self._particles.append(Particle(self.x, self.y, (255, 140, 20)))
            for _ in range(25): self._particles.append(Particle(self.x, self.y, (255, 230, 80)))
            self._rings.append(RingEffect(self.x, self.y, (255, 100, 0), 240, 10, 0.5))
            self._rings.append(RingEffect(self.x, self.y, (255, 220, 60), 120, 6, 0.35))
        self.life -= dt
        if self.life <= 0 and not self.exploded: self.alive = False

    def draw(self, surf, ox, oy):
        if self.exploded:
            alpha = int(200 * max(0, self._exp_life / 0.45))
            sx, sy = iso_pos(self.x, self.y, 2, ox, oy)
            s = pygame.Surface((100, 100), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 160, 0, alpha), (50, 50), 42)
            pygame.draw.circle(s, (255, 240, 120, alpha), (50, 50), 22)
            pygame.draw.circle(s, (255, 255, 200, min(255, alpha + 40)), (50, 50), 10)
            surf.blit(s, (sx - 50, sy - 50))
            return
        for i, (tx, ty, tz) in enumerate(self.trail):
            frac = (i + 1) / len(self.trail)
            alpha = int(220 * frac)
            r = max(2, int(12 * frac))
            tsx, tsy = iso_pos(tx, ty, tz, ox, oy)
            s = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
            col = (255, int(100 + 130 * frac), 0, alpha)
            pygame.draw.circle(s, col, (r+1, r+1), r)
            surf.blit(s, (tsx - r - 1, tsy - r - 1))
        sx, sy = iso_pos(self.x, self.y, self.z, ox, oy)
        s = pygame.Surface((36, 36), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 80, 0, 230), (18, 18), 16)
        pygame.draw.circle(s, (255, 240, 180, 255), (18, 18), 8)
        surf.blit(s, (sx - 18, sy - 18))


class WarriorSPVideoEffect:
    """戦士SP技の動画オーバーレイエフェクト。"""
    def __init__(self):
        self.alive = True
        self._t = 0.0
        self._duration = len(WARRIOR_SP_FRAMES) / max(WARRIOR_SP_FPS, 1.0) if WARRIOR_SP_FRAMES else 0.0
        if self._duration == 0.0:
            self.alive = False

    def update(self, dt):
        self._t += dt
        if self._t >= self._duration:
            self.alive = False

    def draw(self, surf, ox, oy):
        if not WARRIOR_SP_FRAMES:
            return
        fi = min(int(self._t * WARRIOR_SP_FPS), len(WARRIOR_SP_FRAMES) - 1)
        frame = WARRIOR_SP_FRAMES[fi]
        fade_out = min(1.0, (self._duration - self._t) / 0.4)
        fade_in  = min(1.0, self._t / 0.15)
        alpha = int(255 * fade_in * fade_out)
        if alpha <= 0:
            return
        scaled = pygame.transform.scale(frame, (W, H))
        scaled.set_alpha(alpha)
        surf.blit(scaled, (0, 0), special_flags=pygame.BLEND_ADD)


class MageMeteorVideoEffect:
    """隕石動画をフルスクリーンオーバーレイで再生（魔法使いSP用）。"""
    def __init__(self):
        self.alive = True
        self._t = 0.0
        self._duration = len(MAGE_METEOR_FRAMES) / max(MAGE_METEOR_FPS, 1.0) if MAGE_METEOR_FRAMES else 0.0
        if self._duration == 0.0:
            self.alive = False

    def update(self, dt):
        self._t += dt
        if self._t >= self._duration:
            self.alive = False

    def draw(self, surf, ox, oy):
        if not MAGE_METEOR_FRAMES:
            return
        fi = min(int(self._t * MAGE_METEOR_FPS), len(MAGE_METEOR_FRAMES) - 1)
        frame = MAGE_METEOR_FRAMES[fi]
        fade_in  = min(1.0, self._t / 0.12)
        fade_out = min(1.0, (self._duration - self._t) / 0.35)
        alpha = int(220 * fade_in * fade_out)
        if alpha <= 0:
            return
        scaled = pygame.transform.scale(frame, (W, H))
        scaled.set_alpha(alpha)
        surf.blit(scaled, (0, 0), special_flags=pygame.BLEND_ADD)


class MageImpactVideoEffect:
    """衝撃波動画を敵位置に表示（魔法使いSP着弾エフェクト）。"""
    DISP_W = 480
    DISP_H = 270

    def __init__(self, wx, wy, delay=0.0):
        self.wx = wx
        self.wy = wy
        self.alive = True
        self._t = -delay  # delayの間は待機
        self._duration = len(MAGE_IMPACT_FRAMES) / max(MAGE_IMPACT_FPS, 1.0) if MAGE_IMPACT_FRAMES else 0.0
        if self._duration == 0.0 and delay == 0.0:
            self.alive = False

    def update(self, dt):
        self._t += dt
        if self._t >= self._duration:
            self.alive = False

    def draw(self, surf, ox, oy):
        if not MAGE_IMPACT_FRAMES or self._t < 0:
            return
        fi = min(int(self._t * MAGE_IMPACT_FPS), len(MAGE_IMPACT_FRAMES) - 1)
        frame = MAGE_IMPACT_FRAMES[fi]
        fade_in  = min(1.0, self._t / 0.08)
        fade_out = min(1.0, (self._duration - self._t) / 0.25)
        alpha = int(235 * fade_in * fade_out)
        if alpha <= 0:
            return
        sx, sy = iso_pos(self.wx, self.wy, 0, ox, oy)
        scaled = pygame.transform.scale(frame, (self.DISP_W, self.DISP_H))
        scaled.set_alpha(alpha)
        surf.blit(scaled, (sx - self.DISP_W // 2, sy - self.DISP_H // 2),
                  special_flags=pygame.BLEND_ADD)


class RainZone:
    """光の雨武器エフェクト。動画を指定位置に表示しながら範囲ダメージを与える。"""
    TICK_INTERVAL = 0.18  # ダメージ判定間隔（秒）

    def __init__(self, wx, wy, radius, dmg_per_tick, duration=2.8):
        self.wx = wx
        self.wy = wy
        self.radius = radius
        self.dmg = dmg_per_tick
        self.duration = duration
        self._t = 0.0
        self._tick = 0.0
        self.alive = True
        # 表示サイズ = 半径に比例（最小256、最大600）
        self.disp_size = int(max(256, min(600, radius * 2.8)))

    def update(self, dt, enemies, floats):
        self._t += dt
        self._tick += dt
        if self._t >= self.duration:
            self.alive = False
            return
        if self._tick >= self.TICK_INTERVAL:
            self._tick -= self.TICK_INTERVAL
            for e in enemies:
                if dist((self.wx, self.wy), (e.x, e.y)) <= self.radius:
                    e.hp -= self.dmg
                    e.hit_flash = 0.08
                    floats.append(FloatText(e.x, e.y - 18, str(self.dmg), (200, 230, 255), 0.5))

    def draw(self, surf, ox, oy):
        sx, sy = iso_pos(self.wx, self.wy, 0, ox, oy)
        fade_in  = min(1.0, self._t / 0.15)
        fade_out = min(1.0, (self.duration - self._t) / 0.3)
        alpha_base = fade_in * fade_out
        pulse = 0.5 + 0.5 * math.sin(self._t * 5.0)

        # ── 地面楕円（等角投影：縦0.5倍）──
        ew = int(self.radius * 2.2)
        eh = int(ew * 0.45)
        ground_s = pygame.Surface((ew * 2, eh * 2), pygame.SRCALPHA)
        ga = int((30 + 20 * pulse) * alpha_base)
        pygame.draw.ellipse(ground_s, (160, 210, 255, ga),
                            (0, eh // 2, ew * 2, eh), 0)
        pygame.draw.ellipse(ground_s, (200, 230, 255, int(ga * 1.5)),
                            (0, eh // 2, ew * 2, eh), 2)
        surf.blit(ground_s, (sx - ew, sy - eh))

        # ── 動画を当たり判定全体に広げる──
        if RAIN_FRAMES:
            fi = int(self._t * RAIN_FPS) % max(1, len(RAIN_FRAMES))
            frame = RAIN_FRAMES[fi]
            dw = int(self.radius * 2.2)        # 当たり判定直径に合わせる
            dh = int(dw * 1.7)                 # 縦長にして上から降る感
            scaled = pygame.transform.scale(frame, (dw, dh))
            scaled.set_alpha(int(200 * alpha_base))
            # 地面が画像下 1/3 付近に来るよう配置
            surf.blit(scaled, (sx - dw // 2, sy - int(dh * 0.70)),
                      special_flags=pygame.BLEND_ADD)

        # ── 着弾パーティクル風スパーク（地面付近）──
        spark_s = pygame.Surface((ew * 2 + 20, eh * 3), pygame.SRCALPHA)
        rng2 = random.Random(int(self._t * 18) + id(self) % 9999)
        for _ in range(6):
            rx3 = rng2.randint(0, ew * 2)
            ry3 = rng2.randint(eh // 2, eh + eh // 2)
            sa = int(rng2.uniform(80, 160) * alpha_base)
            pygame.draw.circle(spark_s, (220, 240, 255, sa), (rx3, ry3), rng2.randint(1, 3))
        surf.blit(spark_s, (sx - ew - 10, sy - eh - 4), special_flags=pygame.BLEND_ADD)


class SwordSlash:
    """Golden arc slash for Knight SP."""
    def __init__(self, x, y, angle, length=140):
        self.x, self.y = x, y
        self.angle = angle
        self.length = length
        self.life = self.max_life = 0.55
        self.alive = True

    def update(self, dt):
        self.life -= dt
        if self.life <= 0: self.alive = False

    def draw(self, surf, ox, oy):
        alpha = int(255 * (self.life / self.max_life) ** 0.5)
        n = 16
        pts = []
        for i in range(n + 1):
            t = i / n
            a = self.angle - 0.7 + t * 1.4
            r = self.length * (0.4 + t * 0.6)
            wx = self.x + math.cos(a) * r
            wy = self.y + math.sin(a) * r
            pts.append(iso_pos(wx, wy, 20 + t * 60, ox, oy))
        if len(pts) >= 2:
            s = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.lines(s, (255, 240, 100, alpha), False, pts, 5)
            pygame.draw.lines(s, (255, 255, 220, alpha // 2), False, pts, 2)
            surf.blit(s, (0, 0))


class PoisonCloud:
    """Expanding toxic cloud for Rogue SP."""
    def __init__(self, x, y):
        self.x = x + random.uniform(-60, 60)
        self.y = y + random.uniform(-60, 60)
        self.life = self.max_life = random.uniform(1.0, 1.6)
        self.alive = True
        self.max_r = random.uniform(120, 200)
        self._phase = random.uniform(0, math.pi * 2)

    def update(self, dt):
        self.life -= dt
        if self.life <= 0: self.alive = False

    def draw(self, surf, ox, oy):
        prog = 1 - self.life / self.max_life
        r = max(4, int(self.max_r * (prog ** 0.5)))
        alpha = int(110 * (self.life / self.max_life))
        sx, sy = iso_pos(self.x, self.y, 10, ox, oy)
        rw = max(2, r * 2); rh = max(1, int(r * 0.65))
        t_ms = pygame.time.get_ticks() * 0.001
        for j in range(3):
            joff = int(math.sin(t_ms * 2 + self._phase + j) * 6)
            s = pygame.Surface((rw + 24, rh + 24), pygame.SRCALPHA)
            fade = max(0, alpha - j * 30)
            col = (40 + j*10, 200 - j*20, 20 + j*10, fade)
            pygame.draw.ellipse(s, col, (j*4, j*3 + joff, rw + 24 - j*8, rh + 24 - j*6), 0)
            surf.blit(s, (sx - rw//2 - 12, sy - rh//2 - 12))


class KnifeRainEffect:
    """大量のナイフが画面全体に降り注ぐ（ローグSP用）。"""
    KNIFE_DMG   = 180
    FALL_HEIGHT = 700   # 落下開始の画面上オフセット(px)

    def __init__(self, cx, cy, cam_ox, cam_oy, enemies, floats, particles, count=100):
        self._enemies   = enemies
        self._floats    = floats
        self._particles = particles
        self._hit_ids   = set()
        self.alive = True
        self._t    = 0.0
        self._knives = []
        # スクリーン全体にランダム配置（スクリーン座標→ワールド座標変換）
        for _ in range(count):
            sx_r = random.uniform(-W * 0.05, W * 1.05)
            sy_r = random.uniform(-H * 0.1,  H * 1.1)
            # iso_pos の逆変換 (wz=0)
            a_val = (sx_r - W / 2) / ISO_SX
            b_val = (sy_r - H / 2) / ISO_SY
            dx = (a_val + b_val) / 2
            dy = (b_val - a_val) / 2
            wx = cam_ox + dx
            wy = cam_oy + dy
            self._knives.append({
                "wx": wx, "wy": wy,
                "delay":    random.uniform(0, 0.7),
                "fall_dur": random.uniform(0.12, 0.22),
                "rot":      random.uniform(0, 360),
                "rot_spd":  random.uniform(-1080, 1080),
                "scale":    random.uniform(0.8, 1.5),
                "landed":   False,
            })
        self.duration = 0.7 + 0.22 + 0.5

    def update(self, dt):
        self._t += dt
        if self._t >= self.duration:
            self.alive = False
            return
        for k in self._knives:
            age = self._t - k["delay"]
            if age < 0:
                continue
            k["rot"] += k["rot_spd"] * dt
            if not k["landed"] and age >= k["fall_dur"]:
                k["landed"] = True
                # ダメージ判定（着地半径30内の敵）
                for e in self._enemies:
                    if id(e) not in self._hit_ids and dist((k["wx"], k["wy"]), (e.x, e.y)) < 35:
                        e.hp -= self.KNIFE_DMG
                        e.hit_flash = 0.12
                        self._floats.append(FloatText(e.x, e.y - 20,
                                                      str(self.KNIFE_DMG), (220, 255, 180), 0.6))
                        self._hit_ids.add(id(e))
                # 着地パーティクル
                for _ in range(6):
                    self._particles.append(Particle(k["wx"], k["wy"], (200, 230, 160)))

    def draw(self, surf, ox, oy):
        if KNIFE_SPRITE is None:
            return
        for k in self._knives:
            age = self._t - k["delay"]
            if age < 0:
                continue
            sx, sy_land = iso_pos(k["wx"], k["wy"], 0, ox, oy)
            if k["landed"]:
                # 着地後：地面に刺さった状態（徐々に消える）
                remain = self.duration - self._t
                alpha  = int(255 * min(1.0, remain / 0.5))
                if alpha <= 0:
                    continue
                size = int(_KNIFE_SIZE * k["scale"])
                rotated = pygame.transform.rotozoom(KNIFE_SPRITE, k["rot"], k["scale"])
                rotated.set_alpha(alpha)
                surf.blit(rotated, (sx - rotated.get_width() // 2,
                                    sy_land - rotated.get_height() // 2))
            else:
                # 落下中：上から降りてきてサイズが大きくなる
                prog  = age / k["fall_dur"]            # 0→1
                fall  = int(self.FALL_HEIGHT * (1 - prog * prog))  # 加速落下
                scale = 0.08 + prog * 0.92
                sy    = sy_land - fall

                # モーションブレア（残像4枚）
                for ti in range(4, 0, -1):
                    t_back = ti * 0.018
                    prog_b = max(0, age - t_back) / k["fall_dur"]
                    fall_b = int(self.FALL_HEIGHT * (1 - prog_b * prog_b))
                    scale_b = 0.08 + prog_b * 0.92
                    sy_b = sy_land - fall_b
                    trail = pygame.transform.rotozoom(
                        KNIFE_SPRITE, k["rot"] - k["rot_spd"] * t_back,
                        k["scale"] * scale_b * 0.85)
                    trail.set_alpha(int(50 * (1 - ti / 5) * prog))
                    surf.blit(trail, (sx - trail.get_width() // 2,
                                      sy_b - trail.get_height() // 2))

                rotated = pygame.transform.rotozoom(KNIFE_SPRITE, k["rot"],
                                                     k["scale"] * scale)
                rotated.set_alpha(255)
                surf.blit(rotated, (sx - rotated.get_width() // 2,
                                    sy  - rotated.get_height() // 2))

                # 着地直前フラッシュ（prog > 0.85）
                if prog > 0.85:
                    flash_a = int((prog - 0.85) / 0.15 * 180)
                    flash_s = pygame.Surface((60, 60), pygame.SRCALPHA)
                    pygame.draw.circle(flash_s, (255, 255, 200, flash_a), (30, 30), 28)
                    surf.blit(flash_s, (sx - 30, sy_land - 30),
                              special_flags=pygame.BLEND_ADD)


class GunSniperEffect:
    """全画面狙撃レティクル演出（ガンマンSP用）。"""
    SHOT_DMG = 9999

    def __init__(self, target_positions, floats, particles, rings):
        self._targets = [(wx, wy) for wx, wy in target_positions[:12]]
        self._floats    = floats
        self._particles = particles
        self._rings     = rings
        self.alive = True
        self._t = 0.0
        self._shots = []
        for i, pos in enumerate(self._targets):
            self._shots.append({"pos": pos, "time": 0.2 + i * 0.07, "fired": False})
        last_t = self._shots[-1]["time"] if self._shots else 0.2
        self.duration = last_t + 0.45
        if not RETICLE_FRAMES:
            self.duration = 0.01

    def update(self, dt):
        self._t += dt
        if self._t >= self.duration:
            self.alive = False
            return
        for shot in self._shots:
            if not shot["fired"] and self._t >= shot["time"]:
                shot["fired"] = True
                wx, wy = shot["pos"]
                # エフェクトだけ（実際の殺傷はactivate_sp_ultimateで既に処理済み）
                for _ in range(12):
                    p = Particle(wx, wy, (255, 220, 80))
                    ang = random.uniform(0, math.pi * 2)
                    spd = random.uniform(120, 320)
                    p.vx = math.cos(ang) * spd; p.vy = math.sin(ang) * spd - 60
                    p.life = p.max_life = random.uniform(0.15, 0.35)
                    self._particles.append(p)
                self._rings.append(RingEffect(wx, wy, (255, 200, 50), 55, 3, 0.3))
                self._floats.append(FloatText(wx, wy - 28, "狙撃！", (255, 200, 0), 1.0))

    def draw(self, surf, ox, oy):
        if not RETICLE_FRAMES:
            return
        fade_in  = min(1.0, self._t / 0.2)
        fade_out = min(1.0, (self.duration - self._t) / 0.3)
        base_a = fade_in * fade_out

        # 暗幕オーバーレイ
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(110 * base_a)))
        surf.blit(overlay, (0, 0))

        # レティクル動画（ループ再生）
        fi = int(self._t * RETICLE_FPS) % max(len(RETICLE_FRAMES), 1)
        fi = min(fi, len(RETICLE_FRAMES) - 1)
        frame = RETICLE_FRAMES[fi]
        scaled = pygame.transform.scale(frame, (W, H))
        scaled.set_alpha(int(210 * base_a))
        surf.blit(scaled, (0, 0))

        # 各ターゲットにサイトライン + ターゲットサークル
        for shot in self._shots:
            wx, wy = shot["pos"]
            sx, sy = iso_pos(wx, wy, 0, ox, oy)
            pre = self._t - (shot["time"] - 0.28)
            if pre < 0:
                continue
            if not shot["fired"]:
                prog = min(1.0, pre / 0.28)
                r = int(45 - prog * 28)    # 収縮する照準サークル
                a = int(210 * prog * base_a)
                tgt = pygame.Surface((r*2+8, r*2+8), pygame.SRCALPHA)
                pygame.draw.circle(tgt, (255, 40, 40, a), (r+4, r+4), r, 2)
                # 十字線
                cx2 = r + 4
                for dx2, dy2, ex2, ey2 in [
                    (cx2-r-2, cx2, cx2-r+8, cx2),
                    (cx2+r+2, cx2, cx2+r-8, cx2),
                    (cx2, cx2-r-2, cx2, cx2-r+8),
                    (cx2, cx2+r+2, cx2, cx2+r-8),
                ]:
                    pygame.draw.line(tgt, (255, 40, 40, a), (dx2, dy2), (ex2, ey2), 1)
                surf.blit(tgt, (sx - r - 4, sy - r - 4))
            else:
                # 着弾フラッシュ
                ft = self._t - shot["time"]
                if ft < 0.2:
                    fa = int(255 * (1 - ft / 0.2))
                    flash = pygame.Surface((100, 100), pygame.SRCALPHA)
                    pygame.draw.circle(flash, (255, 240, 150, fa), (50, 50),
                                       int(20 + 40 * (ft / 0.2)))
                    surf.blit(flash, (sx - 50, sy - 50), special_flags=pygame.BLEND_ADD)


class SkullFloat:
    """Rising death skull for Plague Dr SP."""
    def __init__(self, x, y):
        self.x = x + random.uniform(-180, 180)
        self.y = y + random.uniform(-180, 180)
        self.z = random.uniform(0, 30)
        self.vz = random.uniform(55, 110)
        self.life = self.max_life = random.uniform(0.9, 1.8)
        self.alive = True
        self._spin = random.uniform(-2.0, 2.0)
        self._angle = random.uniform(0, math.pi * 2)
        self._r = random.randint(10, 16)

    def update(self, dt):
        self.z += self.vz * dt
        self._angle += self._spin * dt
        self.life -= dt
        if self.life <= 0: self.alive = False

    def draw(self, surf, ox, oy):
        alpha = int(255 * (self.life / self.max_life) ** 0.6)
        sx, sy = iso_pos(self.x, self.y, self.z, ox, oy)
        r = self._r
        s = pygame.Surface((r * 3 + 4, r * 3 + 4), pygame.SRCALPHA)
        cx, cy = r + 2, r + 2
        pygame.draw.circle(s, (190, 0, 255, alpha), (cx, cy), r)
        pygame.draw.circle(s, (230, 180, 255, alpha // 2), (cx, cy - r//3), r // 2)
        pygame.draw.circle(s, (0, 0, 0, alpha), (cx - r//3, cy), r//4)
        pygame.draw.circle(s, (0, 0, 0, alpha), (cx + r//3, cy), r//4)
        surf.blit(s, (sx - cx, sy - cy))


class VoidSingularity:
    """Expanding void ring that collapses for Valley Wraith SP."""
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.life = self.max_life = 1.8
        self.alive = True

    def update(self, dt):
        self.life -= dt
        if self.life <= 0: self.alive = False

    def draw(self, surf, ox, oy):
        prog = 1 - self.life / self.max_life
        # expand 0→0.45, hold 0.45→0.6, collapse 0.6→1.0
        if prog < 0.45:
            r = int(500 * prog / 0.45)
        elif prog < 0.6:
            r = 500
        else:
            r = int(500 * (1 - (prog - 0.6) / 0.4))
        r = max(4, r)
        alpha = int(200 * (self.life / self.max_life) ** 0.5)
        sx, sy = iso_pos(self.x, self.y, 4, ox, oy)
        for i in range(5):
            ri = max(2, r - i * (r // 6))
            rw = max(2, ri * 2); rh = max(1, int(ri * 0.65))
            fade = max(0, alpha - i * 30)
            col = (max(0, 60 - i*10), 0, min(255, 180 + i*15), fade)
            s = pygame.Surface((rw + 4, rh + 4), pygame.SRCALPHA)
            pygame.draw.ellipse(s, col, (0, 0, rw + 4, rh + 4), max(1, 4 - i))
            surf.blit(s, (sx - rw//2 - 2, sy - rh//2 - 2))


# ─────────────────────────────────────────────
# SP Ultimate skills (per character)
# ─────────────────────────────────────────────
def activate_sp_ultimate(char_name, player, enemies, floats, rings, particles, bullets, screen, ox, oy, shake=None, flashes=None, sp_effects=None, bolts=None):
    """SP必殺技。雑魚は一撃、ボス/ゴジラにはダメージのみ。"""
    spr_bolts = []

    def _is_boss(e):
        return isinstance(e, (Boss, GodzillaEnemy))

    def _burst(x, y, color, n=80):
        for _ in range(n): particles.append(Particle(x, y, color))

    def _rings(x, y, color, n=5, base_r=200, width=8):
        for i in range(n):
            rings.append(RingEffect(x, y, color, base_r + i*220, width - i, 0.55 + i*0.12))

    def _enemy_fx(e, color, pcount=14, ring_w=5):
        e.hit_flash = 0.45
        rings.append(RingEffect(e.x, e.y, color, e.radius*4, ring_w, 0.45))
        rings.append(RingEffect(e.x, e.y, (255,255,255), e.radius*2, 3, 0.25))
        for _ in range(pcount): particles.append(Particle(e.x, e.y, color))

    if char_name == "ナイト":
        col = (255, 210, 60)
        if flashes is not None: flashes.append(ScreenFlash((180, 130, 10), 0.3, 120))
        _burst(player.x, player.y, col, 80)
        _rings(player.x, player.y, col, 4, 150, 8)
        # 動画オーバーレイ
        if sp_effects is not None:
            sp_effects.append(WarriorSPVideoEffect())
            # 剣閃エフェクトも重ねる
            for i in range(8):
                sp_effects.append(SwordSlash(player.x, player.y, i * math.pi / 4, 160))
        for e in enemies:
            if _is_boss(e): e.hp -= 800
            else:           e.hp  = 0
            _enemy_fx(e, col)
            if sp_effects is not None:
                a = math.atan2(e.y - player.y, e.x - player.x)
                sp_effects.append(SwordSlash(e.x, e.y, a, 110))
        if shake: shake.shake(35, 1.2)

    elif char_name == "魔法使い":
        col = (255, 90, 10)
        if flashes is not None: flashes.append(ScreenFlash((200, 60, 0), 0.55, 170))
        _burst(player.x, player.y, col, 80)
        _burst(player.x, player.y, (255, 200, 100), 30)
        _rings(player.x, player.y, col, 4, 150, 9)
        if sp_effects is not None:
            # 隕石動画をフルスクリーンで1回（イントロ0.2s分スキップして即着弾感）
            meteor_ov = MageMeteorVideoEffect()
            meteor_ov._t = 0.2
            sp_effects.append(meteor_ov)
            # 各敵位置に衝撃波動画（短い時差）+ 従来パーティクル隕石も重ねる
            targets = list(enemies) if enemies else []
            extras = [None] * max(0, 8 - len(targets))
            for i, e in enumerate(targets):
                sp_effects.append(MageImpactVideoEffect(e.x, e.y, delay=i * 0.07))
                sp_effects.append(MeteorEffect(e.x, e.y, particles, rings))
            for j in range(len(extras)):
                ox2 = random.uniform(-220, 220); oy2 = random.uniform(-220, 220)
                sp_effects.append(MageImpactVideoEffect(player.x + ox2, player.y + oy2,
                                                         delay=j * 0.09))
                sp_effects.append(MeteorEffect(player.x, player.y, particles, rings))
        for e in enemies:
            if _is_boss(e): e.hp -= 800
            else:           e.hp  = 0
            _enemy_fx(e, col)
        if shake: shake.shake(28, 1.0)

    elif char_name == "ローグ":
        col = (200, 230, 160)
        if flashes is not None: flashes.append(ScreenFlash((80, 100, 20), 0.4, 140))
        _burst(player.x, player.y, col, 60)
        _rings(player.x, player.y, col, 4, 150, 8)
        # ナイフの雨
        if sp_effects is not None:
            sp_effects.append(KnifeRainEffect(
                player.x, player.y, cam_ox=ox, cam_oy=oy,
                enemies=enemies, floats=floats, particles=particles,
                count=100))
        for e in enemies:
            if _is_boss(e): e.hp -= 700
            else:           e.hp  = 0
            _enemy_fx(e, col)
        if shake: shake.shake(28, 1.2)

    elif char_name == "疫病医師":
        col = (170, 0, 255)
        if flashes is not None: flashes.append(ScreenFlash((100, 0, 180), 0.6, 175))
        _burst(player.x, player.y, col, 90)
        _burst(player.x, player.y, (220, 100, 255), 35)
        _rings(player.x, player.y, col, 5, 150, 10)
        # 死のドクロを大量に浮かび上がらせる
        if sp_effects is not None:
            for _ in range(30):
                sp_effects.append(SkullFloat(player.x, player.y))
            for e in enemies:
                for _ in range(4):
                    sp_effects.append(SkullFloat(e.x, e.y))
        for e in enemies:
            if _is_boss(e): e.hp -= 900
            else:           e.hp  = 0
            _enemy_fx(e, col, ring_w=6)
        if shake: shake.shake(32, 1.2)

    elif char_name == "雷魔道士":
        col = (0, 230, 255)
        if flashes is not None: flashes.append(ScreenFlash((0, 160, 200), 0.5, 165))
        _burst(player.x, player.y, col, 90)
        _burst(player.x, player.y, (200, 240, 255), 40)
        _rings(player.x, player.y, col, 5, 150, 9)
        # 各敵に空から雷3連撃
        if bolts is not None:
            for e in enemies:
                for strike in range(3):
                    sx_off = random.uniform(-25, 25)
                    src = (e.x + sx_off, e.y - 350 - strike * 40)
                    pts = [(src[0], src[1]), (e.x, e.y)]
                    bolts.append(LightningBolt(pts, 0.18 + strike * 0.07))
            # プレイヤー周囲にも追加雷
            for _ in range(6):
                a = random.uniform(0, math.pi*2)
                r2 = random.uniform(80, 280)
                tx2 = player.x + math.cos(a) * r2
                ty2 = player.y + math.sin(a) * r2
                bolts.append(LightningBolt([(tx2, ty2 - 300), (tx2, ty2)], 0.2))
        for e in enemies:
            if _is_boss(e): e.hp -= 800
            else:           e.hp  = 0
            _enemy_fx(e, col)
        if shake: shake.shake(28, 1.0)

    elif char_name == "谷の亡霊":
        col = (160, 60, 255)
        if flashes is not None: flashes.append(ScreenFlash((80, 0, 180), 0.65, 180))
        _burst(player.x, player.y, col, 100)
        _burst(player.x, player.y, (220, 180, 255), 50)
        _rings(player.x, player.y, col, 6, 150, 10)
        # ボイドシンギュラリティ（ブラックホール展開）
        if sp_effects is not None:
            sp_effects.append(VoidSingularity(player.x, player.y))
            for e in enemies:
                sp_effects.append(VoidSingularity(e.x, e.y))
        for e in enemies:
            if _is_boss(e):
                e.hp -= 600
            else:
                e.hp = 0
                e.x = player.x + (e.x-player.x)*0.1
                e.y = player.y + (e.y-player.y)*0.1
            _enemy_fx(e, col, ring_w=6)
        if shake: shake.shake(35, 1.3)

    elif char_name == "ガンマン":
        col = (255, 210, 60)
        if flashes is not None: flashes.append(ScreenFlash((150, 120, 0), 0.4, 130))
        _burst(player.x, player.y, col, 70)
        _rings(player.x, player.y, col, 4, 140, 7)
        # 敵の位置を記録してからSPエフェクト生成（視覚演出用）
        target_positions = [(e.x, e.y) for e in enemies if e.alive]
        if sp_effects is not None and target_positions:
            sp_effects.append(GunSniperEffect(
                target_positions, floats, particles, rings))
        for e in enemies:
            if _is_boss(e): e.hp -= 800
            else:           e.hp  = 0
            _enemy_fx(e, col, ring_w=4)
        if shake: shake.shake(25, 1.0)

    else:
        col = (200, 200, 255)
        if flashes is not None: flashes.append(ScreenFlash((100, 80, 180), 0.55, 160))
        _burst(player.x, player.y, col, 80)
        _rings(player.x, player.y, col, 4, 150, 8)
        for e in enemies:
            if _is_boss(e): e.hp -= 700
            else:           e.hp  = 0
            _enemy_fx(e, col)
        if shake: shake.shake(25, 1.0)

    return spr_bolts


# ─────────────────────────────────────────────
# Main game loop
# ─────────────────────────────────────────────
def run_game(snd,sprites,char_data):
    player=Player(char_data,sprites)
    bullets=[]; enemies=[]; gems=[]; floats=[]; particles=[]
    flames=[]; bolts=[]; chests=[]; rings=[]
    capsules=[]; sp_orbs=[]; minions=[]; flashes=[]; sp_effects=[]; rain_zones=[]
    since_capsule = 0.0
    level=1; xp=0; xp_next=20
    elapsed=0.0; since_spawn=0.0; since_chest=40.0
    boss_timer=60.0; boss_level=1; boss_warn=0.0; kills=0; score=0
    boss_kills=0
    VICTORY_TIME=300  # 5 minutes
    hit_stop_t=0.0    # brief freeze on kill for impact feel
    godzilla_spawned=False; godzilla_warn=0.0
    _vol_drag = None   # "bgm" or "sfx" while dragging slider
    shake=ScreenShake()
    state="play"; levelup_opts=[]; levelup_rects=[]; victory=False
    pause_rects={}
    # Terrain
    terrain_map=TerrainMap()
    underground=False; surface_pos=(0.0,0.0); valley_ascend_immune=0.0
    ladders=[]; magma_spawn_cd=0.0
    cur_terrain=TERRAIN_GRASS; last_terrain=TERRAIN_GRASS; terrain_notify=0.0
    # 死霊使いは初期から1体召喚
    if player.necro_only:
        minions.append(Minion(player.x+60, player.y, player.max_hp, 0))
    snd.start_bgm()

    while True:
        raw_dt=min(clock.tick(60)/1000.0,0.05)
        if hit_stop_t>0:
            hit_stop_t=max(0,hit_stop_t-raw_dt)
            dt=raw_dt*0.05   # near-freeze during hit stop
        else:
            dt=raw_dt

        for event in pygame.event.get():
            if event.type==pygame.QUIT: snd.stop_bgm(); pygame.quit(); sys.exit()
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_m: snd.toggle_mute()
                if state=="gameover":
                    if event.key==pygame.K_RETURN: snd.stop_bgm(); return "char_select"
                    if event.key==pygame.K_ESCAPE: snd.stop_bgm(); return "quit"
                if state=="levelup":
                    for i,opt in enumerate(levelup_opts):
                        if event.key in (pygame.K_1+i,pygame.K_KP1+i):
                            new_evos=apply_upgrade(player,opt["key"]); state="play"
                            for en in new_evos:
                                floats.append(FloatText(player.x,player.y-90,
                                    f"EVOLVED: {en}",(255,215,0),3.0))
                if state=="play" and event.key in (pygame.K_SPACE, pygame.K_f):
                    if player.sp >= player.sp_max:
                        player.sp = 0.0; player.sp_ready = False
                        ox2=player.x; oy2=player.y
                        activate_sp_ultimate(player.char_name, player, enemies, floats, rings, particles, bullets, screen, ox2, oy2, shake=shake, flashes=flashes, sp_effects=sp_effects, bolts=bolts)
                        snd.play("levelup")
                if state=="play" and event.key==pygame.K_ESCAPE:
                    state="pause"; pygame.mixer.pause()
                elif state=="pause":
                    if event.key==pygame.K_ESCAPE:
                        state="play"; pygame.mixer.unpause()
                    elif event.key==pygame.K_t:
                        state="tree"
                    elif event.key==pygame.K_c:
                        snd.stop_bgm(); return "char_select"
                    elif event.key==pygame.K_q:
                        snd.stop_bgm(); return "quit"
                elif state=="tree":
                    if event.key in (pygame.K_ESCAPE,pygame.K_t):
                        state="pause"
            if event.type==pygame.MOUSEBUTTONDOWN:
                mx,my=pygame.mouse.get_pos()
                if state=="levelup":
                    for i,rect in enumerate(levelup_rects):
                        if rect.collidepoint(mx,my):
                            new_evos=apply_upgrade(player,levelup_opts[i]["key"]); state="play"
                            for en in new_evos:
                                floats.append(FloatText(player.x,player.y-90,
                                    f"EVOLVED: {en}",(255,215,0),3.0))
                if state=="pause":
                    _nr = pause_rects
                    if _nr.get("resume",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        state="play"; pygame.mixer.unpause()
                    elif _nr.get("tree",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        state="tree"
                    elif _nr.get("char_select",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.stop_bgm(); return "char_select"
                    elif _nr.get("quit",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.stop_bgm(); return "quit"
                    # ── Volume: ◀▶ ボタン (+/-5%) ──
                    elif _nr.get("bgm_lbtn",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.set_bgm_volume(_vol_bgm - 0.05)
                    elif _nr.get("bgm_rbtn",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.set_bgm_volume(_vol_bgm + 0.05)
                    elif _nr.get("sfx_lbtn",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.set_sfx_volume(_vol_sfx - 0.05)
                    elif _nr.get("sfx_rbtn",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.set_sfx_volume(_vol_sfx + 0.05)
                    # ── Volume: バークリックでジャンプ ──
                    elif _nr.get("bgm_bar",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        bar=_nr["bgm_bar"]
                        snd.set_bgm_volume((mx-bar.x)/bar.w); _vol_drag="bgm"
                    elif _nr.get("sfx_bar",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        bar=_nr["sfx_bar"]
                        snd.set_sfx_volume((mx-bar.x)/bar.w); _vol_drag="sfx"
                if state=="tree" and event.button==1:
                    state="pause"
            if event.type==pygame.MOUSEBUTTONUP:
                _vol_drag=None
            if event.type==pygame.MOUSEMOTION and _vol_drag and state=="pause":
                mx2,_=pygame.mouse.get_pos()
                bar_key=f"{_vol_drag}_bar"
                if pause_rects.get(bar_key):
                    bar=pause_rects[bar_key]
                    v=max(0.0,min(1.0,(mx2-bar.x)/bar.w))
                    if _vol_drag=="bgm": snd.set_bgm_volume(v)
                    else:               snd.set_sfx_volume(v)

        keys=pygame.key.get_pressed()

        if state=="play":
            elapsed+=dt; since_spawn+=dt; since_chest+=dt; boss_timer-=dt
            since_capsule += dt
            # カプセル出現処理（30秒ごとに20%で出現）
            if since_capsule >= 30.0:
                since_capsule = 0.0
                if random.random() < 0.2:
                    a = random.uniform(0, math.pi * 2)
                    rd = random.uniform(150, 350)
                    capsules.append(Capsule(player.x + math.cos(a) * rd, player.y + math.sin(a) * rd))
            if elapsed>=VICTORY_TIME:
                score = kills*100 + boss_kills*500 + level*200
                state="gameover"; victory=True

            if boss_timer<=0:
                enemies.append(spawn_boss(player.x,player.y,boss_level))
                snd.play("boss"); shake.shake(8,0.5); boss_level+=1; boss_timer=60.0
                floats.append(FloatText(player.x,player.y-80,"BOSS!",RED,2.0))

            # ── Godzilla appears at 90 seconds remaining ──
            remaining=VICTORY_TIME-elapsed
            if not godzilla_spawned and remaining<=90.0:
                if godzilla_warn<=0: godzilla_warn=5.0  # 5秒前警告
            if godzilla_warn>0:
                godzilla_warn-=dt
                if godzilla_warn<=0 and not godzilla_spawned:
                    godzilla_spawned=True
                    a2=random.uniform(0,math.pi*2)
                    gz=GodzillaEnemy(player.x+math.cos(a2)*900,
                                     player.y+math.sin(a2)*900)
                    enemies.append(gz)
                    snd.play("boss"); shake.shake(20,1.5)
                    floats.append(FloatText(player.x,player.y-120,
                        "☢ ？？？出現！ ☢",(0,240,120),4.0))

            if since_chest>=60:
                since_chest=0.0; a=random.uniform(0,math.pi*2); rd=random.uniform(150,350)
                chests.append(Chest(player.x+math.cos(a)*rd,player.y+math.sin(a)*rd))

            player.update(dt,keys,enemies,bullets,floats,flames,bolts,rings,particles,snd,shake,
                          None if underground else terrain_map, rain_zones=rain_zones)

            # ── Terrain effects ──
            cur_terrain=terrain_map.at(player.x,player.y) if not underground else TERRAIN_GRASS
            if cur_terrain!=last_terrain:
                last_terrain=cur_terrain; terrain_notify=2.5
            if terrain_notify>0: terrain_notify-=dt

            if cur_terrain==TERRAIN_MAGMA and not player.magma_immune:
                player.hp-=10*dt; player.hurt_flash=0.18
                if player.hurt_sound_cd<=0: snd.play("hurt"); player.hurt_sound_cd=0.5
                magma_spawn_cd-=dt
                if magma_spawn_cd<=0:
                    magma_spawn_cd=random.uniform(3.0,5.0)
                    a=random.uniform(0,math.pi*2); r=random.uniform(300,550)
                    enemies.append(spawn_magma_enemy(player.x+math.cos(a)*r,player.y+math.sin(a)*r,elapsed))
                    floats.append(FloatText(player.x,player.y-60,"Magma Enemy!",ORANGE,1.5))

            valley_ascend_immune=max(0.0,valley_ascend_immune-dt)
            if cur_terrain==TERRAIN_VALLEY and not underground and not player.valley_immune and valley_ascend_immune<=0.0:
                underground=True; surface_pos=(player.x,player.y)
                la=random.uniform(0,math.pi*2); lr=random.uniform(900,1400)
                ladders=[Ladder(player.x+math.cos(la)*lr,player.y+math.sin(la)*lr)]
                floats.append(FloatText(player.x,player.y-80,"FELL INTO THE ABYSS!",(150,80,255),3.0))
                snd.play("hurt"); shake.shake(10,0.5)

            for l in ladders:
                l.update(dt)
                if dist((player.x,player.y),(l.x,l.y))<player.radius+l.radius:
                    l.alive=False; underground=False
                    player.x,player.y=surface_pos
                    valley_ascend_immune=2.5
                    floats.append(FloatText(player.x,player.y-60,"CLIMBED BACK UP!",GREEN,2.0))
                    snd.play("chest")
            ladders=[l for l in ladders if l.alive]

            for b in bullets: b.update(dt)
            bullets=[b for b in bullets if b.alive]
            for f in flames: f.update(dt,enemies,floats)
            flames=[f for f in flames if f.alive]
            for rz in rain_zones: rz.update(dt,enemies,floats)
            rain_zones=[rz for rz in rain_zones if rz.alive]
            for b in bolts: b.update(dt)
            bolts=[b for b in bolts if b.alive]
            for r in rings: r.update(dt)
            rings=[r for r in rings if r.alive]
            for fl in flashes: fl.update(dt)
            flashes=[fl for fl in flashes if fl.alive]
            for se in sp_effects: se.update(dt)
            sp_effects=[se for se in sp_effects if se.alive]
            for cap in capsules:
                cap.update(dt)
                if dist((player.x,player.y),(cap.x,cap.y))<player.radius+cap.radius:
                    cap.alive=False
                    player.hp=min(player.max_hp,player.hp+cap.heal)
                    floats.append(FloatText(player.x,player.y-50,f"+{cap.heal} HP",(80,220,120),1.5))
                    rings.append(RingEffect(player.x,player.y,(80,220,120),45,3,0.3))
                    snd.play("chest")
            capsules=[cap for cap in capsules if cap.alive]

            since_spawn=maybe_spawn(player.x,player.y,elapsed,since_spawn,enemies,underground)
            for e in enemies:
                e.update(dt,player.x,player.y)
                if isinstance(e, GodzillaEnemy):
                    e.update_beam(dt,player.x,player.y,enemies,player,floats,rings,particles)

            # Plague doctor instant-kill aura (1 tile = 80 units)
            if player.weapons.get("plague",{}).get("level",0)>=1:
                for e in enemies:
                    if not isinstance(e,Boss) and dist((player.x,player.y),(e.x,e.y))<80+e.radius:
                        if e.hp>0:
                            e.hp=0
                            rings.append(RingEffect(e.x,e.y,(140,0,220),e.radius*2+8,2,0.22))

            # Bullet-enemy collision with impact effects
            for b in bullets:
                for e in enemies:
                    if id(e) in b.hit_ids: continue
                    if dist((b.x,b.y),(e.x,e.y))<b.radius+e.radius:
                        e.hp-=b.damage; e.hit_flash=0.1; b.hit_ids.add(id(e))
                        floats.append(FloatText(e.x,e.y-20,str(int(b.damage)),WHITE,0.5))
                        # Hit impact ring + sparks
                        rings.append(RingEffect(e.x,e.y,b.color,22,2,0.14))
                        for _ in range(3):
                            particles.append(Particle(e.x,e.y,b.color))
                        snd.play("hit")
                        b.pierce-=1
                        if b.pierce<=0: b.alive=False; break

            for e in enemies:
                if e.hp<=0:
                    e.alive=False; kills+=1; gems.append(Gem(e.x,e.y,e.xp))
                    snd.play("kill")
                    hit_stop_t=max(hit_stop_t,0.06)  # brief freeze for impact
                    for _ in range(14): particles.append(Particle(e.x,e.y,e.color))
                    # bright pop flash
                    for _ in range(6):
                        ang=random.uniform(0,math.pi*2); spd2=random.uniform(80,220)
                        p2=Particle(e.x,e.y,(255,255,200))
                        p2.vx=math.cos(ang)*spd2; p2.vy=math.sin(ang)*spd2-40
                        p2.life=p2.max_life=random.uniform(0.12,0.28); particles.append(p2)
                    rings.append(RingEffect(e.x,e.y,e.color,e.radius*2+10,3,0.3))
                    # SP orb drop: 12% normal, 100% boss
                    if isinstance(e,(Boss,GodzillaEnemy)) or random.random()<0.12:
                        sp_orbs.append(SPOrb(e.x+random.uniform(-20,20), e.y+random.uniform(-20,20)))
                    if isinstance(e,Boss):
                        boss_kills+=1
                        chests.append(Chest(e.x,e.y)); shake.shake(10,0.4)
                        floats.append(FloatText(e.x,e.y-60,"BOSS SLAIN!",GOLD,2.0))
                        for _ in range(20): particles.append(Particle(e.x,e.y,PURPLE))
                        rings.append(RingEffect(e.x,e.y,PURPLE,100,4,0.5))
            enemies=[e for e in enemies if e.alive]

            for g in gems:
                g.update(dt, player.x, player.y)
                if dist((player.x,player.y),(g.x,g.y))<player.PICKUP_RANGE:
                    g.alive=False; xp+=g.value
            gems=[g for g in gems if g.alive]

            for sp in sp_orbs:
                sp.update(dt, player.x, player.y)
                if dist((player.x,player.y),(sp.x,sp.y))<player.PICKUP_RANGE:
                    sp.alive=False
                    was_ready=player.sp>=player.sp_max
                    player.sp=min(player.sp_max, player.sp+6.0)
                    if player.sp>=player.sp_max and not was_ready:
                        player.sp_ready=True
                        floats.append(FloatText(player.x,player.y-80,"SP満タン！[SPACE]",(255,200,0),2.0))
                        rings.append(RingEffect(player.x,player.y,(255,200,0),60,3,0.4))
            sp_orbs=[sp for sp in sp_orbs if sp.alive]

            for c in chests:
                c.update(dt)
                if dist((player.x,player.y),(c.x,c.y))<player.radius+c.radius:
                    c.alive=False
                    if player.necro_only:
                        # 死霊使い専用チェスト: ランダムで死霊バフに変換
                        _necro_buffs = [
                            ("死霊HP回復",   lambda: [setattr(m,'hp',min(m.max_hp,m.hp+int(m.max_hp*0.5))) for m in minions]),
                            ("死霊HP強化",   lambda: [setattr(m,'max_hp',int(m.max_hp*1.3)) or setattr(m,'hp',int(m.hp*1.3)) for m in minions]),
                            ("死霊攻撃力UP", lambda: [setattr(m,'dmg',int(m.dmg*1.3)) for m in minions]),
                            ("死霊速度UP",   lambda: [setattr(m,'speed',int(m.speed*1.2)) for m in minions]),
                            ("HP回復",       lambda: setattr(player,'hp',min(player.max_hp,player.hp+60))),
                        ]
                        _bname, _bfn = random.choice(_necro_buffs)
                        _bfn()
                        floats.append(FloatText(player.x,player.y-50,_bname,(180,100,255),2.0))
                        snd.play("necro_summon")
                    else:
                        bonus=apply_chest_reward(player,c.reward["key"])
                        if bonus: xp+=bonus
                        floats.append(FloatText(player.x,player.y-50,c.reward["name"],GOLD,1.5))
                        snd.play("chest")
                    rings.append(RingEffect(player.x,player.y,(180,100,255) if player.necro_only else GOLD,50,3,0.3))
            chests=[c for c in chests if c.alive]

            while xp>=xp_next:
                xp-=xp_next; level+=1; xp_next=int(xp_next*1.25)
                levelup_opts=pick_upgrades(player); state="levelup"; snd.play("levelup")
                # 死霊使い: レベルに応じてミニオンを追加召喚
                if player.necro_only:
                    cap=minion_cap(level)
                    spawned=0
                    while len(minions)<cap:
                        a=random.uniform(0,math.pi*2)
                        mx=player.x+math.cos(a)*90; my=player.y+math.sin(a)*90
                        minions.append(Minion(mx,my,player.max_hp,player.necro_level))
                        floats.append(FloatText(mx,my-40,"死霊召喚！",(180,100,255),2.0))
                        spawned+=1
                    if spawned>0:
                        snd.play("necro_summon")
                    elif len(minions)>=MINION_MAX:
                        # 上限到達後: 全ミニオンをバフ
                        for m in minions:
                            m.dmg   = int(m.dmg   * 1.25)
                            m.speed = min(int(m.speed * 1.1), 320)
                            m.max_hp= int(m.max_hp * 1.2)
                            m.hp    = min(m.hp + int(m.max_hp*0.2), m.max_hp)
                        floats.append(FloatText(player.x,player.y-60,"死霊強化！",(255,180,50),2.5))
                        snd.play("necro_summon")

            for f in floats:    f.update(dt)
            for p in particles: p.update(dt)
            floats=[f for f in floats if f.alive]
            particles=[p for p in particles if p.alive]
            # ── ミニオン更新 ───────────────────────────────────────
            for i, m in enumerate(minions):
                m.update(dt, enemies, player, minions, i)
                # 敵からミニオンへのダメージ
                for e in enemies:
                    if not e.alive: continue
                    if math.hypot(e.x-m.x, e.y-m.y) < e.radius + 22:
                        m.hp -= e.damage * dt
                        m.hurt_flash = 0.15
                if m.hp <= 0:
                    m.alive = False
                    floats.append(FloatText(m.x, m.y-30, "死霊消滅", (180,80,220), 1.5))
            minions = [m for m in minions if m.alive]
            if not player.alive:
                score = kills*100 + boss_kills*500 + level*200
                state="gameover"; victory=False

        sx_off,sy_off=shake.update(dt)
        ox=player.x+sx_off; oy=player.y+sy_off
        draw_bg(screen,ox,oy,terrain_map,underground,player.x,player.y)
        # Ground-level effects (no depth sort needed)
        for f in flames:    f.draw(screen,ox,oy)
        for rz in rain_zones: rz.draw(screen,ox,oy)
        for r in rings:     r.draw(screen,ox,oy)
        # Godzilla beams (drawn over ground, under entities)
        for e in enemies:
            if isinstance(e, GodzillaEnemy) and e.active_beam:
                e.active_beam.draw(screen, ox, oy)
            # ロックオンマーカー（チャージ中にプレイヤー位置に照準）
            if isinstance(e, GodzillaEnemy) and e.beam_charging:
                t_ms = pygame.time.get_ticks()
                prog = 1.0 - e.beam_charge_t / 1.2  # 0→1
                pulse = abs(math.sin(t_ms * 0.015))
                lx, ly = iso_pos(e.beam_lock_px, e.beam_lock_py, 2, ox, oy)
                r_outer = int(40 + 20 * (1 - prog))
                r_inner = int(8 + 4 * pulse)
                alpha = int(180 + 60 * pulse)
                lock_s = pygame.Surface((r_outer*2+4, r_outer*2+4), pygame.SRCALPHA)
                cx2, cy2 = r_outer+2, r_outer+2
                pygame.draw.circle(lock_s, (255, 40, 40, alpha), (cx2, cy2), r_outer, 2)
                pygame.draw.circle(lock_s, (255, 40, 40, alpha), (cx2, cy2), r_inner)
                for ang in (0, math.pi/2, math.pi, 3*math.pi/2):
                    ex2 = int(cx2 + math.cos(ang)*(r_outer-6))
                    ey2 = int(cy2 + math.sin(ang)*(r_outer-6))
                    pygame.draw.line(lock_s, (255,40,40,alpha), (ex2,ey2),
                                     (int(cx2+math.cos(ang)*(r_outer+2)),
                                      int(cy2+math.sin(ang)*(r_outer+2))), 2)
                screen.blit(lock_s, (lx-r_outer-2, ly-r_outer-2))
        # Depth-sort all entities by (x+y) for correct isometric occlusion
        depth=[]
        for c in chests:    depth.append((c.x+c.y,'chest',c))
        for g in gems:      depth.append((g.x+g.y,'gem',g))
        for sp in sp_orbs:  depth.append((sp.x+sp.y,'sp_orb',sp))
        for cap in capsules: depth.append((cap.x+cap.y,'capsule',cap))
        for e in enemies:   depth.append((e.x+e.y,'enemy',e))
        for b in bullets:   depth.append((b.x+b.y,'bullet',b))
        for p in particles: depth.append((p.x+p.y,'part',p))
        for l in ladders:   depth.append((l.x+l.y,'ladder',l))
        for mn in minions:  depth.append((mn.x+mn.y,'minion',mn))
        depth.append((player.x+player.y,'player',player))
        depth.sort(key=lambda i:i[0])
        for _,etype,ent in depth:
            if etype=='enemy':  ent.draw(screen,ox,oy,sprites)
            elif etype=='minion': ent.draw(screen,ox,oy)
            else:               ent.draw(screen,ox,oy)
        for bl in bolts:    bl.draw(screen,ox,oy)
        for se in sp_effects: se.draw(screen,ox,oy)
        for ft in floats:   ft.draw(screen,ox,oy)
        draw_hud(screen,player,level,xp,xp_next,elapsed,kills,boss_warn,VICTORY_TIME)
        # Godzilla warning flash
        if godzilla_warn>0 and not godzilla_spawned:
            t_ms2=pygame.time.get_ticks()
            pulse3=abs(math.sin(t_ms2/120))
            gw=pygame.Surface((W,H),pygame.SRCALPHA)
            gw.fill((0,180,40,int(25*pulse3)))
            screen.blit(gw,(0,0))
            wt=font_large.render("☢ ？？？接近中 ☢",True,(0,240,80))
            wt.set_alpha(int(160+pulse3*95))
            screen.blit(wt,(W//2-wt.get_width()//2,H//2-wt.get_height()//2))
        # Terrain HUD
        if state=="play":
            if terrain_notify>0:
                lbl=TERRAIN_LABELS.get(cur_terrain,"")
                if lbl:
                    col=TERRAIN_HUD_COLS.get(cur_terrain,WHITE)
                    ts=font_small.render(f"[ {lbl} ]",True,col)
                    ts.set_alpha(min(255,int(255*terrain_notify/2.0)))
                    screen.blit(ts,(W//2-ts.get_width()//2,H-85))
            if underground:
                us=font_med.render("─ 地下 ─",True,(140,80,255))
                screen.blit(us,(W//2-us.get_width()//2,18))
                if ladders:
                    hs=font_small.render("緑のはしごで地上へ戻れ！",True,(80,220,80))
                    screen.blit(hs,(W//2-hs.get_width()//2,58))
                    # Arrow pointing to ladder
                    l=ladders[0]
                    lsx,lsy=iso_pos(l.x,l.y,8,ox,oy)
                    adx=lsx-W//2; ady=lsy-H//2
                    ad=math.hypot(adx,ady)
                    if ad>0:
                        ndx2=adx/ad; ndy2=ady/ad
                        margin=55
                        ts=[]
                        if ndx2>0:  ts.append((W-margin-W//2)/ndx2)
                        elif ndx2<0:ts.append((margin-W//2)/ndx2)
                        if ndy2>0:  ts.append((H-margin-H//2)/ndy2)
                        elif ndy2<0:ts.append((margin-H//2)/ndy2)
                        tval=min(ts)
                        ax=int(W//2+ndx2*tval); ay=int(H//2+ndy2*tval)
                        ang=math.atan2(ndy2,ndx2)
                        tip=(ax,ay)
                        al=(int(ax-math.cos(ang-2.5)*22),int(ay-math.sin(ang-2.5)*22))
                        ar=(int(ax-math.cos(ang+2.5)*22),int(ay-math.sin(ang+2.5)*22))
                        pygame.draw.polygon(screen,(60,240,80),[tip,al,ar])
                        pygame.draw.polygon(screen,(0,140,30),[tip,al,ar],2)
                        wd=int(math.hypot(l.x-player.x,l.y-player.y))
                        ds=font_tiny.render(f"{wd}m",True,(60,240,80))
                        screen.blit(ds,(ax-ds.get_width()//2,ay-ds.get_height()-6))
        if state=="levelup":  levelup_rects=levelup_screen(screen,levelup_opts)
        if state=="gameover": game_over_screen(screen,elapsed,kills,victory,score)
        if state=="pause":    pause_rects=pause_screen(screen)
        if state=="tree":     draw_evolution_tree(screen,player)

        # ── SP発動フラッシュ ─────────────────────────────────
        for fl in flashes: fl.draw(screen)

        # ── 画面端ダメージビネット + ヒットフラッシュ ────────────
        if player.hurt_flash>0:
            t=min(player.hurt_flash/0.22,1.0)
            # inner flash on fresh hit
            if player.hurt_flash>0.18:
                fl_a=int(90*(player.hurt_flash-0.18)/0.04)
                fl=pygame.Surface((W,H),pygame.SRCALPHA)
                fl.fill((255,20,20,fl_a))
                screen.blit(fl,(0,0))
            # vignette rim
            vign=pygame.Surface((W,H),pygame.SRCALPHA)
            edge=int(100*t)
            for i in range(0,edge,2):
                a2=int(180*(1-(i/edge))**1.8*t)
                pygame.draw.rect(vign,(200,0,0,a2),(i,i,W-i*2,H-i*2),2)
            screen.blit(vign,(0,0))

        pygame.display.flip()


# ─────────────────────────────────────────────
# Opening screen
# ─────────────────────────────────────────────

def opening_screen(surf):
    """オープニング画面。モザイクタイル背景 + 中央ENTER。"""
    clock2 = pygame.time.Clock()
    t0 = pygame.time.get_ticks()

    TILE = 56
    COLS = W // TILE + 2
    ROWS = H // TILE + 2

    rng = random.Random(7)
    PALETTES = [
        (8,  18, 42),
        (18, 8,  42),
        (8,  38, 22),
        (38, 8,  18),
        (8,  32, 40),
        (28, 8,  36),
    ]
    tile_pal   = [[rng.choice(PALETTES)         for _ in range(COLS)] for _ in range(ROWS)]
    tile_phase = [[rng.uniform(0, math.pi * 2)  for _ in range(COLS)] for _ in range(ROWS)]
    tile_speed = [[rng.uniform(0.35, 1.1)       for _ in range(COLS)] for _ in range(ROWS)]

    scroll_x = 0.0
    scroll_y = 0.0
    RIPPLE_INTERVAL = 2.8

    phase = "fadein"
    fade_alpha = 255
    fade_surf = pygame.Surface((W, H))
    fade_surf.fill((0, 0, 0))

    blink = 0.0
    scan_y = 0.0          # スキャンライン Y
    done  = False

    font_enter = pygame.font.Font(_YU_GOTH_B, 108)

    while not done:
        dt     = min(clock2.tick(60) / 1000.0, 0.05)
        t_ms   = pygame.time.get_ticks() - t0
        t_sec  = t_ms / 1000.0
        blink += dt
        scroll_x += 14 * dt
        scroll_y += 22 * dt
        scan_y = (scan_y + H * 0.18 * dt) % H

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
                if phase == "main":
                    phase = "fadeout"; fade_alpha = 0
            if event.type == pygame.MOUSEBUTTONDOWN:
                if phase == "main":
                    phase = "fadeout"; fade_alpha = 0

        if phase == "fadein":
            fade_alpha = max(0, fade_alpha - 300 * dt)
            if fade_alpha <= 0:
                phase = "main"
        elif phase == "fadeout":
            fade_alpha = min(255, fade_alpha + 360 * dt)
            if fade_alpha >= 255:
                done = True

        # ── モザイクタイル背景 ──
        surf.fill((2, 2, 8))
        ox = int(scroll_x) % TILE
        oy = int(scroll_y) % TILE

        rw = (t_sec % RIPPLE_INTERVAL) / RIPPLE_INTERVAL
        ripple_r = rw * math.sqrt(W * W + H * H) * 0.65

        for row in range(ROWS):
            for col in range(COLS):
                tx = col * TILE - ox
                ty = row * TILE - oy
                if tx + TILE < 0 or ty + TILE < 0 or tx >= W or ty >= H:
                    continue

                pulse = (math.sin(t_sec * tile_speed[row][col] + tile_phase[row][col]) + 1) * 0.5
                cx_t  = tx + TILE // 2
                cy_t  = ty + TILE // 2
                dist  = math.hypot(cx_t - W // 2, cy_t - H // 2)
                ring  = max(0.0, 1.0 - abs(dist - ripple_r) / 70.0) * (1.0 - rw) * 2.2

                bc = tile_pal[row][col]
                r  = min(255, int(bc[0] * (0.4 + pulse * 0.6) + ring * 50))
                g  = min(255, int(bc[1] * (0.4 + pulse * 0.6) + ring * 200))
                b  = min(255, int(bc[2] * (0.4 + pulse * 0.6) + ring * 90))
                pygame.draw.rect(surf, (r, g, b), (tx, ty, TILE - 2, TILE - 2))

        # ビネット（中央を少し明るく見せる）
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 150))
        surf.blit(ov, (0, 0))

        # スキャンライン
        sl = pygame.Surface((W, 3), pygame.SRCALPHA)
        sl.fill((0, 255, 120, 18))
        surf.blit(sl, (0, int(scan_y)))

        # ── 中央 ENTER ──
        if phase == "main":
            enter_s = font_enter.render("ENTER", True, (255, 255, 255))
            ew, eh  = enter_s.get_size()
            ex = W // 2 - ew // 2
            ey = H // 2 - eh // 2
            surf.blit(enter_s, (ex, ey))

            # ESC ヒント
            esc_s = font_tiny.render("[ ESC ] 終了", True, (55, 50, 75))
            surf.blit(esc_s, (W // 2 - esc_s.get_width() // 2, H - 48))

        # フェードオーバーレイ
        if fade_alpha > 0:
            fade_surf.set_alpha(int(fade_alpha))
            surf.blit(fade_surf, (0, 0))

        pygame.display.flip()


# ─────────────────────────────────────────────
# Tutorial screen
# ─────────────────────────────────────────────

TUTORIAL_PAGES = [
    {
        "title": "基本操作",
        "color": NEON_G,
        "sections": [
            ("移動",       "W A S D  または  矢印キー"),
            ("ポーズ",     "ESC キー"),
            ("ミュート",   "M キー"),
            ("必殺技",     "SPACE キー  （SP満タン時）"),
        ],
        "note": "武器は自動で発射される。動き続けて敵を避けよう！",
    },
    {
        "title": "レベルアップとスキル",
        "color": NEON_B,
        "sections": [
            ("ジェム",     "敵を倒すと緑のジェムを落とす"),
            ("XP",         "ジェムを拾うとXPを獲得"),
            ("レベルアップ","XPが満タンになると3択スキルが出現"),
            ("スキル選択", "[ 1 ] [ 2 ] [ 3 ] キーまたはクリック"),
        ],
        "note": "スキルを組み合わせて強い武器に進化させよう！",
    },
    {
        "title": "SPゲージと必殺技",
        "color": (255, 200, 0),
        "sections": [
            ("SPオーブ",   "敵を倒すとオレンジのオーブが出る"),
            ("ゲージ充填", "オーブを拾うとSPゲージが増える"),
            ("必殺技発動", "ゲージ満タン → SPACE で全体攻撃！"),
            ("キャラ固有", "各キャラで異なる派手なSP技が発動する"),
        ],
        "note": "SP技はほぼ全ての雑魚を一撃で倒す強力な技だ！",
    },
]

def tutorial_screen(surf):
    """チュートリアル画面。← → で前後ページ、ENTER/SPACE/ESC でスキップ。"""
    clock2 = pygame.time.Clock()
    page = 0
    total = len(TUTORIAL_PAGES)
    done = False
    fade_alpha = 255
    fade_in = True
    fade_surf = pygame.Surface((W, H)); fade_surf.fill((0, 0, 0))
    blink = 0.0

    while not done:
        dt = min(clock2.tick(60) / 1000.0, 0.05)
        blink += dt

        if fade_in:
            fade_alpha = max(0, fade_alpha - 400 * dt)
            if fade_alpha <= 0: fade_in = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    if page < total - 1:
                        page += 1; fade_in = True; fade_alpha = 180
                    else:
                        done = True
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    if page > 0:
                        page -= 1; fade_in = True; fade_alpha = 180
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    done = True
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx2, my2 = pygame.mouse.get_pos()
                if mx2 > W // 2:
                    if page < total - 1:
                        page += 1; fade_in = True; fade_alpha = 180
                    else:
                        done = True
                else:
                    if page > 0:
                        page -= 1; fade_in = True; fade_alpha = 180

        pg = TUTORIAL_PAGES[page]
        col = pg["color"]

        # ── 背景 ──
        surf.fill(UI_BG)
        step = 80
        for gx in range(0, W + step, step):
            pygame.draw.line(surf, UI_GRID, (gx, 0), (gx, H))
        for gy in range(0, H + step, step):
            pygame.draw.line(surf, UI_GRID, (0, gy), (W, gy))

        # ── ヘッダー ──
        hdr = font_large.render(f"チュートリアル  {page+1} / {total}", True, col)
        _ang_panel(surf, W//2 - hdr.get_width()//2 - 30, 24,
                   hdr.get_width() + 60, hdr.get_height() + 20, (8, 6, 16), col, cut=12, bw=2)
        _brackets(surf, W//2 - hdr.get_width()//2 - 30, 24,
                  hdr.get_width() + 60, hdr.get_height() + 20, col, size=14)
        surf.blit(hdr, (W//2 - hdr.get_width()//2, 34))

        # ── ページタイトル ──
        pt = font_med.render(f"── {pg['title']} ──", True, (220, 215, 240))
        surf.blit(pt, (W//2 - pt.get_width()//2, 115))

        # ── セクション一覧 ──
        card_w, card_h = 820, 68
        cx0 = W // 2 - card_w // 2
        for i, (label, desc) in enumerate(pg["sections"]):
            ry = 168 + i * (card_h + 14)
            _ang_panel(surf, cx0, ry, card_w, card_h, (14, 10, 24), col, cut=10, bw=2)
            _brackets(surf, cx0, ry, card_w, card_h, col, size=8, bw=1)

            lbl_s = font_med.render(label, True, col)
            surf.blit(lbl_s, (cx0 + 24, ry + card_h // 2 - lbl_s.get_height() // 2))

            _divider(surf, cx0 + 24 + lbl_s.get_width() + 16, ry + card_h // 2, 4, col)

            desc_s = font_small.render(desc, True, (200, 195, 225))
            surf.blit(desc_s, (cx0 + 24 + lbl_s.get_width() + 36,
                                ry + card_h // 2 - desc_s.get_height() // 2))

        # ── ノート ──
        note_y = 168 + len(pg["sections"]) * (card_h + 14) + 10
        note_bg = pygame.Surface((card_w, 46), pygame.SRCALPHA)
        note_bg.fill((*col, 22))
        surf.blit(note_bg, (cx0, note_y))
        pygame.draw.rect(surf, col, (cx0, note_y, card_w, 46), 1)
        note_icon = font_small.render("►", True, col)
        surf.blit(note_icon, (cx0 + 12, note_y + 14))
        note_s = font_small.render(pg["note"], True, (220, 215, 240))
        surf.blit(note_s, (cx0 + 36, note_y + 14))

        # ── ナビゲーション ──
        nav_y = H - 80
        if page > 0:
            left_s = font_small.render("◄  前へ  ( ← )", True, (130, 120, 160))
            surf.blit(left_s, (cx0, nav_y))
        if page < total - 1:
            right_s = font_small.render("次へ  ( → )  ►", True, col)
            surf.blit(right_s, (cx0 + card_w - right_s.get_width(), nav_y))
        else:
            if int(blink * 2) % 2 == 0:
                end_s = font_med.render("[ ENTER ] でゲーム開始 !", True, NEON_G)
                surf.blit(end_s, (W//2 - end_s.get_width()//2, nav_y - 6))

        # ページドット
        for i in range(total):
            dc = col if i == page else (50, 45, 70)
            pygame.draw.circle(surf, dc, (W//2 - (total-1)*16 + i*32, nav_y + 38), 6 if i == page else 4)

        skip_s = font_tiny.render("[ ESC / SPACE ]  スキップ", True, (55, 50, 75))
        surf.blit(skip_s, (W // 2 - skip_s.get_width() // 2, H - 28))

        # フェードオーバーレイ
        if fade_alpha > 0:
            fade_surf.set_alpha(int(fade_alpha))
            surf.blit(fade_surf, (0, 0))

        pygame.display.flip()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__=="__main__":
    screen.fill(DARK)
    screen.blit(font_med.render("アセット生成中...",True,GRAY),(W//2-90,H//2-20))
    pygame.display.flip()
    snd=SoundManager(); sprites=build_sprites()
    screen.fill(DARK)
    screen.blit(font_med.render("エフェクト読み込み中...",True,GRAY),(W//2-100,H//2-20))
    pygame.display.flip()
    _load_flame_video()
    _load_bullet_video()
    _load_gun_bullet_image()
    _load_warrior_sp_video()
    _load_mage_sp_videos()
    _load_rain_video()
    _load_knife_sprite()
    _load_reticle_video()
    opening_screen(screen)
    tutorial_screen(screen)
    while True:
        char_data=character_select(screen,sprites)
        result=run_game(snd,sprites,char_data)
        if result=="quit":
            break
        # "char_select" の場合はループしてキャラ選択画面に戻る
    pygame.quit(); sys.exit()
