"""
귀여운 캐터필러 데스크탑 펫
- 실행 시 텍스트 파일 선택 → 줄별 단어를 몸통에 표시
- 단클릭 / 길이별 자동 : 다음 단어
- 더블클릭 : 파일 재선택
- 우클릭   : 종료
"""
import tkinter as tk
from tkinter import filedialog
import math, random
from collections import deque

TRANS  = '#FF00FF'
DBL_MS = 280

def auto_secs(word):
    n = len(word)
    if n < 10: return 15
    if n < 20: return 20
    if n < 30: return 25
    return 30

# ── 치수 ─────────────────────────────────────────────────────────────────────
SEG_R        = 33    # 마디 반지름 (완전한 원)
HEAD_R       = 46    # 머리 반지름
SEG_SPACE_PX = 54    # 마디 간 거리
LEG_LEN      = 16
SPEED        = 1.5
MARGIN       = 220   # 머리 이동 경계 — 첫 글자 잘림 방지

# ── 색상 ─────────────────────────────────────────────────────────────────────
C_BODY_A  = '#74C830'   # 밝은 라임 그린 A
C_BODY_B  = '#5AB020'   # 라임 그린 B
C_BODY_HL = '#B8EC70'   # 하이라이트
C_BODY_SH = '#347010'   # 그림자 / 윤곽
C_HEAD    = '#84D840'   # 머리 색
C_HEAD_HL = '#C4F080'   # 머리 하이라이트
C_EYE_W   = '#FFFFFF'
C_EYE_P   = '#181830'   # 동공
C_EYE_HL1 = '#FFFFFF'   # 반짝이
C_BLUSH   = '#FF9090'   # 볼터치
C_LEG     = '#347010'
C_ANT     = '#347010'
C_ANT_TIP = '#FFD840'
C_LETTER  = '#204808'   # 글자 (진녹)
C_LTR_HL  = '#FFFFFF'   # 글자 하이라이트
C_MOUTH_L = '#204808'   # 입 윤곽
C_MOUTH_I = '#FF7070'   # 입 안 (혀/잇몸)
C_TEETH   = '#FFFFFF'   # 이

# ══════════════════════════════════════════════════════════════════════════════
# 언어 판별 & 재배치
# ══════════════════════════════════════════════════════════════════════════════

def is_chinese(ch):
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x2A6DF)

def is_korean(ch):
    cp = ord(ch)
    return (0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF or
            0x3130 <= cp <= 0x318F)

def reorder_line(line):
    chinese = [c for c in line if is_chinese(c)]
    digits  = [c for c in line if c.isdigit()]
    korean  = [c for c in line if is_korean(c)]
    others  = [c for c in line if not is_chinese(c) and not c.isdigit()
                                  and not is_korean(c) and c.strip()]
    if chinese and korean:
        return ''.join(chinese + digits + korean + others)
    return line

def load_words(path):
    for enc in ('utf-8', 'utf-8-sig', 'cp949'):
        try:
            with open(path, encoding=enc) as f:
                raw = f.read().splitlines()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return []
    return [reorder_line(ln.strip()) for ln in raw if ln.strip()]

def pick_file(parent=None):
    return filedialog.askopenfilename(
        parent=parent, title="단어 파일을 선택하세요",
        filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
    ) or None

def pick_and_load():
    tmp = tk.Tk(); tmp.withdraw(); tmp.attributes('-topmost', True)
    path = pick_file(parent=tmp); tmp.destroy()
    return load_words(path) if path else []


# ══════════════════════════════════════════════════════════════════════════════
# 캐터필러 클래스
# ══════════════════════════════════════════════════════════════════════════════

