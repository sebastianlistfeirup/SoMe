"""Render the five Pixel & Parameters AI graphics in 16:9 and 9:16.

Procedural (no AI image generation, no stock): brand navy/cyan/coral/white,
pixel squares and parameter sliders from the approved logo. Text-free except the
pixel-built "VS", so titles and captions can sit on top. These are graphics, not
real media: they count toward the 20 % graphic budget of a video.

    python scripts/render_ai_graphics.py [--out assets/graphics/ai] [--seed 7]
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 2  # supersampling factor
NAVY_DEEP = np.array([1, 4, 16], dtype=np.float32) / 255
NAVY = np.array([7, 22, 64], dtype=np.float32) / 255
CYAN = (0, 180, 216)
CYAN_SOFT = (60, 210, 240)
CORAL = (242, 92, 60)
WHITE = (238, 246, 255)
FORMATS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


# --- light helpers ------------------------------------------------------------

def light(W, H):
    image = Image.new("RGB", (W * SS, H * SS), (0, 0, 0))
    return image, ImageDraw.Draw(image)


def scale(color, k):
    return tuple(int(max(0, min(255, c * k))) for c in color)


def arr(image):
    return np.asarray(image, dtype=np.float32) / 255.0


def glow(image, radii=((3, 0.9), (14, 0.55), (48, 0.35))):
    """Additive bloom: the sharp layer plus blurred copies computed at quarter resolution."""
    base = arr(image)
    out = base.copy()
    small = image.resize((image.width // 4, image.height // 4), Image.BILINEAR)
    for radius, amount in radii:
        blurred = small.filter(ImageFilter.GaussianBlur(radius * SS / 4)).resize(image.size, Image.BILINEAR)
        out += arr(blurred) * amount
    return out


def background(W, H, center=(0.5, 0.5), tint=None, rng=None, pixels=True):
    yy, xx = np.mgrid[0:H * SS, 0:W * SS].astype(np.float32)
    cx, cy = center[0] * W * SS, center[1] * H * SS
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (max(W, H) * SS)
    t = np.clip(1 - d * 1.35, 0, 1)[..., None] ** 1.6
    image = NAVY_DEEP + (NAVY - NAVY_DEEP) * t
    if tint is not None:
        image = image + np.array(tint, dtype=np.float32)[None, None, :] / 255 * t * 0.18
    if pixels and rng is not None:
        # Faint brand pixel grid: sparse squares aligned to a coarse grid.
        cell = int(min(W, H) * SS / 18)
        layer = Image.new("L", (W * SS, H * SS), 0)
        draw = ImageDraw.Draw(layer)
        for gx in range(0, W * SS, cell):
            for gy in range(0, H * SS, cell):
                if rng.random() < 0.07:
                    inset = int(cell * 0.18)
                    draw.rectangle([gx + inset, gy + inset, gx + cell - inset, gy + cell - inset], fill=int(rng.uniform(6, 16)))
        image = image + (arr(layer)[..., None] * np.array([0.35, 0.75, 1.0], dtype=np.float32)) * 0.6
    return image


def finish(image, W, H, rng, exposure=1.15, vignette=0.55, grain=0.010):
    yy, xx = np.mgrid[0:H * SS, 0:W * SS].astype(np.float32)
    d = np.sqrt(((xx / (W * SS)) - 0.5) ** 2 * (W / max(W, H)) ** 2 * 4 + ((yy / (H * SS)) - 0.5) ** 2 * (H / max(W, H)) ** 2 * 4)
    image = image * (1 - vignette * np.clip(d - 0.35, 0, 1)[..., None] ** 1.5)
    image = image * exposure
    knee = 0.72  # linear below the knee keeps the brand navy; highlights roll off smoothly
    over = np.maximum(image - knee, 0)
    image = np.where(image > knee, knee + (1 - knee) * (1 - np.exp(-over / (1 - knee))), image)
    out = Image.fromarray((np.clip(image, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)
    noisy = np.asarray(out, dtype=np.float32) / 255 + rng.normal(0, grain, (H, W, 1)).astype(np.float32)
    return Image.fromarray((np.clip(noisy, 0, 1) * 255).astype(np.uint8))


def bokeh(W, H, rng, count, color_choices, size=(0.02, 0.08), intensity=(0.05, 0.18)):
    image, draw = light(W, H)
    for _ in range(count):
        x, y = rng.uniform(0, W * SS), rng.uniform(0, H * SS)
        r = rng.uniform(*size) * min(W, H) * SS
        color = scale(color_choices[rng.integers(len(color_choices))], rng.uniform(*intensity))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return arr(image.filter(ImageFilter.GaussianBlur(6 * SS)))


def stars(W, H, rng, count, intensity=(0.15, 0.6)):
    image, draw = light(W, H)
    for _ in range(count):
        x, y = rng.uniform(0, W * SS), rng.uniform(0, H * SS)
        r = rng.uniform(0.6, 1.8) * SS
        color = scale(WHITE if rng.random() < 0.7 else CYAN_SOFT, rng.uniform(*intensity))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return glow(image, ((2, 0.6), (8, 0.25)))


def slider(draw, cx, cy, length, thickness, knob, color, knob_pos=0.62):
    """The logo's parameter slider: a long rounded bar with a circular knob (proportions from the logo)."""
    knob = min(knob, thickness * 1.6)
    length = max(length, knob * 2 * 3.6)
    knob_pos = min(0.72, max(0.38, knob_pos))
    half = length / 2
    draw.rounded_rectangle([cx - half, cy - thickness / 2, cx + half, cy + thickness / 2], radius=thickness / 2, fill=color)
    kx = cx - half + length * knob_pos
    draw.ellipse([kx - knob, cy - knob, kx + knob, cy + knob], fill=color)


