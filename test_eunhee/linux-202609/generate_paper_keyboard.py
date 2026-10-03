"""
generate_paper_keyboard.py

keyboard_layout.KEY_MAP 과 config_combined.py 의 좌표 상수를 그대로 사용해
인쇄 가능한 종이 키보드 이미지(A3/A4, PNG/PDF)를 만듭니다.

config_combined.py 의 PAPER_DESIGN_W/H 등은 실제 인쇄 크기와 무관한 "추상
디자인 좌표계"이고, paper_edge_mapper 의 인식은 homography 기반이라 종이의
실제 물리적 크기와 무관하게 동작합니다 (A4/A3 모두 ISO 216 규격상 종횡비가
1:root2 로 동일). 그래서 A4 버전을 추가해도 config_combined.py 는 건드리지
않고, 이 스크립트 안에서만 A3 좌표를 비례 축소해 A4 캔버스에 다시 그립니다.

실행:
    python generate_paper_keyboard.py

출력:
    A3_세로_종이키보드_정확버전_300dpi.png / .pdf
    A4_세로_종이키보드_정확버전_300dpi.png / .pdf

반드시 "실제 크기(100%)"로 인쇄하세요. "용지에 맞춤"으로 인쇄하면
PAPER_KEYBOARD_BOX / PAPER_MOUSE_* 좌표와 실제 종이 위 위치가 어긋납니다.
"""

import os
from functools import lru_cache

from PIL import Image, ImageDraw

from keyboard_layout import KEY_MAP
from renderer import load_font, LABEL_MAP
from config_combined import (
    PAPER_DESIGN_W,
    PAPER_DESIGN_H,
    PAPER_KEYBOARD_BOX,
    VIRTUAL_KEYBOARD_BOX,
    PAPER_MARKER_CENTERS,
    PAPER_MOUSE_X1,
    PAPER_MOUSE_X2,
    PAPER_MOUSE_LINE_Y,
    PAPER_MOUSE_BOTTOM_Y,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PAPER_MAPPER_MODE == "marker" 로 되돌릴 때만 True 로 바꾸세요.
# 현재 활성 모드("edge")는 종이 테두리만 인식하므로 마커가 필요 없습니다.
INCLUDE_MARKERS = False
MARKER_SIZE_PX = 130  # 약 1.1cm @ 300dpi

KEY_BORDER_WIDTH = 4
KEY_BORDER_COLOR = (0, 0, 0)
KEY_FILL_COLOR = (255, 255, 255)
TEXT_COLOR = (0, 0, 0)

MOUSE_ZONE_BORDER_WIDTH = 7
MOUSE_ZONE_COLOR = (0, 0, 0)
MOUSE_ZONE_CORNER_LEN = 140  # px, 약 1.2cm @ 300dpi

# 300dpi 표준 A4 픽셀 크기 (210mm x 297mm). A3(3508x4961)와 종횡비가 완전히
# 같아(ISO 216, 1:root2) config_combined.py 의 좌표계를 그대로 비례 축소해 쓸 수 있음.
A4_W, A4_H = 2480, 3508

# 표준 두벌식(KS X 5002) 자모 배치. 실제 키보드도 동일한 물리 키가 IME 상태에
# 따라 영문/한글을 다르게 낸다(keyboard_input.py 의 press_key 는 항상 영문
# 스캔코드를 보내고, "한/영" 키가 OS IME를 토글) — 그래서 종이에도 두 문자를
# 같이 인쇄해야 실제 키보드와 기능적으로 대응된다. 숫자행/;'/,./ 에는 두벌식이
# 자모를 배정하지 않으므로 여기 없음. 쌍자음/이중모음(Shift 조합)은 생략.
HANGUL_MAP = {
    "Q": "ㅂ", "W": "ㅈ", "E": "ㄷ", "R": "ㄱ", "T": "ㅅ",
    "Y": "ㅛ", "U": "ㅕ", "I": "ㅑ", "O": "ㅐ", "P": "ㅔ",
    "A": "ㅁ", "S": "ㄴ", "D": "ㅇ", "F": "ㄹ", "G": "ㅎ",
    "H": "ㅗ", "J": "ㅓ", "K": "ㅏ", "L": "ㅣ",
    "Z": "ㅋ", "X": "ㅌ", "C": "ㅊ", "V": "ㅍ", "B": "ㅠ",
    "N": "ㅜ", "M": "ㅡ",
}

# 숫자행 Shift 기호. keyboard_input.py 는 1글자 키를 전부 같은 분기에서
# 처리하며 shift_mode 가 켜져 있으면 실제 Shift 를 함께 보내므로(len(key)==1
# 분기), 이 키들도 Shift 상태에서 실제로 다른 문자를 낸다 — 실제 키보드처럼
# 표시해야 기능과 맞는다. 요청된 범위(1~0, -, =)만 포함, `(backtick)은 제외.
SHIFT_MAP = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    "-": "_", "=": "+",
}


