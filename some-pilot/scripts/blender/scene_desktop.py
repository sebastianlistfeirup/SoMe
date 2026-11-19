"""Open desktop: ATX mid-tower with the side panel removed, mid-build (CPU cooler not fitted yet).
RAM (DIMMs), SSD (M.2 on the board) and CPU (in the socket) are tagged for masks.

The motherboard is built flat in board coordinates (u along the board's long edge,
v across, z out of the board) and then stood upright inside the case.

blender -b -P scene_desktop.py -- --format 16x9 --samples 256 --out <dir> [--masks] [--preview]
"""

import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import pp_lib as pp  # noqa: E402

CASE = (420, 220, 470)  # depth (x), width (y), height (z) in mm


def build_board(mats):
    """ATX board 305 x 244 mm. Board coords: u = vertical (top edge at +u), v = front->back, z = out of board."""
    rng = random.Random(3)
    before = {obj.name for obj in bpy.context.scene.objects}
    board_mat = pp.mat_image("desktop_board", pp.pcb_texture("desktop_board", base=(9, 10, 12), trace=(22, 24, 28), seed=31, dark=True), roughness=0.32, coat=0.6, bump_strength=0.05)
    pp.box("mb", (305, 244, 1.6), (0, 0, 0.8), board_mat, bevel_mm=0.6, segments=2)
    top = 1.6
    # VRM heatsinks (top and left of socket), chipset heatsink, rear I/O cover.
    pp.box("vrm_top", (26, 120, 14), (118, -2, top + 7), mats.alu_dark, bevel_mm=1.5, segments=3)
    pp.box("vrm_left", (110, 26, 14), (60, -100, top + 7), mats.alu_dark, bevel_mm=1.5, segments=3)
    pp.box("io_cover", (150, 34, 22), (75, -112, top + 11), mats.steel_black, bevel_mm=3, segments=4)
    pp.box("chipset_hs", (80, 70, 9), (-80, -55, top + 4.5), mats.alu_dark, bevel_mm=2, segments=3)
    # CPU socket with retention frame and the CPU (IHS). Tagged cpu.
    sx, sy = 62, 6
    pp.box("socket_base", (60, 66, 2.6), (sx, sy, top + 1.3), mats.plastic_grey, bevel_mm=0.6)
    pp.box("socket_frame_a", (60, 6, 3.4), (sx, sy - 33, top + 1.7), mats.steel, bevel_mm=0.5)
    pp.box("socket_frame_b", (60, 6, 3.4), (sx, sy + 33, top + 1.7), mats.steel, bevel_mm=0.5)
    pp.box("socket_frame_c", (6, 66, 3.4), (sx - 30, sy, top + 1.7), mats.steel, bevel_mm=0.5)
    pp.box("socket_frame_d", (6, 66, 3.4), (sx + 30, sy, top + 1.7), mats.steel, bevel_mm=0.5)
    pp.cylinder("socket_lever", 0.9, 66, (sx + 36, sy, top + 2.5), mats.steel, rotation_deg=(90, 0, 0))
    pp.box("cpu_substrate", (40, 40, 1.2), (sx, sy, top + 3.2), pp.mat_basic("cpu_sub", (0.05, 0.14, 0.09), roughness=0.4, coat=0.5), bevel_mm=0.3, group="cpu")
    ihs = pp.box("cpu_ihs", (36, 36, 3.2), (sx, sy, top + 5.4), mats.nickel, bevel_mm=1.2, segments=4, group="cpu")
    for dx, dy in ((-14, -14), (14, -14), (-14, 14), (14, 14)):
        pp.box(f"ihs_notch_{dx}_{dy}", (4, 4, 0.6), (sx + dx, sy + dy, top + 3.9), mats.ceramic, group="cpu")
    # Cooler mounting standoffs (cooler not fitted yet).
    for dx, dy in ((-36, -45), (36, -45), (-36, 45), (36, 45)):
        pp.cylinder(f"cooler_standoff_{dx}_{dy}", 2.6, 8, (sx + dx, sy + dy, top + 4), mats.steel_black, bevel_mm=0.4)
    # Four DIMM slots to the right of the socket; two DIMMs fitted (slots 2 and 4). Tagged ram.
    hs = pp.mat_brushed("dimm_hs", (0.05, 0.055, 0.065), roughness=0.3)
    for k in range(4):
        v = 70 + k * 9.5
        pp.box(f"dimm_slot_{k}", (133, 6.2, 7), (40, v, top + 3.5), mats.plastic_black, bevel_mm=0.5)
        for side in (-1, 1):
            pp.box(f"dimm_latch_{k}_{side}", (6, 6.8, 9), (40 + side * 69, v, top + 4.5), mats.plastic_grey, bevel_mm=0.6)
    for k in (1, 3):
        v = 70 + k * 9.5
        parts = pp.memory_module(f"dimm{k}", (40, v), top + 5.5, mats, length_mm=133.35, height_mm=31.25, standing=True, heatspreader=hs)
        for part in parts:
            part["pp_group"] = "ram"
    # PCIe x16 slots and an M.2 slot between them with the SSD. Tagged ssd.
    for k, u in enumerate((-25, -105)):
        pp.box(f"pcie_{k}", (12, 90, 11), (u, -40, top + 5.5), mats.plastic_black, bevel_mm=0.6)
        pp.box(f"pcie_armor_{k}", (13, 92, 11.5), (u, -40, top + 5.6), mats.steel, bevel_mm=0.6)
    # Top M.2 slot between the socket and the first PCIe slot, so the SSD stays visible above the GPU.
    pp.box("m2_socket", (22.5, 4.2, 3.0), (4, -77, top + 1.5), mats.plastic_black, bevel_mm=0.3)
    pp.m2_ssd("ssd", (4, -35), top + 1.2, mats, angle_deg=90)
    pp.screw("m2_screw", (4, 6, top + 1.0), mats, radius_mm=1.9, head_mm=0.9)
    # Headers, 24-pin and 8-pin power, SATA, chokes around the socket.
    pp.box("atx24", (52, 10, 16), (-10, 115, top + 8), mats.plastic_black, bevel_mm=0.6)
    pp.box("eps8", (20, 10, 14), (140, -60, top + 7), mats.plastic_black, bevel_mm=0.6)
    for k in range(6):
        pp.box(f"sata_{k}", (8, 16, 9), (-120 + (k % 3) * 11, 112 - (k // 3) * 0, top + 4.5), mats.plastic_black, bevel_mm=0.4)
    for k in range(10):
        pp.box(f"choke_{k}", (8, 8, 6), (sx + 42 - k * 0 if k < 5 else sx - 10 + (k - 5) * 11, sy - 70 if k >= 5 else sy - 46 + k * 11, top + 3), mats.inductor, bevel_mm=0.7)
    pp.cylinder("cmos", 10, 3.2, (-140, 40, top + 1.6), mats.steel, bevel_mm=0.6)
    avoid = [(sx - 45, sy - 50, sx + 45, sy + 50), (-30, 60, 112, 112), (-8, -80, 16, 8), (-130, -88, 20, 8)]
    pp.smd_scatter("mb_smd", (-148, -118, 148, 118), top, 460, mats, rng, avoid=avoid)
    return pp.collect_new(before)


def build(mats):
    dx, dy, dz = CASE
    # Case: open on the -y side (side panel removed). Black steel.
    shell = pp.box("case", (dx, dy, dz), (0, 0, dz / 2), mats.steel_black, bevel_mm=3, segments=4)
    cut = pp.box("case_cut", (dx - 4, dy, dz - 4), (0, -2.5, dz / 2), mats.steel_black)
    for obj in (shell,):
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier="bevel")
    mod = shell.modifiers.new("open", "BOOLEAN")
    mod.object = cut
    mod.operation = "DIFFERENCE"
    bpy.context.view_layer.objects.active = shell
    bpy.ops.object.modifier_apply(modifier="open")
    bpy.data.objects.remove(cut, do_unlink=True)
    pp.box("tray_backplate", (dx - 8, 2, dz - 8), (0, dy / 2 - 6, dz / 2), mats.steel_black)
    # PSU shroud and PSU vent.
    pp.box("psu_shroud", (dx - 8, dy - 10, 80), (0, 0, 44), mats.steel_black, bevel_mm=2)
    for k in range(14):
        pp.box(f"shroud_slot_{k}", (3, dy - 60, 0.5), (-150 + k * 9, 0, 84.3), pp.mat_basic("slot", (0.002, 0.002, 0.003), roughness=0.9))
    # Front intake fans (3 x 120 mm) behind the front, rear exhaust fan.
    for k in range(3):
        z = 140 + k * 122
        pp.box(f"front_fan_frame_{k}", (25, 120, 120), (-dx / 2 + 18, 0, z), mats.plastic_black, bevel_mm=4)
        ring = pp.cylinder(f"front_fan_ring_{k}", 58, 26, (-dx / 2 + 18, 0, z), pp.mat_basic(f"fan_ring_{k}", (0.6, 0.85, 1.0), emission=(0.25, 0.75, 1.0), emission_strength=3.0), vertices=64, rotation_deg=(0, 90, 0))
        hub = pp.cylinder(f"front_fan_hub_{k}", 20, 27, (-dx / 2 + 18, 0, z), mats.plastic_black, vertices=48, rotation_deg=(0, 90, 0))
        for b in range(9):
            angle = b * 40
            blade = pp.box(f"front_fan_blade_{k}_{b}", (2, 36, 18), (-dx / 2 + 18, 0, z), mats.fan_blade, bevel_mm=0.6)
            rad = math.radians(angle)
            blade.location.y = math.cos(rad) * 0.036
            blade.location.z = z * pp.MM + math.sin(rad) * 0.036
            blade.rotation_euler = (rad + math.radians(90), math.radians(25), 0)
    pp.box("rear_fan", (25, 120, 120), (dx / 2 - 16, 0, dz - 110), mats.plastic_black, bevel_mm=4)
    # Motherboard standing on the tray (board z -> world -y, board u -> world z, board v -> world x).
    parts = build_board(mats)
    # Proper rotation (det = +1): board u -> world +z, board v -> world -x, board normal -> world -y.
    from mathutils import Matrix

    board = pp.group_empty("board_assembly", parts, (30, dy / 2 - 10, dz - 180))
    board.rotation_euler = Matrix(((0, -1, 0), (0, 0, -1), (1, 0, 0))).to_euler()
    # Graphics card in the top PCIe slot: card plane perpendicular to the board, fans facing down.
    slot_z = dz - 180 - 25
    gx, gy, gz = 10, dy / 2 - 10 - 72, slot_z - 34
    gpu_shroud = pp.mat_brushed("gpu_shroud", (0.07, 0.075, 0.085), roughness=0.34)
    pp.box("gpu_body", (312, 128, 58), (gx, gy, gz), gpu_shroud, bevel_mm=6, segments=5)
    pp.box("gpu_backplate", (300, 120, 3), (gx, gy, gz + 30.5), mats.alu_dark, bevel_mm=1.2)
    pp.box("gpu_bracket", (2, 128, 62), (dx / 2 - 12, gy, gz), mats.steel, bevel_mm=0.6)
    for k in range(3):
        fx = gx - 100 + k * 100
        pp.cylinder(f"gpu_fan_ring_{k}", 46, 3, (fx, gy, gz - 30), mats.plastic_black, vertices=64)
        pp.cylinder(f"gpu_fan_hub_{k}", 14, 4, (fx, gy, gz - 31), gpu_shroud, vertices=48)
    light_bar = pp.mat_basic("gpu_light", (0.6, 0.9, 1.0), emission=(0.2, 0.75, 1.0), emission_strength=5)
    pp.box("gpu_lightbar", (230, 1.5, 5), (gx - 20, gy - 64.6, gz + 12), light_bar)
    pp.box("gpu_edge_trim", (290, 1.2, 2), (gx, gy - 64.4, gz - 14), mats.alu)
    pp.box("gpu_power", (24, 14, 10), (gx + 60, gy - 40, gz + 33), mats.plastic_black, bevel_mm=0.6)
    # Cables: 24-pin sleeved bundle and GPU power.
    for k in range(6):
        pp.cylinder(f"atx_cable_{k}", 1.6, 120, (-95, 20 - k * 3.4, 300), mats.cable, vertices=16)
    return board


def stage(fmt, mats):
    pp.floor_backdrop(mats.floor, size=8.0, wall=False)
    dx, dy, dz = CASE
    if fmt == "16x9":
        cam = pp.camera((-0.22, -0.98, 0.50), (0.02, 0.04, 0.27), lens=44, fstop=9, focus=(0.03, 0.08, 0.3))
    else:
        cam = pp.camera((-0.20, -1.28, 0.46), (0.02, 0.04, 0.24), lens=46, fstop=9, focus=(0.03, 0.08, 0.3))
    pp.area_light("key", (-0.65, -0.85, 0.95), (50, 0, -35), 1.2, 38, color=(1.0, 0.98, 0.95), size_y=0.9)
    pp.area_light("inside_fill", (0.05, -0.55, 0.40), (85, 0, 0), 0.35, 7, color=(0.9, 0.95, 1.0))
    pp.area_light("rim_cyan", (0.75, 0.6, 0.6), (60, 0, 135), 0.6, 45, color=(0.45, 0.82, 1.0))
    pp.area_light("rim_coral", (-0.8, 0.5, 0.3), (75, 0, -125), 0.5, 18, color=(1.0, 0.5, 0.38))
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
    build(mats)
    stage(args.format, mats)
    os.makedirs(args.out, exist_ok=True)
    pp.render_beauty(scene, os.path.join(args.out, "clean.png"))
    if args.masks:
        pp.render_masks(scene, args.out)


if __name__ == "__main__":
    main()
