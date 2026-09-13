"""Engine release cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import hashlib
import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from reportforge import manifest as manifest_mod



def _release_summary(root: Path) -> dict | None:
    """Sealed-release projection for status views; None when unsealed."""
    try:
        record = _read_release_record(_E._output_dir_of(root))
    except (OSError, ValueError):
        return None
    if not record:
        return None
    return {"release_id": record.get("release_id"),
            "revision": record.get("revision"),
            "registry_version": record.get("registry_version"),
            "artifacts": sorted(record.get("artifacts", {}))}


def _registry_content_hash(root: Path) -> str:
    """sha256 over registry render inputs (sources.bib + figures/)."""
    h = hashlib.sha256()
    bib = root / "sources.bib"
    if bib.is_file():
        try:
            h.update(bib.read_bytes())
        except OSError:
            pass
    figs = root / "figures"
    if figs.is_dir():
        try:
            members = sorted(figs.rglob("*"))
        except OSError:
            members = []
        for p in members:
            if p.is_file():
                try:
                    h.update(str(p.relative_to(root)).encode())
                    h.update(b"\0")
                    h.update(hashlib.sha256(p.read_bytes()).digest())
                except OSError:
                    pass
    return h.hexdigest()


def _release_inputs(workdir: Path, manifest, toolchain: dict) -> dict:
    """Compute the snapshot identity (no I/O beyond hashing)."""
    qmd_bytes = (workdir / "index.qmd").read_bytes()
    qmd_sha = hashlib.sha256(qmd_bytes).hexdigest()
    reg_sha = _registry_content_hash(workdir)
    rid = hashlib.sha256(
        f"{qmd_sha}|{reg_sha}|{toolchain.get('quarto')}|"
        f"{toolchain.get('python')}|{toolchain.get('reportforge')}|"
        f"{manifest.template_version}".encode()).hexdigest()[:12]
    return {"release_id": rid, "qmd_sha256": qmd_sha,
            "registry_sha256": reg_sha, "toolchain": toolchain,
            "template_version": manifest.template_version,
            "revision": manifest.revision,
            "registry_version": manifest.registry_version}


def _read_release_record(out_dir: Path) -> dict | None:
    try:
        return json.loads((out_dir / "release.json").read_text())
    except (OSError, ValueError):
        return None


def _write_release_record(out_dir: Path, record: dict) -> None:
    tmp = out_dir / f".release.json.tmp-{os.getpid()}"
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    os.replace(tmp, out_dir / "release.json")


def freeze_release(project: str) -> dict:
    """Re-seal + verify output/release.json against CURRENT inputs (RF-09).

    Fails loudly when the inputs drifted (qmd/registry/toolchain/template)
    or an artifact is missing/changed on disk — a stale seal must never
    pass as verified. Rewriting the sealed file is the explicit re-seal.
    """
    slug = project.strip("/")
    root = _E.REPORTS_DIR / slug
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    out_dir = _E._output_dir_of(root)
    with _E._project_lock(root):
        record = _read_release_record(out_dir)
        if record is None:
            return {"ok": False,
                    "error": "no release snapshot sealed yet: render_report first"}
        manifest, err = _E._load_or_import(root)
        if err:
            return err
        assert manifest is not None
        try:
            current = _release_inputs(root, manifest, _E._toolchain_stamp())
        except OSError as exc:
            return {"ok": False, "error": f"cannot hash release inputs: {exc}"}
        if current["release_id"] != record.get("release_id"):
            return {
                "ok": False,
                "error": (f"render inputs changed since release {record.get('release_id')} "
                          f"(now {current['release_id']}): re-render all formats together, then freeze again"),
                "sealed_release_id": record.get("release_id"),
                "current_release_id": current["release_id"],
            }
        for fmt in sorted(record.get("artifacts", {})):
            art = record["artifacts"][fmt]
            p = Path(art.get("path", ""))
            try:
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                return {"ok": False,
                        "error": f"release artifact missing on disk: {fmt} -> {art.get('path')}"}
            if digest != art.get("sha256"):
                return {"ok": False,
                        "error": f"release artifact changed on disk: {fmt} -> {art.get('path')}"}
        try:
            _write_release_record(out_dir, record)
        except OSError as exc:
            return {"ok": False, "error": f"could not re-seal release record: {exc}"}
        return {"ok": True, "report_id": manifest.report_id,
                "release_id": record.get("release_id"), "verified": True,
                "artifacts": sorted(record.get("artifacts", {}))}


@_E._section_op_errors
def rollforward_report(project: str, new_slug: str, brief: str = "",
                       params: dict | None = None) -> dict:
    """Birth a next-period report from a finished one (RF-09).

    Copies index.qmd/_quarto.yml/sources.bib/figures(+styles/brand/assets)
    but NEVER output/, state, lock, or the old manifest. Registries
    deep-copy with registry_version preserved (independent counters —
    content revision restarts at 1); supersedes records the lineage.
    Returns carried counts plus the stale / unknown_vintage refresh
    checklist against params.as_of (required ISO-8601 date).
    """
    if not isinstance(brief, str) or not brief.strip():
        return {"ok": False,
                "error": "a new brief is required: the next period needs its own mandate"}
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return {"ok": False, "error": "params must be a map (period, as_of, ...)"}
    cutoff = _E._parse_asof(params.get("as_of"))
    if cutoff is None:
        return {"ok": False,
                "error": f"params.as_of must be an ISO-8601 date (got {params.get('as_of')!r}): "
                         "the stale-facts checklist needs a reference date"}
    slug = "".join(c if c.isalnum() or c in "-_" else "-"
                   for c in new_slug.strip().lower())
    if not slug:
        return {"ok": False,
                "error": "new_slug must contain at least one letter, number, '-' or '_'"}
    src_root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert src_root is not None
    dst = _E.REPORTS_DIR / slug
    if dst.exists():
        return {"ok": False, "error": f"report {slug!r} already exists at {dst}"}
    with _E._project_lock(src_root):
        src_manifest, err = _E._load_or_import(src_root)
        if err:
            return err
        assert src_manifest is not None
        src_reg = src_manifest.registry_version
        src_profile = json.loads(json.dumps(src_manifest.profile))
        src_formats = list(src_manifest.formats)
        src_title = src_manifest.title
        sealed = _read_release_record(_E._output_dir_of(src_root))
        src_release_id = (sealed or {}).get("release_id")
        # Review F2: the tree copy happens under the source lock so a
        # concurrent writer cannot tear the copy mid-flight.
        try:
            shutil.copytree(src_root, dst,
                            ignore=shutil.ignore_patterns(*_E._ROLLFORWARD_SKIP))
        except OSError as exc:
            return {"ok": False,
                    "error": f"could not copy report tree: {exc}"}
    _E._set_frontmatter_description(dst / "index.qmd", brief.strip())
    title = params.get("title") or src_title
    with _E._project_lock(dst):
        new_manifest = manifest_mod.create(
            str(dst), title=title, brief=brief.strip(),
            profile=src_profile, formats=src_formats,
            actor="tool:rollforward", template_version=_E.template_version())
        # Provenance survives the period boundary (JSON round-trip =
        # deep copy; records are JSON by construction).
        new_manifest.sources = json.loads(json.dumps(src_manifest.sources))
        new_manifest.exhibits = json.loads(json.dumps(src_manifest.exhibits))
        new_manifest.facts = json.loads(json.dumps(src_manifest.facts))
        new_manifest.registry_version = src_reg
        # A new period has no commissioning record: report_brief stays {}
        # (the lineage lives in supersedes below).
        new_manifest.supersedes = {
            "report": src_manifest.report_id,
            "release_id": src_release_id,
            "period": params.get("period", ""),
            "as_of": params.get("as_of"),
        }
        new_manifest.revision_log.append({
            "revision": 1,
            "timestamp": new_manifest.updated,
            "actor": "tool:rollforward",
            "op": "rollforward",
            "section_id": None,
            "summary": (f"rolled from {src_manifest.report_id} "
                        f"(registry v{src_reg}, release {src_release_id})"),
        })
        manifest_mod.save(new_manifest, str(dst))
    stale = sorted(
        fid for fid, rec in new_manifest.facts.items()
        if (d := _E._parse_asof(rec.get("as_of"))) is not None and d < cutoff)
    unknown = sorted(
        fid for fid in new_manifest.facts
        if _E._parse_asof(new_manifest.facts[fid].get("as_of")) is None)
    return {"ok": True, "report_id": slug, "path": str(dst),
            "supersedes": dict(new_manifest.supersedes),
            "carried": {"sources": len(new_manifest.sources),
                        "exhibits": len(new_manifest.exhibits),
                        "facts": len(new_manifest.facts)},
            "stale": stale, "unknown_vintage": unknown,
            "registry_version": new_manifest.registry_version}


def _bundle_artifact_id(rel: str) -> tuple[str, str]:
    """(id, role) for a bundle-relative path. Ids are unique by construction.

    Deliverables/previews/charts keep short semantic handles (their source
    dirs are flat with unique stems); everything else derives from the full
    relative path so source/, data/ and *_files/ companions can never
    collide. bundle.json itself is the index — it needs no descriptor.
    """
    p = Path(rel)
    name = p.name
    if name == "manifest.json":
        return "manifest-copy", "metadata"
    if name == "contact-sheet.png":
        return "contact-sheet", "preview"
    m = re.fullmatch(r"page-(\d+)\.png", name)
    if m and "previews" in p.parts:
        return f"page-{m.group(1)}", "preview"
    if p.suffix == ".png" and "previews" in p.parts:
        return f"exhibit-{p.stem}", "preview"
    if name in ("index.pdf", "index.html", "index.docx"):
        return {"index.pdf": "pdf", "index.html": "html",
                "index.docx": "docx"}[name], "deliverable"
    if "charts" in p.parts and p.suffix == ".png":
        return f"exhibit-{p.stem}", "preview"
    if p.parts and p.parts[0] in ("source", "data"):
        return rel.replace("/", "-"), p.parts[0]
    return rel.replace("/", "-"), "companion"


@_E._section_op_errors
def export_release(project: str, revision: int | None = None, dest: str = ".",
                   include_source: bool = False, include_data: bool = False,
                   actor: str = "tool:export_release") -> dict:
    """Export an approved revision as a self-contained bundle (§3).

    Layout: <dest>/<report_id>/r<rev>/ with deliverables, manifest.json copy,
    bundle.json descriptor index, optional source/ + data/. Overwrites are
    atomic per revision dir (rename-aside, never delete-then-rename); a
    successful export transitions the manifest to exported.
    """
    slug = project.strip("/")
    root = _E.REPORTS_DIR / slug
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    with _E._project_lock(root):
        return _export_release_locked(slug, root, revision, dest,
                                      include_source, include_data, actor)


def _export_release_locked(slug: str, root: Path, revision: int | None,
                           dest: str, include_source: bool,
                           include_data: bool, actor: str) -> dict:
    manifest, err = _E._load_or_import(root)
    if err:
        return err
    assert manifest is not None
    current = manifest.revision
    if revision is not None and revision != current:
        return {"ok": False,
                "error": f"stale revision: requested {revision}, manifest is at revision {current}",
                "current_revision": current}
    if manifest.state not in ("approved", "exported"):
        return {"ok": False,
                "error": f"export requires state approved (current: {manifest.state}) — render drafts freely, release only reviewed revisions"}
    out_dir = _E._output_dir_of(root)
    if out_dir == root and (root / "output").is_dir():
        out_dir = root / "output"
    required = [f for f in manifest.to_dict().get("formats", []) if f in _E._BUNDLE_FORMATS]
    missing = [f for f in required if not (out_dir / f"index.{f}").is_file()]
    if missing:
        return {"ok": False,
                "error": f"no rendered output for {', '.join(missing)}: render first (export never auto-renders)"}
    exported_at = datetime.now().astimezone().isoformat()
    dest_root = Path(dest)
    rdir = dest_root / manifest.report_id / f"r{current}"
    tmp = dest_root / manifest.report_id / f".r{current}.tmp-{os.getpid()}"
    aside = dest_root / manifest.report_id / f".r{current}.prev-{os.getpid()}"
    warnings: list[str] = []
    artifacts: list = []
    swapped = False
    try:
        for stale in (tmp, aside):
            if stale.exists():
                shutil.rmtree(stale)
        tmp.mkdir(parents=True)
        for fmt in required:
            shutil.copy2(out_dir / f"index.{fmt}", tmp / f"index.{fmt}")
        for companion in sorted(out_dir.glob("*_files")):
            if companion.is_dir():
                shutil.copytree(companion, tmp / companion.name)
        (tmp / "manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
        # C-4: bundles carry the sealed release record; a report sealed
        # before Milestone C warns (grandfathered) instead of failing.
        if (out_dir / "release.json").is_file():
            shutil.copy2(out_dir / "release.json", tmp / "release.json")
        else:
            warnings.append("no release snapshot sealed for this revision "
                            "(pre-C report?): re-render to bind artifacts to exact inputs")
        prev_src = out_dir / "previews" / f"r{current}"
        if prev_src.is_dir():
            shutil.copytree(prev_src, tmp / "previews")
        includes = {"source": False, "data": False}
        if include_source:
            copied = []
            srcd = tmp / "source"
            srcd.mkdir()
            for name in ("index.qmd", "_quarto.yml", "styles.scss", "_brand.yml"):
                p = root / name
                if p.is_file():
                    shutil.copy2(p, srcd / name)
                    copied.append(name)
            includes["source"] = bool(copied)
            if not copied:
                warnings.append("include_source requested but no source files found")
        if include_data:
            data_src = root / "data"
            data_files = ([p for p in data_src.rglob("*") if p.is_file()]
                          if data_src.is_dir() else [])
            if data_files:
                shutil.copytree(data_src, tmp / "data")
                includes["data"] = True
            else:
                warnings.append("include_data requested but data/ is missing or empty")
        artifacts = []
        skipped: list[str] = []
        for p in sorted(tmp.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(tmp))
            aid, role = _bundle_artifact_id(rel)
            desc = _E._describe_or_skip(tmp, rel, aid, role, _E._mime_for_name(p.name), skipped)
            if desc is not None:
                artifacts.append(desc)
        if skipped:
            warnings.append(f"artifacts vanished mid-build and were skipped: {', '.join(sorted(skipped))}")
        (tmp / "bundle.json").write_text(json.dumps({
            "schema_version": 1,
            "report_id": manifest.report_id,
            "revision": current,
            "exported_at": exported_at,
            "artifacts": artifacts,
            "includes": includes,
            "delivery": {"adapters": ["local-bundle", "deerflow"], "present_paths": []},
        }, indent=2, ensure_ascii=False))
        # Re-read bundle.json into the descriptor list so disk == response.
        artifacts = json.loads((tmp / "bundle.json").read_text())["artifacts"]
        rdir.parent.mkdir(parents=True, exist_ok=True)
        if rdir.exists():
            os.rename(rdir, aside)  # aside first: no crash window without a bundle
        os.rename(tmp, rdir)
        swapped = True
    except Exception as exc:  # noqa: BLE001 — cleanup + loud dict, never partial
        for stale in (tmp, aside):
            try:
                if stale.exists() and stale != rdir:
                    shutil.rmtree(stale)
            except OSError:
                pass
        # The only survivable failure is after a completed swap (e.g. aside
        # cleanup); anything earlier means no new bundle — fail loudly even
        # though a previous bundle may still sit at rdir.
        if not (swapped and rdir.is_dir()):
            return {"ok": False, "error": f"bundle write failed: {exc}"}
    finally:
        # Best-effort aside removal; a leftover .prev dir never shadows rdir.
        try:
            if aside.exists():
                shutil.rmtree(aside)
        except OSError:
            pass
    tr = manifest_mod.transition(manifest, "exported", actor, f"export r{current}")
    if tr.get("ok"):
        manifest_mod.save(manifest, str(root))
    return {
        "ok": True,
        "report_id": manifest.report_id,
        "revision": current,
        "state": manifest.state,
        "bundle_root": str(Path(manifest.report_id) / f"r{current}"),
        "artifacts": artifacts,
        "warnings": warnings,
        "next_step": "retrieve the bundle at <report_id>/r<rev> under the dest root",
    }


