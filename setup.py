from distutils.core import setup
import py2exe
import sys
import os

sys.argv.append('py2exe')

setup(
    options={'py2exe': {'bundle_files': 1, 'compressed': True}},
    windows=[{'script': "main.py", "icon_resources": [(1, "icon.ico")]}],
    zipfile=None,
)
