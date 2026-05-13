"""
귀여운 캐터필러 데스크탑 펫
- 실행 시 텍스트 파일 선택 → 줄별 단어를 몸통에 표시
- 중국어+숫자+한국어 혼합 행 → 중국어 우선 재배치
- 단클릭 / 15초 경과 : 다음 단어
- 더블클릭 : 파일 재선택
- 우클릭   : 종료
"""
import tkinter as tk
from tkinter import filedialog
import math
import random
from collections import deque

TRANS  = '#FF00FF'
AUTO_S = 15
DBL_MS = 280

# ── 캐터필러 치수 ─────────────────────────────────────────────────────────────
SEG_RX       = 27    # 마디 반너비 (앞뒤)
SEG_RY       = 25    # 마디 반높이 (좌우) — 거의 원형
HEAD_RX      = 34
HEAD_RY      = 32
SEG_SPACE_PX = 43    # 마디 간 거리 (살짝 겹쳐 구슬 엮인 느낌)
LEG_LEN      = 13
SPEED        = 1.5   # 살살 기어다님

# ── 색상 팔레트 ───────────────────────────────────────────────────────────────
C_SEG_A  = '#52B788'   # 마디 A (민트그린)
C_SEG_B  = '#40916C'   # 마디 B (짙은 민트)
C_SEG_HL = '#B7E4C7'   # 마디 하이라이트
C_SEG_SH = '#2D6A4F'   # 마디 윤곽/그림자
C_HEAD   = '#74C69D'   # 머리
C_HEAD_HL= '#D8F3DC'   # 머리 하이라이트
C_HEAD_OL= '#2D6A4F'   # 머리 윤곽
C_LEG    = '#2D6A4F'   # 다리
C_EYE_W  = '#FFFFFF'   # 눈 흰자
C_EYE_P  = '#1B1B2F'   # 동공
C_EYE_SH = '#FFFFFF'   # 눈 반짝이
C_BLUSH  = '#FFB3C6'   # 볼터치 (분홍)
C_SMILE  = '#2D6A4F'   # 미소
C_ANT    = '#2D6A4F'   # 더듬이
C_ANT_TIP= '#FFD166'   # 더듬이 끝 (노랑)
C_LETTER = '#FFFFFF'   # 글자
C_LTR_SH = '#1B4332'   # 글자 그림자


# ══════════════════════════════════════════════════════════════════════════════
# 언어 판별 & 재배치
# ══════════════════════════════════════════════════════════════════════════════

def is_chinese(ch):
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or
            0x3400 <= cp <= 0x4DBF or
            0xF900 <= cp <= 0xFAFF or
            0x20000 <= cp <= 0x2A6DF)

def is_korean(ch):
    cp = ord(ch)
    return (0xAC00 <= cp <= 0xD7AF or
            0x1100 <= cp <= 0x11FF or
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


# ══════════════════════════════════════════════════════════════════════════════
# 파일 선택 & 파싱
# ══════════════════════════════════════════════════════════════════════════════

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
        parent=parent,
        title="단어 파일을 선택하세요",
        filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
    ) or None

