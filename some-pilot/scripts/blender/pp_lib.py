"""Shared Blender helpers for Pixel & Parameters hardware renders (Blender 5.x, Cycles).

Units: metres in Blender, helpers take millimetres. Every component is tagged with
obj["pp_group"] in {"ram", "ssd", "cpu"} or nothing, so masks can be rendered.
Textures (PCB traces, labels, contacts) are generated with Pillow at build time.
No brand logos are reproduced; markings are generic.
"""

import math
import os
import random
import tempfile

import bpy
from mathutils import Vector

from pp_textures import chip_marking_texture, contacts_texture, label_texture, pcb_texture  # noqa: F401

MM = 0.001
TEX_DIR = os.path.join(tempfile.gettempdir(), "pp_textures")
os.makedirs(TEX_DIR, exist_ok=True)


# --- scene ------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def setup_cycles(scene, samples=256, width=1920, height=1080):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for device_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = device_type
            prefs.get_devices()
            if any(device.type == device_type for device in prefs.devices):
                for device in prefs.devices:
                    device.use = device.type == device_type
                scene.cycles.device = "GPU"
                break
        except Exception:
            continue
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.glossy_bounces = 6
    scene.cycles.transmission_bounces = 6
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        scene.view_settings.view_transform = "Filmic"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def world(color=(0.004, 0.006, 0.014), strength=1.0):
    w = bpy.data.worlds.new("PPWorld")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = w


