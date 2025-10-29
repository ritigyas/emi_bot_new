import subprocess, os, sys

# Change these to your test files
BASE_VIDEO = "images\WhatsApp Video 2025-10-30 at 00.34.24_510e6cc9.mp4"
LOAN_IMG = "images\1.png"
EMI_IMG  = "images\2.png"
BANK_IMG = "images\3.png"
OUT_VIDEO = "output/hindi/001_final_test.mp4"

# Create output dir
os.makedirs(os.path.dirname(OUT_VIDEO), exist_ok=True)

# Overlay positions (x,y) in pixels on 1280x720. Adjust to taste.
OVERLAY_X = 80
OVERLAY_Y = 400

# Timings in seconds (edit to match your base video’s planned windows)
loan_start, loan_end = 5.5, 7.0
emi_start, emi_end   = 7.0, 9.0
bank_start, bank_end = 9.0, 11.0

# Build filter_complex chain:
# - Show loan image between loan_start..loan_end
# - Then emi image between emi_start..emi_end
# - Then bank image between bank_start..bank_end
filter_complex = f"""
[0:v][1:v]overlay=enable='between(t,{loan_start},{loan_end})':x={OVERLAY_X}:y={OVERLAY_Y}[v1];
[v1][2:v]overlay=enable='between(t,{emi_start},{emi_end})':x={OVERLAY_X}:y={OVERLAY_Y}[v2];
[v2][3:v]overlay=enable='between(t,{bank_start},{bank_end})':x={OVERLAY_X}:y={OVERLAY_Y}[vout]
""".strip()

# Build ffmpeg command (video overlays only; original audio passed through)
cmd = [
    "ffmpeg",
    "-y",
    "-i", BASE_VIDEO,     # 0
    "-i", LOAN_IMG,       # 1
    "-i", EMI_IMG,        # 2
    "-i", BANK_IMG,       # 3
    "-filter_complex", filter_complex,
    "-map", "[vout]",
    "-map", "0:a?",
    "-c:v", "libx264",
    "-c:a", "aac",
    "-shortest",
    OUT_VIDEO
]

print("Running:\n", " ".join(cmd))
subprocess.run(cmd, check=True)
print("✅ Done:", OUT_VIDEO)