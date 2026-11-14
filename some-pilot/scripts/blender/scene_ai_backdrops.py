"""Cinematic AI backdrops with space for titles: ai_core, datacenter, glass_panels.

blender -b -P scene_ai_backdrops.py -- --scene ai_core --format 16x9 --samples 256 --out <dir> [--preview]
"""

import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

import pp_lib as pp  # noqa: E402


def volume_fog(density=0.012, color=(0.75, 0.88, 1.0), size=8, center=(0, 0, 2)):
    """World-filling scatter volume so light beams become visible."""
    bpy.ops.mesh.primitive_cube_add(size=size, location=center)
    fog = bpy.context.active_object
    fog.name = "fog"
    mat = bpy.data.materials.new("fog")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.remove(nodes.get("Principled BSDF"))
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.inputs["Density"].default_value = density
    volume.inputs["Color"].default_value = (*color, 1)
    mat.node_tree.links.new(volume.outputs["Volume"], nodes["Material Output"].inputs["Volume"])
    fog.data.materials.append(mat)
    return fog


def spot(name, location, target, energy, color, size_deg=25, blend=0.4, radius=0.05):
    data = bpy.data.lights.new(name, "SPOT")
    data.energy = energy
    data.color = color
    data.spot_size = math.radians(size_deg)
    data.spot_blend = blend
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    bpy.context.collection.objects.link(obj)
    pp.look_at(obj, target)
    return obj


def glass(name, tint=(0.85, 0.95, 1.0), roughness=0.04):
    mat, nodes, links, bsdf = pp._principled(name)
    pp._set(bsdf, "Base Color", (*tint, 1))
    pp._set(bsdf, "Transmission Weight", 1.0)
    pp._set(bsdf, "Roughness", roughness)
    pp._set(bsdf, "IOR", 1.45)
    return mat


def batch_boxes(name, boxes, material):
    """Many axis-aligned boxes as ONE mesh object: thousands of LEDs without bpy.ops overhead."""
    import bmesh

    bm = bmesh.new()
    for (sx, sy, sz), (x, y, z) in boxes:
        verts = bmesh.ops.create_cube(bm, size=1)["verts"]
        bmesh.ops.scale(bm, vec=(sx * pp.MM, sy * pp.MM, sz * pp.MM), verts=verts)
        bmesh.ops.translate(bm, vec=(x * pp.MM, y * pp.MM, z * pp.MM), verts=verts)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def bokeh_field(count, x_range, y_range, z_range, seed=11, size=(8, 26)):
    """Small emissive orbs far behind the focus plane: they render as soft bokeh discs."""
    rng = random.Random(seed)
    palette = [emission("bokeh_cyan", (0.0, 0.55, 1.0), 14), emission("bokeh_white", (0.8, 0.9, 1.0), 9), emission("bokeh_coral", (1.0, 0.32, 0.18), 14)]
    for k in range(count):
        material = palette[2] if k % 9 == 0 else (palette[1] if k % 4 == 0 else palette[0])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=rng.uniform(*size) * pp.MM, segments=16, ring_count=8,
                                             location=(rng.uniform(*x_range) * pp.MM, rng.uniform(*y_range) * pp.MM, rng.uniform(*z_range) * pp.MM))
        bpy.context.active_object.data.materials.append(material)


def emission(name, color, strength):
    return pp.mat_basic(name, color, emission=color, emission_strength=strength)


