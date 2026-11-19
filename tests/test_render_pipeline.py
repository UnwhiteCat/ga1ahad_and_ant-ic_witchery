"""Backend policy and orchestration checks, independent of GPU availability."""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ga1ahad.cli import build_parser
from ga1ahad.crt import resolve_backend, resolve_strength
from ga1ahad.encode import RawVideoEncoder, render_video


class BackendPolicyTests(unittest.TestCase):
    def test_auto_reports_fallback_but_explicit_gpu_fails(self):
        with patch("ga1ahad.crt.create_filter", side_effect=RuntimeError("no hardware")):
            log = io.StringIO()
            with patch("sys.stderr", log):
                self.assertEqual(resolve_backend("auto", 1.0), "cpu")
            self.assertIn("no hardware", log.getvalue())
            with self.assertRaisesRegex(RuntimeError, "GPU CRT unavailable"):
                resolve_backend("gpu", 1.0)

    def test_flat_path_does_not_probe_gpu(self):
        with patch("ga1ahad.crt.create_filter") as create:
            for strength in (resolve_strength(False, 2.0, default=1.0),
                             resolve_strength(None, 0.0, default=1.0)):
                self.assertEqual(resolve_backend("auto", strength), "cpu")
            with patch.dict("os.environ", {"GA1AHAD_CRT": "0"}):
                self.assertEqual(resolve_backend("auto", resolve_strength(None, None, default=1.0)), "cpu")
            create.assert_not_called()
        with self.assertRaisesRegex(ValueError, "requires CRT"):
            resolve_backend("gpu", 0.0)

    def test_hardware_failure_leaves_existing_output_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "existing.mp4"
            out.write_bytes(b"previous video")
            with patch("ga1ahad.crt.create_filter", side_effect=RuntimeError("no hardware")):
                with self.assertRaises(RuntimeError):
                    render_video(out, end=1.0, backend="gpu")
            self.assertEqual(out.read_bytes(), b"previous video")

    def test_render_and_preview_defaults(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["render"]).backend, "auto")
        self.assertEqual(parser.parse_args(["png", "--crt"]).backend, "cpu")
        args = parser.parse_args(["render", "--backend", "gpu", "--encoder", "h264_vaapi", "--qp", "20"])
        self.assertEqual((args.encoder, args.qp), ("h264_vaapi", 20))

    def test_encoders_use_separate_quality_controls_and_correct_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ga1ahad.encode.find_ffmpeg", return_value="ffmpeg"), \
                 patch("ga1ahad.encode.subprocess.Popen"):
                cpu = RawVideoEncoder(Path(tmp) / "cpu.ts", crf=19, scale=False)
                gpu = RawVideoEncoder(Path(tmp) / "gpu.ts", encoder="h264_vaapi", qp=23,
                                      in_size=(1920, 1080), scale=False)
                flat = RawVideoEncoder(Path(tmp) / "flat.ts", encoder="h264_vaapi", scale=True)
        self.assertIn("19", cpu.cmd)
        self.assertNotIn("-vaapi_device", cpu.cmd)
        self.assertNotIn("-crf", gpu.cmd)
        self.assertNotIn("-preset", gpu.cmd)
        self.assertEqual(gpu.cmd[gpu.cmd.index("-qp") + 1], "23")
        self.assertEqual(gpu.cmd[gpu.cmd.index("-vf") + 1], "format=nv12,hwupload")
        self.assertEqual(flat.cmd[flat.cmd.index("-vf") + 1],
                         "scale=1920:1080:flags=lanczos,format=nv12,hwupload")


if __name__ == "__main__":
    unittest.main()
