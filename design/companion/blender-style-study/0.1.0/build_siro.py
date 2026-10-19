# SIRO anime bust style study. Blender 4.5 LTS, headless:
#   blender -b -P build_siro.py -- --output /path/to/out
# Z up, face toward -Y. Preview only: not a VRM, no MToon, no physics.
import bpy, bmesh, sys, os, math, argparse
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(); ap.add_argument("--output", default="/tmp/siro-3d-prototype/out")
OUT = os.path.abspath(ap.parse_args(argv).output); os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene

def mat(name, rgb, rough=0.8, emit=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.15
    b.inputs["Emission Color"].default_value = (*rgb, 1)
    b.inputs["Emission Strength"].default_value = emit
    return m

SKIN = mat("Skin", (0.97, 0.85, 0.76))
HAIR = mat("Hair", (0.78, 0.79, 0.82), 0.5); HAIRD = mat("HairShadow", (0.62, 0.64, 0.70), 0.6)
EYEW = mat("EyeWhite", (0.97, 0.97, 0.96)); IRIS = mat("Iris", (0.10, 0.45, 0.45), 0.3)
PUPIL = mat("Pupil", (0.03, 0.10, 0.12)); HL = mat("Highlight", (1, 1, 1), emit=1.5)
LASH = mat("Lash", (0.12, 0.10, 0.12)); BROW = mat("Brow", (0.48, 0.46, 0.50))
LIP = mat("Mouth", (0.62, 0.36, 0.35)); CLIP = mat("HairClip", (0.09, 0.42, 0.45), 0.35)
CARD = mat("Cardigan", (0.90, 0.85, 0.72)); TOP = mat("InnerTop", (0.55, 0.63, 0.76))

def obj(name, mesh, m, parent=None, smooth=True):
    o = bpy.data.objects.new(name, mesh); scn.collection.objects.link(o)
    o.data.materials.append(m); o.parent = parent
    if smooth:
        for p in o.data.polygons: p.use_smooth = True
    return o

def sphere(name, m, loc, scale, parent=None, seg=48, ring=32):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    bm.to_mesh(me); bm.free()
    o = obj(name, me, m, parent); o.location = loc; o.scale = scale; return o

def sub(o, lv=2):
    s = o.modifiers.new("Sub", "SUBSURF"); s.levels = lv; s.render_levels = lv

def ribbon(name, pts, widths, m, parent, thick=0.003, normal=Vector((0, -1, 0)), normals=None):
    """Tapered swept lock: centre polyline pts, per-point half widths, facing normal(s)."""
    me = bpy.data.meshes.new(name); bm = bmesh.new(); rows = []
    for i, p in enumerate(pts):
        p = Vector(p); t = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        side = t.cross(normals[i] if normals else normal).normalized() * widths[i]
        rows.append([bm.verts.new(p - side), bm.verts.new(p), bm.verts.new(p + side)])
    for a, b in zip(rows, rows[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0])); bm.faces.new((a[1], a[2], b[2], b[1]))
    bm.to_mesh(me); bm.free()
    o = obj(name, me, m, parent)
    s = o.modifiers.new("Thick", "SOLIDIFY"); s.thickness = thick; s.offset = 0
    sub(o, 2); return o

def stroke(name, pts, m, parent, bevel=0.004):
    """Thin stroke (lash/brow/mouth); y is later projected onto the face."""
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER"); sp.bezier_points.add(len(pts) - 1)
    for bp, (p, r) in zip(sp.bezier_points, pts):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = "AUTO"; bp.radius = r
    cu.bevel_depth = bevel; cu.bevel_resolution = 2
    o = bpy.data.objects.new(name, cu); scn.collection.objects.link(o)
    o.data.materials.append(m); o.parent = parent; return o

