import json
from pathlib import Path


def main():
    sample_path = Path(__file__).parent / "sample_data" / "documents.json"
    docs = json.loads(sample_path.read_text())
    print(f"Loaded {len(docs)} sample documents for future seed flow")


if __name__ == "__main__":
    main()
