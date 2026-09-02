import argparse
import json
from pathlib import Path

from fairhire_api.main import app

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT / "contracts" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        return 0 if TARGET.exists() and TARGET.read_text() == expected else 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