# ---- body (not parented to head) ----
sphere("Torso", TOP, (0, 0.02, -0.42), (0.36, 0.20, 0.30))
for sx in (-1, 1):   # open cardigan front
    c = sphere("Cardigan", CARD, (sx * 0.17, 0.02, -0.44), (0.25, 0.215, 0.30))
    cut = sphere(c.name + "_cut", TOP, (0, -0.2, -0.32), (0.09, 0.2, 0.22))
    cut.hide_render = cut.hide_viewport = True
    b = c.modifiers.new("Open", "BOOLEAN"); b.object = cut; b.operation = "DIFFERENCE"
sphere("Neck", SKIN, (0, 0.02, -0.12), (0.055, 0.055, 0.14))
sphere("Collar", SKIN, (0, -0.03, -0.20), (0.11, 0.06, 0.05))

# ---- head ----
pivot = bpy.data.objects.new("HeadPivot", None); scn.collection.objects.link(pivot)
head = sphere("Head", SKIN, (0, 0, 0.17), (0.145, 0.155, 0.17), pivot)
for v in head.data.vertices:               # sculpt in local space
    x, y, z = v.co
    if z < 0: v.co.z *= 1.22; v.co.x *= 1 - 0.36 * (-z) ** 1.6; v.co.y *= 1 - 0.18 * (-z)  # round, defined chin
    if y < 0:
        v.co.y *= 0.82 + 0.1 * abs(x)                                                      # flat facial plane
        wx, wz = v.co.x * 0.145, 0.17 + v.co.z * 0.17                                      # modest nose
        v.co.y -= (0.02 / 0.155) * math.exp(-(wx / 0.022) ** 2 - ((wz - 0.11) / 0.035) ** 2)
sub(head, 2)
for sx in (-1, 1):
    sphere("Ear", SKIN, (sx * 0.142, 0.01, 0.15), (0.018, 0.03, 0.04), pivot, 16, 12)

# ---- face decals (positions in XZ; depth comes from projection) ----
decals, strokes = [], []
for sx in (-1, 1):
    ex, ez, rz = sx * 0.055, 0.155, -sx * 0.32
    for nm, m, loc, sc, off in (("EyeWhite", EYEW, (ex, 0, ez), (0.034, 0.004, 0.022), 0.0004),
                                ("Iris", IRIS, (ex + sx * 0.003, 0, ez - 0.002), (0.019, 0.002, 0.023), 0.0008),
                                ("Pupil", PUPIL, (ex + sx * 0.003, 0, ez), (0.009, 0.001, 0.012), 0.0012),
                                ("Highlight", HL, (ex - sx * 0.004 + 0.004, 0, ez + 0.009), (0.004, 0.001, 0.005), 0.0015)):
        o = sphere(nm, m, loc, sc, pivot, 32, 12); o.rotation_euler.z = rz; decals.append((o, off))
    strokes += [stroke("UpperLash", [((ex - sx * 0.036, 0, ez - 0.002), 1.3), ((ex - sx * 0.01, 0, ez + 0.020), 1.6),
                                     ((ex + sx * 0.022, 0, ez + 0.020), 1.6), ((ex + sx * 0.040, 0, ez + 0.006), 0.6)], LASH, pivot, 0.0035),
                stroke("LowerLine", [((ex - sx * 0.02, 0, ez - 0.021), 0.3), ((ex + sx * 0.02, 0, ez - 0.019), 0.5)], LASH, pivot, 0.002),
                stroke("Brow", [((ex - sx * 0.03, 0, ez + 0.042), 0.5), ((ex, 0, ez + 0.050), 0.9),
                                ((ex + sx * 0.035, 0, ez + 0.044), 0.3)], BROW, pivot, 0.0025)]
strokes.append(stroke("Mouth", [((-0.016, 0, 0.058), 0.3), ((-0.006, 0, 0.0545), 1.0), ((0.006, 0, 0.0545), 1.0),
                                ((0.016, 0, 0.058), 0.3)], LIP, pivot, 0.0022))

