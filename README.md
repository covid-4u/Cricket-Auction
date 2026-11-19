# 🏏 CricBid — Cricket Auction Manager

CricBid is a Flask + SQLite web app for running a live, IPL-style player auction. It is built for office/community cricket tournaments: an organizer manages players and teams, runs the auction in real time, and everyone else can watch live.

## ✨ Features

- **Organizer login** with a dashboard showing players, teams, sold count and active auctions
- **Player management** — add, edit, delete, with photo upload (png, jpg, jpeg, gif, webp; max 5 MB)
- **Team management** — team logo, owner, captain, reserve player, per-team budget and remaining budget
- **Live auction room**
  - Bid in fixed increments (configurable per auction)
  - Budget check: a team cannot bid more than its remaining budget
  - Sell, mark unsold, and **re-bid unsold** players (re-queued at the end)
  - **RTM (Right to Match)** — a team can match the current bid and take the player
  - Full bid history
- **Round-based player order** — players are grouped by `price_round` (1 → 2 → 3) and shuffled within each round
- **Spectator view** (`/watch/<auction_id>`) — public live page, no login needed
- **Team view** (`/team-view/<team_id>`) and team squad pages
- **Results page** and **CSV export** of the final auction results
- **Settings** — change organizer name/password, reset sold statuses
- **Bulk import** of players from Excel
- **Database reset tool** (command line)

## 🧰 Tech Stack

- Python 3
- Flask
- SQLite (`auction.db`)
- openpyxl (only for the Excel importer)

## 📁 Project Structure

```
cricbid/
├── app.py              # Flask app: routes, JSON APIs, DB setup
├── auction.db          # SQLite database (auto-created if missing)
├── import_player.py    # Import players from an Excel file
├── clear_data.py       # Interactive DB reset tool
├── player.xlsx         # (your Excel file for import, not included)
├── templates/          # HTML templates (login, dashboard, auction room, ...)
└── static/
    └── uploads/        # Uploaded player photos and team logos
```

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2. Install dependencies

```bash
pip install flask openpyxl
```

### 3. Run the app

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

The database tables are created automatically on first run.

### 4. Log in

A default organizer account is created automatically:

| Username | Password   |
|----------|------------|
| `admin`  | `admin123` |

> ⚠️ **Change the password immediately** from the **Settings** page, especially before hosting this anywhere public.

## 🎮 How to Run an Auction

1. **Add players** (manually or via Excel import).
2. **Add teams** with their budgets.
3. **Create an auction** — set a title, budget per team and bid increment. The player queue is generated automatically (Round 1 first, then 2, then 3; shuffled within each round).
4. **Start the auction** and bring players up one by one.
5. **Place bids** for teams, then **Sell** or mark **Unsold**. Use **RTM** when a team exercises its right to match.
6. Share the **spectator link** `/watch/<auction_id>` so everyone can follow live.
7. When finished, view the **results** and **export CSV**.

## 📥 Importing Players from Excel

1. Put your Excel file in the project folder (default name: `player.xlsx`).
2. Open `import_player.py` and edit the settings at the top:

   ```python
   EXCEL_FILE = r'./player.xlsx'

   COLUMN_MAP = {
       'name':       'NAME',                                       # required
       'type':       'What is your strongest skill in cricket?',
       'department': 'DEPARTMENT',
       'base_price': 'BASE_PRICE',
       'photo':      None, # path to .jpg file
   }
   ```

   The right-hand side must match your Excel header row exactly.
3. Run:

   ```bash
   python import_player.py
   ```

4. Check the preview and type `yes` to import.

Notes:
- The player **type** is matched flexibly (e.g. "bat" → Batsman, "wk" → Wicket-Keeper). Valid types: `Batsman`, `Bowler`, `Fielder`, `All-Rounder`, `Wicket-Keeper`.
- Players whose name already exists are skipped.
- Missing values fall back to the defaults in the `DEFAULTS` dictionary.
- The importer does not set `price_round`, so imported players default to Round 1.

## 🗑️ Resetting Data

```bash
python clear_data.py
```

Interactive menu:

| Option | Action |
|--------|--------|
| 1 | Clear players only (also clears auction queue and bid history) |
| 2 | Clear teams only (also resets players' sold status) |
| 3 | Clear auction history only (keeps players and teams, resets budgets) |
| 4 | Clear players + auction history |
| 5 | Clear everything |

Each option asks for confirmation. **This permanently deletes data**, so back up `auction.db` first.

## 🗄️ Database Schema

| Table | Purpose |
|-------|---------|
| `organizer` | Admin login |
| `players` | Name, type, department, photo, base price, price round, sold status/price/team |
| `teams` | Name, logo, owner, captain, reserve player, budget, remaining budget |
| `auctions` | Title, status, current player/bid/bidder, bid increment, budget per team |
| `auction_players` | Player queue for each auction (order, status, round) |
| `bid_history` | Every bid placed |

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auction/<id>/start` | Start the auction |
| POST | `/api/auction/<id>/next_player` | Bring up the next player |
| POST | `/api/auction/<id>/bid` | Place a bid (`team_id`) |
| POST | `/api/auction/<id>/sell` | Sell the current player |
| POST | `/api/auction/<id>/unsold` | Mark the current player unsold |
| POST | `/api/auction/<id>/rebid_unsold` | Re-queue an unsold player |
| POST | `/api/auction/<id>/rtm` | Use Right to Match (`team_id`) |
| GET | `/api/auction/<id>/unsold_list` | List unsold players |
| GET | `/api/auction/<id>/state` | Current auction state |
| GET | `/api/auction/<id>/full_state` | Full auction state |
| GET | `/api/team/<id>/state` | Team state |

## 🔒 Security Notes

Before deploying publicly:

- Change the default `admin` / `admin123` credentials.
- Replace the hard-coded `app.secret_key` in `app.py` with a secret value from an environment variable.
- Passwords are currently stored in plain text. Consider hashing them (e.g. `werkzeug.security.generate_password_hash`).
- Turn off `debug=True` in production and use a proper WSGI server such as Gunicorn or Waitress.
- Don't commit a real `auction.db` containing personal data to a public repository.

## 📄 License

Add a license of your choice (e.g. MIT) here.
