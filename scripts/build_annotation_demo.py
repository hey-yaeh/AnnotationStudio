"""Create a deterministic, explicitly synthetic UI demo (no OCUMO labels)."""
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotationstudio.models import Project
from annotationstudio.speech_structure import build_speech_structure,apply_speech_structure

NS=uuid.UUID('584336d4-3020-4f9b-a3fb-51e0cc604581')
def uid(value):return str(uuid.uuid5(NS,value))


def build():
    p=Project('Synthetic annotation demo — NOT OCUMO reference labels')
    p.tracks=[]; p.annotations=[]
    p.settings.update(duration_s=18.,manual_duration_s=18.,synthetic_demo=True,
        project_note='Synthetic times, speech and sofa/table relationships for software demonstration only. '
                     'No recorded audio, video or motion is attached. No scientific accuracy is demonstrated.')
    p.add_object('Demo sofa','sofa',id='sofa_01',notes='Illustrative object; no real scene geometry.')
    p.add_object('Demo table','table',id='table_01',notes='Illustrative object; no real scene geometry.')
    tracks={}
    for role in ('R01','R02'):
        tracks[(role,'Speaking')]=p.add_track(name='Speaking',id=uid(role+'speech'),role=role,
            category='Speaking',channel='Speech')
    for role,category,name,channel in [('R01','Body Posture','Seated posture','Full Body'),
            ('R01','Action / HOI','Sofa support','Root'),('R01','Action / HOI','Right hand on table','Right Hand')]:
        tracks[(role,name)]=p.add_track(name=name,id=uid(role+name),role=role,category=category,channel=channel)

    def add(key,start,end,label,tag,**attributes):
        t=tracks[key]
        return p.add_annotation(start,end,id=uid(tag),track_id=t.id,role=t.role,category=t.category,
            channel=t.channel,label=label,status='approved',source='demo:synthetic',reviewer='DEMO',
            notes='Synthetic demonstration record; not a real participant annotation.',
            attributes={'synthetic_demo':True,**attributes})
    for role,spans in [('R01',[(2.,4.),(4.2,6.),(9.,12.)]),('R02',[(6.25,8.5),(11.5,13.)])]:
        for i,(start,end) in enumerate(spans):add((role,'Speaking'),start,end,'Speaking',f'{role}speaking{i}')
    add(('R01','Seated posture'),0.,18.,'sitting','sitting')
    add(('R01','Sofa support'),0.,18.,'sit on object','sofa',object_id='sofa_01',effector='Pelvis / seat')
    add(('R01','Right hand on table'),3.,11.,'rest on object','table',object_id='table_01',effector='Right hand')
    proposed,report=build_speech_structure(p,attribution_confirmed=True,merge_gap_s=.3)
    apply_speech_structure(p,proposed,report)
    p.save(ROOT/'examples/annotation_schema_demo.studio.json')
    print(f'Synthetic demo: {len(p.tracks)} tracks, {len(p.annotations)} illustrative records. No recorded media.')
    return p

if __name__=='__main__':build()
