#!/usr/bin/env python3
"""Artifact faults must fail before the static study video is published."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('study_check', Path(__file__).with_name('check-study-media.py'))
check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)


class StudyMedia(unittest.TestCase):
    def test_real_video_and_sources(self):
        self.assertEqual(check.validate()['decoded_frames'], 288)

    def test_frozen_frame_negative_control(self):
        with self.assertRaisesRegex(ValueError, 'Frozen model'):
            check.moving_model(bytes(range(256)) * 20, bytes(range(256)) * 20)

    def test_corruptions(self):
        with tempfile.TemporaryDirectory(prefix='gyropup-study-faults-') as tmp:
            root = Path(tmp)
            paths = [check.SUMMARY, 'exports/leg/fea/media.json', 'tools/render-hip-frame-e1.py']
            paths += [p.relative_to(check.ROOT).as_posix() for p in (check.ROOT / check.MEDIA).iterdir() if p.is_file()]
            for path in paths:
                target = root / path; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(check.ROOT / path, target)
            def fault(path, mutate, pattern):
                target = root / path; original = target.read_bytes()
                try:
                    mutate(target)
                    with self.assertRaisesRegex(ValueError, pattern): check.validate(root, decode=False)
                finally: target.write_bytes(original)
            def edit(fn):
                def mutate(path):
                    data = json.loads(path.read_text()); fn(data); path.write_text(json.dumps(data))
                return mutate
            fault(check.SUMMARY, edit(lambda d: d['results'].append({'part':'different','case':'E1'})), 'Stale report binding')
            fault('tools/render-hip-frame-e1.py', lambda p: p.write_bytes(p.read_bytes()+b'\n# changed\n'), 'Stale animation source')
            fault(check.MEDIA+'hip_frame-E1.json', lambda p: p.write_bytes(p.read_bytes()+b'\n'), 'Field bytes changed')
            fault(check.MEDIA+'hip-frame-e1.mp4', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault(check.MEDIA+'hip-frame-e1-poster.png', lambda p: p.write_bytes(p.read_bytes()[:-1]), 'Rendered artifact changed')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1']['recorded'].update(safety_factor=2.5)), 'Media index differs')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1'].update(transient_simulation=True)), 'Static evidence mislabeled')
            fault('exports/leg/fea/media.json', edit(lambda d: d['cases']['hip_frame/E1'].update(video='elsewhere.mp4')), 'Media index paths differ')
            fault(check.MEDIA+'video-receipt.json', edit(lambda d: d['timeline'][144].update(load_factor=2)), 'Presentation extrapolates')
            fault(check.MEDIA+'video-receipt.json', edit(lambda d: d['outputs'].pop(check.MEDIA+'hip-frame-e1-poster.png')), 'Incomplete rendered artifacts')
            fault(check.MEDIA+'field-receipt.json', edit(lambda d: d.update(qualified_for_manufacture=True)), 'Static evidence cannot qualify')


if __name__ == '__main__': unittest.main()
