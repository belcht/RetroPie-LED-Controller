#!/usr/bin/env python3
"""
RetroLED — Arcade-styled LED controller for RetroPie and Batocera.
Connects to LEDControl.py via WebSocket for live LED visualization and control.
"""

import sys
import math
import struct
import json
import queue
import threading
import time
from pathlib import Path
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli  (Python < 3.11)
    except ImportError:
        tomllib = None

import pygame

# ────────────────────────────────────────────────
# WebSocket client (optional)
# Prefer system websockets; fall back to vendored copy bundled with RetroLED
# ────────────────────────────────────────────────
_vendor = Path(__file__).parent / 'vendor'
if _vendor.exists() and str(_vendor) not in sys.path:
    sys.path.insert(0, str(_vendor))

try:
    import asyncio
    import websockets
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False

WS_URL     = "ws://127.0.0.1:8765"
WS_TIMEOUT = 3.0

# ────────────────────────────────────────────────
# Platform detection
# ────────────────────────────────────────────────
def detect_platform():
    if Path('/userdata/system').exists():
        return 'batocera', Path('/userdata/system/ledcontrol.toml')
    if Path('/home/pi/LEDControl').exists():
        return 'retropie', Path('/home/pi/ledcontrol.toml')
    return 'desktop', Path.home() / 'ledcontrol.toml'

PLATFORM, CONFIG_PATH = detect_platform()
FULLSCREEN = (PLATFORM in ('retropie', 'batocera')) or '--fullscreen' in sys.argv

# ────────────────────────────────────────────────
# Cabinet image — LED overlay coordinates
# Fractions of the cabinet image dimensions.
# Tune these if your artwork changes.
# ────────────────────────────────────────────────
CABINET_LED_Y  = 0.36   # LED row vertical position (fraction of cabinet height)
CABINET_LED_X1 = 0.08   # LED row left edge  (fraction of cabinet width)
CABINET_LED_X2 = 0.92   # LED row right edge (fraction of cabinet width)

# ────────────────────────────────────────────────
# Arcade colour palette
# ────────────────────────────────────────────────
BLACK      = (  0,   0,   0)
WHITE      = (255, 255, 255)
DIM_WHITE  = (160, 160, 160)
ORANGE     = (255, 140,   0)
GOLD       = (255, 200,   0)
RED_BORDER = (200,  30,  10)

ROW_COLORS = [
    (255,  60,  60),
    (255, 255, 255),
    (255, 220,   0),
    ( 60, 255,  60),
    ( 60, 255, 255),
    (255, 120, 200),
]

# ────────────────────────────────────────────────
# Menu definitions
# ────────────────────────────────────────────────
ANIMATIONS = [
    ('kitt',        'KITT SCANNER'),
    ('cylon',       'CYLON EYE'),
    ('glow',        'GLOW PULSE'),
    ('centerpulse', 'CENTER PULSE'),
    ('meteor',      'METEOR SHOWER'),
    ('twinkle',     'TWINKLE SPARKLES'),
    ('cycle',       'COLOR CYCLE'),
    ('rainbow',     'RAINBOW WAVE'),
    ('',            'SOLID COLOR'),
    ('off',         'LEDS OFF'),
]

COLORS = [
    ('red',    'RED',    (220,  40,  40)),
    ('orange', 'ORANGE', (255, 100,   0)),
    ('yellow', 'YELLOW', (220, 220,   0)),
    ('green',  'GREEN',  ( 30, 200,  30)),
    ('cyan',   'CYAN',   (  0, 200, 200)),
    ('blue',   'BLUE',   ( 40,  80, 220)),
    ('purple', 'PURPLE', (120,   0, 180)),
    ('pink',   'PINK',   (220,  60, 160)),
    ('white',  'WHITE',  (220, 220, 220)),
]

# ────────────────────────────────────────────────
# Sound generation (no numpy required)
# ────────────────────────────────────────────────
SAMPLE_RATE = 22050
CHANNELS    = 2

def _tone_bytes(freq: float, ms: int, vol: float = 0.35, decay: float = 0.6) -> bytes:
    """Square wave tone — the harsh chunky sound of classic arcade hardware."""
    n = int(SAMPLE_RATE * ms / 1000)
    buf = bytearray(n * 4)
    for i in range(n):
        env = max(0.0, 1.0 - (i / n) * decay)
        # Square wave: sign of sine
        raw = 1.0 if math.sin(2 * math.pi * freq * i / SAMPLE_RATE) >= 0 else -1.0
        val = int(vol * env * 32767 * raw)
        val = max(-32768, min(32767, val))
        struct.pack_into('<hh', buf, i * 4, val, val)
    return bytes(buf)

def _concat_bytes(*parts: bytes) -> bytes:
    return b''.join(parts)

