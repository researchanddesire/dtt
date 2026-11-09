"""Read a DTT 3MF back, check every part sits on its plate, and render the plates.

Usage: python3 check_3mf.py <file.3mf> <out dir>
"""
import zipfile,sys,re,numpy as np
import xml.etree.ElementTree as ET
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import trimesh
f=sys.argv[1]; z=zipfile.ZipFile(f)
N='{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
objs={}
for o in ET.fromstring(z.read('3D/Objects/object_1.model')).iter(N+'object'):
  v=np.array([[float(x.get(k)) for k in 'xyz'] for x in o.iter(N+'vertex')])
  t=np.array([[int(x.get(k)) for k in ('v1','v2','v3')] for x in o.iter(N+'triangle')])
  objs[o.get('id')]=trimesh.Trimesh(v,t,process=False)
cfg=ET.fromstring(z.read('Metadata/model_settings.config'))
fil={p.get('id'):int(p.find("metadata[@key='extruder']").get('value')) for p in cfg.iter('part')}
pname={p.get('id'):p.find("metadata[@key='name']").get('value') for p in cfg.iter('part')}
plate={}
for pl in cfg.iter('plate'):
  n=int(pl.find("metadata[@key='plater_id']").get('value'))
  for mi in pl.iter('model_instance'): plate[mi.find("metadata[@key='object_id']").get('value')]=n
root=ET.fromstring(z.read('3D/3dmodel.model'))
comps={o.get('id'):[c.get('objectid') for c in o.iter(N+'component')] for o in root.iter(N+'object')}
col={1:(0.09,0.42,0.93),2:(0.95,0.95,0.95),3:(0.30,0.30,0.32)}
scenes={}
for it in root.iter(N+'item'):
  oid=it.get('objectid'); T=[float(x) for x in it.get('transform').split()]; tx,ty,tz=T[9:]
  n=plate[oid]; ox=(n-1)*307.2
  zmin=min(objs[c].bounds[0][2] for c in comps[oid])
  for c in comps[oid]:
    m=objs[c].copy(); m.apply_translation([tx-ox,ty,tz])
    b=m.bounds
    print(f"plate {n} {pname[c]:24s} fil {fil[c]} wt={m.is_watertight} x {b[0][0]:.1f}..{b[1][0]:.1f} y {b[0][1]:.1f}..{b[1][1]:.1f} z {b[0][2]:.2f}..{b[1][2]:.2f}")
    assert 0<=b[0][0] and b[1][0]<=256 and 0<=b[0][1] and b[1][1]<=256
    scenes.setdefault(n,[]).append((m,col[fil[c]]))
  assert abs(zmin)<1e-6
for n,parts in scenes.items():
  fig=plt.figure(figsize=(9,7),dpi=150); ax=fig.add_subplot(projection='3d')
  ax.plot([0,256,256,0,0],[0,0,256,256,0],[0,0,0,0,0],color='0.6',lw=1)
  tris=[];fcs=[]
  L=np.array([0.3,-0.5,0.8]); L/=np.linalg.norm(L)
  for m,c in parts:
    sh=0.35+0.65*np.clip(m.face_normals@L,0,1)
    fc=np.clip(np.array(c)[None,:]*sh[:,None]+0.05*sh[:,None],0,1)
    tris.append(m.triangles);fcs.append(fc)
  ax.add_collection3d(Poly3DCollection(np.concatenate(tris),facecolors=np.concatenate(fcs),edgecolor='none'))
  for g in range(0,257,32):
    ax.plot([g,g],[0,256],[0,0],color='0.85',lw=0.5);ax.plot([0,256],[g,g],[0,0],color='0.85',lw=0.5)
  ax.set_xlim(0,256);ax.set_ylim(0,256);ax.set_zlim(0,60);ax.set_box_aspect((256,256,60))
  ax.view_init(elev=38,azim=-58);ax.set_axis_off()
  ax.set_title(["Plate 1: case, flat cap, suction-cup cap, switch cover","Plate 2: sleeve backplate, wall bracket"][n-1], fontsize=11)
  plt.tight_layout(); plt.savefig(f"{sys.argv[2]}/Plate-{n}.png",bbox_inches='tight'); plt.close()
