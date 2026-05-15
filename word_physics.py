"""
단어 물리 엔진 — 글자가 공처럼 튀며 기억 앵커가 된다
- 글자마다 개성 다른 물리값(중력·탄성·진동주기)
- ASSEMBLING → BOUNCING → SCATTERING 상태 전환
- 컨트롤 패널: ◀ ■ ⏸ ▶ + 파일열기    우클릭(캔버스) : 종료
"""
import tkinter as tk
from tkinter import filedialog
import math, random, unicodedata

TRANS  = '#FF00FF'
DBL_MS = 300
FPS    = 60

def auto_secs(word):
    n = len(word)
    if n < 10: return 15
    if n < 20: return 20
    if n < 30: return 25
    return 30

# ── 중국어(한자) 판별 ──────────────────────────────────────────────────────────
def is_chinese(ch):
    """CJK 통합한자 범위인지 확인"""
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF or   # CJK Unified Ideographs
        0x3400 <= cp <= 0x4DBF or   # CJK Extension A
        0x20000 <= cp <= 0x2A6DF or # CJK Extension B
        0x2A700 <= cp <= 0x2CEAF or # CJK Extension C/D/E
        0xF900 <= cp <= 0xFAFF or   # CJK Compatibility Ideographs
        0x2F800 <= cp <= 0x2FA1F    # CJK Compatibility Supplement
    )

def extract_chinese(word):
    """단어에서 한자만 추출해 반환"""
    return ''.join(ch for ch in word if is_chinese(ch))

# ── 물리 상수 ─────────────────────────────────────────────────────────────────
GRAVITY       = 0.22
BOUNCE_FLOOR  = 0.80
BOUNCE_WALL   = 0.84
AIR_DAMP      = 0.9985
FLOOR_FRIC    = 0.91
MARGIN        = 70

# ── 상태 ─────────────────────────────────────────────────────────────────────
S_ASSEMBLE = 0
S_BOUNCE   = 1
S_SCATTER  = 2

# ── 글자 색상 팔레트 ───────────────────────────────────────────────────────────
PALETTE = [
    '#FF6B6B', '#FF9F43', '#FFC312', '#A3CB38',
    '#12CBC4', '#1289A7', '#9980FA', '#FDA7DF',
    '#EE5A24', '#009432', '#0652DD', '#833471',
    '#F8EFBA', '#58B19F', '#D63031', '#6C5CE7',
]

# ── 컨트롤 패널 색상 ──────────────────────────────────────────────────────────
PANEL_BG  = '#1a1a2e'
BTN_BG    = '#252545'
BTN_FG    = '#e2e2e2'
BTN_ACT   = '#3a3a6e'
BTN_PAUSE = '#ffcc00'   # 일시정지 시 색상 변경


# ══════════════════════════════════════════════════════════════════════════════
# 파일 로드
# ══════════════════════════════════════════════════════════════════════════════

def load_words(path):
    for enc in ('utf-8', 'utf-8-sig', 'cp949'):
        try:
            with open(path, encoding=enc) as f:
                lines = f.read().splitlines()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return []
    words = [l.strip() for l in lines if l.strip()]
    random.shuffle(words)
    return words

def pick_file(parent=None):
    return filedialog.askopenfilename(
        parent=parent, title="단어 파일 선택",
        filetypes=[("텍스트 파일", "*.txt"), ("모든 파일", "*.*")]
    ) or None

def pick_and_load():
    tmp = tk.Tk(); tmp.withdraw(); tmp.attributes('-topmost', True)
    path = pick_file(parent=tmp); tmp.destroy()
    return load_words(path) if path else []


# ══════════════════════════════════════════════════════════════════════════════
# 글자 공 (Bubble)
# ══════════════════════════════════════════════════════════════════════════════