def ai_core(fmt, mats):
    rng = random.Random(5)
    pp.floor_backdrop(pp.mat_floor(radius_m=0.9, color=(0.0015, 0.002, 0.005)), size=12, wall=False)
    # Chip package: dark substrate, gold traces fanning out, a glowing die under a glass block.
    pp.box("substrate", (180, 180, 6), (0, 0, 60), pp.mat_basic("sub", (0.01, 0.015, 0.03), roughness=0.3, coat=0.8), bevel_mm=6, segments=6)
    gold = mats.gold
    for side in range(4):
        for k in range(22):
            offset = -84 + k * 8
            length = rng.uniform(18, 34)
            if side == 0:
                pp.box(f"trace_{side}_{k}", (length, 1.6, 0.4), (90 - length / 2 + 1, offset, 63.2), gold)
            elif side == 1:
                pp.box(f"trace_{side}_{k}", (length, 1.6, 0.4), (-90 + length / 2 - 1, offset, 63.2), gold)
            elif side == 2:
                pp.box(f"trace_{side}_{k}", (1.6, length, 0.4), (offset, 90 - length / 2 + 1, 63.2), gold)
            else:
                pp.box(f"trace_{side}_{k}", (1.6, length, 0.4), (offset, -90 + length / 2 - 1, 63.2), gold)
    die = emission("die_glow", (0.0, 0.5, 1.0), 9.0)
    grid = 6
    cell = 15
    for gx in range(grid):
        for gy in range(grid):
            hot = (gx, gy) in {(2, 2), (3, 2), (2, 3)}
            material = emission("die_hot", (1.0, 0.25, 0.10), 11.0) if hot else die
            pp.box(f"core_{gx}_{gy}", (cell - 2.4, cell - 2.4, 1.2), (-45 + gx * cell + cell / 2, -45 + gy * cell + cell / 2, 64), material, bevel_mm=0.6)
    pp.box("glass_cap", (110, 110, 22), (0, 0, 76), glass("glass_cap"), bevel_mm=6, segments=8)
    # Gold slider (brand parameter) etched across the glass top.
    pp.box("slider_bar", (80, 3.2, 0.8), (0, -40, 87.6), emission("slider", (1, 1, 1), 6))
    pp.cylinder("slider_knob", 5.2, 1.0, (12, -40, 87.7), emission("knob", (1, 1, 1), 6), vertices=48)
    # Floating pixel cubes (brand pixels) orbiting the chip.
    cube_glass = glass("cube_glass", (0.8, 0.95, 1.0), 0.12)
    coral_cube = emission("coral_cube", (1.0, 0.36, 0.22), 6)
    for k in range(26):
        angle = rng.uniform(0, math.tau)
        radius = rng.uniform(130, 260)
        size = rng.uniform(6, 16)
        z = rng.uniform(70, 230)
        material = coral_cube if k % 7 == 0 else cube_glass
        pp.box(f"pixel_{k}", (size, size, size), (math.cos(angle) * radius, math.sin(angle) * radius, z), material, bevel_mm=1.0, rotation_deg=(rng.uniform(0, 45), rng.uniform(0, 45), rng.uniform(0, 90)))
    volume_fog(0.012)
    spot("beam_cyan", (-0.35, 0.25, 1.2), (0, 0, 0.06), 700, (0.25, 0.7, 1.0), 12, blend=0.6)
    spot("beam_coral", (0.45, 0.35, 1.1), (0, 0, 0.06), 320, (1.0, 0.38, 0.22), 9, blend=0.6)
    pp.area_light("key", (-0.5, -0.6, 0.7), (50, 0, -35), 0.8, 6)
    bokeh_field(40, (-900, 900), (900, 2200), (0, 900), seed=21)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if fmt == "16x9":
        pp.camera((0.0, -0.78, 0.48), (0.0, 0.0, 0.10), lens=50, fstop=5.6, focus=(0, 0, 0.07))
    else:
        pp.camera((0.0, -0.70, 0.62), (0.0, 0.0, 0.14), lens=44, fstop=5.6, focus=(0, 0, 0.07))