def map_virtual_rect_to_paper(rect, keyboard_box, vbox=VIRTUAL_KEYBOARD_BOX):
    """paper_board_mapper._virtual_rect_to_paper_with_box 와 동일한 선형 보간."""
    x1, y1, x2, y2 = rect
    vx1, vy1, vx2, vy2 = vbox
    kx1, ky1, kx2, ky2 = keyboard_box

    def one(vx, vy):
        px = kx1 + (float(vx) - vx1) * (kx2 - kx1) / max(vx2 - vx1, 1e-6)
        py = ky1 + (float(vy) - vy1) * (ky2 - ky1) / max(vy2 - vy1, 1e-6)
        return px, py

    p1 = one(x1, y1)
    p2 = one(x2, y2)
    return (p1[0], p1[1], p2[0], p2[1])


@lru_cache(maxsize=None)
def cached_font(size):
    return load_font(size)


def fit_font(draw, text, max_w, max_h, min_size=16, max_size=180):
    lo, hi = min_size, max_size
    best = min_size
    while lo <= hi:
        mid = (lo + hi) // 2
        font = cached_font(mid)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if tw <= max_w and th <= max_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return cached_font(best)


def draw_centered_text(draw, text, cx, cy, font, color):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), text, font=font, fill=color)


def draw_corner_text(draw, text, x, y, font, color, h_align, v_align):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (x - bbox[0]) if h_align == "left" else (x - tw - bbox[0])
    ty = (y - bbox[1]) if v_align == "top" else (y - th - bbox[1])
    draw.text((tx, ty), text, font=font, fill=color)


def draw_key(draw, name, rect_virtual, keyboard_box):
    px1, py1, px2, py2 = map_virtual_rect_to_paper(rect_virtual, keyboard_box)
    draw.rectangle(
        [px1, py1, px2, py2],
        outline=KEY_BORDER_COLOR,
        width=KEY_BORDER_WIDTH,
        fill=KEY_FILL_COLOR,
    )

    w = px2 - px1
    h = py2 - py1
    jamo = HANGUL_MAP.get(name)
    shifted = SHIFT_MAP.get(name)

    if jamo:
        # 실제 한글 키보드처럼 영문은 좌상단, 자모는 우하단 모서리에 작게 배치.
        label = LABEL_MAP.get(name, name)
        pad_x = 0.10 * w
        pad_y = 0.08 * h
        corner_w = 0.42 * w
        corner_h = 0.30 * h

        en_font = fit_font(draw, label, corner_w, corner_h)
        ko_font = fit_font(draw, jamo, corner_w, corner_h)

        draw_corner_text(draw, label, px1 + pad_x, py1 + pad_y, en_font, TEXT_COLOR, "left", "top")
        draw_corner_text(draw, jamo, px2 - pad_x, py2 - pad_y, ko_font, TEXT_COLOR, "right", "bottom")
    elif shifted:
        # 실제 키보드 숫자행처럼 Shift 기호는 위쪽, 기본 문자는 아래쪽에 중앙 정렬.
        label = LABEL_MAP.get(name, name)
        cx = (px1 + px2) / 2
        pad_x = 0.10 * w
        pad_y = 0.08 * h
        gap = 0.04 * h
        zone_h = (h - 2 * pad_y - gap) / 2

        top_font = fit_font(draw, shifted, w - 2 * pad_x, zone_h)
        bot_font = fit_font(draw, label, w - 2 * pad_x, zone_h)

        top_cy = py1 + pad_y + zone_h / 2
        bot_cy = py2 - pad_y - zone_h / 2

        draw_centered_text(draw, shifted, cx, top_cy, top_font, TEXT_COLOR)
        draw_centered_text(draw, label, cx, bot_cy, bot_font, TEXT_COLOR)
    else:
        label = LABEL_MAP.get(name, name)
        pad = 0.12 * min(w, h)
        font = fit_font(draw, label, max(w - 2 * pad, 1), max(h - 2 * pad, 1))
        cx = (px1 + px2) / 2
        cy = (py1 + py2) / 2
        draw_centered_text(draw, label, cx, cy, font, TEXT_COLOR)


def _draw_corner(draw, x, y, dx, dy, length, width, color):
    """(x,y) 모서리에서 (dx,dy) 방향(각 +1/-1)으로 뻗는 ㄱ자 코너마크."""
    draw.line([(x, y), (x + dx * length, y)], fill=color, width=width)
    draw.line([(x, y), (x, y + dy * length)], fill=color, width=width)