class Bubble:
    def __init__(self, char, color, radius, W, H):
        self.char   = char
        self.color  = color
        self.radius = radius
        self.W, self.H = W, H

        side = random.randint(0, 3)
        r2   = radius * 3
        if   side == 0: self.x, self.y = random.uniform(0, W), -r2
        elif side == 1: self.x, self.y = W + r2, random.uniform(0, H)
        elif side == 2: self.x, self.y = random.uniform(0, W), H + r2
        else:           self.x, self.y = -r2, random.uniform(0, H)

        self.vx = self.vy = 0.0
        self.tx = self.ty = 0.0

        self.osc_freq  = random.uniform(0.025, 0.065)
        self.osc_amp   = random.uniform(6, 18)
        self.osc_phase = random.uniform(0, math.tau)
        self.bounce_personality = random.uniform(0.88, 1.12)

        self.assembled = False
        self.svx = self.svy = 0.0

    def step_assemble(self):
        self.vx = self.vx * 0.80 + (self.tx - self.x) * 0.20
        self.vy = self.vy * 0.80 + (self.ty - self.y) * 0.20
        self.x += self.vx
        self.y += self.vy
        if math.hypot(self.tx - self.x, self.ty - self.y) < 1.5:
            self.x, self.y = self.tx, self.ty
            self.vx = self.vy = 0.0
            self.assembled = True

    def step_track(self):
        self.vx = self.vx * 0.70 + (self.tx - self.x) * 0.30
        self.vy = self.vy * 0.70 + (self.ty - self.y) * 0.30
        self.x += self.vx
        self.y += self.vy

    def step_scatter(self):
        self.svy += GRAVITY * 1.6
        self.x   += self.svx
        self.y   += self.svy

    @property
    def offscreen(self):
        return self.x < -200 or self.x > self.W + 200 or self.y < -200 or self.y > self.H + 300


# ══════════════════════════════════════════════════════════════════════════════
# 단어 물리 (WordPhysics)
# ══════════════════════════════════════════════════════════════════════════════

class WordPhysics:
    def __init__(self, word, W, H):
        self.word  = word
        self.W, self.H = W, H
        self.n     = len(word)
        self.state = S_ASSEMBLE
        self.frame = 0

        raw_space    = (W - MARGIN * 2) / max(self.n, 1)
        self.spacing = min(68, max(44, int(raw_space * 0.90)))
        self.radius  = min(28, int(self.spacing * 0.44))
        self.font    = ('맑은 고딕', max(10, self.radius - 3), 'bold')

        self.gx  = W / 2
        self.gy  = H * 0.42
        self.gvx = random.uniform(-7, 7)
        self.gvy = random.uniform(-13, -7)

        total_w      = (self.n - 1) * self.spacing
        self.offsets = [(i * self.spacing - total_w / 2) for i in range(self.n)]

        self.bubbles: list[Bubble] = []
        for i, ch in enumerate(word):
            b = Bubble(ch, PALETTE[i % len(PALETTE)], self.radius, W, H)
            b.tx = self.gx + self.offsets[i]
            b.ty = self.gy
            self.bubbles.append(b)

        osc_margin   = int(18 * 0.35) + 10
        self.left_w  = abs(self.offsets[0])  + self.radius + osc_margin
        self.right_w = abs(self.offsets[-1]) + self.radius + osc_margin

        self.word_fits = (self.left_w + self.right_w) <= (W - 2 * MARGIN)

        if self.word_fits:
            self.gx = max(MARGIN + self.left_w,
                          min(W - MARGIN - self.right_w, W / 2))
        else:
            self.gx = MARGIN + self.left_w

    def update(self) -> bool:
        self.frame += 1

        if self.state == S_ASSEMBLE:
            for b in self.bubbles:
                if not b.assembled:
                    b.step_assemble()
            if all(b.assembled for b in self.bubbles):
                self.state = S_BOUNCE
                self.frame = 0

        elif self.state == S_BOUNCE:
            self.gvy += GRAVITY
            self.gvx *= AIR_DAMP
            self.gvy *= AIR_DAMP
            self.gx  += self.gvx
            self.gy  += self.gvy

            r = self.radius
            if self.gy + r > self.H - MARGIN:
                self.gy  = self.H - MARGIN - r
                self.gvy = -abs(self.gvy) * BOUNCE_FLOOR
                self.gvx *= FLOOR_FRIC
                self.gvx += random.uniform(-1.2, 1.2)
            if self.gy - r < MARGIN:
                self.gy  = MARGIN + r
                self.gvy = abs(self.gvy) * BOUNCE_FLOOR
            if self.gx - self.left_w < MARGIN:
                self.gx  = MARGIN + self.left_w
                self.gvx = abs(self.gvx) * BOUNCE_WALL
            if self.gx + self.right_w > self.W - MARGIN:
                self.gx  = self.W - MARGIN - self.right_w
                self.gvx = -abs(self.gvx) * BOUNCE_WALL

            for i, b in enumerate(self.bubbles):
                t   = self.frame * b.osc_freq + b.osc_phase
                ox  = math.sin(t * 1.3) * b.osc_amp * 0.35
                oy  = math.cos(t)       * b.osc_amp
                b.tx = self.gx + self.offsets[i] + ox
                b.ty = self.gy + oy
                b.step_track()
                min_x = MARGIN + self.radius + i * self.spacing
                if b.x < min_x:
                    b.x = min_x
                    if b.vx < 0:
                        b.vx = 0
                b.x = min(self.W - self.radius, b.x)
                b.y = max(MARGIN + self.radius, min(self.H - MARGIN - self.radius, b.y))

        elif self.state == S_SCATTER:
            for b in self.bubbles:
                b.step_scatter()
            if all(b.offscreen for b in self.bubbles):
                return True

        return False

    def scatter(self):
        self.state = S_SCATTER
        cx = sum(b.x for b in self.bubbles) / len(self.bubbles)
        cy = sum(b.y for b in self.bubbles) / len(self.bubbles)
        for b in self.bubbles:
            dx   = b.x - cx
            dy   = b.y - cy
            dist = max(1, math.hypot(dx, dy))
            spd  = random.uniform(12, 26)
            b.svx = dx / dist * spd + random.uniform(-4, 4)
            b.svy = dy / dist * spd - random.uniform(3, 9)

    def draw(self, cv: tk.Canvas, ids: list):
        r = self.radius
        for b in self.bubbles:
            x, y = b.x, b.y
            c    = b.color
            ids.append(cv.create_oval(
                x - r + 4, y - r + 4, x + r + 4, y + r + 4,
                fill='#2A2A2A', outline=''))
            ids.append(cv.create_oval(
                x - r, y - r, x + r, y + r,
                fill=c, outline='white', width=2))
            ids.append(cv.create_text(
                x + 1.5, y + 1.5, text=b.char,
                font=self.font, fill='#444444'))
            ids.append(cv.create_text(
                x, y, text=b.char,
                font=self.font, fill='white'))


