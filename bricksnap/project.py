"""Read and write a project folder. See "Project folder" in docs/ARCHITECTURE.md.

projects/<name>/
  project.json       name, seed file, size in studs, up axis, hollow or solid, the brief
  seed.<ext>         a copy of the input model
  design.base.npz    the Design exactly as voxelised from the seed (never edited)
  design.npz         the current Design arrays
  design.json        named regions, detail parts and the edit log
  build.json         the parts, their steps and the check report
  build.rough.json   the plain conversion's build, kept for before-and-after pictures
  build.ldr          the LDraw file
  parts.csv          the parts list (written by 'bricksnap export')
  wanted_list.xml    the same list in BrickLink's upload format
  renders/           pictures
  designer/          transcripts of AI design runs
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from bricksnap.types import Build, Design, write_text_atomic


class ProjectError(ValueError):
    """Something is wrong with a project folder. The message is written for a non-programmer."""


def slug(name: str) -> str:
    """A safe folder name made from any text."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s or "model"


class Project:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        meta_file = self.path / "project.json"
        if not meta_file.exists():
            raise ProjectError(f"{self.path} is not a BrickSnap project (no project.json in it).")
        self.meta: dict[str, Any] = json.loads(meta_file.read_text(encoding="utf-8"))

    # ---- creating and opening -------------------------------------------------------------

    @classmethod
    def create(
        cls,
        path: str | Path,
        seed_file: str | Path,
        *,
        studs: int,
        up: str | None = None,
        hollow: bool = False,
        name: str | None = None,
    ) -> Project:
        """Make a new project folder and copy the seed model into it."""
        path = Path(path)
        seed_file = Path(seed_file)
        if not seed_file.exists():
            raise ProjectError(f"Cannot find the model file {seed_file}.")
        if (path / "project.json").exists():
            raise ProjectError(f"{path} already holds a project. Choose another name.")
        path.mkdir(parents=True, exist_ok=True)
        seed_copy = "seed" + seed_file.suffix.lower()
        shutil.copyfile(seed_file, path / seed_copy)
        meta = {
            "name": name or seed_file.stem,
            "seed": seed_copy,
            "seed_original_name": seed_file.name,
            "studs": int(studs),
            "up": up,
            "hollow": bool(hollow),
            "brief": None,
        }
        write_text_atomic(path / "project.json", json.dumps(meta, indent=1) + "\n")
        return cls(path)

    def save_meta(self) -> None:
        write_text_atomic(self.path / "project.json", json.dumps(self.meta, indent=1) + "\n")

    # ---- files ----------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return str(self.meta.get("name", self.path.name))

    @property
    def seed_path(self) -> Path:
        return self.path / self.meta["seed"]

    @property
    def renders_dir(self) -> Path:
        d = self.path / "renders"
        d.mkdir(exist_ok=True)
        return d

    @property
    def designer_dir(self) -> Path:
        d = self.path / "designer"
        d.mkdir(exist_ok=True)
        return d

    @property
    def design_path(self) -> Path:
        return self.path / "design.npz"

    @property
    def build_path(self) -> Path:
        return self.path / "build.json"

    @property
    def rough_build_path(self) -> Path:
        return self.path / "build.rough.json"

    @property
    def ldraw_path(self) -> Path:
        return self.path / "build.ldr"

    # ---- design ---------------------------------------------------------------------------

    def has_design(self) -> bool:
        return self.design_path.exists()

    def save_design(self, design: Design, *, base: bool = False) -> None:
        """Save the current Design. With ``base=True`` also record it as the untouched base."""
        if base:
            design.save(self.path / "design.base.npz")
        design.save(self.design_path, self.path / "design.json")

    def load_design(self, *, base: bool = False) -> Design:
        if base:
            f = self.path / "design.base.npz"
            if not f.exists():
                raise ProjectError(
                    f"{self.path} has no base design yet. Run 'bricksnap new' first."
                )
            return Design.load(f)
        if not self.design_path.exists():
            raise ProjectError(f"{self.path} has no design yet. Run 'bricksnap new' first.")
        return Design.load(self.design_path, self.path / "design.json")

    # ---- build ----------------------------------------------------------------------------

    def has_build(self) -> bool:
        return self.build_path.exists()

    def save_build(self, build: Build) -> None:
        build.save(self.build_path)

    def load_build(self) -> Build:
        if not self.build_path.exists():
            raise ProjectError(f"{self.path} has not been built yet. Run 'bricksnap build' first.")
        return Build.load(self.build_path)

    def build_is_current(self, design: Design | None = None, build: Build | None = None) -> bool:
        """True when the saved Build was made from the Design as it is now.

        Compares the Design's fingerprint with the one recorded in the Build, so it does not
        depend on file times. Pass ``design`` or ``build`` if you already have them loaded.
        """
        if not self.has_design() or not self.has_build():
            return False
        design = design if design is not None else self.load_design()
        build = build if build is not None else self.load_build()
        return bool(build.design_id) and build.design_id == design.fingerprint()