def flow_mapper(W, H):
    """Map (u along the flow, v across) to pixels: left->right in 16:9, top->bottom in 9:16."""
    landscape = W >= H

    def point(u, v):
        if landscape:
            return u * W * SS, v * H * SS
        return v * W * SS, u * H * SS

    return point, landscape


# --- 1. Neural Constellation -----------------------------------------------------

def neural_constellation(W, H, rng):
    landscape = W >= H
    unit = min(W, H) * SS
    cx, cy = W * SS / 2, H * SS * (0.5 if landscape else 0.44)
    bg = background(W, H, (cx / (W * SS), cy / (H * SS)), tint=CYAN, rng=rng)
    radius = unit * (0.40 if landscape else 0.42)
    count = 260
    k = np.arange(count) + 0.5
    phi = np.arccos(1 - 2 * k / count)
    theta = math.pi * (1 + 5 ** 0.5) * k
    pts = np.stack([np.cos(theta) * np.sin(phi), np.sin(theta) * np.sin(phi), np.cos(phi)], axis=1)
    pts += rng.normal(0, 0.035, pts.shape)
    pts /= np.linalg.norm(pts, axis=1, keepdims=True)
    tilt_x, tilt_y = 0.55, -0.35
    rx = np.array([[1, 0, 0], [0, math.cos(tilt_x), -math.sin(tilt_x)], [0, math.sin(tilt_x), math.cos(tilt_x)]])
    ry = np.array([[math.cos(tilt_y), 0, math.sin(tilt_y)], [0, 1, 0], [-math.sin(tilt_y), 0, math.cos(tilt_y)]])
    pts = pts @ rx.T @ ry.T
    depth = (pts[:, 2] + 1) / 2  # 0 back .. 1 front
    persp = 1 + pts[:, 2] * 0.12
    screen = np.stack([cx + pts[:, 0] * radius * persp, cy + pts[:, 1] * radius * persp], axis=1)
    distances = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
    neighbours = np.argsort(distances, axis=1)[:, 1:4]
    back, bdraw = light(W, H)
    front, fdraw = light(W, H)
    hot, hdraw = light(W, H)
    drawn = set()
    for i in range(count):
        for j in neighbours[i]:
            key = (min(i, j), max(i, j))
            if key in drawn:
                continue
            drawn.add(key)
            d = (depth[i] + depth[j]) / 2
            target = fdraw if d > 0.5 else bdraw
            target.line([tuple(screen[i]), tuple(screen[j])], fill=scale(CYAN, 0.08 + 0.42 * d ** 1.6), width=max(1, int((0.8 + 1.4 * d) * SS)))
    for i in range(count):
        d = depth[i]
        r = unit * (0.0025 + 0.0065 * d ** 1.5)
        target = fdraw if d > 0.5 else bdraw
        x, y = screen[i]
        target.ellipse([x - r, y - r, x + r, y + r], fill=scale(WHITE if d > 0.75 else CYAN_SOFT, 0.25 + 0.75 * d ** 1.4))
    # Activation paths: random walks over the front hemisphere.
    front_nodes = [i for i in range(count) if depth[i] > 0.86]  # start on the face of the sphere, not its rim
    for walk_index in range(3):
        node = int(rng.choice(front_nodes))
        path = [node]
        for _ in range(9):
            options = [int(j) for j in neighbours[node] if int(j) not in path and depth[int(j)] > 0.45]
            if not options:
                break
            node = options[int(rng.integers(len(options)))]
            path.append(node)
        color = CORAL if walk_index < 2 else WHITE
        for a, b in zip(path, path[1:]):
            hdraw.line([tuple(screen[a]), tuple(screen[b])], fill=scale(color, 0.95), width=int(2.6 * SS))
        for index, node in enumerate(path):
            x, y = screen[node]
            r = unit * (0.011 if index in (0, len(path) - 1) else 0.006)
            hdraw.ellipse([x - r, y - r, x + r, y + r], fill=scale(WHITE, 1.0))
            if index in (0, len(path) - 1):
                r2 = r * 2.1
                hdraw.ellipse([x - r2, y - r2, x + r2, y + r2], outline=scale(color, 1.0), width=int(2 * SS))
    # Equator and meridian rings for structure.
    rings, rdraw = light(W, H)
    for tilt, bright in ((0.0, 0.18), (1.1, 0.12)):
        ring = []
        for t in np.linspace(0, 2 * math.pi, 300):
            p = np.array([math.cos(t), math.sin(t) * math.sin(tilt), math.sin(t) * math.cos(tilt)]) * 1.18
            p = p @ rx.T @ ry.T
            ring.append((cx + p[0] * radius, cy + p[1] * radius))
        rdraw.line(ring, fill=scale(CYAN, bright), width=int(1.2 * SS))
    core, cdraw = light(W, H)
    r = radius * 0.9
    cdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=scale(CYAN, 0.35))
    image = bg + arr(core.filter(ImageFilter.GaussianBlur(90 * SS))) * 0.75
    image += glow(back, ((2, 0.5), (10, 0.25))) * 0.8 + glow(front, ((2, 0.8), (10, 0.45), (36, 0.25))) + glow(rings, ((2, 0.6), (12, 0.3)))
    image += glow(hot, ((3, 1.0), (14, 0.7), (50, 0.45)))
    image += bokeh(W, H, rng, 10, [CYAN, CORAL], size=(0.01, 0.035), intensity=(0.04, 0.10))
    image += stars(W, H, rng, 200)
    return finish(image, W, H, rng)


