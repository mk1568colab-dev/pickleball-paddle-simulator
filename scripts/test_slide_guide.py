import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest


class GuideTests(unittest.TestCase):
    def test_all_slides_and_boundaries(self):
        page = Path(__file__).resolve().parents[1] / "pages" / "10_Game_Big_Picture_Guide.py"
        with patch("utils.auth.require_authenticated_user"):
            app = AppTest.from_file(str(page))
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(app.button(key="slide_previous").disabled)
            for index in range(1, 8):
                app.button(key="slide_next").click().run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.session_state["kiki_big_picture_slide"], index)
            self.assertTrue(app.button(key="slide_next").disabled)
            app.button(key="slide_previous").click().run()
            self.assertEqual(app.session_state["kiki_big_picture_slide"], 6)


if __name__ == "__main__":
    unittest.main()
