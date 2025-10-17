import json
import sys
from pathlib import Path


def repair_text(s: str) -> str:
    try:
        # Attempt to reverse CP1252/Latin-1 mojibake of UTF-8
        return s.encode('latin-1').decode('utf-8')
    except Exception:
        return s


def repair_obj(obj):
    if isinstance(obj, dict):
        return {repair_obj(k): repair_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [repair_obj(x) for x in obj]
    if isinstance(obj, str):
        return repair_text(obj)
    return obj


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/fix_mojibake_json.py <path-to-json>")
        sys.exit(1)
    path = Path(sys.argv[1])
    raw = path.read_text(encoding='utf-8-sig')
    data = json.loads(raw)
    fixed = repair_obj(data)
    # Pretty and ensure UTF-8 without BOM
    path.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Repaired: {path}")


if __name__ == '__main__':
    main()

