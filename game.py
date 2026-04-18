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
DARK   = (6,   6,   10)     # near-black bg
ORANGE = (255, 140, 0)
CYAN   = (0,   200, 220)
GOLD   = (255, 200, 0)
LIME   = (130, 255, 50)

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

def _draw_enemy_normal(size=36):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s,(0,0,0,50),(cx-12,size-8,24,7))
    pygame.draw.circle(s,(185,42,42),(cx,cx-2),14)
    pygame.draw.polygon(s,(142,25,25),[(cx-10,11),(cx-15,2),(cx-6,9)])
    pygame.draw.polygon(s,(142,25,25),[(cx+10,11),(cx+15,2),(cx+6,9)])
    pygame.draw.circle(s,YELLOW,(cx-5,cx-4),4)
    pygame.draw.circle(s,YELLOW,(cx+5,cx-4),4)
    pygame.draw.circle(s,(18,8,8),(cx-5,cx-4),2)
    pygame.draw.circle(s,(18,8,8),(cx+5,cx-4),2)
    pygame.draw.arc(s,(18,8,8),(cx-6,cx-1,12,8),math.pi,0,2)
    pygame.draw.circle(s,(142,25,25),(cx,cx-2),14,2)
    return s

def _draw_enemy_fast(size=28):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    pygame.draw.ellipse(s,(0,0,0,50),(cx-9,size-7,18,6))
    pygame.draw.circle(s,(235,72,72),(cx,cx-1),10)
    pygame.draw.polygon(s,(200,40,40),[(cx-7,9),(cx-10,2),(cx-4,7)])
    pygame.draw.polygon(s,(200,40,40),[(cx+7,9),(cx+10,2),(cx+4,7)])
    pygame.draw.circle(s,YELLOW,(cx-3,cx-3),3)
    pygame.draw.circle(s,YELLOW,(cx+3,cx-3),3)
    pygame.draw.circle(s,(15,6,6),(cx-3,cx-3),1)
    pygame.draw.circle(s,(15,6,6),(cx+3,cx-3),1)
    pygame.draw.circle(s,(200,40,40),(cx,cx-1),10,2)
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
        "enemy_normal": _draw_enemy_normal(36),
        "enemy_fast":   _draw_enemy_fast(28),
        "boss":         _draw_boss(88),
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
    __slots__=("x","y","vx","vy","life","max_life","color","r","alive")
    def __init__(self,x,y,color):
        a=random.uniform(0,math.pi*2); v=random.uniform(60,200)
        self.x,self.y=x,y; self.vx,self.vy=math.cos(a)*v,math.sin(a)*v
        self.life=self.max_life=random.uniform(0.3,0.7)
        self.color=color; self.r=random.randint(3,7); self.alive=True
    def update(self,dt):
        self.x+=self.vx*dt; self.vx*=0.92
        self.y+=self.vy*dt; self.vy*=0.92
        self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        alpha=int(255*self.life/self.max_life)
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
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
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
        s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
        cr,cg,cb=self.color
        pygame.draw.circle(s,(cr,cg,cb,alpha),(r+2,r+2),r,self.width)
        surf.blit(s,(sx-r-2,sy-r-2))


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
            tsx=int(tx-ox+W//2); tsy=int(ty-oy+H//2)
            ts=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
            pygame.draw.circle(ts,(cr,cg,cb,int(90*ratio)),(r+1,r+1),r)
            surf.blit(ts,(tsx-r-1,tsy-r-1))

    def draw(self,surf,ox,oy):
        self._draw_trail(surf,ox,oy)
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
        cr,cg,cb=self.color
        r=self.radius

        if self.style=="orb":          # Wand — glowing orb
            # Outer glow
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
            tsx=int(tx-ox+W//2); tsy=int(ty-oy+H//2)
            ts=pygame.Surface((tr*2+2,tr*2+2),pygame.SRCALPHA)
            pygame.draw.circle(ts,(255,140,0,int(75*ratio)),(tr+1,tr+1),tr)
            surf.blit(ts,(tsx-tr-1,tsy-tr-1))
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
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
        r=self.radius; sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
        s=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
        pygame.draw.circle(s,(255,100,0,alpha),(r,r),r)
        pygame.draw.circle(s,(255,200,0,alpha//2),(r,r),r//2)
        surf.blit(s,(sx-r,sy-r))
        # Flickering inner sparks
        for _ in range(3):
            a=random.uniform(0,math.pi*2); rd=random.uniform(0,r*0.7)
            fx=int(sx+math.cos(a)*rd); fy=int(sy+math.sin(a)*rd)
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
            spts=[(int(p[0]-ox+W//2),int(p[1]-oy+H//2)) for p in seg]
            if len(spts)>=2:
                pygame.draw.lines(surf,CYAN,False,spts,3)
                pygame.draw.lines(surf,WHITE,False,spts,1)
        for fork in self.forks:
            spts=[(int(p[0]-ox+W//2),int(p[1]-oy+H//2)) for p in fork]
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
        r=self.radius; sx=int(self.player.x-ox+W//2); sy=int(self.player.y-oy+H//2)
        s=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
        pygame.draw.circle(s,(200,50,50,48),(r,r),r)
        surf.blit(s,(sx-r,sy-r))


# ─────────────────────────────────────────────
# Gem / Chest / FloatText
# ─────────────────────────────────────────────
class Gem:
    def __init__(self,x,y,value=5):
        self.x,self.y=x,y; self.value=value; self.radius=6; self.alive=True
    def draw(self,surf,ox,oy):
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
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
        bob=math.sin(self.bob)*4
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2+bob)
        r=pygame.Rect(sx-14,sy-10,28,20)
        pygame.draw.rect(surf,GOLD,r,border_radius=3)
        pygame.draw.rect(surf,ORANGE,r,2,border_radius=3)
        pygame.draw.rect(surf,(200,160,0),(sx-14,sy-14,28,8),border_radius=3)
        pygame.draw.rect(surf,ORANGE,(sx-14,sy-14,28,8),2,border_radius=3)
        pygame.draw.circle(surf,BLACK,(sx,sy-2),3)
        gs=pygame.Surface((60,60),pygame.SRCALPHA)
        pygame.draw.circle(gs,(255,200,0,38),(30,30),30)
        surf.blit(gs,(sx-30,sy-30))

class FloatText:
    def __init__(self,x,y,text,color,life=1.0):
        self.x,self.y=x,y; self.text=text; self.color=color
        self.life=self.max_life=life; self.alive=True
    def update(self,dt):
        self.y-=40*dt; self.life-=dt
        if self.life<=0: self.alive=False
    def draw(self,surf,ox,oy):
        alpha=int(255*self.life/self.max_life)
        s=font_small.render(self.text,True,self.color); s.set_alpha(alpha)
        surf.blit(s,(int(self.x-ox+W//2),int(self.y-oy+H//2)))


# ─────────────────────────────────────────────
# Enemy / Boss
# ─────────────────────────────────────────────
class Enemy:
    def __init__(self,x,y,hp,speed,damage,radius,color,xp,sprite_key="enemy_normal"):
        self.x,self.y=x,y; self.hp=self.max_hp=hp; self.speed=speed
        self.damage=damage; self.radius=radius; self.color=color; self.xp=xp
        self.alive=True; self.hit_flash=0.0; self.sprite_key=sprite_key
    def update(self,dt,px,py,_b=None,_f=None):
        dx,dy=norm(px-self.x,py-self.y)
        self.x+=dx*self.speed*dt; self.y+=dy*self.speed*dt
        if self.hit_flash>0: self.hit_flash-=dt
    def draw(self,surf,ox,oy,sprites):
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
        spr=sprites.get(self.sprite_key)
        if spr:
            if self.hit_flash>0:
                ws=spr.copy(); ws.fill((255,255,255,160),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws,(sx-spr.get_width()//2,sy-spr.get_height()//2))
            else:
                surf.blit(spr,(sx-spr.get_width()//2,sy-spr.get_height()//2))
        else:
            pygame.draw.circle(surf,self.color,(sx,sy),self.radius)
        bw=self.radius*2; ratio=max(0,self.hp/self.max_hp)
        pygame.draw.rect(surf,GRAY,(sx-self.radius,sy-self.radius-8,bw,5))
        pygame.draw.rect(surf,GREEN,(sx-self.radius,sy-self.radius-8,int(bw*ratio),5))

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
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
        if self.telegraph>0:
            pulse=abs(math.sin(self.telegraph*20))*22; r=36+int(pulse)
            s=pygame.Surface((r*2,r*2),pygame.SRCALPHA)
            pygame.draw.circle(s,(255,50,50,115),(r,r),r)
            surf.blit(s,(sx-r,sy-r))
        spr=sprites.get("boss")
        if spr:
            if self.hit_flash>0:
                ws=spr.copy(); ws.fill((255,255,255,160),special_flags=pygame.BLEND_RGBA_ADD)
                surf.blit(ws,(sx-spr.get_width()//2,sy-spr.get_height()//2))
            else:
                surf.blit(spr,(sx-spr.get_width()//2,sy-spr.get_height()//2))
        else:
            pygame.draw.circle(surf,PURPLE,(sx,sy),self.radius)
        bw=100; ratio=max(0,self.hp/self.max_hp)
        pygame.draw.rect(surf,GRAY,(sx-50,sy-self.radius-14,bw,8))
        pygame.draw.rect(surf,RED,(sx-50,sy-self.radius-14,int(bw*ratio),8))
        lbl=font_small.render(self.name,True,YELLOW)
        surf.blit(lbl,(sx-lbl.get_width()//2,sy-self.radius-28))


# ─────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────
CHARACTERS=[
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
    PICKUP_RANGE=120
    def __init__(self,char_data,sprites):
        self.x=self.y=0.0; self.max_hp=char_data["hp"]; self.hp=self.max_hp
        self.speed=char_data["speed"]; self.char_color=char_data["color"]
        self.radius=16; self.alive=True; self.hurt_sound_cd=0.0
        self.sprite=sprites.get(char_data["sprite"])
        self.weapons={
            "wand":     {"level":char_data["weapons"]["wand"],     "timer":0.0,"cooldown":char_data["wand_cd"]},
            "axe":      {"level":char_data["weapons"]["axe"],      "timer":0.0,"cooldown":1.5},
            "cross":    {"level":char_data["weapons"]["cross"],    "timer":0.0,"cooldown":3.0},
            "garlic":   {"level":char_data["weapons"]["garlic"]},
            "lightning":{"level":char_data["weapons"]["lightning"],"timer":0.0,"cooldown":2.0},
            "flame":    {"level":char_data["weapons"]["flame"],    "timer":0.0,"cooldown":4.0},
        }
        self.aura=None

    def update(self,dt,keys,enemies,bullets,floats,flames,bolts,rings,particles,snd,shake):
        dx=dy=0
        if keys[pygame.K_w] or keys[pygame.K_UP]:   dy-=1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy+=1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx-=1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx+=1
        ndx,ndy=norm(dx,dy)
        self.x+=ndx*self.speed*dt; self.y+=ndy*self.speed*dt
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
        sx=int(self.x-ox+W//2); sy=int(self.y-oy+H//2)
        if self.sprite:
            surf.blit(self.sprite,(sx-self.sprite.get_width()//2,sy-self.sprite.get_height()//2))
        else:
            pygame.draw.circle(surf,self.char_color,(sx,sy),self.radius)
        bw=80; ratio=max(0,self.hp/self.max_hp)
        pygame.draw.rect(surf,GRAY,(sx-40,sy-self.radius-14,bw,8))
        pygame.draw.rect(surf,RED, (sx-40,sy-self.radius-14,int(bw*ratio),8))
        if self.aura: self.aura.draw(surf,ox,oy)


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
    if random.random()<0.18:
        return Enemy(x,y,hp=28+diff*8, speed=175+diff*22,damage=8, radius=10,color=(255,72,72),xp=3,sprite_key="enemy_fast")
    return Enemy(x,y,hp=60+diff*25,speed=90+diff*10,damage=15,radius=14,color=RED,xp=5,sprite_key="enemy_normal")

def maybe_spawn(px,py,elapsed,since_last,enemies):
    rate=max(0.3,1.5-elapsed/120)
    if since_last>=rate:
        for _ in range(min(1+int(elapsed//30),6)):
            enemies.append(spawn_enemy(px,py,elapsed))
        return 0.0
    return since_last

def spawn_boss(px,py,level):
    a=random.uniform(0,math.pi*2)
    return Boss(px+math.cos(a)*700,py+math.sin(a)*700,level)

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
        cw2, ch2 = 316, 295
        total_w  = len(CHARACTERS)*cw2 + (len(CHARACTERS)-1)*28
        sx0      = W//2 - total_w//2
        char_rects = []

        for i, cd in enumerate(CHARACTERS):
            rx = sx0 + i*(cw2+28); ry = 155
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


def draw_bg(surf, ox, oy):
    surf.fill(DARK)
    step = 80; ox_mod = int(ox)%step; oy_mod = int(oy)%step
    # Grid lines
    for gx in range(-1, W//step+2):
        pygame.draw.line(surf, UI_GRID, (gx*step-ox_mod, 0), (gx*step-ox_mod, H))
    for gy in range(-1, H//step+2):
        pygame.draw.line(surf, UI_GRID, (0, gy*step-oy_mod), (W, gy*step-oy_mod))
    # Glowing dots at intersections
    for gx in range(-1, W//step+2):
        for gy in range(-1, H//step+2):
            pygame.draw.circle(surf, (42, 30, 68), (gx*step-ox_mod, gy*step-oy_mod), 2)


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

            player.update(dt,keys,enemies,bullets,floats,flames,bolts,rings,particles,snd,shake)

            for b in bullets: b.update(dt)
            bullets=[b for b in bullets if b.alive]
            for f in flames: f.update(dt,enemies,floats)
            flames=[f for f in flames if f.alive]
            for b in bolts: b.update(dt)
            bolts=[b for b in bolts if b.alive]
            for r in rings: r.update(dt)
            rings=[r for r in rings if r.alive]

            since_spawn=maybe_spawn(player.x,player.y,elapsed,since_spawn,enemies)
            for e in enemies: e.update(dt,player.x,player.y)

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
        draw_bg(screen,ox,oy)
        for c in chests:    c.draw(screen,ox,oy)
        for g in gems:      g.draw(screen,ox,oy)
        for f in flames:    f.draw(screen,ox,oy)
        for r in rings:     r.draw(screen,ox,oy)      # rings behind enemies
        for e in enemies:   e.draw(screen,ox,oy,sprites)
        for b in bullets:   b.draw(screen,ox,oy)
        for bl in bolts:    bl.draw(screen,ox,oy)
        for p in particles: p.draw(screen,ox,oy)
        player.draw(screen,ox,oy)
        for ft in floats:   ft.draw(screen,ox,oy)
        draw_hud(screen,player,level,xp,xp_next,elapsed,kills,boss_warn)
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