def area_light(name, location, rotation_deg, size, energy, color=(1, 1, 1), shape="RECTANGLE", size_y=None, spread_deg=None):
    data = bpy.data.lights.new(name, "AREA")
    data.shape = shape
    if spread_deg is not None:
        data.spread = math.radians(spread_deg)
    data.size = size
    if size_y is not None:
        data.size_y = size_y
    data.energy = energy
    data.color = color
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    bpy.context.collection.objects.link(obj)
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def camera(location, target, lens=70, fstop=4.0, focus=None, sensor=36, roll_deg=0.0):
    data = bpy.data.cameras.new("Camera")
    data.lens = lens
    data.sensor_width = sensor
    data.dof.use_dof = True
    data.dof.aperture_fstop = fstop
    obj = bpy.data.objects.new("Camera", data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    data.dof.focus_distance = (Vector(focus or target) - obj.location).length
    if roll_deg:
        obj.rotation_euler.rotate_axis("Z", math.radians(roll_deg))
    bpy.context.scene.camera = obj
    return obj


# --- materials -----------------------------------------------------------------------

def _principled(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    return mat, nodes, mat.node_tree.links, bsdf


def _set(bsdf, key, value):
    if key in bsdf.inputs:
        bsdf.inputs[key].default_value = value


def mat_basic(name, color, metallic=0.0, roughness=0.5, coat=0.0, coat_rough=0.05, aniso=0.0, emission=None, emission_strength=0.0):
    mat, nodes, links, bsdf = _principled(name)
    _set(bsdf, "Base Color", (*color, 1))
    _set(bsdf, "Metallic", metallic)
    _set(bsdf, "Roughness", roughness)
    _set(bsdf, "Coat Weight", coat)
    _set(bsdf, "Coat Roughness", coat_rough)
    _set(bsdf, "Anisotropic", aniso)
    if emission:
        _set(bsdf, "Emission Color", (*emission, 1))
        _set(bsdf, "Emission Strength", emission_strength)
    return mat


def mat_brushed(name, color, roughness=0.26, scale=(1.0, 180.0, 1.0), metallic=1.0):
    """Brushed metal: fine stretched noise drives roughness and a tiny bump."""
    mat, nodes, links, bsdf = _principled(name)
    _set(bsdf, "Base Color", (*color, 1))
    _set(bsdf, "Metallic", metallic)
    _set(bsdf, "Anisotropic", 0.55)
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale[0] * 60, scale[1] * 60, scale[2] * 60)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = roughness * 0.75
    ramp.inputs["To Max"].default_value = roughness * 1.25
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.035
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def mat_image(name, image_path, roughness=0.45, metallic=0.0, coat=0.0, bump_strength=0.0, roughness_map=False):
    mat, nodes, links, bsdf = _principled(name)
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(image_path)
    tex.interpolation = "Cubic"
    coord = nodes.new("ShaderNodeTexCoord")
    links.new(coord.outputs["UV"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", roughness)
    _set(bsdf, "Metallic", metallic)
    _set(bsdf, "Coat Weight", coat)
    _set(bsdf, "Coat Roughness", 0.08)
    if bump_strength:
        bw = nodes.new("ShaderNodeRGBToBW")
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = bump_strength
        bump.inputs["Distance"].default_value = 0.0002
        links.new(tex.outputs["Color"], bw.inputs["Color"])
        links.new(bw.outputs["Val"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if roughness_map:
        bw2 = nodes.new("ShaderNodeRGBToBW")
        inv = nodes.new("ShaderNodeMapRange")
        inv.inputs["To Min"].default_value = roughness + 0.25
        inv.inputs["To Max"].default_value = max(0.05, roughness - 0.25)
        links.new(tex.outputs["Color"], bw2.inputs["Color"])
        links.new(bw2.outputs["Val"], inv.inputs["Value"])
        links.new(inv.outputs["Result"], bsdf.inputs["Roughness"])
    return mat


def mat_floor(radius_m=0.55, color=(0.006, 0.009, 0.02)):
    """Studio floor that falls off to black away from the product (spherical gradient)."""
    mat, nodes, links, bsdf = _principled("floor")
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1 / radius_m, 1 / radius_m, 1 / radius_m)
    grad = nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "SPHERICAL"
    power = nodes.new("ShaderNodeMath")
    power.operation = "POWER"
    power.inputs[1].default_value = 1.8
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0, 0, 0, 1)
    mix.inputs["B"].default_value = (*color, 1)
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], grad.inputs["Vector"])
    links.new(grad.outputs["Fac"], power.inputs[0])
    links.new(power.outputs["Value"], mix.inputs["Factor"])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    spec = nodes.new("ShaderNodeMath")
    spec.operation = "MULTIPLY"
    spec.inputs[1].default_value = 0.35
    links.new(power.outputs["Value"], spec.inputs[0])
    links.new(spec.outputs["Value"], bsdf.inputs["Coat Weight"])
    _set(bsdf, "Roughness", 0.55)
    _set(bsdf, "Specular IOR Level", 0.25)
    return mat


class Materials:
    def __init__(self):
        self.alu = mat_brushed("alu", (0.78, 0.79, 0.81), roughness=0.24)
        self.alu_dark = mat_brushed("alu_dark", (0.16, 0.17, 0.19), roughness=0.32)
        self.steel_black = mat_basic("steel_black", (0.012, 0.013, 0.016), roughness=0.42, coat=0.2, coat_rough=0.3)
        self.plastic_black = mat_basic("plastic_black", (0.010, 0.010, 0.012), roughness=0.55)
        self.plastic_grey = mat_basic("plastic_grey", (0.12, 0.12, 0.13), roughness=0.5)
        self.chip = mat_basic("chip", (0.012, 0.012, 0.014), roughness=0.62)
        self.gold = mat_basic("gold", (1.0, 0.74, 0.34), metallic=1.0, roughness=0.22)
        self.copper = mat_basic("copper", (0.96, 0.52, 0.32), metallic=1.0, roughness=0.28)
        self.nickel = mat_brushed("nickel", (0.80, 0.80, 0.82), roughness=0.16, scale=(1, 1, 1))
        self.steel = mat_basic("steel", (0.62, 0.63, 0.65), metallic=1.0, roughness=0.34)
        self.solder = mat_basic("solder", (0.78, 0.78, 0.78), metallic=1.0, roughness=0.25)
        self.ceramic = mat_basic("ceramic", (0.20, 0.16, 0.11), roughness=0.5)
        self.cap_alu = mat_basic("cap_alu", (0.55, 0.56, 0.58), metallic=1.0, roughness=0.3)
        self.inductor = mat_basic("inductor", (0.05, 0.05, 0.055), roughness=0.4, metallic=0.4)
        self.thermal = mat_basic("thermal", (0.42, 0.42, 0.44), roughness=0.8)
        self.rubber = mat_basic("rubber", (0.02, 0.02, 0.02), roughness=0.85)
        self.fan_blade = mat_basic("fan_blade", (0.025, 0.026, 0.03), roughness=0.4, coat=0.3)
        self.floor = mat_floor()
        self.battery = mat_basic("battery", (0.012, 0.012, 0.014), roughness=0.5, coat=0.15)
        self.cable = mat_basic("cable", (0.015, 0.015, 0.018), roughness=0.55)
        self.port_blue = mat_basic("port_blue", (0.05, 0.25, 0.85), roughness=0.4)


# --- geometry -------------------------------------------------------------------------

def box(name, size_mm, location_mm, material, bevel_mm=0.0, segments=3, group=None, rotation_deg=(0, 0, 0), parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_mm[0] * MM, size_mm[1] * MM, size_mm[2] * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location = (location_mm[0] * MM, location_mm[1] * MM, location_mm[2] * MM)
    obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    if bevel_mm > 0:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel_mm * MM
        mod.segments = segments
        mod.limit_method = "ANGLE"
        mod.harden_normals = False
    obj.data.materials.append(material)
    for poly in obj.data.polygons:
        poly.use_smooth = bevel_mm > 0
    if group:
        obj["pp_group"] = group
    if parent:
        obj.parent = parent
    return obj


def cylinder(name, radius_mm, depth_mm, location_mm, material, vertices=48, rotation_deg=(0, 0, 0), group=None, bevel_mm=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius_mm * MM, depth=depth_mm * MM)
    obj = bpy.context.active_object
    obj.name = name
    obj.location = (location_mm[0] * MM, location_mm[1] * MM, location_mm[2] * MM)
    obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    if bevel_mm > 0:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel_mm * MM
        mod.segments = 3
        mod.limit_method = "ANGLE"
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.data.materials.append(material)
    if group:
        obj["pp_group"] = group
    return obj


def plane(name, size_mm, location_mm, material, rotation_deg=(0, 0, 0), group=None):
    bpy.ops.mesh.primitive_plane_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size_mm[0] * MM, size_mm[1] * MM, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location = (location_mm[0] * MM, location_mm[1] * MM, location_mm[2] * MM)
    obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    obj.data.materials.append(material)
    if group:
        obj["pp_group"] = group
    return obj


def hollow_shell(name, outer_mm, wall_mm, floor_mm, location_mm, material, radius_mm=8.0):
    """Open-top rounded box (chassis) built with a solidify-free boolean of two bevelled boxes."""
    outer = box(name, outer_mm, (location_mm[0], location_mm[1], location_mm[2] + outer_mm[2] / 2), material, bevel_mm=radius_mm, segments=8)
    inner = box(name + "_cut", (outer_mm[0] - 2 * wall_mm, outer_mm[1] - 2 * wall_mm, outer_mm[2]), (location_mm[0], location_mm[1], location_mm[2] + floor_mm + outer_mm[2] / 2 + 0.01), material, bevel_mm=max(0.5, radius_mm - wall_mm), segments=8)
    for obj in (outer, inner):
        bpy.context.view_layer.objects.active = obj
        for mod in list(obj.modifiers):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    mod = outer.modifiers.new("cut", "BOOLEAN")
    mod.object = inner
    mod.operation = "DIFFERENCE"
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.modifier_apply(modifier="cut")
    bpy.data.objects.remove(inner, do_unlink=True)
    for poly in outer.data.polygons:
        poly.use_smooth = True
    try:
        outer.data.set_sharp_from_angle(angle=math.radians(35))
    except Exception:
        pass
    return outer


def floor_backdrop(material, size=4.0, wall=True):
    """Floor (optionally with a back wall); without the wall the floor fades into the dark world."""
    bpy.ops.mesh.primitive_plane_add(size=size)
    floor = bpy.context.active_object
    floor.name = "floor"
    floor.data.materials.append(material)
    if not wall:
        return floor
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, size / 2, size / 2), rotation=(math.radians(90), 0, 0))
    wall = bpy.context.active_object
    wall.name = "wall"
    wall.data.materials.append(material)
    return floor


