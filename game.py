import pygame
import math
import random
import sys
import array as arr

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)

W, H = 1280, 720
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Vampire Survivors Like")
clock = pygame.time.Clock()

WHITE  = (255, 255, 255)
BLACK  = (0,   0,   0)
RED    = (220, 50,  50)
GREEN  = (50,  200, 80)
BLUE   = (50,  100, 220)
YELLOW = (255, 220, 0)
PURPLE = (180, 50,  220)
GRAY   = (120, 120, 120)
DARK   = (20,  20,  30)
ORANGE = (255, 140, 0)
CYAN   = (0,   200, 220)
PINK   = (255, 100, 180)
GOLD   = (255, 200, 0)
LIME   = (130, 255, 50)

font_large = pygame.font.SysFont(None, 72)
font_med   = pygame.font.SysFont(None, 38)
font_small = pygame.font.SysFont(None, 24)
font_tiny  = pygame.font.SysFont(None, 20)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def norm(dx, dy):
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d else (0.0, 0.0)


# ─────────────────────────────────────────────
# Sprite generation
# ─────────────────────────────────────────────
def _draw_knight(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0, 0, 0, 55), (cx-18, size-12, 36, 10))
    # Legs
    pygame.draw.rect(s, (45, 60, 150), (cx-13, 40, 11, 16), border_radius=3)
    pygame.draw.rect(s, (45, 60, 150), (cx+2,  40, 11, 16), border_radius=3)
    pygame.draw.rect(s, (38, 28, 18),  (cx-14, 50, 13, 10), border_radius=2)
    pygame.draw.rect(s, (38, 28, 18),  (cx+1,  50, 13, 10), border_radius=2)
    # Body armor
    pygame.draw.rect(s, (70, 95, 190), (cx-15, 22, 30, 22), border_radius=5)
    pygame.draw.rect(s, (115, 148, 230), (cx-9, 24, 18, 12), border_radius=3)
    pygame.draw.rect(s, (45, 60, 150), (cx-15, 22, 30, 22), 2, border_radius=5)
    # Shield
    pts = [(cx-22,24),(cx-27,29),(cx-25,41),(cx-18,45),(cx-16,41),(cx-16,24)]
    pygame.draw.polygon(s, (210, 182, 45), pts)
    pygame.draw.polygon(s, (160, 135, 22), pts, 2)
    pygame.draw.line(s, (160, 135, 22), (cx-22, 24), (cx-19, 44), 1)
    pygame.draw.circle(s, (160, 135, 22), (cx-21, 34), 3)
    # Sword
    pygame.draw.rect(s, (195, 200, 215), (cx+19, 11, 5, 30))
    pygame.draw.rect(s, (145, 115, 42),  (cx+15, 27, 13, 5))
    pygame.draw.rect(s, (105, 78, 28),   (cx+17, 32, 9, 8))
    pygame.draw.rect(s, (185, 165, 60),  (cx+19, 39, 5, 4))
    pygame.draw.line(s, (230, 238, 255), (cx+21, 12), (cx+21, 26), 1)
    # Helmet
    pygame.draw.ellipse(s, (70, 95, 190), (cx-13, 5, 26, 22))
    pygame.draw.rect(s,  (22, 32, 80),   (cx-9, 14, 18, 8), border_radius=2)
    pygame.draw.line(s,  (14, 22, 60),   (cx-9, 18), (cx+9, 18), 1)
    pygame.draw.ellipse(s, (120, 155, 235), (cx-8, 7, 9, 6))
    pygame.draw.ellipse(s, (45, 60, 150), (cx-13, 5, 26, 22), 2)
    return s


def _draw_mage(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0, 0, 0, 55), (cx-16, size-12, 32, 10))
    # Robe
    robe = [(cx-14,22),(cx+14,22),(cx+18,58),(cx-18,58)]
    pygame.draw.polygon(s, (115, 42, 168), robe)
    pygame.draw.polygon(s, (145, 62, 198), [(cx-6,22),(cx+6,22),(cx+4,44),(cx-4,44)])
    pygame.draw.polygon(s, (88, 25, 132), robe, 2)
    pygame.draw.polygon(s, (205, 165, 52), [(cx-18,54),(cx+18,54),(cx+18,58),(cx-18,58)])
    # Staff
    pygame.draw.rect(s, (102, 72, 32), (cx+15, 8, 5, 50))
    pygame.draw.circle(s, (52, 205, 255), (cx+17, 8), 8)
    pygame.draw.circle(s, (155, 235, 255), (cx+15, 6), 4)
    pygame.draw.circle(s, (0, 155, 225), (cx+17, 8), 8, 2)
    # Face
    pygame.draw.ellipse(s, (242, 205, 162), (cx-10, 13, 20, 18))
    pygame.draw.circle(s, (82, 42, 125), (cx-4, 19), 3)
    pygame.draw.circle(s, (82, 42, 125), (cx+4, 19), 3)
    pygame.draw.circle(s, (205, 225, 255), (cx-3, 18), 1)
    pygame.draw.circle(s, (205, 225, 255), (cx+5, 18), 1)
    pygame.draw.arc(s, (160, 110, 80), (cx-5, 21, 10, 6), math.pi, 0, 2)
    # Hat
    hat = [(cx, 0), (cx-13, 15), (cx+13, 15)]
    pygame.draw.polygon(s, (115, 42, 168), hat)
    pygame.draw.polygon(s, (88, 25, 132), hat, 2)
    pygame.draw.ellipse(s, (135, 52, 185), (cx-16, 12, 32, 8))
    pygame.draw.ellipse(s, (88, 25, 132), (cx-16, 12, 32, 8), 2)
    pygame.draw.circle(s, YELLOW, (cx+3, 7), 3)
    pygame.draw.circle(s, WHITE,  (cx+3, 7), 1)
    return s


