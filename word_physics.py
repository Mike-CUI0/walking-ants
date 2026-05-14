"""
단어 물리 엔진 — 글자가 공처럼 튀며 기억 앵커가 된다
- 글자마다 개성 다른 물리값(중력·탄성·진동주기)
- ASSEMBLING → BOUNCING → SCATTERING 상태 전환
- 단클릭 / 15초 : 다음 단어    더블클릭 : 파일재선택    우클릭 : 종료
"""
import tkinter as tk
from tkinter import filedialog
import math, random

TRANS  = '#FF00FF'
DBL_MS = 300
FPS    = 60

def auto_secs(word):
    n = len(word)
    if n < 10: return 15
    if n < 20: return 20
    if n < 30: return 25
    return 30

# ── 물리 상수 ─────────────────────────────────────────────────────────────────
GRAVITY       = 0.22
BOUNCE_FLOOR  = 0.80    # 바닥 탄성
BOUNCE_WALL   = 0.84    # 벽 탄성
AIR_DAMP      = 0.9985  # 공기저항
FLOOR_FRIC    = 0.91    # 바닥 마찰
MARGIN        = 70      # 화면 경계

# ── 상태 ─────────────────────────────────────────────────────────────────────
S_ASSEMBLE = 0   # 글자들이 날아와 단어 완성
S_BOUNCE   = 1   # 단어가 튀어다님
S_SCATTER  = 2   # 글자들이 폭발하며 흩어짐

# ── 글자 색상 팔레트 (위치별 고정 → 색-위치 기억 강화) ───────────────────────
PALETTE = [
    '#FF6B6B', '#FF9F43', '#FFC312', '#A3CB38',
    '#12CBC4', '#1289A7', '#9980FA', '#FDA7DF',
    '#EE5A24', '#009432', '#0652DD', '#833471',
    '#F8EFBA', '#58B19F', '#D63031', '#6C5CE7',
]


# ══════════════════════════════════════════════════════════════════════════════
# 언어 헬퍼
# ══════════════════════════════════════════════════════════════════════════════

def load_words(path):
    for enc in ('utf-8','utf-8-sig','cp949'):
        try:
            with open(path, encoding=enc) as f:
                lines = f.read().splitlines()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        return []
    words = [l.strip() for l in lines if l.strip()]
    random.shuffle(words)   # 랜덤 순서로 로드
    return words