# --- components ---------------------------------------------------------------------------

def rotate_group(parts, center_mm, angle_deg):
    if not angle_deg:
        return parts
    angle = math.radians(angle_deg)
    cx, cy = center_mm[0] * MM, center_mm[1] * MM
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    for part in parts:
        dx, dy = part.location.x - cx, part.location.y - cy
        part.location.x = cx + dx * cos_a - dy * sin_a
        part.location.y = cy + dx * sin_a + dy * cos_a
        part.rotation_euler[2] += angle
    return parts

def smd_scatter(prefix, area_mm, z_mm, count, mats, rng, avoid=()):
    """Resistors/caps (0402/0603), some taller caps: the fine detail that sells realism."""
    x0, y0, x1, y1 = area_mm
    made = 0
    attempts = 0
    while made < count and attempts < count * 6:
        attempts += 1
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if any(ax0 <= x <= ax1 and ay0 <= y <= ay1 for ax0, ay0, ax1, ay1 in avoid):
            continue
        kind = rng.random()
        rot = rng.choice([0, 90])
        if kind < 0.55:
            box(f"{prefix}_r{made}", (1.0, 0.5, 0.35), (x, y, z_mm + 0.17), mats.chip if rng.random() < 0.6 else mats.ceramic, rotation_deg=(0, 0, rot))
        elif kind < 0.9:
            box(f"{prefix}_c{made}", (1.6, 0.8, 0.8), (x, y, z_mm + 0.4), mats.ceramic, bevel_mm=0.08, segments=2, rotation_deg=(0, 0, rot))
        else:
            box(f"{prefix}_q{made}", (2.9, 1.6, 1.0), (x, y, z_mm + 0.5), mats.chip, bevel_mm=0.1, segments=2, rotation_deg=(0, 0, rot))
        made += 1


