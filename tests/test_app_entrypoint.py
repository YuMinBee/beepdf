from __future__ import annotations

import unittest


class FastAPIEntrypointTest(unittest.TestCase):
    def test_app_entrypoint_imports_when_fastapi_is_installed(self) -> None:
        try:
            from app.v2_main import app
        except ModuleNotFoundError as exc:
            if exc.name == "fastapi":
                self.skipTest("fastapi is not installed in this local environment")
            raise

        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertEqual(app.title, "BeePDF")
        self.assertIn("/health", paths)
        self.assertIn("/v2/documents/ingest", paths)
        self.assertIn("/v2/ask", paths)
        self.assertIn("/v2/study-kit", paths)
        self.assertIn("/v2/audio-script", paths)
        self.assertIn("/v2/concept-map", paths)


if __name__ == "__main__":
    unittest.main()


