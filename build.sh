#!/bin/sh

set -e

rm -rf *.exe _internal
pyinstaller CK3_PP.py
mv dist/*/* .
rm -rf dist *.spec