def screw(name, location_mm, mats, radius_mm=2.2, head_mm=1.2):
    head = cylinder(name, radius_mm, head_mm, (location_mm[0], location_mm[1], location_mm[2] + head_mm / 2), mats.steel, bevel_mm=0.3)
    box(name + "_x1", (radius_mm * 1.3, 0.35, 0.4), (location_mm[0], location_mm[1], location_mm[2] + head_mm), mats.chip)
    box(name + "_x2", (0.35, radius_mm * 1.3, 0.4), (location_mm[0], location_mm[1], location_mm[2] + head_mm), mats.chip)
    return head


def memory_module(prefix, center_mm, z_mm, mats, length_mm=69.6, height_mm=30.0, chips=4, angle_deg=0.0, heatspreader=None, pcb_tex=None, standing=False):
    """SO-DIMM (lying in its latch) or desktop DIMM (standing in its slot). Tagged 'ram'."""
    pcb_mat = mat_image(f"{prefix}_pcbmat", pcb_tex or pcb_texture("ram_pcb", seed=7), roughness=0.38, coat=0.5, bump_strength=0.05)
    contact_mat = mat_image(f"{prefix}_contactmat", contacts_texture("ram_contacts_" + str(int(length_mm)), 130), roughness=0.22, metallic=0.85)
    cx, cy = center_mm
    parts = []
    if standing:
        board = box(f"{prefix}_pcb", (length_mm, 1.2, height_mm), (cx, cy, z_mm + height_mm / 2), pcb_mat, group="ram")
        parts.append(board)
        parts.append(box(f"{prefix}_fingers", (length_mm * 0.96, 1.25, 3.2), (cx, cy, z_mm + 1.6), contact_mat, group="ram"))
        if heatspreader:
            for side in (-1, 1):
                parts.append(box(f"{prefix}_hs{side}", (length_mm + 1, 1.6, height_mm - 4), (cx, cy + side * 1.4, z_mm + height_mm / 2 + 2), heatspreader, bevel_mm=0.6, group="ram"))
            parts.append(box(f"{prefix}_hstop", (length_mm + 1, 4.4, 4.0), (cx, cy, z_mm + height_mm + 1.5), heatspreader, bevel_mm=1.2, group="ram"))
        else:
            for i in range(chips):
                x = cx - length_mm / 2 + (i + 0.5) * length_mm / chips
                for side in (-1, 1):
                    parts.append(box(f"{prefix}_chip{i}_{side}", (10.5, 1.0, 12.0), (x, cy + side * 1.1, z_mm + height_mm * 0.55), mats.chip, bevel_mm=0.2, group="ram"))
    else:
        board = box(f"{prefix}_pcb", (length_mm, height_mm, 1.0), (cx, cy, z_mm + 0.5), pcb_mat, group="ram")
        parts.append(board)
        parts.append(box(f"{prefix}_fingers", (length_mm * 0.96, 3.2, 1.05), (cx, cy - height_mm / 2 + 1.6, z_mm + 0.5), contact_mat, group="ram"))
        chip_mat = mat_image(f"{prefix}_chipmark", chip_marking_texture("ram_chip", "D8BPK\nM16G 4C3A\n2547"), roughness=0.6)
        for i in range(chips):
            x = cx - length_mm / 2 + (i + 0.5) * length_mm / chips
            parts.append(box(f"{prefix}_chip{i}", (11.0, 9.0, 1.1), (x, cy + 3.0, z_mm + 1.55), chip_mat, bevel_mm=0.25, group="ram"))
        parts.append(box(f"{prefix}_spd", (3.0, 3.0, 0.9), (cx + length_mm * 0.08, cy - 7.5, z_mm + 1.45), mats.chip, group="ram"))
        rng = random.Random(len(prefix))
        for k in range(26):
            x = cx - length_mm / 2 + 3 + k * (length_mm - 6) / 25
            box(f"{prefix}_cap{k}", (1.0, 0.5, 0.5), (x, cy - 5.0 + rng.uniform(-0.4, 0.4), z_mm + 1.25), mats.ceramic, group="ram")
    return rotate_group(parts, center_mm, angle_deg)