# --- 2. Local Silicon ------------------------------------------------------------------

def local_silicon(W, H, rng):
    landscape = W >= H
    cx, cy = W * SS / 2, H * SS * (0.5 if landscape else 0.44)
    unit = min(W, H) * SS
    bg = background(W, H, (cx / (W * SS), cy / (H * SS)), tint=CYAN, rng=rng)
    traces, tdraw = light(W, H)
    pulses, pdraw = light(W, H)
    core, cdraw = light(W, H)
    package = unit * 0.40
    die = package * 0.56
    step = unit * 0.014
    # Manhattan traces from the package edge outward, with pads at the ends.
    for side in range(4):
        for k in range(26):
            offset = (k - 12.5) / 12.5 * package * 0.46
            reach = rng.uniform(0.35, 1.0) * max(W, H) * SS * 0.55
            kink = rng.uniform(0.15, 0.55) * reach
            drift = rng.choice([-1, 1]) * rng.uniform(1, 4) * step
            if side == 0:
                pts = [(cx + package / 2, cy + offset), (cx + package / 2 + kink, cy + offset), (cx + package / 2 + kink + abs(drift), cy + offset + drift), (cx + package / 2 + reach, cy + offset + drift)]
            elif side == 1:
                pts = [(cx - package / 2, cy + offset), (cx - package / 2 - kink, cy + offset), (cx - package / 2 - kink - abs(drift), cy + offset + drift), (cx - package / 2 - reach, cy + offset + drift)]
            elif side == 2:
                pts = [(cx + offset, cy + package / 2), (cx + offset, cy + package / 2 + kink), (cx + offset + drift, cy + package / 2 + kink + abs(drift)), (cx + offset + drift, cy + package / 2 + reach)]
            else:
                pts = [(cx + offset, cy - package / 2), (cx + offset, cy - package / 2 - kink), (cx + offset + drift, cy - package / 2 - kink - abs(drift)), (cx + offset + drift, cy - package / 2 - reach)]
            bright = rng.uniform(0.12, 0.42)
            tdraw.line(pts, fill=scale(CYAN, bright), width=int(1.7 * SS), joint="curve")
            ex, ey = pts[-1]
            r = step * 0.42
            tdraw.ellipse([ex - r, ey - r, ex + r, ey + r], outline=scale(CYAN_SOFT, bright * 1.6), width=int(1.4 * SS))
            if rng.random() < 0.28:
                a, b = pts[2], pts[3]
                t = rng.uniform(0.1, 0.8)
                px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                qx, qy = a[0] + (b[0] - a[0]) * min(1, t + 0.07), a[1] + (b[1] - a[1]) * min(1, t + 0.07)
                pdraw.line([(px, py), (qx, qy)], fill=scale(WHITE if rng.random() < 0.6 else CORAL, 1.0), width=int(3 * SS))
    # Package body (drawn into the background so it reads as a solid object).
    body = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(body)
    bdraw.rounded_rectangle([cx - package / 2, cy - package / 2, cx + package / 2, cy + package / 2], radius=package * 0.06, fill=(10, 24, 58, 255), outline=(40, 80, 130, 255), width=int(2 * SS))
    bdraw.rounded_rectangle([cx - die / 2 - step, cy - die / 2 - step, cx + die / 2 + step, cy + die / 2 + step], radius=die * 0.04, fill=(5, 12, 32, 255))
    alpha = arr(body)[..., 3:4] if False else (np.asarray(body, dtype=np.float32)[..., 3:4] / 255)
    bg = bg * (1 - alpha) + (np.asarray(body, dtype=np.float32)[..., :3] / 255) * alpha
    # Pins along the package edge.
    for side in range(4):
        for k in range(18):
            offset = (k - 8.5) / 8.5 * package * 0.42
            length, thick = step * 0.9, step * 0.32
            if side == 0:
                box = [cx + package / 2 - length, cy + offset - thick, cx + package / 2 - 2, cy + offset + thick]
            elif side == 1:
                box = [cx - package / 2 + 2, cy + offset - thick, cx - package / 2 + length, cy + offset + thick]
            elif side == 2:
                box = [cx + offset - thick, cy + package / 2 - length, cx + offset + thick, cy + package / 2 - 2]
            else:
                box = [cx + offset - thick, cy - package / 2 + 2, cx + offset + thick, cy - package / 2 + length]
            cdraw.rectangle(box, fill=scale(CYAN, 0.35))
    # Die: a grid of pixel cores; a hot coral cluster is the "NPU".
    grid = 7
    cell = die / grid
    hot = {(3, 2), (3, 3), (4, 2), (4, 3), (2, 3)}
    for gx in range(grid):
        for gy in range(grid):
            x0 = cx - die / 2 + gx * cell + cell * 0.12
            y0 = cy - die / 2 + gy * cell + cell * 0.12
            box = [x0, y0, x0 + cell * 0.76, y0 + cell * 0.76]
            if (gx, gy) in hot:
                cdraw.rectangle(box, fill=scale(CORAL, rng.uniform(0.85, 1.0)))
            else:
                cdraw.rectangle(box, fill=scale(CYAN, rng.uniform(0.18, 0.62)))
    # Parameter slider etched across the die top.
    slider(cdraw, cx, cy + die / 2 + package * 0.12, package * 0.5, step * 0.55, step * 0.9, scale(WHITE, 0.9))
    heat, hdraw = light(W, H)
    r = die * 0.55
    hdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=scale(CORAL, 0.55))
    image = bg + glow(traces, ((2, 0.6), (12, 0.4), (40, 0.25))) + glow(pulses, ((3, 1.0), (14, 0.7), (40, 0.4))) + glow(core, ((2, 0.8), (12, 0.6), (50, 0.4)))
    image += arr(heat.filter(ImageFilter.GaussianBlur(70 * SS))) * 0.9
    image += stars(W, H, rng, 90, (0.1, 0.4))
    return finish(image, W, H, rng, exposure=1.1)


