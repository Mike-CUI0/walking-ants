"""
벚꽃 단어 기억 앱
벚꽃이 위에서 떨어져 바닥에 쌓이고 → 쌓인 꽃잎이 텍스트 파일 단어 글자 모양으로 정렬
- 단클릭 / 15초 : 다음 단어
- 더블클릭     : 파일 재선택
- 우클릭       : 종료
"""
import tkinter as tk
from tkinter import filedialog
import math, random, collections

TRANS  = '#FF00FF'
AUTO_S = 15
DBL_MS = 300
FPS    = 60
GRAVITY = 0.18
FLOOR_PAD = 60   # 바닥에서 위로 얼마나 쌓을지 기준

# 상태
S_FALL    = 0   # 벚꽃이 떨어짐
S_PILE    = 1   # 바닥에 쌓인 상태 (뭉쳐있음)
S_FORM    = 2   # 글자 모양으로 정렬 중
S_SHOW    = 3   # 글자 형태 완성 - 보여주는 중
S_SCATTER = 4   # 흩어져서 사라짐

# 벚꽃 색상
PETAL_COLORS = [
    '#FFB7C5', '#FFC4CE', '#FFCCD5',
    '#FFD6DE', '#FFE0E8', '#FF9EB5',
    '#FFA8BC', '#FFB2C3',
]
PETAL_VEIN   = '#FF85A1'
PETAL_SHADOW = '#E8809A'

# 글자 폰트 픽셀 맵 (5×7 bitmap)
# 없는 글자는 박스로 대체 — 실제로는 tkinter canvas text로 글자 위치 계산
# → 꽃잎을 글자 형태로 배치하기 위해 off-screen 캔버스 렌더링 방식 사용

# ──────────────────────────────────────────────────────────────────────────────
# 언어 헬퍼
# ──────────────────────────────────────────────────────────────────────────────
def is_chinese(ch):
    cp = ord(ch)
    return 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF

def is_korean(ch):
    cp = ord(ch)
    return 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F

def reorder_line(line):
    chinese = [c for c in line if is_chinese(c)]
    digits  = [c for c in line if c.isdigit()]
    korean  = [c for c in line if is_korean(c)]
    others  = [c for c in line if not is_chinese(c) and not is_digit_or_korean(c)]
    if chinese and korean:
        return ''.join(chinese + digits + korean + others)
    return line

def is_digit_or_korean(c):
    return c.isdigit() or is_korean(c)

def load_words(path):
    words = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            w = reorder_line(line.strip())
            if w:
                words.append(w)
    return words if words else ['벚꽃']

def pick_and_load():
    tmp = tk.Tk(); tmp.withdraw()
    path = filedialog.askopenfilename(
        title='단어 파일 선택',
        filetypes=[('텍스트 파일','*.txt'),('모든 파일','*.*')]
    )
    tmp.destroy()
    if not path:
        return None
    return load_words(path)

