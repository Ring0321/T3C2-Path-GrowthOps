"""Create the committed synthetic validation artifacts."""

from pathlib import Path

from t3c2_path.research import export_validation_bundle

if __name__ == "__main__":
    result = export_validation_bundle(Path("research/generated"), n=1_200, seed=20260719)
    print(result)
