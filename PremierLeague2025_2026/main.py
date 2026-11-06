"""Command line entry point for local FBref HTML analysis."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from epl.common import RAW


def main(argv=None):
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Phân tích Premier League 2025-2026 từ HTML đã lưu")
    commands = parser.add_subparsers(dest="command", required=True)
    collection_commands = [
        commands.add_parser("all", help="Chạy đầy đủ 4 phần và xuất báo cáo"),
        commands.add_parser("prepare", aliases=["fetch"], help="Trích xuất và làm sạch 20 HTML"),
    ]
    for subparser in collection_commands:
        subparser.add_argument("--html-dir", type=Path, default=RAW.parent / "sources",
                               help="Thư mục HTML; mặc định data/sources")
        subparser.add_argument("--allow-partial", action="store_true",
                               help="Cho phép kiểm tra tập chưa đủ 20 đội")
        subparser.add_argument("--offline", action="store_true",
                               help="Tùy chọn tương thích; chương trình luôn chỉ đọc tệp cục bộ")
    for name, description in [
        ("stats", "Thống kê và histogram"),
        ("transfers", "Lọc và ghép giao dịch chuyển nhượng"),
        ("valuation", "Huấn luyện và đánh giá mô hình phí hồi cứu"),
        ("report", "Xuất báo cáo HTML, Markdown và PDF"),
    ]:
        commands.add_parser(name, help=description)
    cluster = commands.add_parser("cluster", help="K-means và PCA")
    cluster.add_argument("--k", type=int, default=5)
    radar = commands.add_parser("radar", help="So sánh hai cầu thủ")
    radar.add_argument("--p1", required=True, help="Tên đầy đủ hoặc PlayerID")
    radar.add_argument("--p2", required=True)
    radar.add_argument("--attributes", "--Attribute", dest="attributes")
    radar.add_argument("--all-positions", action="store_true")
    args = parser.parse_args(argv)

    if args.command in ["prepare", "fetch"]:
        from epl.fbref_scraper import collect_fbref
        result = collect_fbref(html_dir=args.html_dir, allow_partial=args.allow_partial)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    from epl import fbref_pipeline as fb

    if args.command == "all":
        result = fb.run_all(args)
    elif args.command == "cluster":
        result = fb.clustering(args.k)
    elif args.command == "radar":
        attributes = [value.strip() for value in args.attributes.split(",")] if args.attributes else None
        result = fb.radar(args.p1, args.p2, attributes, not args.all_positions)
    else:
        result = {
            "stats": fb.statistics,
            "transfers": fb.transfers,
            "valuation": fb.valuation,
            "report": fb.report,
        }[args.command]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Lỗi: {error}", file=sys.stderr)
        sys.exit(1)
