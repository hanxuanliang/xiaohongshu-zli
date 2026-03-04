# xhs-cli 🍰

A command-line tool for [Xiaohongshu (小红书)](https://www.xiaohongshu.com) — search notes, view profiles, like, favorite, and comment, all from your terminal.

## ✨ Features

- 🔍 **Search** — search notes by keyword with rich table output
- 📖 **Note Detail** — view note content, stats, and comments
- 👤 **User Profile** — view user info and stats
- ❤️ **Like / Unlike** — like or unlike notes
- ⭐ **Favorite / Unfavorite** — collect or uncollect notes
- 💬 **Comment** — post comments on notes
- 🔐 **Auth** — auto-extract cookies from Chrome, or login via QR code
- 📊 **JSON output** — `--json` flag for all data commands

## 🏗️ Architecture

```
CLI (click) → XhsClient (camoufox browser)
                  ↓ navigate to real pages
              window.__INITIAL_STATE__ → extract structured data
```

Uses [camoufox](https://github.com/nicochichat/camoufox) (anti-fingerprint Firefox) to browse Xiaohongshu like a real user. Data is extracted from the page's `window.__INITIAL_STATE__` — completely indistinguishable from normal browsing.

## 📦 Installation

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone and install
git clone git@github.com:jackwener/xhs-cli.git
cd xhs-cli
uv sync

# Install camoufox browser
uv run python -m camoufox fetch
```

## 🚀 Usage

### Login

```bash
# Auto-extract cookies from Chrome (recommended)
uv run xhs login

# Or provide cookie string manually
uv run xhs login --cookie "a1=xxx; web_session=yyy"

# Check login status
uv run xhs status
```

### Search

```bash
# Search with rich table output
uv run xhs search "咖啡"

# JSON output
uv run xhs search "咖啡" --json
```

### Note Detail

```bash
# View note (xsec_token from search results)
uv run xhs note <note_id> --xsec-token <token>

# Include comments
uv run xhs note <note_id> --xsec-token <token> --comments

# JSON output
uv run xhs note <note_id> --xsec-token <token> --json
```

### User Profile

```bash
# View user profile (use internal user_id, not Red ID)
uv run xhs user <user_id>
uv run xhs user <user_id> --json
```

### Interactions

```bash
# Like / Unlike
uv run xhs like <note_id> --xsec-token <token>
uv run xhs like <note_id> --xsec-token <token> --undo

# Favorite / Unfavorite
uv run xhs favorite <note_id> --xsec-token <token>
uv run xhs favorite <note_id> --xsec-token <token> --undo

# Comment
uv run xhs comment <note_id> "好棒！" --xsec-token <token>
```

### Options

```bash
# Enable debug logging
uv run xhs -v search "咖啡"

# Show help
uv run xhs --help
uv run xhs search --help
```

## 📁 Project Structure

```
xhs-cli/
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Lock file
├── README.md
├── LICENSE
└── xhs_cli/
    ├── __init__.py         # Package version
    ├── cli.py              # Click CLI commands
    ├── client.py           # Camoufox browser client
    ├── auth.py             # Cookie extraction + QR login
    └── exceptions.py       # Custom exceptions
```

## 🔧 How It Works

1. **Authentication**: Cookies are extracted from your local Chrome browser via [browser-cookie3](https://github.com/nicochichat/browsercookie). Falls back to QR code login if extraction fails.

2. **Browsing**: Each operation navigates to the real Xiaohongshu page using camoufox (a fingerprint-resistant Firefox fork). This makes all traffic look like normal user browsing.

3. **Data Extraction**: Structured data is pulled from `window.__INITIAL_STATE__`, which is the same data React/Vue uses to render the page.

4. **Interactions**: Like, favorite, and comment work by finding and clicking the actual DOM buttons — exactly as a real user would.

## ⚠️ Notes

- Cookies are stored in `~/.xhs-cli/cookies.json` with `0600` permissions.
- The tool uses headless Firefox via camoufox — no browser window is shown.
- First run may be slower as camoufox downloads its browser binary.
- User profile lookup requires the internal user_id (hex format), not the Red ID (numeric).

## 📄 License

MIT
