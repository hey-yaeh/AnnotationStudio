"""Build a blank manual project referencing the included real BVH sample.

No labels, segments or social-event judgments are fabricated by this script.
The historical automatic example remains a separate, unchanged project.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from annotationstudio.models import Project
from annotationstudio.ontology import WORKSPACE_CATEGORIES, category_info


def build():
    original = Project.load(ROOT / 'examples' / 'S004_I02_example.ocumo.json')
    project = Project(name='S004 · I02 · Annotation workspace')
    project.tracks.clear(); project.annotations.clear()
    project.assets = original.assets
    project.settings.update(original.settings)
    project.settings['project_note'] = (
        'Blank annotation workspace with real R01/R02 BVH sources. Generate motion proposals or annotate with the label lists. '
        'No human-reviewed events are supplied. World-coordinate alignment remains unverified. '
        'Use Oculo Studio gaze results as external references; no new gaze or face annotation tracks.')
    for workspace, categories in WORKSPACE_CATEGORIES.items():
        if workspace == 'Overview': continue
        for category in categories:
            if category == 'Motion Primitive':
                # One explicit anatomical track per actor and major part.
                # This same idempotent helper powers new projects and the
                # optional UI action for filling an older project's gaps.
                project.ensure_primitive_tracks()
                continue
            info = category_info(category)
            channel = info.get('default_channel', 'Full Body')
            roles = ['Both'] if info.get('actor_scope') == 'pair' else (['Scene'] if workspace == 'Review' else ['R01', 'R02'])
            for role in roles:
                extra = {'label_scope': 0}
                if role == 'Both': extra['participants'] = ['R01', 'R02']
                project.add_track(name=category, role=role, workspace=workspace,
                    category=category, channel=channel, body_parts=[channel], extra=extra)
    target = ROOT / 'examples' / 'S004_I02_manual.studio.json'
    project.save(target)
    print(f'Built {target.name}: {len(project.tracks)} tracks, {len(project.annotations)} annotations.')


if __name__ == '__main__': build()
