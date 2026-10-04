#!/usr/bin/env python3
"""Assemble a local 60- or 120-second demo from media and narration.

Requires FFmpeg, ffprobe and Pillow. Relative input paths are relative to the
timeline file. Animatics are always silent and visibly labeled. A final render
requires an explicitly ready timeline, ElevenLabs voice metadata, footage or a
still image, and non-silent narration for every scene. This validates technical
readiness, not the scientific claims or the authenticity of declared provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

WIDTH, HEIGHT, FPS, LENGTH = 1920, 1080, 30, 120
LABELS = {"Recorded replay", "Live Omnigent run", "Deterministic local run", "Context"}


class DemoError(ValueError):
    """A validation or external-process error suitable for CLI display."""


def run(command: list[str], timeout: int = 900) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DemoError(f"Could not complete {Path(command[0]).name}: {exc}") from exc
    if result.returncode:
        raise DemoError(f"{Path(command[0]).name} failed ({result.returncode}):\n{result.stderr[-5000:]}")
    return result.stdout + result.stderr


def executable(value: str) -> str:
    found = shutil.which(value)
    if not found:
        raise DemoError(f"Missing executable: {value}. Install FFmpeg or pass its explicit path.")
    return found


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    try:
        return json.loads(run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    except json.JSONDecodeError as exc:
        raise DemoError(f"ffprobe returned invalid JSON for {path}") from exc


def duration(info: dict[str, Any], kind: str) -> float:
    stream = next((s for s in info.get("streams", []) if s.get("codec_type") == kind), None)
    if stream is None:
        raise DemoError(f"Input does not contain a {kind} stream")
    value = stream.get("duration", info.get("format", {}).get("duration"))
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DemoError(f"Cannot determine {kind} duration") from exc
    if not math.isfinite(number) or number <= 0:
        raise DemoError(f"Invalid {kind} duration: {value}")
    return number


def input_path(value: Any, folder: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise DemoError(f"{label} must be a local file path")
    path = Path(value).expanduser()
    path = (folder / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_file():
        raise DemoError(f"Missing {label}: {path}")
    return path


def file_hash(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_timeline(path: Path, mode: str) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoError(f"Cannot read timeline: {exc}") from exc
    if not isinstance(plan, dict) or plan.get("version") != 1:
        raise DemoError("Timeline must be an object with version: 1")
    if plan.get("duration_seconds") != LENGTH:
        raise DemoError(f"Timeline duration_seconds must equal {LENGTH}")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise DemoError("Timeline requires a nonempty scenes list")
    if mode == "final":
        if not isinstance(plan.get("readiness"), dict) or plan["readiness"].get("status") != "ready":
            raise DemoError("Final render requires readiness.status: ready after evidence and system review")
        voice = plan.get("voice", {})
        if not isinstance(voice, dict) or voice.get("provider") != "elevenlabs" or not voice.get("voice_id") or not voice.get("model_id"):
            raise DemoError("Final render requires voice.provider: elevenlabs, voice_id and model_id")
        if not voice.get("provenance_file"):
            raise DemoError("Final render requires voice.provenance_file with ElevenLabs generation IDs and audio hashes")
    seen: set[str] = set()
    total_frames = 0
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise DemoError(f"Scene {index} must be an object")
        name = scene.get("id")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name) or name in seen:
            raise DemoError(f"Scene {index} needs a unique id using letters, digits, underscores or hyphens")
        seen.add(name)
        seconds = scene.get("duration_seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            raise DemoError(f"Scene {name} requires a positive duration_seconds")
        frames = seconds * FPS
        if abs(frames - round(frames)) > 0.000001:
            raise DemoError(f"Scene {name} duration must align to 1/30 second")
        total_frames += round(frames)
        if not isinstance(scene.get("title"), str) or not scene["title"].strip():
            raise DemoError(f"Scene {name} requires a title")
        for field in ("caption", "narration"):
            if scene.get(field) is not None and not isinstance(scene[field], str):
                raise DemoError(f"Scene {name} {field} must be text")
        if scene.get("evidence_label") not in LABELS:
            raise DemoError(f"Scene {name} requires evidence_label from: {', '.join(sorted(LABELS))}")
        if scene.get("image") and scene.get("video"):
            raise DemoError(f"Scene {name} must choose either image or video")
        offset = scene.get("video_start_seconds", 0)
        if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset) or offset < 0:
            raise DemoError(f"Scene {name} has invalid video_start_seconds")
        if mode == "final":
            if not (scene.get("image") or scene.get("video")):
                raise DemoError(f"Scene {name} has no image or video; final renders cannot use placeholders")
            if not scene.get("audio"):
                raise DemoError(f"Scene {name} has no narration audio; silent substitution is forbidden")
            if not isinstance(scene.get("narration"), str) or not scene["narration"].strip():
                raise DemoError(f"Scene {name} needs a verbatim narration transcript for subtitles")
    if total_frames != LENGTH * FPS:
        raise DemoError(f"Scene durations sum to {total_frames / FPS:g}s; exactly {LENGTH}s is required")
    return plan


def check_provenance(plan: dict[str, Any], scenes: list[dict[str, Any]], folder: Path) -> None:
    """Bind the selected audio bytes to the explicitly recorded generation log."""
    voice = plan["voice"]
    path = input_path(voice.get("provenance_file"), folder, "ElevenLabs provenance manifest")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DemoError(f"Cannot read ElevenLabs provenance manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise DemoError("ElevenLabs provenance manifest must be an object")
    for key in ("provider", "voice_id", "model_id"):
        if manifest.get(key) != voice.get(key):
            raise DemoError(f"ElevenLabs provenance {key} does not match timeline voice metadata")
    clips = manifest.get("clips")
    if not isinstance(clips, list) or any(not isinstance(clip, dict) for clip in clips):
        raise DemoError("ElevenLabs provenance requires a clips list")
    mapped = {clip.get("scene_id"): clip for clip in clips}
    if len(mapped) != len(clips):
        raise DemoError("ElevenLabs provenance has duplicate scene IDs")
    for scene in scenes:
        clip = mapped.get(scene["id"], {})
        if not clip.get("generation_id"):
            raise DemoError(f"{scene['id']} has no recorded ElevenLabs generation_id")
        selected = input_path(clip.get("path"), path.parent, f"{scene['id']} provenance audio")
        if selected != scene["audio"]:
            raise DemoError(f"{scene['id']} selected audio differs from its ElevenLabs provenance record")
        if clip.get("sha256") != file_hash(selected):
            raise DemoError(f"{scene['id']} audio hash differs from its ElevenLabs provenance record")
        scene["elevenlabs_generation_id"] = clip["generation_id"]


def inspect_inputs(plan: dict[str, Any], folder: Path, mode: str, ffmpeg: str, ffprobe: str) -> list[dict[str, Any]]:
    checked = []
    for scene in plan["scenes"]:
        item: dict[str, Any] = dict(scene)
        for kind in ("image", "video"):
            if scene.get(kind):
                item[kind] = input_path(scene[kind], folder, f"{scene['id']} {kind}")
                item[f"{kind}_sha256"] = file_hash(item[kind])
                info = probe(item[kind], ffprobe)
                if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
                    raise DemoError(f"{scene['id']} {kind} contains no visual stream")
                if kind == "video":
                    available = duration(info, "video") - scene.get("video_start_seconds", 0)
                    if available + 0.000001 < scene["duration_seconds"]:
                        raise DemoError(f"{scene['id']} video has {available:.3f}s after its start, needs {scene['duration_seconds']}s")
        if mode == "final":
            item["audio"] = input_path(scene["audio"], folder, f"{scene['id']} audio")
            item["audio_sha256"] = file_hash(item["audio"])
            item["audio_duration_seconds"] = duration(probe(item["audio"], ffprobe), "audio")
            if item["audio_duration_seconds"] > scene["duration_seconds"] + 0.000001:
                raise DemoError(f"{scene['id']} narration is {item['audio_duration_seconds']:.3f}s, longer than its {scene['duration_seconds']}s slot. Revise or regenerate it; narration will not be truncated.")
            output = run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(item["audio"]), "-vn", "-af", "volumedetect", "-f", "null", "-"])
            match = re.search(r"max_volume:\s*(-?[\d.]+|[-+]?inf)\s*dB", output)
            if not match or float(match.group(1)) <= -65:
                raise DemoError(f"{scene['id']} narration is silent or inaudible; provide genuine recorded speech")
            item["audio_peak_dbfs"] = float(match.group(1))
        else:
            item.pop("audio", None)
        checked.append(item)
    if mode == "final":
        check_provenance(plan, checked, folder)
    return checked


def find_font(explicit: str | None = None) -> str:
    options = [explicit] if explicit else [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in options:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise DemoError("No suitable font found. Pass --font /path/to/font.ttf")


def draw_text(draw: Any, text: str, box: tuple[int, int, int, int], font_path: str, size: int, fill: str) -> None:
    from PIL import ImageFont

    x, y, width, height = box
    for current_size in range(size, 17, -1):
        font = ImageFont.truetype(font_path, current_size)
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            line = ""
            for word in paragraph.split():
                candidate = f"{line} {word}".strip()
                if draw.textlength(candidate, font=font) <= width:
                    line = candidate
                else:
                    if line:
                        lines.append(line)
                    line = word
            lines.append(line)
        line_height = round(current_size * 1.35)
        if len(lines) * line_height <= height and all(draw.textlength(line, font=font) <= width for line in lines):
            for index, line in enumerate(lines):
                draw.text((x, y + index * line_height), line, font=font, fill=fill)
            return
    raise DemoError("Text does not fit its video card. Shorten the title or caption.")


def make_overlay(scene: dict[str, Any], mode: str, font: str, output: Path, index: int, count: int) -> None:
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, WIDTH, 135), fill="#153f35")
    draw.rectangle((0, 826, WIDTH, HEIGHT), fill="#153f35")
    draw.rounded_rectangle((72, 34, 248, 93), radius=14, fill="#bdd0a5")
    draw_text(draw, "FALSIFY", (89, 43, 150, 46), font, 32, "#153f35")
    draw_text(draw, scene["title"], (284, 38, 1300, 80), font, 43, "#f6f7f2")
    draw_text(draw, f"{index:02d} / {count:02d}", (1668, 46, 180, 50), font, 28, "#bdd0a5")
    caption = scene.get("caption") or scene.get("narration") or "Visual placeholder. Final footage and narration are pending."
    draw_text(draw, caption, (76, 847, 1768, 145), font, 34, "#f6f7f2")
    label = scene["evidence_label"]
    if mode == "animatic":
        label = f"SILENT ANIMATIC | PLANNED CONTENT | {label}"
    else:
        label = f"{label} | Narration: ElevenLabs"
    draw_text(draw, label, (76, 1021, 1768, 42), font, 23, "#bdd0a5")
    canvas.save(output)


def make_placeholder(scene: dict[str, Any], font: str, output: Path) -> None:
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#f6f7f2")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((200, 230, 1720, 850), radius=40, fill="#e7ecdf", outline="#bdd0a5", width=2)
    draw_text(draw, "PLANNED SHOT", (288, 313, 1344, 65), font, 31, "#567653")
    draw_text(draw, scene["title"], (288, 410, 1344, 235), font, 80, "#153f35")
    draw_text(draw, "Footage will be captured after the system is ready.", (288, 710, 1344, 90), font, 36, "#567653")
    canvas.save(output)


def timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def subtitles(scenes: list[dict[str, Any]], mode: str) -> str:
    import textwrap

    entries, offset = [], 0.0
    for scene in scenes:
        spoken = str(scene.get("narration") or scene.get("caption") or scene["title"])
        lines = textwrap.wrap(spoken, width=44, break_long_words=False, break_on_hyphens=False)
        chunks = ["\n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]
        # Timing is proportionally estimated from text, not word-aligned speech.
        span = scene.get("audio_duration_seconds", scene["duration_seconds"])
        weights = [len(chunk) for chunk in chunks]
        elapsed = 0.0
        for chunk, weight in zip(chunks, weights):
            end = elapsed + span * weight / sum(weights)
            body = f"[PLANNED NARRATION, SILENT ANIMATIC]\n{chunk}" if mode == "animatic" else chunk
            entries.append(f"{len(entries) + 1}\n{timestamp(offset + elapsed)} --> {timestamp(offset + end)}\n{body}\n")
            elapsed = end
        offset += scene["duration_seconds"]
    return "\n".join(entries)


def verify_output(path: Path, mode: str, ffmpeg: str, ffprobe: str) -> dict[str, Any]:
    info = probe(path, ffprobe)
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
    audio = next((s for s in info["streams"] if s.get("codec_type") == "audio"), {})
    checks = {
        f"duration_{LENGTH}_seconds": abs(float(info["format"]["duration"]) - LENGTH) <= 0.001,
        "resolution_1920x1080": (video.get("width"), video.get("height")) == (WIDTH, HEIGHT),
        "frame_rate_30": video.get("avg_frame_rate") == "30/1",
        f"frame_count_{LENGTH * FPS}": int(video.get("nb_frames", 0)) == LENGTH * FPS,
        "video_h264": video.get("codec_name") == "h264",
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "audio_aac_stereo_48khz": audio.get("codec_name") == "aac" and audio.get("channels") == 2 and audio.get("sample_rate") == "48000",
    }
    failed = [key for key, valid in checks.items() if not valid]
    if failed:
        raise DemoError(f"Rendered video failed validation: {', '.join(failed)}")
    # Decode every frame and sample to catch corruption that metadata misses.
    run([ffmpeg, "-v", "error", "-xerror", "-nostdin", "-i", str(path), "-f", "null", "-"])
    checks["complete_decode"] = True
    details: dict[str, Any] = {"checks": checks, "duration_seconds": float(info["format"]["duration"]), "bytes": path.stat().st_size}
    if mode == "final":
        output = run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(path), "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
        match = re.search(r'\{\s*"input_i".*?\}', output, re.DOTALL)
        if match:
            details["measured_audio_loudness"] = json.loads(match.group(0))
        if not match or not math.isfinite(float(details["measured_audio_loudness"]["input_i"])):
            raise DemoError("Final output audio could not be verified as non-silent")
    return details


def assemble(args: argparse.Namespace) -> Path:
    ffmpeg, ffprobe = executable(args.ffmpeg), executable(args.ffprobe)
    plan_path = args.timeline.expanduser().resolve()
    plan = load_timeline(plan_path, args.mode)
    timeline_hash = file_hash(plan_path)
    scenes = inspect_inputs(plan, plan_path.parent, args.mode, ffmpeg, ffprobe)
    if args.check:
        print(json.dumps({"status": "inputs_validated", "mode": args.mode, "seconds": LENGTH, "scenes": len(scenes), "ffmpeg": ffmpeg, "ffprobe": ffprobe}, indent=2))
        return plan_path
    try:
        import PIL  # noqa: F401
    except ImportError as exc:
        raise DemoError("Pillow is required for video cards. Use the bundled Python runtime or install Pillow.") from exc
    font = find_font(args.font)
    output = args.output.expanduser().resolve()
    if output.suffix.lower() != ".mp4":
        raise DemoError("Output must end in .mp4")
    if output in {scene.get(kind) for scene in scenes for kind in ("audio", "image", "video")}:
        raise DemoError("Output path must not overwrite source media")
    sidecars = [output.with_suffix(".srt"), output.with_suffix(".report.json")]
    if not args.overwrite and any(path.exists() for path in [output, *sidecars]):
        raise DemoError("An output already exists. Choose a new filename or pass --overwrite.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="falsify-demo-", dir=output.parent) as temporary:
        work = Path(temporary)
        clips: list[Path] = []
        rendering_scenes = []
        for index, scene in enumerate(scenes, 1):
            snapshot = dict(scene)
            for kind in ("image", "video", "audio"):
                if scene.get(kind):
                    snapshot[kind] = work / f"source-{index:02d}-{kind}{scene[kind].suffix}"
                    shutil.copyfile(scene[kind], snapshot[kind])
                    if file_hash(snapshot[kind]) != scene[f"{kind}_sha256"]:
                        raise DemoError(f"{scene['id']} {kind} changed during input inspection. Retry with stable input files.")
            rendering_scenes.append(snapshot)
        for index, scene in enumerate(rendering_scenes, 1):
            print(f"Rendering {args.mode} scene {index}/{len(scenes)}: {scene['id']}", flush=True)
            overlay = work / f"overlay-{index:02d}.png"
            make_overlay(scene, args.mode, font, overlay, index, len(scenes))
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
            if scene.get("video"):
                command += ["-ss", str(scene.get("video_start_seconds", 0)), "-i", str(scene["video"])]
            else:
                still = scene.get("image")
                if not still:
                    still = work / f"placeholder-{index:02d}.png"
                    make_placeholder(scene, font, still)
                command += ["-loop", "1", "-framerate", str(FPS), "-i", str(still)]
            command += ["-loop", "1", "-framerate", str(FPS), "-i", str(overlay)]
            if args.mode == "final":
                command += ["-i", str(scene["audio"])]
                audio_filter = "loudnorm=I=-16:TP=-1.5:LRA=11:linear=false,aresample=48000,"
            else:
                command += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                audio_filter = ""
            seconds = scene["duration_seconds"]
            filters = (
                "[0:v]fps=30,scale=1776:652:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:154+(652-ih)/2:color=0xf6f7f2,setsar=1[base];"
                "[base][1:v]overlay=0:0:format=auto,format=yuv420p[v];"
                f"[2:a]{audio_filter}aformat=sample_rates=48000:channel_layouts=stereo,"
                f"apad=whole_dur={seconds},atrim=duration={seconds},asetpts=PTS-STARTPTS[a]"
            )
            clip = work / f"scene-{index:02d}.mkv"
            command += ["-filter_complex", filters, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf), "-r", "30", "-frames:v", str(round(seconds * FPS)), "-c:a", "pcm_s16le", "-t", str(seconds), str(clip)]
            run(command)
            clips.append(clip)
        concat = work / "concat.txt"
        # Generated basenames have no shell or concat escaping requirements.
        concat.write_text("".join(f"file '{clip.name}'\n" for clip in clips), encoding="utf-8")
        rendered = work / "render.mp4"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "concat", "-safe", "1", "-i", str(concat), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-af", f"aresample=48000:async=1:first_pts=0,apad,atrim=duration={LENGTH}", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", str(LENGTH), "-movflags", "+faststart", str(rendered)])
        quality = verify_output(rendered, args.mode, ffmpeg, ffprobe)
        report: dict[str, Any] = {
            "status": "technical_checks_passed", "mode": args.mode,
            "submission_ready": False, "review_required": "Review full video, subtitle timing, evidence and voice attribution before submission.",
            "timeline": str(plan_path), "timeline_sha256": timeline_hash,
            "output": str(output), "silent": args.mode == "animatic",
            "voice_declared": plan.get("voice") if args.mode == "final" else None,
            "subtitle_timing": "Approximate, distributed across source narration duration; review before submission.",
            "ffmpeg": ffmpeg, "ffprobe": ffprobe, "font": font, "quality": quality,
            "scenes": [{key: str(value) if isinstance(value, Path) else value for key, value in scene.items()} for scene in scenes],
        }
        srt = work / "render.srt"
        srt.write_text(subtitles(scenes, args.mode), encoding="utf-8")
        report_file = work / "render.report.json"
        report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        rendered.replace(output)
        srt.replace(sidecars[0])
        report_file.replace(sidecars[1])
    print(f"Created {output}\nSubtitles: {sidecars[0]}\nReport: {sidecars[1]}")
    return output


def main() -> int:
    global LENGTH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--mode", choices=("animatic", "final"), required=True)
    parser.add_argument("--duration-seconds", type=int, choices=(60, 120), default=120)
    parser.add_argument("--output", type=Path, default=Path("output/demo-video/falsify-demo.mp4"))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--font", help="Path to a TrueType/OpenType font")
    parser.add_argument("--preset", choices=("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"), default="veryfast")
    parser.add_argument("--crf", type=int, choices=range(0, 36), default=18)
    parser.add_argument("--check", action="store_true", help="Validate the timeline and input media without rendering")
    parser.add_argument("--overwrite", action="store_true")
    try:
        args = parser.parse_args()
        LENGTH = args.duration_seconds
        assemble(args)
    except (DemoError, OSError) as exc:
        print(f"Demo render failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
