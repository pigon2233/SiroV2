"""Asset-only inspection and preview rendering; does not save scene changes."""
import bpy, json, os, math
from pathlib import Path
out=Path(__import__('sys').argv[__import__('sys').argv.index('--')+1]); out.mkdir(parents=True,exist_ok=True); s=bpy.context.scene
p=bpy.data.objects['HeadPivot']; frames=[]
for f in [1,18,36,54,72]:
 s.frame_set(f); frames.append({'frame':f,'rotation_degrees':[round(math.degrees(v),3) for v in p.rotation_euler]})
assert frames[1]['rotation_degrees'] != frames[3]['rotation_degrees']
dg=bpy.context.evaluated_depsgraph_get(); triangles=0
for o in s.objects:
 if o.type=='MESH' and not o.hide_render:
  me=o.evaluated_get(dg).to_mesh();me.calc_loop_triangles();triangles+=len(me.loop_triangles);o.evaluated_get(dg).to_mesh_clear()
report={'blender':bpy.app.version_string,'objects':len(s.objects),'visible_evaluated_triangles':triangles,'fps':s.render.fps,'frame_start':s.frame_start,'frame_end':s.frame_end,'keyframe_readback':frames,'armatures':sum(o.type=='ARMATURE' for o in s.objects),'preview_render_frames':list(range(1,73,6))}
(out/'inspection.json').write_text(json.dumps(report,indent=2)+'\n')
s.render.resolution_x=s.render.resolution_y=384;s.cycles.samples=8
(out/'frames').mkdir(exist_ok=True)
for f in range(1,73,6):
 s.frame_set(f);s.render.filepath=str(out/'frames'/f'{f:03}.png');bpy.ops.render.render(write_still=True)
print('INSPECTION_AND_PREVIEW_DONE')
