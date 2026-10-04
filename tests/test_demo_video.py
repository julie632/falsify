import base64
import hashlib
import json
import math
import shutil
import struct
import wave

import pytest

from scripts.assemble_demo import DemoError, inspect_inputs, load_timeline, subtitles


def timeline():
    return {
        "version": 1,
        "duration_seconds": 120,
        "readiness": {"status": "ready"},
        "voice": {"provider": "elevenlabs", "voice_id": "test-id", "model_id": "test-model", "provenance_file": "provenance.json"},
        "scenes": [{
            "id": "proof",
            "duration_seconds": 120,
            "title": "Recorded evidence",
            "narration": "This is the source narration transcript.",
            "evidence_label": "Recorded replay",
            "image": "still.png",
            "audio": "voice.wav",
        }],
    }


def write_plan(tmp_path, plan):
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(plan))
    return path


def test_final_refuses_unready_timeline_and_missing_voice(tmp_path):
    plan = timeline()
    plan["readiness"]["status"] = "pending_system_ready"
    with pytest.raises(DemoError, match="readiness.status"):
        load_timeline(write_plan(tmp_path, plan), "final")
    plan["readiness"]["status"] = "ready"
    plan["voice"]["voice_id"] = None
    with pytest.raises(DemoError, match="voice_id"):
        load_timeline(write_plan(tmp_path, plan), "final")


@pytest.mark.parametrize("missing, message", [("image", "placeholders"), ("audio", "silent substitution"), ("narration", "transcript")])
def test_final_never_substitutes_missing_assets(tmp_path, missing, message):
    plan = timeline()
    del plan["scenes"][0][missing]
    with pytest.raises(DemoError, match=message):
        load_timeline(write_plan(tmp_path, plan), "final")


def test_exact_two_minute_timeline_and_frame_boundaries(tmp_path):
    plan = timeline()
    plan["scenes"][0]["duration_seconds"] = 119
    with pytest.raises(DemoError, match="exactly 120s"):
        load_timeline(write_plan(tmp_path, plan), "animatic")
    plan["scenes"][0]["duration_seconds"] = 119.99
    with pytest.raises(DemoError, match="1/30 second"):
        load_timeline(write_plan(tmp_path, plan), "animatic")


def test_animatic_allows_pending_assets_and_labels_planned_narration(tmp_path):
    plan = timeline()
    plan["readiness"]["status"] = "pending_system_ready"
    del plan["scenes"][0]["image"]
    del plan["scenes"][0]["audio"]
    parsed = load_timeline(write_plan(tmp_path, plan), "animatic")
    srt = subtitles(parsed["scenes"], "animatic")
    assert "PLANNED NARRATION, SILENT ANIMATIC" in srt
    assert "00:02:00,000" in srt


def write_media(tmp_path, seconds, silent=False):
    (tmp_path / "still.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD1sAAAAASUVORK5CYII="
    ))
    with wave.open(str(tmp_path / "voice.wav"), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"".join(struct.pack("<h", 0 if silent else round(8000 * math.sin(2 * math.pi * 440 * frame / 8000))) for frame in range(round(seconds * 8000))))
    (tmp_path / "provenance.json").write_text(json.dumps({
        "provider": "elevenlabs", "voice_id": "test-id", "model_id": "test-model",
        "clips": [{"scene_id": "proof", "path": "voice.wav", "sha256": hashlib.sha256((tmp_path / "voice.wav").read_bytes()).hexdigest(), "generation_id": "test-only-synthetic-tone"}],
    }))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="Requires FFmpeg input inspection")
@pytest.mark.parametrize("seconds,silent,message", [(121, False, "will not be truncated"), (1, True, "silent or inaudible")])
def test_final_rejects_overlong_or_silent_narration(tmp_path, seconds, silent, message):
    write_media(tmp_path, seconds, silent)
    with pytest.raises(DemoError, match=message):
        inspect_inputs(timeline(), tmp_path, "final", "ffmpeg", "ffprobe")


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="Requires FFmpeg input inspection")
def test_media_paths_resolve_from_timeline_directory(tmp_path, monkeypatch):
    write_media(tmp_path, 1)
    elsewhere = tmp_path / "another-working-directory"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    checked = inspect_inputs(timeline(), tmp_path, "final", "ffmpeg", "ffprobe")
    assert checked[0]["audio"] == tmp_path / "voice.wav"
    assert checked[0]["audio_duration_seconds"] == 1
    assert checked[0]["audio_peak_dbfs"] > -20


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="Requires FFmpeg input inspection")
def test_final_rejects_changed_audio_generation_record(tmp_path):
    write_media(tmp_path, 1)
    manifest = json.loads((tmp_path / "provenance.json").read_text())
    manifest["clips"][0]["sha256"] = "0" * 64
    (tmp_path / "provenance.json").write_text(json.dumps(manifest))
    with pytest.raises(DemoError, match="audio hash differs"):
        inspect_inputs(timeline(), tmp_path, "final", "ffmpeg", "ffprobe")
