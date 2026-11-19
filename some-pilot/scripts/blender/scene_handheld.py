"""Open gaming handheld (back cover removed): APU (cpu), 4 LPDDR5X packages (ram), M.2 2230 SSD (ssd),
blower fan + heat pipe + fin stack, battery, stick and trigger modules. Generic design, no brand.

blender -b -P scene_handheld.py -- --format 16x9 --samples 192 --out <dir> --masks
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import pp_lib as pp  # noqa: E402
from pp_textures import chip_marking_texture, label_texture, pcb_texture  # noqa: E402

MM = pp.MM


def tube(name, points_mm, radius_mm, material):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius_mm * MM
    curve.bevel_resolution = 4
    curve.use_fill_caps = True
    spline = curve.splines.new("POLY")
    spline.points.add(len(points_mm) - 1)
    for point, (x, y, z) in zip(spline.points, points_mm):
        point.co = (x * MM, y * MM, z * MM, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def build(mats):
    rng = random.Random(17)
    body = pp.mat_basic("hh_body", (0.012, 0.013, 0.016), roughness=0.5)
    pp.hollow_shell("shell", (272, 112, 24), 2.4, 2.4, (0, 0, 0), body, radius_mm=18)
    pp.box("midframe", (262, 104, 1.0), (0, 0, 3.0), mats.alu_dark)
    # Battery with label
    pp.box("battery", (128, 44, 6.5), (0, -27, 6.8), mats.battery, bevel_mm=1.2)
    pp.plane("battery_label", (96, 30), (0, -27, 10.1), pp.mat_image("hh_batt_label", label_texture("battery_label", ["Li-ion Battery", "15.48V · 4840mAh · 75Wh", "Do not puncture · Recycle properly"], size_px=(1600, 420), bg=(14, 14, 16), fg=(200, 202, 206)), roughness=0.5))
    # Mainboard
    board = pp.mat_image("hh_board", pcb_texture("laptop_board", base=(10, 14, 22), trace=(22, 30, 44), seed=21, dark=True), roughness=0.36, coat=0.5, bump_strength=0.04)
    pp.box("board", (150, 48, 1.0), (4, 26, 6.5), board)
    top = 7.0
    sub = pp.mat_basic("hh_substrate", (0.03, 0.06, 0.045), roughness=0.45, coat=0.4)
    apu_x, apu_y = -4, 27
    pp.box("apu_substrate", (25, 33, 1.2), (apu_x, apu_y, top + 0.6), sub, bevel_mm=0.4, group="cpu")
    die = pp.mat_image("hh_die", chip_marking_texture("cpu_die", "AI 9 HX\n100-000001\n2546 SUS"), roughness=0.18, coat=0.9)
    pp.box("apu_die", (15, 21, 0.6), (apu_x, apu_y, top + 1.5), die, bevel_mm=0.15, group="cpu")
    ram = pp.mat_image("hh_ram", chip_marking_texture("ram_chip", "D8BPK\nM16G 4C3A\n2547"), roughness=0.6)
    for k, (dx, dy) in enumerate(((-29, -9), (-29, 9), (23, -9), (23, 9))):
        pp.box(f"lpddr_{k}", (12, 15, 1.0), (apu_x + dx, apu_y + dy, top + 0.5), ram, bevel_mm=0.2, group="ram")
    # M.2 2230 NVMe: short board, single controller+NAND package, gold key-M fingers (helper m2_ssd is 2280-only)
    sx, sy = 52, 27
    ssd_pcb = pp.mat_image("hh_ssd_pcb", pcb_texture("ssd_pcb", base=(12, 12, 14), trace=(26, 26, 30), seed=3, dark=True), roughness=0.35, coat=0.6)
    pp.box("ssd_pcb", (30, 22, 0.8), (sx, sy, top + 0.4), ssd_pcb, group="ssd")
    pp.box("ssd_fingers", (3.5, 19, 0.85), (sx - 13.25, sy, top + 0.4), pp.mat_basic("hh_gold", (1.0, 0.74, 0.34), metallic=1.0, roughness=0.22), group="ssd")
    pp.box("ssd_package", (17, 16, 1.2), (sx + 2, sy, top + 1.4), pp.mat_image("hh_nand", chip_marking_texture("ram_chip", "D8BPK\nM16G 4C3A\n2547"), roughness=0.6), bevel_mm=0.3, group="ssd")
    pp.screw("ssd_screw", (sx + 15, sy, top + 0.8), mats, radius_mm=1.8, head_mm=1.0)
    pp.smd_scatter("hh_smd", (-70, 4, 78, 49), top, 170, mats, rng,
                   avoid=[(apu_x - 38, apu_y - 20, apu_x + 32, apu_y + 20), (34, 14, 70, 40)])
    # Cooling: blower, copper heat pipe to a fin stack at the top edge
    pp.blower_fan("fan", (-58, 22), 6.5, mats, radius_mm=19, blades=13, height_mm=6, housing=True)
    pp.heatsink_fins("fins", (-58, 49.5), 6.5, (42, 6, 7), 28, mats, material=mats.copper, axis="y")
    tube("heatpipe", [(apu_x, apu_y, top + 2.6), (-22, 38, top + 3.2), (-40, 47, top + 3.2), (-80, 47, top + 3.2)], 2.4, mats.copper)
    pp.box("coldplate", (20, 26, 1.6), (apu_x, apu_y, top + 2.4), mats.copper, bevel_mm=0.4)
    # Controls and peripherals
    for side in (-1, 1):
        pp.box(f"stick_mod_{side}", (28, 28, 9), (side * 106, 8, 7.5), mats.plastic_black, bevel_mm=1.2)
        pp.cylinder(f"stick_pcb_{side}", 10, 1.2, (side * 106, 8, 12.6), mats.chip)
        pp.box(f"trigger_{side}", (32, 14, 11), (side * 110, 48, 8.5), mats.plastic_grey, bevel_mm=2)
        pp.box(f"speaker_{side}", (24, 14, 5), (side * 80, -46, 5.5), mats.plastic_black, bevel_mm=1)
        pp.box(f"abxy_pcb_{side}", (34, 34, 1.0), (side * 100, -18, 4.0), board)
    flex = pp.mat_basic("flex", (0.55, 0.32, 0.05), roughness=0.35, coat=0.4)
    pp.box("flex_left", (36, 5, 0.3), (-86, 10, 7.2), flex)
    pp.box("flex_right", (24, 5, 0.3), (88, 14, 7.2), flex)
    pp.box("flex_batt", (6, 18, 0.3), (40, -2, 10.2), flex)
    for x, y in ((-122, 44), (122, 44), (-60, -50), (60, -50), (0, 50)):
        pp.screw(f"screw_{x}_{y}", (x, y, 3.2), mats)


def stage(fmt, mats):
    pp.floor_backdrop(mats.floor, size=6.0, wall=False)
    if fmt == "16x9":
        pp.camera((0.0, -0.34, 0.40), (0.0, 0.004, 0.0), lens=52, fstop=7.1, focus=(0.0, 0.0, 0.006))
    else:
        pp.camera((0.0, -0.10, 0.62), (0.0, 0.006, 0.0), lens=48, fstop=7.1, focus=(0.0, 0.0, 0.006), roll_deg=90)
    pp.area_light("key", (-0.30, -0.28, 0.50), (40, 0, -45), 0.8, 18, color=(1.0, 0.98, 0.95), size_y=0.5)
    pp.area_light("top", (0.04, 0.02, 0.55), (0, 0, 0), 0.35, 10, color=(0.95, 0.97, 1.0))
    pp.area_light("rim_cyan", (0.30, 0.20, 0.10), (78, 0, 128), 0.30, 18, color=(0.45, 0.82, 1.0))
    pp.area_light("rim_coral", (-0.42, 0.32, 0.10), (78, 0, -128), 0.35, 10, color=(1.0, 0.5, 0.38))
    pp.world((0.004, 0.006, 0.014), 1.0)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", default="16x9", choices=["16x9", "9x16"])
    parser.add_argument("--samples", type=int, default=192)
    parser.add_argument("--out", required=True)
    parser.add_argument("--masks", action="store_true")
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    scene = pp.reset_scene()
    width, height = (1920, 1080) if args.format == "16x9" else (1080, 1920)
    if args.preview:
        width, height = width // 2, height // 2
    pp.setup_cycles(scene, args.samples, width, height)
    mats = pp.Materials()
    build(mats)
    stage(args.format, mats)
    os.makedirs(args.out, exist_ok=True)
    pp.render_beauty(scene, os.path.join(args.out, "clean.png"))
    if args.masks:
        pp.render_masks(scene, args.out)


if __name__ == "__main__":
    main()