# --- 3. Agent Swarm -------------------------------------------------------------------

def agent_swarm(W, H, rng):
    landscape = W >= H
    cx, cy = W * SS / 2, H * SS * (0.5 if landscape else 0.43)
    unit = min(W, H) * SS
    bg = background(W, H, (cx / (W * SS), cy / (H * SS)), tint=CYAN, rng=rng)
    orbits, odraw = light(W, H)
    links, kdraw = light(W, H)
    actors, adraw = light(W, H)
    rx, ry = (unit * 0.78, unit * 0.30) if landscape else (unit * 0.42, unit * 0.62)
    tilts = [-0.18, 0.22]
    agents = []
    for index, tilt in enumerate(tilts):
        sx, sy = rx * (1 - 0.18 * index), ry * (1 - 0.18 * index)
        pts = []
        for t in np.linspace(0, 2 * math.pi, 240):
            x, y = sx * math.cos(t), sy * math.sin(t)
            pts.append((cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt)))
        odraw.line(pts, fill=scale(CYAN, 0.22), width=int(1.4 * SS))
        for k in range(3):
            t = 2 * math.pi * (k / 3) + index * 0.9 + rng.uniform(-0.2, 0.2)
            x, y = sx * math.cos(t), sy * math.sin(t)
            agents.append((cx + x * math.cos(tilt) - y * math.sin(tilt), cy + x * math.sin(tilt) + y * math.cos(tilt)))

    def arc(a, b, bend, color, packets, packet_color):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        nx, ny = -(b[1] - a[1]), b[0] - a[0]
        norm = math.hypot(nx, ny) or 1
        ctrl = (mx + nx / norm * bend, my + ny / norm * bend)
        pts = [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * ctrl[0] + t ** 2 * b[0], (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * ctrl[1] + t ** 2 * b[1]) for t in np.linspace(0, 1, 80)]
        kdraw.line(pts, fill=color, width=int(1.6 * SS))
        for t in packets:
            x, y = pts[int(t * 79)]
            r = unit * 0.0055
            kdraw.ellipse([x - r, y - r, x + r, y + r], fill=packet_color)

    for i, agent in enumerate(agents):
        arc((cx, cy), agent, unit * rng.uniform(-0.12, 0.12), scale(CYAN, 0.35), rng.uniform(0.2, 0.85, 2), scale(WHITE, 0.95) if i % 2 else scale(CORAL, 1.0))
    for i in range(len(agents)):
        a, b = agents[i], agents[(i + 2) % len(agents)]
        arc(a, b, unit * rng.uniform(0.08, 0.2) * rng.choice([-1, 1]), scale(CYAN, 0.16), rng.uniform(0.3, 0.7, 1), scale(CYAN_SOFT, 0.8))
    # Agents: rounded pixel tiles, each with a tiny slider (a "parameter" it owns).
    for i, (x, y) in enumerate(agents):
        size = unit * 0.05
        color = [CYAN_SOFT, CORAL, WHITE][i % 3]
        adraw.rounded_rectangle([x - size, y - size, x + size, y + size], radius=size * 0.28, outline=scale(color, 1.0), width=int(2.6 * SS))
        slider(adraw, x, y, size * 1.3, size * 0.11, size * 0.17, scale(color, 0.95), knob_pos=0.4 + 0.06 * (i % 4))
        for dx in (-1, 1):
            q = size * 0.18
            adraw.rectangle([x + dx * size * 1.35 - q, y - size * 1.25 - q, x + dx * size * 1.35 + q, y - size * 1.25 + q], fill=scale(CORAL, 0.7))
    # Hub: concentric rings and the logo slider.
    for k, (radius, bright) in enumerate([(0.13, 0.25), (0.10, 0.45), (0.075, 0.9)]):
        r = unit * radius
        adraw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=scale(CYAN_SOFT if k < 2 else WHITE, bright), width=int((1.5 + k) * SS))
    slider(adraw, cx, cy, unit * 0.11, unit * 0.011, unit * 0.017, scale(WHITE, 0.85))
    core, cdraw = light(W, H)
    r = unit * 0.16
    cdraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=scale(CYAN, 0.45))
    image = bg + glow(orbits, ((2, 0.5), (10, 0.3))) + glow(links, ((2, 0.8), (10, 0.5), (36, 0.3))) + glow(actors, ((3, 1.0), (14, 0.65), (50, 0.4)))
    image += arr(core.filter(ImageFilter.GaussianBlur(60 * SS))) * 0.8
    image += stars(W, H, rng, 220)
    image += bokeh(W, H, rng, 14, [CYAN, CORAL], intensity=(0.04, 0.12))
    return finish(image, W, H, rng)


