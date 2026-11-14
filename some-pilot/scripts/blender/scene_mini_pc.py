"""Open mini PC (lid off, cooler set aside): RAM, SSD and CPU are tagged for masks.

blender -b -P scene_mini_pc.py -- --format 16x9 --samples 256 --out <dir> [--masks] [--preview]
"""

import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import pp_lib as pp  # noqa: E402


def _darken(material, factor):
    """Multiply an image base colour (keeps the texture, deepens the solder-mask green)."""
    nodes, links = material.node_tree.nodes, material.node_tree.links
    tex = next(node for node in nodes if node.type == "TEX_IMAGE")
    bsdf = nodes.get("Principled BSDF")
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs["B"].default_value = (factor, factor * 1.02, factor * 1.05, 1)
    links.new(tex.outputs["Color"], mix.inputs["A"])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])


def build(mats, fmt="16x9"):
    rng = random.Random(42)
    # Aluminium unibody shell, open top.
    shell = pp.hollow_shell("shell", (128, 128, 38), 2.6, 2.4, (0, 0, 0), mats.alu, radius_mm=10)
    pp.box("shell_foot", (118, 118, 1.2), (0, 0, 0.3), mats.rubber, bevel_mm=6, segments=6)
    # Front ports cut-outs as inset dark blocks on the front wall (y = -64).
    for x, w, h, material in ((-36, 13.2, 5.6, mats.port_blue), (-18, 13.2, 5.6, mats.port_blue), (0, 8.6, 3.0, mats.plastic_black), (14, 3.4, 3.4, mats.plastic_black)):
        pp.box(f"port_{x}", (w, 1.2, h), (x, -64.05, 16), mats.plastic_black, bevel_mm=0.4)
        if material is mats.port_blue:
            pp.box(f"port_tongue_{x}", (w * 0.7, 1.3, h * 0.35), (x, -64.1, 16 - h * 0.12), material)
    pp.cylinder("power_button", 3.6, 1.0, (-52, -64.2, 16), mats.alu, rotation_deg=(90, 0, 0), bevel_mm=0.3)
    pp.cylinder("power_led", 0.6, 1.0, (-46, -64.2, 16), pp.mat_basic("led", (0.2, 0.8, 1.0), emission=(0.3, 0.85, 1.0), emission_strength=8))
    # Side vent perforation (right wall).
    vent = pp.mat_basic("vent_hole", (0.004, 0.004, 0.005), roughness=0.9)
    for row in range(5):
        for col in range(26):
            pp.cylinder(f"vent_{row}_{col}", 0.9, 0.6, (64.2, -48 + col * 3.8 + (row % 2) * 1.9, 9 + row * 3.6), vent, vertices=12, rotation_deg=(0, 90, 0))

    # Mainboard.
    board_z = 6.0
    board_mat = pp.mat_image("mini_board", pp.pcb_texture("mini_board", base=(20, 74, 60), trace=(34, 104, 84), seed=11), roughness=0.36, coat=0.55, bump_strength=0.06)
    _darken(board_mat, 0.55)
    pp.box("board", (118, 118, 1.6), (0, 0, board_z), board_mat, bevel_mm=1.0, segments=2)
    top = board_z + 0.8
    for x, y in ((-54, -54), (54, -54), (-54, 54), (54, 54)):
        pp.cylinder(f"standoff_{x}_{y}", 2.6, board_z - 2.4, (x, y, 2.4 + (board_z - 2.4) / 2), mats.solder)
        pp.screw(f"screw_{x}_{y}", (x, y, top), mats)

    # CPU: BGA substrate with two dies (compute + iGPU), surrounded by caps. Tagged cpu.
    cpu_x, cpu_y = 6, -24
    pp.box("cpu_substrate", (31, 27, 1.1), (cpu_x, cpu_y, top + 0.55), pp.mat_basic("substrate", (0.06, 0.16, 0.11), roughness=0.45, coat=0.5), bevel_mm=0.3, group="cpu")
    die_mat = pp.mat_basic("silicon", (0.03, 0.035, 0.05), metallic=0.6, roughness=0.08)
    pp.box("cpu_die_compute", (12.5, 10, 0.7), (cpu_x - 5.5, cpu_y + 1.5, top + 1.45), die_mat, group="cpu")
    pp.box("cpu_die_io", (9, 7, 0.7), (cpu_x + 7.5, cpu_y + 1.5, top + 1.45), die_mat, group="cpu")
    for k in range(18):
        pp.box(f"cpu_cap_{k}", (1.0, 0.5, 0.45), (cpu_x - 13 + (k % 9) * 3.2, cpu_y - 10.5 + (k // 9) * 21, top + 1.3), mats.ceramic, group="cpu")
    # VRM: inductors + mosfets left of CPU.
    for k in range(6):
        pp.box(f"choke_{k}", (5.2, 5.2, 3.2), (cpu_x - 26, cpu_y - 13 + k * 5.6, top + 1.6), mats.inductor, bevel_mm=0.5)
        pp.box(f"mosfet_{k}", (4.0, 3.2, 0.9), (cpu_x - 19.5, cpu_y - 13 + k * 5.6, top + 0.45), mats.chip, bevel_mm=0.15)
    for k in range(4):
        pp.cylinder(f"polycap_{k}", 2.4, 4.2, (cpu_x - 33, cpu_y - 10 + k * 6, top + 2.1), mats.cap_alu, bevel_mm=0.3)
    # Cooler mounting holes / springs around CPU.
    for dx, dy in ((-19, -16), (19, -16), (-19, 16), (19, 16)):
        pp.cylinder(f"mount_{dx}_{dy}", 2.0, 3.6, (cpu_x + dx, cpu_y + dy, top + 1.8), mats.steel, bevel_mm=0.3)

    # RAM: two SO-DIMMs in a dual latch, top right. Tagged ram.
    for k, y in enumerate((40, 9)):
        pp.box(f"ram_slot_{k}", (75, 4.5, 4.2), (24, y - 15.5, top + 2.1), mats.plastic_black, bevel_mm=0.4)
        for side in (-1, 1):
            pp.box(f"ram_latch_{k}_{side}", (2.2, 8, 3.4), (24 + side * 38.5, y - 8, top + 1.7), mats.steel, bevel_mm=0.3)
        pp.memory_module(f"ram{k}", (24, y), top + 3.1 + k * 0.01, mats)

    # SSD: M.2 2280 on the left, vertical. Tagged ssd.
    pp.box("m2_socket", (22.5, 4.2, 3.0), (-36, -26, top + 1.5), mats.plastic_black, bevel_mm=0.3)
    pp.m2_ssd("ssd", (-36, 15), top + 1.2, mats, angle_deg=90)
    pp.cylinder("ssd_standoff", 2.4, 1.6, (-36, 55.5, top + 0.8), mats.solder)
    pp.screw("ssd_screw", (-36, 55.5, top + 1.6), mats, radius_mm=1.9, head_mm=0.9)

    # WiFi card (M.2 2230) with antenna leads.
    wifi = pp.mat_basic("wifi_shield", (0.72, 0.73, 0.75), metallic=1.0, roughness=0.3)
    pp.box("wifi_pcb", (22, 30, 0.8), (-12, 42, top + 0.4), pp.mat_basic("wifi_pcb", (0.05, 0.05, 0.06), roughness=0.4), group=None)
    pp.box("wifi_shield", (18, 20, 1.4), (-12, 44, top + 1.5), wifi, bevel_mm=0.3)
    for k, color in enumerate(((0.02, 0.02, 0.02), (0.6, 0.6, 0.62))):
        cable = pp.mat_basic(f"antenna_{k}", color, roughness=0.45)
        pts = [(-15 + k * 6, 54), (-15 + k * 6, 60), (-40 + k * 3, 61), (-58, 58 - k * 4)]
        curve = bpy.data.curves.new(f"antenna{k}", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = 0.55 * pp.MM
        curve.bevel_resolution = 3
        spline = curve.splines.new("BEZIER")
        spline.bezier_points.add(len(pts) - 1)
        for point, (x, y) in zip(spline.bezier_points, pts):
            point.co = (x * pp.MM, y * pp.MM, (top + 2.6) * pp.MM)
            point.handle_left_type = point.handle_right_type = "AUTO"
        obj = bpy.data.objects.new(f"antenna{k}", curve)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(cable)
        pp.cylinder(f"antenna_plug_{k}", 1.2, 1.0, (-15 + k * 6, 54, top + 1.9), mats.solder)

    # CMOS coin cell, headers, rear I/O shields.
    pp.cylinder("cmos", 10, 3.2, (36, -48, top + 1.6), mats.steel, bevel_mm=0.6)
    for k in range(3):
        pp.box(f"header_{k}", (10, 2.6, 6), (-20 + k * 14, -54, top + 3), mats.plastic_black, bevel_mm=0.2)
    for k, (x, w) in enumerate(((-30, 15.0), (-10, 15.0), (10, 9.0), (28, 16.0), (46, 8.0))):
        pp.box(f"rear_io_{k}", (w, 12, 7.5), (x, 56, top + 3.75), mats.alu_dark, bevel_mm=0.4)
    for k in range(4):
        pp.box(f"usb_front_{k}", (14, 13, 6.2), (-36 + k * 18 if k < 2 else 0 + (k - 2) * 14, -55, top + 3.1), mats.steel, bevel_mm=0.4) if k < 2 else None

    avoid = [(cpu_x - 20, cpu_y - 18, cpu_x + 20, cpu_y + 18), (-14, -8, 62, 56), (-48, -30, -24, 58), (-24, 26, 0, 58)]
    pp.smd_scatter("board_smd", (-55, -58, 58, 58), top, 420, mats, rng, avoid=avoid)

    # Cooler module set aside on the floor: blower fan + fins + copper heatpipes.
    group = []
    base_x, base_y = (112, -12) if fmt == "16x9" else (8, 118)
    cool_base = pp.box("cooler_plate", (64, 62, 1.6), (base_x, base_y, 0.8), mats.alu_dark, bevel_mm=1.2)
    pp.box("cooler_coldplate", (24, 22, 2.2), (base_x - 10, base_y - 4, 2.3), mats.copper, bevel_mm=0.4)
    pp.box("cooler_pad", (12.5, 10, 0.15), (base_x - 15.5, base_y - 2.5, 3.45), mats.thermal)
    group += pp.blower_fan("cooler_fan", (base_x + 8, base_y + 6), 1.6, mats, radius_mm=21, blades=13, height_mm=8)
    pp.heatsink_fins("cooler_fins", (base_x - 2, base_y + 27), 1.6, (48, 7, 8), 34, mats, axis="y")
    pp.heatpipe("pipe_a", [(base_x - 18, base_y - 6), (base_x - 18, base_y + 18), (base_x - 22, base_y + 27), (base_x + 20, base_y + 27)], 2.6, 3.5, mats)
    pp.heatpipe("pipe_b", [(base_x - 4, base_y - 6), (base_x - 4, base_y + 14), (base_x + 2, base_y + 24), (base_x + 22, base_y + 24)], 2.6, 3.5, mats)
    cool_base.rotation_euler[2] = 0
    return shell


def stage(fmt, mats):
    pp.floor_backdrop(mats.floor, size=6.0, wall=False)
    landscape = fmt == "16x9"
    if landscape:
        cam = pp.camera((-0.02, -0.30, 0.38), (0.035, 0.002, 0.004), lens=58, fstop=7.1, focus=(0.0, 0.0, 0.01))
    else:
        cam = pp.camera((0.004, -0.16, 0.56), (0.004, 0.05, 0.0), lens=64, fstop=7.1, focus=(0.0, 0.02, 0.01))
    pp.area_light("key", (-0.30, -0.28, 0.50), (40, 0, -45), 0.8, 24, color=(1.0, 0.98, 0.95), size_y=0.5)
    pp.area_light("top", (0.04, 0.02, 0.55), (0, 0, 0), 0.35, 9, color=(0.95, 0.97, 1.0))
    pp.area_light("rim_cyan", (0.30, 0.20, 0.10), (78, 0, 128), 0.30, 18, color=(0.45, 0.82, 1.0))
    pp.area_light("rim_coral", (-0.42, 0.32, 0.10), (78, 0, -128), 0.35, 10, color=(1.0, 0.5, 0.38))
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
