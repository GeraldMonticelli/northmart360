from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run(label: str, command: list[str]) -> None:
    print(f"\n{'=' * 70}")
    print(f"{label}")
    print("=" * 70)

    result = subprocess.run(
        command,
        cwd=ROOT,
    )

    if result.returncode != 0:
        print(f"\n❌ FAILED: {label}")
        sys.exit(result.returncode)

    print(f"\n✓ PASS: {label}")


def main() -> None:
    print("\nSEMANTIC CONTRACT VALIDATION")

    run(
        "[1/3] Contract parsing + governance SHACL",
        [PYTHON, "scripts/validate_contract.py"],
    )

    run(
        "[2/3] Generate R2RML from contract",
        [PYTHON, "scripts/generate_r2rml.py"],
    )

    run(
        "[3/3] Validate generated R2RML against contract",
        [PYTHON, "scripts/validate_r2rml.py"],
    )

    print("\n" + "=" * 70)
    print("✓ SEMANTIC CONTRACT VALID")
    print("=" * 70)


if __name__ == "__main__":
    main()