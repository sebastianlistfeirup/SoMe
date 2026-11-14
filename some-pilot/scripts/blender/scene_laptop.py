"""Open laptop: lying upside down, bottom cover removed and set beside it.
RAM, SSD and CPU (cold plate over the CPU die) are tagged for masks.

blender -b -P scene_laptop.py -- --format 16x9 --samples 256 --out <dir> [--masks] [--preview]
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import pp_lib as pp  # noqa: E402


def flex_cable(name, points, z, width, mats, color=(0.55, 0.32, 0.08)):
    material = pp.mat_basic(name + "_mat", color, roughness=0.35, coat=0.4)
    for index, ((x0, y0), (x1, y1)) in enumerate(zip(points, points[1:])):
        length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        import math

        angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
        pp.box(f"{name}_{index}", (length + width * 0.2, width, 0.18), ((x0 + x1) / 2, (y0 + y1) / 2, z), material, rotation_deg=(0, 0, angle))


def build(mats, fmt):
    rng = random.Random(7)
    # Base shell (upside down): dark anodised aluminium tub, 356 x 250 mm.
    pp.hollow_shell("chassis", (356, 250, 18), 2.0, 1.6, (0, 0, 0), mats.alu_dark, radius_mm=9)
    floor_z = 1.6
    # Battery pack across the front (four cells under a black wrap with a label).
    batt_label = pp.mat_image("battery_label", pp.label_texture("battery_label", ["Li-ion Battery", "15.48V · 4840mAh · 75Wh", "Do not puncture · Recycle properly"], size_px=(1600, 420), bg=(14, 14, 16), fg=(200, 202, 206)), roughness=0.35)
    pp.box("battery", (300, 82, 7.5), (0, -72, floor_z + 3.75), mats.battery, bevel_mm=2.0, segments=4)
    for k in range(3):
        pp.box(f"battery_seam_{k}", (0.8, 80, 0.4), (-75 + k * 75, -72, floor_z + 7.6), mats.chip)
    pp.plane("battery_sticker", (120, 32), (-60, -72, floor_z + 7.56), batt_label)
    for x in (-152, 152):
        pp.screw(f"batt_screw_{x}", (x, -40, floor_z + 2), mats, radius_mm=1.8, head_mm=0.8)
    flex_cable("battery_flex", [(0, -30), (0, -18), (20, -10)], floor_z + 8.0, 9, mats, color=(0.04, 0.04, 0.05))

    # Mainboard across the rear half.
    board_z = floor_z + 3.0
    board_mat = pp.mat_image("laptop_board", pp.pcb_texture("laptop_board", base=(10, 14, 22), trace=(22, 30, 44), seed=21, dark=True), roughness=0.34, coat=0.6, bump_strength=0.05)
    pp.box("board", (300, 120, 1.0), (0, 52, board_z), board_mat, bevel_mm=0.6, segments=2)
    top = board_z + 0.5

    # CPU and GPU packages (dies) under copper cold plates.
    cpu_x, cpu_y, gpu_x, gpu_y = -22, 62, 42, 62
    substrate = pp.mat_basic("substrate", (0.05, 0.14, 0.10), roughness=0.45, coat=0.5)
    pp.box("cpu_substrate", (35, 25, 1.2), (cpu_x, cpu_y, top + 0.6), substrate, bevel_mm=0.3, group="cpu")
    pp.box("gpu_substrate", (40, 40, 1.4), (gpu_x, gpu_y, top + 0.7), substrate, bevel_mm=0.3)
    pp.box("cpu_coldplate", (30, 24, 2.4), (cpu_x, cpu_y, top + 2.4), mats.copper, bevel_mm=0.5, group="cpu")
    pp.box("gpu_coldplate", (34, 34, 2.4), (gpu_x, gpu_y, top + 2.5), mats.copper, bevel_mm=0.5)
    pp.box("cooling_bracket", (120, 10, 1.0), (10, cpu_y, top + 4.2), mats.steel, bevel_mm=0.4)
    for dx in (-17, 17):
        for dy in (-15, 15):
            pp.screw(f"cpu_mount_{dx}_{dy}", (cpu_x + dx, cpu_y + dy, top + 3.2), mats, radius_mm=2.0, head_mm=1.0)
            pp.screw(f"gpu_mount_{dx}_{dy}", (gpu_x + dx * 1.2, gpu_y + dy * 1.2, top + 3.2), mats, radius_mm=2.0, head_mm=1.0)

    # Two blower fans at the rear corners with fin stacks at the exhaust.
    for name, x in (("fan_left", -112), ("fan_right", 112)):
        pp.blower_fan(name, (x, 58), floor_z + 0.5, mats, radius_mm=30, blades=37, height_mm=9)
        pp.heatsink_fins(f"{name}_fins", (x + (12 if x > 0 else -12), 108), floor_z + 1.0, (52, 10, 10), 34, mats, material=mats.copper, axis="y")
    # Heat pipes: CPU/GPU cold plates to both fin stacks.
    pp.heatpipe("pipe1", [(cpu_x, cpu_y - 6), (-60, cpu_y - 6), (-85, 104), (-138, 104)], 2.8, top + 4.8, mats)
    pp.heatpipe("pipe2", [(cpu_x, cpu_y + 6), (-55, 100), (-138, 110)], 2.8, top + 4.8, mats)
    pp.heatpipe("pipe3", [(gpu_x, gpu_y - 6), (80, gpu_y - 6), (100, 104), (138, 104)], 2.8, top + 4.8, mats)
    pp.heatpipe("pipe4", [(gpu_x, gpu_y + 6), (85, 100), (138, 110)], 2.8, top + 4.8, mats)
    pp.heatpipe("pipe5", [(cpu_x + 10, cpu_y), (gpu_x - 10, gpu_y)], 2.8, top + 4.8, mats)

    # RAM: two SO-DIMMs side by side under the cooling, centre-left. Tagged ram.
    for k, y in enumerate((-6, 26)):
        pp.box(f"ram_slot_{k}", (75, 4.5, 3.6), (-92, y - 15.5, top + 1.8), mats.plastic_black, bevel_mm=0.4)
        pp.memory_module(f"ram{k}", (-92, y), top + 2.4 + k * 0.01, mats)

    # SSD: M.2 2280 centre-right, horizontal. Tagged ssd.
    pp.box("m2_socket", (4.2, 22.5, 3.0), (52, 12, top + 1.5), mats.plastic_black, bevel_mm=0.3)
    pp.m2_ssd("ssd", (92, 12), top + 1.2, mats, angle_deg=0)
    pp.screw("ssd_screw", (133, 12, top + 1.0), mats, radius_mm=1.8, head_mm=0.9)
    pp.box("ssd_slot2", (4.2, 22.5, 3.0), (52, -14, top + 1.5), mats.plastic_black, bevel_mm=0.3)

    # WiFi, speakers, ribbon cables, rubber feet.
    pp.box("wifi_card", (22, 30, 1.6), (20, 12, top + 0.8), pp.mat_basic("wifi_shield", (0.70, 0.71, 0.73), metallic=1.0, roughness=0.3), bevel_mm=0.3)
    for x in (-160, 160):
        pp.box(f"speaker_{x}", (22, 50, 9), (x, -20, floor_z + 4.5), mats.plastic_black, bevel_mm=1.5)
        for k in range(8):
            pp.box(f"speaker_grille_{x}_{k}", (18, 1.0, 0.4), (x, -40 + k * 5.5, floor_z + 9.1), mats.steel)
    flex_cable("display_flex", [(-60, 118), (-60, 100), (-40, 92)], top + 1.0, 12, mats)
    flex_cable("keyboard_flex", [(10, -30), (10, -6), (30, 0)], top + 1.0, 14, mats)
    for k in range(3):
        pp.box(f"connector_{k}", (12, 4, 2.4), (-30 + k * 30, -2, top + 1.2), mats.plastic_black, bevel_mm=0.3)
    avoid = [(cpu_x - 22, cpu_y - 16, gpu_x + 26, gpu_y + 24), (-132, -24, -52, 44), (48, -26, 136, 26), (-150, 25, -75, 120), (75, 25, 150, 120)]
    pp.smd_scatter("laptop_smd", (-148, -6, 148, 110), top, 520, mats, rng, avoid=avoid)



def stage(fmt, mats):
    pp.floor_backdrop(mats.floor, size=8.0, wall=False)
    if fmt == "16x9":
        cam = pp.camera((0.10, -0.46, 0.66), (0.075, 0.015, 0.0), lens=44, fstop=8, focus=(0.0, 0.02, 0.01))
    else:
        cam = pp.camera((0.0, -0.36, 0.70), (0.0, 0.02, 0.0), lens=42, fstop=8, focus=(0.0, 0.02, 0.01), roll_deg=90)
    pp.area_light("key", (-0.45, -0.40, 0.75), (40, 0, -45), 1.0, 42, color=(1.0, 0.98, 0.95), size_y=0.7)
    pp.area_light("top", (0.0, 0.05, 0.85), (0, 0, 0), 0.6, 14)
    pp.area_light("rim_cyan", (0.55, 0.45, 0.18), (75, 0, 130), 0.45, 22, color=(0.45, 0.82, 1.0))
    pp.area_light("rim_coral", (-0.55, 0.42, 0.14), (78, 0, -128), 0.35, 10, color=(1.0, 0.5, 0.38))
    pp.world((0.002, 0.003, 0.008), 1.0)
    return cam


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", default="16x9", choices=["16x9", "9x16"])
    parser.add_argument("--samples", type=int, default=256)
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
    build(mats, args.format)
    stage(args.format, mats)
    os.makedirs(args.out, exist_ok=True)
    pp.render_beauty(scene, os.path.join(args.out, "clean.png"))
    if args.masks:
        pp.render_masks(scene, args.out)


if __name__ == "__main__":
    main()