# project decals onto the evaluated head front surface (pivot is identity at build time)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); he = head.evaluated_get(dg)
hm = head.matrix_world; hinv = hm.inverted(); hdir = (hinv.to_3x3() @ Vector((0, 1, 0))).normalized()
def face_y(x, z):
    ok, loc, _, _ = he.ray_cast(hinv @ Vector((x, -1, z)), hdir)
    return (hm @ loc).y if ok else -0.12
for o, off in decals:
    mw = o.matrix_world.copy()
    for v in o.data.vertices:
        w = mw @ v.co; w.y = face_y(w.x, w.z) - off; v.co = w
    o.location, o.rotation_euler, o.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    o.visible_shadow = False
for o in strokes:
    for bp in o.data.splines[0].bezier_points:
        bp.co.y = face_y(bp.co.x, bp.co.z) - 0.0015
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    o.visible_shadow = False

# ---- hair cap: ring surface crown -> bob, open front wedge below z .22 ----
rings = [(0.37, 0.015, 0.015), (0.35, 0.09, 0.10), (0.30, 0.145, 0.15), (0.23, 0.166, 0.17),
         (0.12, 0.17, 0.17), (0.01, 0.16, 0.15), (-0.07, 0.13, 0.13)]
N = 48; bm = bmesh.new(); grid = []
for z, rx, ry in rings:
    grid.append([bm.verts.new((rx * math.sin(2 * math.pi * i / N), -ry * math.cos(2 * math.pi * i / N) * (0.72 if math.cos(2 * math.pi * i / N)>0 else 1), z + (0.025 * math.cos(4 * math.pi * i / N) if abs(z-0.23)<0.001 and math.cos(2 * math.pi * i / N)>0 else 0))) for i in range(N)])
top = bm.verts.new((0, 0, 0.375))
for i in range(N): bm.faces.new((top, grid[0][(i + 1) % N], grid[0][i]))
for r in range(len(rings) - 1):
    for i in range(N):
        a = math.degrees(2 * math.pi * (i + 0.5) / N); a = a - 360 if a > 180 else a
        if rings[r + 1][0] < 0.22 and abs(a) < 68: continue
        bm.faces.new((grid[r][i], grid[r][(i + 1) % N], grid[r + 1][(i + 1) % N], grid[r + 1][i]))
me = bpy.data.meshes.new("HairCap"); bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); bm.to_mesh(me); bm.free()
cap = obj("HairCap", me, HAIR, pivot)
s = cap.modifiers.new("Thick", "SOLIDIFY"); s.thickness = 0.006; s.offset = 0
sub(cap, 2)

# back/side locks following the cap from the crown (slightly outside it)
for k in range(18):
    a = math.radians(68 + k * (224 / 17)); sa, ca = math.sin(a), -math.cos(a)
    curl = 0.012 if k % 2 else -0.01
    prof = [(0.35, 0.065), (0.29, 0.145), (0.17, 0.173), (0.03, 0.17), (-0.06 + 0.015 * ((k * 7) % 3 - 1), 0.14 + curl)]
    pts = [(sa * (r + 0.008), ca * (r + 0.008), z) for z, r in prof]
    ribbon(f"BobLock{k:02d}", pts, [0.014, 0.028, 0.03, 0.025, 0.001], HAIR if k % 4 else HAIRD,
           pivot, 0.003, normals=[Vector((sa, ca, 0))] * 5)
# layered asymmetric fringe from a crown parting at x=.025
root = Vector((0.025, -0.06, 0.36))
for j, (xt, zt) in enumerate(((-0.125, 0.14), (-0.10, 0.19), (-0.075, 0.22), (-0.035, 0.245), (0.085, 0.22), (0.13, 0.16))):
    yt = -0.16 + 0.6 * abs(xt)
    lx = lambda f: root.x + (xt - root.x) * f
    pts = [root, (lx(0.3), -0.15, 0.30), (lx(0.6), -0.17 + 0.3 * abs(lx(0.6)), 0.26),
           (lx(0.85), (yt - 0.165) / 2 + 0.002, (0.26 + zt) / 2), (xt, yt, zt)]
    ribbon(f"Fringe{j}", pts, [0.006, 0.02, 0.022, 0.014, 0.001], HAIR if j % 3 else HAIRD,
           pivot, 0.004, Vector((xt * 4, -1, 0)))