def _draw_rogue(size=64):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0, 0, 0, 55), (cx-15, size-12, 30, 10))
    # Legs
    pygame.draw.rect(s, (32, 26, 44), (cx-12, 40, 10, 18), border_radius=3)
    pygame.draw.rect(s, (32, 26, 44), (cx+2,  40, 10, 18), border_radius=3)
    pygame.draw.rect(s, (52, 36, 22), (cx-13, 50, 12, 10), border_radius=2)
    pygame.draw.rect(s, (52, 36, 22), (cx+1,  50, 12, 10), border_radius=2)
    # Body
    pygame.draw.rect(s, (42, 32, 58), (cx-13, 22, 26, 22), border_radius=4)
    pygame.draw.rect(s, (225, 122, 22), (cx-13, 30, 26, 5))
    pygame.draw.rect(s, (30, 22, 46), (cx-13, 22, 26, 22), 2, border_radius=4)
    # Left dagger
    pygame.draw.rect(s, (185, 190, 205), (cx-21, 26, 4, 18))
    pygame.draw.rect(s, (132, 102, 32),  (cx-23, 32, 8,  4))
    pygame.draw.rect(s, (102, 76, 26),   (cx-22, 36, 6,  6))
    pygame.draw.line(s, (222, 228, 242), (cx-20, 27), (cx-20, 33), 1)
    # Right dagger
    pygame.draw.rect(s, (185, 190, 205), (cx+17, 26, 4, 18))
    pygame.draw.rect(s, (132, 102, 32),  (cx+15, 32, 8,  4))
    pygame.draw.rect(s, (102, 76, 26),   (cx+16, 36, 6,  6))
    pygame.draw.line(s, (222, 228, 242), (cx+18, 27), (cx+18, 33), 1)
    # Face
    pygame.draw.ellipse(s, (202, 162, 122), (cx-9, 14, 18, 16))
    pygame.draw.circle(s, ORANGE, (cx-3, 20), 3)
    pygame.draw.circle(s, ORANGE, (cx+3, 20), 3)
    pygame.draw.circle(s, (255, 222, 152), (cx-2, 19), 1)
    pygame.draw.circle(s, (255, 222, 152), (cx+4, 19), 1)
    # Hood
    hood = [(cx-15,12),(cx,4),(cx+15,12),(cx+13,22),(cx-13,22)]
    pygame.draw.polygon(s, (52, 40, 72), hood)
    pygame.draw.polygon(s, (225, 122, 22), hood, 2)
    gs = pygame.Surface((22, 14), pygame.SRCALPHA)
    pygame.draw.ellipse(gs, (40, 30, 56, 115), (0, 0, 22, 14))
    s.blit(gs, (cx-11, 10))
    return s


def _draw_enemy_normal(size=36):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0, 0, 0, 50), (cx-12, size-8, 24, 7))
    pygame.draw.circle(s, (185, 42, 42), (cx, cx-2), 14)
    # Horns
    pygame.draw.polygon(s, (142, 25, 25), [(cx-10,11),(cx-15,2),(cx-6,9)])
    pygame.draw.polygon(s, (142, 25, 25), [(cx+10,11),(cx+15,2),(cx+6,9)])
    # Eyes
    pygame.draw.circle(s, YELLOW, (cx-5, cx-4), 4)
    pygame.draw.circle(s, YELLOW, (cx+5, cx-4), 4)
    pygame.draw.circle(s, (18,  8,  8), (cx-5, cx-4), 2)
    pygame.draw.circle(s, (18,  8,  8), (cx+5, cx-4), 2)
    pygame.draw.arc(s, (18, 8, 8), (cx-6, cx-1, 12, 8), math.pi, 0, 2)
    pygame.draw.circle(s, (142, 25, 25), (cx, cx-2), 14, 2)
    return s


def _draw_enemy_fast(size=28):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s, (0, 0, 0, 50), (cx-9, size-7, 18, 6))
    pygame.draw.circle(s, (235, 72, 72), (cx, cx-1), 10)
    pygame.draw.polygon(s, (200, 40, 40), [(cx-7,9),(cx-10,2),(cx-4,7)])
    pygame.draw.polygon(s, (200, 40, 40), [(cx+7,9),(cx+10,2),(cx+4,7)])
    pygame.draw.circle(s, YELLOW, (cx-3, cx-3), 3)
    pygame.draw.circle(s, YELLOW, (cx+3, cx-3), 3)
    pygame.draw.circle(s, (15, 6, 6), (cx-3, cx-3), 1)
    pygame.draw.circle(s, (15, 6, 6), (cx+3, cx-3), 1)
    pygame.draw.circle(s, (200, 40, 40), (cx, cx-1), 10, 2)
    return s


def _draw_boss(size=88):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    # Glow
    gs = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(gs, (155, 0, 205, 38), (cx, cx), cx-4)
    s.blit(gs, (0, 0))
    pygame.draw.ellipse(s, (0, 0, 0, 62), (cx-24, size-14, 48, 12))
    # Body
    pygame.draw.circle(s, (145, 32, 198), (cx, cx-2), 30)
    # Horns
    pygame.draw.polygon(s, (102, 15, 145), [(cx-19,21),(cx-30,2),(cx-11,17)])
    pygame.draw.polygon(s, (102, 15, 145), [(cx+19,21),(cx+30,2),(cx+11,17)])
    pygame.draw.polygon(s, (78,  8, 112), [(cx-19,21),(cx-30,2),(cx-11,17)], 2)
    pygame.draw.polygon(s, (78,  8, 112), [(cx+19,21),(cx+30,2),(cx+11,17)], 2)
    # Eyes
    pygame.draw.circle(s, RED, (cx-10, cx-6), 8)
    pygame.draw.circle(s, RED, (cx+10, cx-6), 8)
    pygame.draw.circle(s, (255, 52, 52), (cx-10, cx-6), 5)
    pygame.draw.circle(s, (255, 52, 52), (cx+10, cx-6), 5)
    pygame.draw.circle(s, (18,  8,  8), (cx-10, cx-6), 2)
    pygame.draw.circle(s, (18,  8,  8), (cx+10, cx-6), 2)
    # Mouth
    pygame.draw.arc(s, (48, 5, 68), (cx-16, cx-3, 32, 18), math.pi, 0, 4)
    pygame.draw.polygon(s, WHITE, [(cx-9,cx+2),(cx-7,cx+12),(cx-5,cx+2)])
    pygame.draw.polygon(s, WHITE, [(cx+5,cx+2),(cx+7,cx+12),(cx+9,cx+2)])
    pygame.draw.circle(s, (82, 10, 122), (cx, cx-2), 30, 3)
    return s


def build_sprites():
    return {
        "knight":       _draw_knight(64),
        "mage":         _draw_mage(64),
        "rogue":        _draw_rogue(64),
        "enemy_normal": _draw_enemy_normal(36),
        "enemy_fast":   _draw_enemy_fast(28),
        "boss":         _draw_boss(88),
    }


