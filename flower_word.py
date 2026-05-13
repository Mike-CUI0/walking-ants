"""
꽃잎 단어 기억 앱
꽃잎들이 날아와 꽃을 완성 → 꽃이 천천히 살아 숨쉼 → 꽃잎이 흩날리며 다음 단어로
- 단클릭 / 15초 : 다음 단어
- 더블클릭     : 파일 재선택
- 우클릭       : 종료
"""
import tkinter as tk
from tkinter import filedialog
import math, random

TRANS  = '#FF00FF'
AUTO_S = 15
DBL_MS = 300
FPS    = 60

# 상태
S_ASSEMBLE = 0
S_BLOOM    = 1
S_SCATTER  = 2

# 꽃 색상 팔레트 (main, highlight, vein)
PALETTES = [
    ('#FFB7C5', '#FFE0EA', '#FF85A1'),  # 벚꽃
    ('#FF9FF3', '#FFCDF8', '#DD6FD0'),  # 라일락
    ('#FF6B6B', '#FF9E9E', '#BB3333'),  # 빨간 꽃
    ('#FFD93D', '#FFF0A0', '#CC9900'),  # 노란 꽃
    ('#74D7FF', '#C0EDFF', '#3AAAD4'),  # 하늘 꽃
    ('#A29BFE', '#CFC8FF', '#6C5CE7'),  # 보라 꽃
    ('#55EFC4', '#A0F5DC', '#2ECC7A'),  # 민트 꽃
    ('#FD9644', '#FFCFA0', '#CC6611'),  # 주황 꽃
]
CENTER_OUT = '#FFD700'
CENTER_IN  = '#FF8C00'
CENTER_DOT = '#CC6600'


# ══════════════════════════════════════════════════════════════════════════════
# 언어 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def is_chinese(ch):
    cp=ord(ch); return 0x4E00<=cp<=0x9FFF or 0x3400<=cp<=0x4DBF or 0xF900<=cp<=0xFAFF

def is_korean(ch):
    cp=ord(ch); return 0xAC00<=cp<=0xD7AF or 0x1100<=cp<=0x11FF or 0x3130<=cp<=0x318F

def reorder_line(line):
    chinese=[c for c in line if is_chinese(c)]
    digits =[c for c in line if c.isdigit()]
    korean =[c for c in line if is_korean(c)]
    others =[c for c in line if not is_chinese(c) and not c.isdigit()
                              and not is_korean(c) and c.strip()]
    return ''.join(chinese+digits+korean+others) if chinese and korean else line

def load_words(path):
    for enc in ('utf-8','utf-8-sig','cp949'):
        try:
            with open(path,encoding=enc) as f: lines=f.read().splitlines(); break
        except (UnicodeDecodeError,LookupError): continue
    else: return []
    return [reorder_line(l.strip()) for l in lines if l.strip()]

def pick_file(parent=None):
    return filedialog.askopenfilename(
        parent=parent, title="단어 파일 선택",
        filetypes=[("텍스트 파일","*.txt"),("모든 파일","*.*")]) or None

def pick_and_load():
    tmp=tk.Tk(); tmp.withdraw(); tmp.attributes('-topmost',True)
    path=pick_file(parent=tmp); tmp.destroy()
    return load_words(path) if path else []


# ══════════════════════════════════════════════════════════════════════════════
# 꽃잎 폴리곤 생성
# ══════════════════════════════════════════════════════════════════════════════

def petal_polygon(cx, cy, angle, petal_l, petal_w, n=28):
    """
    꽃잎 다각형 좌표 반환.
    angle = 꽃잎이 바깥쪽으로 가리키는 방향(라디안).
    로컬 좌표: +y = 꽃 바깥쪽(tip), -y = 꽃 안쪽(base)
    """
    pts = []
    for k in range(n):
        t = 2*math.pi*k/n
        # 기본 타원
        lx = petal_w/2 * math.sin(t)
        ly = petal_l/2 * math.cos(t)
        # 끝을 살짝 뾰족하게, 밑동을 살짝 좁게
        taper = 1.0 - 0.18*(1 - math.cos(t))   # tip: 1.0, sides: ~0.82
        lx *= taper
        # 스크린 좌표 변환
        # local +y → 꽃 바깥 방향(angle)
        sx = cx - math.sin(angle)*lx + math.cos(angle)*ly
        sy = cy + math.cos(angle)*lx + math.sin(angle)*ly
        pts.extend([sx, sy])
    return pts

