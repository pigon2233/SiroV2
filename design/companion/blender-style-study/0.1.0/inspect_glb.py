import bpy, json,struct
from pathlib import Path
p=Path(__import__('sys').argv[__import__('sys').argv.index('--')+1])
b=p.read_bytes();magic,ver,total=struct.unpack_from('<4sII',b);n,kind=struct.unpack_from('<II',b,12);d=json.loads(b[20:20+n])
assert magic==b'glTF' and ver==2 and total==len(b)
assert d.get('animations') and not d.get('skins')
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(p))
pivot=bpy.data.objects.get('HeadPivot');assert pivot and pivot.animation_data
bpy.context.scene.frame_set(1);a=[list(r) for r in pivot.matrix_world];bpy.context.scene.frame_set(18);z=[list(r) for r in pivot.matrix_world];assert a!=z
r={'status':'imported_and_animation_readback_pass','glb_bytes':len(b),'nodes':len(d.get('nodes',[])),'meshes':len(d.get('meshes',[])),'animations':len(d.get('animations',[])),'skins':len(d.get('skins',[])),'extensions_used':d.get('extensionsUsed',[]),'imported_objects':len(bpy.context.scene.objects),'imported_head_matrix_frame_1':a,'imported_head_matrix_frame_18':z,'vrm':False,'runtime_playback_tested':False}
(p.parent/'glb-import.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
