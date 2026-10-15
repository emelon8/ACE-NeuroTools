import os
import shutil
import subprocess

# Run from the installed development environment; preserve configured data roots.
from aceneurotools.shared.paths import PROJECT_ROOT

src_dir = PROJECT_ROOT / "data_types"
dst_dir = PROJECT_ROOT / "tests/data/sample_recording/ONIX"
os.makedirs(dst_dir, exist_ok=True)

for f in os.listdir(src_dir):
    src_file = os.path.join(src_dir, f)
    dst_file = os.path.join(dst_dir, f)

    if os.path.isdir(src_file):
        continue

    print(f"Processing {f}...")

    if f.endswith(".raw"):
        # Truncate to first 1 MB for .raw data files
        with open(src_file, "rb") as fin:
            data = fin.read(1024 * 1024)
        with open(dst_file, "wb") as fout:
            fout.write(data)

    elif f.endswith(".avi"):
        # Truncate to 100 frames using ffmpeg
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src_file, "-frames:v", "100", "-c", "copy", dst_file]
        )

    elif f.endswith(".csv"):
        # Truncate to 1000 lines
        with open(src_file, encoding="utf-8", errors="ignore") as fin:
            lines = []
            for i, line in enumerate(fin):
                if i >= 1000:
                    break
                lines.append(line)
        with open(dst_file, "w", encoding="utf-8") as fout:
            fout.writelines(lines)

    else:
        # Just copy if it's something else
        shutil.copy(src_file, dst_file)

print(f"Truncated ONIX files generated at: {dst_dir}")