def pick_and_load():
    tmp = tk.Tk()
    tmp.withdraw()
    tmp.attributes('-topmost', True)
    path = pick_file(parent=tmp)
    tmp.destroy()
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

        self.hx = self.W / 2.0
        self.hy = self.H / 2.0
        self.heading  = random.uniform(0, 360)
        self.steer    = 0.0
        self.steer_cd = 0
        self.tick     = 0

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
            self.hist.append((self.hx - k * math.cos(a0) * SPEED,
                              self.hy - k * math.sin(a0) * SPEED))

    # ── 자동 전환 ────────────────────────────────────────────────────────────

    def _reset_auto(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
        self._auto_job = self.root.after(AUTO_S * 1000, self._next_word)

    # ── 레이블 ───────────────────────────────────────────────────────────────

    def _lbl(self):
        return (f"  {self.word_idx+1}/{len(self.words)}  "
                f"단클릭·{AUTO_S}초:다음  더블클릭:파일재선택  우클릭:종료  ")

    # ── 클릭 ─────────────────────────────────────────────────────────────────

    def _on_click(self, event):
        if self._clk_job is not None:
            self.root.after_cancel(self._clk_job)
            self._clk_job = None
            self._reload_file()
        else:
            self._clk_job = self.root.after(DBL_MS, self._next_word)

    def _next_word(self):
        self._clk_job  = None
        self.word_idx  = (self.word_idx + 1) % len(self.words)
        self.word      = self.words[self.word_idx]
        self.n         = max(8, len(self.word))
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

    def _at(self, cx, cy, a_rad, dx, dy):
        ca, sa = math.cos(a_rad), math.sin(a_rad)
        return cx + dx*ca - dy*sa, cy + dx*sa + dy*ca

    def _oval_pts(self, cx, cy, a_rad, rx, ry, n=24):
        pts = []
        for k in range(n):
            θ = 2*math.pi*k/n
            pts.extend(self._at(cx, cy, a_rad, rx*math.cos(θ), ry*math.sin(θ)))
        return pts

    def _circle(self, cx, cy, r, fill, outline='', width=0):
        self.ids.append(self.cv.create_oval(
            cx-r, cy-r, cx+r, cy+r, fill=fill, outline=outline, width=width))

    # ── 그리기 ───────────────────────────────────────────────────────────────

    def _draw(self):
        cv = self.cv
        for i in self.ids:
            cv.delete(i)
        self.ids = []

        hist  = list(self.hist)
        total = len(hist)
        n     = self.n

        # ── ① 다리 (몸체 아래) ──────────────────────────────────────────────
        for i in range(n - 1, -1, -1):
            hi = self._all_seg_idx[i]
            if hi >= total:
                continue
            x, y   = hist[hi]
            px, py = hist[max(0, hi-1)]
            a_rad  = math.atan2(py-y, px-x)
            phase  = math.sin(self.tick * 0.13 - i * 0.65)

            for side in (-1, 1):
                # 다리 부착점
                bx, by = self._at(x, y, a_rad, SEG_RX*0.1, side*SEG_RY*0.88)
                # 무릎 (살짝 앞뒤로 흔들림)
                kx, ky = self._at(x, y, a_rad, phase*5, side*(SEG_RY + LEG_LEN*0.6))
                # 발끝 (둥근 발)
                tx, ty = self._at(x, y, a_rad, phase*7, side*(SEG_RY + LEG_LEN))

                self.ids.append(cv.create_line(
                    bx, by, kx, ky, tx, ty,
                    fill=C_LEG, width=4, capstyle='round', smooth=True))
                # 귀여운 둥근 발끝
                self._circle(tx, ty, 5, C_LEG)

        # ── ② 몸통 마디 (꼬리→머리 순) ──────────────────────────────────────
        for i in range(n - 1, -1, -1):
            hi = self._all_seg_idx[i]
            if hi >= total:
                continue
            x, y   = hist[hi]
            px, py = hist[max(0, hi-1)]
            a_rad  = math.atan2(py-y, px-x)

            fill = C_SEG_A if i % 2 == 0 else C_SEG_B

            # 마디 그림자 (살짝 아래 어두운 원)
            sp = self._oval_pts(x+2, y+2, a_rad, SEG_RX, SEG_RY)
            self.ids.append(cv.create_polygon(*sp, fill=C_SEG_SH,
                                              outline='', smooth=True))
            # 마디 본체
            pts = self._oval_pts(x, y, a_rad, SEG_RX, SEG_RY)
            self.ids.append(cv.create_polygon(*pts, fill=fill,
                                              outline=C_SEG_SH, width=1, smooth=True))
            # 하이라이트 (왼쪽 위 느낌)
            hlx = x - math.sin(a_rad) * SEG_RY * 0.28
            hly = y + math.cos(a_rad) * SEG_RY * 0.28
            hl = self._oval_pts(hlx, hly, a_rad, SEG_RX*0.50, SEG_RY*0.42)
            self.ids.append(cv.create_polygon(*hl, fill=C_SEG_HL,
                                              outline='', smooth=True))

            # 글자 그림자 + 글자
            char = self.word[i] if i < len(self.word) else ''
            if char:
                self.ids.append(cv.create_text(
                    x+1, y+1, text=char,
                    font=('맑은 고딕', 16, 'bold'), fill=C_LTR_SH))
                self.ids.append(cv.create_text(
                    x, y, text=char,
                    font=('맑은 고딕', 16, 'bold'), fill=C_LETTER))

        # ── ③ 머리 ───────────────────────────────────────────────────────────
        hx, hy = hist[0] if hist else (self.hx, self.hy)
        ha     = math.radians(self.heading)

        # 머리 그림자
        sp = self._oval_pts(hx+2, hy+2, ha, HEAD_RX, HEAD_RY)
        self.ids.append(cv.create_polygon(*sp, fill=C_SEG_SH,
                                          outline='', smooth=True))
        # 머리 본체
        pts = self._oval_pts(hx, hy, ha, HEAD_RX, HEAD_RY)
        self.ids.append(cv.create_polygon(*pts, fill=C_HEAD,
                                          outline=C_HEAD_OL, width=1, smooth=True))
        # 머리 하이라이트
        hlx = hx - math.sin(ha) * HEAD_RY * 0.28
        hly = hy + math.cos(ha) * HEAD_RY * 0.28
        hl  = self._oval_pts(hlx, hly, ha, HEAD_RX*0.50, HEAD_RY*0.42)
        self.ids.append(cv.create_polygon(*hl, fill=C_HEAD_HL,
                                          outline='', smooth=True))

        # ── 눈 (크고 동그랗고 귀엽게) ────────────────────────────────────────
        eye_r = HEAD_RY * 0.44
        for side in (-1, 1):
            ex, ey = self._at(hx, hy, ha, HEAD_RX*0.18, side*HEAD_RY*0.52)

            # 흰자
            self._circle(ex, ey, eye_r, C_EYE_W, C_SEG_SH, 1)
            # 동공
            self._circle(ex + eye_r*0.12, ey + eye_r*0.10,
                         eye_r*0.55, C_EYE_P)
            # 반짝이 큰 것
            self._circle(ex - eye_r*0.18, ey - eye_r*0.20,
                         eye_r*0.24, C_EYE_SH)
            # 반짝이 작은 것
            self._circle(ex + eye_r*0.20, ey - eye_r*0.28,
                         eye_r*0.12, C_EYE_SH)

        # ── 볼터치 ───────────────────────────────────────────────────────────
        for side in (-1, 1):
            bx, by = self._at(hx, hy, ha, HEAD_RX*0.08, side*HEAD_RY*0.76)
            br = HEAD_RY * 0.21
            self.ids.append(self.cv.create_oval(
                bx-br, by-br*0.65, bx+br, by+br*0.65,
                fill=C_BLUSH, outline='', stipple='gray50'))

        # ── 미소 ─────────────────────────────────────────────────────────────
        # 반원 호 (앞면에 작은 U자)
        smile_pts = []
        for k in range(9):
            t = k / 8
            ang = math.pi + t * math.pi   # 아래 반원
            sdx = HEAD_RX * 0.36 * math.cos(ang)
            sdy = HEAD_RY * 0.22 * math.sin(ang) + HEAD_RY * 0.38
            px2, py2 = self._at(hx, hy, ha, sdx, sdy)
            smile_pts.extend([px2, py2])
        if len(smile_pts) >= 4:
            self.ids.append(cv.create_line(
                *smile_pts, fill=C_SMILE, width=2,
                smooth=True, capstyle='round'))

        # ── 더듬이 ───────────────────────────────────────────────────────────
        sway = math.sin(self.tick * 0.09) * 0.45
        for side in (-1, 1):
            base = self._at(hx, hy, ha, HEAD_RX*0.55, side*HEAD_RY*0.45)
            mid  = self._at(hx, hy, ha,
                            HEAD_RX*0.80 + sway*side*HEAD_RY*0.20,
                            side*(HEAD_RY*0.95 + sway*HEAD_RY*0.15))
            tip  = self._at(hx, hy, ha,
                            HEAD_RX*0.60,
                            side*(HEAD_RY*1.52 + sway*HEAD_RY*0.35))
            self.ids.append(cv.create_line(
                *base, *mid, *tip,
                fill=C_ANT, width=2, smooth=True, capstyle='round'))
            # 더듬이 끝 노란 공
            self._circle(tip[0], tip[1], 5, C_ANT_TIP, C_SEG_SH, 1)

    # ── 이동 AI ──────────────────────────────────────────────────────────────

    def _update(self):
        self.tick += 1

        if self.steer_cd <= 0:
            self.steer_cd = random.randint(60, 210)
            self.steer    = random.uniform(-1.8, 1.8)
        self.steer_cd -= 1
        self.heading = (self.heading + self.steer) % 360

        a = math.radians(self.heading)
        self.hx += SPEED * math.cos(a)
        self.hy += SPEED * math.sin(a)

        m = 150
        if self.hx < m:
            self.heading = random.uniform(-70, 70);  self.hx = m;          self.steer_cd = 40
        elif self.hx > self.W - m:
            self.heading = random.uniform(110, 250); self.hx = self.W - m; self.steer_cd = 40
        if self.hy < m:
            self.heading = random.uniform(15, 165);  self.hy = m;          self.steer_cd = 40
        elif self.hy > self.H - m:
            self.heading = random.uniform(195, 345); self.hy = self.H - m; self.steer_cd = 40

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
