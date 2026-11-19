"""The comparison run: the same session with no tools but one final submit.

    python -m bricksnap.lab.blind "TASK" --out DIR [--model ...] [--reference PICTURE ...]

See ``bricksnap.lab.run``; the work folder gets the same files, made after the session.
"""

from __future__ import annotations

import sys

from bricksnap.lab.run import main

if __name__ == "__main__":
    main(sys.argv[1:], mode="blind")
