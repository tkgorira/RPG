import pygame
import math
import random
import sys
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
                self._cache[key] = rng.choices(range(6), weights=TERRAIN_WEIGHTS)[0]
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

def _draw_boss(size=88):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    gs = pygame.Surface((size,size),pygame.SRCALPHA)
    pygame.draw.circle(gs,(155,0,205,38),(cx,cx),cx-4)
    s.blit(gs,(0,0))
    pygame.draw.ellipse(s,(0,0,0,62),(cx-24,size-14,48,12))
    pygame.draw.circle(s,(145,32,198),(cx,cx-2),30)
    pygame.draw.polygon(s,(102,15,145),[(cx-19,21),(cx-30,2),(cx-11,17)])
    pygame.draw.polygon(s,(102,15,145),[(cx+19,21),(cx+30,2),(cx+11,17)])
    pygame.draw.polygon(s,(78,8,112),[(cx-19,21),(cx-30,2),(cx-11,17)],2)
    pygame.draw.polygon(s,(78,8,112),[(cx+19,21),(cx+30,2),(cx+11,17)],2)
    pygame.draw.circle(s,RED,(cx-10,cx-6),8)
    pygame.draw.circle(s,RED,(cx+10,cx-6),8)
    pygame.draw.circle(s,(255,52,52),(cx-10,cx-6),5)
    pygame.draw.circle(s,(255,52,52),(cx+10,cx-6),5)
    pygame.draw.circle(s,(18,8,8),(cx-10,cx-6),2)
    pygame.draw.circle(s,(18,8,8),(cx+10,cx-6),2)
    pygame.draw.arc(s,(48,5,68),(cx-16,cx-3,32,18),math.pi,0,4)
    pygame.draw.polygon(s,WHITE,[(cx-9,cx+2),(cx-7,cx+12),(cx-5,cx+2)])
    pygame.draw.polygon(s,WHITE,[(cx+5,cx+2),(cx+7,cx+12),(cx+9,cx+2)])
    pygame.draw.circle(s,(82,10,122),(cx,cx-2),30,3)
    return s