def pick_file(parent=None):
    return filedialog.askopenfilename(
        parent=parent, title="단어 파일 선택",
        filetypes=[("텍스트 파일","*.txt"),("모든 파일","*.*")]
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

        # 시작 위치: 화면 바깥 랜덤 가장자리
        side = random.randint(0, 3)
        r2   = radius * 3
        if   side == 0: self.x, self.y = random.uniform(0,W), -r2
        elif side == 1: self.x, self.y = W+r2, random.uniform(0,H)
        elif side == 2: self.x, self.y = random.uniform(0,W), H+r2
        else:           self.x, self.y = -r2, random.uniform(0,H)

        self.vx = self.vy = 0.0

        # 목표 위치 (나중에 설정)
        self.tx = self.ty = 0.0

        # 개성 있는 물리값 (글자마다 다름 → 움직임이 기억 앵커)
        self.osc_freq = random.uniform(0.025, 0.065)   # 진동 주기
        self.osc_amp  = random.uniform(6, 18)           # 진동 폭
        self.osc_phase= random.uniform(0, math.tau)     # 위상
        self.bounce_personality = random.uniform(0.88, 1.12)  # 탄성 개성

        self.assembled  = False
        # scatter 전용
        self.svx = self.svy = 0.0

    # ── ASSEMBLING: 목표 위치로 스프링 수렴 ──────────────────────────────────
    def step_assemble(self):
        self.vx = self.vx * 0.80 + (self.tx - self.x) * 0.20
        self.vy = self.vy * 0.80 + (self.ty - self.y) * 0.20
        self.x += self.vx
        self.y += self.vy
        if math.hypot(self.tx-self.x, self.ty-self.y) < 1.5:
            self.x, self.y = self.tx, self.ty
            self.vx = self.vy = 0.0
            self.assembled = True

    # ── BOUNCING: 진동하는 목표 추적 ──────────────────────────────────────────
    def step_track(self):
        self.vx = self.vx * 0.70 + (self.tx - self.x) * 0.30
        self.vy = self.vy * 0.70 + (self.ty - self.y) * 0.30
        self.x += self.vx
        self.y += self.vy

    # ── SCATTERING: 자유낙하 + 폭발 ──────────────────────────────────────────
    def step_scatter(self):
        self.svy += GRAVITY * 1.6
        self.x   += self.svx
        self.y   += self.svy

    @property
    def offscreen(self):
        return self.x<-200 or self.x>self.W+200 or self.y<-200 or self.y>self.H+300


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

        # 단어 길이에 맞게 크기 조절
        raw_space   = (W - MARGIN*2) / max(self.n, 1)
        self.spacing = min(68, max(44, int(raw_space * 0.90)))
        self.radius  = min(28, int(self.spacing * 0.44))
        self.font    = ('맑은 고딕', max(10, self.radius - 3), 'bold')

        # 그룹 앵커 (단어 전체가 하나로 움직임)
        self.gx  = W / 2
        self.gy  = H * 0.42
        self.gvx = random.uniform(-7, 7)
        self.gvy = random.uniform(-13, -7)   # 강한 위쪽 킥

        # 각 글자의 그룹 내 상대 오프셋 (수평 배열)
        total_w      = (self.n - 1) * self.spacing
        self.offsets = [(i * self.spacing - total_w/2) for i in range(self.n)]

        # 글자 공 생성
        self.bubbles: list[Bubble] = []
        for i, ch in enumerate(word):
            b = Bubble(ch, PALETTE[i % len(PALETTE)], self.radius, W, H)
            b.tx = self.gx + self.offsets[i]
            b.ty = self.gy
            self.bubbles.append(b)

        # 벽 계산: 진동 폭(osc_amp*0.35 최대 ≈7px) + 여유
        osc_margin   = int(18 * 0.35) + 10
        self.left_w  = abs(self.offsets[0])  + self.radius + osc_margin
        self.right_w = abs(self.offsets[-1]) + self.radius + osc_margin

        # 단어가 화면 안에 들어오는지 여부
        self.word_fits = (self.left_w + self.right_w) <= (W - 2 * MARGIN)

        # 시작 gx: 왼쪽 기준으로 클램프 (왼쪽 우선)
        if self.word_fits:
            self.gx = max(MARGIN + self.left_w,
                          min(W - MARGIN - self.right_w, W / 2))
        else:
            # 단어가 너무 길면 왼쪽 정렬 시작 (오른쪽 중복 허용)
            self.gx = MARGIN + self.left_w

    # ── 상태 업데이트 → True 반환 시 다음 단어로 전환 ──────────────────────────
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
            # 그룹 물리
            self.gvy += GRAVITY
            self.gvx *= AIR_DAMP
            self.gvy *= AIR_DAMP
            self.gx  += self.gvx
            self.gy  += self.gvy

            r = self.radius
            # 바닥
            if self.gy + r > self.H - MARGIN:
                self.gy  = self.H - MARGIN - r
                self.gvy = -abs(self.gvy) * BOUNCE_FLOOR
                self.gvx *= FLOOR_FRIC
                self.gvx += random.uniform(-1.2, 1.2)
            # 천장
            if self.gy - r < MARGIN:
                self.gy  = MARGIN + r
                self.gvy = abs(self.gvy) * BOUNCE_FLOOR
            # 왼쪽 벽: 항상 강제 — 첫 글자 절대 잘리지 않음
            if self.gx - self.left_w < MARGIN:
                self.gx  = MARGIN + self.left_w
                self.gvx = abs(self.gvx) * BOUNCE_WALL
            # 오른쪽 벽: 항상 반사
            if self.gx + self.right_w > self.W - MARGIN:
                self.gx  = self.W - MARGIN - self.right_w
                self.gvx = -abs(self.gvx) * BOUNCE_WALL

            # 각 글자: 위상 다른 진동으로 개성 있게 흔들림
            for i, b in enumerate(self.bubbles):
                t   = self.frame * b.osc_freq + b.osc_phase
                ox  = math.sin(t * 1.3) * b.osc_amp * 0.35
                oy  = math.cos(t)       * b.osc_amp
                b.tx = self.gx + self.offsets[i] + ox
                b.ty = self.gy + oy
                b.step_track()
                # 왼쪽: 모든 글자가 하나씩 반드시 보이도록 — 속도도 함께 제거
                if b.x < MARGIN + self.radius:
                    b.x  = MARGIN + self.radius
                    if b.vx < 0:
                        b.vx = 0
                # 오른쪽: 화면 밖으로만 안 나가게 (겹침 허용)
                b.x = min(self.W - self.radius, b.x)
                b.y = max(MARGIN + self.radius, min(self.H - MARGIN - self.radius, b.y))

        elif self.state == S_SCATTER:
            for b in self.bubbles:
                b.step_scatter()
            if all(b.offscreen for b in self.bubbles):
                return True   # ← 다음 단어 신호

        return False

    def scatter(self):
        """폭발 흩어짐 시작"""
        self.state = S_SCATTER
        cx = sum(b.x for b in self.bubbles) / len(self.bubbles)
        cy = sum(b.y for b in self.bubbles) / len(self.bubbles)
        for b in self.bubbles:
            dx   = b.x - cx
            dy   = b.y - cy
            dist = max(1, math.hypot(dx, dy))
            spd  = random.uniform(12, 26)
            b.svx = dx/dist * spd + random.uniform(-4, 4)
            b.svy = dy/dist * spd - random.uniform(3, 9)   # 위로 날아오름

    def draw(self, cv: tk.Canvas, ids: list):
        r = self.radius
        for b in self.bubbles:
            x, y = b.x, b.y
            c    = b.color

            # 그림자
            ids.append(cv.create_oval(
                x-r+4, y-r+4, x+r+4, y+r+4,
                fill='#2A2A2A', outline=''))

            # 메인 원
            ids.append(cv.create_oval(
                x-r, y-r, x+r, y+r,
                fill=c, outline='white', width=2))

            # 글자 그림자
            ids.append(cv.create_text(
                x+1.5, y+1.5, text=b.char,
                font=self.font, fill='#444444'))

            # 글자 본체 (흰색)
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

        self.ids      = []
        self._clk_job = None
        self._auto_job= None
        self.physics  = WordPhysics(words[0], self.W, self.H)

        self.cv.bind('<Button-1>', self._on_click)
        self.cv.bind('<Button-3>', lambda e: root.destroy())

        self._reset_auto()
        self._loop()
        root.mainloop()

    # ── 자동 전환 ────────────────────────────────────────────────────────────

    def _reset_auto(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
        w = self.words[self.word_idx % len(self.words)]
        self._auto_job = self.root.after(auto_secs(w) * 1000, self._next_word)

    # ── 클릭 ─────────────────────────────────────────────────────────────────

    def _on_click(self, event):
        if self._clk_job is not None:
            self.root.after_cancel(self._clk_job)
            self._clk_job = None
            self._reload_file()
        else:
            self._clk_job = self.root.after(DBL_MS, self._next_word)

    # ── 단어 전환 ────────────────────────────────────────────────────────────

    def _next_word(self):
        self._clk_job = None
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        if self.physics.state != S_SCATTER:
            self.physics.scatter()
        # 실제 단어 교체는 _loop에서 S_SCATTER 완료 감지 시 처리

    # ── 파일 재선택 ──────────────────────────────────────────────────────────

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
        self.physics  = WordPhysics(nw[0], self.W, self.H)
        self._reset_auto()

    # ── 그리기 ───────────────────────────────────────────────────────────────

    def _draw(self):
        for i in self.ids:
            self.cv.delete(i)
        self.ids = []
        self.physics.draw(self.cv, self.ids)

    # ── 메인 루프 ─────────────────────────────────────────────────────────────

    def _loop(self):
        done = self.physics.update()

        if done:  # S_SCATTER 완료 → 다음 단어
            self.word_idx = (self.word_idx + 1) % len(self.words)
            self.physics  = WordPhysics(self.words[self.word_idx], self.W, self.H)
            self._reset_auto()

        self._draw()
        self.root.after(1000 // FPS, self._loop)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    words = pick_and_load()
    if words:
        App(words)
