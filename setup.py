"""
py2app-Setup für Presentinize.
Bauen:  ./build.sh   (oder: python3 setup.py py2app)

Wichtig: KEIN Shell-Launcher mit /usr/bin/python3 — nur ein echtes Bundle
sorgt dafür, dass das Menüleisten-Icon zuverlässig erscheint.
"""
from setuptools import setup

APP = ["presentify.py"]

OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "Presentinize",
        "CFBundleDisplayName": "Presentinize",
        "CFBundleIdentifier": "de.calvinhollywood.presentinize",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "LSUIElement": True,               # kein Dock-Icon, reine Menüleisten-App
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
}

setup(
    name="Presentify",
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
