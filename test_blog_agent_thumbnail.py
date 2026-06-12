#!/usr/bin/env python3
"""Tests for Codex thumbnail generation integration."""

import subprocess
import tempfile
import unittest
from pathlib import Path

import blog_agent


class ThumbnailGenerationTests(unittest.TestCase):
    def test_parser_accepts_no_thumbnail_flag(self):
        parser = blog_agent.build_parser()

        args = parser.parse_args(["https://example.com/post", "--no-thumbnail"])

        self.assertTrue(args.no_thumbnail)

    def test_codex_thumbnail_generation_updates_qmd_image_on_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            output_dir = workspace / "output"
            output_dir.mkdir()
            qmd_path = output_dir / "202606121200.qmd"
            qmd_path.write_text(
                """---
title: "Test Post"
description: "A post about AI agents."
image: https://picsum.photos/id/92/200
---

本文です。
""",
                encoding="utf-8",
            )
            calls = []

            def fake_runner(cmd, **kwargs):
                calls.append((cmd, kwargs))
                if cmd[:2] == ["codex", "exec"]:
                    (output_dir / "202606121200.png").write_bytes(b"png")
                elif cmd[:2] == ["sips", "-g"]:
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout=(
                            f"{output_dir / '202606121200.png'}\n"
                            "  pixelWidth: 1200\n"
                            "  pixelHeight: 675\n"
                        ),
                        stderr="",
                    )
                return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

            generated = blog_agent.generate_thumbnail_with_codex(
                qmd_path,
                workspace_dir=workspace,
                runner=fake_runner,
                printer=lambda message: None,
            )

            self.assertTrue(generated)
            self.assertEqual(len(calls), 4)
            cmd, kwargs = calls[0]
            self.assertEqual(cmd[:2], ["codex", "exec"])
            self.assertIn("-C", cmd)
            self.assertEqual(cmd[cmd.index("-C") + 1], str(workspace))
            self.assertNotIn("--ask-for-approval", cmd)
            self.assertEqual(cmd[-1], "-")
            self.assertIn(str(qmd_path), kwargs["input"])
            self.assertIn("output/202606121200.png", kwargs["input"])
            self.assertIn("1:1", kwargs["input"])
            self.assertNotIn("16:9", kwargs["input"])
            self.assertIn("scientific journal cover", kwargs["input"])
            self.assertIn("Nature or Science", kwargs["input"])
            self.assertIn("research editorial illustration", kwargs["input"])
            self.assertIn(
                "image: 202606121200.png",
                qmd_path.read_text(encoding="utf-8"),
            )
            resize_cmd, _ = calls[1]
            self.assertEqual(
                resize_cmd,
                [
                    "sips",
                    "-g",
                    "pixelWidth",
                    "-g",
                    "pixelHeight",
                    str(output_dir / "202606121200.png"),
                ],
            )
            crop_cmd, _ = calls[2]
            self.assertEqual(
                crop_cmd,
                [
                    "sips",
                    "--cropToHeightWidth",
                    "675",
                    "675",
                    str(output_dir / "202606121200.png"),
                ],
            )
            resize_cmd, _ = calls[3]
            self.assertEqual(
                resize_cmd,
                [
                    "sips",
                    "-z",
                    "600",
                    "600",
                    str(output_dir / "202606121200.png"),
                ],
            )

    def test_codex_thumbnail_generation_keeps_qmd_image_when_codex_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            output_dir = workspace / "output"
            output_dir.mkdir()
            qmd_path = output_dir / "202606121201.qmd"
            original_qmd = """---
title: "Test Post"
description: "A post about AI agents."
image: https://picsum.photos/id/92/200
---

本文です。
"""
            qmd_path.write_text(original_qmd, encoding="utf-8")

            def fake_runner(cmd, **kwargs):
                return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="failed")

            generated = blog_agent.generate_thumbnail_with_codex(
                qmd_path,
                workspace_dir=workspace,
                runner=fake_runner,
                printer=lambda message: None,
            )

            self.assertFalse(generated)
            self.assertEqual(original_qmd, qmd_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