def draw_mouse_zone(draw, mouse_rect):
    # 닫힌 사각형 대신 코너마크만 그립니다: 실선 사각형은 paper_edge_mapper의
    # 종이 테두리 탐지 필터(면적비/종횡비)를 통과할 만큼 크고 A3와 비슷한 비율이라
    # 종이 자체로 오인식될 수 있습니다. 서로 떨어진 4개의 짧은 L자는 하나의 닫힌
    # 컨투어로 합쳐지지 않아 그 후보에서 애초에 제외됩니다.
    x1, y1, x2, y2 = mouse_rect
    L = MOUSE_ZONE_CORNER_LEN
    w = MOUSE_ZONE_BORDER_WIDTH
    _draw_corner(draw, x1, y1, +1, +1, L, w, MOUSE_ZONE_COLOR)  # TL
    _draw_corner(draw, x2, y1, -1, +1, L, w, MOUSE_ZONE_COLOR)  # TR
    _draw_corner(draw, x1, y2, +1, -1, L, w, MOUSE_ZONE_COLOR)  # BL
    _draw_corner(draw, x2, y2, -1, -1, L, w, MOUSE_ZONE_COLOR)  # BR


def draw_markers(draw, marker_centers):
    s = MARKER_SIZE_PX / 2
    for cx, cy in marker_centers:
        draw.rectangle([cx - s, cy - s, cx + s, cy + s], fill=(0, 0, 0))


def _sanity_check_bounds(keyboard_box, label):
    xs1 = [r[0] for r in KEY_MAP.values()]
    ys1 = [r[1] for r in KEY_MAP.values()]
    xs2 = [r[2] for r in KEY_MAP.values()]
    ys2 = [r[3] for r in KEY_MAP.values()]
    full_bbox = (min(xs1), min(ys1), max(xs2), max(ys2))

    mapped = map_virtual_rect_to_paper(full_bbox, keyboard_box)
    assert all(abs(a - b) < 0.5 for a, b in zip(mapped, keyboard_box)), (mapped, keyboard_box)
    print(f"[{label}] Bounds OK:", mapped, "== expected", keyboard_box)

    for sample in ("Esc", "Space", "Right"):
        print(f"[{label}]", sample, "->", map_virtual_rect_to_paper(KEY_MAP[sample], keyboard_box))


def render_page(paper_w, paper_h, keyboard_box, mouse_rect, marker_centers, output_png, output_pdf, label):
    _sanity_check_bounds(keyboard_box, label)

    img = Image.new("RGB", (paper_w, paper_h), "white")
    draw = ImageDraw.Draw(img)

    for name, rect in KEY_MAP.items():
        draw_key(draw, name, rect, keyboard_box)

    draw_mouse_zone(draw, mouse_rect)

    if INCLUDE_MARKERS:
        draw_markers(draw, marker_centers)

    img.save(output_png, dpi=(300, 300))
    img.save(output_pdf, "PDF", resolution=300.0)
    print(f"[{label}] Saved: {output_png}")
    print(f"[{label}] Saved: {output_pdf}")


def main():
    # --- A3: config_combined.py 좌표 그대로 ---
    render_page(
        PAPER_DESIGN_W, PAPER_DESIGN_H,
        PAPER_KEYBOARD_BOX,
        (PAPER_MOUSE_X1, PAPER_MOUSE_LINE_Y, PAPER_MOUSE_X2, PAPER_MOUSE_BOTTOM_Y),
        PAPER_MARKER_CENTERS,
        os.path.join(BASE_DIR, "A3_세로_종이키보드_정확버전_300dpi.png"),
        os.path.join(BASE_DIR, "A3_세로_종이키보드_정확버전_300dpi.pdf"),
        "A3",
    )

    # --- A4: A3 좌표를 비례 축소해서 파생 (config_combined.py는 수정하지 않음) ---
    sx = A4_W / PAPER_DESIGN_W
    sy = A4_H / PAPER_DESIGN_H
    kx1, ky1, kx2, ky2 = PAPER_KEYBOARD_BOX
    a4_keyboard_box = (kx1 * sx, ky1 * sy, kx2 * sx, ky2 * sy)
    a4_mouse_rect = (
        PAPER_MOUSE_X1 * sx, PAPER_MOUSE_LINE_Y * sy,
        PAPER_MOUSE_X2 * sx, PAPER_MOUSE_BOTTOM_Y * sy,
    )
    a4_marker_centers = [(x * sx, y * sy) for x, y in PAPER_MARKER_CENTERS]

    render_page(
        A4_W, A4_H,
        a4_keyboard_box,
        a4_mouse_rect,
        a4_marker_centers,
        os.path.join(BASE_DIR, "A4_세로_종이키보드_정확버전_300dpi.png"),
        os.path.join(BASE_DIR, "A4_세로_종이키보드_정확버전_300dpi.pdf"),
        "A4",
    )


if __name__ == "__main__":
    main()
