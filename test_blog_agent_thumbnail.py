#!/usr/bin/env python3
"""Tests for Codex thumbnail generation integration."""

import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import blog_agent


class ThumbnailGenerationTests(unittest.TestCase):
    def test_parser_accepts_no_thumbnail_flag(self):
        parser = blog_agent.build_parser()

        args = parser.parse_args(["https://example.com/post", "--no-thumbnail"])

        self.assertTrue(args.no_thumbnail)

    def test_thumbnail_style_selection_uses_configured_distribution(self):
        cases = [
            (0.0, "Pablo Picasso"),
            (0.099999, "Pablo Picasso"),
            (0.1, "Claude Monet"),
            (0.2, "Paul Cézanne"),
            (0.399999, "Wassily Kandinsky"),
            (0.4, "Henri Matisse"),
            (0.8, "Joan Miró"),
            (0.999999, "Georgia O'Keeffe"),
        ]

        for random_value, expected_style in cases:
            with self.subTest(random_value=random_value):
                self.assertEqual(
                    blog_agent.select_thumbnail_style(lambda: random_value),
                    expected_style,
                )

    def test_thumbnail_style_selection_covers_full_roster(self):
        produced = {
            blog_agent.select_thumbnail_style(lambda v=value: v)
            for value in [i / len(blog_agent.THUMBNAIL_ARTIST_STYLES)
                          for i in range(len(blog_agent.THUMBNAIL_ARTIST_STYLES))]
        }

        self.assertEqual(produced, set(blog_agent.THUMBNAIL_ARTIST_STYLES))

    def test_thumbnail_prompt_includes_selected_artist_style_and_fresh_artifact_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            qmd_path = workspace / "output" / "202606121202.qmd"
            thumbnail_path = workspace / "output" / "202606121202.jpg"

            prompt = blog_agent.build_thumbnail_prompt(
                qmd_path,
                thumbnail_path,
                workspace,
                style_rng=lambda: 0.8,
            )

            self.assertIn("Generate the image in the style of Joan Miró", prompt)
            self.assertIn("Apply only the selected artist style", prompt)
            self.assertIn("fresh new ImageGen artifact", prompt)
            self.assertIn("created during this Codex run", prompt)
            self.assertIn("Do not reuse", prompt)
            self.assertIn("Do not convert or copy any pre-existing image", prompt)
            self.assertIn("do not leave it only as an inline preview", prompt)
            self.assertIn("explicitly authorizes the ImageGen CLI fallback", prompt)

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
            messages = []

            def fake_runner(cmd, **kwargs):
                calls.append((cmd, kwargs))
                if cmd[:2] == ["codex", "exec"]:
                    (output_dir / "202606121200.jpg").write_bytes(b"jpg")
                elif cmd[:2] == ["sips", "-g"]:
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout=(
                            f"{output_dir / '202606121200.jpg'}\n"
                            "  pixelWidth: 1200\n"
                            "  pixelHeight: 675\n"
                        ),
                        stderr="",
                    )
                return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

            generated = blog_agent.generate_thumbnail_with_codex(
                qmd_path,
                workspace_dir=workspace,
                style_rng=lambda: 0.4,
                runner=fake_runner,
                printer=messages.append,
            )

            self.assertTrue(generated)
            self.assertEqual(len(calls), 5)
            cmd, kwargs = calls[0]
            self.assertEqual(cmd[:2], ["codex", "exec"])
            self.assertIn("--json", cmd)
            self.assertIn("-C", cmd)
            self.assertEqual(cmd[cmd.index("-C") + 1], str(workspace))
            self.assertNotIn("--ask-for-approval", cmd)
            self.assertEqual(cmd[-1], "-")
            self.assertIn(str(qmd_path), kwargs["input"])
            self.assertIn("output/202606121200.jpg", kwargs["input"])
            self.assertIn("Save the final JPEG", kwargs["input"])
            self.assertIn("1:1", kwargs["input"])
            self.assertNotIn("16:9", kwargs["input"])
            self.assertIn("Generate the image in the style of Henri Matisse", kwargs["input"])
            self.assertIn("fresh new ImageGen artifact", kwargs["input"])
            self.assertIn("created during this Codex run", kwargs["input"])
            self.assertIn("Do not reuse", kwargs["input"])
            self.assertIn("Do not convert or copy any pre-existing image", kwargs["input"])
            self.assertIn(
                "image: 202606121200.jpg",
                qmd_path.read_text(encoding="utf-8"),
            )
            self.assertIn("artist_style = 'Henri Matisse'", messages)
            resize_cmd, _ = calls[1]
            self.assertEqual(
                resize_cmd,
                [
                    "sips",
                    "-g",
                    "pixelWidth",
                    "-g",
                    "pixelHeight",
                    str(output_dir / "202606121200.jpg"),
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
                    str(output_dir / "202606121200.jpg"),
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
                    str(output_dir / "202606121200.jpg"),
                ],
            )
            convert_cmd, _ = calls[4]
            self.assertEqual(
                convert_cmd,
                [
                    "sips",
                    "-s",
                    "format",
                    "jpeg",
                    str(output_dir / "202606121200.jpg"),
                    "--out",
                    str(output_dir / "202606121200.jpg"),
                ],
            )

    def test_codex_thumbnail_generation_recovers_imagegen_payload_from_session_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            output_dir = workspace / "output"
            output_dir.mkdir()
            codex_home = workspace / ".codex"
            session_dir = codex_home / "sessions" / "2026" / "06" / "23"
            session_dir.mkdir(parents=True)
            qmd_path = output_dir / "202606121203.qmd"
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
            image_bytes = b"fresh image payload"
            calls = []
            messages = []

            def fake_runner(cmd, **kwargs):
                calls.append((cmd, kwargs))
                if cmd[:2] == ["codex", "exec"]:
                    event = {
                        "timestamp": "2026-06-23T00:18:16.090Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "image_generation_end",
                            "status": "generating",
                            "call_id": "ig_test",
                            "result": base64.b64encode(image_bytes).decode("ascii"),
                        },
                    }
                    (session_dir / "rollout-2026-06-23T09-18-15-test.jsonl").write_text(
                        json.dumps(event) + "\n",
                        encoding="utf-8",
                    )
                elif cmd[:2] == ["sips", "-g"]:
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout=(
                            f"{output_dir / '202606121203.jpg'}\n"
                            "  pixelWidth: 1024\n"
                            "  pixelHeight: 1024\n"
                        ),
                        stderr="",
                    )
                return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

            with patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
                generated = blog_agent.generate_thumbnail_with_codex(
                    qmd_path,
                    workspace_dir=workspace,
                    style_rng=lambda: 0.8,
                    runner=fake_runner,
                    printer=messages.append,
                )

            self.assertTrue(generated)
            self.assertEqual((output_dir / "202606121203.jpg").read_bytes(), image_bytes)
            self.assertIn(
                "image: 202606121203.jpg",
                qmd_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(
                any("Recovered fresh ImageGen artifact" in message for message in messages),
                messages,
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
