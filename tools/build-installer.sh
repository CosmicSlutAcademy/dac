#!/usr/bin/env bash
# Regenerate install-dac.sh from the source tree.
# Usage: bash tools/build-installer.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "from dac import __version__; print(__version__)")
OUT=install-dac.sh

FILES=(
  dac/__init__.py
  dac/__main__.py
  dac/config.py
  dac/launcher.py
  dac/cli.py
  dac/repl.py
  dac/daemon.py
  dac/orchestrator.py
  dac/assistant.py
  dac/monitor.py
  dac/telegram_bot.py
  dac/demo.py
  dac/site.py
  dac/commands/__init__.py
  dac/core/__init__.py
  dac/core/llm.py
  dac/core/executor.py
  dac/core/session.py
  dac/core/autonomous.py
  gcia/__init__.py
  gcia/__main__.py
  gcia/audit.py
  gcia/laptop.py
  gcia/launcher.py
  gcia/policy.py
  gcia/recon.py
  gcia/vault.py
  gcia/notify.py
  gcia/patrol.py
  gcia/remote.py
  gcia/agent.py
  setup.py
  README.md
)

cat > "$OUT" <<EOF
#!/usr/bin/env bash
# DAC v$VERSION Installer  |  bash install-dac.sh [API_KEY] [MODEL]
set -euo pipefail

API_KEY="\${1:-}"
MODEL="\${2:-gpt-4o}"
DEST="\${HOME}/NEXTGENWORLD+HUMAN_AI"

echo ""
echo "DAC v$VERSION Installer → \$DEST"
echo ""

# --- package manager ---
echo "[1/7] Detecting package manager..."
if command -v pkg >/dev/null 2>&1; then PM="pkg";
elif command -v apt-get >/dev/null 2>&1; then PM="apt";
else echo "ERROR: need pkg or apt"; exit 1; fi
echo "  \$PM"

# --- preflight: catch corrupted binaries before anything else ---
echo "[2/7] Preflight integrity check..."
BROKEN=""
if [ -n "\${PREFIX:-}" ] && [ -d "\$PREFIX/bin" ]; then
  BROKEN=\$(find "\$PREFIX/bin" -maxdepth 1 -type f -size 0 2>/dev/null | head -20)
elif [ -d /usr/bin ]; then
  BROKEN=\$(find /usr/bin -maxdepth 1 -type f -size 0 2>/dev/null | head -20)
fi
if [ -n "\$BROKEN" ]; then
  echo "  WARNING: 0-byte binaries detected — the install shell is corrupt."
  echo "\$BROKEN" | sed 's/^/    /'
  echo "  Attempting repair: \$PM reinstall of owning packages..."
  for f in \$BROKEN; do
    OWNER=\$(dpkg -S "\$f" 2>/dev/null | cut -d: -f1 | head -1 || true)
    if [ -n "\$OWNER" ]; then
      echo "    Reinstalling \$OWNER (owns \$(basename "\$f"))..."
      if [ "\$PM" = "pkg" ]; then pkg reinstall -y "\$OWNER" >/dev/null 2>&1 || true;
      else apt-get install --reinstall -y "\$OWNER" >/dev/null 2>&1 || true; fi
    fi
  done
  BIN_DIR=""
  if [ -n "\${PREFIX:-}" ] && [ -d "\$PREFIX/bin" ]; then BIN_DIR="\$PREFIX/bin"; fi
  if [ -z "\$BIN_DIR" ] && [ -d /usr/bin ]; then BIN_DIR=/usr/bin; fi
  if [ -n "\$BIN_DIR" ]; then
    REMAIN=\$(find "\$BIN_DIR" -maxdepth 1 -type f -size 0 2>/dev/null | head -5 || true)
    if [ -n "\$REMAIN" ]; then
      echo "  ERROR: corruption persists. Fix on Android:"
      echo "    Settings → Apps → Termux → Storage → Clear data"
      echo "  then reopen Termux and rerun this installer."
      echo "\$REMAIN" | sed 's/^/    /'
      exit 1
    fi
  fi
  echo "  Repaired."
else
  echo "  OK — no 0-byte binaries found."
fi

# --- install deps ---
echo "[3/7] Installing python, git, tmux..."
if [ "\$PM" = "pkg" ]; then
  pkg update -y 2>/dev/null || true
  pkg install -y python git tmux 2>/dev/null || true
else
  apt-get update -y 2>/dev/null || true
  apt-get install -y python3 python3-pip git tmux 2>/dev/null || true
fi

# --- dirs ---
echo "[4/7] Creating \$DEST..."
mkdir -p "\$DEST/dac/commands" "\$DEST/dac/core" "\$DEST/gcia"

# --- write source files ---
echo "[5/7] Writing source files..."
EOF

for f in "${FILES[@]}"; do
  B64=$(base64 -w0 "$f")
  printf "echo '%s' | base64 -d > \"\$DEST/%s\"\n" "$B64" "$f" >> "$OUT"
done

cat >> "$OUT" <<'EOF'

# --- install ---
echo "[6/7] Installing DAC globally..."
cp "$DEST/gcia-agent" /usr/local/bin/gcia-agent 2>/dev/null || true
chmod +x /usr/local/bin/gcia-agent 2>/dev/null || true
cp "$DEST/gcia-agent" "$PREFIX/bin/gcia-agent" 2>/dev/null || true
chmod +x "$PREFIX/bin/gcia-agent" 2>/dev/null || true
cd "$DEST"
PIP_FLAGS=""
if [ "$PM" = "apt" ]; then PIP_FLAGS="--break-system-packages"; fi
python3 -m pip install $PIP_FLAGS -e . 2>/dev/null || python3 -m pip install $PIP_FLAGS . 2>/dev/null

# --- configure ---
echo "[7/7] Configuring..."
if [ -n "$API_KEY" ]; then
  python3 -c "
from dac.config import load_config, save_config
cfg = load_config()
cfg['api_key'] = '$API_KEY'
cfg['model'] = '$MODEL'
save_config(cfg)
print('API key: sk-***' + '$API_KEY'[-4:])
  "
fi

# --- smoke test ---
echo ""
if dac run 'print("DAC installed OK")'; then
  echo ""
  echo "=== DAC v__DAC_VERSION__ ready ==="
  echo ""
  echo "  dac --version"
  echo "  dac doctor"
  echo "  dac doctor --fix"
  echo "  dac assistant --say hi"
  echo "  dac monitor --add BTC"
  echo "  dac demo"
  echo "  dac quick \"your task\""
  echo "  dac daemon start"
  echo ""
else
  echo "WARNING: smoke test failed"
fi
EOF

# Substitute the build-time version into the quoted heredoc output.
sed -i "s/__DAC_VERSION__/$VERSION/g" "$OUT"

chmod +x "$OUT"
echo "Wrote $OUT (v$VERSION, $(wc -l < "$OUT") lines)"