def petal_highlight(cx, cy, angle, petal_l, petal_w):
    """꽃잎 중앙 하이라이트 (작은 타원, 바깥쪽으로 치우침)"""
    hl = 0.45
    offset_ly = petal_l * 0.10    # 바깥쪽으로 약간 치우침
    ncx = cx + math.cos(angle)*offset_ly
    ncy = cy + math.sin(angle)*offset_ly
    return petal_polygon(ncx, ncy, angle, petal_l*hl, petal_w*hl*0.72, n=16)

def petal_vein(cx, cy, angle, petal_l):
    """꽃잎 중심맥 좌표 (선)"""
    inner = cx + math.cos(angle)*(-petal_l*0.38)
    innery = cy + math.sin(angle)*(-petal_l*0.38)
    outer = cx + math.cos(angle)*(petal_l*0.45)
    outery = cy + math.sin(angle)*(petal_l*0.45)
    return inner, innery, outer, outery


# ══════════════════════════════════════════════════════════════════════════════
# 꽃 물리 클래스
# ══════════════════════════════════════════════════════════════════════════════

class FlowerPhysics:
    def __init__(self, word, palette_idx, W, H):
        self.word      = word
        self.n         = max(5, len(word))
        self.W, self.H = W, H
        self.state     = S_ASSEMBLE
        self.frame     = 0

        pal = PALETTES[palette_idx % len(PALETTES)]
        self.c_main, self.c_hl, self.c_vein = pal

        # 꽃 위치 (화면 중앙)
        self.fx = W/2
        self.fy = H/2

        # 꽃잎 치수 (꽃잎 수에 맞게 조절)
        self.petal_l = max(48, min(80, 340 // self.n + 20))
        self.petal_w = int(self.petal_l * 0.52)
        self.D       = self.petal_l * 0.50   # 중심→꽃잎 중심 거리

        # 각 꽃잎 목표 각도
        self.target_angles = [2*math.pi*i/self.n + math.pi/self.n*0
                               for i in range(self.n)]

        # 꽃잎별 비행 상태 (날아오는 중 / 흩어지는 중)
        self.ps = []
        for i in range(self.n):
            side = random.randint(0,3)
            if   side==0: x,y = random.uniform(0,W), -120
            elif side==1: x,y = W+120, random.uniform(0,H)
            elif side==2: x,y = random.uniform(0,W), H+120
            else:          x,y = -120, random.uniform(0,H)
            self.ps.append({
                'x':x,'y':y,'vx':0.0,'vy':0.0,
                'rot': random.uniform(0,math.tau),
                'vrot': random.uniform(-0.12, 0.12),
                'assembled': False,
                'svx':0.0,'svy':0.0,'svrot':0.0,
            })

        # 꽃 전체 애니메이션 파라미터
        self.flower_rot  = random.uniform(0, math.tau)
        self.rot_speed   = random.uniform(-0.004, 0.004)
        self.breathe     = 0.0
        self.petal_phase = [random.uniform(0, math.tau) for _ in range(self.n)]
        self.petal_amp   = [random.uniform(3, 9) for _ in range(self.n)]

        # 중심 팝인 애니메이션
        self.center_scale   = 0.0
        self.bloom_started  = False

        self.font_size = max(11, min(16, self.petal_w//2))
        self.font      = ('맑은 고딕', self.font_size, 'bold')

    # ── 업데이트 → True 반환 시 다음 단어 ────────────────────────────────────

    def update(self) -> bool:
        self.frame += 1

        if self.state == S_ASSEMBLE:
            all_done = True
            for i, p in enumerate(self.ps):
                if p['assembled']:
                    continue
                angle = self.target_angles[i] + self.flower_rot
                tx = self.fx + self.D*math.cos(angle)
                ty = self.fy + self.D*math.sin(angle)
                p['vx'] = p['vx']*0.80 + (tx - p['x'])*0.20
                p['vy'] = p['vy']*0.80 + (ty - p['y'])*0.20
                p['x'] += p['vx']; p['y'] += p['vy']
                p['rot'] += p['vrot']
                p['vrot'] *= 0.93   # 착지할수록 회전 감소
                if math.hypot(tx-p['x'], ty-p['y']) < 2.0:
                    p['assembled'] = True
                    p['x'], p['y'] = tx, ty
                    p['vx'] = p['vy'] = p['vrot'] = 0.0
                else:
                    all_done = False
            if all_done:
                self.state = S_BLOOM; self.frame = 0

        elif self.state == S_BLOOM:
            self.flower_rot += self.rot_speed
            self.breathe    += 0.022
            # 중심 팝인
            if self.center_scale < 1.0:
                self.center_scale = min(1.0, self.center_scale + 0.06)

        elif self.state == S_SCATTER:
            all_gone = True
            for p in self.ps:
                p['svy'] += 0.38
                p['x'] += p['svx']; p['y'] += p['svy']
                p['rot'] += p['svrot']
                if not (p['x']<-200 or p['x']>self.W+200 or
                        p['y']<-200 or p['y']>self.H+300):
                    all_gone = False
            if all_gone: return True

        return False

    def scatter(self):
        # 현재 꽃잎 위치 캡처
        for i, p in enumerate(self.ps):
            angle = self.target_angles[i] + self.flower_rot
            p['x']   = self.fx + self.D*math.cos(angle)
            p['y']   = self.fy + self.D*math.sin(angle)
            p['rot'] = angle
        self.state = S_SCATTER
        for i, p in enumerate(self.ps):
            angle = self.target_angles[i] + self.flower_rot
            spd = random.uniform(10, 24)
            p['svx']  = math.cos(angle)*spd + random.uniform(-4, 4)
            p['svy']  = math.sin(angle)*spd - random.uniform(3, 10)
            p['svrot']= random.uniform(-0.18, 0.18)

    # ── 그리기 ───────────────────────────────────────────────────────────────

    def draw(self, cv: tk.Canvas, ids: list):
        breathe_scale = 1.0 + 0.04*math.sin(self.breathe)

        # ── 꽃잎 그리기 ──────────────────────────────────────────────────────
        for i, p in enumerate(self.ps):
            # 위치와 각도 결정
            if self.state == S_BLOOM or (self.state == S_ASSEMBLE and p['assembled']):
                angle  = self.target_angles[i] + self.flower_rot
                wobble = math.sin(self.breathe*1.1 + self.petal_phase[i])
                r_off  = wobble * self.petal_amp[i] * 0.25
                a_off  = wobble * 0.04
                eff_angle = angle + a_off
                eff_D     = (self.D + r_off) * breathe_scale
                px = self.fx + eff_D*math.cos(eff_angle)
                py = self.fy + eff_D*math.sin(eff_angle)
                pl = self.petal_l * breathe_scale
                pw = self.petal_w * breathe_scale
                draw_angle = eff_angle
            else:
                # 날아오는 / 흩어지는 중
                px, py = p['x'], p['y']
                draw_angle = p['rot']
                pl = self.petal_l
                pw = self.petal_w

            # 그림자
            sp = petal_polygon(px+4, py+4, draw_angle, pl, pw)
            ids.append(cv.create_polygon(*sp, fill='#1A1A2E', outline='', smooth=True))

            # 꽃잎 본체
            mp = petal_polygon(px, py, draw_angle, pl, pw)
            ids.append(cv.create_polygon(*mp, fill=self.c_main,
                                          outline='white', width=1, smooth=True))

            # 하이라이트
            hp = petal_highlight(px, py, draw_angle, pl, pw)
            ids.append(cv.create_polygon(*hp, fill=self.c_hl,
                                          outline='', smooth=True))

            # 중심맥
            vx1,vy1,vx2,vy2 = petal_vein(px, py, draw_angle, pl)
            ids.append(cv.create_line(vx1,vy1,vx2,vy2,
                                       fill=self.c_vein, width=1,
                                       smooth=True, capstyle='round'))

            # 글자 (항상 수평)
            char = self.word[i] if i < len(self.word) else ''
            if char:
                ids.append(cv.create_text(px+1.5, py+1.5, text=char,
                                           font=self.font, fill='#2A1A00'))
                ids.append(cv.create_text(px, py, text=char,
                                           font=self.font, fill='white'))

        # ── 꽃 중심 (BLOOM 상태에서만) ───────────────────────────────────────
        if self.state == S_BLOOM or (self.state==S_ASSEMBLE and
                                     all(p['assembled'] for p in self.ps)):
            self._draw_center(cv, ids, breathe_scale)

    def _draw_center(self, cv, ids, breathe):
        fx, fy = self.fx, self.fy
        r = max(16, int(self.petal_w * 0.52)) * breathe * self.center_scale

        # 그림자
        ids.append(cv.create_oval(fx-r+4, fy-r+4, fx+r+4, fy+r+4,
                                   fill='#1A1A2E', outline=''))
        # 외곽 노란 원
        ids.append(cv.create_oval(fx-r, fy-r, fx+r, fy+r,
                                   fill=CENTER_OUT, outline='white', width=2))
        # 내부 주황 원
        r2 = r*0.62
        ids.append(cv.create_oval(fx-r2, fy-r2, fx+r2, fy+r2,
                                   fill=CENTER_IN, outline=''))
        # 수술 점들
        n_dot = 8
        for k in range(n_dot):
            a   = 2*math.pi*k/n_dot + self.flower_rot*2
            dr  = r*0.42
            ddr = r*0.12
            dx  = fx + dr*math.cos(a)
            dy  = fy + dr*math.sin(a)
            ids.append(cv.create_oval(dx-ddr, dy-ddr, dx+ddr, dy+ddr,
                                       fill=CENTER_DOT, outline=''))
        # 중심점
        ids.append(cv.create_oval(fx-r*0.18, fy-r*0.18,
                                   fx+r*0.18, fy+r*0.18,
                                   fill='#AA4400', outline=''))


# ══════════════════════════════════════════════════════════════════════════════
# 메인 앱
# ══════════════════════════════════════════════════════════════════════════════

class App:
    def __init__(self, words):
        self.words     = words
        self.word_idx  = 0
        self.palette_idx = 0

        root = tk.Tk()
        self.root = root
        root.overrideredirect(True)
        root.wm_attributes('-topmost', True)
        root.wm_attributes('-transparentcolor', TRANS)
        root.config(bg=TRANS)

        self.W = root.winfo_screenwidth()
        self.H = root.winfo_screenheight()
        root.geometry(f"{self.W}x{self.H}+0+0")

        self.cv = tk.Canvas(root, width=self.W, height=self.H,
                            bg=TRANS, highlightthickness=0)
        self.cv.pack()

        self.ids       = []
        self._clk_job  = None
        self._auto_job = None
        self.flower    = FlowerPhysics(words[0], 0, self.W, self.H)

        self.cv.bind('<Button-1>', self._on_click)
        self.cv.bind('<Button-3>', lambda e: root.destroy())

        self._label = tk.Label(root,
            text=self._lbl(),
            bg='#1a1a2e', fg='#eeeeee',
            font=('맑은 고딕', 9), padx=7, pady=4)
        self._label.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)

        self._reset_auto()
        self._loop()
        root.mainloop()

    def _lbl(self):
        w = self.words[self.word_idx]
        return (f"  [{self.word_idx+1}/{len(self.words)}]  {w}  |  "
                f"단클릭·{AUTO_S}s:다음  더블클릭:파일재선택  우클릭:종료  ")

    def _reset_auto(self):
        if self._auto_job: self.root.after_cancel(self._auto_job)
        self._auto_job = self.root.after(AUTO_S*1000, self._next_word)

    def _on_click(self, event):
        if self._clk_job is not None:
            self.root.after_cancel(self._clk_job)
            self._clk_job = None
            self._reload_file()
        else:
            self._clk_job = self.root.after(DBL_MS, self._next_word)

    def _next_word(self):
        self._clk_job = None
        if self._auto_job: self.root.after_cancel(self._auto_job); self._auto_job=None
        if self.flower.state != S_SCATTER:
            self.flower.scatter()

    def _reload_file(self):
        self.root.wm_attributes('-topmost', False)
        path = pick_file(parent=self.root)
        self.root.wm_attributes('-topmost', True)
        if not path: return
        nw = load_words(path)
        if not nw: return
        self.words = nw; self.word_idx = 0; self.palette_idx = 0
        self.flower = FlowerPhysics(nw[0], 0, self.W, self.H)
        self._label.config(text=self._lbl())
        self._reset_auto()

    def _draw(self):
        for i in self.ids: self.cv.delete(i)
        self.ids = []
        self.flower.draw(self.cv, self.ids)

    def _loop(self):
        done = self.flower.update()
        if done:
            self.word_idx    = (self.word_idx+1) % len(self.words)
            self.palette_idx = (self.palette_idx+1) % len(PALETTES)
            self.flower = FlowerPhysics(self.words[self.word_idx],
                                        self.palette_idx, self.W, self.H)
            self._label.config(text=self._lbl())
            self._reset_auto()
        self._draw()
        self.root.after(1000//FPS, self._loop)


if __name__ == '__main__':
    words = pick_and_load()
    if words:
        App(words)
