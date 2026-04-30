#!/usr/bin/env python3
"""Debug script to check model directory structure in macOS .app bundle"""

import sys
from pathlib import Path

def check_macos_structure():
    """Check the structure of a macOS .app bundle"""

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent

        print(f"Executable path: {exe_dir}")
        print(f"Parent directory: {exe_dir.parent}")

        # Check for .app bundle structure
        if exe_dir.name == "MacOS":
            resources_dir = exe_dir.parent / "Resources"
            print(f"Resources directory: {resources_dir}")
            print(f"Resources exists: {resources_dir.exists()}")

            if resources_dir.exists():
                rapidocr_dir = resources_dir / "rapidocr"
                print(f"RapidOCR directory: {rapidocr_dir}")
                print(f"RapidOCR exists: {rapidocr_dir.exists()}")

                if rapidocr_dir.exists():
                    models_dir = rapidocr_dir / "models"
                    print(f"Models directory: {models_dir}")
                    print(f"Models exists: {models_dir.exists()}")

                    if models_dir.exists():
                        print("Model files:")
                        for f in models_dir.iterdir():
                            print(f"  - {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")
                    else:
                        print("No models directory found!")
                        print("Contents of rapidocr directory:")
                        for f in rapidocr_dir.iterdir():
                            print(f"  - {f.name}")
                else:
                    print("No rapidocr directory found!")
        else:
            print("Not running in a .app bundle")
            print(f"Contents of exe_dir: {list(exe_dir.iterdir())}")
    else:
        print("Not running as a frozen executable")

if __name__ == "__main__":
    check_macos_structure()