# ──────────────────────────────────────────────────────────────────────────────
# 꽃잎 클래스
# ──────────────────────────────────────────────────────────────────────────────
class Petal:
    """하나의 벚꽃 잎"""
    def __init__(self, W, H):
        self.W = W
        self.H = H
        self._reset_fall()
        self.color   = random.choice(PETAL_COLORS)
        self.size    = random.uniform(10, 18)
        self.rot     = random.uniform(0, math.pi * 2)
        self.vrot    = random.uniform(-0.08, 0.08)
        self.state   = S_FALL
        # 타겟 (글자 모양 위치)
        self.tx = self.x
        self.ty = self.y
        self.tvx = 0.0
        self.tvy = 0.0
        # 더미 위치 (바닥 파일)
        self.pile_x = 0.0
        self.pile_y = 0.0

    def _reset_fall(self):
        self.x  = random.uniform(0, self.W)
        self.y  = random.uniform(-200, -20)
        self.vx = random.uniform(-0.8, 0.8)
        self.vy = random.uniform(0.5, 2.0)
        self.swing_phase = random.uniform(0, math.pi * 2)
        self.swing_freq  = random.uniform(0.02, 0.05)
        self.swing_amp   = random.uniform(0.4, 1.2)

    def step_fall(self, frame):
        """중력 + 좌우 흔들리며 낙하"""
        self.vy += GRAVITY * 0.4
        self.vx += math.sin(frame * self.swing_freq + self.swing_phase) * self.swing_amp * 0.08
        self.vx *= 0.98
        self.x += self.vx
        self.y += self.vy
        self.rot += self.vrot

    def step_pile(self, frame, pile_tx, pile_ty):
        """바닥 더미 위치로 스프링"""
        self.tvx = self.tvx * 0.75 + (pile_tx - self.x) * 0.18
        self.tvy = self.tvy * 0.75 + (pile_ty - self.y) * 0.18
        self.x += self.tvx
        self.y += self.tvy
        self.vrot *= 0.92

    def step_form(self, tx, ty):
        """글자 위치로 스프링 이동"""
        self.tvx = self.tvx * 0.78 + (tx - self.x) * 0.22
        self.tvy = self.tvy * 0.78 + (ty - self.y) * 0.22
        self.x += self.tvx
        self.y += self.tvy
        # 목표 도달 확인
        return abs(self.x - tx) < 2.5 and abs(self.y - ty) < 2.5

    def step_scatter(self):
        """흩어짐 - 중력 + 초기 속도"""
        self.tvy += GRAVITY * 1.5
        self.tvx *= 0.99
        self.x += self.tvx
        self.y += self.tvy
        self.vrot = self.vrot * 0.97 + random.uniform(-0.01, 0.01)
        self.rot += self.vrot * 2

    @property
    def offscreen(self):
        return self.y > self.H + 40 or self.x < -60 or self.x > self.W + 60

    def draw(self, cv, ids):
        """타원형 꽃잎 + 결 그리기"""
        cx, cy = self.x, self.y
        a = self.rot
        L = self.size        # 길이
        W = self.size * 0.55 # 폭

        def rot(lx, ly):
            return cx + lx * math.cos(a) - ly * math.sin(a), \
                   cy + lx * math.sin(a) + ly * math.cos(a)

        # 꽃잎 타원 근사 (8각형)
        pts = []
        for t in range(16):
            angle = t / 16 * math.pi * 2
            lx = W * math.sin(angle) * (1 - 0.15 * (1 - math.cos(angle)))
            ly = L * math.cos(angle)
            sx, sy = rot(lx, ly)
            pts.extend([sx, sy])

        sid = cv.create_polygon(pts, fill=PETAL_SHADOW, outline='', smooth=True)
        ids.append(sid)

        # 그림자 약간 offset
        pts2 = []
        for i in range(0, len(pts), 2):
            pts2.extend([pts[i] + 1.2, pts[i+1] + 1.5])
        s2 = cv.create_polygon(pts2, fill=PETAL_SHADOW, outline='', smooth=True)
        ids.append(s2)

        pid = cv.create_polygon(pts, fill=self.color, outline='', smooth=True)
        ids.append(pid)

        # 중앙 결선
        x0, y0 = rot(0,  L * 0.85)
        x1, y1 = rot(0, -L * 0.85)
        vid = cv.create_line(x0, y0, x1, y1, fill=PETAL_VEIN, width=0.8)
        ids.append(vid)


