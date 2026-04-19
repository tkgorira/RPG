import pygame
import math
import random
import sys
import os
import array as arr

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

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

TERRAIN_LABELS = {
    TERRAIN_GRASS:    "Grassland",
    TERRAIN_MAGMA:    "MAGMA  -HP / Enemy spawn!",
    TERRAIN_ICE:      "Ice  Slippery!",
    TERRAIN_SWAMP:    "Swamp  Slowed",
    TERRAIN_VALLEY:   "Valley  FALLING...",
    TERRAIN_MOUNTAIN: "Mountain  Blocked",
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

font_large = pygame.font.SysFont("consolas", 64, bold=True)
font_med   = pygame.font.SysFont("consolas", 32)
font_small = pygame.font.SysFont("consolas", 20)
font_tiny  = pygame.font.SysFont("consolas", 16)


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
    {"time":80,  "key":"virus_influenza", "name":"Influenza",      "hp":0.85,"spd":1.25,"dmg":0.9,"r":13},
    {"time":160, "key":"virus_hiv",       "name":"HIV",            "hp":1.3,"spd":0.8,"dmg":1.5,"r":13},
    {"time":240, "key":"virus_ebola",     "name":"Ebola",          "hp":1.5,"spd":1.1,"dmg":1.8,"r":14},
    {"time":320, "key":"virus_rabies",    "name":"Rabies",         "hp":1.1,"spd":1.5,"dmg":1.3,"r":12},
    {"time":400, "key":"virus_plague",    "name":"ペスト菌",        "hp":1.4,"spd":1.0,"dmg":1.6,"r":11},
    {"time":460, "key":"virus_measles",   "name":"Measles",        "hp":0.9,"spd":1.3,"dmg":1.0,"r":13},
    {"time":510, "key":"virus_dengue",    "name":"Dengue",         "hp":1.1,"spd":1.2,"dmg":1.2,"r":13},
    {"time":555, "key":"virus_smallpox",  "name":"Smallpox",       "hp":1.8,"spd":0.7,"dmg":2.0,"r":14},
    {"time":580, "key":"virus_phage",     "name":"Bacteriophage",  "hp":0.7,"spd":1.8,"dmg":0.8,"r":13},
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


def _draw_boss_phage(size=108):
    """ボス用バクテリオファージ — 大型・金脚・青キャプシド。"""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    # ── ボスオーラ（外周グロー）──
    for gr, ga in [(cx-2, 28), (cx-8, 18), (cx-14, 10)]:
        gs = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(gs, (0, 200, 255, ga), (cx, cx), gr)
        s.blit(gs, (0, 0))

    # ── カプシド（正二十面体ヘッド）──
    HR = 22          # 六角形の半径
    hcy = 4 + HR     # ヘッド中心 y
    HEAD_COL  = (80,  190, 230)   # メインカラー（水色）
    HEAD_FACE = (120, 220, 255)   # ハイライト面
    HEAD_EDGE = (40,  120, 170)   # エッジ色
    HEAD_DARK = (25,  80,  120)   # 暗い面

    # 外六角形の頂点
    hpts = [(int(cx + math.cos(i * math.pi / 3 - math.pi / 6) * HR),
             int(hcy + math.sin(i * math.pi / 3 - math.pi / 6) * HR)) for i in range(6)]

    # 面を塗り分け（上3面は明るく、下3面は暗く）
    for i in range(6):
        tri = [(cx, hcy), hpts[i], hpts[(i + 1) % 6]]
        col = HEAD_FACE if i in (0, 1, 5) else HEAD_DARK
        pygame.draw.polygon(s, col, tri)

    # 外枠・エッジライン
    pygame.draw.polygon(s, HEAD_COL, hpts)          # 全面ベース
    for i in range(6):
        pygame.draw.line(s, HEAD_EDGE, (cx, hcy), hpts[i], 1)
        pygame.draw.line(s, HEAD_EDGE, hpts[i], hpts[(i + 1) % 6], 2)
    pygame.draw.polygon(s, HEAD_EDGE, hpts, 2)

    # 中段帯ライン（イコサヘドラルの特徴）
    mid_l = ((hpts[3][0] + hpts[4][0]) // 2, (hpts[3][1] + hpts[4][1]) // 2)
    mid_r = ((hpts[0][0] + hpts[1][0]) // 2, (hpts[0][1] + hpts[1][1]) // 2)
    pygame.draw.line(s, HEAD_EDGE, mid_l, mid_r, 1)

    # 赤いアクセントドット（参考画像の赤点）
    pygame.draw.circle(s, (220, 30, 30),  (cx + 6, hcy - 6), 5)
    pygame.draw.circle(s, (255, 100, 80), (cx + 6, hcy - 6), 3)
    pygame.draw.circle(s, (255, 200, 180),(cx + 7, hcy - 7), 1)

    head_bot = hcy + HR        # ヘッド底辺 y ≈ 48

    # ── カラー（ネック）──
    COLLAR_COL = (60, 150, 200)
    pygame.draw.rect(s, COLLAR_COL,   (cx - 13, head_bot,     26, 7))
    pygame.draw.rect(s, HEAD_EDGE,    (cx - 13, head_bot,     26, 7), 1)
    # ボルト状のリベット
    for bx in (cx - 8, cx, cx + 8):
        pygame.draw.circle(s, HEAD_EDGE, (bx, head_bot + 3), 2)

    # ── テールシース（円筒状胴体）──
    TAIL_COL  = (50, 130, 185)
    TAIL_HIGH = (90, 180, 230)
    tail_top = head_bot + 7
    tail_h   = 26
    tw       = 10          # 半幅
    n_rings  = 9

    # 外壁
    pygame.draw.rect(s, TAIL_COL, (cx - tw, tail_top, tw * 2, tail_h))
    # ハイライト（左側面）
    pygame.draw.rect(s, TAIL_HIGH, (cx - tw, tail_top, 4, tail_h))
    # コイル状バンド
    for i in range(n_rings):
        ry = tail_top + i * tail_h // n_rings
        pygame.draw.ellipse(s, TAIL_HIGH, (cx - tw, ry, tw * 2, 4))
        pygame.draw.ellipse(s, HEAD_EDGE, (cx - tw, ry, tw * 2, 4), 1)
    # 外枠
    pygame.draw.rect(s, HEAD_EDGE, (cx - tw, tail_top, tw * 2, tail_h), 1)

    # ── ベースプレート（六角形）──
    bp_y  = tail_top + tail_h
    bpr   = 15
    bppts = [(int(cx + math.cos(i * math.pi / 3) * bpr),
              int(bp_y + 4 + math.sin(i * math.pi / 3) * 5)) for i in range(6)]
    pygame.draw.polygon(s, COLLAR_COL, bppts)
    pygame.draw.polygon(s, HEAD_EDGE,  bppts, 2)
    bp_cy = bp_y + 4

    # ── テールファイバー（6本の金色の脚）──
    GOLD     = (210, 160,  20)
    GOLD_HI  = (255, 210,  60)
    GOLD_DK  = (140,  95,   5)

    for i in range(6):
        a = i * math.pi / 3
        # 根本（ベースプレートのエッジ）
        rx = int(cx  + math.cos(a) * bpr * 0.75)
        ry_r = int(bp_cy + math.sin(a) * 4)

        # 第1セグメント：斜め外側下方へ
        spread = 28
        k1x = int(rx + math.cos(a) * spread)
        k1y = int(ry_r + 14)

        # 第2セグメント：さらに外側・下方へ
        k2x = int(k1x + math.cos(a) * 16)
        k2y = int(k1y + 14)

        # 描画（太め・金色）
        pygame.draw.line(s, GOLD_DK, (rx, ry_r), (k1x, k1y), 4)
        pygame.draw.line(s, GOLD,    (rx, ry_r), (k1x, k1y), 2)
        pygame.draw.line(s, GOLD_DK, (k1x, k1y), (k2x, k2y), 4)
        pygame.draw.line(s, GOLD,    (k1x, k1y), (k2x, k2y), 2)

        # ハイライトライン（金属感）
        pygame.draw.line(s, GOLD_HI, (rx, ry_r), (k1x, k1y), 1)

        # 関節部
        pygame.draw.circle(s, GOLD_DK, (k1x, k1y), 4)
        pygame.draw.circle(s, GOLD,    (k1x, k1y), 3)

        # 足先ピン
        pygame.draw.circle(s, GOLD_DK, (k2x, k2y), 3)
        pygame.draw.line(s, GOLD_DK, (k2x, k2y), (k2x, k2y + 5), 2)

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

    raw = {
        "knight":         _pc("knight.png",        64, _draw_knight),
        "mage":           _pc("mage.png",           64, _draw_mage),
        "rogue":          _pc("rogue.png",           64, _draw_rogue),
        "plague_doctor":  _pc("plague_doctor.png",  64, _draw_plague_doctor),
        "lightning_mage": _pc("lightning_mage.png", 64, _draw_lightning_mage),
        "valley_wraith":  _pc("valley_wraith.png",  64, _draw_valley_wraith),
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
        "boss":           _draw_boss_phage(108),
    }
    # 敵・ボス系スプライトに3Dシェーディングを事前適用
    _enemy_keys = {k for k in raw if k not in
                   ("knight","mage","rogue","plague_doctor","lightning_mage","valley_wraith")}
    for k in _enemy_keys:
        if raw[k] is not None:
            raw[k] = apply_3d_shading(raw[k])
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
        self.sfx["shoot"]    =pygame.mixer.Sound(buffer=_sine_buf(700,0.05,0.18))
        self.sfx["axe"]      =pygame.mixer.Sound(buffer=_sweep_buf(500,250,0.12,0.25))
        self.sfx["lightning"]=pygame.mixer.Sound(buffer=_sweep_buf(1400,600,0.08,0.28))
        self.sfx["flame"]    =pygame.mixer.Sound(buffer=_noise_buf(0.18,0.22))
        self.sfx["hit"]      =pygame.mixer.Sound(buffer=_sine_buf(380,0.07,0.2))
        self.sfx["kill"]     =pygame.mixer.Sound(buffer=_sweep_buf(500,150,0.14,0.25))
        self.sfx["levelup"]  =pygame.mixer.Sound(buffer=_chord_buf([523,659,784,1046],0.45,0.22))
        self.sfx["boss"]     =pygame.mixer.Sound(buffer=_chord_buf([60,80,55],0.7,0.3))
        self.sfx["chest"]    =pygame.mixer.Sound(buffer=_chord_buf([523,659,784],0.3,0.2))
        self.sfx["hurt"]     =pygame.mixer.Sound(buffer=_sweep_buf(300,150,0.09,0.35))
        self.sfx["cross"]    =pygame.mixer.Sound(buffer=_chord_buf([400,600],0.1,0.2))
        bgm=pygame.mixer.Sound(buffer=_bgm_buf()); bgm.set_volume(0.4); self.sfx["bgm"]=bgm
    def play(self,name):
        if not self.muted and name in self.sfx: self.sfx[name].play()
    def start_bgm(self):
        if not self.muted: self.sfx["bgm"].play(loops=-1)
    def stop_bgm(self): self.sfx["bgm"].stop()
    def toggle_mute(self):
        self.muted=not self.muted
        if self.muted: pygame.mixer.pause()
        else: pygame.mixer.unpause(); self.sfx["bgm"].play(loops=-1)


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
        self.trail=[]

    def update(self,dt):
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

        if self.style=="orb":          # Wand — glowing orb
            gs=r+5; gsurf=pygame.Surface((gs*2,gs*2),pygame.SRCALPHA)
            pygame.draw.circle(gsurf,(cr,cg,cb,55),(gs,gs),gs)
            surf.blit(gsurf,(sx-gs,sy-gs))
            pygame.draw.circle(surf,self.color,(sx,sy),r)
            pygame.draw.circle(surf,WHITE,(sx,sy),max(1,r//2))
            pygame.draw.circle(surf,(cr,cg,min(cb+40,255)),(sx,sy),r,1)

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
        super().__init__(x,y,dx,dy,speed,damage,radius=11,
                         color=ORANGE,lifetime=0.75,pierce=99,style="axe")
        self.angle=math.atan2(dy,dx); self.spin=11.0

    def update(self,dt):
        self.trail.append((self.x,self.y))
        if len(self.trail)>6: self.trail=self.trail[-6:]
        self.x+=self.dx*self.speed*dt; self.y+=self.dy*self.speed*dt
        self.angle+=self.spin*dt; self.life-=dt
        if self.life<=0: self.alive=False

    def draw(self,surf,ox,oy):
        # Orange trail
        n=len(self.trail)
        for i,(tx,ty) in enumerate(self.trail):
            ratio=(i+1)/max(n,1); tr=max(1,int(self.radius*ratio*0.55))
            tsx,tsy=iso_pos(tx,ty,26,ox,oy)
            ts=pygame.Surface((tr*2+2,tr*2+2),pygame.SRCALPHA)
            pygame.draw.circle(ts,(255,140,0,int(75*ratio)),(tr+1,tr+1),tr)
            surf.blit(ts,(tsx-tr-1,tsy-tr-1))
        sx,sy=iso_pos(self.x,self.y,26,ox,oy)
        r=self.radius
        # Axe blade: spinning diamond
        bl=r*1.65; bw=r*0.72
        pts=[(sx+math.cos(self.angle)*bl,       sy+math.sin(self.angle)*bl),
             (sx+math.cos(self.angle+1.8)*bw,   sy+math.sin(self.angle+1.8)*bw),
             (sx-math.cos(self.angle)*r*0.45,    sy-math.sin(self.angle)*r*0.45),
             (sx+math.cos(self.angle-1.8)*bw,   sy+math.sin(self.angle-1.8)*bw)]
        pts=[(int(x),int(y)) for x,y in pts]
        pygame.draw.polygon(surf,ORANGE,pts)
        pygame.draw.polygon(surf,(255,200,80),pts,2)
        # Blade tip shine
        tip=(int(sx+math.cos(self.angle)*bl),int(sy+math.sin(self.angle)*bl))
        pygame.draw.circle(surf,(255,240,160),tip,3)
        # Spin glow
        gs_r=r+3; gsurf=pygame.Surface((gs_r*2,gs_r*2),pygame.SRCALPHA)
        pygame.draw.circle(gsurf,(255,140,0,40),(gs_r,gs_r),gs_r)
        surf.blit(gsurf,(sx-gs_r,sy-gs_r))


# ─────────────────────────────────────────────
# FlameZone / Lightning (enhanced)
# ─────────────────────────────────────────────
class FlameZone:
    def __init__(self,x,y,radius,damage,lifetime):
        self.x,self.y=x,y; self.radius=radius; self.damage=damage
        self.life=self.max_life=lifetime; self.hit_ids=set()
        self.tick=0.3; self.timer=0.0; self.alive=True
    def update(self,dt,enemies,floats):
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
        alpha=int(180*self.life/self.max_life)
        r=self.radius; sx,sy=iso_pos(self.x,self.y,2,ox,oy)
        rw=max(2,int(r*2.0)); rh=max(1,int(r*0.7))
        s=pygame.Surface((rw,rh),pygame.SRCALPHA)
        pygame.draw.ellipse(s,(255,100,0,alpha),(0,0,rw,rh))
        pygame.draw.ellipse(s,(255,200,0,alpha//2),(rw//4,rh//4,rw//2,rh//2))
        surf.blit(s,(sx-rw//2,sy-rh//2))
        # Flickering inner sparks
        for _ in range(3):
            a=random.uniform(0,math.pi*2); rd=random.uniform(0,r*0.7)
            fx=int(sx+math.cos(a)*rd*1.3); fy=int(sy+math.sin(a)*rd*0.45)
            fs=pygame.Surface((6,6),pygame.SRCALPHA)
            pygame.draw.circle(fs,(255,220,50,alpha//2+60),(3,3),2)
            surf.blit(fs,(fx-3,fy-3))


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
    {"name":"HP Restore","desc":"+60 HP",           "key":"hp"},
    {"name":"Wand Lv+",  "desc":"Magic bolt enhanced","key":"wand"},
    {"name":"Axe",       "desc":"Axe enhanced",       "key":"axe"},
    {"name":"Lightning", "desc":"Lightning enhanced", "key":"lightning"},
    {"name":"Flame",     "desc":"Flame enhanced",     "key":"flame"},
    {"name":"XP Burst",  "desc":"+50 XP",             "key":"xp"},
]

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
        lbl=font_small.render("▲ ASCEND",True,lc)
        surf.blit(lbl,(sx-lbl.get_width()//2,top_y-22+int(bv)))

class FloatText:
    def __init__(self,x,y,text,color,life=1.0):
        self.x,self.y=x,y; self.text=text; self.color=color
        self.life=self.max_life=life; self.alive=True
    def update(self,dt):
        self.y-=40*dt; self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        alpha=int(255*self.life/self.max_life)
        sx,sy=iso_pos(self.x,self.y,50,ox,oy)
        s=font_small.render(self.text,True,self.color); s.set_alpha(alpha)
        surf.blit(s,(sx-s.get_width()//2,sy))


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
    def draw(self,surf,ox,oy,sprites):
        hover=math.sin(pygame.time.get_ticks()*0.002+self._hphase)*6
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,100)
        draw_shadow(surf,self.x,self.y+self.radius*0.35,ox,oy,int(self.radius*0.6),50)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        if self.telegraph>0:
            pulse=abs(math.sin(self.telegraph*20))*22; r=36+int(pulse)
            rw=max(2,int(r*2.0)); rh=max(1,int(r*0.7))
            s=pygame.Surface((rw,rh),pygame.SRCALPHA)
            pygame.draw.ellipse(s,(255,50,50,115),(0,0,rw,rh))
            surf.blit(s,(gsx-rw//2,gsy-rh//2))
        spr=sprites.get("boss")
        if spr:
            blit_dy=gsy-spr.get_height()-int(hover); blit_dx=gsx-spr.get_width()//2
            ol=get_enemy_outline("boss",spr)
            for odx,ody in ((-3,0),(3,0),(0,-3),(0,3)):
                surf.blit(ol,(blit_dx+odx,blit_dy+ody))
            if self.hit_flash>0:
                ws=spr.copy(); ws.fill((255,255,255,160),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws,(blit_dx,blit_dy))
            else:
                surf.blit(spr,(blit_dx,blit_dy))
            bw=100; ratio=max(0,self.hp/self.max_hp)
            dy=blit_dy
            pygame.draw.rect(surf,GRAY,(gsx-50,dy-14,bw,8))
            pygame.draw.rect(surf,RED,(gsx-50,dy-14,int(bw*ratio),8))
            lbl=font_small.render(self.name,True,YELLOW)
            surf.blit(lbl,(gsx-lbl.get_width()//2,dy-28))
        else:
            sy2=int(gsy-self.radius-hover)
            pygame.draw.circle(surf,PURPLE,(gsx,sy2),self.radius)
            bw=100; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-50,sy2-self.radius-14,bw,8))
            pygame.draw.rect(surf,RED,(gsx-50,sy2-self.radius-14,int(bw*ratio),8))
            lbl=font_small.render(self.name,True,YELLOW)
            surf.blit(lbl,(gsx-lbl.get_width()//2,sy2-self.radius-28))


# ─────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────
CHARACTERS=[
    {"name":"Knight","desc":["High HP & defense","Starts with Axe"],
     "color":BLUE,  "hp":200,"speed":175,"sprite":"knight",
     "weapons":{"wand":0,"axe":1,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0},"wand_cd":0.8},
    {"name":"Mage",  "desc":["Fast magic attack","Starts with Wand Lv2"],
     "color":PURPLE,"hp":90, "speed":230,"sprite":"mage",
     "weapons":{"wand":2,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0},"wand_cd":0.38},
    {"name":"Rogue", "desc":["Very fast & agile","Starts with Holy Cross"],
     "color":ORANGE,"hp":110,"speed":290,"sprite":"rogue",
     "weapons":{"wand":0,"axe":0,"cross":1,"garlic":0,"lightning":0,"flame":0,"plague":0},"wand_cd":0.8},
    {"name":"Plague Dr","desc":["Instant-kill aura","Enemies within 1 tile vanish"],
     "color":(160,0,220),"hp":150,"speed":210,"sprite":"plague_doctor",
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":1,"scatter":0},"wand_cd":0.8,
     "magma_immune":True},
    {"name":"Lightning Mage","desc":["Scatter lightning strike","Hits random targets at once"],
     "color":(0,200,255),"hp":80,"speed":240,"sprite":"lightning_mage",
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0,"scatter":2},"wand_cd":0.8},
    {"name":"Valley Wraith","desc":["Ignores valley terrain","Speed boost in the void"],
     "color":(160,0,255),"hp":130,"speed":260,"sprite":"valley_wraith",
     "weapons":{"wand":1,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":0,"scatter":0},"wand_cd":0.6,
     "valley_immune":True},
]


# ─────────────────────────────────────────────
# Player
# ─────────────────────────────────────────────
class Player:
    PICKUP_RANGE=120
    def __init__(self,char_data,sprites):
        self.x=self.y=0.0; self.max_hp=char_data["hp"]; self.hp=self.max_hp
        self.speed=char_data["speed"]; self.char_color=char_data["color"]
        self.radius=16; self.alive=True; self.hurt_sound_cd=0.0
        self.bob=0.0; self.ice_dir=(0.0,0.0); self.hurt_flash=0.0
        self.sprite=sprites.get(char_data["sprite"])
        self.weapons={
            "wand":     {"level":char_data["weapons"]["wand"],     "timer":0.0,"cooldown":char_data["wand_cd"]},
            "axe":      {"level":char_data["weapons"]["axe"],      "timer":0.0,"cooldown":1.5},
            "cross":    {"level":char_data["weapons"]["cross"],    "timer":0.0,"cooldown":3.0},
            "garlic":   {"level":char_data["weapons"]["garlic"]},
            "lightning":{"level":char_data["weapons"]["lightning"],"timer":0.0,"cooldown":2.0},
            "flame":    {"level":char_data["weapons"]["flame"],    "timer":0.0,"cooldown":4.0},
            "plague":   {"level":char_data["weapons"].get("plague",0)},
            "scatter":  {"level":char_data["weapons"].get("scatter",0),"timer":0.0,"cooldown":2.2},
        }
        self.aura=None
        self.valley_immune=char_data.get("valley_immune",False)
        self.magma_immune=char_data.get("magma_immune",False)
        self.accessories=set()
        self.evolutions=set()

    def update(self,dt,keys,enemies,bullets,floats,flames,bolts,rings,particles,snd,shake,terrain_map=None):
        dx=dy=0
        if keys[pygame.K_w] or keys[pygame.K_UP]:   dy-=1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy+=1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx-=1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx+=1
        ndx,ndy=norm(dx,dy)

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
                    for i in range(cnt):
                        a=math.radians(-70+i*20)
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

    def draw(self,surf,ox,oy):
        hover=5+math.sin(self.bob)*5
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,70)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        if self.sprite:
            dy=gsy-self.sprite.get_height()-int(hover)
            dx=gsx-self.sprite.get_width()//2
            if self.hurt_flash>0:
                flash_spr=self.sprite.copy()
                alpha=int(180*min(self.hurt_flash/0.18,1.0))
                flash_spr.fill((255,0,0,alpha),special_flags=pygame.BLEND_RGBA_MULT)
                flash_spr.fill((255,80,80,alpha),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(flash_spr,(dx,dy))
            else:
                surf.blit(self.sprite,(dx,dy))
            bw=80; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-40,dy-14,bw,8))
            pygame.draw.rect(surf,RED, (gsx-40,dy-14,int(bw*ratio),8))
        else:
            sy2=int(gsy-self.radius-hover)
            col=self.char_color
            if self.hurt_flash>0:
                t=min(self.hurt_flash/0.18,1.0)
                col=(int(col[0]+(255-col[0])*t*0.8),
                     int(col[1]*( 1-t*0.7)),
                     int(col[2]*(1-t*0.7)))
            pygame.draw.circle(surf,col,(gsx,sy2),self.radius)
            bw=80; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-40,sy2-self.radius-14,bw,8))
            pygame.draw.rect(surf,RED, (gsx-40,sy2-self.radius-14,int(bw*ratio),8))
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
    {"name":"Wand Lv+",     "desc":"Faster, stronger magic bolt",   "key":"wand"},
    {"name":"Axe",          "desc":"Cleaving axe through enemies",  "key":"axe"},
    {"name":"Holy Cross",   "desc":"Cross fires in 4 directions",   "key":"cross"},
    {"name":"Garlic",       "desc":"Damage aura around you",        "key":"garlic"},
    {"name":"Lightning",    "desc":"Chain lightning strikes",       "key":"lightning"},
    {"name":"Flame",        "desc":"Burning fire zone",             "key":"flame"},
    {"name":"Scatter Bolt", "desc":"Random multi-target lightning", "key":"scatter"},
    {"name":"Speed Up",     "desc":"Move 15% faster",               "key":"speed"},
    {"name":"Max HP Up",    "desc":"Max HP +30, restore 30",        "key":"maxhp"},
]

# T1 accessories (unlock first evolution per weapon)
# T2 accessories (unlock second evolution per weapon)
ACCESSORIES=[
    {"name":"Tome of Arcane",  "desc":"Wand S4: Arcane Bolt",        "key":"acc_tome",   "color":(100,150,255), "tier":1},
    {"name":"Warrior Ring",    "desc":"Axe S4: Death Scythe",        "key":"acc_ring",   "color":(255,160,40),  "tier":1},
    {"name":"Thunder Rod",     "desc":"Lightning S4: Chain Storm",   "key":"acc_rod",    "color":(0,220,255),   "tier":1},
    {"name":"Hellfire Ember",  "desc":"Flame S4: Inferno",           "key":"acc_ember",  "color":(255,80,30),   "tier":1},
    {"name":"Crystal Orb",     "desc":"Wand S5: Arcane Barrage",     "key":"acc_crystal","color":(200,230,255), "tier":2},
    {"name":"Reaper's Edge",   "desc":"Axe S5: Soul Reaper",         "key":"acc_reaper", "color":(180,50,255),  "tier":2},
    {"name":"Storm Crown",     "desc":"Lightning S5: Omega Storm",   "key":"acc_crown",  "color":(50,255,220),  "tier":2},
    {"name":"Abyssal Core",    "desc":"Flame S5: Dragon Fire",       "key":"acc_abyss",  "color":(255,50,0),    "tier":2},
]

# Each node: key, name, color, stage, requirements (list of dicts)
# req types: {"w":key,"lv":n}  {"acc":key}  {"evo":key}
EVOLUTION_NODES=[
    # ── Stage 4 (weapon Lv5 + T1 acc) ───────────────────────
    {"key":"evo_arcane",  "name":"Arcane Bolt",    "color":(120,180,255),"stage":4,
     "req":[{"w":"wand","lv":5},      {"acc":"acc_tome"}]},
    {"key":"evo_scythe",  "name":"Death Scythe",   "color":(200,80,255), "stage":4,
     "req":[{"w":"axe","lv":5},       {"acc":"acc_ring"}]},
    {"key":"evo_storm",   "name":"Chain Storm",    "color":(0,240,255),  "stage":4,
     "req":[{"w":"lightning","lv":5}, {"acc":"acc_rod"}]},
    {"key":"evo_inferno", "name":"Inferno",        "color":(255,120,20), "stage":4,
     "req":[{"w":"flame","lv":5},     {"acc":"acc_ember"}]},

    # ── Stage 5 (S4 evo + T2 acc + weapon Lv7) ───────────────
    {"key":"evo_arcane2",  "name":"Arcane Barrage", "color":(80,140,255), "stage":5,
     "req":[{"evo":"evo_arcane"},  {"w":"wand","lv":7},      {"acc":"acc_crystal"}]},
    {"key":"evo_scythe2",  "name":"Soul Reaper",    "color":(220,60,255), "stage":5,
     "req":[{"evo":"evo_scythe"},  {"w":"axe","lv":7},       {"acc":"acc_reaper"}]},
    {"key":"evo_storm2",   "name":"Omega Storm",    "color":(0,255,180),  "stage":5,
     "req":[{"evo":"evo_storm"},   {"w":"lightning","lv":7}, {"acc":"acc_crown"}]},
    {"key":"evo_inferno2", "name":"Dragon Fire",    "color":(255,50,0),   "stage":5,
     "req":[{"evo":"evo_inferno"}, {"w":"flame","lv":7},     {"acc":"acc_abyss"}]},

    # ── Stage 6 (two S4 evos fused) ──────────────────────────
    {"key":"evo_arcane_storm","name":"Arcane Storm",   "color":(180,240,255),"stage":6,
     "req":[{"evo":"evo_arcane"},{"evo":"evo_storm"}]},
    {"key":"evo_apocalypse",  "name":"Apocalypse",     "color":(200,30,30),  "stage":6,
     "req":[{"evo":"evo_scythe"},{"evo":"evo_inferno"}]},
    {"key":"evo_thunder_gen", "name":"Thunder Genesis","color":(0,255,255),  "stage":6,
     "req":[{"evo":"evo_arcane2"},{"evo":"evo_storm2"}]},
    {"key":"evo_doom",        "name":"Doom Bringer",   "color":(150,0,200),  "stage":6,
     "req":[{"evo":"evo_scythe2"},{"evo":"evo_inferno2"}]},

    # ── Stage 7 (S5+S6 cross-fusions) ────────────────────────
    {"key":"evo_armageddon","name":"Armageddon",  "color":(255,110,30),"stage":7,
     "req":[{"evo":"evo_arcane_storm"},{"evo":"evo_doom"}]},
    {"key":"evo_ragnarok",  "name":"Ragnarok",    "color":(255,40,100),"stage":7,
     "req":[{"evo":"evo_thunder_gen"},{"evo":"evo_apocalypse"}]},

    # ── Stage 8 (GENESIS) ─────────────────────────────────────
    {"key":"evo_genesis","name":"★ GENESIS ★","color":(255,215,0),"stage":8,
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
    pool=[u for u in UPGRADES if not (u["key"]=="wand" and player.weapons["wand"]["level"]>=8)
          and not (u["key"]=="scatter" and player.weapons["scatter"]["level"]>=8)]
    for acc in ACCESSORIES:
        if acc["key"] not in player.accessories:
            pool.append(acc)
    random.shuffle(pool); return pool[:n]

def apply_upgrade(player,key):
    if key.startswith("acc_"):
        player.accessories.add(key); return check_evolutions(player)
    if key in ("wand","axe","cross","garlic","lightning","flame","scatter"):
        w=player.weapons[key]; w["level"]=w.get("level",0)+1
        if key=="wand":      w["cooldown"]=max(0.2, 0.8 -w["level"]*0.07)
        if key=="axe":       w["cooldown"]=max(0.5, 1.5 -w["level"]*0.10)
        if key=="lightning": w["cooldown"]=max(0.6, 2.0 -w["level"]*0.15)
        if key=="flame":     w["cooldown"]=max(1.5, 4.0 -w["level"]*0.30)
        if key=="scatter":   w["cooldown"]=max(0.8, 2.2 -w["level"]*0.18)
        return check_evolutions(player)
    elif key=="speed":  player.speed*=1.15
    elif key=="maxhp":  player.max_hp+=30; player.hp=min(player.hp+30,player.max_hp)
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
    rate=max(0.3,1.5-elapsed/120)
    if since_last>=rate:
        count=min(1+int(elapsed//30),6)
        if underground: count*=10
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


def draw_hud(surf, player, level, xp, xp_next, elapsed, kills, boss_warn):
    t_ms = pygame.time.get_ticks()

    # ── Bottom XP panel ──
    bar_h = 26
    _ang_panel(surf, 0, H-bar_h, W, bar_h, UI_BG, NEON_P, cut=0, bw=1)
    lv_s = font_small.render(f"LV.{level:02d}", True, NEON_G)
    surf.blit(lv_s, (6, H-bar_h+4))
    _seg_bar(surf, 68, H-bar_h+5, W-136, bar_h-10, xp/xp_next, NEON_G)
    xp_s = font_tiny.render(f"{xp}/{xp_next} XP", True, (80,75,100))
    surf.blit(xp_s, (W-xp_s.get_width()-6, H-bar_h+6))

    # ── Timer (top center) ──
    m2, s2 = divmod(int(elapsed), 60)
    t_str  = f"[ {m2:02d}:{s2:02d} ]"
    t_surf = font_med.render(t_str, True, (200,200,210))
    tw = t_surf.get_width()+28
    _ang_panel(surf, W//2-tw//2, 4, tw, 38, UI_BG, NEON_P, cut=7, bw=2)
    surf.blit(t_surf, (W//2-t_surf.get_width()//2, 9))

    # ── Kill counter (top right) ──
    k_s = font_small.render(f"KILLS:{kills:04d}", True, NEON_R)
    kw  = k_s.get_width()+18
    _ang_panel(surf, W-kw-4, 4, kw, 30, UI_BG, NEON_R, cut=5, bw=1)
    surf.blit(k_s, (W-k_s.get_width()-10, 9))

    # ── Weapon chips (top left) ──
    WCOLORS = {"wand":NEON_B,"axe":ORANGE,"cross":YELLOW,
               "garlic":NEON_R,"lightning":CYAN,"flame":ORANGE,"scatter":(0,230,255)}
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

    # ── Mute hint ──
    surf.blit(font_tiny.render("[M]MUTE  [ESC]PAUSE", True, (45,40,65)), (W-148, H-bar_h-16))

    # ── Boss warning ──
    if boss_warn > 0:
        alpha  = int(255 * min(1, boss_warn*3))
        flash  = pygame.Surface((W, H), pygame.SRCALPHA)
        flash.fill((200, 0, 30, int(40*abs(math.sin(t_ms/90)))))
        surf.blit(flash, (0,0))
        pulse  = abs(math.sin(t_ms/85))
        warn_c = (255, int(15+pulse*50), int(15+pulse*30))
        warn   = font_large.render("!! BOSS INCOMING !!", True, warn_c)
        warn.set_alpha(alpha)
        pw, ph = warn.get_width()+48, warn.get_height()+24
        wp     = pygame.Surface((pw, ph), pygame.SRCALPHA)
        _ang_panel(wp, 0, 0, pw, ph, (35,0,12,190), NEON_R, cut=12, bw=2)
        _brackets(wp, 0, 0, pw, ph, NEON_R, size=14)
        wp.set_alpha(alpha)
        surf.blit(wp,   (W//2-pw//2, H//2-ph//2-14))
        surf.blit(warn, (W//2-warn.get_width()//2, H//2-warn.get_height()//2-14))


def levelup_screen(surf, options):
    t_ms = pygame.time.get_ticks()
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 195))
    surf.blit(overlay, (0, 0))
    # Scanlines on overlay
    for row in range(0, H, 4):
        pygame.draw.line(surf, (0, 0, 0, 18), (0, row), (W, row))

    # Title
    title = font_large.render("// POWER SURGE //", True, NEON_G)
    _ang_panel(surf, W//2-title.get_width()//2-20, 70,
               title.get_width()+40, title.get_height()+16, UI_BG, NEON_G, cut=10, bw=2)
    _brackets(surf, W//2-title.get_width()//2-20, 70,
              title.get_width()+40, title.get_height()+16, NEON_G, size=12)
    surf.blit(title, (W//2-title.get_width()//2, 78))

    sub = font_small.render("SELECT UPGRADE  [ 1 ]  [ 2 ]  [ 3 ]", True, (100,95,130))
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
        c     = opt.get("color") or WCOLORS2.get(opt["key"], WHITE)
        bg    = (22, 16, 36) if not hover else (32, 22, 52)
        _ang_panel(surf, rx, ry, cw, ch, bg, c, cut=10, bw=2)
        _brackets(surf, rx, ry, cw, ch, c, size=10, bw=1)
        _scan_overlay(surf, (rx, ry, cw, ch), 22)
        # Number badge
        badge = font_small.render(f"[{i+1}]", True, c)
        surf.blit(badge, (rx+10, ry+10))
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
        title_str = "//  SELECT  WARRIOR  //"
        title_s   = font_large.render(title_str, True, NEON_P)
        th = title_s.get_height()
        _ang_panel(surf, W//2-title_s.get_width()//2-24, 30,
                   title_s.get_width()+48, th+16, UI_BG, NEON_P, cut=12, bw=2)
        _brackets(surf, W//2-title_s.get_width()//2-24, 30,
                  title_s.get_width()+48, th+16, NEON_P, size=14)
        surf.blit(title_s, (W//2-title_s.get_width()//2, 38))

        sub_s = font_small.render("PRESS  [ 1 ] - [ 6 ]  OR  CLICK", True, (80,75,110))
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
    title=font_large.render("// EVOLUTION TREE //",True,(255,215,0))
    pulse=abs(math.sin(t_ms*0.0015))
    tw=title.get_width()+50
    _ang_panel(surf,W//2-tw//2,4,tw,36,UI_BG,(255,215,0),cut=10,bw=2)
    surf.blit(title,(W//2-title.get_width()//2,8))

    # ── Layout ───────────────────────────────────────────────────────────────
    LANES=[W//2-470,W//2-157,W//2+157,W//2+470]
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
    for label,cy in [("T1 Accessories",SY["acc1"]),("T2 Accessories",SY["acc2"]),
                     ("Stage IV",SY["s4"]),("Stage V",SY["s5"]),
                     ("Stage VI",SY["s6"]),("Stage VII",SY["s7"]),("Stage VIII",SY["s8"])]:
        sl=font_tiny.render(label,True,(70,65,90))
        surf.blit(sl,(6,cy-7))
        pygame.draw.line(surf,(40,38,55),(90,cy),(LANES[0]-NW//2-6,cy))

    # ── Accessories ───────────────────────────────────────────────────────────
    t1=[a for a in ACCESSORIES if a["tier"]==1]
    t2=[a for a in ACCESSORIES if a["tier"]==2]
    for i,acc in enumerate(t1): _acc_card(acc,LANES[i],SY["acc1"])
    for i,acc in enumerate(t2): _acc_card(acc,LANES[i],SY["acc2"])

    # Wire acc T1→T2
    for i in range(4):
        _wire(LANES[i],SY["acc1"]+AH//2,LANES[i],SY["acc2"]-AH//2,(60,56,80))

    # ── S4 nodes ──────────────────────────────────────────────────────────────
    for i,node in enumerate(EVOLUTION_NODES[:4]):
        cx=LANES[i]
        top=_evo_card(node,cx,SY["s4"])
        # Wire from T2 acc bottom
        _wire(cx,SY["acc2"]+AH//2,cx,top[1],(60,56,80))

    # ── S5 nodes ──────────────────────────────────────────────────────────────
    for i,node in enumerate(EVOLUTION_NODES[4:8]):
        cx=LANES[i]
        top=_evo_card(node,cx,SY["s5"])
        s4key=next(r["evo"] for r in node["req"] if "evo" in r)
        if s4key in node_pos:
            px2,py2=node_pos[s4key]
            col=node["color"] if s4key in player.evolutions else (60,56,80)
            _wire(px2,py2,cx,top[1],col)

    # ── S6 nodes ──────────────────────────────────────────────────────────────
    S6_CX=[W//2-355,W//2-118,W//2+118,W//2+355]
    for j,node in enumerate(EVOLUTION_NODES[8:12]):
        cx=S6_CX[j]
        top=_evo_card(node,cx,SY["s6"])
        for r in node["req"]:
            if "evo" in r and r["evo"] in node_pos:
                px2,py2=node_pos[r["evo"]]
                col=node["color"] if r["evo"] in player.evolutions else (60,56,80)
                _wire(px2,py2,cx,top[1],col)

    # ── S7 nodes ──────────────────────────────────────────────────────────────
    S7_CX=[W//2-215,W//2+215]
    for j,node in enumerate(EVOLUTION_NODES[12:14]):
        cx=S7_CX[j]
        top=_evo_card(node,cx,SY["s7"])
        for r in node["req"]:
            if "evo" in r and r["evo"] in node_pos:
                px2,py2=node_pos[r["evo"]]
                col=node["color"] if r["evo"] in player.evolutions else (60,56,80)
                _wire(px2,py2,cx,top[1],col,2)

    # ── S8 GENESIS ────────────────────────────────────────────────────────────
    node8=EVOLUTION_NODES[14]; cx8=W//2
    top8=_evo_card(node8,cx8,SY["s8"])
    for r in node8["req"]:
        if "evo" in r and r["evo"] in node_pos:
            px2,py2=node_pos[r["evo"]]
            col=(255,215,0) if r["evo"] in player.evolutions else (80,70,40)
            _wire(px2,py2,cx8,top8[1],col,2)

    # ── Hint ──────────────────────────────────────────────────────────────────
    hint=font_tiny.render("[ESC] / [T]  Back to Pause          ✓ = Unlocked   ✗ = Locked",
                          True,(70,65,90))
    surf.blit(hint,(W//2-hint.get_width()//2,H-18))
    return {}


def pause_screen(surf):
    """
    ポーズ画面を描画し、プレイヤー操作を待つ。
    戻り値: "resume" | "char_select" | "quit"
    """
    t_ms = pygame.time.get_ticks()

    # 半透明オーバーレイ
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    surf.blit(overlay, (0, 0))

    # スキャンライン
    for row in range(0, H, 4):
        pygame.draw.line(surf, (0, 0, 0, 20), (0, row), (W, row))

    # タイトル
    title = font_large.render("//  PAUSED  //", True, NEON_P)
    pulse = abs(math.sin(t_ms / 600))
    title.set_alpha(int(180 + pulse * 75))
    tw = title.get_width() + 48
    _ang_panel(surf, W//2 - tw//2, 80, tw, title.get_height() + 20, UI_BG, NEON_P, cut=12, bw=2)
    _brackets(surf, W//2 - tw//2, 80, tw, title.get_height() + 20, NEON_P, size=14)
    surf.blit(title, (W//2 - title.get_width()//2, 88))

    # メニュー項目定義
    ITEMS = [
        {"label": "RESUME",           "key": "resume",      "color": NEON_G,  "hint": "[ESC]"},
        {"label": "EVOLUTION TREE",   "key": "tree",        "color": (255,215,0), "hint": "[T]"},
        {"label": "CHARACTER SELECT", "key": "char_select", "color": NEON_P,  "hint": "[C]"},
        {"label": "QUIT GAME",        "key": "quit",        "color": NEON_R,  "hint": "[Q]"},
    ]
    iw, ih, gap = 420, 64, 16
    total_h = len(ITEMS) * ih + (len(ITEMS) - 1) * gap
    iy0 = H // 2 - total_h // 2 + 10
    mx, my = pygame.mouse.get_pos()

    rects = {}
    for i, item in enumerate(ITEMS):
        rx = W // 2 - iw // 2
        ry = iy0 + i * (ih + gap)
        rect = pygame.Rect(rx, ry, iw, ih)
        rects[item["key"]] = rect
        hover = rect.collidepoint(mx, my)
        c = item["color"]
        bg = (28, 20, 44) if not hover else (40, 28, 62)
        _ang_panel(surf, rx, ry, iw, ih, bg, c, cut=10, bw=2)
        if hover:
            gs = pygame.Surface((iw, ih), pygame.SRCALPHA)
            _ang_panel(gs, 0, 0, iw, ih, (0, 0, 0, 0), (*c, 55), cut=10, bw=4)
            surf.blit(gs, (rx, ry))
        _brackets(surf, rx, ry, iw, ih, c, size=10, bw=1)
        # ヒントキー（左）
        hint_s = font_small.render(item["hint"], True, c)
        surf.blit(hint_s, (rx + 14, ry + ih // 2 - hint_s.get_height() // 2))
        # ラベル（中央）
        lbl = font_med.render(item["label"], True, WHITE if not hover else c)
        surf.blit(lbl, (W // 2 - lbl.get_width() // 2, ry + ih // 2 - lbl.get_height() // 2))

    # 操作ヒント
    hint2 = font_tiny.render("ESC: Resume  |  T: Tree  |  C: Char Select  |  Q: Quit", True, (60, 55, 85))
    surf.blit(hint2, (W // 2 - hint2.get_width() // 2, H - 45))

    return rects


def game_over_screen(surf, elapsed, kills, victory):
    surf.fill(DARK)
    # Background grid
    for gx in range(-1, W//80+2):
        pygame.draw.line(surf, UI_GRID, (gx*80, 0), (gx*80, H))
    for gy in range(-1, H//80+2):
        pygame.draw.line(surf, UI_GRID, (0, gy*80), (W, gy*80))

    t_ms = pygame.time.get_ticks()
    if victory:
        title_c = NEON_G;  title_t = "// MISSION COMPLETE //"
        border_c = NEON_G
    else:
        title_c = NEON_R;  title_t = "//  YOU  DIED  //"
        border_c = NEON_R

    title = font_large.render(title_t, True, title_c)
    pulse = abs(math.sin(t_ms/500))
    title.set_alpha(int(180 + pulse*75))

    # Main panel
    pw, ph = 520, 300
    _ang_panel(surf, W//2-pw//2, H//2-ph//2-20, pw, ph, UI_BG, border_c, cut=16, bw=2)
    _brackets(surf, W//2-pw//2, H//2-ph//2-20, pw, ph, border_c, size=18, bw=2)
    _scan_overlay(surf, (W//2-pw//2, H//2-ph//2-20, pw, ph), 25)

    surf.blit(title, (W//2-title.get_width()//2, H//2-ph//2))
    _divider(surf, W//2-pw//2+20, H//2-ph//2+title.get_height()+8,
             pw-40, border_c)

    m2, s2 = divmod(int(elapsed), 60)
    stats = [
        f"TIME    {m2:02d}:{s2:02d}",
        f"KILLS   {kills:04d}",
    ]
    for i, line in enumerate(stats):
        ls = font_med.render(line, True, (200,195,220))
        surf.blit(ls, (W//2-ls.get_width()//2, H//2-ph//2+title.get_height()+28+i*38))

    _divider(surf, W//2-pw//2+20, H//2+ph//2-56, pw-40, (40,35,60))
    hint = font_small.render("[ENTER] RESTART    [ESC] QUIT", True, (80,75,110))
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
            pygame.draw.polygon(surf,tile_col,pts)
            pygame.draw.polygon(surf,grid_col,pts,1)
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
# Main game loop
# ─────────────────────────────────────────────
def run_game(snd,sprites,char_data):
    player=Player(char_data,sprites)
    bullets=[]; enemies=[]; gems=[]; floats=[]; particles=[]
    flames=[]; bolts=[]; chests=[]; rings=[]
    capsules=[]
    since_capsule = 0.0
    level=1; xp=0; xp_next=20
    elapsed=0.0; since_spawn=0.0; since_chest=40.0
    boss_timer=120.0; boss_level=1; boss_warn=0.0; kills=0
    VICTORY_TIME=600
    shake=ScreenShake()
    state="play"; levelup_opts=[]; levelup_rects=[]; victory=False
    pause_rects={}
    # Terrain
    terrain_map=TerrainMap()
    underground=False; surface_pos=(0.0,0.0); valley_ascend_immune=0.0
    ladders=[]; magma_spawn_cd=0.0
    cur_terrain=TERRAIN_GRASS; last_terrain=TERRAIN_GRASS; terrain_notify=0.0
    snd.start_bgm()

    while True:
        dt=min(clock.tick(60)/1000.0,0.05)

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
                    if pause_rects.get("resume",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        state="play"; pygame.mixer.unpause()
                    elif pause_rects.get("tree",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        state="tree"
                    elif pause_rects.get("char_select",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.stop_bgm(); return "char_select"
                    elif pause_rects.get("quit",pygame.Rect(0,0,0,0)).collidepoint(mx,my):
                        snd.stop_bgm(); return "quit"
                if state=="tree" and event.button==1:
                    state="pause"

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
            if boss_warn>0: boss_warn-=dt
            if elapsed>=VICTORY_TIME: state="gameover"; victory=True

            if boss_timer<=10 and boss_warn<=0: boss_warn=boss_timer
            if boss_timer<=0:
                enemies.append(spawn_boss(player.x,player.y,boss_level))
                snd.play("boss"); shake.shake(8,0.5); boss_level+=1; boss_timer=120.0
                floats.append(FloatText(player.x,player.y-80,"BOSS!",RED,2.0))

            if since_chest>=60:
                since_chest=0.0; a=random.uniform(0,math.pi*2); rd=random.uniform(150,350)
                chests.append(Chest(player.x+math.cos(a)*rd,player.y+math.sin(a)*rd))

            player.update(dt,keys,enemies,bullets,floats,flames,bolts,rings,particles,snd,shake,
                          None if underground else terrain_map)

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
            for b in bolts: b.update(dt)
            bolts=[b for b in bolts if b.alive]
            for r in rings: r.update(dt)
            rings=[r for r in rings if r.alive]
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
            for e in enemies: e.update(dt,player.x,player.y)

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
                    for _ in range(8): particles.append(Particle(e.x,e.y,e.color))
                    rings.append(RingEffect(e.x,e.y,e.color,e.radius*2+10,3,0.3))
                    if isinstance(e,Boss):
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

            for c in chests:
                c.update(dt)
                if dist((player.x,player.y),(c.x,c.y))<player.radius+c.radius:
                    c.alive=False; bonus=apply_chest_reward(player,c.reward["key"])
                    if bonus: xp+=bonus
                    floats.append(FloatText(player.x,player.y-50,c.reward["name"],GOLD,1.5))
                    rings.append(RingEffect(player.x,player.y,GOLD,50,3,0.3))
                    snd.play("chest")
            chests=[c for c in chests if c.alive]

            while xp>=xp_next:
                xp-=xp_next; level+=1; xp_next=int(xp_next*1.25)
                levelup_opts=pick_upgrades(player); state="levelup"; snd.play("levelup")

            for f in floats:    f.update(dt)
            for p in particles: p.update(dt)
            floats=[f for f in floats if f.alive]
            particles=[p for p in particles if p.alive]
            if not player.alive: state="gameover"; victory=False

        sx_off,sy_off=shake.update(dt)
        ox=player.x+sx_off; oy=player.y+sy_off
        draw_bg(screen,ox,oy,terrain_map,underground,player.x,player.y)
        # Ground-level effects (no depth sort needed)
        for f in flames:    f.draw(screen,ox,oy)
        for r in rings:     r.draw(screen,ox,oy)
        # Depth-sort all entities by (x+y) for correct isometric occlusion
        depth=[]
        for c in chests:    depth.append((c.x+c.y,'chest',c))
        for g in gems:      depth.append((g.x+g.y,'gem',g))
        for cap in capsules: depth.append((cap.x+cap.y,'capsule',cap))
        for e in enemies:   depth.append((e.x+e.y,'enemy',e))
        for b in bullets:   depth.append((b.x+b.y,'bullet',b))
        for p in particles: depth.append((p.x+p.y,'part',p))
        for l in ladders:   depth.append((l.x+l.y,'ladder',l))
        depth.append((player.x+player.y,'player',player))
        depth.sort(key=lambda i:i[0])
        for _,etype,ent in depth:
            if etype=='enemy': ent.draw(screen,ox,oy,sprites)
            else:              ent.draw(screen,ox,oy)
        for bl in bolts:    bl.draw(screen,ox,oy)
        for ft in floats:   ft.draw(screen,ox,oy)
        draw_hud(screen,player,level,xp,xp_next,elapsed,kills,boss_warn)
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
                us=font_med.render("─ UNDERGROUND ─",True,(140,80,255))
                screen.blit(us,(W//2-us.get_width()//2,18))
                if ladders:
                    hs=font_small.render("Find the green LADDER to return!",True,(80,220,80))
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
        if state=="gameover": game_over_screen(screen,elapsed,kills,victory)
        if state=="pause":    pause_rects=pause_screen(screen)
        if state=="tree":     draw_evolution_tree(screen,player)

        # ── 画面端血しぶきビネット ──────────────────────────────
        if player.hurt_flash>0:
            t=min(player.hurt_flash/0.22,1.0)
            vign=pygame.Surface((W,H),pygame.SRCALPHA)
            edge=int(80*t)
            for i in range(edge):
                a2=int(140*(1-(i/edge))**1.5*t)
                col2=(180,0,0,a2)
                pygame.draw.rect(vign,col2,(i,i,W-i*2,H-i*2),1)
            screen.blit(vign,(0,0))

        pygame.display.flip()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__=="__main__":
    screen.fill(DARK)
    screen.blit(font_med.render("Generating assets...",True,GRAY),(W//2-100,H//2-20))
    pygame.display.flip()
    snd=SoundManager(); sprites=build_sprites()
    while True:
        char_data=character_select(screen,sprites)
        result=run_game(snd,sprites,char_data)
        if result=="quit":
            break
        # "char_select" の場合はループしてキャラ選択画面に戻る
    pygame.quit(); sys.exit()