def make_sounds() -> dict:
    try:
        pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=CHANNELS, buffer=512)
        return {
            # Short low blip — DK footstep feel
            'nav':    pygame.mixer.Sound(buffer=_tone_bytes(220, 38, vol=0.22, decay=1.0)),
            # Rising two-tone — like DK jump
            'select': pygame.mixer.Sound(buffer=_concat_bytes(
                          _tone_bytes(330, 55, vol=0.30, decay=0.8),
                          _tone_bytes(523, 75, vol=0.34, decay=0.7))),
            # Descending two-tone — reverse jump
            'back':   pygame.mixer.Sound(buffer=_concat_bytes(
                          _tone_bytes(523, 55, vol=0.30, decay=0.8),
                          _tone_bytes(262, 75, vol=0.26, decay=0.7))),
            # 4-note ascending arpeggio — DK bonus/points sound (C-E-G-C)
            'save':   pygame.mixer.Sound(buffer=_concat_bytes(
                          _tone_bytes(262, 55, vol=0.30, decay=0.6),
                          _tone_bytes(330, 55, vol=0.32, decay=0.6),
                          _tone_bytes(392, 55, vol=0.34, decay=0.6),
                          _tone_bytes(523, 90, vol=0.36, decay=0.5))),
            # Low square buzz — DK death/error feel
            'error':  pygame.mixer.Sound(buffer=_concat_bytes(
                          _tone_bytes(110, 80,  vol=0.35, decay=0.3),
                          _tone_bytes(98,  80,  vol=0.35, decay=0.3),
                          _tone_bytes(82,  120, vol=0.35, decay=0.2))),
            # Tiny tick — DK UI click
            'adjust': pygame.mixer.Sound(buffer=_tone_bytes(440, 28, vol=0.18, decay=1.0)),
        }
    except Exception as e:
        print(f"Sound init failed: {e}", file=sys.stderr)
        return {}

