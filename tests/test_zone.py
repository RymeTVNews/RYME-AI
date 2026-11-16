import unittest

from ryme_ai import zone


class ZoneTest(unittest.TestCase):
    def test_fractions_any_drag_direction(self):
        a = zone.selection_to_fractions(50, 25, 150, 75, 200, 100)
        b = zone.selection_to_fractions(150, 75, 50, 25, 200, 100)  # glissé à l'envers
        self.assertEqual(a, (0.25, 0.25, 0.75, 0.75))
        self.assertEqual(a, b)

    def test_clamped_to_image(self):
        self.assertEqual(zone.selection_to_fractions(-30, -30, 999, 999, 200, 100), (0.0, 0.0, 1.0, 1.0))

    def test_simple_click_is_ignored(self):
        self.assertIsNone(zone.selection_to_fractions(10, 10, 11, 11, 200, 100))
        self.assertIsNone(zone.selection_to_fractions(0, 0, 10, 10, 0, 0))

    def test_hint_format(self):
        hint = zone.format_hint("images/a.png", (0.1, 0.2, 0.5, 0.6), "ellipse")
        self.assertEqual(hint, "[zone : images/a.png | left=0.100 top=0.200 right=0.500 bottom=0.600 | ellipse]")

    def test_replace_hint_keeps_user_text_and_swaps_old_block(self):
        old = zone.format_hint("a.png", (0, 0, 0.5, 0.5))
        new = zone.format_hint("a.png", (0.5, 0.5, 1, 1))
        out = zone.replace_hint(f"{old} mets un chapeau", new)
        self.assertEqual(out, new + " mets un chapeau")
        self.assertEqual(zone.replace_hint("", new), new + " ")

    def test_hint_matches_tool_arguments(self):
        """Les valeurs du bloc sont directement utilisables par edit_image_zone."""
        import re
        hint = zone.format_hint("a.png", (0.25, 0.25, 0.75, 0.75))
        vals = {k: float(v) for k, v in re.findall(r"(left|top|right|bottom)=([0-9.]+)", hint)}
        from ryme_ai import images
        images.make_mask(100, 100, **vals)  # ne doit pas lever d'erreur


if __name__ == "__main__":
    unittest.main()
