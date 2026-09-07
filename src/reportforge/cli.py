"""Command-line interface for reportforge."""

from __future__ import annotations

import argparse
import json
import sys

from reportforge.engine import (
    check_readiness,
    export_release,
    list_templates,
    open_report,
    project_status,
    register_source,
    render_preview,
    render_report,
    reportforge_capabilities,
    save_chart,
    scaffold_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reportforge", description="Quarto-backed report generation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("templates", help="list available templates")
    p_new = sub.add_parser("new", help="scaffold a new report")
    p_new.add_argument("slug")
    p_new.add_argument("--title", default="")
    p_new.add_argument("--subtitle", default="")
    p_new.add_argument("--author", default="")
    p_new.add_argument("--abstract", default="Add a short abstract here.")
    p_new.add_argument("--template", default="standard", choices=[item["name"] for item in list_templates()])
    p_new.add_argument("--firm", default="", help="firm/institution name (whitepaper or modern; also accepted by studio)")
    p_new.add_argument("--organization", default="", help="generic organization or brand name for studio")
    p_new.add_argument("--eyebrow", default="", help="short studio kicker above the title")
    p_new.add_argument("--title-layout", default="hero", choices=["hero", "compact"], help="studio title composition")
    p_new.add_argument("--accent", default="#4f46e5", help="studio accent as a six-digit hex color")
    p_new.add_argument("--confidential-mark", default="", help="optional footer text for modern or studio")
    p_new.add_argument("--kpis", default="", help="legacy modern metric strip as a JSON list")
    p_new.add_argument("--metrics", default="", help="studio metrics as a JSON list of value/label objects (0-6)")
    p_new.add_argument("--formats", default="", help="comma list, e.g. html,pdf,docx")

    p_render = sub.add_parser("render", help="render a report")
    p_render.add_argument("source")
    p_render.add_argument("--formats", default="", help="comma list, e.g. html,pdf,docx")

    p_chart = sub.add_parser("chart", help="export a plotly JSON figure to png+html")
    p_chart.add_argument("fig_json_file")
    p_chart.add_argument("out_basename")
    p_chart.add_argument("--width", type=int, default=1400)
    p_chart.add_argument("--height", type=int, default=700)

    p_status = sub.add_parser("status", help="show a report's manifest view + artifacts")
    p_status.add_argument("project")

    p_open = sub.add_parser("open", help="open a report by slug (brief/profile/sections/revision)")
    p_open.add_argument("project")

    p_ready = sub.add_parser("readiness", help="run readiness checks on a report")
    p_ready.add_argument("project")

    p_preview = sub.add_parser("preview", help="render preview PNGs for a revision")
    p_preview.add_argument("project")
    p_preview.add_argument("--revision", type=int, default=None)

    p_export = sub.add_parser("export", help="export an approved revision as a bundle")
    p_export.add_argument("project")
    p_export.add_argument("dest")
    p_export.add_argument("--revision", type=int, default=None)
    p_export.add_argument("--include-source", action="store_true")
    p_export.add_argument("--include-data", action="store_true")

    p_caps = sub.add_parser("capabilities", help="show capability discovery response")

    p_source = sub.add_parser("source", help="register a citable source (RF-03)")
    p_source.add_argument("project")
    p_source.add_argument("key", help="citekey, must match src-<slug>")
    p_source.add_argument("kind")
    p_source.add_argument("title")
    p_source.add_argument("--date", default=None)
    p_source.add_argument("--url", default=None)
    p_source.add_argument("--publisher", default=None)
    p_source.add_argument("--accessed", default=None)
    p_source.add_argument("--as-of", default=None)
    p_source.add_argument("--overwrite", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "templates":
        print(json.dumps(list_templates(), indent=2))
    elif args.cmd == "new":
        formats = [f.strip() for f in args.formats.split(",") if f.strip()] or None
        kpis = None
        metrics = None
        if args.kpis.strip() and args.metrics.strip():
            print(json.dumps({"ok": False, "error": "use either --metrics or --kpis, not both"}), file=sys.stderr)
            return 1
        if args.kpis.strip():
            try:
                kpis = json.loads(args.kpis)
            except json.JSONDecodeError as exc:
                print(json.dumps({"ok": False, "error": f"--kpis is not valid JSON: {exc}"}), file=sys.stderr)
                return 1
        if args.metrics.strip():
            try:
                metrics = json.loads(args.metrics)
            except json.JSONDecodeError as exc:
                print(json.dumps({"ok": False, "error": f"--metrics is not valid JSON: {exc}"}), file=sys.stderr)
                return 1
        result = scaffold_report(
            args.slug, args.title or None, args.subtitle, args.author, args.abstract,
            args.template, formats, args.firm,
            kpis=kpis, confidential_mark=args.confidential_mark,
            organization=args.organization, eyebrow=args.eyebrow,
            title_layout=args.title_layout, accent=args.accent, metrics=metrics,
        )
        print(
            json.dumps(result, indent=2),
            file=sys.stdout if result.get("ok") else sys.stderr,
        )
        return 0 if result.get("ok") else 1
    elif args.cmd == "render":
        formats = [f.strip() for f in args.formats.split(",") if f.strip()] or None
        result = render_report(args.source, formats)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "chart":
        fig_json = open(args.fig_json_file).read()
        result = save_chart(fig_json, args.out_basename, args.width, args.height)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "status":
        result = project_status(args.project)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "open":
        result = open_report(args.project)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "readiness":
        result = check_readiness(args.project)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "preview":
        result = render_preview(args.project, revision=args.revision)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "export":
        result = export_release(args.project, revision=args.revision, dest=args.dest,
                                include_source=args.include_source,
                                include_data=args.include_data)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    elif args.cmd == "capabilities":
        print(json.dumps(reportforge_capabilities(), indent=2))
        return 0
    elif args.cmd == "source":
        result = register_source(args.project, args.key, args.kind, args.title,
                                 date=args.date, url=args.url,
                                 publisher=args.publisher,
                                 accessed=args.accessed,
                                 as_of=getattr(args, "as_of"),
                                 overwrite=args.overwrite)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