def datacenter(fmt, mats):
    rng = random.Random(9)
    floor = pp.mat_basic("dc_floor", (0.008, 0.01, 0.015), roughness=0.12, coat=0.7, coat_rough=0.04)
    pp.floor_backdrop(floor, size=40, wall=False)
    rack = pp.mat_basic("rack", (0.012, 0.013, 0.016), roughness=0.4, metallic=0.5)
    mesh = pp.mat_basic("rack_mesh", (0.03, 0.035, 0.045), roughness=0.5, metallic=0.6)
    leds = {"cyan": [], "white": [], "coral": []}
    racks, doors = [], []
    for side in (-1, 1):
        for k in range(16):
            y = -2000 + k * 640
            x = side * 1600
            racks.append(((2000, 620, 2100), (x, y, 1050)))
            doors.append(((6, 560, 1960), (x - side * 1002, y, 1050)))
            for u in range(36):
                z = 180 + u * 50
                if rng.random() < 0.7:
                    for led in range(rng.randint(1, 4)):
                        roll = rng.random()
                        key = "coral" if roll < 0.05 else ("white" if roll < 0.3 else "cyan")
                        leds[key].append(((4, rng.uniform(6, 40), 3), (x - side * 1006, y - 240 + led * 60 + rng.uniform(0, 20), z)))
    batch_boxes("racks", racks, rack)
    batch_boxes("rack_doors", doors, mesh)
    batch_boxes("leds_cyan", leds["cyan"], emission("led_cyan", (0.0, 0.6, 1.0), 30))
    batch_boxes("leds_white", leds["white"], emission("led_white", (0.85, 0.93, 1.0), 18))
    batch_boxes("leds_coral", leds["coral"], emission("led_coral", (1.0, 0.3, 0.15), 30))
    batch_boxes("ceiling", [((60, 500, 10), (0, 600 + k * 600, 3200)) for k in range(14)], emission("ceiling_strip", (0.85, 0.92, 1.0), 4))
    # End of the aisle: a cold glow that the fog turns into a soft vanishing point.
    for k in range(7):
        y = 0.4 + k * 1.15
        spot(f"aisle_spot_{k}", (0.0, y, 3.0), (0.0, y + 0.15, 0.0), 260, (0.55, 0.8, 1.0), 34, blend=0.5)
    pp.box("aisle_end", (2600, 20, 2600), (0, 9000, 1300), emission("aisle_end", (0.0, 0.2, 0.7), 0.25))
    volume_fog(0.02, size=26, center=(0, 5, 2))
    pp.world((0.002, 0.003, 0.006), 1.0)
    if fmt == "16x9":
        pp.camera((0.0, -1.2, 1.45), (0.0, 8.0, 1.25), lens=30, fstop=4.0, focus=(0, 3.0, 1.2))
    else:
        pp.camera((0.0, -1.2, 1.35), (0.0, 8.0, 1.45), lens=24, fstop=4.0, focus=(0, 3.0, 1.2))


def glass_panels(fmt, mats):
    pp.floor_backdrop(pp.mat_floor(radius_m=2.2, color=(0.0015, 0.002, 0.005)), size=20, wall=False)
    frosted = glass("frosted", (0.82, 0.93, 1.0), 0.22)
    edge_cyan = emission("edge_cyan", (0.0, 0.55, 1.0), 18)
    edge_coral = emission("edge_coral", (1.0, 0.3, 0.15), 18)
    count = 7
    for k in range(count):
        t = k - (count - 1) / 2
        x = t * 330
        y = 1000 + abs(t) ** 1.6 * 110
        z = 330 + (0.5 - abs(t) / count) * 60
        parts = [
            pp.box(f"card_{k}", (280, 6, 400), (x, y, z), frosted, bevel_mm=14, segments=8),
            pp.box(f"card_edge_{k}", (230, 4, 5), (x, y - 6, z + 182), edge_coral if t == 0 else edge_cyan),
        ]
        pp.rotate_group(parts, (x, y, z), -t * 9)
    bokeh_field(70, (-2400, 2400), (2600, 5200), (-200, 1800), seed=4, size=(14, 40))
    volume_fog(0.0035)
    pp.area_light("top", (0.0, 0.8, 2.4), (0, 0, 0), 3.0, 70)
    pp.area_light("back_rim", (0.0, 2.6, 1.4), (-62, 0, 0), 2.5, 260, color=(0.35, 0.7, 1.0))
    spot("beam", (-1.4, 3.4, 2.6), (0.4, 1.0, 0.0), 2200, (0.3, 0.7, 1.0), 16, blend=0.7)
    spot("beam2", (1.6, 3.6, 2.4), (-0.3, 1.2, 0.0), 900, (1.0, 0.4, 0.25), 12, blend=0.7)
    pp.world((0.0015, 0.002, 0.005), 1.0)
    if fmt == "16x9":
        pp.camera((0.0, -1.25, 0.42), (0.0, 1.2, 0.36), lens=32, fstop=1.2, focus=(0, 1.0, 0.33))
    else:
        pp.camera((0.0, -1.6, 0.48), (0.0, 1.2, 0.40), lens=26, fstop=1.2, focus=(0, 1.0, 0.33))


SCENES = {"ai_core": ai_core, "datacenter": datacenter, "glass_panels": glass_panels}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", choices=list(SCENES), required=True)
    parser.add_argument("--format", default="16x9", choices=["16x9", "9x16"])
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--out", required=True)
    parser.add_argument("--preview", action="store_true")
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
            obj.visible_camera = False  # area lights must light the set, not appear in frame
            if obj.data.type == "AREA":
                obj.visible_glossy = False  # no mirrored light rectangles in the glossy floor
    os.makedirs(args.out, exist_ok=True)
    pp.render_beauty(scene, os.path.join(args.out, f"{args.scene}.png"))


if __name__ == "__main__":
    main()
