"""Engine preview cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import hashlib
import re
from pathlib import Path
from reportforge.renderer import errors as _rerrors
from reportforge.renderer import poppler as _rpoppler
from reportforge.renderer import toolchain as _rtoolchain



def render_preview(project: str, revision: int | None = None) -> dict:
    """Render preview artifacts (contact sheet, pages, exhibits) for a report.

    Contract §5: previews bind to (report_id, revision), are generated only
    from that revision's rendered PDF (no auto-render), live under
    <project>/output/previews/r<rev>/, and are returned as §3.2-shaped
    relative-path artifact descriptors — never host absolute paths.
    Read-only: the manifest revision is never bumped.

    PDF-staleness rule: the PDF must have been rendered from the current
    manifest revision (stamped in .reportforge-state.json at render time).
    A stamped-but-older PDF fails loudly; an unstamped legacy PDF proceeds
    with a warning and pdf_rendered_at_revision null. The same rule covers
    the registry binding (R2): a registration after the render fails loudly
    and names both registry versions.
    """
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _E._load_or_import(root)
    if err:
        return err
    assert manifest is not None
    current = manifest.revision
    if revision is not None and revision != current:
        return {
            "ok": False,
            "error": f"stale revision: requested {revision}, manifest is at revision {current}",
            "current_revision": current,
        }
    rev = current
    warnings: list[str] = []

    pdf_rev = _E._render_state_revision(root)
    if pdf_rev is not None and pdf_rev != rev:
        return {
            "ok": False,
            "error": (f"PDF was rendered from revision {pdf_rev} but the manifest "
                      f"is at revision {rev}: render_report first (a content edit "
                      f"invalidates previews)"),
            "current_revision": rev,
            "pdf_rendered_at_revision": pdf_rev,
        }
    if pdf_rev is None:
        warnings.append("PDF predates revision stamping; re-render to bind "
                        "previews to an exact revision")
    pdf_reg = _E._render_state_registry_version(root)
    current_reg = manifest.registry_version
    if pdf_reg is not None and pdf_reg != current_reg:
        return {
            "ok": False,
            "error": (f"PDF was rendered at registry v{pdf_reg} but the manifest "
                      f"is at registry v{current_reg}: render_report first (a "
                      "registration changes render inputs without bumping revision)"),
            "current_revision": rev,
            "pdf_rendered_at_revision": pdf_rev,
            "pdf_rendered_at_registry_version": pdf_reg,
            "current_registry_version": current_reg,
        }
    if pdf_rev is not None and pdf_reg is None:
        # Finding 6: symmetric leniency — a stamped revision with no
        # registry stamp (hand-edited or pre-binding state) warns rather
        # than silently skipping the R2 binding.
        warnings.append("state file predates registry binding; re-render to bind "
                        "previews to an exact registry version")

    pdftoppm = _rtoolchain.which("pdftoppm")
    if not pdftoppm:
        return {"ok": False, "error": "pdftoppm not found on PATH (previews unavailable)"}

    out_dir = _E._output_dir_of(root)
    if out_dir == root and (root / "output").is_dir():
        out_dir = root / "output"
    pdf = out_dir / "index.pdf"
    if not pdf.is_file():
        return {
            "ok": False,
            "error": f"no rendered PDF for revision {rev}: render first (previews never auto-render), missing {pdf.name}",
        }

    previews_dir = out_dir / "previews" / f"r{rev}"
    try:
        previews_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"cannot create previews dir: {exc}"}

    page_count = _E._pdf_page_count(pdf)
    if page_count < 1:
        return {"ok": False, "error": f"cannot count pages in {pdf.name}: not a readable PDF"}

    pages_dir = previews_dir / "pages"
    try:
        pages_dir.mkdir(parents=True, exist_ok=True)
        run = _rpoppler.raster_pages(pdftoppm, pdf, pages_dir)
        if run.returncode != 0:
            return {"ok": False, "error": f"pdftoppm page raster failed: {run.stderr.strip()}"}
    except _rerrors.ToolTimeoutError:
        return {"ok": False, "error": "pdftoppm page raster timed out (120s)"}
    except OSError as exc:
        return {"ok": False, "error": f"pdftoppm page raster failed: {exc}"}

    page_files = sorted(pages_dir.glob("page-*.png"), key=_page_sort_key)
    unnumbered = pages_dir / "page.png"
    if not page_files and unnumbered.is_file():
        # poppler names single-page output <prefix>.png (no page number)
        numbered = pages_dir / "page-1.png"
        numbered.write_bytes(unnumbered.read_bytes())
        unnumbered.unlink()
        page_files = [numbered]
    if not page_files:
        return {"ok": False, "error": "pdftoppm produced no page PNGs"}

    contact = _build_contact_sheet(page_files, previews_dir / "contact-sheet.png")
    if contact is None:
        return {"ok": False, "error": "contact sheet composition failed (no page PNGs readable)"}

    artifacts: list[dict] = []
    skipped_previews: list[str] = []
    desc = _describe_or_skip(root, f"output/previews/r{rev}/contact-sheet.png",
                             "contact-sheet", "preview", "image/png", skipped_previews)
    if desc is not None:
        artifacts.append(desc)
    for p in _numbered_pages(page_files):
        desc = _describe_or_skip(root, f"output/previews/r{rev}/pages/page-{p}.png",
                                 f"page-{p}", "preview", "image/png", skipped_previews)
        if desc is not None:
            artifacts.append(desc)

    charts_dir = root / "charts"
    if charts_dir.is_dir():
        for chart in sorted(charts_dir.glob("*.png")):
            desc = _describe_or_skip(root, f"charts/{chart.name}",
                                     f"exhibit-{chart.stem}", "preview", "image/png",
                                     skipped_previews)
            if desc is not None:
                artifacts.append(desc)
    if skipped_previews:
        warnings.append("artifacts vanished mid-build and were skipped: "
                        + ", ".join(sorted(skipped_previews)))

    return {
        "ok": True,
        "report_id": manifest.report_id,
        "revision": rev,
        "page_count": page_count,
        "pdf_rendered_at_revision": pdf_rev,
        "artifacts": artifacts,
        "warnings": warnings,
        "next_step": "retrieve artifacts via read_project_file (binary) or export bundle §3",
    }


def _page_sort_key(p: Path) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.png$", p.name)
    return (int(m.group(1)),) if m else (10**9,)


def _numbered_pages(page_files: list[Path]) -> list[int]:
    nums: list[int] = []
    for p in page_files:
        m = re.search(r"(\d+)\.png$", p.name)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def _build_contact_sheet(page_files: list[Path], dest: Path) -> Path | None:
    """Tile page PNGs into one contact sheet PNG (Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    tile_w = 360
    cols = 4
    thumbs: list[Image.Image] = []
    for pf in page_files:
        try:
            img = Image.open(pf)
            img.load()
        except Exception:
            continue
        ratio = tile_w / img.width
        thumbs.append(img.resize((tile_w, max(1, round(img.height * ratio)))))
    if not thumbs:
        return None
    rows = (len(thumbs) + cols - 1) // cols
    tile_h = max(t.height for t in thumbs)
    pad = 12
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * pad, rows * tile_h + (rows + 1) * pad), (24, 24, 28))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (pad + c * (tile_w + pad), pad + r * (tile_h + pad)))
    sheet.save(dest, format="PNG")
    return dest


def _describe_or_skip(root: Path, relpath: str, artifact_id: str, role: str,
                      mime: str, skipped: list[str]) -> dict | None:
    """Describe one artifact; on a glob→read race record it and skip."""
    desc = _file_descriptor(root, relpath, artifact_id, role, mime)
    if desc is None:
        skipped.append(artifact_id)
    return desc


def _file_descriptor(root: Path, relpath: str, artifact_id: str, role: str, mime: str) -> dict | None:
    """§3.2 artifact descriptor for a file under a project/bundle root.

    Returns None when the file vanishes mid-build (glob→read race) instead
    of raising across the tool boundary (§2.5 no-exceptions convention);
    callers skip None and record which handle went missing.
    """
    p = root / relpath
    try:
        data = p.read_bytes()
    except OSError:
        return None
    return {
        "id": artifact_id,
        "path": relpath,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mime": mime,
        "role": role,
    }