def build_sprites():
    return {
        "knight":       _draw_knight(64),
        "mage":         _draw_mage(64),
        "rogue":        _draw_rogue(64),
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
        "plague_doctor":  _draw_plague_doctor(64),
        "boss":           _draw_boss(88),
    }


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
# Gem / Chest / FloatText
# ─────────────────────────────────────────────
class Gem:
    def __init__(self,x,y,value=5):
        self.x,self.y=x,y; self.value=value; self.radius=6; self.alive=True
    def draw(self,surf,ox,oy):
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,50)
        sx,sy=iso_pos(self.x,self.y,10,ox,oy)
        pygame.draw.circle(surf,CYAN,(sx,sy),self.radius)
        pygame.draw.circle(surf,WHITE,(sx,sy),self.radius,1)

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
        self.x,self.y=x,y; self.radius=20; self.alive=True
        self.bob=0.0; self.pulse=0.0
    def update(self,dt): self.bob+=dt*1.5; self.pulse+=dt*2.5
    def draw(self,surf,ox,oy):
        bv=math.sin(self.bob)*3
        sx,sy=iso_pos(self.x,self.y,0,ox,oy)
        shaft_h=80
        # Shaft walls (dark stone, tapers toward top)
        pygame.draw.polygon(surf,(22,16,30),
            [(sx-18,sy),(sx-7,sy-shaft_h),(sx+7,sy-shaft_h),(sx+18,sy)])
        # Stone texture lines
        for i in range(3):
            fy=sy-20-i*22; fw=int(18-i*3)
            pygame.draw.line(surf,(35,26,46),(sx-fw,fy),(sx-fw+5,fy),1)
            pygame.draw.line(surf,(35,26,46),(sx+fw-5,fy),(sx+fw,fy),1)
        # Ground-level opening (dark oval hole)
        pygame.draw.ellipse(surf,(5,3,10),(sx-18,sy-9,36,14))
        pygame.draw.ellipse(surf,(50,35,70),(sx-18,sy-9,36,14),2)
        # Light from surface at top (pulse glow)
        pa=int(70+50*abs(math.sin(self.pulse)))
        gs=pygame.Surface((70,35),pygame.SRCALPHA)
        pygame.draw.ellipse(gs,(180,255,140,pa),(5,5,60,25))
        pygame.draw.ellipse(gs,(230,255,200,pa//2),(15,8,40,16))
        surf.blit(gs,(sx-35,sy-shaft_h-20+int(bv)))
        # Light beam rays
        ra=int(30+20*abs(math.sin(self.pulse)))
        for rx,rw in [(-9,4),(0,3),(9,4)]:
            rs=pygame.Surface((abs(rw)+2,shaft_h-10),pygame.SRCALPHA)
            pygame.draw.rect(rs,(200,255,160,ra),(0,0,abs(rw)+2,shaft_h-10))
            surf.blit(rs,(sx+rx-1,sy-shaft_h+5))
        # Ladder rails (perspective - converge at top)
        col=(175,135,55)
        pygame.draw.line(surf,col,(sx-16,sy-4),(sx-5,sy-shaft_h+2),3)
        pygame.draw.line(surf,col,(sx+16,sy-4),(sx+5,sy-shaft_h+2),3)
        # Rungs (7 rungs, get smaller/closer toward top)
        for i in range(7):
            t=i/6
            ry=int(sy-6-t*(shaft_h-10))
            lx=int(sx-16+t*11); rx2=int(sx+16-t*11)
            w=max(1,3-int(t*2))
            pygame.draw.line(surf,col,(lx,ry),(rx2,ry),w)
        # Pulsing label
        lc=(int(70+80*abs(math.sin(self.pulse))),255,80)
        lbl=font_tiny.render("▲ SURFACE",True,lc)
        surf.blit(lbl,(sx-lbl.get_width()//2,sy-shaft_h-30+int(bv)))

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
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,60)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        spr=sprites.get(self.sprite_key)
        if spr:
            dy=gsy-spr.get_height()-int(hover); dx=gsx-spr.get_width()//2
            if self.hit_flash>0:
                ws=spr.copy(); ws.fill((255,255,255,160),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws,(dx,dy))
            else:
                surf.blit(spr,(dx,dy))
            bw=self.radius*2; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-self.radius,dy-8,bw,5))
            pygame.draw.rect(surf,GREEN,(gsx-self.radius,dy-8,int(bw*ratio),5))
        else:
            sy2=int(gsy-self.radius-hover)
            pygame.draw.circle(surf,self.color,(gsx,sy2),self.radius)
            bw=self.radius*2; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-self.radius,sy2-self.radius-8,bw,5))
            pygame.draw.rect(surf,GREEN,(gsx-self.radius,sy2-self.radius-8,int(bw*ratio),5))

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
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,70)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        if self.telegraph>0:
            pulse=abs(math.sin(self.telegraph*20))*22; r=36+int(pulse)
            rw=max(2,int(r*2.0)); rh=max(1,int(r*0.7))
            s=pygame.Surface((rw,rh),pygame.SRCALPHA)
            pygame.draw.ellipse(s,(255,50,50,115),(0,0,rw,rh))
            surf.blit(s,(gsx-rw//2,gsy-rh//2))
        spr=sprites.get("boss")
        if spr:
            dy=gsy-spr.get_height()-int(hover); dx=gsx-spr.get_width()//2
            if self.hit_flash>0:
                ws=spr.copy(); ws.fill((255,255,255,160),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws,(dx,dy))
            else:
                surf.blit(spr,(dx,dy))
            bw=100; ratio=max(0,self.hp/self.max_hp)
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
     "weapons":{"wand":0,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0,"plague":1},"wand_cd":0.8},
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
        self.bob=0.0; self.ice_dir=(0.0,0.0)
        self.sprite=sprites.get(char_data["sprite"])
        self.weapons={
            "wand":     {"level":char_data["weapons"]["wand"],     "timer":0.0,"cooldown":char_data["wand_cd"]},
            "axe":      {"level":char_data["weapons"]["axe"],      "timer":0.0,"cooldown":1.5},
            "cross":    {"level":char_data["weapons"]["cross"],    "timer":0.0,"cooldown":3.0},
            "garlic":   {"level":char_data["weapons"]["garlic"]},
            "lightning":{"level":char_data["weapons"]["lightning"],"timer":0.0,"cooldown":2.0},
            "flame":    {"level":char_data["weapons"]["flame"],    "timer":0.0,"cooldown":4.0},
            "plague":   {"level":char_data["weapons"].get("plague",0)},
        }
        self.aura=None

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

        target=min(enemies,key=lambda e:dist((self.x,self.y),(e.x,e.y)),default=None)

        # ── Wand ──
        w=self.weapons["wand"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"] and target:
                w["timer"]=0.0
                count=1+(w["level"]-1)//2
                base=math.atan2(target.y-self.y,target.x-self.x)
                sp=math.radians(12)
                for i in range(count):
                    a=base+sp*(i-(count-1)/2)
                    bullets.append(Bullet(self.x,self.y,math.cos(a),math.sin(a),
                        420,20+w["level"]*5,6,BLUE,1.5,1+w["level"]//3,style="orb"))
                # Muzzle flash
                rings.append(RingEffect(self.x,self.y,BLUE,38,2,0.18))
                rings.append(RingEffect(self.x,self.y,(150,200,255),22,2,0.12))
                snd.play("shoot")

        # ── Axe ──
        w=self.weapons["axe"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                for i in range(w["level"]):
                    a=math.radians(-70+i*20)
                    bullets.append(AxeBullet(self.x,self.y,math.cos(a),math.sin(a),
                        360,40+w["level"]*10))
                rings.append(RingEffect(self.x,self.y,ORANGE,42,3,0.2))
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
                dmg=55+w["level"]*15; chains=1+w["level"]
                target.hp-=dmg; target.hit_flash=0.1
                floats.append(FloatText(target.x,target.y-20,str(dmg),CYAN,0.6))
                pts=[(self.x,self.y),(target.x,target.y)]
                prev=target; hit=[target]
                for _ in range(chains-1):
                    nearby=sorted([e for e in enemies if e not in hit],
                                  key=lambda e:dist((prev.x,prev.y),(e.x,e.y)))
                    if not nearby or dist((prev.x,prev.y),(nearby[0].x,nearby[0].y))>350: break
                    nxt=nearby[0]; nxt.hp-=int(dmg*0.6); nxt.hit_flash=0.1
                    floats.append(FloatText(nxt.x,nxt.y-20,str(int(dmg*0.6)),CYAN,0.5))
                    pts.append((nxt.x,nxt.y)); hit.append(nxt); prev=nxt
                bolts.append(LightningBolt(pts))
                # Discharge flash at origin
                rings.append(RingEffect(self.x,self.y,CYAN,50,3,0.18))
                rings.append(RingEffect(self.x,self.y,WHITE,25,2,0.12))
                snd.play("lightning"); shake.shake(4)

        # ── Flame ──
        w=self.weapons["flame"]
        if w["level"]>=1:
            w["timer"]+=dt
            if w["timer"]>=w["cooldown"]:
                w["timer"]=0.0
                flames.append(FlameZone(self.x,self.y,70+w["level"]*20,12+w["level"]*6,3.0))
                # Eruption burst
                for _ in range(12):
                    p=Particle(self.x+random.uniform(-25,25),self.y+random.uniform(-10,10),
                               random.choice([ORANGE,(255,60,0),(255,200,0)]))
                    p.vy=-abs(p.vy)-100
                    p.vx*=0.4
                    particles.append(p)
                rings.append(RingEffect(self.x,self.y,ORANGE,55,3,0.22))
                snd.play("flame")

        # ── Contact damage (continuous DPS) ──
        for e in enemies:
            if dist((self.x,self.y),(e.x,e.y))<self.radius+e.radius:
                self.hp-=e.damage*dt
                if self.hurt_sound_cd<=0:
                    snd.play("hurt"); self.hurt_sound_cd=0.5
        if self.hp<=0: self.alive=False

    def draw(self,surf,ox,oy):
        hover=5+math.sin(self.bob)*5
        draw_shadow(surf,self.x,self.y,ox,oy,self.radius,70)
        gsx,gsy=iso_pos(self.x,self.y,0,ox,oy)
        if self.sprite:
            dy=gsy-self.sprite.get_height()-int(hover)
            dx=gsx-self.sprite.get_width()//2
            surf.blit(self.sprite,(dx,dy))
            bw=80; ratio=max(0,self.hp/self.max_hp)
            pygame.draw.rect(surf,GRAY,(gsx-40,dy-14,bw,8))
            pygame.draw.rect(surf,RED, (gsx-40,dy-14,int(bw*ratio),8))
        else:
            sy2=int(gsy-self.radius-hover)
            pygame.draw.circle(surf,self.char_color,(gsx,sy2),self.radius)
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
    {"name":"Wand Lv+",  "desc":"Faster, stronger magic bolt", "key":"wand"},
    {"name":"Axe",       "desc":"Cleaving axe through enemies","key":"axe"},
    {"name":"Holy Cross","desc":"Cross fires in 4 directions", "key":"cross"},
    {"name":"Garlic",    "desc":"Damage aura around you",      "key":"garlic"},
    {"name":"Lightning", "desc":"Chain lightning strikes",     "key":"lightning"},
    {"name":"Flame",     "desc":"Burning fire zone",           "key":"flame"},
    {"name":"Speed Up",  "desc":"Move 15% faster",             "key":"speed"},
    {"name":"Max HP Up", "desc":"Max HP +30, restore 30",      "key":"maxhp"},
]

def pick_upgrades(player,n=3):
    pool=[u for u in UPGRADES if not (u["key"]=="wand" and player.weapons["wand"]["level"]>=8)]
    random.shuffle(pool); return pool[:n]

def apply_upgrade(player,key):
    if key in ("wand","axe","cross","garlic","lightning","flame"):
        w=player.weapons[key]; w["level"]=w.get("level",0)+1
        if key=="wand":      w["cooldown"]=max(0.2, 0.8 -w["level"]*0.07)
        if key=="axe":       w["cooldown"]=max(0.5, 1.5 -w["level"]*0.10)
        if key=="lightning": w["cooldown"]=max(0.6, 2.0 -w["level"]*0.15)
        if key=="flame":     w["cooldown"]=max(1.5, 4.0 -w["level"]*0.30)
    elif key=="speed":  player.speed*=1.15
    elif key=="maxhp":  player.max_hp+=30; player.hp=min(player.hp+30,player.max_hp)

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
               "garlic":NEON_R,"lightning":CYAN,"flame":ORANGE}
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
    surf.blit(font_tiny.render("[M]MUTE", True, (45,40,65)), (W-58, H-bar_h-16))

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
                "lightning":CYAN,"flame":ORANGE,"speed":NEON_G,"maxhp":NEON_R}

    for i, opt in enumerate(options):
        rx = sx0 + i*(cw+22); ry = 210
        rect = pygame.Rect(rx, ry, cw, ch); rects.append(rect)
        hover = rect.collidepoint(mx, my)
        c     = WCOLORS2.get(opt["key"], WHITE)
        bg    = (22, 16, 36) if not hover else (32, 22, 52)
        _ang_panel(surf, rx, ry, cw, ch, bg, c, cut=10, bw=2)
        _brackets(surf, rx, ry, cw, ch, c, size=10, bw=1)
        _scan_overlay(surf, (rx, ry, cw, ch), 22)
        # Number badge
        badge = font_small.render(f"[{i+1}]", True, c)
        surf.blit(badge, (rx+10, ry+10))
        # Name
        nm = font_med.render(opt["name"], True, WHITE)
        surf.blit(nm, (rx+12, ry+38))
        # Divider
        _divider(surf, rx+10, ry+72, cw-20, c)
        # Desc
        desc = font_tiny.render(opt["desc"], True, (140,135,160))
        surf.blit(desc, (rx+12, ry+80))
        # Color dot
        pygame.draw.rect(surf, c, (rx+cw-22, ry+10, 12, 12))
        pygame.draw.rect(surf, WHITE, (rx+cw-22, ry+10, 12, 12), 1)
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

        sub_s = font_small.render("PRESS  [ 1 ]  [ 2 ]  [ 3 ]  OR  CLICK", True, (80,75,110))
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


def draw_bg(surf, ox, oy, terrain_map=None, underground=False):
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
            h=18
            face_l=[pts[2],pts[3],(pts[3][0],pts[3][1]-h),(pts[2][0],pts[2][1]-h)]
            face_r=[pts[1],pts[2],(pts[2][0],pts[2][1]-h),(pts[1][0],pts[1][1]-h)]
            pygame.draw.polygon(surf,(45,40,33),face_l)
            pygame.draw.polygon(surf,(55,50,42),face_r)
            top=[(p[0],p[1]-h) for p in pts]
            pygame.draw.polygon(surf,tile_col,top)
            pygame.draw.polygon(surf,grid_col,top,1)
        else:
            pygame.draw.polygon(surf,tile_col,pts)
            pygame.draw.polygon(surf,grid_col,pts,1)
            if tt==TERRAIN_MAGMA:
                lv=int(190+50*abs(math.sin(t*2.5+gx*0.7+gy*0.5)))
                cx=sum(p[0] for p in pts)//4; cy=sum(p[1] for p in pts)//4
                pygame.draw.circle(surf,(lv,lv//5,0),(cx,cy),7)
                pygame.draw.line(surf,(lv,lv//4,0),pts[0],(cx,cy),1)
                pygame.draw.line(surf,(lv,lv//4,0),pts[1],(cx,cy),1)
            elif tt==TERRAIN_ICE:
                cx=sum(p[0] for p in pts)//4; cy=sum(p[1] for p in pts)//4
                pygame.draw.circle(surf,(200,235,255),(cx,cy),4)

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
                N=16
                for ri in range(N,0,-1):
                    r=ri/N
                    rpts=zring(r)
                    if ri>int(N*0.55):
                        v=int((ri-N*0.45)*5.5); col=(v,v//2,v+5)
                    else:
                        v=max(0,int(ri*2)); col=(v,v//4,v//2)
                    pygame.draw.polygon(surf,col,rpts)
                # Terrace ledge lines
                for ri in range(N,1,-2):
                    ec=int(42+(N-ri)*3)
                    pygame.draw.polygon(surf,(ec,ec//2,ec+6),zring(ri/N),1)
                # Absolute void center
                pygame.draw.polygon(surf,(0,0,0),zring(0.05))

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
    level=1; xp=0; xp_next=20
    elapsed=0.0; since_spawn=0.0; since_chest=40.0
    boss_timer=120.0; boss_level=1; boss_warn=0.0; kills=0
    VICTORY_TIME=600
    shake=ScreenShake()
    state="play"; levelup_opts=[]; levelup_rects=[]; victory=False
    # Terrain
    terrain_map=TerrainMap()
    underground=False; surface_pos=(0.0,0.0)
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
                    if event.key==pygame.K_RETURN: snd.stop_bgm(); return True
                    if event.key==pygame.K_ESCAPE: snd.stop_bgm(); pygame.quit(); sys.exit()
                if state=="levelup":
                    for i,opt in enumerate(levelup_opts):
                        if event.key in (pygame.K_1+i,pygame.K_KP1+i):
                            apply_upgrade(player,opt["key"]); state="play"
                if state=="play" and event.key==pygame.K_ESCAPE:
                    snd.stop_bgm(); pygame.quit(); sys.exit()
            if event.type==pygame.MOUSEBUTTONDOWN and state=="levelup":
                mx,my=pygame.mouse.get_pos()
                for i,rect in enumerate(levelup_rects):
                    if rect.collidepoint(mx,my): apply_upgrade(player,levelup_opts[i]["key"]); state="play"

        keys=pygame.key.get_pressed()

        if state=="play":
            elapsed+=dt; since_spawn+=dt; since_chest+=dt; boss_timer-=dt
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

            if cur_terrain==TERRAIN_MAGMA:
                player.hp-=10*dt
                if player.hurt_sound_cd<=0: snd.play("hurt"); player.hurt_sound_cd=0.5
                magma_spawn_cd-=dt
                if magma_spawn_cd<=0:
                    magma_spawn_cd=random.uniform(3.0,5.0)
                    a=random.uniform(0,math.pi*2); r=random.uniform(300,550)
                    enemies.append(spawn_magma_enemy(player.x+math.cos(a)*r,player.y+math.sin(a)*r,elapsed))
                    floats.append(FloatText(player.x,player.y-60,"Magma Enemy!",ORANGE,1.5))

            if cur_terrain==TERRAIN_VALLEY and not underground:
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
                if dist((player.x,player.y),(g.x,g.y))<player.PICKUP_RANGE: g.alive=False; xp+=g.value
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
        draw_bg(screen,ox,oy,terrain_map,underground)
        # Ground-level effects (no depth sort needed)
        for f in flames:    f.draw(screen,ox,oy)
        for r in rings:     r.draw(screen,ox,oy)
        # Depth-sort all entities by (x+y) for correct isometric occlusion
        depth=[]
        for c in chests:    depth.append((c.x+c.y,'chest',c))
        for g in gems:      depth.append((g.x+g.y,'gem',g))
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
        if not run_game(snd,sprites,char_data): break
