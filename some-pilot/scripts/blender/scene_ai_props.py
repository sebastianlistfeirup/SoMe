"""3D props for AI graphics (no text in the render except podium numbers; labels are composited from anchors).

  gpu      exploded graphics card: backplate, PCB (GPU + 16 GDDR chips tagged gpu / vram), cooler
  vram     memory "Tetris": a 32 GB well with 8B + 32B blocks inside, the 70B block towering next to it
  books    context window as books: 1 book (128K), 8 books (1M), a shelf of 78 books (10M)
  agents   agent team: three glowing glass nodes joined by light paths with message pulses
  podium   top-3 podium with 3D numbers
  locks    open vs closed weights: an open and a locked padlock on lit pedestals

blender -b -P scene_ai_props.py -- --scene gpu --format 16x9 --samples 192 --out <dir> [--preview]

Writes <out>/clean.png and <out>/anchors.json (pixel positions of named points for compose_ai_extras.py).
The gpu scene also writes mask-gpu.png and mask-vram.png (picked up by compose_hardware.py).
Run `python pp_textures.py` first (textures are made with Pillow outside Blender).
"""

import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import pp_lib as pp  # noqa: E402
import scene_ai_backdrops as bd  # noqa: E402
from pp_textures import chip_marking_texture, contacts_texture, pcb_texture  # noqa: E402

MM = pp.MM
FONT = "C:/Windows/Fonts/segoeuib.ttf"
ANCHORS = {}
CYAN = (0.0, 0.55, 1.0)
CORAL = (1.0, 0.28, 0.14)
ICE = (0.75, 0.9, 1.0)


def anchor(name, point_mm):
    ANCHORS[name] = tuple(v * MM for v in point_mm)