def m2_ssd(prefix, center_mm, z_mm, mats, length_mm=80.0, angle_deg=0.0, label=("NVMe SSD", "2 TB · PCIe 4.0 x4 · M.2 2280")):
    """M.2 2280 NVMe SSD with controller, DRAM, NAND, label and gold key-M connector. Tagged 'ssd'."""
    cx, cy = center_mm
    pcb_mat = mat_image(f"{prefix}_pcbmat", pcb_texture("ssd_pcb", base=(12, 12, 14), trace=(26, 26, 30), seed=3, dark=True), roughness=0.35, coat=0.6, bump_strength=0.04)
    contact_mat = mat_image(f"{prefix}_contacts", contacts_texture("m2_contacts", 67), roughness=0.22, metallic=0.85)
    label_mat = mat_image(f"{prefix}_labelmat", label_texture("ssd_label", list(label) + ["S/N 7F42C19A0D · Made in TW"], size_px=(1400, 380), bg=(18, 18, 20), fg=(225, 228, 232), accent=(0, 170, 210)), roughness=0.4)
    parts = [box(f"{prefix}_pcb", (length_mm, 22.0, 0.8), (cx, cy, z_mm + 0.4), pcb_mat, group="ssd")]
    parts.append(box(f"{prefix}_fingers", (4.0, 19.0, 0.85), (cx - length_mm / 2 + 2.0, cy, z_mm + 0.4), contact_mat, group="ssd"))
    parts.append(box(f"{prefix}_controller", (11.5, 11.5, 1.2), (cx - length_mm / 2 + 16, cy, z_mm + 1.4), mats.chip, bevel_mm=0.3, group="ssd"))
    parts.append(box(f"{prefix}_dram", (9.0, 13.0, 1.0), (cx - length_mm / 2 + 30, cy, z_mm + 1.3), mats.chip, bevel_mm=0.25, group="ssd"))
    for i in range(2):
        parts.append(box(f"{prefix}_nand{i}", (14.0, 18.0, 1.3), (cx - length_mm / 2 + 47 + i * 19, cy, z_mm + 1.45), mats.chip, bevel_mm=0.3, group="ssd"))
    parts.append(plane(f"{prefix}_label", (length_mm * 0.62, 20.0), (cx + length_mm * 0.12, cy, z_mm + 2.15), label_mat, group="ssd"))
    parts.append(box(f"{prefix}_notch", (3.2, 3.2, 0.9), (cx + length_mm / 2 - 1.6, cy, z_mm + 0.4), mats.gold, group="ssd"))
    return rotate_group(parts, center_mm, angle_deg)