# ──────────────────────────────────────────────────────────────────────────────
# 글자 픽셀 위치 계산
# ──────────────────────────────────────────────────────────────────────────────
def get_char_petal_positions(chars, W, H, petal_size=14):
    """
    각 글자를 off-screen에 렌더링해서 꽃잎 배치 위치 리스트 반환
    글자 수 = 꽃잎 수
    단어를 화면 하단부 중앙에 배치
    """
    n = len(chars)
    if n == 0:
        return []

    # 글자당 꽃잎 개수 (글자의 '밀도' 느낌)
    petals_per_char = max(6, min(14, 60 // n))
    font_size = max(36, min(72, 420 // n))

    # 각 글자별 중심 위치 계산
    char_spacing = font_size * 1.1
    total_w = char_spacing * n
    start_x = W / 2 - total_w / 2 + char_spacing / 2
    # 바닥에서 font_size + 여백 위치
    base_y = H - FLOOR_PAD - font_size * 0.5

    positions = []
    for i, ch in enumerate(chars):
        cx = start_x + i * char_spacing
        cy = base_y
        # 글자 주변에 꽃잎 배치 (원형 + 중심 클러스터)
        for j in range(petals_per_char):
            # 글자 모양에 맞게: 가로로 약간 넓은 타원형으로 배치
            t = j / petals_per_char * math.pi * 2
            rx = font_size * 0.45 * (0.5 + 0.5 * abs(math.sin(t * 1.3)))
            ry = font_size * 0.52 * (0.5 + 0.5 * abs(math.cos(t * 0.9)))
            px = cx + rx * math.cos(t) + random.uniform(-petal_size * 0.4, petal_size * 0.4)
            py = cy + ry * math.sin(t) + random.uniform(-petal_size * 0.3, petal_size * 0.3)
            positions.append((px, py, i))  # (x, y, char_index)
    return positions, petals_per_char, font_size, start_x, base_y, char_spacing


# ──────────────────────────────────────────────────────────────────────────────
# 메인 장면 클래스
# ──────────────────────────────────────────────────────────────────────────────
class SakuraScene:
    def __init__(self, word, W, H):
        self.word = word
        self.W = W
        self.H = H
        self.frame = 0
        self.state = S_FALL
        self.state_frame = 0

        chars = list(word)
        result = get_char_petal_positions(chars, W, H)
        self.target_positions, self.petals_per_char, self.font_size, \
            self.start_x, self.base_y, self.char_spacing = result

        total_petals = len(self.target_positions)

        # 꽃잎 생성 - 낙하 시작 시간을 분산시킴
        self.petals = []
        for i in range(total_petals):
            p = Petal(W, H)
            p.delay = i * 3 + random.randint(0, 30)  # 순차 낙하
            p.landed = False
            p.formed = False
            p.target_idx = i
            self.petals.append(p)

        # 더미 위치 (글자 아래 중앙에 뭉침)
        self.pile_cx = W / 2
        self.pile_cy = H - FLOOR_PAD + 10

        # 글자 레이블 (SHOW 상태에서만 표시)
        self.show_labels = False
        self.label_alpha = 0  # 0..1 fade in

        # 쌓임 카운터
        self.piled_count = 0
        self.formed_count = 0

    def update(self):
        self.frame += 1
        self.state_frame += 1

        if self.state == S_FALL:
            all_landed = True
            for i, p in enumerate(self.petals):
                if self.frame < p.delay:
                    all_landed = False
                    continue
                if not p.landed:
                    p.step_fall(self.frame)
                    # 바닥 도달
                    if p.y >= self.pile_cy + random.uniform(-15, 15):
                        p.landed = True
                        p.vy = 0; p.vx = 0
                        p.tvx = 0; p.tvy = 0
                    else:
                        all_landed = False

            # 60% 이상 쌓이면 PILE로 전환
            landed_ratio = sum(1 for p in self.petals if p.landed) / len(self.petals)
            if landed_ratio >= 0.6 or (self.state_frame > 180 and landed_ratio > 0.2):
                self.state = S_PILE
                self.state_frame = 0

        elif self.state == S_PILE:
            # 아직 안 착지한 것들은 계속 낙하
            for p in self.petals:
                if not p.landed:
                    p.step_fall(self.frame)
                    if p.y >= self.pile_cy:
                        p.landed = True
                        p.tvx = 0; p.tvy = 0
                else:
                    # 더미 중앙으로 모임 (약간의 랜덤 오프셋)
                    jitter_x = self.pile_cx + random.uniform(-40, 40) * (1 - self.state_frame / 80)
                    jitter_y = self.pile_cy + random.uniform(-8, 8)
                    p.step_pile(self.frame, jitter_x, jitter_y)

            # 1.5초 후 글자 모양으로 전환
            if self.state_frame > 90:
                self.state = S_FORM
                self.state_frame = 0
                # 각 꽃잎에 목표 위치 할당
                for p in self.petals:
                    tx, ty, ci = self.target_positions[p.target_idx]
                    p.form_tx = tx
                    p.form_ty = ty
                    p.tvx = 0; p.tvy = 0

        elif self.state == S_FORM:
            formed = 0
            for p in self.petals:
                if not p.formed:
                    done = p.step_form(p.form_tx, p.form_ty)
                    if done:
                        p.formed = True
                else:
                    formed += 1

            if formed >= len(self.petals) * 0.85 or self.state_frame > 120:
                self.state = S_SHOW
                self.state_frame = 0
                self.show_labels = True

        elif self.state == S_SHOW:
            # 글자 위에서 꽃잎 살랑살랑
            for p in self.petals:
                wobble = math.sin(self.frame * 0.04 + p.target_idx * 0.5) * 0.8
                wobble_y = math.cos(self.frame * 0.035 + p.target_idx * 0.3) * 0.5
                p.x += wobble * 0.1
                p.y += wobble_y * 0.1
                p.rot += p.vrot * 0.3

        elif self.state == S_SCATTER:
            all_off = True
            for p in self.petals:
                if not p.offscreen:
                    p.step_scatter()
                    all_off = False
            return all_off  # True = 완료

        return False

    def scatter(self):
        """다음 단어로 전환 시 흩어지기"""
        self.state = S_SCATTER
        self.state_frame = 0
        center_x = self.W / 2
        center_y = self.H - FLOOR_PAD
        for p in self.petals:
            dx = p.x - center_x
            dy = p.y - center_y
            dist = max(1, math.hypot(dx, dy))
            speed = random.uniform(4, 12)
            p.tvx = dx / dist * speed + random.uniform(-2, 2)
            p.tvy = dy / dist * speed + random.uniform(-4, -1)
            p.vrot = random.uniform(-0.15, 0.15)

    def draw(self, cv, ids):
        # 꽃잎 그리기
        for p in self.petals:
            if self.frame >= p.delay or p.landed:
                p.draw(cv, ids)

        # 글자 라벨 (SHOW 상태)
        if self.show_labels and self.state in (S_SHOW, S_SCATTER):
            chars = list(self.word)
            alpha_val = min(1.0, self.state_frame / 30.0) if self.state == S_SHOW else max(0.0, 1.0 - self.state_frame / 20.0)
            for i, ch in enumerate(chars):
                cx = self.start_x + i * self.char_spacing
                cy = self.base_y
                # 그림자
                sid = cv.create_text(
                    cx + 2, cy + 2,
                    text=ch,
                    font=('맑은 고딕', self.font_size, 'bold'),
                    fill='#CC6688'
                )
                ids.append(sid)
                tid = cv.create_text(
                    cx, cy,
                    text=ch,
                    font=('맑은 고딕', self.font_size, 'bold'),
                    fill='#FF1493'
                )
                ids.append(tid)

        # 추가 낙하 꽃잎 (배경 분위기용)
        # → App 레벨에서 별도 bg_petals로 처리


# ──────────────────────────────────────────────────────────────────────────────
# 배경 낙하 꽃잎 (항상 떨어지는 배경)
# ──────────────────────────────────────────────────────────────────────────────
class BgPetal:
    def __init__(self, W, H):
        self.W = W
        self.H = H
        self.x = random.uniform(0, W)
        self.y = random.uniform(-100, 0)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(0.6, 1.8)
        self.rot = random.uniform(0, math.pi * 2)
        self.vrot = random.uniform(-0.04, 0.04)
        self.size = random.uniform(5, 11)
        self.color = random.choice(PETAL_COLORS[:4])
        self.alpha_color = '#FFD6DE'
        self.swing_phase = random.uniform(0, math.pi * 2)
        self.swing_freq = random.uniform(0.015, 0.04)

    def step(self, frame):
        self.vy += 0.01
        self.vx += math.sin(frame * self.swing_freq + self.swing_phase) * 0.04
        self.vx *= 0.98
        self.x += self.vx
        self.y += self.vy
        self.rot += self.vrot

    def reset(self):
        self.x = random.uniform(0, self.W)
        self.y = random.uniform(-60, -5)
        self.vy = random.uniform(0.6, 1.8)
        self.vx = random.uniform(-0.5, 0.5)

    @property
    def offscreen(self):
        return self.y > self.H + 20

    def draw(self, cv, ids):
        cx, cy = self.x, self.y
        a = self.rot
        L = self.size
        W2 = self.size * 0.5

        pts = []
        for t in range(12):
            angle = t / 12 * math.pi * 2
            lx = W2 * math.sin(angle)
            ly = L * math.cos(angle)
            sx = cx + lx * math.cos(a) - ly * math.sin(a)
            sy = cy + lx * math.sin(a) + ly * math.cos(a)
            pts.extend([sx, sy])

        if len(pts) >= 6:
            pid = cv.create_polygon(pts, fill=self.color, outline='', smooth=True)
            ids.append(pid)


# ──────────────────────────────────────────────────────────────────────────────
# 앱
# ──────────────────────────────────────────────────────────────────────────────
class App:
    def __init__(self, words):
        self.words     = words
        self.word_idx  = 0
        self._clk_job  = None
        self._auto_job = None

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes('-topmost', True)
        self.root.wm_attributes('-transparentcolor', TRANS)

        self.W = self.root.winfo_screenwidth()
        self.H = self.root.winfo_screenheight()
        self.root.geometry(f'{self.W}x{self.H}+0+0')

        self.cv = tk.Canvas(self.root, width=self.W, height=self.H,
                            bg=TRANS, highlightthickness=0)
        self.cv.pack()

        # 배경 꽃잎
        self.bg_petals = [BgPetal(self.W, self.H) for _ in range(35)]
        self.bg_frame  = 0

        # 현재 장면
        self.scene = None
        self._draw_ids = []
        self._make_scene()

        self.cv.bind('<Button-1>',   self._on_click)
        self.cv.bind('<Button-3>',   lambda e: self.root.destroy())

        self._reset_auto()
        self._loop()
        self.root.mainloop()

    def _make_scene(self):
        word = self.words[self.word_idx % len(self.words)]
        self.scene = SakuraScene(word, self.W, self.H)

    def _next_word(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
            self._auto_job = None
        if self.scene and self.scene.state not in (S_SCATTER,):
            self.scene.scatter()
        self.word_idx += 1
        # scatter 완료 후 make_scene은 _loop에서 처리

    def _reset_auto(self):
        if self._auto_job:
            self.root.after_cancel(self._auto_job)
        self._auto_job = self.root.after(AUTO_S * 1000, self._next_word)

    def _on_click(self, e):
        if self._clk_job:
            self.root.after_cancel(self._clk_job)
            self._clk_job = None
            self._reload_file()
        else:
            self._clk_job = self.root.after(DBL_MS, self._single_click)

    def _single_click(self):
        self._clk_job = None
        self._next_word()
        self._reset_auto()

    def _reload_file(self):
        self.root.wm_attributes('-topmost', False)
        path = filedialog.askopenfilename(
            title='단어 파일 선택',
            filetypes=[('텍스트 파일', '*.txt'), ('모든 파일', '*.*')]
        )
        self.root.wm_attributes('-topmost', True)
        if path:
            try:
                self.words    = load_words(path)
                self.word_idx = 0
                if self.scene:
                    self.scene.scatter()
                self.root.after(800, self._make_scene)
            except Exception as ex:
                print(f'파일 오류: {ex}')
        self._reset_auto()

    def _loop(self):
        self.bg_frame += 1

        # 배경 꽃잎 업데이트
        for bp in self.bg_petals:
            bp.step(self.bg_frame)
            if bp.offscreen:
                bp.reset()

        # 장면 업데이트
        scatter_done = False
        if self.scene:
            scatter_done = self.scene.update()

        # scatter 완료 → 새 장면
        if scatter_done:
            self._make_scene()

        # 그리기
        for iid in self._draw_ids:
            try: self.cv.delete(iid)
            except: pass
        self._draw_ids = []

        # 배경 꽃잎
        for bp in self.bg_petals:
            bp.draw(self.cv, self._draw_ids)

        # 메인 장면
        if self.scene:
            self.scene.draw(self.cv, self._draw_ids)

        self.root.after(1000 // FPS, self._loop)


# ──────────────────────────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────────────────────────
def main():
    words = pick_and_load()
    if not words:
        words = ['벚꽃', '봄날', '아름다워']
    App(words)

if __name__ == '__main__':
    main()