def tube(name, points_mm, radius_mm, material, resolution=6):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius_mm * MM
    curve.bevel_resolution = resolution
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points_mm) - 1)
    for point, (x, y, z) in zip(spline.points, points_mm):
        point.co = (x * MM, y * MM, z * MM, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def bezier(a, c, b, n=48):
    return [tuple((1 - t) ** 2 * a[i] + 2 * (1 - t) * t * c[i] + t ** 2 * b[i] for i in range(3)) for t in (k / (n - 1) for k in range(n))]


def sphere(name, radius_mm, location_mm, material, segments=64):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius_mm * MM, segments=segments, ring_count=segments // 2, location=tuple(v * MM for v in location_mm))
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def torus(name, major_mm, minor_mm, location_mm, material, rotation_deg=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major_mm * MM, minor_radius=minor_mm * MM, major_segments=96, minor_segments=12,
                                     location=tuple(v * MM for v in location_mm), rotation=[math.radians(a) for a in rotation_deg])
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(material)
    return obj


def text3d(name, body, location_mm, size_mm, depth_mm, material, rotation_deg=(90, 0, 0)):
    curve = bpy.data.curves.new(name, "FONT")
    curve.body = body
    curve.font = bpy.data.fonts.load(FONT, check_existing=True)
    curve.size = size_mm * MM
    curve.extrude = depth_mm * MM / 2
    curve.bevel_depth = 0.6 * MM
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = tuple(v * MM for v in location_mm)
    obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    obj.data.materials.append(material)
    return obj


def reflector(name, location_m, rotation_deg, size_m, strength=3.0, color=(1, 1, 1)):
    """Emissive softbox seen only in reflections: gives chrome and brushed metal something to mirror."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=location_m, rotation=[math.radians(a) for a in rotation_deg])
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_m[0], size_m[1], 1)
    obj.data.materials.append(bd.emission(name + "_mat", color, strength))
    obj.visible_camera = False
    obj.visible_shadow = False
    obj.visible_diffuse = False
    obj["pp_reflector"] = True
    return obj


def boolean_cut(target, cutter):
    mod = target.modifiers.new("cut_" + cutter.name, "BOOLEAN")
    mod.object = cutter
    mod.operation = "DIFFERENCE"
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    return mod


# --- 1. exploded graphics card ----------------------------------------------------------------

def gpu(fmt, mats):
    rng = random.Random(4)
    portrait = fmt == "9x16"
    pp.floor_backdrop(pp.mat_floor(radius_m=0.8), size=8, wall=False)
    bp_y, pcb_y, cool_y = (-120, 0, 150) if portrait else (-80, 0, 100)
    bp_z, pcb_z, cool_z = (30, 120, 230) if portrait else (30, 110, 205)

    # Backplate (bottom layer)
    pp.box("backplate", (304, 124, 2.5), (0, bp_y, bp_z), pp.mat_brushed("backplate_mat", (0.20, 0.21, 0.23), roughness=0.3), bevel_mm=2)
    for k in range(9):
        pp.box(f"bp_slot_{k}", (2.2, 60, 0.4), (-120 + k * 30, bp_y, bp_z + 1.3), mats.plastic_black)

    # PCB with GPU package, 16 GDDR chips, VRM, PCIe fingers
    board = pp.mat_image("gpu_board_mat", pcb_texture("gpu_board", base=(10, 11, 14), trace=(22, 24, 30), seed=41, dark=True), roughness=0.36, coat=0.55, bump_strength=0.04)
    top = pcb_z + 0.8
    pp.box("pcb", (300, 122, 1.6), (0, pcb_y, pcb_z), board)
    pp.box("pcb_tab", (88, 8, 1.6), (-45, pcb_y - 65, pcb_z), board)
    fingers = pp.mat_image("pcie_mat", contacts_texture("pcie_contacts", 82), roughness=0.22, metallic=0.85)
    pp.box("pcie_fingers", (84, 7.6, 1.65), (-45, pcb_y - 65, pcb_z), fingers)
    gx, gy = -30, pcb_y + 2
    substrate = pp.mat_basic("substrate", (0.025, 0.05, 0.04), roughness=0.45, coat=0.4)
    pp.box("gpu_substrate", (58, 58, 1.6), (gx, gy, top + 0.8), substrate, bevel_mm=0.6, group="gpu")
    die = pp.mat_image("gpu_die_mat", chip_marking_texture("gpu_die", "GN22-X6\nA1 2544\nTAIWAN"), roughness=0.16, coat=0.9)
    pp.box("gpu_die", (31, 27, 0.9), (gx, gy, top + 2.05), die, bevel_mm=0.2, group="gpu")
    for k in range(24):
        side = k % 4
        t = (k // 4) / 5 - 0.5
        x, y = [(gx + t * 48, gy + 25), (gx + t * 48, gy - 25), (gx + 25, gy + t * 48), (gx - 25, gy + t * 48)][side]
        pp.box(f"gpu_cap{k}", (1.6, 0.8, 0.7), (x, y, top + 1.95), mats.ceramic, group="gpu")
    vram = pp.mat_image("vram_mat", chip_marking_texture("vram_chip", "GDDR7\nD8BZC 2G\n2543"), roughness=0.55)
    slots = [(gx - 52, gy + d, 90) for d in (-38, -19, 0, 19, 38)] + [(gx + 52, gy + d, 90) for d in (-38, -19, 0, 19, 38)]
    slots += [(gx + d, gy + 48, 0) for d in (-19, 0, 19)] + [(gx + d, gy - 48, 0) for d in (-19, 0, 19)]
    for k, (x, y, rot) in enumerate(slots):
        pp.box(f"vram_{k}", (14, 12, 1.1), (x, y, top + 0.55), vram, bevel_mm=0.15, group="vram", rotation_deg=(0, 0, rot))
    for row, y in enumerate((-30, 0, 30)):
        for i in range(7):
            x = 52 + i * 13
            pp.box(f"choke_{row}_{i}", (9.5, 9.5, 6.5), (x, pcb_y + y, top + 3.25), mats.inductor, bevel_mm=0.6)
            pp.box(f"mosfet_{row}_{i}", (6, 5, 1.0), (x, pcb_y + y - 10, top + 0.5), mats.chip, bevel_mm=0.1)
    for k in range(14):
        pp.cylinder(f"polycap_{k}", 3.4, 5.5, (50 + (k % 7) * 13, pcb_y + (48 if k < 7 else -48), top + 2.75), mats.cap_alu, bevel_mm=0.4)
    pp.box("power_conn", (21, 9, 9.5), (110, pcb_y + 54, top + 4.75), mats.plastic_black, bevel_mm=0.5)
    for k in range(6):
        pp.box(f"dp_ic_{k}", (5, 5, 0.9), (-135 + (k % 2) * 9, pcb_y - 30 + (k // 2) * 22, top + 0.45), mats.chip, bevel_mm=0.1)
    pp.smd_scatter("gpu_smd", (-148, pcb_y - 58, 148, pcb_y + 58), top, 420, mats, rng,
                   avoid=[(gx - 62, gy - 58, gx + 62, gy + 58), (44, pcb_y - 54, 148, pcb_y + 54)])

    # Cooler: vapour chamber, fin stack, heat pipes, shroud with three fans
    pp.box("vapor_chamber", (110, 104, 4), (gx, cool_y, cool_z - 24), mats.nickel, bevel_mm=1)
    pp.heatsink_fins("fins", (0, cool_y), cool_z - 22, (296, 118, 32), 100, mats, material=mats.alu, axis="y")
    for k in range(5):
        y = cool_y - 40 + k * 20
        tube(f"heatpipe_{k}", [(-150, y, cool_z - 8), (150, y, cool_z - 8)], 3.0, mats.copper)
    shroud = pp.box("shroud", (306, 126, 14), (0, cool_y, cool_z + 18), pp.mat_brushed("shroud_mat", (0.42, 0.43, 0.46), roughness=0.28), bevel_mm=3)
    for k, x in enumerate((-100, 0, 100)):
        cutter = pp.cylinder(f"shroud_hole_{k}", 44, 40, (x, cool_y, cool_z + 18), mats.plastic_black)
        boolean_cut(shroud, cutter)
        torus(f"fan_frame_{k}", 44.5, 2.2, (x, cool_y, cool_z + 24), mats.plastic_black)
        pp.blower_fan(f"fan_{k}", (x, cool_y), cool_z + 8, mats, radius_mm=42, blades=11, height_mm=12, housing=False)
    pp.box("light_bar", (250, 1.2, 3), (0, cool_y - 63.2, cool_z + 18), bd.emission("gpu_bar", CYAN, 8))

    anchor("gpu", (gx, gy, top + 3))
    anchor("vram", (gx - 52, gy - 38, top + 1))
    pp.area_light("key", (-0.35, -0.55, 0.75), (40, 0, -30), 0.9, 55)
    pp.area_light("top", (0.1, 0.1, 0.9), (0, 0, 0), 0.8, 30)
    pp.area_light("rim_cyan", (0.4, 0.45, 0.25), (-70, 0, 135), 0.5, 30, color=(0.4, 0.75, 1.0))
    pp.world((0.002, 0.003, 0.007), 1.0)
    reflector("gpu_softbox", (0.0, -0.4, 0.9), (25, 0, 0), (1.2, 0.5), 2.5)
    if portrait:
        pp.camera((0.10, -0.85, 0.80), (0.0, 0.02, 0.14), lens=38, fstop=8)
    else:
        pp.camera((0.20, -0.70, 0.56), (0.0, 0.015, 0.145), lens=40, fstop=8)


# --- 2. VRAM tetris ----------------------------------------------------------------------------

def vram(fmt, mats):
    portrait = fmt == "9x16"
    pp.floor_backdrop(pp.mat_floor(radius_m=0.9, color=(0.0015, 0.002, 0.005)), size=10, wall=False)
    pitch, cube, base = 43, 38, 8
    well_x, tower_x = (-125, 125) if portrait else (-150, 150)
    inner = 4 * pitch
    height = 8 * pitch
    wall = bd.glass("well_glass", (0.85, 0.95, 1.0), 0.05)
    pp.box("well_floor", (inner + 16, 64, base), (well_x, 0, base / 2), wall, bevel_mm=2)
    for side in (-1, 1):
        pp.box(f"well_wall_{side}", (8, 64, height + 24), (well_x + side * (inner / 2 + 4), 0, base + (height + 24) / 2), wall, bevel_mm=2)
    line = bd.emission("level", ICE, 5)
    limit = bd.emission("level_top", CORAL, 9)
    for gb in (8, 16, 24, 32):
        z = base + gb / 4 * pitch
        pp.box(f"level_{gb}", (inner + 40, 2, 2.4), (well_x, 34, z), limit if gb == 32 else line)
        anchor(f"gb{gb}", (well_x - inner / 2 - 26, 0, z))

    def stack(prefix, count, start, x0, z0, color, strength):
        shell = bd.glass(prefix + "_glass", (0.9, 0.97, 1.0), 0.1)
        core = bd.emission(prefix + "_core", color, strength)
        points = []
        for k in range(count):
            slot = start + k
            col, row = slot % 4, slot // 4
            x, z = x0 + (col - 1.5) * pitch, z0 + pitch / 2 + row * pitch
            pp.box(f"{prefix}_{k}", (cube, cube, cube), (x, 0, z), shell, bevel_mm=3, segments=4)
            pp.box(f"{prefix}_core_{k}", (cube * 0.6,) * 3, (x, 0, z), core, bevel_mm=2)
            points.append((x, z))
        cx = sum(p[0] for p in points) / len(points)
        cz = sum(p[1] for p in points) / len(points)
        return cx, cz, max(p[1] for p in points)

    cx, cz, _ = stack("b8", 5, 0, well_x, base, CYAN, 2.2)
    anchor("b8", (cx, -cube / 2, cz))
    cx, cz, _ = stack("b32", 20, 5, well_x, base, (0.12, 0.25, 1.0), 1.6)
    anchor("b32", (cx, -cube / 2, cz))
    hover = 46
    cx, cz, top = stack("b70", 43, 0, tower_x, hover, CORAL, 2.0)
    anchor("b70", (tower_x, -cube / 2, top + pitch * 0.9))
    anchor("b70_mid", (tower_x, -cube / 2, cz))
    anchor("well_top", (well_x, -cube / 2, base + height + 30))
    bd.volume_fog(0.006)
    bd.bokeh_field(50, (-1600, 1600), (1400, 3200), (0, 1400), seed=8, size=(10, 30))
    pp.area_light("key", (-0.5, -0.7, 0.9), (45, 0, -35), 1.0, 40)
    pp.area_light("top", (0.0, 0.2, 1.2), (0, 0, 0), 1.0, 25)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((0.0, -1.55, 0.55), (0.0, 0.0, 0.29), lens=42, fstop=5.6, focus=(0, 0, 0.25))
    else:
        pp.camera((0.0, -1.25, 0.45), (0.0, 0.0, 0.27), lens=38, fstop=5.6, focus=(0, 0, 0.25))


# --- 3. context window as books ---------------------------------------------------------------

COVERS = [(0.02, 0.05, 0.12), (0.01, 0.16, 0.22), (0.50, 0.08, 0.04), (0.09, 0.10, 0.12), (0.62, 0.60, 0.55),
          (0.03, 0.07, 0.05), (0.22, 0.035, 0.045), (0.0, 0.30, 0.45), (0.35, 0.26, 0.13), (0.015, 0.015, 0.02)]


def pages_material(name, axis):
    mat, nodes, links, bsdf = pp._principled(name)
    coord = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = axis
    wave.inputs["Scale"].default_value = 900
    wave.inputs["Distortion"].default_value = 2
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.55, 0.51, 0.43, 1)
    ramp.color_ramp.elements[1].color = (0.80, 0.76, 0.66, 1)
    links.new(coord.outputs["Object"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    pp._set(bsdf, "Roughness", 0.85)
    return mat


def book(prefix, center_mm, size_mm, cover, pages, band, standing, rng, rot=0.0):
    """Hardcover: two boards, spine (facing -y), inset page block. Flat books lie along x; standing books along z."""
    cx, cy, cz = center_mm
    length, width, thick = size_mm
    parts = []
    if standing:
        for side in (-1, 1):
            parts.append(pp.box(f"{prefix}_board{side}", (1.6, width, length), (cx + side * (thick / 2 - 0.8), cy, cz), cover, bevel_mm=0.5))
        parts.append(pp.box(f"{prefix}_spine", (thick, 2.2, length), (cx, cy - width / 2 + 1.1, cz), cover, bevel_mm=1.0))
        parts.append(pp.box(f"{prefix}_pages", (thick - 3.0, width - 4, length - 5), (cx, cy + 1.5, cz), pages))
        if band:
            for f in (0.82, 0.16):
                parts.append(pp.box(f"{prefix}_band{f}", (thick * 0.86, 0.6, 3.5), (cx, cy - width / 2 - 0.1, cz - length / 2 + length * f), band))
    else:
        for side in (-1, 1):
            parts.append(pp.box(f"{prefix}_board{side}", (length, width, 1.6), (cx, cy, cz + side * (thick / 2 - 0.8)), cover, bevel_mm=0.5))
        parts.append(pp.box(f"{prefix}_spine", (length, 2.2, thick), (cx, cy - width / 2 + 1.1, cz), cover, bevel_mm=1.0))
        parts.append(pp.box(f"{prefix}_pages", (length - 5, width - 4, thick - 3.0), (cx, cy + 1.5, cz), pages))
        if band:
            for f in (0.12, 0.88):
                parts.append(pp.box(f"{prefix}_band{f}", (3.5, 0.6, thick * 0.86), (cx - length / 2 + length * f, cy - width / 2 - 0.1, cz), band))
    return pp.rotate_group(parts, (cx, cy), rot)


def books(fmt, mats):
    rng = random.Random(12)
    portrait = fmt == "9x16"
    floor = pp.mat_basic("books_floor", (0.006, 0.008, 0.014), roughness=0.22, coat=0.6, coat_rough=0.08)
    pp.floor_backdrop(floor, size=12, wall=False)
    covers = [pp.mat_basic(f"cover_{k}", c, roughness=0.55, coat=0.25, coat_rough=0.3) for k, c in enumerate(COVERS)]
    pages_flat = pages_material("pages_flat", "Z")
    pages_stand = pages_material("pages_stand", "X")
    band = pp.mat_basic("spine_band", (0.85, 0.66, 0.3), metallic=1.0, roughness=0.3)
    if portrait:
        one, eight, shelf = (-150, -330), (150, -330), (0, 260)
    else:
        one, eight, shelf = (-600, -40), (-300, -40), (230, 40)

    t = 22
    book("one", (one[0], one[1], t / 2), (235, 155, t), covers[2], pages_flat, band, False, rng, rot=-8)
    anchor("one", (one[0], one[1], t + 70))
    z = 0
    for k in range(8):
        thick = rng.uniform(19, 25)
        book(f"stack{k}", (eight[0] + rng.uniform(-6, 6), eight[1] + rng.uniform(-5, 5), z + thick / 2), (235 - rng.uniform(0, 20), 155 - rng.uniform(0, 8), thick),
             covers[(k * 3 + 1) % len(covers)], pages_flat, band if k % 3 == 0 else None, False, rng, rot=rng.uniform(-5, 5))
        z += thick
    anchor("eight", (eight[0], eight[1], z + 70))

    wood = pp.mat_basic("shelf_wood", (0.03, 0.021, 0.015), roughness=0.45, coat=0.3)
    sx, sy = shelf
    inner_w, depth, gap_h, board = 600, 175, 262, 18
    rows = 3
    total_h = rows * gap_h + (rows + 1) * board
    for side in (-1, 1):
        pp.box(f"shelf_side{side}", (board, depth, total_h), (sx + side * (inner_w / 2 + board / 2), sy, total_h / 2), wood, bevel_mm=1.5)
    for r in range(rows + 1):
        pp.box(f"shelf_board{r}", (inner_w, depth, board), (sx, sy, board / 2 + r * (gap_h + board)), wood, bevel_mm=1.0)
    pp.box("shelf_back", (inner_w + 2 * board, 6, total_h), (sx, sy + depth / 2 - 3, total_h / 2), wood)
    count = 0
    for r in range(rows):
        base_z = board + r * (gap_h + board)
        thicknesses = [rng.uniform(18.5, 26) for _ in range(26)]
        scale = (inner_w - 26 * 0.6 - 4) / sum(thicknesses)
        x = sx - inner_w / 2 + 2
        for k, th in enumerate(thicknesses):
            th *= scale
            h = rng.uniform(205, 240)
            book(f"shelf{r}_{k}", (x + th / 2, sy - 6 + rng.uniform(-3, 3), base_z + h / 2), (h, 155, th),
                 covers[rng.randrange(len(covers))], pages_stand, band if rng.random() < 0.35 else None, True, rng)
            x += th + 0.6
            count += 1
    assert count == 78
    anchor("shelf", (sx, sy - depth / 2, total_h + 70))
    pp.area_light("key", (-0.9, -1.1, 1.4), (45, 0, -38), 1.6, 95)
    pp.area_light("fill", (1.2, -0.8, 0.8), (60, 0, 50), 1.2, 45, color=(0.55, 0.75, 1.0))
    pp.area_light("top", (0.0, 0.4, 2.0), (0, 0, 0), 1.5, 50)
    bd.volume_fog(0.004, size=10, center=(0, 0, 2))
    bd.bokeh_field(40, (-2600, 2600), (2200, 4400), (0, 2000), seed=3, size=(14, 40))
    pp.world((0.002, 0.003, 0.007), 1.0)
    if portrait:
        pp.camera((0.0, -2.35, 1.15), (0.0, 0.0, 0.36), lens=40, fstop=8, focus=(0, -0.1, 0.3))
    else:
        pp.camera((0.0, -2.45, 0.95), (-0.06, 0.0, 0.42), lens=40, fstop=8, focus=(0, 0, 0.3))


# --- 4. agent team -----------------------------------------------------------------------------

def agents(fmt, mats):
    portrait = fmt == "9x16"
    pp.floor_backdrop(pp.mat_floor(radius_m=1.4, color=(0.0015, 0.002, 0.005)), size=12, wall=False)
    if portrait:
        nodes = {"planner": (0, 60, 620), "coder": (-190, 0, 300), "reviewer": (190, 0, 300)}
    else:
        nodes = {"planner": (0, 120, 430), "coder": (-340, 0, 190), "reviewer": (340, 0, 190)}
    colors = {"planner": ICE, "coder": CYAN, "reviewer": CORAL}
    shell = bd.glass("node_glass", (0.9, 0.97, 1.0), 0.05)
    for name, pos in nodes.items():
        sphere(f"{name}_shell", 78, pos, shell)
        sphere(f"{name}_core", 30, pos, bd.emission(f"{name}_core", colors[name], 3.5), segments=32)
        torus(f"{name}_ring", 104, 1.6, pos, bd.emission(f"{name}_ring", colors[name], 2.5), rotation_deg=(72, 0, 0))
        anchor(name, (pos[0], pos[1], pos[2] - 78 - 46))
    link = bd.emission("link", (0.05, 0.5, 1.0), 2.5)
    pulse = bd.emission("pulse", (0.9, 0.96, 1.0), 6)
    edges = [("planner", "coder", -1), ("coder", "reviewer", 1), ("reviewer", "planner", -1)]
    for k, (a, b, bend) in enumerate(edges):
        pa, pb = Vector(nodes[a]), Vector(nodes[b])
        direction = (pb - pa).normalized()
        start, end = pa + direction * 84, pb - direction * 84
        mid = (start + end) / 2 + Vector((0, -60, 70 * bend))
        points = bezier(tuple(start), tuple(mid), tuple(end))
        tube(f"link_{k}", points, 2.2, link)
        for j, t in enumerate((0.28, 0.52, 0.76)):
            sphere(f"pulse_{k}_{j}", 7, points[int(t * (len(points) - 1))], pulse, segments=24)
    bd.volume_fog(0.008)
    bd.bokeh_field(60, (-2400, 2400), (2000, 4200), (-200, 1800), seed=17, size=(12, 34))
    pp.area_light("top", (0.0, 0.2, 1.6), (0, 0, 0), 1.6, 18)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((0.0, -1.85, 0.62), (0.0, 0.0, 0.40), lens=40, fstop=4, focus=(0, 0, 0.35))
    else:
        pp.camera((0.0, -1.55, 0.50), (0.0, 0.04, 0.27), lens=40, fstop=4, focus=(0, 0, 0.3))


# --- 5. podium ----------------------------------------------------------------------------------

def podium(fmt, mats):
    pp.floor_backdrop(pp.mat_floor(radius_m=1.3, color=(0.0015, 0.002, 0.005)), size=12, wall=False)
    block = pp.mat_basic("podium_block", (0.008, 0.016, 0.04), roughness=0.12, coat=1.0, coat_rough=0.04)
    number = bd.emission("podium_number", (0.92, 0.96, 1.0), 4)
    width = 230
    for place, x, h in ((2, -258, 200), (1, 0, 290), (3, 258, 140)):
        pp.box(f"p{place}", (width, width, h), (x, 0, h / 2), block, bevel_mm=6, segments=5)
        edge = bd.emission(f"p{place}_edge", CORAL if place == 1 else CYAN, 10)
        for dx, dy, sx, sy in ((0, -width / 2, width, 3), (0, width / 2, width, 3), (-width / 2, 0, 3, width), (width / 2, 0, 3, width)):
            pp.box(f"p{place}_edge_{dx}_{dy}", (sx, sy, 3), (x + dx, dy, h + 0.5), edge)
        text3d(f"p{place}_num", str(place), (x, -width / 2 - 1.5, h * 0.5), 150 if place == 1 else 120, 5, number)
        anchor(f"p{place}", (x, 0, h + 12))
        bd.spot(f"p{place}_beam", (x * MM * 1.2, -0.2, 1.6), (x * MM, 0, h * MM), 900 if place == 1 else 600, (1.0, 0.92, 0.85) if place == 1 else (0.6, 0.82, 1.0), 16, blend=0.6)
    bd.volume_fog(0.01)
    bd.bokeh_field(60, (-2400, 2400), (2000, 4200), (-200, 1800), seed=23, size=(12, 34))
    pp.area_light("key", (-0.6, -1.2, 1.2), (50, 0, -25), 1.4, 60)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if fmt == "9x16":
        pp.camera((0.0, -2.1, 0.75), (0.0, 0.0, 0.34), lens=40, fstop=5.6, focus=(0, -0.1, 0.2))
    else:
        pp.camera((0.0, -1.75, 0.62), (0.0, 0.0, 0.26), lens=40, fstop=5.6, focus=(0, -0.1, 0.2))


# --- 6. open vs closed padlocks ----------------------------------------------------------------

def padlock(prefix, x, opened, accent):
    body_mat = pp.mat_brushed(prefix + "_body", (0.10, 0.11, 0.125), roughness=0.3)
    chrome = pp.mat_basic(prefix + "_chrome", (0.9, 0.92, 0.95), metallic=1.0, roughness=0.08)
    glow = bd.emission(prefix + "_glow", accent, 9)
    base_z = 22
    pp.cylinder(prefix + "_pedestal", 120, base_z, (x, 0, base_z / 2), pp.mat_basic(prefix + "_ped", (0.004, 0.006, 0.012), roughness=0.25, coat=0.6), vertices=128, bevel_mm=3)
    torus(prefix + "_ped_ring", 121, 1.8, (x, 0, base_z - 2), glow)
    bw, bdp, bh = 118, 50, 98
    body_z = base_z + bh / 2
    pp.box(prefix + "_lockbody", (bw, bdp, bh), (x, 0, body_z), body_mat, bevel_mm=10, segments=6)
    pp.box(prefix + "_band", (bw + 1.5, bdp + 1.5, 5), (x, 0, body_z + bh * 0.28), glow, bevel_mm=2)
    pp.cylinder(prefix + "_keyhole", 7, 3, (x, -bdp / 2 - 0.6, body_z - 8), mats_black(), rotation_deg=(90, 0, 0))
    pp.box(prefix + "_keyslot", (4.5, 3, 16), (x, -bdp / 2 - 0.6, body_z - 18), mats_black())
    top = base_z + bh
    r, leg = 36, 52
    lift = 34 if opened else 0
    points = [(-r, 0, -22 + lift)] + [(-r, 0, z) for z in range(-21 + lift, leg + lift, 4)]
    points += [(-r * math.cos(a), 0, leg + lift + r * math.sin(a)) for a in [math.pi * k / 30 for k in range(1, 30)]]
    right_end = (-4 if opened else -22) + lift
    points += [(r, 0, z) for z in range(leg + lift, right_end, -4)] + [(r, 0, right_end)]
    shackle = tube(prefix + "_shackle", points, 9, chrome, resolution=8)
    shackle.location = ((x - 0) * MM, 0, top * MM)
    if opened:
        # Swing open around the left leg.
        shackle.location = ((x - r) * MM, 0, top * MM)
        for p in shackle.data.splines[0].points:
            p.co.x += r * MM
        shackle.rotation_euler[2] = math.radians(-115)
    anchor(prefix, (x, -120, 0))
    anchor(prefix + "_top", (x, 0, top + leg + r + lift + 30))


_BLACK = {}


def mats_black():
    if "m" not in _BLACK:
        _BLACK["m"] = pp.mat_basic("lock_black", (0.005, 0.005, 0.006), roughness=0.6)
    return _BLACK["m"]


def locks(fmt, mats):
    portrait = fmt == "9x16"
    pp.floor_backdrop(pp.mat_floor(radius_m=1.2, color=(0.0015, 0.002, 0.005)), size=12, wall=False)
    spread = 165 if portrait else 230
    padlock("open", -spread, True, CYAN)
    padlock("closed", spread, False, CORAL)
    bd.volume_fog(0.006)
    bd.bokeh_field(50, (-2400, 2400), (2000, 4200), (-200, 1800), seed=31, size=(12, 34))
    pp.area_light("key", (-0.6, -0.9, 1.0), (45, 0, -30), 1.2, 60)
    pp.area_light("top", (0.0, 0.3, 1.4), (0, 0, 0), 1.2, 12)
    pp.area_light("rim", (0.0, 0.9, 0.5), (-70, 0, 0), 1.2, 40, color=(0.5, 0.75, 1.0))
    reflector("lock_softbox", (0.0, -0.9, 0.9), (55, 0, 0), (1.6, 0.6), 3.0)
    reflector("lock_strip_l", (-0.7, -0.2, 0.5), (0, 75, 0), (0.15, 0.8), 6.0, (0.6, 0.85, 1.0))
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((0.0, -1.35, 0.62), (0.0, 0.0, -0.05), lens=40, fstop=5.6, focus=(0, 0, 0.1))
    else:
        pp.camera((0.0, -1.2, 0.45), (0.0, 0.0, 0.0), lens=45, fstop=5.6, focus=(0, 0, 0.1))


# --- 7. quantization ladder --------------------------------------------------------------------

def load_data():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "content", "AI_RATINGS.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def quant(fmt, mats):
    portrait = fmt == "9x16"
    data = load_data()["quant"]
    pp.floor_backdrop(pp.mat_floor(radius_m=1.0, color=(0.0015, 0.002, 0.005)), size=10, wall=False)
    pitch, cube = 44, 39
    colors = [CORAL, (0.2, 0.3, 1.0), CYAN, (0.0, 0.7, 0.55)]
    spacing = 175 if portrait else 245
    xs = [(k - 1.5) * spacing for k in range(4)]
    width = 3 if not portrait else 3
    shell = bd.glass("q_glass", (0.9, 0.97, 1.0), 0.1)
    for k, level in enumerate(data["levels"]):
        count = round(level["gb"] / data["gb_per_cube"])
        core = bd.emission(f"q_core_{k}", colors[k], 2.0)
        x0 = xs[k]
        pp.box(f"q_base_{k}", (width * pitch + 24, 70, 8), (x0, 0, 4), pp.mat_basic(f"q_base_mat_{k}", (0.01, 0.016, 0.035), roughness=0.15, coat=1.0), bevel_mm=3)
        pp.box(f"q_base_edge_{k}", (width * pitch + 26, 2, 2.5), (x0, -36, 7.5), bd.emission(f"q_edge_{k}", colors[k], 6))
        top = 0
        for c in range(count):
            col, row = c % width, c // width
            x = x0 + (col - (width - 1) / 2) * pitch
            z = 8 + pitch / 2 + row * pitch
            pp.box(f"q_{k}_{c}", (cube, cube, cube), (x, 0, z), shell, bevel_mm=3, segments=4)
            pp.box(f"q_core_{k}_{c}", (cube * 0.6,) * 3, (x, 0, z), core, bevel_mm=2)
            top = max(top, z + cube / 2)
        anchor(f"{level['label']}_top", (x0, -cube / 2, top + 34))
        anchor(f"{level['label']}_base", (x0, -36, 0))
    bd.volume_fog(0.006)
    bd.bokeh_field(50, (-1800, 1800), (1400, 3200), (0, 1400), seed=44, size=(10, 30))
    pp.area_light("key", (-0.5, -0.8, 0.9), (45, 0, -35), 1.0, 40)
    pp.area_light("top", (0.0, 0.2, 1.3), (0, 0, 0), 1.2, 25)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((0.0, -1.75, 0.55), (0.0, 0.0, 0.27), lens=40, fstop=5.6, focus=(0, 0, 0.25))
    else:
        pp.camera((0.0, -1.45, 0.48), (0.0, 0.0, 0.25), lens=40, fstop=5.6, focus=(0, 0, 0.25))


# --- 8. local vs cloud ---------------------------------------------------------------------------

def localcloud(fmt, mats):
    portrait = fmt == "9x16"
    pp.floor_backdrop(pp.mat_floor(radius_m=1.6, color=(0.0015, 0.002, 0.005)), size=14, wall=False)
    local = (-330, -60) if not portrait else (0, -330)
    cloud = (330, 140) if not portrait else (0, 420)
    # Local: a closed mini PC on a desk slab
    wood = pp.mat_basic("desk_wood", (0.022, 0.014, 0.009), roughness=0.35, coat=0.5)
    pp.box("desk", (420, 300, 26), (local[0], local[1], 13), wood, bevel_mm=4)
    alu = pp.mat_brushed("mini_alu", (0.55, 0.56, 0.6), roughness=0.25)
    pp.box("minipc", (128, 128, 48), (local[0], local[1], 26 + 24), alu, bevel_mm=10, segments=6)
    pp.box("minipc_top", (112, 112, 1.5), (local[0], local[1], 26 + 48.6), pp.mat_basic("minipc_top_mat", (0.02, 0.022, 0.026), roughness=0.3, coat=0.6), bevel_mm=6)
    pp.box("minipc_led", (60, 1.2, 2), (local[0], local[1] - 64.4, 26 + 12), bd.emission("minipc_led_mat", CYAN, 10))
    for k in range(2):
        pp.box(f"minipc_usb_{k}", (12, 1.5, 5), (local[0] - 40 + k * 18, local[1] - 64.3, 26 + 26), mats.port_blue)
    # Cloud: three racks with LED rows on a platform
    rack = pp.mat_basic("lc_rack", (0.012, 0.013, 0.016), roughness=0.4, metallic=0.5)
    pp.box("platform", (720, 320, 20), (cloud[0], cloud[1], 10), pp.mat_basic("lc_platform", (0.01, 0.015, 0.03), roughness=0.15, coat=1.0), bevel_mm=4)
    leds = {"cyan": [], "white": []}
    rng = random.Random(8)
    for k in range(3):
        x = cloud[0] + (k - 1) * 230
        pp.box(f"lc_rack_{k}", (210, 240, 560), (x, cloud[1], 20 + 280), rack, bevel_mm=6)
        for u in range(24):
            z = 60 + u * 21
            for led in range(rng.randint(1, 3)):
                key = "white" if rng.random() < 0.3 else "cyan"
                leds[key].append(((rng.uniform(10, 50), 3, 4), (x - 80 + led * 60 + rng.uniform(0, 20), cloud[1] - 121.5, z)))
    batch_boxes = bd.batch_boxes
    batch_boxes("lc_leds_cyan", leds["cyan"], bd.emission("lc_led_cyan", CYAN, 25))
    batch_boxes("lc_leds_white", leds["white"], bd.emission("lc_led_white", ICE, 15))
    # Data arc between them, with pulses
    a = (local[0], local[1], 90)
    b = (cloud[0], cloud[1] - 60, 600)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 80, 760)
    points = bezier(a, mid, b, 60)
    tube("lc_arc", points, 3.0, bd.emission("lc_arc_mat", (0.05, 0.5, 1.0), 4))
    pulse = bd.emission("lc_pulse", (0.9, 0.96, 1.0), 10)
    for j, t in enumerate((0.2, 0.42, 0.64, 0.86)):
        sphere(f"lc_pulse_{j}", 9, points[int(t * (len(points) - 1))], pulse, segments=24)
    anchor("local", (local[0], local[1] - 150, 0))
    anchor("cloud", (cloud[0], cloud[1] - 160, 0))
    bd.volume_fog(0.006)
    bd.bokeh_field(60, (-2600, 2600), (2200, 4400), (-200, 2000), seed=12, size=(12, 36))
    pp.area_light("key", (-0.7, -1.2, 1.3), (50, 0, -30), 1.4, 70)
    pp.area_light("top", (0.0, 0.3, 1.8), (0, 0, 0), 1.6, 25)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((0.35, -2.3, 1.15), (0.0, 0.05, 0.3), lens=40, fstop=8, focus=(0, -0.1, 0.2))
    else:
        pp.camera((0.0, -2.0, 0.85), (0.0, 0.05, 0.28), lens=38, fstop=8, focus=(0, 0, 0.2))


# --- 9. token conveyor ---------------------------------------------------------------------------

def tokens(fmt, mats):
    portrait = fmt == "9x16"
    rng = random.Random(6)
    pp.floor_backdrop(pp.mat_floor(radius_m=1.2, color=(0.0015, 0.002, 0.005)), size=12, wall=False)
    # Chip in the middle
    pp.box("tk_substrate", (170, 170, 8), (0, 0, 4), pp.mat_basic("tk_sub", (0.01, 0.015, 0.03), roughness=0.3, coat=0.8), bevel_mm=6)
    die = bd.emission("tk_die", (0.0, 0.5, 1.0), 8)
    hot = bd.emission("tk_hot", (1.0, 0.25, 0.1), 10)
    for gx in range(5):
        for gy in range(5):
            pp.box(f"tk_core_{gx}_{gy}", (17, 17, 1.2), (-44 + gx * 22, -44 + gy * 22, 8.6), hot if (gx, gy) == (2, 2) else die, bevel_mm=0.6)
    pp.box("tk_cap", (120, 120, 22), (0, 0, 20), bd.glass("tk_cap_glass"), bevel_mm=6, segments=8)
    rail = bd.emission("tk_rail", (0.1, 0.55, 1.0), 4)
    shell = bd.glass("tk_glass", (0.9, 0.97, 1.0), 0.1)
    cin = bd.emission("tk_in", CYAN, 2.2)
    cout = bd.emission("tk_out", CORAL, 2.2)

    def lane(axis_sign, start, direction, count, core, prefix):
        pos = start
        for k in range(count):
            length = rng.choice([34, 46, 58, 70, 40, 52])
            centre = pos + direction * length / 2
            loc = (centre, 0, 22) if axis_sign == "x" else (0, centre, 22)
            size = (length, 44, 34) if axis_sign == "x" else (44, length, 34)
            pp.box(f"{prefix}_{k}", size, loc, shell, bevel_mm=4, segments=4)
            inner = (length * 0.7, 26, 20) if axis_sign == "x" else (26, length * 0.7, 20)
            pp.box(f"{prefix}_core_{k}", inner, loc, core, bevel_mm=3)
            pos += direction * (length + 16)

    axis = "y" if portrait else "x"
    for side in (-1, 1):
        if axis == "x":
            pp.box(f"tk_rail_{side}", (1900, 2, 2), (0, side * 34, 1), rail)
        else:
            pp.box(f"tk_rail_{side}", (2, 1900, 2), (side * 34, 0, 1), rail)
    if axis == "x":
        lane("x", -110, -1, 9, cin, "tk_in")
        lane("x", 110, 1, 6, cout, "tk_out")
    else:
        lane("y", 110, 1, 9, cin, "tk_in")
        lane("y", -110, -1, 6, cout, "tk_out")
    bd.volume_fog(0.006)
    bd.bokeh_field(50, (-2400, 2400), (1800, 3800), (0, 1600), seed=61, size=(10, 30))
    pp.area_light("key", (-0.5, -0.8, 1.0), (45, 0, -30), 1.0, 30)
    pp.area_light("top", (0.0, 0.2, 1.4), (0, 0, 0), 1.2, 15)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((0.42, -1.05, 0.62), (0.0, 0.05, 0.0), lens=34, fstop=5.6, focus=(0, 0, 0.02))
    else:
        pp.camera((0.0, -1.05, 0.48), (0.0, 0.0, 0.02), lens=30, fstop=5.6, focus=(0, 0, 0.02))


# --- 10. retro meets AI ---------------------------------------------------------------------------

def retro(fmt, mats):
    from pp_textures import retro_screen_texture

    portrait = fmt == "9x16"
    floor = pp.mat_basic("retro_floor", (0.006, 0.008, 0.014), roughness=0.25, coat=0.5)
    pp.floor_backdrop(floor, size=12, wall=False)
    wood = pp.mat_basic("retro_desk", (0.06, 0.035, 0.02), roughness=0.45, coat=0.35)
    pp.box("retro_desk", (1100, 560, 30), (0, 60, 15), wood, bevel_mm=5)
    shellmat = pp.mat_basic("crt_shell", (0.04, 0.042, 0.048), roughness=0.45, coat=0.2)
    base = 30
    pp.box("crt_body", (520, 380, 400), (0, 150, base + 200), shellmat, bevel_mm=34, segments=8)
    pp.box("crt_back", (400, 220, 300), (0, 360, base + 190), shellmat, bevel_mm=60, segments=8)
    pp.box("crt_bezel", (400, 10, 310), (-50, -42, base + 215), pp.mat_basic("crt_bezel", (0.015, 0.016, 0.02), roughness=0.35), bevel_mm=12)
    screen = pp.mat_image("crt_screen_img", retro_screen_texture(), roughness=0.3)
    nodes = screen.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    tex = next(n for n in nodes if n.type == "TEX_IMAGE")
    tex.interpolation = "Closest"
    screen.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    pp._set(bsdf, "Emission Strength", 3.2)
    pp.plane("crt_screen", (348, 261), (-50, -48, base + 215), screen, rotation_deg=(90, 0, 0))
    glass_cover = bd.glass("crt_glass", (0.85, 0.92, 1.0), 0.05)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32, location=(-50 * MM, -40 * MM, (base + 215) * MM))
    bulge = bpy.context.active_object
    bulge.scale = (190 * MM, 14 * MM, 145 * MM)
    bpy.ops.object.shade_smooth()
    bulge.data.materials.append(glass_cover)
    for k, z in enumerate((300, 230)):
        pp.cylinder(f"crt_knob_{k}", 18, 14, (200, -46, base + z), mats.steel, rotation_deg=(90, 0, 0), bevel_mm=2)
    for k in range(8):
        pp.box(f"crt_grille_{k}", (60, 3, 4), (200, -42, base + 80 + k * 12), mats.plastic_black)
    pp.box("crt_power_led", (8, 3, 4), (200, -43, base + 170), bd.emission("crt_led", CORAL, 12))
    # Retro console + controller with cable
    grey = pp.mat_basic("console_grey", (0.32, 0.33, 0.35), roughness=0.5)
    cx, cy = (330, -170) if not portrait else (170, -230)
    pp.box("console", (250, 180, 62), (cx, cy, base + 31), grey, bevel_mm=8)
    pp.box("console_slot", (130, 26, 6), (cx, cy + 20, base + 62), mats.plastic_black)
    pp.box("cartridge", (112, 18, 70), (cx, cy + 20, base + 90), pp.mat_basic("cartridge", (0.05, 0.25, 0.5), roughness=0.4), bevel_mm=3)
    pp.box("cart_label", (90, 1, 46), (cx, cy + 10.6, base + 96), bd.emission("cart_label", CYAN, 1.5))
    for k in range(2):
        pp.box(f"console_btn_{k}", (24, 14, 8), (cx - 80 + k * 34, cy - 70, base + 64), mats.plastic_black, bevel_mm=2)
    px, py = (-300, -200) if not portrait else (-150, -250)
    pp.box("pad", (130, 58, 18), (px, py, base + 9), grey, bevel_mm=8, rotation_deg=(0, 0, 12))
    for k, (dx, dy) in enumerate(((-38, 0), (36, 6), (48, -6))):
        if k == 0:
            pp.box("pad_dpad_a", (24, 8, 4), (px + dx, py + dy, base + 19), mats.plastic_black)
            pp.box("pad_dpad_b", (8, 24, 4), (px + dx, py + dy, base + 19), mats.plastic_black)
        else:
            pp.cylinder(f"pad_btn_{k}", 6, 4, (px + dx, py + dy, base + 19), bd.emission(f"pad_btn_{k}", CORAL if k == 1 else CYAN, 1.2))
    cable = pp.mat_basic("pad_cable", (0.01, 0.01, 0.012), roughness=0.5)
    tube("pad_cable", bezier((px + 40, py + 30, base + 9), ((px + cx) / 2, py + 160, base + 2), (cx - 125, cy, base + 20), 40), 2.5, cable)
    pp.area_light("key", (-0.8, -1.1, 1.0), (55, 0, -35), 1.2, 60, color=(1.0, 0.9, 0.8))
    pp.area_light("rim", (0.8, 0.9, 0.7), (-65, 0, 140), 1.0, 45, color=(0.4, 0.75, 1.0))
    reflector("retro_softbox", (0.0, -1.0, 0.9), (55, 0, 0), (1.6, 0.6), 2.0)
    bd.volume_fog(0.005)
    bd.bokeh_field(50, (-2600, 2600), (2200, 4400), (0, 2000), seed=77, size=(12, 34))
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if portrait:
        pp.camera((-0.25, -1.75, 0.75), (0.02, 0.0, 0.25), lens=40, fstop=5.6, focus=(0, -0.05, 0.25))
    else:
        pp.camera((-0.35, -1.6, 0.6), (0.0, 0.0, 0.22), lens=40, fstop=5.6, focus=(0, -0.05, 0.25))


SCENES = {"gpu": gpu, "vram": vram, "books": books, "agents": agents, "podium": podium, "locks": locks,
          "quant": quant, "localcloud": localcloud, "tokens": tokens, "retro": retro}


def export_anchors(scene, path):
    bpy.context.view_layer.update()  # camera matrix_world is stale until the depsgraph is evaluated
    cam = scene.camera
    w, h = scene.render.resolution_x, scene.render.resolution_y
    out = {}
    for name, point in ANCHORS.items():
        co = world_to_camera_view(scene, cam, Vector(point))
        out[name] = [round(co.x * w, 1), round((1 - co.y) * h, 1)]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"size": [w, h], "anchors": out}, handle, indent=1)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", choices=list(SCENES), required=True)
    parser.add_argument("--format", default="16x9", choices=["16x9", "9x16"])
    parser.add_argument("--samples", type=int, default=192)
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--anchors-only", action="store_true", help="rebuild the scene and rewrite anchors.json without rendering")
    args = parser.parse_args(argv)
    scene = pp.reset_scene()
    width, height = (1920, 1080) if args.format == "16x9" else (1080, 1920)
    if args.preview:
        width, height = width // 2, height // 2
    pp.setup_cycles(scene, args.samples, width, height)
    scene.cycles.volume_bounces = 1
    mats = pp.Materials()
    SCENES[args.scene](args.format, mats)
    for obj in scene.objects:
        if obj.type == "LIGHT":
            obj.visible_camera = False
            if obj.data.type == "AREA":
                obj.visible_glossy = False
    os.makedirs(args.out, exist_ok=True)
    export_anchors(scene, os.path.join(args.out, "anchors.json"))
    if args.anchors_only:
        return
    pp.render_beauty(scene, os.path.join(args.out, "clean.png"))
    if args.scene == "gpu":
        for obj in scene.objects:
            if obj.name == "fog":
                obj.hide_render = True
        pp.render_masks(scene, args.out, groups=("gpu", "vram"))


if __name__ == "__main__":
    main()
