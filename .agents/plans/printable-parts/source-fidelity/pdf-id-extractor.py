"""Finite known-ID extraction from pdftotext output, including wrapped prefixes.

This does not replace the independent DOM/frozen-source exact-ID membership
check. It allocates a longer known identity's whole span before shorter keys,
so a line-wrapped suffix cannot masquerade as a duplicate of its prefix.
"""
import re
import unittest


def maximal_known_id_matches(keys, text):
    if len(keys) != len(set(keys)) or any(not key or any(ch.isspace() for ch in key) for key in keys):
        raise ValueError('expected distinct nonempty source IDs without whitespace')
    candidates = []
    for key in sorted(keys, key=lambda value: (-len(value), value)):
        pattern = r'(?<![A-Za-z0-9_/-])' + r'\s*'.join(map(re.escape, key)) + r'(?![A-Za-z0-9_/-])'
        candidates.extend((key, match.start(), match.end()) for match in re.finditer(pattern, text))
    selected = []
    for key, start, end in candidates:
        if not any(start < old_end and old_start < end for _, old_start, old_end in selected):
            selected.append((key, start, end))
    return {key: [(start, end) for actual, start, end in selected if actual == key] for key in keys}


def unique_known_ids(keys, text):
    matches = maximal_known_id_matches(keys, text)
    for key in keys:
        if len(matches[key]) != 1:
            raise ValueError(f'{key}: expected one occurrence, got {len(matches[key])}')
    return matches


class KnownIdTests(unittest.TestCase):
    short = 'buy/turret_screw_m3x10'
    longer = short + '_flat'

    def test_wrapped_prefixes_keep_both_source_ids(self):
        text = '☐ buy/turret_s\ncrew_m3x10\nPart A\n☐ buy/turret_s\ncrew_m3x10\n_flat\nPart B'
        result = unique_known_ids([self.short, self.longer], text)
        self.assertEqual([len(result[key]) for key in [self.short, self.longer]], [1, 1])
        self.assertLess(result[self.short][0][0], result[self.longer][0][0])
        self.assertEqual(result, unique_known_ids([self.longer, self.short], text))

    def test_second_wrapped_prefix_pair(self):
        keys = ['print/rig/pod', 'print/rig/pod_lid']
        result = unique_known_ids(keys, 'print/rig/pod\nPart A\nprint/rig/pod\n_lid\nPart B')
        self.assertTrue(all(len(result[key]) == 1 for key in keys))

    def test_real_short_id_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'got 2'):
            unique_known_ids([self.short, self.longer], self.short + '\nA\n' + self.longer + '\nB\n' + self.short)

    def test_missing_short_id_is_not_supplied_by_longer_prefix(self):
        with self.assertRaisesRegex(ValueError, 'got 0'):
            unique_known_ids([self.short, self.longer], self.short + '\n_flat\nPart B')

    def test_real_long_id_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'got 2'):
            unique_known_ids([self.short, self.longer], self.short + '\nA\n' + self.longer + '\nB\n' + self.longer)


if __name__ == '__main__':
    unittest.main()
