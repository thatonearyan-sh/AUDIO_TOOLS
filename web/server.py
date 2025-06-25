#!/usr/bin/env python3
"""
Aryan Audio Toolkit — Flask Web Server
Provides REST API for all audio operations.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime
import re

# ── Ensure pydub / ffmpeg available ──────────────────────────────────────────
try:
    from pydub import AudioSegment
    from pydub.effects import speedup
    from pydub.silence import split_on_silence
except ImportError:
    print("❌ pydub not installed. Run: pip3 install pydub")
    sys.exit(1)

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# ── App setup ─────────────────────────────────────────────────────────────────
APP_DIR     = Path(__file__).parent
ROOT_DIR    = APP_DIR.parent
UPLOAD_DIR  = ROOT_DIR / ".web_uploads"
OUTPUT_DIR  = ROOT_DIR / "WebOutputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_EXTS = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus'}
VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp'}

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response   # 500 MB for video support


# ── Helpers ───────────────────────────────────────────────────────────────────

def uid() -> str:
    return uuid.uuid4().hex[:10]


def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == "":
            return float(default)
        return float(val)
    except (ValueError, TypeError):
        return float(default)


def safe_int(val, default=0):
    try:
        if val is None or str(val).strip() == "":
            return int(default)
        return int(val)
    except (ValueError, TypeError):
        return int(default)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]', '_', name)

def save_upload(file) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ext  = Path(file.filename).suffix.lower()
    base = sanitize_filename(Path(file.filename).stem)
    name = f"{ts}_INPUT_{base}{ext}"
    path = UPLOAD_DIR / name
    file.save(str(path))
    return path


def load_audio(path: Path | str) -> AudioSegment:
    p   = Path(path)
    ext = p.suffix.lower().lstrip('.') or 'mp3'
    return AudioSegment.from_file(str(p), format=ext)


def export_audio(audio: AudioSegment, suffix: str, ext: str = "mp3", input_path: Path = None) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    base = uid()[:6]
    if input_path:
        stem = input_path.stem
        if "_INPUT_" in stem:
            base = stem.split("_INPUT_")[-1]
        else:
            base = stem

    name = f"{ts}_{base}_{suffix}.{ext.lstrip('.')}"
    out  = OUTPUT_DIR / name
    audio.export(str(out), format=ext.lstrip('.'))
    return out


def parse_ms(t: str) -> int:
    """'1:30' or '90' → milliseconds."""
    t = str(t).strip()
    if not t:
        return 0
    try:
        if ':' in t:
            m, s = t.split(':', 1)
            return int((int(m) * 60 + float(s)) * 1000)
        return int(float(t) * 1000)
    except (ValueError, TypeError):
        return 0


def ms_to_str(ms: int) -> str:
    s = ms / 1000
    m = int(s // 60)
    return f"{m}:{s % 60:05.2f}"


def error(msg: str, code: int = 400):
    return jsonify({"ok": False, "error": msg}), code


def ok(data: dict):
    return jsonify({"ok": True, **data})


def file_url(path: Path) -> str:
    return f"/outputs/{path.name}"


@app.errorhandler(500)
def handle_500(e):
    return jsonify({"ok": False, "error": "Internal Server Error", "details": str(e)}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"ok": False, "error": "Not Found"}), 404





# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/outputs/<filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/api/info", methods=["POST"])
def api_info():
    if 'file' not in request.files:
        return error("No file uploaded")
    f    = request.files['file']
    path = save_upload(f)
    try:
        audio = load_audio(path)
        return ok({
            "filename":     f.filename,
            "duration_ms":  len(audio),
            "duration_str": ms_to_str(len(audio)),
            "channels":     audio.channels,
            "frame_rate":   audio.frame_rate,
            "sample_width": audio.sample_width * 8,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
        })
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/crop", methods=["POST"])
def api_crop():
    if 'file' not in request.files:
        return error("No file uploaded")
    f     = request.files['file']
    start = request.form.get("start", "0")
    end   = request.form.get("end", "")
    path  = save_upload(f)
    try:
        audio    = load_audio(path)
        start_ms = parse_ms(start)
        end_ms   = parse_ms(end) if end else len(audio)
        if start_ms >= end_ms:
            return error("Start must be before end")
        end_ms = min(end_ms, len(audio))
        cropped  = audio[start_ms:end_ms]
        ext  = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out  = export_audio(cropped, "crop", ext, input_path=path)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(cropped))})
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/merge", methods=["POST"])
def api_merge():
    files = request.files.getlist("files")
    if len(files) < 2:
        return error("Upload at least 2 files")
        
    import json
    try:
        metadata = json.loads(request.form.get("metadata", "[]"))
    except Exception:
        metadata = []
        
    paths = []
    try:
        combined = AudioSegment.empty()
        for i, f in enumerate(files):
            p = save_upload(f)
            paths.append(p)
            audio = load_audio(p)
            
            m = metadata[i] if i < len(metadata) else {}
            if m.get("db"):
                audio += float(m["db"])
                
            start_str = m.get("start", "")
            end_str = m.get("end", "")
            if start_str or end_str:
                start_ms = parse_ms(start_str) if start_str else 0
                end_ms = parse_ms(end_str) if end_str else len(audio)
                audio = audio[start_ms:end_ms]
                
            combined += audio
            
        ext = Path(files[0].filename).suffix.lstrip('.') or 'mp3'
        out = export_audio(combined, "merged", ext, input_path=paths[0] if paths else None)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(combined))})
    except Exception as e:
        return error(str(e))
    finally:
        for p in paths:
            try: p.unlink()
            except Exception: pass


@app.route("/api/overlay", methods=["POST"])
def api_overlay():
    base = request.files.get("base")
    overlays = request.files.getlist("overlays")
    if not base or not overlays:
        return error("Upload both base and at least one overlay file")
    
    import json
    try:
        metadata = json.loads(request.form.get("metadata", "[]"))
    except Exception:
        metadata = []
        
    paths = []
    try:
        p_base = save_upload(base)
        paths.append(p_base)
        audio_base = load_audio(p_base)
        
        # Apply base metadata (index 0)
        m_base = metadata[0] if len(metadata) > 0 else {}
        if m_base.get("db"):
            audio_base += float(m_base["db"])
        if m_base.get("start") or m_base.get("end"):
            s_ms = parse_ms(m_base.get("start", "")) if m_base.get("start") else 0
            e_ms = parse_ms(m_base.get("end", "")) if m_base.get("end") else len(audio_base)
            audio_base = audio_base[s_ms:e_ms]
        
        for i, ov in enumerate(overlays):
            p_ov = save_upload(ov)
            paths.append(p_ov)
            audio_ov = load_audio(p_ov)
            
            # Apply overlay metadata (index i + 1)
            m_ov = metadata[i+1] if i+1 < len(metadata) else {}
            if m_ov.get("db"):
                audio_ov += float(m_ov["db"])
            if m_ov.get("start") or m_ov.get("end"):
                s_ms = parse_ms(m_ov.get("start", "")) if m_ov.get("start") else 0
                e_ms = parse_ms(m_ov.get("end", "")) if m_ov.get("end") else len(audio_ov)
                audio_ov = audio_ov[s_ms:e_ms]
                
            # Loop the overlay if it's shorter than the base track
            if len(audio_ov) < len(audio_base) and len(audio_ov) > 0:
                audio_ov = audio_ov * ((len(audio_base) // len(audio_ov)) + 1)
            audio_base = audio_base.overlay(audio_ov)
            
        ext = Path(base.filename).suffix.lstrip('.') or 'mp3'
        out = export_audio(audio_base, "mixed", ext, input_path=p_base)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(audio_base))})
    except Exception as e:
        return error(str(e))
    finally:
        for p in paths:
            try: p.unlink()
            except Exception: pass


@app.route("/api/volume", methods=["POST"])
def api_volume():
    if 'file' not in request.files:
        return error("No file uploaded")
    f  = request.files['file']
    db = safe_float(request.form.get("db"), 3.0)
    path = save_upload(f)
    try:
        audio    = load_audio(path)
        adjusted = audio + db
        ext = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out = export_audio(adjusted, f"vol{'+' if db>=0 else ''}{int(db)}dB", ext, input_path=path)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(adjusted))})
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/convert", methods=["POST"])
def api_convert():
    if 'file' not in request.files:
        return error("No file uploaded")
    f   = request.files['file']
    fmt = request.form.get("format", "mp3").lower()
    path = save_upload(f)
    try:
        audio = load_audio(path)
        out   = export_audio(audio, "converted", fmt, input_path=path)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(audio))})
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/speed", methods=["POST"])
def api_speed():
    if 'file' not in request.files:
        return error("No file uploaded")
    f     = request.files['file']
    speed = safe_float(request.form.get("speed"), 1.5)
    if speed <= 0:
        return error("Speed must be > 0")
    path = save_upload(f)
    try:
        audio = load_audio(path)
        if speed > 1.0:
            result = speedup(audio, playback_speed=speed)
        else:
            slowed = audio._spawn(audio.raw_data, overrides={
                "frame_rate": int(audio.frame_rate * speed)
            })
            result = slowed.set_frame_rate(audio.frame_rate)
        ext = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out = export_audio(result, f"speed{speed}x", ext, input_path=path)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(result))})
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/fade", methods=["POST"])
def api_fade():
    if 'file' not in request.files:
        return error("No file uploaded")
    f         = request.files['file']
    fade_in   = int(safe_float(request.form.get("fade_in"),  0.0)  * 1000)
    fade_out  = int(safe_float(request.form.get("fade_out"), 0.0)  * 1000)
    path = save_upload(f)
    try:
        audio = load_audio(path)
        if fade_in:  audio = audio.fade_in(fade_in)
        if fade_out: audio = audio.fade_out(fade_out)
        ext = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out = export_audio(audio, "faded", ext, input_path=path)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(audio))})
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/reverse", methods=["POST"])
def api_reverse():
    if 'file' not in request.files:
        return error("No file uploaded")
    f    = request.files['file']
    path = save_upload(f)
    try:
        audio   = load_audio(path)
        rev     = audio.reverse()
        ext     = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out     = export_audio(rev, "reversed", ext, input_path=path)
        return ok({"url": file_url(out), "duration_str": ms_to_str(len(rev))})
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/normalize", methods=["POST"])
def api_normalize():
    if 'file' not in request.files:
        return error("No file uploaded")
    f      = request.files['file']
    target = safe_float(request.form.get("target"), -14.0)
    path   = save_upload(f)
    try:
        audio      = load_audio(path)
        change     = target - audio.dBFS
        normalized = audio + change
        ext        = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out        = export_audio(normalized, "normalized", ext, input_path=path)
        return ok({
            "url": file_url(out),
            "duration_str": ms_to_str(len(normalized)),
            "change_db": round(change, 1),
        })
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/silence", methods=["POST"])
def api_silence():
    if 'file' not in request.files:
        return error("No file uploaded")
    f       = request.files['file']
    thresh  = safe_float(request.form.get("threshold"), -40.0)
    min_sil = safe_int(request.form.get("min_silence"), 500)
    padding = safe_int(request.form.get("padding"), 200)
    path    = save_upload(f)
    try:
        audio  = load_audio(path)
        chunks = split_on_silence(audio, min_silence_len=min_sil,
                                  silence_thresh=thresh, keep_silence=padding)
        if not chunks:
            return error("No speech detected — try a higher threshold (e.g. -30)")
        combined = sum(chunks, AudioSegment.empty())
        ext      = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out      = export_audio(combined, "no_silence", ext, input_path=path)
        removed  = len(audio) - len(combined)
        return ok({
            "url": file_url(out),
            "duration_str": ms_to_str(len(combined)),
            "removed_str":  ms_to_str(removed),
        })
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/besttakes", methods=["POST"])
def api_besttakes():
    if 'file' not in request.files:
        return error("No file uploaded")
    f = request.files['file']
    path = save_upload(f)
    try:
        audio = load_audio(path)
        # Aggressive silence stripping for spoken word
        chunks = split_on_silence(
            audio,
            min_silence_len=400,
            silence_thresh=audio.dBFS - 14,
            keep_silence=150
        )
        if not chunks:
            return error("Could not detect distinct audio takes.")
            
        # Stitch them together with a tiny crossfade to prevent pops
        best_takes = chunks[0]
        for chunk in chunks[1:]:
            best_takes = best_takes.append(chunk, crossfade=min(50, len(chunk), len(best_takes)))
            
        ext = Path(f.filename).suffix.lstrip('.') or 'mp3'
        out = export_audio(best_takes, "besttakes", ext, input_path=path)
        return ok({
            "url": file_url(out), 
            "duration_str": ms_to_str(len(best_takes)),
            "removed_str": ms_to_str(len(audio) - len(best_takes))
        })
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/extract", methods=["POST"])
def api_extract():
    if 'file' not in request.files:
        return error("No file uploaded")
    f      = request.files['file']
    start  = request.form.get("start", "0")
    end    = request.form.get("end", "")
    fmt    = request.form.get("format", "mp3").lower()
    path   = save_upload(f)
    try:
        # Build ffmpeg command
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = path.stem
        if "_INPUT_" in base:
            base = base.split("_INPUT_")[-1]
            
        out_name = f"{ts}_{base}_extracted.{fmt}"
        out_path = OUTPUT_DIR / out_name

        cmd = ["ffmpeg", "-y", "-i", str(path)]

        start_ms = parse_ms(start)
        if start_ms > 0:
            cmd += ["-ss", str(start_ms / 1000)]

        if end:
            end_ms = parse_ms(end)
            if end_ms <= start_ms:
                return error("End time must be after start time")
            duration_sec = (end_ms - start_ms) / 1000
            cmd += ["-t", str(duration_sec)]

        cmd += ["-vn"]  # no video

        if fmt == "mp3":
            cmd += ["-acodec", "libmp3lame", "-q:a", "2"]
        elif fmt == "wav":
            cmd += ["-acodec", "pcm_s16le"]
        elif fmt == "flac":
            cmd += ["-acodec", "flac"]
        elif fmt == "aac":
            cmd += ["-acodec", "aac", "-b:a", "192k"]
        elif fmt == "ogg":
            cmd += ["-acodec", "libvorbis", "-q:a", "5"]
        elif fmt == "opus":
            cmd += ["-acodec", "libopus", "-b:a", "128k"]

        cmd.append(str(out_path))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            stderr = result.stderr[-500:] if result.stderr else 'Unknown ffmpeg error'
            return error(f"ffmpeg error: {stderr}")

        # Get output duration
        audio = load_audio(out_path)
        return ok({
            "url": file_url(out_path),
            "duration_str": ms_to_str(len(audio)),
            "file_size_kb": round(out_path.stat().st_size / 1024, 1),
        })
    except subprocess.TimeoutExpired:
        return error("Processing timed out (video may be too large)")
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/video-info", methods=["POST"])
def api_video_info():
    """Get video duration via ffprobe."""
    if 'file' not in request.files:
        return error("No file uploaded")
    f    = request.files['file']
    path = save_upload(f)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30
        )
        total_sec = float(probe.stdout.strip())
        return ok({
            "duration_ms":  int(total_sec * 1000),
            "duration_str": ms_to_str(int(total_sec * 1000)),
            "filename":     f.filename,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
        })
    except Exception:
        return ok({
            "duration_ms":  0,
            "duration_str": "Unknown",
            "filename":     f.filename,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
        })
    finally:
        try: path.unlink()
        except Exception: pass


@app.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    if 'file' not in request.files:
        return error("No file uploaded")
    f = request.files['file']
    path = save_upload(f)
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        
        # Load audio (works for both audio and video files via ffmpeg under the hood)
        audio = load_audio(path)
        
        try:
            chunk_sec = safe_int(request.form.get("chunk_sec"), 60)
        except ValueError:
            chunk_sec = 60
            
        chunk_ms = chunk_sec * 1000
        full_text = []
        srt_lines = []
        
        def ms_to_srt(ms):
            s = ms // 1000
            m = s // 60
            h = m // 60
            return f"{h:02d}:{m%60:02d}:{s%60:02d},{ms%1000:03d}"
        
        chunk_idx = 1
        for i in range(0, len(audio), chunk_ms):
            chunk = audio[i:i+chunk_ms]
            start_str = ms_to_str(i)
            end_ms_val = min(i + chunk_ms, len(audio))
            end_str = ms_to_str(end_ms_val)
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_wav:
                chunk.export(temp_wav.name, format="wav")
                with sr.AudioFile(temp_wav.name) as source:
                    audio_data = r.record(source)
                    try:
                        text = r.recognize_google(audio_data)
                        full_text.append(f"[{start_str} - {end_str}]\n{text}")
                        srt_lines.append(f"{chunk_idx}\n{ms_to_srt(i)} --> {ms_to_srt(end_ms_val)}\n{text}\n")
                        chunk_idx += 1
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        return error(f"Speech API Error: {e}")
                        
        final_text = "\n\n".join(full_text)
        final_srt = "\n".join(srt_lines)
        if not final_text.strip():
            final_text = "(No speech could be recognized)"
            
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base = path.stem
        if "_INPUT_" in base:
            base = base.split("_INPUT_")[-1]
        
        out_name = f"{ts}_{base}_transcription.txt"
        out_path = OUTPUT_DIR / out_name
        out_path.write_text(final_text)
        
        srt_name = f"{ts}_{base}_subtitles.srt"
        srt_path = OUTPUT_DIR / srt_name
        srt_path.write_text(final_srt)
        
        return ok({
            "text": final_text, 
            "url": file_url(out_path),
            "srt_url": file_url(srt_path)
        })
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass




# ── Entry point ───────────────────────────────────────────────────────────────

# ── PRO FEATURES ──────────────────────────────────────────────────────────────

@app.route("/api/master", methods=["POST"])
def api_master():
    if 'file' not in request.files: return error("No file uploaded")
    path = save_upload(request.files['file'])
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = OUTPUT_DIR / f"{ts}_{path.stem}_Mastered.mp3"
        # loudnorm is the broadcast standard for mastering loudness
        cmd = ["ffmpeg", "-y", "-i", str(path), "-af", "loudnorm=I=-14:LRA=11:TP=-1.0", str(out_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        return ok({"url": file_url(out_path), "duration_str": "Mastered"})
    except subprocess.CalledProcessError as e:
        return error(f"FFmpeg error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass

@app.route("/api/isolate", methods=["POST"])
def api_isolate():
    if 'file' not in request.files: return error("No file uploaded")
    path = save_upload(request.files['file'])
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = OUTPUT_DIR / f"{ts}_{path.stem}_Instrumental.mp3"
        # Karaoke effect via pan filter (center channel subtraction)
        cmd = ["ffmpeg", "-y", "-i", str(path), "-af", "pan=stereo|c0=c0-c1|c1=c1-c0", str(out_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        return ok({"url": file_url(out_path), "duration_str": "Isolated"})
    except subprocess.CalledProcessError as e:
        return error(f"FFmpeg error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass

@app.route("/api/visualizer", methods=["POST"])
def api_visualizer():
    if 'file' not in request.files: return error("No file uploaded")
    path = save_upload(request.files['file'])
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = OUTPUT_DIR / f"{ts}_{path.stem}_Visualizer.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", str(path),
            "-filter_complex", "[0:a]showwaves=s=1280x720:mode=cline:rate=30:colors=0x00E5FF[v]",
            "-map", "[v]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(out_path)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return ok({"url": file_url(out_path), "duration_str": "MP4 Generated"})
    except subprocess.CalledProcessError as e:
        return error(f"FFmpeg error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass

@app.route("/api/fx", methods=["POST"])
def api_fx():
    if 'file' not in request.files: return error("No file uploaded")
    path = save_upload(request.files['file'])
    reverb = safe_float(request.form.get("reverb"), 0.0)
    bass = safe_float(request.form.get("bass"), 0.0)
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = OUTPUT_DIR / f"{ts}_{path.stem}_FX.mp3"
        filters = []
        if reverb > 0:
            filters.append(f"aecho=0.8:0.9:{int(reverb*1000)}:0.3")
        if bass != 0:
            filters.append(f"bass=g={bass}")
        
        filter_str = ",".join(filters) if filters else "anull"
        cmd = ["ffmpeg", "-y", "-i", str(path), "-af", filter_str, str(out_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        return ok({"url": file_url(out_path), "duration_str": "FX Applied"})
    except subprocess.CalledProcessError as e:
        return error(f"FFmpeg error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass

@app.route("/api/8d", methods=["POST"])
def api_8d():
    if 'file' not in request.files: return error("No file uploaded")
    path = save_upload(request.files['file'])
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = OUTPUT_DIR / f"{ts}_{path.stem}_8D.mp3"
        # apulsator pans the audio left and right continuously to create an 8D effect
        cmd = ["ffmpeg", "-y", "-i", str(path), "-af", "apulsator=hz=0.125", str(out_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        return ok({"url": file_url(out_path), "duration_str": "8D Generated"})
    except subprocess.CalledProcessError as e:
        return error(f"FFmpeg error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return error(str(e))
    finally:
        try: path.unlink()
        except Exception: pass

@app.route("/api/tts", methods=["POST"])
def api_tts():
    # Since this does not upload a file, we can't depend on request.files['file']
    text = request.form.get("tts_text", "").strip()
    if not text: return error("No text provided")
    voice = request.form.get("tts_voice", "Samantha")
    try:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_aiff = OUTPUT_DIR / f"{ts}_TTS_temp.aiff"
        out_mp3 = OUTPUT_DIR / f"{ts}_Voiceover.mp3"
        
        # Use native macOS 'say' engine for high-quality TTS
        subprocess.run(["say", "-v", voice, "-o", str(out_aiff), text], check=True, capture_output=True)
        # Convert AIFF to MP3 via FFmpeg
        subprocess.run(["ffmpeg", "-y", "-i", str(out_aiff), "-q:a", "2", str(out_mp3)], check=True, capture_output=True)
        
        return ok({"url": file_url(out_mp3), "duration_str": "AI Voiceover"})
    except subprocess.CalledProcessError as e:
        return error(f"TTS Error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        return error(str(e))
    finally:
        try: out_aiff.unlink()
        except Exception: pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7171))
    print("\n🎵  Aryan Audio Toolkit — Web UI")
    print(f"   → http://localhost:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=True)