# ─────────────────────────────────────────────
# Sound Manager
# ─────────────────────────────────────────────
def _sine_buf(freq, dur, vol=0.3, rate=44100):
    n = int(rate * dur)
    period = max(1, int(rate / max(freq, 1)))
    one = [math.sin(2 * math.pi * i / period) * vol for i in range(period)]
    tiled = (one * (n // period + 2))[:n]
    fade  = min(int(0.02 * rate), n // 4)
    buf   = arr.array('h', [0] * n * 2)
    for i, v in enumerate(tiled):
        s = int(v * 32767)
        if i < fade:       s = int(s * i / fade)
        if i >= n - fade:  s = int(s * (n - i) / max(fade, 1))
        buf[i*2] = s;  buf[i*2+1] = s
    return buf

def _sweep_buf(f1, f2, dur, vol=0.3, rate=44100):
    n = int(rate * dur)
    fade  = min(int(0.02 * rate), n // 4)
    buf   = arr.array('h', [0] * n * 2)
    phase = 0.0
    for i in range(n):
        phase += 2 * math.pi * (f1 + (f2 - f1) * i / n) / rate
        s = int(math.sin(phase) * 32767 * vol)
        if i < fade:       s = int(s * i / fade)
        if i >= n - fade:  s = int(s * (n - i) / max(fade, 1))
        buf[i*2] = s;  buf[i*2+1] = s
    return buf

def _chord_buf(freqs, dur, vol=0.25, rate=44100):
    n  = int(rate * dur)
    pv = vol / len(freqs)
    fade   = min(int(0.05 * rate), n // 4)
    buf    = arr.array('h', [0] * n * 2)
    phases = [0.0] * len(freqs)
    for i in range(n):
        s = 0
        for j, f in enumerate(freqs):
            phases[j] += 2 * math.pi * f / rate
            s += math.sin(phases[j]) * 32767 * pv
        s = int(max(-32767, min(32767, s)))
        if i < fade:       s = int(s * i / fade)
        if i >= n - fade:  s = int(s * (n - i) / max(fade, 1))
        buf[i*2] = s;  buf[i*2+1] = s
    return buf

def _noise_buf(dur, vol=0.18, rate=44100):
    n    = int(rate * dur)
    fade = min(int(0.01 * rate), n // 4)
    buf  = arr.array('h', [0] * n * 2)
    for i in range(n):
        s = int((random.random() * 2 - 1) * 32767 * vol)
        if i < fade:       s = int(s * i / fade)
        if i >= n - fade:  s = int(s * (n - i) / max(fade, 1))
        buf[i*2] = s;  buf[i*2+1] = s
    return buf

def _bgm_buf(rate=44100):
    bar_dur = 1.6
    bars = [(110.00,220.00,329.63),(87.31,174.61,261.63),
            (130.81,261.63,392.00),(98.00,196.00,293.66)]
    total = int(rate * bar_dur * len(bars))
    buf   = arr.array('h', [0] * total * 2)
    idx   = 0
    for bass, mid, top in bars:
        seg = int(rate * bar_dur)
        phases = [0.0, 0.0, 0.0]
        freqs  = [bass, mid, top]
        vols   = [0.14, 0.08, 0.04]
        fade   = int(0.04 * rate)
        for i in range(seg):
            s = 0
            for j in range(3):
                phases[j] += 2 * math.pi * freqs[j] / rate
                s += math.sin(phases[j]) * 32767 * vols[j]
            s = int(max(-32767, min(32767, s)))
            if i < fade:        s = int(s * i / fade)
            if i >= seg - fade: s = int(s * (seg - i) / max(fade, 1))
            buf[(idx+i)*2]   = s
            buf[(idx+i)*2+1] = s
        idx += seg
    return buf

class SoundManager:
    def __init__(self):
        self.muted = False
        self.sfx   = {}
        self._build()

    def _build(self):
        self.sfx["shoot"]     = pygame.mixer.Sound(buffer=_sine_buf(700, 0.05, 0.18))
        self.sfx["axe"]       = pygame.mixer.Sound(buffer=_sweep_buf(500, 250, 0.12, 0.25))
        self.sfx["lightning"] = pygame.mixer.Sound(buffer=_sweep_buf(1400, 600, 0.08, 0.28))
        self.sfx["flame"]     = pygame.mixer.Sound(buffer=_noise_buf(0.18, 0.22))
        self.sfx["hit"]       = pygame.mixer.Sound(buffer=_sine_buf(380, 0.07, 0.2))
        self.sfx["kill"]      = pygame.mixer.Sound(buffer=_sweep_buf(500, 150, 0.14, 0.25))
        self.sfx["levelup"]   = pygame.mixer.Sound(buffer=_chord_buf([523,659,784,1046], 0.45, 0.22))
        self.sfx["boss"]      = pygame.mixer.Sound(buffer=_chord_buf([60, 80, 55], 0.7, 0.3))
        self.sfx["chest"]     = pygame.mixer.Sound(buffer=_chord_buf([523,659,784], 0.3, 0.2))
        self.sfx["hurt"]      = pygame.mixer.Sound(buffer=_sweep_buf(300, 150, 0.09, 0.35))
        self.sfx["cross"]     = pygame.mixer.Sound(buffer=_chord_buf([400, 600], 0.1, 0.2))
        bgm = pygame.mixer.Sound(buffer=_bgm_buf())
        bgm.set_volume(0.4)
        self.sfx["bgm"] = bgm

    def play(self, name):
        if not self.muted and name in self.sfx:
            self.sfx[name].play()

    def start_bgm(self):
        if not self.muted:
            self.sfx["bgm"].play(loops=-1)

    def stop_bgm(self):
        self.sfx["bgm"].stop()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            pygame.mixer.pause()
        else:
            pygame.mixer.unpause()
            self.sfx["bgm"].play(loops=-1)


# ─────────────────────────────────────────────
# Particles / Screen shake
# ─────────────────────────────────────────────
class Particle:
    __slots__ = ("x","y","vx","vy","life","max_life","color","r","alive")
    def __init__(self, x, y, color):
        a = random.uniform(0, math.pi * 2)
        v = random.uniform(60, 200)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a)*v, math.sin(a)*v
        self.life = self.max_life = random.uniform(0.3, 0.7)
        self.color = color
        self.r     = random.randint(3, 7)
        self.alive = True

    def update(self, dt):
        self.x += self.vx * dt;  self.vx *= 0.92
        self.y += self.vy * dt;  self.vy *= 0.92
        self.life -= dt
        if self.life <= 0: self.alive = False

    def draw(self, surf, ox, oy):
        alpha = int(255 * self.life / self.max_life)
        sx = int(self.x - ox + W//2)
        sy = int(self.y - oy + H//2)
        s = pygame.Surface((self.r*2, self.r*2), pygame.SRCALPHA)
        r, g, b = self.color
        pygame.draw.circle(s, (r, g, b, alpha), (self.r, self.r), self.r)
        surf.blit(s, (sx-self.r, sy-self.r))


class ScreenShake:
    def __init__(self):
        self.timer = 0.0; self.strength = 0.0

    def shake(self, strength, duration=0.25):
        self.strength = max(self.strength, strength)
        self.timer    = max(self.timer, duration)

    def update(self, dt):
        self.timer = max(0, self.timer - dt)
        if self.timer > 0:
            s = self.strength * (self.timer / 0.25)
            return random.randint(-int(s), int(s)), random.randint(-int(s), int(s))
        self.strength = 0
        return 0, 0


# ─────────────────────────────────────────────
# Projectiles / Zones / Aura
# ─────────────────────────────────────────────
class Bullet:
    __slots__ = ("x","y","dx","dy","speed","damage","radius","color","life","pierce","hit_ids","alive")
    def __init__(self, x, y, dx, dy, speed, damage, radius, color, lifetime=2.0, pierce=1):
        self.x, self.y   = x, y
        self.dx, self.dy = dx, dy
        self.speed = speed; self.damage = damage; self.radius = radius
        self.color = color; self.life = lifetime; self.pierce = pierce
        self.hit_ids = set(); self.alive = True

    def update(self, dt):
        self.x += self.dx * self.speed * dt
        self.y += self.dy * self.speed * dt
        self.life -= dt
        if self.life <= 0: self.alive = False

    def draw(self, surf, ox, oy):
        pygame.draw.circle(surf, self.color,
                           (int(self.x-ox+W//2), int(self.y-oy+H//2)), self.radius)


class FlameZone:
    def __init__(self, x, y, radius, damage, lifetime):
        self.x, self.y = x, y
        self.radius = radius; self.damage = damage
        self.life = self.max_life = lifetime
        self.hit_ids = set(); self.tick = 0.3; self.timer = 0.0; self.alive = True

    def update(self, dt, enemies, floats):
        self.life -= dt
        if self.life <= 0: self.alive = False; return
        self.timer += dt
        if self.timer >= self.tick:
            self.timer = 0.0; self.hit_ids.clear()
        for e in enemies:
            if id(e) in self.hit_ids: continue
            if dist((self.x,self.y),(e.x,e.y)) < self.radius + e.radius:
                e.hp -= self.damage; e.hit_flash = 0.1
                self.hit_ids.add(id(e))
                floats.append(FloatText(e.x, e.y-20, str(int(self.damage)), ORANGE, 0.5))

    def draw(self, surf, ox, oy):
        alpha = int(180 * self.life / self.max_life)
        r  = self.radius
        sx = int(self.x - ox + W//2); sy = int(self.y - oy + H//2)
        s  = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 100, 0, alpha), (r, r), r)
        pygame.draw.circle(s, (255, 200, 0, alpha//2), (r, r), r//2)
        surf.blit(s, (sx-r, sy-r))


class LightningBolt:
    def __init__(self, pts, life=0.12):
        self.pts = pts; self.life = life; self.alive = True
    def update(self, dt):
        self.life -= dt
        if self.life <= 0: self.alive = False
    def draw(self, surf, ox, oy):
        for i in range(len(self.pts)-1):
            ax = int(self.pts[i][0]   - ox + W//2); ay = int(self.pts[i][1]   - oy + H//2)
            bx = int(self.pts[i+1][0] - ox + W//2); by = int(self.pts[i+1][1] - oy + H//2)
            pygame.draw.line(surf, CYAN,  (ax,ay),(bx,by), 3)
            pygame.draw.line(surf, WHITE, (ax,ay),(bx,by), 1)


class Aura:
    def __init__(self, player):
        self.player = player; self.radius = 80; self.damage = 8
        self.tick = 0.5; self.timer = 0.0; self.hit_ids = set()
    def update(self, dt, enemies):
        self.timer += dt
        if self.timer >= self.tick: self.timer = 0.0; self.hit_ids.clear()
        for e in enemies:
            if id(e) in self.hit_ids: continue
            if dist((self.player.x,self.player.y),(e.x,e.y)) <= self.radius + e.radius:
                e.hp -= self.damage; self.hit_ids.add(id(e))
    def draw(self, surf, ox, oy):
        r  = self.radius
        sx = int(self.player.x - ox + W//2); sy = int(self.player.y - oy + H//2)
        s  = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (200, 50, 50, 52), (r, r), r)
        surf.blit(s, (sx-r, sy-r))


# ─────────────────────────────────────────────
# Gem / Chest
# ─────────────────────────────────────────────
class Gem:
    def __init__(self, x, y, value=5):
        self.x, self.y = x, y; self.value = value; self.radius = 6; self.alive = True
    def draw(self, surf, ox, oy):
        sx = int(self.x-ox+W//2); sy = int(self.y-oy+H//2)
        pygame.draw.circle(surf, CYAN,  (sx,sy), self.radius)
        pygame.draw.circle(surf, WHITE, (sx,sy), self.radius, 1)


CHEST_REWARDS = [
    {"name":"HP Restore", "desc":"+60 HP",            "key":"hp"},
    {"name":"Wand Lv+",   "desc":"Magic bolt enhanced","key":"wand"},
    {"name":"Axe",        "desc":"Axe enhanced",       "key":"axe"},
    {"name":"Lightning",  "desc":"Lightning enhanced", "key":"lightning"},
    {"name":"Flame",      "desc":"Flame enhanced",     "key":"flame"},
    {"name":"XP Burst",   "desc":"+50 XP",             "key":"xp"},
]

class Chest:
    def __init__(self, x, y):
        self.x, self.y = x, y; self.radius = 18; self.alive = True
        self.bob = random.uniform(0, math.pi*2); self.reward = random.choice(CHEST_REWARDS)
    def update(self, dt): self.bob += dt * 2
    def draw(self, surf, ox, oy):
        bob = math.sin(self.bob) * 4
        sx = int(self.x-ox+W//2); sy = int(self.y-oy+H//2+bob)
        r = pygame.Rect(sx-14, sy-10, 28, 20)
        pygame.draw.rect(surf, GOLD,   r, border_radius=3)
        pygame.draw.rect(surf, ORANGE, r, 2, border_radius=3)
        pygame.draw.rect(surf, (200,160,0), (sx-14,sy-14,28,8), border_radius=3)
        pygame.draw.rect(surf, ORANGE, (sx-14,sy-14,28,8), 2, border_radius=3)
        pygame.draw.circle(surf, BLACK, (sx,sy-2), 3)
        gs = pygame.Surface((60,60), pygame.SRCALPHA)
        pygame.draw.circle(gs, (255,200,0,38), (30,30), 30)
        surf.blit(gs, (sx-30,sy-30))


# ─────────────────────────────────────────────
# Float text
# ─────────────────────────────────────────────
class FloatText:
    def __init__(self, x, y, text, color, life=1.0):
        self.x, self.y = x, y; self.text = text; self.color = color
        self.life = self.max_life = life; self.alive = True
    def update(self, dt):
        self.y -= 40 * dt; self.life -= dt
        if self.life <= 0: self.alive = False
    def draw(self, surf, ox, oy):
        alpha = int(255 * self.life / self.max_life)
        s = font_small.render(self.text, True, self.color); s.set_alpha(alpha)
        surf.blit(s, (int(self.x-ox+W//2), int(self.y-oy+H//2)))


# ─────────────────────────────────────────────
# Enemy / Boss
# ─────────────────────────────────────────────
class Enemy:
    def __init__(self, x, y, hp, speed, damage, radius, color, xp, sprite_key="enemy_normal"):
        self.x, self.y = x, y; self.hp = self.max_hp = hp; self.speed = speed
        self.damage = damage; self.radius = radius; self.color = color; self.xp = xp
        self.alive = True; self.hit_flash = 0.0; self.sprite_key = sprite_key

    def update(self, dt, px, py, _b=None, _f=None):
        dx, dy = norm(px-self.x, py-self.y)
        self.x += dx*self.speed*dt; self.y += dy*self.speed*dt
        if self.hit_flash > 0: self.hit_flash -= dt

    def draw(self, surf, ox, oy, sprites):
        sx = int(self.x-ox+W//2); sy = int(self.y-oy+H//2)
        spr = sprites.get(self.sprite_key)
        if spr:
            if self.hit_flash > 0:
                ws = spr.copy()
                ws.fill((255,255,255,160), special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws, (sx - spr.get_width()//2, sy - spr.get_height()//2))
            else:
                surf.blit(spr, (sx - spr.get_width()//2, sy - spr.get_height()//2))
        else:
            pygame.draw.circle(surf, self.color, (sx, sy), self.radius)
        # HP bar
        bw = self.radius * 2
        ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surf, GRAY,  (sx-self.radius, sy-self.radius-8, bw, 5))
        pygame.draw.rect(surf, GREEN, (sx-self.radius, sy-self.radius-8, int(bw*ratio), 5))


class Boss(Enemy):
    CHARGE_INTERVAL = 5.0
    def __init__(self, x, y, level):
        hp = 800 + level*300; spd = 70 + level*10
        super().__init__(x, y, hp=hp, speed=spd, damage=25,
                         radius=36, color=PURPLE, xp=80+level*20, sprite_key="boss")
        self.level = level; self.base_speed = spd
        self.charge_timer = self.CHARGE_INTERVAL
        self.charge_dir = (0.0, 0.0); self.charging = False
        self.charge_time = 0.0; self.telegraph = 0.0
        self.name = f"BOSS Lv{level}"

    def update(self, dt, px, py, _b=None, _f=None):
        if self.hit_flash > 0: self.hit_flash -= dt
        if self.telegraph > 0:
            self.telegraph -= dt
            if self.telegraph <= 0:
                self.charging = True; self.charge_time = 0.8
            return
        if self.charging:
            self.charge_time -= dt
            self.x += self.charge_dir[0]*420*dt; self.y += self.charge_dir[1]*420*dt
            if self.charge_time <= 0: self.charging = False
            return
        dx, dy = norm(px-self.x, py-self.y)
        self.x += dx*self.speed*dt; self.y += dy*self.speed*dt
        self.charge_timer -= dt
        if self.charge_timer <= 0:
            self.charge_timer = self.CHARGE_INTERVAL
            self.charge_dir   = norm(px-self.x, py-self.y)
            self.telegraph    = 0.6

    def draw(self, surf, ox, oy, sprites):
        sx = int(self.x-ox+W//2); sy = int(self.y-oy+H//2)
        if self.telegraph > 0:
            pulse = abs(math.sin(self.telegraph*20))*22
            r = 36 + int(pulse)
            s = pygame.Surface((r*2,r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (255,50,50,115), (r,r), r)
            surf.blit(s, (sx-r, sy-r))
        spr = sprites.get("boss")
        if spr:
            if self.hit_flash > 0:
                ws = spr.copy()
                ws.fill((255,255,255,160), special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws, (sx-spr.get_width()//2, sy-spr.get_height()//2))
            else:
                surf.blit(spr, (sx-spr.get_width()//2, sy-spr.get_height()//2))
        else:
            pygame.draw.circle(surf, PURPLE, (sx,sy), self.radius)
        bw = 100; ratio = max(0, self.hp/self.max_hp)
        pygame.draw.rect(surf, GRAY, (sx-50, sy-self.radius-14, bw, 8))
        pygame.draw.rect(surf, RED,  (sx-50, sy-self.radius-14, int(bw*ratio), 8))
        lbl = font_small.render(self.name, True, YELLOW)
        surf.blit(lbl, (sx-lbl.get_width()//2, sy-self.radius-28))


# ─────────────────────────────────────────────
# Character data
# ─────────────────────────────────────────────
CHARACTERS = [
    {"name":"Knight","desc":["High HP & defense","Starts with Axe"],
     "color":BLUE,  "hp":200,"speed":175,"sprite":"knight",
     "weapons":{"wand":0,"axe":1,"cross":0,"garlic":0,"lightning":0,"flame":0},"wand_cd":0.8},
    {"name":"Mage",  "desc":["Fast magic attack","Starts with Wand Lv2"],
     "color":PURPLE,"hp":90, "speed":230,"sprite":"mage",
     "weapons":{"wand":2,"axe":0,"cross":0,"garlic":0,"lightning":0,"flame":0},"wand_cd":0.38},
    {"name":"Rogue", "desc":["Very fast & agile","Starts with Holy Cross"],
     "color":ORANGE,"hp":110,"speed":290,"sprite":"rogue",
     "weapons":{"wand":0,"axe":0,"cross":1,"garlic":0,"lightning":0,"flame":0},"wand_cd":0.8},
]


# ─────────────────────────────────────────────
# Player
# ─────────────────────────────────────────────
class Player:
    PICKUP_RANGE = 120

    def __init__(self, char_data, sprites):
        self.x = self.y = 0.0
        self.max_hp = char_data["hp"]; self.hp = self.max_hp
        self.speed  = char_data["speed"]; self.char_color = char_data["color"]
        self.radius = 16; self.alive = True
        self.hurt_sound_cd = 0.0          # prevents sound spam
        self.sprite = sprites.get(char_data["sprite"])
        self.weapons = {
            "wand":      {"level":char_data["weapons"]["wand"],     "timer":0.0,"cooldown":char_data["wand_cd"]},
            "axe":       {"level":char_data["weapons"]["axe"],      "timer":0.0,"cooldown":1.5},
            "cross":     {"level":char_data["weapons"]["cross"],    "timer":0.0,"cooldown":3.0},
            "garlic":    {"level":char_data["weapons"]["garlic"]},
            "lightning": {"level":char_data["weapons"]["lightning"],"timer":0.0,"cooldown":2.0},
            "flame":     {"level":char_data["weapons"]["flame"],    "timer":0.0,"cooldown":4.0},
        }
        self.aura = None

    def update(self, dt, keys, enemies, bullets, floats, flames, bolts, snd, shake):
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1
        ndx, ndy = norm(dx, dy)
        self.x += ndx*self.speed*dt; self.y += ndy*self.speed*dt
        self.hurt_sound_cd = max(0, self.hurt_sound_cd - dt)

        target = min(enemies, key=lambda e: dist((self.x,self.y),(e.x,e.y)), default=None)

        # ── Wand ──
        w = self.weapons["wand"]
        if w["level"] >= 1:
            w["timer"] += dt
            if w["timer"] >= w["cooldown"] and target:
                w["timer"] = 0.0
                count = 1 + (w["level"]-1)//2
                base  = math.atan2(target.y-self.y, target.x-self.x)
                sp    = math.radians(12)
                for i in range(count):
                    a = base + sp*(i-(count-1)/2)
                    bullets.append(Bullet(self.x,self.y,math.cos(a),math.sin(a),
                        420, 20+w["level"]*5, 6, BLUE, 1.5, 1+w["level"]//3))
                snd.play("shoot")

        # ── Axe ──
        w = self.weapons["axe"]
        if w["level"] >= 1:
            w["timer"] += dt
            if w["timer"] >= w["cooldown"]:
                w["timer"] = 0.0
                for i in range(w["level"]):
                    a = math.radians(-70+i*20)
                    bullets.append(Bullet(self.x,self.y,math.cos(a),math.sin(a),
                        360, 40+w["level"]*10, 10, ORANGE, 0.75, 99))
                snd.play("axe")

        # ── Cross ──
        w = self.weapons["cross"]
        if w["level"] >= 1:
            w["timer"] += dt
            if w["timer"] >= w["cooldown"]:
                w["timer"] = 0.0
                for ddx,ddy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    bullets.append(Bullet(self.x,self.y,ddx,ddy,
                        300, 30+w["level"]*8, 8, YELLOW, 2.0, 3+w["level"]))
                snd.play("cross")

        # ── Garlic ──
        if self.weapons["garlic"]["level"] >= 1 and self.aura is None:
            self.aura = Aura(self)
        if self.aura:
            self.aura.radius = 80 + self.weapons["garlic"]["level"]*20
            self.aura.damage = 5  + self.weapons["garlic"]["level"]*3
            self.aura.update(dt, enemies)

        # ── Lightning ──
        w = self.weapons["lightning"]
        if w["level"] >= 1:
            w["timer"] += dt
            if w["timer"] >= w["cooldown"] and target:
                w["timer"] = 0.0
                dmg = 55 + w["level"]*15; chains = 1 + w["level"]
                target.hp -= dmg; target.hit_flash = 0.1
                floats.append(FloatText(target.x, target.y-20, str(dmg), CYAN, 0.6))
                pts = [(self.x,self.y),(target.x,target.y)]
                prev = target; hit = [target]
                for _ in range(chains-1):
                    nearby = sorted([e for e in enemies if e not in hit],
                                    key=lambda e: dist((prev.x,prev.y),(e.x,e.y)))
                    if not nearby or dist((prev.x,prev.y),(nearby[0].x,nearby[0].y)) > 350:
                        break
                    nxt = nearby[0]; nxt.hp -= int(dmg*0.6); nxt.hit_flash = 0.1
                    floats.append(FloatText(nxt.x,nxt.y-20,str(int(dmg*0.6)),CYAN,0.5))
                    pts.append((nxt.x,nxt.y)); hit.append(nxt); prev = nxt
                bolts.append(LightningBolt(pts)); snd.play("lightning"); shake.shake(4)

        # ── Flame ──
        w = self.weapons["flame"]
        if w["level"] >= 1:
            w["timer"] += dt
            if w["timer"] >= w["cooldown"]:
                w["timer"] = 0.0
                flames.append(FlameZone(self.x,self.y, 70+w["level"]*20, 12+w["level"]*6, 3.0))
                snd.play("flame")

        # ── Contact damage (continuous, no invincibility) ──
        for e in enemies:
            if dist((self.x,self.y),(e.x,e.y)) < self.radius + e.radius:
                self.hp -= e.damage * dt          # DPS-style, no invincibility
                if self.hurt_sound_cd <= 0:
                    snd.play("hurt")
                    self.hurt_sound_cd = 0.5
        if self.hp <= 0:
            self.alive = False

    def draw(self, surf, ox, oy):
        sx = int(self.x-ox+W//2); sy = int(self.y-oy+H//2)
        if self.sprite:
            surf.blit(self.sprite, (sx-self.sprite.get_width()//2, sy-self.sprite.get_height()//2))
        else:
            pygame.draw.circle(surf, self.char_color, (sx,sy), self.radius)
        # HP bar
        bw = 80; ratio = max(0, self.hp/self.max_hp)
        pygame.draw.rect(surf, GRAY, (sx-40, sy-self.radius-14, bw, 8))
        pygame.draw.rect(surf, RED,  (sx-40, sy-self.radius-14, int(bw*ratio), 8))
        if self.aura: self.aura.draw(surf, ox, oy)


# ─────────────────────────────────────────────
# Upgrade system
# ─────────────────────────────────────────────
UPGRADES = [
    {"name":"Wand Lv+",   "desc":"Faster, stronger magic bolt",  "key":"wand"},
    {"name":"Axe",        "desc":"Cleaving axe through enemies", "key":"axe"},
    {"name":"Holy Cross", "desc":"Cross fires in 4 directions",  "key":"cross"},
    {"name":"Garlic",     "desc":"Damage aura around you",       "key":"garlic"},
    {"name":"Lightning",  "desc":"Chain lightning strikes",      "key":"lightning"},
    {"name":"Flame",      "desc":"Burning fire zone",            "key":"flame"},
    {"name":"Speed Up",   "desc":"Move 15% faster",              "key":"speed"},
    {"name":"Max HP Up",  "desc":"Max HP +30, restore 30",       "key":"maxhp"},
]

def pick_upgrades(player, n=3):
    pool = [u for u in UPGRADES
            if not (u["key"]=="wand" and player.weapons["wand"]["level"]>=8)]
    random.shuffle(pool); return pool[:n]

def apply_upgrade(player, key):
    if key in ("wand","axe","cross","garlic","lightning","flame"):
        w = player.weapons[key]; w["level"] = w.get("level",0)+1
        if key=="wand":      w["cooldown"] = max(0.2,  0.8  - w["level"]*0.07)
        if key=="axe":       w["cooldown"] = max(0.5,  1.5  - w["level"]*0.10)
        if key=="lightning": w["cooldown"] = max(0.6,  2.0  - w["level"]*0.15)
        if key=="flame":     w["cooldown"] = max(1.5,  4.0  - w["level"]*0.30)
    elif key=="speed": player.speed *= 1.15
    elif key=="maxhp": player.max_hp += 30; player.hp = min(player.hp+30, player.max_hp)

def apply_chest_reward(player, key):
    if key=="hp":  player.hp = min(player.max_hp, player.hp+60)
    elif key=="xp": return 50
    elif key in ("wand","axe","lightning","flame"): apply_upgrade(player, key)
    return 0


# ─────────────────────────────────────────────
# Spawn helpers
# ─────────────────────────────────────────────
def spawn_enemy(px, py, elapsed):
    a = random.uniform(0, math.pi*2); r = 700
    x = px + math.cos(a)*r; y = py + math.sin(a)*r
    diff = min(elapsed/60, 5)
    if random.random() < 0.18:
        return Enemy(x,y, hp=28+diff*8,  speed=175+diff*22, damage=8,
                     radius=10, color=(255,72,72), xp=3, sprite_key="enemy_fast")
    return Enemy(x,y, hp=60+diff*25, speed=90+diff*10,  damage=15,
                 radius=14, color=RED, xp=5, sprite_key="enemy_normal")

def maybe_spawn(px, py, elapsed, since_last, enemies):
    rate = max(0.3, 1.5 - elapsed/120)
    if since_last >= rate:
        for _ in range(min(1+int(elapsed//30), 6)):
            enemies.append(spawn_enemy(px, py, elapsed))
        return 0.0
    return since_last

def spawn_boss(px, py, level):
    a = random.uniform(0, math.pi*2)
    return Boss(px+math.cos(a)*700, py+math.sin(a)*700, level)


# ─────────────────────────────────────────────
# HUD
# ─────────────────────────────────────────────
def draw_hud(surf, player, level, xp, xp_next, elapsed, kills, boss_warn):
    ratio = xp / xp_next
    pygame.draw.rect(surf, GRAY, (0, H-18, W, 18))
    pygame.draw.rect(surf, CYAN, (0, H-18, int(W*ratio), 18))
    surf.blit(font_small.render(f"LV {level}  XP {xp}/{xp_next}", True, WHITE), (6, H-16))
    m, s = divmod(int(elapsed), 60)
    t = font_med.render(f"{m:02d}:{s:02d}", True, WHITE)
    surf.blit(t, (W//2-t.get_width()//2, 8))
    surf.blit(font_small.render(f"Kills: {kills}", True, WHITE), (W-90, 8))
    surf.blit(font_tiny.render("M: mute/unmute", True, GRAY), (W-130, H-36))
    WCOLORS = {"wand":BLUE,"axe":ORANGE,"cross":YELLOW,"garlic":RED,"lightning":CYAN,"flame":ORANGE}
    wx = 10
    for name, w in player.weapons.items():
        lv = w.get("level",0)
        if lv == 0: continue
        s2 = font_small.render(f"{name[:3].upper()} {lv}", True, WCOLORS.get(name,WHITE))
        surf.blit(s2, (wx, 10)); wx += s2.get_width()+12
    if boss_warn > 0:
        alpha = int(255 * min(1, boss_warn * 4))
        pulse = abs(math.sin(pygame.time.get_ticks()/120))*60
        warn  = font_large.render("BOSS INCOMING!", True, (255, int(50+pulse), int(50+pulse)))
        warn.set_alpha(alpha)
        surf.blit(warn, (W//2-warn.get_width()//2, H//2-60))


# ─────────────────────────────────────────────
# Level-up screen
# ─────────────────────────────────────────────
def levelup_screen(surf, options):
    overlay = pygame.Surface((W,H), pygame.SRCALPHA); overlay.fill((0,0,0,170))
    surf.blit(overlay, (0,0))
    surf.blit(font_large.render("LEVEL UP!", True, YELLOW), (W//2-130, 100))
    surf.blit(font_med.render("Choose an upgrade  (1 / 2 / 3  or click)", True, WHITE),
              (W//2-230, 168))
    cw, ch = 320, 120
    total_w = len(options)*cw+(len(options)-1)*20
    sx0 = W//2-total_w//2
    mx, my = pygame.mouse.get_pos()
    rects = []
    WCOLORS2 = {"wand":BLUE,"axe":ORANGE,"cross":YELLOW,"garlic":RED,
                "lightning":CYAN,"flame":ORANGE,"speed":LIME,"maxhp":RED}
    for i, opt in enumerate(options):
        rx = sx0+i*(cw+20); ry = 240
        rect = pygame.Rect(rx,ry,cw,ch); rects.append(rect)
        hover = rect.collidepoint(mx,my)
        pygame.draw.rect(surf, (55,55,82) if hover else (35,35,55), rect, border_radius=12)
        pygame.draw.rect(surf, YELLOW, rect, 2, border_radius=12)
        surf.blit(font_med.render(f"[{i+1}] {opt['name']}", True, WHITE), (rx+12,ry+20))
        surf.blit(font_small.render(opt["desc"], True, GRAY), (rx+12,ry+62))
        pygame.draw.circle(surf, WCOLORS2.get(opt["key"],WHITE), (rx+cw-24,ry+24), 10)
    return rects


# ─────────────────────────────────────────────
# Character select
# ─────────────────────────────────────────────
def character_select(surf, sprites):
    selected = None
    char_rects = []
    while selected is None:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1,pygame.K_KP1): selected = 0
                if event.key in (pygame.K_2,pygame.K_KP2): selected = 1
                if event.key in (pygame.K_3,pygame.K_KP3): selected = 2
                if event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                for i, rect in enumerate(char_rects):
                    if rect.collidepoint(mx,my): selected = i

        surf.fill(DARK)
        for gx in range(0,W,80): pygame.draw.line(surf,(30,30,45),(gx,0),(gx,H))
        for gy in range(0,H,80): pygame.draw.line(surf,(30,30,45),(0,gy),(W,gy))
        surf.blit(font_large.render("SELECT CHARACTER", True, YELLOW),
                  (W//2-200, 55))
        surf.blit(font_med.render("Press 1 / 2 / 3  or click", True, GRAY),
                  (W//2-148, 135))
        mx, my = pygame.mouse.get_pos()
        cw, ch2 = 310, 290
        total_w = len(CHARACTERS)*cw+(len(CHARACTERS)-1)*30
        sx0 = W//2-total_w//2
        char_rects = []
        for i, cd in enumerate(CHARACTERS):
            rx = sx0+i*(cw+30); ry = 190
            rect = pygame.Rect(rx,ry,cw,ch2); char_rects.append(rect)
            hover = rect.collidepoint(mx,my)
            pygame.draw.rect(surf, (55,55,80) if hover else (35,35,55), rect, border_radius=14)
            pygame.draw.rect(surf, cd["color"], rect, 3, border_radius=14)
            surf.blit(font_large.render(str(i+1), True, cd["color"]), (rx+14,ry+12))
            # Sprite preview
            spr = sprites.get(cd["sprite"])
            if spr:
                scaled = pygame.transform.scale(spr, (96, 96))
                surf.blit(scaled, (rx+cw//2-48, ry+50))
            else:
                pygame.draw.circle(surf, cd["color"], (rx+cw//2, ry+98), 36)
            nm = font_med.render(cd["name"], True, WHITE)
            surf.blit(nm, (rx+cw//2-nm.get_width()//2, ry+155))
            for j, st in enumerate([f"HP: {cd['hp']}", f"SPD: {cd['speed']}"]):
                surf.blit(font_small.render(st, True, GRAY), (rx+20, ry+190+j*22))
            for j, line in enumerate(cd["desc"]):
                surf.blit(font_tiny.render(line, True, cd["color"]), (rx+20, ry+248+j*18))
        pygame.display.flip()
    return CHARACTERS[selected]


# ─────────────────────────────────────────────
# Game over
# ─────────────────────────────────────────────
def game_over_screen(surf, elapsed, kills, victory):
    surf.fill(DARK)
    color = YELLOW if victory else RED
    surf.blit(font_large.render("YOU SURVIVED!" if victory else "GAME OVER", True, color),
              (W//2-200, 190))
    m, s = divmod(int(elapsed), 60)
    for i, line in enumerate([f"Time: {m:02d}:{s:02d}", f"Kills: {kills}", "",
                               "ENTER: play again    ESC: quit"]):
        t = font_med.render(line, True, WHITE)
        surf.blit(t, (W//2-t.get_width()//2, 300+i*44))


def draw_bg(surf, ox, oy):
    surf.fill(DARK)
    grid = 80
    for gx in range(-1, W//grid+2):
        pygame.draw.line(surf,(32,32,48),(gx*grid-ox%grid,0),(gx*grid-ox%grid,H))
    for gy in range(-1, H//grid+2):
        pygame.draw.line(surf,(32,32,48),(0,gy*grid-oy%grid),(W,gy*grid-oy%grid))


# ─────────────────────────────────────────────
# Main game loop
# ─────────────────────────────────────────────
def run_game(snd, sprites, char_data):
    player    = Player(char_data, sprites)
    bullets=[]; enemies=[]; gems=[]; floats=[]; particles=[]; flames=[]; bolts=[]; chests=[]
    level=1; xp=0; xp_next=20
    elapsed=0.0; since_spawn=0.0; since_chest=40.0
    boss_timer=120.0; boss_level=1; boss_warn=0.0; kills=0
    VICTORY_TIME = 600
    shake = ScreenShake()
    state="play"; levelup_opts=[]; levelup_rects=[]; victory=False

    snd.start_bgm()
    while True:
        dt = min(clock.tick(60)/1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT: snd.stop_bgm(); pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_m: snd.toggle_mute()
                if state=="gameover":
                    if event.key==pygame.K_RETURN: snd.stop_bgm(); return True
                    if event.key==pygame.K_ESCAPE: snd.stop_bgm(); pygame.quit(); sys.exit()
                if state=="levelup":
                    for i, opt in enumerate(levelup_opts):
                        if event.key in (pygame.K_1+i, pygame.K_KP1+i):
                            apply_upgrade(player, opt["key"]); state="play"
                if state=="play" and event.key==pygame.K_ESCAPE:
                    snd.stop_bgm(); pygame.quit(); sys.exit()
            if event.type==pygame.MOUSEBUTTONDOWN and state=="levelup":
                mx, my = pygame.mouse.get_pos()
                for i, rect in enumerate(levelup_rects):
                    if rect.collidepoint(mx,my): apply_upgrade(player,levelup_opts[i]["key"]); state="play"

        keys = pygame.key.get_pressed()

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
                since_chest=0.0; a=random.uniform(0,math.pi*2); r=random.uniform(150,350)
                chests.append(Chest(player.x+math.cos(a)*r, player.y+math.sin(a)*r))

            player.update(dt,keys,enemies,bullets,floats,flames,bolts,snd,shake)

            for b in bullets: b.update(dt)
            bullets=[b for b in bullets if b.alive]
            for f in flames: f.update(dt,enemies,floats)
            flames=[f for f in flames if f.alive]
            for b in bolts: b.update(dt)
            bolts=[b for b in bolts if b.alive]

            since_spawn = maybe_spawn(player.x,player.y,elapsed,since_spawn,enemies)
            for e in enemies: e.update(dt,player.x,player.y)

            for b in bullets:
                for e in enemies:
                    if id(e) in b.hit_ids: continue
                    if dist((b.x,b.y),(e.x,e.y)) < b.radius+e.radius:
                        e.hp-=b.damage; e.hit_flash=0.1; b.hit_ids.add(id(e))
                        floats.append(FloatText(e.x,e.y-20,str(int(b.damage)),WHITE,0.5))
                        b.pierce-=1
                        if b.pierce<=0: b.alive=False; break

            for e in enemies:
                if e.hp<=0:
                    e.alive=False; kills+=1; gems.append(Gem(e.x,e.y,e.xp))
                    snd.play("kill")
                    for _ in range(8): particles.append(Particle(e.x,e.y,e.color))
                    if isinstance(e,Boss):
                        chests.append(Chest(e.x,e.y)); shake.shake(10,0.4)
                        floats.append(FloatText(e.x,e.y-60,"BOSS SLAIN!",GOLD,2.0))
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

        sx_off, sy_off = shake.update(dt)
        ox = player.x+sx_off; oy = player.y+sy_off
        draw_bg(screen, ox, oy)
        for c in chests:    c.draw(screen,ox,oy)
        for g in gems:      g.draw(screen,ox,oy)
        for f in flames:    f.draw(screen,ox,oy)
        for e in enemies:   e.draw(screen,ox,oy,sprites)
        for b in bullets:   b.draw(screen,ox,oy)
        for bl in bolts:    bl.draw(screen,ox,oy)
        for p in particles: p.draw(screen,ox,oy)
        player.draw(screen,ox,oy)
        for ft in floats:   ft.draw(screen,ox,oy)
        draw_hud(screen,player,level,xp,xp_next,elapsed,kills,boss_warn)
        if state=="levelup":    levelup_rects=levelup_screen(screen,levelup_opts)
        if state=="gameover":   game_over_screen(screen,elapsed,kills,victory)
        pygame.display.flip()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    screen.fill(DARK)
    screen.blit(font_med.render("Generating assets...", True, GRAY),
                (W//2-100, H//2-20))
    pygame.display.flip()

    snd     = SoundManager()
    sprites = build_sprites()

    while True:
        char_data = character_select(screen, sprites)
        if not run_game(snd, sprites, char_data):
            break
