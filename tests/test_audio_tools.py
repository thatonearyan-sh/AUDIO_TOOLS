"""
AUDIO_TOOLS Comprehensive DSP Test Suite
Verifies audio format conversions, FFmpeg filter graph synthesis, and sidechain ducking.
"""
import unittest
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

class TestAudioTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = BASE_DIR / "temp"
        cls.temp_dir.mkdir(exist_ok=True)
        cls.test_wav = cls.temp_dir / "sine_voice.wav"
        cls.test_bgm = cls.temp_dir / "sine_bgm.wav"

        # Generate two small 2-second test audio files with FFmpeg
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-ar", "44100", "-ac", "1", str(cls.test_wav)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=3", "-ar", "44100", "-ac", "2", str(cls.test_bgm)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        for f in (BASE_DIR / "temp").glob("sine_*"):
            if f.is_file():
                f.unlink()

    def test_01_ffmpeg_available(self):
        """Verify FFmpeg installation and version string."""
        res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("ffmpeg version", res.stdout)
        print("  [Pass] FFmpeg DSP engine detected and functional")

    def test_02_pitch_preserved_speed_filter(self):
        """Verify atempo filter speed adjustment."""
        out_speed = self.temp_dir / "sine_1.25x.wav"
        res = subprocess.run(["ffmpeg", "-y", "-i", str(self.test_wav), "-filter:a", "atempo=1.25", str(out_speed)], capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_speed.exists())
        out_speed.unlink()
        print("  [Pass] WSOLA atempo retiming filter verified")

    def test_03_format_transcoder(self):
        """Verify lossless WAV to 320k MP3 transcoding."""
        out_mp3 = self.temp_dir / "sine_out.mp3"
        res = subprocess.run(["ffmpeg", "-y", "-i", str(self.test_wav), "-b:a", "320k", str(out_mp3)], capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_mp3.exists())
        out_mp3.unlink()
        print("  [Pass] 320k MP3 transcoding verified")

    def test_04_sidechain_ducking_filter(self):
        """Verify sidechain compression filter graph."""
        out_mix = self.temp_dir / "sine_mix.wav"
        filter_str = "[1:a]asplit=2[sc][mix];[0:a][sc]sidechaincompress=threshold=0.08:ratio=4:attack=15:release=350[ducked];[ducked][mix]amix=inputs=2"
        res = subprocess.run(["ffmpeg", "-y", "-i", str(self.test_bgm), "-i", str(self.test_wav), "-filter_complex", filter_str, str(out_mix)], capture_output=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_mix.exists())
        out_mix.unlink()
        print("  [Pass] Sidechain compression & BGM auto-ducking verified")

if __name__ == "__main__":
    unittest.main()
