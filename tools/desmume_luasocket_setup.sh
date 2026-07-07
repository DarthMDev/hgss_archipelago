#!/usr/bin/env bash
#
# Build a LuaSocket for DeSmuME's embedded Lua 5.1 and stage it where
# connector_desmume_generic.lua looks for it (~/.desmume-ap-lua).
#
# LuaSocket must be built for Lua 5.1 (DeSmuME's version) and linked with
# -undefined dynamic_lookup so it binds to DeSmuME's single Lua instance at
# load time. luarocks already links this way by default; we just need a
# Lua 5.1 toolchain, which hererocks provides without needing a system Lua
# 5.1 (Homebrew no longer ships lua@5.1).
#
# Requirements: python3, a C compiler (Xcode Command Line Tools), network.
#
# NOTE: This only produces the LuaSocket module. You ALSO need a DeSmuME
# built to export its Lua symbols (see the DarthMDev/desmume fork).
set -euo pipefail

STAGE="${DESMUME_LUASOCKET_DIR:-$HOME/.desmume-ap-lua}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo ">> Creating Python venv for hererocks..."
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" -q install --upgrade pip >/dev/null
"$WORK/venv/bin/pip" -q install hererocks certifi >/dev/null

# python.org Python builds often lack CA certs; point at certifi's bundle
# so hererocks can download Lua/LuaRocks over HTTPS.
export SSL_CERT_FILE="$("$WORK/venv/bin/python" -m certifi)"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"

PREFIX="$WORK/lua51"
echo ">> Building Lua 5.1.5 + LuaRocks (this compiles from source)..."
"$WORK/venv/bin/hererocks" "$PREFIX" -l 5.1 -r latest >/dev/null

echo ">> Installing LuaSocket..."
"$PREFIX/bin/luarocks" install luasocket >/dev/null

CORE_SO="$PREFIX/lib/lua/5.1/socket/core.so"
SOCKET_LUA="$PREFIX/share/lua/5.1/socket.lua"
[ -f "$CORE_SO" ] || { echo "ERROR: socket/core.so was not built"; exit 1; }

echo ">> Staging into $STAGE ..."
mkdir -p "$STAGE/socket"
cp "$SOCKET_LUA" "$STAGE/socket.lua"
cp "$CORE_SO" "$STAGE/socket/core.so"

echo ">> Verifying the module imports the Lua C API from the host (dynamic_lookup)..."
if nm -u "$STAGE/socket/core.so" | grep -q "_lua_gettop"; then
    echo "   OK: core.so imports Lua and will bind to DeSmuME's single Lua at load time."
else
    echo "   WARNING: core.so does not import the Lua C API, so it likely bundles its own"
    echo "   copy of Lua. Two Lua 5.1 instances in one process crash DeSmuME on teardown."
fi

echo ""
echo "Done. Staged files:"
echo "  $STAGE/socket.lua"
echo "  $STAGE/socket/core.so"
echo ""
echo "Reminder: you still need a DeSmuME build that exports its Lua symbols"
echo "(DarthMDev/desmume fork) for require(\"socket\") to load inside DeSmuME."
