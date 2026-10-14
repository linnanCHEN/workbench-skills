import argparse
import json
import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size, bold=False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    path = Path(r"C:\Windows\Fonts") / name
    return ImageFont.truetype(str(path), size=size) if path.exists() else ImageFont.load_default()


def fit_image(source, width, height):
    image = Image.open(source).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    return canvas


def main():
    parser = argparse.ArgumentParser(description="Build a target-plus-candidates contact sheet")
    parser.add_argument("--input", required=True)
    parser.add_argument("--seed-image", required=True)
    parser.add_argument("--seed-title", default="SEED")
    parser.add_argument("--seed-price", type=float)
    parser.add_argument("--seed-units", type=int)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])[args.start :]
    if args.limit is not None:
        candidates = candidates[: args.limit]
    entries = [
        {
            "index": 0,
            "asin": data.get("seedAsin") or data.get("seedId") or "IMAGE-SEED",
            "title": args.seed_title,
            "price": args.seed_price,
            "units": args.seed_units,
            "localImagePath": str(Path(args.seed_image).resolve()),
            "seed": True,
        }
    ]
    for index, product in enumerate(candidates, args.start + 1):
        if not product.get("localImagePath"):
            continue
        copy = dict(product)
        copy["index"] = index
        copy["seed"] = False
        entries.append(copy)

    columns = max(1, args.columns)
    cell_width, cell_height = 330, 330
    image_width, image_height = 298, 220
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#f4f5f7")
    draw = ImageDraw.Draw(sheet)
    heading_font = load_font(17, bold=True)
    text_font = load_font(14)
    small_font = load_font(13)

    for position, entry in enumerate(entries):
        column, row = position % columns, position // columns
        x0, y0 = column * cell_width, row * cell_height
        border = "#d62828" if entry["seed"] else "#b8bcc4"
        draw.rounded_rectangle(
            (x0 + 5, y0 + 5, x0 + cell_width - 5, y0 + cell_height - 5),
            radius=10,
            fill="white",
            outline=border,
            width=4 if entry["seed"] else 2,
        )
        sheet.paste(fit_image(entry["localImagePath"], image_width, image_height), (x0 + 16, y0 + 14))
        price = entry.get("price")
        price_text = f"${price:g}" if isinstance(price, (int, float)) else "price n/a"
        draw.text(
            (x0 + 16, y0 + 240),
            f"{entry['index']:02d} | {entry.get('asin')} | {price_text}",
            fill="#111827",
            font=heading_font,
        )
        units = entry.get("units")
        sales_text = f"Est. {units:,}/month" if isinstance(units, (int, float)) else "Sales estimate unavailable"
        draw.text((x0 + 16, y0 + 263), sales_text, fill="#b42318" if units else "#6b7280", font=small_font)
        title = " ".join(str(entry.get("title") or "").split())
        for line_index, line in enumerate(textwrap.wrap(title, width=39)[:2]):
            draw.text(
                (x0 + 16, y0 + 283 + line_index * 17),
                line,
                fill="#374151",
                font=text_font if line_index == 0 else small_font,
            )

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    print(f"saved={output} size={sheet.width}x{sheet.height} entries={len(entries)}")


if __name__ == "__main__":
    main()