def blower_fan(prefix, center_mm, z_mm, mats, radius_mm=30, blades=11, height_mm=6, housing=True):
    cx, cy = center_mm
    parts = []
    if housing:
        ring = cylinder(f"{prefix}_housing", radius_mm + 3, height_mm, (cx, cy, z_mm + height_mm / 2), mats.plastic_black, vertices=96)
        cut = cylinder(f"{prefix}_housing_cut", radius_mm + 1.2, height_mm * 2, (cx, cy, z_mm + height_mm / 2 + 1.0), mats.plastic_black, vertices=96)
        mod = ring.modifiers.new("cut", "BOOLEAN")
        mod.object = cut
        mod.operation = "DIFFERENCE"
        bpy.context.view_layer.objects.active = ring
        bpy.ops.object.modifier_apply(modifier="cut")
        bpy.data.objects.remove(cut, do_unlink=True)
        parts.append(ring)
        parts.append(cylinder(f"{prefix}_floor", radius_mm + 3, 0.8, (cx, cy, z_mm + 0.4), mats.plastic_black, vertices=96))
    hub = cylinder(f"{prefix}_hub", radius_mm * 0.35, height_mm + 0.4, (cx, cy, z_mm + height_mm / 2 + 0.3), mats.fan_blade, vertices=48, bevel_mm=0.6)
    parts.append(hub)
    for i in range(blades):
        angle = 360 * i / blades
        blade = box(f"{prefix}_blade{i}", (radius_mm * 0.62, 1.0, height_mm * 0.85), (cx, cy, z_mm + height_mm / 2 + 0.6), mats.fan_blade, bevel_mm=0.3)
        rad = math.radians(angle)
        blade.location.x = (cx + math.cos(rad) * radius_mm * 0.66) * MM
        blade.location.y = (cy + math.sin(rad) * radius_mm * 0.66) * MM
        blade.rotation_euler[2] = rad + math.radians(28)
        parts.append(blade)
    return parts


def heatsink_fins(prefix, center_mm, z_mm, size_mm, fin_count, mats, material=None, axis="x"):
    cx, cy = center_mm
    sx, sy, sz = size_mm
    parts = []
    for i in range(fin_count):
        if axis == "x":
            y = cy - sy / 2 + (i + 0.5) * sy / fin_count
            parts.append(box(f"{prefix}_fin{i}", (sx, 0.35, sz), (cx, y, z_mm + sz / 2), material or mats.alu, bevel_mm=0.1, segments=1))
        else:
            x = cx - sx / 2 + (i + 0.5) * sx / fin_count
            parts.append(box(f"{prefix}_fin{i}", (0.35, sy, sz), (x, cy, z_mm + sz / 2), material or mats.alu, bevel_mm=0.1, segments=1))
    return parts


def heatpipe(prefix, points_mm, radius_mm, z_mm, mats):
    """Flattened copper heat pipe along a polyline (curve with bevel)."""
    curve = bpy.data.curves.new(prefix, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = radius_mm * MM
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(points_mm) - 1)
    for point, (x, y) in zip(spline.points, points_mm):
        point.co = (x * MM, y * MM, z_mm * MM, 1)
    obj = bpy.data.objects.new(prefix, curve)
    obj.scale = (1, 1, 0.45)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mats.copper)
    return obj


# --- masks --------------------------------------------------------------------------------

def render_masks(scene, out_dir, groups=("ram", "ssd", "cpu")):
    """One white-on-black matte per component group, via flat Workbench object colours."""
    previous_engine = scene.render.engine
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "FLAT"
    shading.color_type = "OBJECT"
    shading.background_type = "WORLD"
    scene.display.render_aa = "16"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    world_backup = scene.world.node_tree.nodes["Background"].inputs["Color"].default_value[:]
    scene.world.color = (0, 0, 0)
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    camera_obj = scene.camera
    dof = camera_obj.data.dof.use_dof
    for group in groups:
        for obj in scene.objects:
            if obj.type in {"MESH", "CURVE"}:
                obj.color = (1, 1, 1, 1) if obj.get("pp_group") == group else (0, 0, 0, 1)
        scene.render.filepath = os.path.join(out_dir, f"mask-{group}.png")
        bpy.ops.render.render(write_still=True)
    scene.render.engine = previous_engine
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = world_backup
    camera_obj.data.dof.use_dof = dof
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


def render_beauty(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def group_empty(name, parts, location_mm=(0, 0, 0), rotation_deg=(0, 0, 0)):
    """Parent parts to an empty so a whole assembly can be placed/rotated (e.g. a board standing upright)."""
    empty = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(empty)
    for part in parts:
        part.parent = empty
    empty.location = (location_mm[0] * MM, location_mm[1] * MM, location_mm[2] * MM)
    empty.rotation_euler = [math.radians(a) for a in rotation_deg]
    return empty


def collect_new(before):
    """Objects created since `before` (a set of names) — used to gather an assembly's parts."""
    return [obj for obj in bpy.context.scene.objects if obj.name not in before]
