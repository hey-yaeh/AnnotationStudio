from pathlib import Path
import csv
import json
import wave
import xml.etree.ElementTree as ET
import numpy as np
import pytest
from annotationstudio.bvh import BVHMotion, open_motion
from annotationstudio.models import Project, import_annotation_csv, export_csv, export_eaf
from annotationstudio.segmentation import SegmentationConfig, segment_motion, detect_phase_structures, detect_dyadic_coactivity
from annotationstudio.modalities import read_gaze_csv, read_aoi_csv, read_props, wav_envelope

BASE = Path(__file__).resolve().parent.parent

def test_bvh_sample_structure(private_samples):
    private_samples('S004_I02_R01_BVH.bvh')
    m=BVHMotion(BASE/'examples/S004_I02_R01_BVH.bvh')
    assert m.nframes==12808
    assert len(m.joints)==60
    assert m.frames.shape==(12808,183)
    assert abs(m.frame_time-.008333)<1e-7
    assert m.joint('RightHand') is not None
    pose=m.positions([0,1000,8000,12807])
    assert pose.shape==(4,60,3)
    assert np.isfinite(pose).all()
    assert 10<m.scale_hint()<100


def test_bvh_noncommuting_euler_order(tmp_path):
    # A 90-degree X then Z intrinsic BVH rotation is noncommutative.
    bvh='''HIERARCHY
ROOT Hips
{
 OFFSET 0 0 0
 CHANNELS 6 Xposition Yposition Zposition Xrotation Zrotation Yrotation
 JOINT Child
 {
 OFFSET 1 0 0
 CHANNELS 3 Xrotation Yrotation Zrotation
 End Site
 {
 OFFSET 1 0 0
 }
 }
}
MOTION
Frames: 1
Frame Time: 0.01
1 2 3 90 90 0 0 0 0
'''
    p=tmp_path/'toy.bvh';p.write_text(bvh)
    m=BVHMotion(p)
    pos=m.pose_at(0)
    from scipy.spatial.transform import Rotation
    desired=np.array([1,2,3])+Rotation.from_euler('XZY',[90,90,0],degrees=True).apply([1,0,0])
    assert np.allclose(pos[1],desired,atol=1e-5)


def test_graph_and_baseline_detect_kinematic_right_arm(private_samples):
    private_samples('S004_I02_R01_BVH.bvh')
    m=open_motion(BASE/'examples/S004_I02_R01_BVH.bvh')
    graph,_,_=segment_motion(m,'R01',SegmentationConfig(mode='graph'))
    baseline,_,_=segment_motion(m,'R01',SegmentationConfig(mode='velocity'))
    assert len(graph)>15 and len(baseline)>15
    assert any(a.channel=='Right Arm' and a.label=='raise right arm' and a.start_s<93 and a.end_s>88 for a in graph)
    assert any(a.channel=='Right Arm' and a.label=='lower right arm' and a.start_s<96 and a.end_s>93 for a in graph)
    assert all(a.status=='pending' and a.source.startswith('auto:') for a in graph)
    # There is no evaluated "ground truth" semantic F1 in this test.
    assert len(detect_phase_structures(graph))>0


def test_dyadic_coactivity_is_unverified(private_samples):
    private_samples('S004_I02_R01_BVH.bvh', 'S004_I02_R02_BVH.bvh')
    m1=BVHMotion(BASE/'examples/S004_I02_R01_BVH.bvh')
    m2=BVHMotion(BASE/'examples/S004_I02_R02_BVH.bvh')
    a,_,_=segment_motion(m1,'R01',SegmentationConfig(mode='graph'))
    b,_,_=segment_motion(m2,'R02',SegmentationConfig(mode='graph'))
    co=detect_dyadic_coactivity(a+b)
    assert len(co)>0
    assert all('unverified' in x.label and x.status=='pending' for x in co)
    assert all(x.role=='Both' and x.channel=='Dyadic' for x in co)


def test_import_stage2_and_project_roundtrip(tmp_path, private_samples):
    private_samples('S004_I02_stage2_annotation_template.csv', 'S004_I02_R01_BVH.bvh')
    ann=import_annotation_csv(BASE/'examples/S004_I02_stage2_annotation_template.csv')
    assert len(ann)==167
    assert all(a.valid() for a in ann)
    p=Project('Test session')
    p.add_asset('motion','R01',BASE/'examples/S004_I02_R01_BVH.bvh')
    p.annotations=ann[:6]
    out=tmp_path/'session.ocumo.json'
    p.save(out)
    again=Project.load(out)
    assert len(again.assets)==1 and len(again.annotations)==6
    assert Path(again.assets[0].path).exists()
    csvout=tmp_path/'out.csv';export_csv(again.annotations,csvout)
    assert len(import_annotation_csv(csvout))==6
    eaf=tmp_path/'out.eaf';export_eaf(again.annotations,eaf)
    root=ET.parse(eaf).getroot()
    assert len(root.findall('.//ALIGNABLE_ANNOTATION'))==6


def test_multimodal_imports(tmp_path):
    gp=tmp_path/'gaze.csv';gp.write_text('time_s,origin_x,origin_y,origin_z,dir_x,dir_y,dir_z\n0,0,0,0,1,0,0\n0.02,0,0,0,1,0,0\n')
    ray=read_gaze_csv(gp,'R01')
    assert ray.ray_at(.01) is not None
    assert ray.ray_at(4.) is None
    aoi=tmp_path/'aoi.csv';aoi.write_text('start_s,end_s,label\n1,2,Partner Face\n3,4,Partner Hand\n')
    assert read_aoi_csv(aoi,offset_s=.3)==[(1.3,2.3,'Partner Face'),(3.3,4.3,'Partner Hand')]
    props=tmp_path/'props.csv';props.write_text('time_s,prop_id,x,y,z\n0,Cup,1,2,3\n0.1,Cup,2,2,3\n')
    track=read_props(props)
    assert track.at(0).shape==(1,3)
    audio=tmp_path/'audio.wav';sr=16000
    values=(np.sin(2*np.pi*220*np.arange(sr)/sr)*.5*32767).astype(np.int16)
    with wave.open(str(audio),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(sr);out.writeframes(values.tobytes())
    t,amp=wav_envelope(audio)
    assert len(t)>100 and .8 < float(np.max(amp)) <= 1.


def test_sample_project_is_self_contained(private_samples):
    private_samples('S004_I02_example.ocumo.json', 'S004_I02_R01_BVH.bvh', 'S004_I02_R02_BVH.bvh')
    f=BASE/'examples/S004_I02_example.ocumo.json'
    p=Project.load(f)
    assert len(p.assets)==2
    assert all(Path(a.path).exists() for a in p.assets)
    assert len(p.annotations)==167
