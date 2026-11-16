"""Extract a zip archive. Usage: python3 -I unzip.py <zip> <dest_dir>"""

import os
import sys
import zipfile

dest = os.path.realpath(sys.argv[2])
with zipfile.ZipFile(sys.argv[1]) as z:
    for m in z.infolist():
        target = os.path.realpath(os.path.join(dest, m.filename))
        if not target.startswith(dest + os.sep) and target != dest:
            raise SystemExit(f"unsafe path in zip: {m.filename}")
    z.extractall(dest)