# ────────────────────────────────────────────────
# WebSocket client thread
# ────────────────────────────────────────────────
class WSClient:
    def __init__(self):
        self.pixel_queue = queue.SimpleQueue()
        self.connected   = False
        self._send_queue = queue.SimpleQueue()
        self._stop       = False
        threading.Thread(target=self._run, daemon=True).start()

    def send(self, data: dict):
        self._send_queue.put(data)

    def stop(self):
        self._stop = True

    def _run(self):
        if not WS_AVAILABLE:
            return
        try:
            asyncio.run(self._async_run())
        except Exception:
            pass

    async def _async_run(self):
        try:
            async with websockets.connect(WS_URL, ping_interval=20,
                                          open_timeout=WS_TIMEOUT) as ws:
                self.connected = True
                recv = asyncio.create_task(self._recv(ws))
                send = asyncio.create_task(self._send_loop(ws))
                stop = asyncio.create_task(self._watch_stop())
                done, pending = await asyncio.wait(
                    [recv, send, stop], return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
        except Exception:
            pass
        finally:
            self.connected = False

    async def _recv(self, ws):
        async for msg in ws:
            try:
                data = json.loads(msg)
                if data.get('type') == 'pixels':
                    self.pixel_queue.put(data['data'])
            except Exception:
                pass

    async def _send_loop(self, ws):
        while True:
            if not self._send_queue.empty():
                try:
                    await ws.send(json.dumps(self._send_queue.get_nowait()))
                except Exception:
                    break
            await asyncio.sleep(0.01)

    async def _watch_stop(self):
        while not self._stop:
            await asyncio.sleep(0.1)

# ────────────────────────────────────────────────
# LED glow rendering
# ────────────────────────────────────────────────
_glow_cache: dict = {}

def _glow_surf(radius: int, color: tuple) -> pygame.Surface:
    """Glow ring only — transparent hole in the center the size of the LED.
    Blit with BLEND_ADD, then draw the solid core circle separately."""
    key = (radius, color)
    if key in _glow_cache:
        return _glow_cache[key]
    glow_reach = radius // 2
    size = (radius + glow_reach) * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    cx = size // 2
    # Glow rings from outer to inner, fading in
    for step in range(3, 0, -1):
        gr    = radius + int(glow_reach * step / 3)
        alpha = int(64 * step / 3)
        pygame.draw.circle(surf, (*color, alpha), (cx, cx), gr)
    # Punch out the center — transparent hole the exact size of the LED circle
    pygame.draw.circle(surf, (0, 0, 0, 0), (cx, cx), radius)
    _glow_cache[key] = surf
    return surf

# ────────────────────────────────────────────────
# Font helpers
# ────────────────────────────────────────────────
_font_cache: dict = {}

def get_font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        font_path = Path(__file__).parent / 'assets' / 'PressStart2P.ttf'
        if font_path.exists():
            _font_cache[size] = pygame.font.Font(str(font_path), size)
        else:
            _font_cache[size] = pygame.font.SysFont('courier', size, bold=True)
    return _font_cache[size]

def draw_text(surface, text, size, color, cx, cy, anchor='center'):
    font = get_font(size)
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if anchor == 'center': rect.center   = (cx, cy)
    elif anchor == 'left': rect.midleft  = (cx, cy)
    elif anchor == 'right':rect.midright = (cx, cy)
    surface.blit(surf, rect)
    return rect

# ────────────────────────────────────────────────
# Config loading
# ────────────────────────────────────────────────
def _hsv_to_rgb(h: int, s: float, v: float) -> tuple:
    """h 0-359, s/v 0-1. Returns (r, g, b) 0-255."""
    h = h % 360
    hi = h // 60
    f  = (h / 60.0) - hi
    p  = v * (1 - s)
    q  = v * (1 - s * f)
    t  = v * (1 - s * (1 - f))
    rgb = [(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][hi]
    return tuple(int(c * 255) for c in rgb)

def load_toml(path: Path) -> dict:
    if tomllib is None:
        return {}
    try:
        with open(path, 'rb') as f:
            return tomllib.load(f)
    except Exception:
        return {}

# ────────────────────────────────────────────────
# Main app
# ────────────────────────────────────────────────
class RetroLED:
    BOOT         = 'boot'       # faux ROM/RAM flash screens
    DIAG         = 'diag'       # CPU OK / RAM OK messages
    SPLASH       = 'splash'     # full title splash + press start
    CONNECTING   = 'connecting'
    ERROR        = 'error'
    MAIN         = 'main'
    ANIM_SELECT  = 'anim_select'
    COLOR_SELECT = 'color_select'

    # Boot sequence timing (seconds)
    BOOT_DURATION   = 1.0   # flashing ROM screens
    DIAG_DURATION   = 1.0   # diagnostic messages
    SPLASH_DURATION = 1.2   # splash (then connect attempt continues in bg)

    DIAG_MESSAGES = [
        ('RAM TEST', (60, 255, 60)),
        ('RAM  OK',  (60, 255, 60)),
        ('ROM TEST', (255, 220, 0)),
        ('ROM  OK',  (255, 220, 0)),
        ('CPU  OK',  (60, 255, 255)),
        ('I/O  OK',  (255, 120, 200)),
        ('BOOTING',  (255, 255, 255)),
    ]

    MAIN_ITEMS = [
        ('animation', 'SET ANIMATION'),
        ('color',     'SET COLOR'),
        ('brightness','BRIGHTNESS'),
        ('flip',      'FLIP STRIP'),
        ('off',       'LEDS OFF'),
        ('exit',      'EXIT'),
    ]

    def __init__(self):
        pygame.init()
        self.sounds = make_sounds()

        if FULLSCREEN:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((960, 720))

        pygame.display.set_caption('RetroLED')
        pygame.mouse.set_visible(False)

        self.W, self.H = self.screen.get_size()
        self.clock = pygame.time.Clock()

        # Config
        self.cfg       = load_toml(CONFIG_PATH)
        hw             = self.cfg.get('hardware', {})
        self.num_leds  = hw.get('num_leds', 14)
        gen            = self.cfg.get('general', {})
        self.brightness    = gen.get('global_brightness', 1.0)
        self.cur_animate   = gen.get('default_animate', 'kitt')
        self.cur_color     = gen.get('default_color', 'red')
        self.flip_strip    = gen.get('flip_strip', False)
        ui             = self.cfg.get('ui', {})
        self.btn_sel   = ui.get('btn_select', [0, 2, 9, 11])   # A/Start on RetroPie(0,9) + Batocera(11,2)
        self.btn_back  = ui.get('btn_back',   [1, 8, 10, 3])  # B/Select on RetroPie(1,8) + Batocera(10,3)
        self.preview_animate = self.cur_animate
        self.preview_color   = self.cur_color

        # Menu state
        self.state       = self.BOOT
        self.main_idx    = 0
        self.anim_idx    = self._anim_index(self.cur_animate)
        self.color_idx   = self._color_index(self.cur_color)
        self.scroll_off  = 0
        self.error_msg   = ''

        # Boot sequence
        self._boot_start       = time.monotonic()
        self._splash_title     = None
        self._splash_confirmed = False

        # Assets
        self.title_img             = self._load_title()
        self.cabinet_img           = None
        self.cabinet_rect          = None
        self.menu_top              = int(self.H * 0.60)  # updated after cabinet loads
        self._load_cabinet()

        # WebSocket
        self.ws             = WSClient()
        self.pixel_data     = [[0, 0, 0]] * self.num_leds
        self._connect_start = time.monotonic()

        # Joystick
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

        # UI helpers
        self._scanlines = self._make_scanlines()
        self._blink     = True
        self._blink_t   = time.monotonic()

    # ── Asset loading ─────────────────────────────

    def _load_title(self):
        for name in ('title.png', 'title.jpg'):
            path = Path(__file__).parent / 'assets' / 'images' / name
            if path.exists():
                try:
                    img   = pygame.image.load(str(path)).convert_alpha()
                    max_w = int(self.W * 0.45)
                    max_h = int(self.H * 0.096)
                    scale = min(max_w / img.get_width(), max_h / img.get_height(), 1.0)
                    return pygame.transform.smoothscale(
                        img, (int(img.get_width() * scale), int(img.get_height() * scale)))
                except Exception as e:
                    print(f"Could not load title: {e}", file=sys.stderr)
        return None

    def _load_cabinet(self):
        for name in ('cabinet.png', 'cabinet.jpg'):
            path = Path(__file__).parent / 'assets' / 'images' / name
            if path.exists():
                try:
                    img   = pygame.image.load(str(path)).convert_alpha()
                    # Scale to fit: fill screen width, cap height at 44% of screen
                    max_w = int(self.W * 0.98)
                    max_h = int(self.H * 0.42)
                    scale = min(max_w / img.get_width(), max_h / img.get_height())
                    w = int(img.get_width()  * scale)
                    h = int(img.get_height() * scale)
                    self.cabinet_img  = pygame.transform.smoothscale(img, (w, h))
                    # Position: centered horizontally, below title
                    title_h = self.title_img.get_height() if self.title_img else int(self.H * 0.12)
                    cab_y   = int(self.H * 0.03) + title_h + int(self.H * 0.02)
                    self.cabinet_rect = pygame.Rect((self.W - w) // 2, cab_y, w, h)
                    self.menu_top     = self.cabinet_rect.bottom + int(self.H * 0.03)
                    return
                except Exception as e:
                    print(f"Could not load cabinet: {e}", file=sys.stderr)

    def _make_scanlines(self) -> pygame.Surface:
        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for y in range(0, self.H, 4):
            pygame.draw.line(surf, (0, 0, 0, 30), (0, y), (self.W, y))
        return surf

    # ── Helpers ───────────────────────────────────

    def _play(self, name: str):
        snd = self.sounds.get(name)
        if snd:
            snd.play()

    def _anim_index(self, key: str) -> int:
        for i, (k, _) in enumerate(ANIMATIONS):
            if k == key: return i
        return 0

    def _color_index(self, key: str) -> int:
        for i, (k, _, _) in enumerate(COLORS):
            if k == key: return i
        return 0

    def _save_setting(self, section: str, key: str, value: str):
        """Write a single key to the TOML config file."""
        try:
            import re as _re
            with open(CONFIG_PATH, 'r') as f:
                content = f.read()
            sec_re = _re.compile(r'(\[' + _re.escape(section) + r'\].*?)(?=\n\[|\Z)', _re.DOTALL)
            key_re = _re.compile(r'^' + _re.escape(key) + r'\s*=.*$', _re.MULTILINE)
            m = sec_re.search(content)
            if m:
                sec = m.group(1)
                new_sec = key_re.sub(f'{key} = {value}', sec) if key_re.search(sec) \
                          else sec.rstrip('\n') + f'\n{key} = {value}'
                content = content[:m.start()] + new_sec + content[m.end():]
            else:
                content = content.rstrip('\n') + f'\n\n[{section}]\n{key} = {value}\n'
            with open(CONFIG_PATH, 'w') as f:
                f.write(content)
        except Exception as e:
            print(f"Config save failed: {e}", file=sys.stderr)

    def _send_preview(self, animate: str, color: str, save: bool = False):
        self.ws.send({
            'cmd':        'set',
            'animate':    animate,
            'color':      color,
            'brightness': self.brightness,
            'save':       save,
        })

    def _max_visible(self) -> int:
        """How many menu rows fit in the available menu area."""
        avail = int(self.H * 0.92) - self.menu_top
        return max(4, avail // max(1, int(self.H * 0.078)))

    def _clamp_scroll(self, idx: int, items_len: int):
        mv = self._max_visible()
        if idx < self.scroll_off:
            self.scroll_off = idx
        elif idx >= self.scroll_off + mv:
            self.scroll_off = idx - mv + 1
        self.scroll_off = max(0, min(self.scroll_off, max(0, items_len - mv)))

    # ── Input ─────────────────────────────────────

    def handle_events(self):
        up = down = left = right = sel = back = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()
            elif event.type == pygame.KEYDOWN:
                if   event.key in (pygame.K_UP,    pygame.K_w):     up    = True
                elif event.key in (pygame.K_DOWN,  pygame.K_s):     down  = True
                elif event.key in (pygame.K_LEFT,  pygame.K_a):     left  = True
                elif event.key in (pygame.K_RIGHT, pygame.K_d):     right = True
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z): sel  = True
                elif event.key in (pygame.K_ESCAPE, pygame.K_x):    back  = True
                elif event.key == pygame.K_q:                        self._quit()
            elif event.type == pygame.JOYHATMOTION:
                hx, hy = event.value
                if  hy ==  1: up    = True
                if  hy == -1: down  = True
                if  hx == -1: left  = True
                if  hx ==  1: right = True
            elif event.type == pygame.JOYAXISMOTION:
                if   event.axis == 1:
                    if   event.value < -0.5: up    = True
                    elif event.value >  0.5: down  = True
                elif event.axis == 0:
                    if   event.value < -0.5: left  = True
                    elif event.value >  0.5: right = True
            elif event.type == pygame.JOYBUTTONDOWN:
                if   event.button in self.btn_sel:  sel  = True
                elif event.button in self.btn_back: back = True

        if   self.state == self.BOOT:         pass  # no input during boot flash
        elif self.state == self.DIAG:         pass  # no input during diag
        elif self.state == self.SPLASH:
            if sel:  # press start to continue
                self._splash_confirmed = True
        elif self.state == self.MAIN:         self._input_main(up, down, left, right, sel, back)
        elif self.state == self.ANIM_SELECT:  self._input_anim(up, down, sel, back)
        elif self.state == self.COLOR_SELECT: self._input_color(up, down, sel, back)
        elif self.state == self.ERROR:
            if sel or back: self._quit()

    def _input_main(self, up, down, left, right, sel, back):
        n = len(self.MAIN_ITEMS)
        if up:   self.main_idx = (self.main_idx - 1) % n; self._play('nav')
        if down: self.main_idx = (self.main_idx + 1) % n; self._play('nav')

        key = self.MAIN_ITEMS[self.main_idx][0]

        if key == 'brightness' and (left or right):
            step = -0.05 if left else 0.05
            self.brightness = round(max(0.0, min(1.0, self.brightness + step)), 2)
            self._play('adjust')
            self._send_preview(self.preview_animate, self.preview_color)

        if sel:
            if key == 'animation':
                self.anim_idx   = self._anim_index(self.preview_animate)
                self.scroll_off = 0
                self._clamp_scroll(self.anim_idx, len(ANIMATIONS))
                self.state = self.ANIM_SELECT
                self._play('select')
            elif key == 'color':
                self.color_idx  = self._color_index(self.preview_color)
                self.scroll_off = 0
                self._clamp_scroll(self.color_idx, len(COLORS))
                self.state = self.COLOR_SELECT
                self._play('select')
            elif key == 'flip':
                self.flip_strip = not self.flip_strip
                self._save_setting('general', 'flip_strip', str(self.flip_strip).lower())
                self._play('save')
            elif key == 'off':
                self.preview_animate = 'off'
                self._send_preview('off', self.preview_color, save=True)
                self.cur_animate = 'off'
                self._play('save')
            elif key == 'exit':
                self._quit()

        if back:
            self._quit()

    def _input_anim(self, up, down, sel, back):
        n = len(ANIMATIONS)
        if up:
            self.anim_idx = (self.anim_idx - 1) % n
            self._clamp_scroll(self.anim_idx, n)
            self.preview_animate = ANIMATIONS[self.anim_idx][0]
            self._send_preview(self.preview_animate, self.preview_color)
            self._play('nav')
        if down:
            self.anim_idx = (self.anim_idx + 1) % n
            self._clamp_scroll(self.anim_idx, n)
            self.preview_animate = ANIMATIONS[self.anim_idx][0]
            self._send_preview(self.preview_animate, self.preview_color)
            self._play('nav')
        if sel:
            self.cur_animate = self.preview_animate
            self._send_preview(self.preview_animate, self.preview_color, save=True)
            self.state = self.MAIN
            self._play('save')
        if back:
            self.preview_animate = self.cur_animate
            self._send_preview(self.cur_animate, self.cur_color)
            self.state = self.MAIN
            self._play('back')

    def _input_color(self, up, down, sel, back):
        n = len(COLORS)
        if up:
            self.color_idx = (self.color_idx - 1) % n
            self._clamp_scroll(self.color_idx, n)
            self.preview_color = COLORS[self.color_idx][0]
            self._send_preview(self.preview_animate, self.preview_color)
            self._play('nav')
        if down:
            self.color_idx = (self.color_idx + 1) % n
            self._clamp_scroll(self.color_idx, n)
            self.preview_color = COLORS[self.color_idx][0]
            self._send_preview(self.preview_animate, self.preview_color)
            self._play('nav')
        if sel:
            self.cur_color = self.preview_color
            self._send_preview(self.preview_animate, self.preview_color, save=True)
            self.state = self.MAIN
            self._play('save')
        if back:
            self.preview_color = self.cur_color
            self._send_preview(self.cur_animate, self.cur_color)
            self.state = self.MAIN
            self._play('back')

    # ── Update ────────────────────────────────────

    def update(self):
        now = time.monotonic()
        if now - self._blink_t > 0.5:
            self._blink   = not self._blink
            self._blink_t = now

        # Drain pixel queue — keep only latest frame
        latest = None
        while not self.ws.pixel_queue.empty():
            try:
                latest = self.ws.pixel_queue.get_nowait()
            except Exception:
                break
        if latest:
            self.pixel_data = latest

        elapsed = now - self._boot_start

        if self.state == self.BOOT:
            if elapsed >= self.BOOT_DURATION:
                self.state = self.DIAG
        elif self.state == self.DIAG:
            if elapsed >= self.BOOT_DURATION + self.DIAG_DURATION:
                self.state = self.SPLASH
        elif self.state == self.SPLASH:
            # Wait for player to press start (minimum SPLASH_DURATION before input accepted)
            splash_ready = elapsed >= self.BOOT_DURATION + self.DIAG_DURATION + self.SPLASH_DURATION
            if splash_ready and self._splash_confirmed:
                if self.ws.connected:
                    self.state = self.MAIN
                    self._send_preview(self.cur_animate, self.cur_color)
                else:
                    self.state = self.CONNECTING
                    self._connect_start = now  # reset WS timeout from here
        elif self.state == self.CONNECTING:
            if self.ws.connected:
                self.state = self.MAIN
                self._send_preview(self.cur_animate, self.cur_color)
            elif now - self._connect_start > WS_TIMEOUT:
                self.error_msg = (
                    "CANNOT CONNECT TO LED SERVICE\n\n"
                    "MAKE SURE LEDCONTROL IS RUNNING\n\n"
                    "PRESS START OR BACK TO EXIT"
                )
                self.state = self.ERROR
                self._play('error')

    # ── Draw ──────────────────────────────────────

    def draw(self):
        self.screen.fill(BLACK)
        if   self.state == self.BOOT:       self._draw_boot()
        elif self.state == self.DIAG:       self._draw_diag()
        elif self.state == self.SPLASH:     self._draw_splash()
        elif self.state == self.CONNECTING: self._draw_connecting()
        elif self.state == self.ERROR:      self._draw_error()
        else:                               self._draw_main_ui()
        self.screen.blit(self._scanlines, (0, 0))
        pygame.display.flip()

    def _draw_boot(self):
        """Flashing full-screen colorful block character noise — ROM test effect."""
        W, H  = self.W, self.H
        now   = time.monotonic()
        # Regenerate noise ~15 times per second for that frantic flash feel
        seed  = int(now * 15)
        rng   = __import__('random').Random(seed)
        cols  = 40
        rows  = 28
        cw    = W // cols
        ch    = H // rows
        BLOCK_CHARS = ['\u2588', '\u2593', '\u2592', '\u2591', '\u2580', '\u2584',
                       '\u258c', '\u2590', '\u25a0', '\u25aa', '@', '#', '%', '&']
        FLASH_COLORS = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0),
            (0, 255, 255), (255, 0, 255), (255, 140, 0), (255, 255, 255),
            (180, 0, 255), (0, 180, 255),
        ]
        font = get_font(max(8, cw - 1))
        for row in range(rows):
            for col in range(cols):
                ch_char = rng.choice(BLOCK_CHARS)
                color   = rng.choice(FLASH_COLORS)
                x = col * cw
                y = row * (H // rows)
                surf = font.render(ch_char, True, color)
                self.screen.blit(surf, (x, y))

    def _draw_diag(self):
        """Diagnostic messages: RAM OK, ROM OK, etc., appearing one by one."""
        W, H    = self.W, self.H
        elapsed = time.monotonic() - self._boot_start - self.BOOT_DURATION
        n       = len(self.DIAG_MESSAGES)
        # Show messages progressively
        show_count = max(1, int((elapsed / self.DIAG_DURATION) * n) + 1)
        font_sz = max(14, H // 26)
        line_h  = int(font_sz * 2.2)
        total_h = n * line_h
        start_y = (H - total_h) // 2

        # Dark background panel
        pad = 32
        pygame.draw.rect(self.screen, (8, 8, 8),
                         (W // 6, start_y - pad, W * 2 // 3, total_h + pad * 2))
        pygame.draw.rect(self.screen, (60, 60, 60),
                         (W // 6, start_y - pad, W * 2 // 3, total_h + pad * 2), 2)

        for i, (msg, color) in enumerate(self.DIAG_MESSAGES):
            if i >= show_count:
                break
            cy = start_y + i * line_h + line_h // 2
            # Label left, OK indicator right
            parts = msg.split()
            label = parts[0]
            status = parts[1] if len(parts) > 1 else ''
            draw_text(self.screen, label,  font_sz, DIM_WHITE, W // 3,       cy, anchor='left')
            draw_text(self.screen, status, font_sz, color,     W * 2 // 3,   cy, anchor='right')

    def _draw_splash(self):
        """Full title splash screen with blinking PRESS START."""
        W, H = self.W, self.H

        # Title image centered
        if self.title_img:
            # Scale up for splash — bigger than main screen version
            path = Path(__file__).parent / 'assets' / 'images' / 'title.png'
            if not hasattr(self, '_splash_title') or self._splash_title is None:
                try:
                    img = pygame.image.load(str(path)).convert_alpha()
                    max_w = int(W * 0.80)
                    max_h = int(H * 0.30)
                    scale = min(max_w / img.get_width(), max_h / img.get_height(), 1.0)
                    self._splash_title = pygame.transform.smoothscale(
                        img, (int(img.get_width() * scale), int(img.get_height() * scale)))
                except Exception:
                    self._splash_title = self.title_img
            img = self._splash_title
            tr  = img.get_rect(center=(W // 2, int(H * 0.38)))
            self.screen.blit(img, tr)
            # Copyright below title
            tm_sz = max(9, H // 55)
            draw_text(self.screen, '\u00a9 BELCH STUDIOS  \u2122 1981',
                      tm_sz, (130, 130, 130), W // 2, tr.bottom + int(tm_sz * 2.0))
        else:
            self._draw_title_text(W // 2, int(H * 0.38))
            draw_text(self.screen, '\u00a9 BELCH STUDIOS  \u2122 1981',
                      max(9, H // 55), (130, 130, 130), W // 2, int(H * 0.50))

        # Blinking PRESS START
        if self._blink:
            ps_sz = max(14, H // 30)
            # Classic arcade rainbow cycle
            t   = time.monotonic()
            hue = int(t * 120) % 360
            r, g, b = _hsv_to_rgb(hue, 1.0, 1.0)
            draw_text(self.screen, 'PRESS START', ps_sz, (r, g, b),
                      W // 2, int(H * 0.72))

    def _draw_connecting(self):
        dots = '.' * (int((time.monotonic() * 2) % 4))
        draw_text(self.screen, f'CONNECTING{dots}', self.H // 28,
                  GOLD, self.W // 2, self.H // 2)

    def _draw_error(self):
        lines    = self.error_msg.split('\n')
        line_h   = self.H // 18
        start_y  = self.H // 2 - (len(lines) * line_h) // 2
        palette  = [RED_BORDER, DIM_WHITE, GOLD]
        for i, line in enumerate(lines):
            if line.strip():
                draw_text(self.screen, line, self.H // 32,
                          palette[i % len(palette)], self.W // 2, start_y + i * line_h)

    def _draw_main_ui(self):
        W, H = self.W, self.H

        # ── Title image ──
        title_cy = int(H * 0.03) + (self.title_img.get_height() // 2 if self.title_img else int(H * 0.07))
        if self.title_img:
            tr = self.title_img.get_rect(center=(W // 2, title_cy))
            self.screen.blit(self.title_img, tr)
            # © TM note to the right of the title
            tm_sz = max(7, H // 72)
            tm_x  = tr.right + 6
            tm_y  = tr.bottom - int(tm_sz * 3.2)
            draw_text(self.screen, '\u00a9 BELCH STUDIOS', tm_sz, (130, 130, 130), tm_x, tm_y,  anchor='left')
            draw_text(self.screen, '\u2122 1981',          tm_sz, (130, 130, 130), tm_x, tm_y + int(tm_sz * 1.8), anchor='left')
        else:
            self._draw_title_text(W // 2, title_cy)

        # ── Cabinet art with LED overlay ──
        if self.cabinet_img and self.cabinet_rect:
            self.screen.blit(self.cabinet_img, self.cabinet_rect)
            self._draw_leds_on_cabinet()
        else:
            # Fallback plain strip
            sr = pygame.Rect(int(W * 0.03), int(H * 0.22), int(W * 0.94), int(H * 0.13))
            pygame.draw.rect(self.screen, (12, 12, 12), sr, border_radius=6)
            pygame.draw.rect(self.screen, (40, 40, 40), sr, 1,  border_radius=6)
            self._draw_leds_plain(sr)

        # ── Divider ──
        div_y = self.menu_top - int(H * 0.015)
        pygame.draw.line(self.screen, (50, 50, 50),
                         (int(W * 0.05), div_y), (int(W * 0.95), div_y), 1)

        # ── Menu ──
        menu_h = int(H * 0.92) - self.menu_top

        if self.state == self.MAIN:
            _base_item_h = menu_h // 5  # font size locked to original 5-item layout
            _fixed_fsz   = max(14, min(26, _base_item_h // 2))
            self._draw_list(
                items      = [(lbl, '') for _, lbl in self.MAIN_ITEMS],
                sel_idx    = self.main_idx,
                top        = self.menu_top,
                height     = menu_h,
                show_all   = True,
                right_vals = self._main_right_vals(),
                font_sz    = _fixed_fsz,
            )
        elif self.state == self.ANIM_SELECT:
            draw_text(self.screen, 'SELECT ANIMATION', H // 42, GOLD,
                      W // 2, self.menu_top - int(H * 0.025))
            self._draw_list(
                items   = [(lbl, '') for _, lbl in ANIMATIONS],
                sel_idx = self.anim_idx,
                top     = self.menu_top,
                height  = menu_h,
            )
        elif self.state == self.COLOR_SELECT:
            draw_text(self.screen, 'SELECT COLOR', H // 42, GOLD,
                      W // 2, self.menu_top - int(H * 0.025))
            self._draw_list(
                items       = [(lbl, '') for _, lbl, _ in COLORS],
                sel_idx     = self.color_idx,
                top         = self.menu_top,
                height      = menu_h,
                color_dots  = [rgb for _, _, rgb in COLORS],
                item_colors = [rgb for _, _, rgb in COLORS],
            )

        # ── Controls hint ──
        draw_text(self.screen, 'UP/DN NAVIGATE   A SELECT   B BACK',
                  max(8, H // 60), (70, 70, 70), W // 2, int(H * 0.98))

    def _draw_leds_on_cabinet(self):
        """Overlay LED circles at the correct position on the cabinet image."""
        cr = self.cabinet_rect
        led_y  = int(cr.top  + cr.height * CABINET_LED_Y)
        led_x1 = int(cr.left + cr.width  * CABINET_LED_X1)
        led_x2 = int(cr.left + cr.width  * CABINET_LED_X2)
        self._draw_led_row(led_x1, led_x2, led_y)

    def _draw_leds_plain(self, rect: pygame.Rect):
        """Fallback: LED row centred in a plain rect."""
        self._draw_led_row(
            int(rect.left  + rect.width  * 0.03),
            int(rect.right - rect.width  * 0.03),
            rect.centery,
        )

    def _draw_led_row(self, x1: int, x2: int, cy: int):
        """Render num_leds glowing circles between x1 and x2 at height cy."""
        n = self.num_leds
        if n == 0:
            return
        span   = x2 - x1
        step   = span / n
        radius = max(4, min(int(step * 0.36), 24))

        pixels = list(reversed(self.pixel_data)) if self.flip_strip else self.pixel_data
        for i in range(n):
            cx = int(x1 + step * i + step / 2)
            color = tuple(pixels[i]) if (pixels and i < len(pixels)) \
                    else (0, 0, 0)

            if color == (0, 0, 0):
                pygame.draw.circle(self.screen, (22, 22, 22), (cx, cy), radius)
                pygame.draw.circle(self.screen, (50, 50, 50), (cx, cy), radius, 1)
            else:
                # 1. Glow ring (donut — transparent center) via additive blend
                gs = _glow_surf(radius, color)
                self.screen.blit(gs,
                                 (cx - gs.get_width() // 2, cy - gs.get_height() // 2),
                                 special_flags=pygame.BLEND_ADD)
                # 2. Solid LED core — exact ws2812 color, no blending
                pygame.draw.circle(self.screen, color, (cx, cy), radius)

    def _draw_title_text(self, cx, cy):
        """Fallback title when no logo image is present."""
        H  = self.H
        sz = max(14, H // 22)
        surf = get_font(sz).render('RETRO LED', True, GOLD)
        bx = cx - surf.get_width() // 2 - 16
        by = cy - surf.get_height() // 2 - 8
        bw = surf.get_width() + 32
        bh = surf.get_height() + 16
        pygame.draw.rect(self.screen, ORANGE,     (bx, by, bw, bh), border_radius=6)
        pygame.draw.rect(self.screen, RED_BORDER, (bx, by, bw, bh), 4, border_radius=6)
        self.screen.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

    def _main_right_vals(self):
        anim_lbl  = next((lbl for k, lbl in ANIMATIONS    if k == self.cur_animate), 'KITT SCANNER')
        color_lbl = next((lbl for k, lbl, _ in COLORS     if k == self.cur_color),   'RED')
        flip_lbl  = 'ON' if self.flip_strip else 'OFF'
        return [anim_lbl, color_lbl, f'{int(self.brightness * 100)}%', flip_lbl, '', '']

    def _draw_list(self, items, sel_idx, top, height,
                   show_all=False, right_vals=None, color_dots=None, item_colors=None, font_sz=None):
        W, H  = self.W, self.H
        n     = len(items)
        mv    = self._max_visible()

        if show_all:
            visible = items
            v_start = 0
        else:
            v_start = self.scroll_off
            visible = items[v_start: v_start + mv]

        item_h  = height // max(len(visible), 1)
        if font_sz is None:
            font_sz = max(14, min(26, item_h // 2))
        rval_sz = max(11, font_sz - 4)

        for vi, (label, _) in enumerate(visible):
            abs_idx = v_start + vi
            row_col = item_colors[abs_idx] if (item_colors and abs_idx < len(item_colors)) \
                      else ROW_COLORS[abs_idx % len(ROW_COLORS)]
            cy      = top + vi * item_h + item_h // 2
            is_sel  = (abs_idx == sel_idx)

            if is_sel:
                hl = tuple(min(255, int(c * 0.22)) for c in row_col)
                pygame.draw.rect(self.screen, hl,
                                 pygame.Rect(int(W * 0.04), cy - item_h // 2 + 2,
                                             int(W * 0.92), item_h - 4),
                                 border_radius=4)

            if is_sel and self._blink:
                draw_text(self.screen, '\u25ba', font_sz, row_col,
                          int(W * 0.07), cy, anchor='left')

            label_color = row_col if is_sel else tuple(int(c * 0.55) for c in row_col)
            draw_text(self.screen, label, font_sz, label_color,
                      int(W * 0.12), cy, anchor='left')

            if right_vals and abs_idx < len(right_vals) and right_vals[abs_idx]:
                draw_text(self.screen, right_vals[abs_idx], rval_sz, label_color,
                          int(W * 0.93), cy, anchor='right')

            if color_dots and abs_idx < len(color_dots):
                dot_r = max(5, font_sz // 2)
                dot_x = int(W * 0.88)
                pygame.draw.circle(self.screen, color_dots[abs_idx], (dot_x, cy), dot_r)
                if is_sel:
                    pygame.draw.circle(self.screen, WHITE, (dot_x, cy), dot_r, 1)

        if not show_all and n > mv:
            ind_sz = max(8, H // 60)
            if v_start > 0:
                draw_text(self.screen, '\u25b2 MORE', ind_sz, (80, 80, 80),
                          W // 2, top - 14)
            if v_start + mv < n:
                draw_text(self.screen, '\u25bc MORE', ind_sz, (80, 80, 80),
                          W // 2, top + height + 14)

    # ── Lifecycle ─────────────────────────────────

    def _quit(self):
        self.ws.stop()
        pygame.quit()
        sys.exit(0)

    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)

# ────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────
if __name__ == '__main__':
    app = RetroLED()
    app.run()