# --- 4. The Fair Duel ------------------------------------------------------------------

PIXEL_FONT = {
    "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
}


def fair_duel(W, H, rng):
    landscape = W >= H
    unit = min(W, H) * SS
    WW, HH = W * SS, H * SS
    yy, xx = np.mgrid[0:HH, 0:WW].astype(np.float32)
    # Diagonal split: signed distance to the clash line.
    if landscape:
        nx, ny = 1.0, -0.32
    else:
        nx, ny = 0.32, 1.0
    norm = math.hypot(nx, ny)
    side = ((xx - WW / 2) * nx + (yy - HH / 2) * ny) / norm / unit
    bg = background(W, H, rng=rng)
    left = np.clip(0.5 - side * 1.2, 0, 1)[..., None] ** 1.6
    right = np.clip(0.5 + side * 1.2, 0, 1)[..., None] ** 1.6
    bg = bg + left * np.array(CYAN, dtype=np.float32) / 255 * 0.16 + right * np.array(CORAL, dtype=np.float32) / 255 * 0.14
    seam = np.exp(-(side * 120) ** 2)[..., None] + 0.35 * np.exp(-(side * 28) ** 2)[..., None]
    bg = bg + seam * np.array(WHITE, dtype=np.float32) / 255 * 0.6
    streaks, sdraw = light(W, H)
    emblems, edraw = light(W, H)
    sparks, kdraw = light(W, H)
    # Motion streaks rushing toward the seam from each side.
    for _ in range(140):
        s = rng.choice([-1, 1])
        along = rng.uniform(-0.9, 0.9)
        dist = rng.uniform(0.08, 0.9)
        length = rng.uniform(0.04, 0.22)
        tx, ty = -ny / norm, nx / norm
        bx = WW / 2 + tx * along * unit * 1.2 + (nx / norm) * s * dist * unit
        by = HH / 2 + ty * along * unit * 1.2 + (ny / norm) * s * dist * unit
        ex = bx - (nx / norm) * s * length * unit
        ey = by - (ny / norm) * s * length * unit
        color = CYAN_SOFT if s < 0 else CORAL
        sdraw.line([(bx, by), (ex, ey)], fill=scale(color, rng.uniform(0.15, 0.55)), width=int(rng.uniform(1, 2.6) * SS))
    # Sparks along the seam.
    for _ in range(260):
        along = rng.uniform(-1.0, 1.0)
        px = WW / 2 + (-ny / norm) * along * unit * 1.1
        py = HH / 2 + (nx / norm) * along * unit * 1.1
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.exponential(0.018) * unit
        color = WHITE if rng.random() < 0.6 else (CORAL if rng.random() < 0.5 else CYAN_SOFT)
        kdraw.line([(px, py), (px + math.cos(angle) * length, py + math.sin(angle) * length)], fill=scale(color, rng.uniform(0.4, 1.0)), width=int(1.4 * SS))
    # Emblems: two mirrored rings, each holding a parameter slider.
    offset = 0.30 if landscape else 0.25
    centers = [(WW / 2 - (nx / norm) * offset * unit * (1.9 if landscape else 1.2), HH / 2 - (ny / norm) * offset * unit * (1.0 if landscape else 1.6)), (WW / 2 + (nx / norm) * offset * unit * (1.9 if landscape else 1.2), HH / 2 + (ny / norm) * offset * unit * (1.0 if landscape else 1.6))]
    for (ex, ey), color, knob in ((centers[0], CYAN_SOFT, 0.40), (centers[1], CORAL, 0.62)):
        for radius, bright, width in ((0.17, 0.25, 1.5), (0.135, 0.55, 2.2), (0.105, 1.0, 3.2)):
            r = unit * radius
            edraw.ellipse([ex - r, ey - r, ex + r, ey + r], outline=scale(color, bright), width=int(width * SS))
        for k in range(24):
            t = 2 * math.pi * k / 24
            r1, r2 = unit * 0.152, unit * (0.16 if k % 3 else 0.168)
            edraw.line([(ex + math.cos(t) * r1, ey + math.sin(t) * r1), (ex + math.cos(t) * r2, ey + math.sin(t) * r2)], fill=scale(color, 0.6), width=int(1.6 * SS))
        slider(edraw, ex, ey, unit * 0.15, unit * 0.012, unit * 0.019, scale(WHITE, 1.0), knob_pos=knob)
    # Pixel "VS" on the seam.
    block = unit * (0.024 if landscape else 0.03)
    gap = block * 0.07
    text_w = (5 * 2 + 2) * block
    x0, y0 = WW / 2 - text_w / 2, HH / 2 - 3.5 * block
    vs, vdraw = light(W, H)
    for index, letter in enumerate("VS"):
        for row, bits in enumerate(PIXEL_FONT[letter]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    bx = x0 + (index * 7 + col) * block
                    by = y0 + row * block
                    vdraw.rectangle([bx + gap, by + gap, bx + block - gap, by + block - gap], fill=WHITE)
    plate = Image.new("RGBA", (WW, HH), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([x0 - block * 1.1, y0 - block * 1.1, x0 + text_w + block * 1.1, y0 + 8.1 * block], radius=block * 0.8, fill=(3, 9, 28, 235))
    alpha = np.asarray(plate, dtype=np.float32)[..., 3:4] / 255
    image = bg + glow(streaks, ((2, 0.6), (10, 0.3))) + glow(sparks, ((2, 0.9), (8, 0.5), (30, 0.3))) + glow(emblems, ((3, 1.0), (14, 0.6), (50, 0.4)))
    image = image * (1 - alpha * 0.92) + (np.asarray(plate, dtype=np.float32)[..., :3] / 255) * alpha * 0.92
    image += glow(vs, ((2, 0.5), (10, 0.35), (34, 0.25)))
    image += stars(W, H, rng, 70, (0.1, 0.35))
    return finish(image, W, H, rng, exposure=1.05)


# --- 5. Signal from Noise ----------------------------------------------------------------

def signal_from_noise(W, H, rng):
    point, landscape = flow_mapper(W, H)
    unit = min(W, H) * SS
    bg = background(W, H, (0.5, 0.5), tint=CYAN, rng=rng, pixels=False)
    noise, ndraw = light(W, H)
    flows, fdraw = light(W, H)
    prism, pdraw = light(W, H)
    tokens, tdraw = light(W, H)
    # Noise: scattered pixel squares of every size and colour.
    for _ in range(520):
        u = abs(rng.normal(0, 0.16))
        v = rng.uniform(0.04, 0.96)
        x, y = point(min(0.42, u), v)
        s = rng.uniform(0.003, 0.016) * unit
        color = [CYAN, CORAL, WHITE, CYAN_SOFT][int(rng.integers(4))]
        ndraw.rectangle([x - s, y - s, x + s, y + s], fill=scale(color, rng.uniform(0.12, 0.7)))
    # Flow lines from noise into the lens.
    lens_u = 0.5
    for _ in range(46):
        v0 = rng.uniform(0.08, 0.92)
        pts = []
        for t in np.linspace(0, 1, 60):
            u = 0.06 + (lens_u - 0.06) * t
            v = v0 + (0.5 - v0) * (t ** 2.2) + math.sin(t * math.pi * rng.uniform(1, 3)) * 0.02 * (1 - t)
            pts.append(point(u, v))
        fdraw.line(pts, fill=scale(CYAN, rng.uniform(0.08, 0.3)), width=int(1.3 * SS))
    # Ordered lanes of identical tokens leaving the lens.
    lanes = 9
    token = unit * 0.016
    for lane in range(lanes):
        v_end = 0.18 + 0.64 * lane / (lanes - 1)
        pts = []
        for t in np.linspace(0, 1, 60):
            u = lens_u + (0.96 - lens_u) * t
            v = 0.5 + (v_end - 0.5) * (1 - (1 - t) ** 3)
            pts.append(point(u, v))
        fdraw.line(pts, fill=scale(CYAN_SOFT, 0.22), width=int(1.2 * SS))
        for k, t in enumerate(np.linspace(0.18, 1.0, 14)):
            u = lens_u + (0.96 - lens_u) * t
            v = 0.5 + (v_end - 0.5) * (1 - (1 - t) ** 3)
            x, y = point(u, v)
            color = CORAL if (lane * 7 + k) % 11 == 0 else CYAN_SOFT
            bright = 0.35 + 0.65 * t
            tdraw.rectangle([x - token / 2, y - token / 2, x + token / 2, y + token / 2], fill=scale(color, bright))
    # The lens: a glowing triangle (prism) with an inner slider.
    cx, cy = point(lens_u, 0.5)
    r = unit * 0.13
    if landscape:
        tri = [(cx - r * 0.8, cy - r), (cx - r * 0.8, cy + r), (cx + r * 0.95, cy)]
    else:
        tri = [(cx - r, cy - r * 0.8), (cx + r, cy - r * 0.8), (cx, cy + r * 0.95)]
    pdraw.polygon(tri, outline=scale(WHITE, 1.0), width=int(3 * SS))
    inner = [(cx + (x - cx) * 0.72, cy + (y - cy) * 0.72) for x, y in tri]
    pdraw.polygon(inner, outline=scale(CYAN_SOFT, 0.6), width=int(1.6 * SS))
    slider(pdraw, cx - (r * 0.14 if landscape else 0), cy - (0 if landscape else r * 0.12), r * 0.7, r * 0.05, r * 0.08, scale(CORAL, 1.0), knob_pos=0.6)
    halo, hdraw = light(W, H)
    hr = r * 1.5
    hdraw.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=scale(CYAN, 0.5))
    image = bg + glow(noise, ((2, 0.6), (10, 0.35), (30, 0.2))) + glow(flows, ((2, 0.6), (12, 0.35))) + glow(tokens, ((2, 0.8), (12, 0.55), (40, 0.3))) + glow(prism, ((3, 1.0), (16, 0.7), (60, 0.45)))
    image += arr(halo.filter(ImageFilter.GaussianBlur(70 * SS))) * 0.7
    image += stars(W, H, rng, 80, (0.1, 0.4))
    return finish(image, W, H, rng)


THEMES = {
    "01-neural-constellation": neural_constellation,
    "02-local-silicon": local_silicon,
    "03-agent-swarm": agent_swarm,
    "04-fair-duel": fair_duel,
    "05-signal-from-noise": signal_from_noise,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "graphics" / "ai")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--only", choices=list(THEMES))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, render in THEMES.items():
        if args.only and name != args.only:
            continue
        for label, (W, H) in FORMATS.items():
            rng = np.random.default_rng(args.seed)
            image = render(W, H, rng)
            path = args.out / f"{name}-{label}.png"
            image.save(path, optimize=True)
            print(path)


if __name__ == "__main__":
    main()
