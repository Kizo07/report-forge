"""Command-line interface for reportforge."""

from __future__ import annotations

import argparse
import json
import sys

from reportforge.engine import list_templates, render_report, save_chart, scaffold_report


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
    p_new.add_argument("--template", default="standard", choices=["standard", "memo", "whitepaper", "modern"])
    p_new.add_argument("--firm", default="", help="firm/institution name (whitepaper title page / modern masthead + header)")
    p_new.add_argument("--confidential-mark", default="", help="confidentiality mark in modern template footer, e.g. 'Confidential'")
    p_new.add_argument("--kpis", default="", help="modern template KPI strip as JSON list, e.g. '[{\"value\":\"+62 bps\",\"label\":\"Alpha\"}]'")
    p_new.add_argument("--formats", default="", help="comma list, e.g. html,pdf,docx")

    p_render = sub.add_parser("render", help="render a report")
    p_render.add_argument("source")
    p_render.add_argument("--formats", default="", help="comma list, e.g. html,pdf,docx")

    p_chart = sub.add_parser("chart", help="export a plotly JSON figure to png+html")
    p_chart.add_argument("fig_json_file")
    p_chart.add_argument("out_basename")
    p_chart.add_argument("--width", type=int, default=1400)
    p_chart.add_argument("--height", type=int, default=700)

    args = parser.parse_args(argv)
    if args.cmd == "templates":
        print(json.dumps(list_templates(), indent=2))
    elif args.cmd == "new":
        formats = [f.strip() for f in args.formats.split(",") if f.strip()] or None
        kpis = None
        if args.kpis.strip():
            try:
                kpis = json.loads(args.kpis)
            except json.JSONDecodeError as exc:
                print(json.dumps({"ok": False, "error": f"--kpis is not valid JSON: {exc}"}), file=sys.stderr)
                return 1
        result = scaffold_report(
            args.slug, args.title or None, args.subtitle, args.author, args.abstract,
            args.template, formats, args.firm,
            kpis=kpis, confidential_mark=args.confidential_mark,
        )
        print(json.dumps(result, indent=2))
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