class Caterpillar:
    def __init__(self, words):
        self.words    = words
        self.word_idx = 0
        self.word     = words[0]
        self.max_n    = max(8, max(len(w) for w in words))
        self.n        = max(8, len(self.word))

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

        self.hx      = self.W / 2.0
        self.hy      = self.H / 2.0
        self.heading = random.uniform(0, 360)
        self.steer   = 0.0
        self.steer_cd= 0
        self.tick    = 0

        self._rebuild_seg_idx()
        self._init_hist()

        self.ids       = []
        self._clk_job  = None
        self._auto_job = None

        self.cv.bind('<Button-1>', self._on_click)
        self.cv.bind('<Button-3>', lambda e: root.destroy())

        self._label = tk.Label(root, text=self._lbl(),
                               bg='#1B4332', fg='#D8F3DC',
                               font=('맑은 고딕', 9), padx=6, pady=3)
        self._label.place(relx=1.0, rely=1.0, anchor='se', x=-10, y=-10)

        self._reset_auto()
        self._loop()
        root.mainloop()

    # ── 히스토리 ─────────────────────────────────────────────────────────────

    def _rebuild_seg_idx(self):
        self._all_seg_idx = [max(1, int((i + 1) * SEG_SPACE_PX / SPEED))
                             for i in range(self.max_n)]

    def _init_hist(self):
        max_hist = self._all_seg_idx[-1] + int(SEG_SPACE_PX / SPEED) * 4 + 10
        self.hist = deque(maxlen=max_hist)
        a0 = math.radians(self.heading)
        for k in range(max_hist):
            # 뒤쪽 위치를 화면 안으로 클램프 — 시작 시 글자 잘림 방지
            px = self.hx - k * math.cos(a0) * SPEED
            py = self.hy - k * math.sin(a0) * SPEED
            px = max(SEG_R + 10, min(self.W - SEG_R - 10, px))
            py = max(SEG_R + 10, min(self.H - SEG_R - 10, py))
            self.hist.append((px, py))

    # ── 자동 전환 ────────────────────────────────────────────────────────────

    def _reset_auto(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
        secs = auto_secs(self.word)
        self._auto_job = self.root.after(secs * 1000, self._next_word)

    def _lbl(self):
        secs = auto_secs(self.word)
        return (f"  {self.word_idx+1}/{len(self.words)}  "
                f"단클릭·{secs}초:다음  더블클릭:파일재선택  우클릭:종료  ")

    # ── 클릭 ─────────────────────────────────────────────────────────────────

    def _on_click(self, event):
        if self._clk_job is not None:
            self.root.after_cancel(self._clk_job)
            self._clk_job = None
            self._reload_file()
        else:
            self._clk_job = self.root.after(DBL_MS, self._next_word)

    def _next_word(self):
        self._clk_job = None
        self.word_idx = (self.word_idx + 1) % len(self.words)
        self.word     = self.words[self.word_idx]
        self.n        = max(8, len(self.word))
        self._label.config(text=self._lbl())
        self._reset_auto()

    def _reload_file(self):
        self.root.wm_attributes('-topmost', False)
        path = pick_file(parent=self.root)
        self.root.wm_attributes('-topmost', True)
        if not path:
            return
        nw = load_words(path)
        if not nw:
            return
        self.words    = nw
        self.word_idx = 0
        self.word     = nw[0]
        new_max = max(8, max(len(w) for w in nw))
        if new_max != self.max_n:
            self.max_n = new_max
            self._rebuild_seg_idx()
            mh = self._all_seg_idx[-1] + int(SEG_SPACE_PX / SPEED) * 4 + 10
            self.hist = deque(list(self.hist), maxlen=mh)
        self.n = max(8, len(self.word))
        self._label.config(text=self._lbl())
        self._reset_auto()

    # ── 좌표 헬퍼 ────────────────────────────────────────────────────────────

    def _at(self, cx, cy, a, dx, dy):
        ca, sa = math.cos(a), math.sin(a)
        return cx + dx*ca - dy*sa, cy + dx*sa + dy*ca

    def _circle(self, x, y, r, fill, outline='', width=0):
        self.ids.append(self.cv.create_oval(
            x-r, y-r, x+r, y+r, fill=fill, outline=outline, width=width))

    # ── 마디 그리기 ───────────────────────────────────────────────────────────

    def _draw_segment(self, x, y, r, color, hl, sh, char=''):
        cv = self.cv

        # 그림자
        self._circle(x+3, y+4, r, sh)

        # 본체
        self.ids.append(cv.create_oval(
            x-r, y-r, x+r, y+r,
            fill=color, outline=sh, width=1))

        # 하이라이트 (왼쪽 위 빛 반사)
        hx2 = x - r * 0.28
        hy2 = y - r * 0.28
        hr  = r * 0.44
        self._circle(hx2, hy2, hr, hl)

        # 글자 (있을 때만)
        if char:
            fs = max(14, int(r * 1.05))
            # 글자 그림자
            self.ids.append(cv.create_text(
                x+1.5, y+1.5, text=char,
                font=('맑은 고딕', fs, 'bold'), fill=C_BODY_SH))
            # 글자 본체
            self.ids.append(cv.create_text(
                x, y, text=char,
                font=('맑은 고딕', fs, 'bold'), fill=C_LETTER))

    # ── 머리 그리기 ───────────────────────────────────────────────────────────

    def _draw_head(self, hx, hy, ha):
        cv = self.cv
        r  = HEAD_R

        # 그림자
        self._circle(hx+3, hy+4, r, C_BODY_SH)

        # 머리 본체
        self._circle(hx, hy, r, C_HEAD, C_BODY_SH, 1)

        # 머리 하이라이트
        self._circle(hx - r*0.27, hy - r*0.27, r*0.42, C_HEAD_HL)

        # ── 더듬이 ────────────────────────────────────────────────────────
        sway = math.sin(self.tick * 0.09) * 0.5
        for side in (-1, 1):
            base = self._at(hx, hy, ha, r*0.45, side*r*0.48)
            mid  = self._at(hx, hy, ha,
                            r*0.72 + sway*side*r*0.18,
                            side*(r*0.90 + sway*r*0.12))
            tip  = self._at(hx, hy, ha,
                            r*0.52,
                            side*(r*1.55 + sway*r*0.30))
            self.ids.append(cv.create_line(
                *base, *mid, *tip,
                fill=C_ANT, width=2.5, smooth=True, capstyle='round'))
            self._circle(tip[0], tip[1], 6, C_ANT_TIP, C_BODY_SH, 1)

        # ── 눈 (크고 동그랗게) ────────────────────────────────────────────
        eye_r = r * 0.40
        for side in (-1, 1):
            ex, ey = self._at(hx, hy, ha, r*0.20, side*r*0.50)

            # 흰자
            self._circle(ex, ey, eye_r, C_EYE_W, C_BODY_SH, 1)

            # 동공 (약간 앞쪽으로)
            px2, py2 = self._at(ex, ey, ha, eye_r*0.15, 0)
            self._circle(px2, py2, eye_r*0.58, C_EYE_P)

            # 반짝이 큰 것
            self._circle(ex - eye_r*0.22, ey - eye_r*0.22, eye_r*0.26, C_EYE_HL1)
            # 반짝이 작은 것
            self._circle(ex + eye_r*0.18, ey - eye_r*0.28, eye_r*0.13, C_EYE_HL1)

        # ── 볼터치 (분홍 타원) ────────────────────────────────────────────
        for side in (-1, 1):
            bx, by = self._at(hx, hy, ha, r*0.08, side*r*0.78)
            br = r * 0.24
            self.ids.append(cv.create_oval(
                bx-br, by-br*0.6, bx+br, by+br*0.6,
                fill=C_BLUSH, outline=''))

        # ── 열린 입 ───────────────────────────────────────────────────────
        mx, my = self._at(hx, hy, ha, r*0.55, 0)
        mw, mh2 = r*0.34, r*0.22

        # 입 내부 (혀/잇몸 색)
        self.ids.append(cv.create_oval(
            mx-mw, my-mh2, mx+mw, my+mh2,
            fill=C_MOUTH_I, outline=C_MOUTH_L, width=1.5))

        # 윗니 (흰 작은 반원 2개)
        for side in (-1, 1):
            tx2 = mx + side * mw * 0.38
            ty2 = my - mh2 * 0.3
            self._circle(tx2, ty2, mw*0.28, C_TEETH)

    # ── 전체 그리기 ───────────────────────────────────────────────────────────

    def _draw(self):
        cv = self.cv
        for i in self.ids:
            cv.delete(i)
        self.ids = []

        hist  = list(self.hist)
        total = len(hist)
        n     = self.n
        ha    = math.radians(self.heading)

        # ① 다리 (몸체 뒤에 먼저 그림)
        for i in range(n - 1, -1, -1):
            hi = self._all_seg_idx[i]
            if hi >= total:
                continue
            x, y   = hist[hi]
            px, py = hist[max(0, hi - 1)]
            a_rad  = math.atan2(py - y, px - x)
            phase  = math.sin(self.tick * 0.13 - i * 0.65)

            for side in (-1, 1):
                bx, by = self._at(x, y, a_rad, SEG_R*0.1, side*SEG_R*0.90)
                kx, ky = self._at(x, y, a_rad, phase*4,   side*(SEG_R + LEG_LEN*0.55))
                tx2,ty2= self._at(x, y, a_rad, phase*6,   side*(SEG_R + LEG_LEN))
                self.ids.append(cv.create_line(
                    bx, by, kx, ky, tx2, ty2,
                    fill=C_LEG, width=3.5, capstyle='round', smooth=True))
                self._circle(tx2, ty2, 5, C_LEG)

        # ② 몸통 마디 (꼬리→머리 순)
        for i in range(n - 1, -1, -1):
            hi = self._all_seg_idx[i]
            if hi >= total:
                continue
            x, y = hist[hi]

            color = C_BODY_A if i % 2 == 0 else C_BODY_B
            char  = self.word[i] if i < len(self.word) else ''
            self._draw_segment(x, y, SEG_R, color, C_BODY_HL, C_BODY_SH, char)

        # ③ 머리
        hx2, hy2 = hist[0] if hist else (self.hx, self.hy)
        self._draw_head(hx2, hy2, ha)

    # ── 이동 AI ──────────────────────────────────────────────────────────────

    def _update(self):
        self.tick += 1

        if self.steer_cd <= 0:
            self.steer_cd = random.randint(60, 200)
            self.steer    = random.uniform(-1.8, 1.8)
        self.steer_cd -= 1
        self.heading = (self.heading + self.steer) % 360

        a = math.radians(self.heading)
        self.hx += SPEED * math.cos(a)
        self.hy += SPEED * math.sin(a)

        m = MARGIN
        if self.hx < m:
            self.heading = random.uniform(-60, 60);   self.hx = m;          self.steer_cd = 40
        elif self.hx > self.W - m:
            self.heading = random.uniform(120, 240);  self.hx = self.W - m; self.steer_cd = 40
        if self.hy < m:
            self.heading = random.uniform(20, 160);   self.hy = m;          self.steer_cd = 40
        elif self.hy > self.H - m:
            self.heading = random.uniform(200, 340);  self.hy = self.H - m; self.steer_cd = 40

        self.hist.appendleft((self.hx, self.hy))

    # ── 메인 루프 ─────────────────────────────────────────────────────────────

    def _loop(self):
        self._update()
        self._draw()
        self.root.after(16, self._loop)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    words = pick_and_load()
    if words:
        Caterpillar(words)
