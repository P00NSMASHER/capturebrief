"""CSS contract checks; browser geometry is verified separately in offline QA."""
from pathlib import Path
import unittest


class PublicLayoutContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = Path('assets/v5.css').read_text(encoding='utf-8')

    def test_evidence_grid_can_shrink_below_hash_intrinsic_width(self):
        self.assertIn('.evidence-sample .watch-flow{grid-template-columns:repeat(4,minmax(0,1fr))}', self.css)
        self.assertIn('.evidence-sample .watch-flow>div{min-width:0;overflow-wrap:anywhere}', self.css)

    def test_tablet_and_phone_tracks_are_explicit(self):
        self.assertIn('@media(max-width:960px){.evidence-sample .watch-flow{grid-template-columns:repeat(2,minmax(0,1fr))}}', self.css)
        self.assertIn('@media(max-width:720px){.evidence-sample .watch-flow{grid-template-columns:minmax(0,1fr)}}', self.css)

    def test_hashes_wrap_instead_of_being_hidden_or_truncated(self):
        self.assertIn('.evidence-sample .watch-flow code{display:block;white-space:normal;overflow-wrap:anywhere;', self.css)
        self.assertIn('.evidence-sample .mini-meta{overflow-wrap:anywhere}', self.css)
        guard = self.css.split('/* Decision Evidence:', 1)[1]
        self.assertNotIn('overflow:hidden', guard)
        self.assertNotIn('text-overflow:ellipsis', guard)


if __name__ == '__main__':
    unittest.main()