for sx in (-1, 1):                   # thin face-framing side locks
    pts = [(sx * 0.13, -0.09, 0.27), (sx * 0.15, -0.10, 0.17), (sx * 0.145, -0.095, 0.06), (sx * 0.13, -0.08, -0.04)]
    ribbon("SideLock", pts, [0.022, 0.026, 0.018, 0.002], HAIR, pivot, 0.004, Vector((sx, -0.4, 0)))
# rectangular teal hair clip on her LEFT (+X)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
for v in bm.verts: v.co = Vector((v.co.x * 0.025, v.co.y * 0.005, v.co.z * 0.01))
me = bpy.data.meshes.new("HairClip"); bm.to_mesh(me); bm.free()
clip = obj("HairClip", me, CLIP, pivot, smooth=False)
clip.location = (0.13, -0.115, 0.28); clip.rotation_euler = (0, math.radians(-35), math.radians(-25))
bv = clip.modifiers.new("Bevel", "BEVEL"); bv.width = 0.002; bv.segments = 2

# ---- head-turn animation ----
scn.frame_start, scn.frame_end = 1, 72
for f, rz, rx in ((1, 0, 0), (18, 30, -3), (36, 0, 0), (54, -30, 3), (72, 0, 0)):
    pivot.rotation_euler = (math.radians(rx), 0, math.radians(rz)); pivot.keyframe_insert("rotation_euler", frame=f)
scn.frame_set(1)

# ---- light, camera, render ----
w = bpy.data.worlds.new("W"); scn.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.96, 0.95, 0.92, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
def light(name, rot, e):
    o = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN")); o.data.energy = e; o.data.angle = 0.35
    scn.collection.objects.link(o); o.rotation_euler = [math.radians(a) for a in rot]
light("Key", (55, 0, -30), 2.0); light("Fill", (70, 0, 50), 0.3)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); scn.collection.objects.link(cam); scn.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 0.72
scn.render.engine = "CYCLES"; scn.cycles.device = "CPU"; scn.cycles.samples = 16; scn.cycles.use_denoising = True
scn.render.resolution_x = scn.render.resolution_y = 768
scn.view_settings.view_transform = "AgX"; scn.view_settings.exposure = 0.0; scn.view_settings.look = "AgX - Medium High Contrast"
target = Vector((0, 0, 0.10))
for fname, ang in (("front", 0), ("three-quarter", 35), ("profile", 90)):
    a = math.radians(ang); cam.location = target + Vector((math.sin(a) * 3, -math.cos(a) * 3, 0))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = os.path.join(OUT, fname + ".png"); bpy.ops.render.render(write_still=True)
cam.location = target + Vector((0, -3, 0)); cam.rotation_euler = (math.radians(90), 0, 0)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "siro-style.blend"))
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "siro-style.glb"), export_format="GLB",
                          export_apply=True, export_animations=True, use_visible=True, use_renderable=True)
with open(os.path.join(OUT, "README.md"), "w") as fh:
    fh.write("# SIRO 3D style study\n\nPreview bust only. GLB is a plain glTF preview, NOT a valid VRM: no humanoid "
             "skeleton, no MToon extension, no spring-bone physics, no blendshapes, no outlines. Principled base "
             "colours and emission transfer; Cycles lighting and color management do not. Face decals are baked flat onto "
             "the head surface. Head turn is an object keyframe on HeadPivot (frames 1-72). Mood study, not an exact "
             "likeness.\n")
print("SIRO done:", OUT)
