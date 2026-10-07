#!/bin/sh
# Builds bin/turn-ding from turn-ding.swift.
set -e
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$here/../bin"
swiftc -O -swift-version 5 "$here/turn-ding.swift" -o "$here/../bin/turn-ding"
