"""Prepare Flow answer clips for the concierge screen.

  python prepare_clips.py <folder with Flow downloads> <avatar-frontend/public/videos/library>

- Renames "service_home_1080p_2026....mp4" -> "service_home.mp4"
- Cuts the silent start/end so she answers quickly and doesn't stand there
- Makes every clip the same loudness
Needs ffmpeg on PATH.
"""
import json, re, subprocess, sys
from pathlib import Path

LEAD = 0.35   # seconds kept before she starts speaking
TAIL = 0.80   # seconds kept after she stops (her closing smile)
STEP = 0.1

def loudness(path):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af",
        "aresample=48000,asetnsamples=n=4800,astats=metadata=1:reset=1,"
        "ametadata=print:key=lavfi.astats.Overall.RMS_level", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    vals = []
    for v in re.findall(r"RMS_level=(\S+)", out):
        vals.append(-120.0 if "inf" in v else float(v))
    return vals

def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)

def speech_window(path):
    rms = loudness(path)
    floor = sorted(rms)[len(rms) // 5]
    threshold = max(floor + 15, -30)  # real speech, not room hum
    loud = [i for i, v in enumerate(rms) if v > threshold]
    if not loud:
        return None
    return loud[0] * STEP, (loud[-1] + 1) * STEP

def main(src, dst):
    src, dst = Path(src), Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    report = {}
    for f in sorted(src.glob("*.mp4")):
        name = re.sub(r"^[0-9a-f]{8}-", "", f.stem)          # upload prefix
        name = re.sub(r"_1080p(_\d+)?$", "", name)           # Flow suffix
        dur = duration(f)
        win = speech_window(f)
        if not win:
            print(f"SKIP {f.name}: no speech found"); continue
        start = max(0.0, win[0] - LEAD)
        end = min(dur, win[1] + TAIL)
        length = end - start
        out = dst / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", str(f), "-t", f"{length:.2f}",
            "-af", f"loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:d=0.05,afade=t=out:st={length-0.15:.2f}:d=0.15,aresample=48000",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
        report[name] = {"from": f.name, "start": round(start, 2), "end": round(end, 2),
                        "speech": [round(win[0], 2), round(win[1], 2)]}
        print(f"{name:32s} speech {win[0]:4.1f}-{win[1]:4.1f}s  -> clip {length:4.1f}s")
    return report

if __name__ == "__main__":
    r = main(sys.argv[1], sys.argv[2])
    print(f"{len(r)} clips ready.")
