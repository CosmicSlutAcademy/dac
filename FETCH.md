# Install DAC on Any Device — One Line

## One-line install (no files needed)

```bash
curl -sL https://paste.rs/dzyVO | bash -s
```

With API key + model:

```bash
curl -sL https://paste.rs/dzyVO | bash -s -- sk-your-api-key gpt-4o
```

Works on:
- Termux (`pkg`) — any phone
- Proot/rooted (`apt`) — any Linux device

## What it does

1. Detects package manager (pkg/apt)
2. Installs python, git, tmux
3. Writes all 16 DAC source files (embedded)
4. Installs DAC globally via pip
5. Sets API key + model
6. Runs smoke test → `DAC installed OK`

## Push to GitHub (when you have a token)

```bash
cd ~/NEXTGENWORLD+HUMAN_AI
gh auth login                    # or: git credential approve
git remote add origin https://github.com/YOUR_USERNAME/dac.git
git push -u origin main
```

Then install from GitHub instead:

```bash
curl -sL https://raw.githubusercontent.com/YOUR_USERNAME/dac/main/install-dac.sh | bash -s
```