# ══════════════════════════════════════════════════════════════════════════════
# 메인 앱
# ══════════════════════════════════════════════════════════════════════════════

class App:
    def __init__(self, words: list[str]):
        self.words    = words
        self.word_idx = 0
        self.paused   = False

        root = tk.Tk()
        self.root = root
        root.overrideredirect(True)
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
        self.physics   = WordPhysics(words[0], self.W, self.H)

        self.cv.bind('<Button-3>', lambda e: root.destroy())

        # ── 컨트롤 패널 프레임 (좌측, H×2/5 지점) ────────────────────────────
        panel_x = 8
        panel_y = int(self.H * 2 / 5)
        self._panel = tk.Frame(root, bg=PANEL_BG,
                               bd=0, relief='flat',
                               padx=4, pady=4)
        self._panel.place(x=panel_x, y=panel_y, anchor='w')

        # 파일 열기 버튼 (첫 행 오른쪽 정렬)
        top_row = tk.Frame(self._panel, bg=PANEL_BG)
        top_row.pack(fill='x', pady=(0, 4))

        tk.Label(top_row, text="", bg=PANEL_BG).pack(side='left', expand=True)
        self._btn_file = self._make_btn(top_row, "📂", self._reload_file,
                                        side='right', padx=2)

        # 버튼 행: ◀  ■  ⏸  ▶
        btn_row = tk.Frame(self._panel, bg=PANEL_BG)
        btn_row.pack()

        self._btn_prev  = self._make_btn(btn_row, "◀", self._prev_word, side='left', padx=2)
        self._btn_stop  = self._make_btn(btn_row, "■", root.destroy,    side='left', padx=2)
        self._btn_pause = self._make_btn(btn_row, "⏸", self._toggle_pause, side='left', padx=2)
        self._btn_next  = self._make_btn(btn_row, "▶", self._next_word_btn, side='left', padx=2)

        # ── 하단 중국어 전용 레이블 ────────────────────────────────────────────
        self._cn_label = tk.Label(root,
            text="",
            bg='#1a1a2e', fg='#FFD700',
            font=('맑은 고딕', 18, 'bold'),
            padx=10, pady=4)
        self._cn_label.place(relx=0.5, y=self.H - 38, anchor='center')
        self._update_cn_label()

        self._reset_auto()
        self._loop()
        root.mainloop()

    # ── 버튼 생성 헬퍼 ──────────────────────────────────────────────────────
    def _make_btn(self, parent, text, cmd, side='left', padx=2):
        btn = tk.Button(parent, text=text, command=cmd,
                        bg=BTN_BG, fg=BTN_FG,
                        activebackground=BTN_ACT, activeforeground=BTN_FG,
                        font=('맑은 고딕', 14),
                        width=2, relief='flat', bd=0,
                        cursor='hand2')
        btn.pack(side=side, padx=padx)
        return btn

    # ── 하단 한자 레이블 업데이트 ────────────────────────────────────────────
    def _update_cn_label(self):
        word = self.words[self.word_idx % len(self.words)]
        cn   = extract_chinese(word)
        self._cn_label.config(text=cn)
        # 한자가 없으면 숨김
        if cn:
            self._cn_label.place(relx=0.5, y=self.H - 38, anchor='center')
        else:
            self._cn_label.place_forget()

    # ── 자동 전환 ────────────────────────────────────────────────────────────
    def _reset_auto(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
        if not self.paused:
            w = self.words[self.word_idx % len(self.words)]
            self._auto_job = self.root.after(auto_secs(w) * 1000, self._next_word)

    # ── 일시정지 토글 ────────────────────────────────────────────────────────
    def _toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            # 자동 타이머 취소, 버튼 강조
            if self._auto_job:
                self.root.after_cancel(self._auto_job)
                self._auto_job = None
            self._btn_pause.config(fg=BTN_PAUSE)
        else:
            self._btn_pause.config(fg=BTN_FG)
            self._reset_auto()

    # ── 이전 단어 ────────────────────────────────────────────────────────────
    def _prev_word(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        self.word_idx = (self.word_idx - 1) % len(self.words)
        self.physics  = WordPhysics(self.words[self.word_idx], self.W, self.H)
        self._update_cn_label()
        self._reset_auto()

    # ── 다음 단어 (버튼) ─────────────────────────────────────────────────────
    def _next_word_btn(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        if self.physics.state != S_SCATTER:
            self.physics.scatter()
        # 실제 교체는 _loop에서 S_SCATTER 완료 후 처리

    # ── 다음 단어 (내부 / 자동) ───────────────────────────────────────────────
    def _next_word(self):
        self._clk_job = None
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        if self.physics.state != S_SCATTER:
            self.physics.scatter()

    # ── 파일 재선택 ──────────────────────────────────────────────────────────
    def _reload_file(self):
        path = pick_file(parent=self.root)
        if not path:
            return
        nw = load_words(path)
        if not nw:
            return
        self.words    = nw
        self.word_idx = 0
        self.physics  = WordPhysics(nw[0], self.W, self.H)
        self._update_cn_label()
        self._reset_auto()

    # ── 그리기 ───────────────────────────────────────────────────────────────
    def _draw(self):
        for i in self.ids:
            self.cv.delete(i)
        self.ids = []
        self.physics.draw(self.cv, self.ids)

    # ── 메인 루프 ─────────────────────────────────────────────────────────────
    def _loop(self):
        if not self.paused:
            done = self.physics.update()

            if done:
                self.word_idx = (self.word_idx + 1) % len(self.words)
                self.physics  = WordPhysics(self.words[self.word_idx], self.W, self.H)
                self._update_cn_label()
                self._reset_auto()

        self._draw()
        self.root.after(1000 // FPS, self._loop)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    words = pick_and_load()
    if words:
        App(words)
