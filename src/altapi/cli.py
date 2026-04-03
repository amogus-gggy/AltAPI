import argparse
from importlib.metadata import version, PackageNotFoundError

def get_v():
    print(version)
    return version

def main():
    parser = argparse.ArgumentParser(description="AltAPI - Fast and powerful ASGI framework")
    parser.add_argument(
        "--version",
        action="version",
        version=f"altapi {version('AltAPI')}"
    )
    args = parser.parse_args()


