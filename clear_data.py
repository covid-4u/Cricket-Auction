"""
CricBid — Database Reset Tool
==============================
Run: python reset_db.py
"""

import sqlite3, os, sys

DB_FILE = 'auction.db'   # same folder as app.py

def get_db():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    return db

def show_counts():
    db = get_db()
    players  = db.execute('SELECT COUNT(*) FROM players').fetchone()[0]
    teams    = db.execute('SELECT COUNT(*) FROM teams').fetchone()[0]
    auctions = db.execute('SELECT COUNT(*) FROM auctions').fetchone()[0]
    bids     = db.execute('SELECT COUNT(*) FROM bid_history').fetchone()[0]
    ap       = db.execute('SELECT COUNT(*) FROM auction_players').fetchone()[0]
    db.close()
    print(f"""
  Current DB state:
    Players       : {players}
    Teams         : {teams}
    Auctions      : {auctions}
    Bid history   : {bids}
    Auction queue : {ap}
""")

def reset_players():
    db = get_db()
    count = db.execute('SELECT COUNT(*) FROM players').fetchone()[0]
    print(f"\n  This will DELETE all {count} players.")
    print("  WARNING: Also clears player references in auction history.\n")
    ans = input("  Type 'yes' to confirm: ").strip().lower()
    if ans != 'yes':
        print("  Cancelled.")
        db.close()
        return
    db.execute('DELETE FROM players')
    db.execute('DELETE FROM auction_players')
    db.execute('DELETE FROM bid_history')
    db.commit()
    db.close()
    print(f"  Done. Deleted {count} players + auction queue + bid history.")

def reset_teams():
    db = get_db()
    count = db.execute('SELECT COUNT(*) FROM teams').fetchone()[0]
    print(f"\n  This will DELETE all {count} teams.")
    print("  WARNING: Also resets all player sold status.\n")
    ans = input("  Type 'yes' to confirm: ").strip().lower()
    if ans != 'yes':
        print("  Cancelled.")
        db.close()
        return
    db.execute('DELETE FROM teams')
    db.execute('UPDATE players SET is_sold=0, sold_to_team=NULL, sold_price=NULL')
    db.commit()
    db.close()
    print(f"  Done. Deleted {count} teams + reset all player sold status.")

def reset_auctions():
    db = get_db()
    a_count  = db.execute('SELECT COUNT(*) FROM auctions').fetchone()[0]
    b_count  = db.execute('SELECT COUNT(*) FROM bid_history').fetchone()[0]
    ap_count = db.execute('SELECT COUNT(*) FROM auction_players').fetchone()[0]
    print(f"\n  This will DELETE:")
    print(f"    {a_count} auctions")
    print(f"    {b_count} bid history records")
    print(f"    {ap_count} auction queue entries")
    print("  Also resets player sold status and team budgets.\n")
    ans = input("  Type 'yes' to confirm: ").strip().lower()
    if ans != 'yes':
        print("  Cancelled.")
        db.close()
        return
    db.execute('DELETE FROM auctions')
    db.execute('DELETE FROM bid_history')
    db.execute('DELETE FROM auction_players')
    db.execute('UPDATE players SET is_sold=0, sold_to_team=NULL, sold_price=NULL')
    db.execute('UPDATE teams SET remaining_budget=budget')
    db.commit()
    db.close()
    print(f"  Done. Cleared all auction history and reset player/team status.")

def reset_all():
    db = get_db()
    print("\n  !! NUCLEAR OPTION !!")
    print("  This will DELETE EVERYTHING:")
    print(f"    {db.execute('SELECT COUNT(*) FROM players').fetchone()[0]} players")
    print(f"    {db.execute('SELECT COUNT(*) FROM teams').fetchone()[0]} teams")
    print(f"    {db.execute('SELECT COUNT(*) FROM auctions').fetchone()[0]} auctions")
    print(f"    {db.execute('SELECT COUNT(*) FROM bid_history').fetchone()[0]} bid records")
    db.close()
    print()
    ans = input("  Type 'DELETE EVERYTHING' to confirm: ").strip()
    if ans != 'DELETE EVERYTHING':
        print("  Cancelled.")
        return
    db = get_db()
    db.execute('DELETE FROM bid_history')
    db.execute('DELETE FROM auction_players')
    db.execute('DELETE FROM auctions')
    db.execute('DELETE FROM players')
    db.execute('DELETE FROM teams')
    db.commit()
    db.close()
    print("  Done. Database is completely empty.")

def main():
    if not os.path.exists(DB_FILE):
        print(f"ERROR: '{DB_FILE}' not found.")
        print("Run this from the cricbid folder (where app.py is).")
        sys.exit(1)

    while True:
        print("=" * 45)
        print("   CricBid — Database Reset Tool")
        print("=" * 45)
        show_counts()
        print("  What do you want to clear?\n")
        print("  1. Clear PLAYERS only")
        print("  2. Clear TEAMS only")
        print("  3. Clear AUCTION HISTORY only")
        print("     (auctions + bids + queue, keeps players & teams)")
        print("  4. Clear PLAYERS + AUCTION HISTORY")
        print("  5. Clear EVERYTHING (players + teams + auctions)")
        print("  0. Exit\n")

        choice = input("  Enter choice (0-5): ").strip()
        print()

        if   choice == '1': reset_players()
        elif choice == '2': reset_teams()
        elif choice == '3': reset_auctions()
        elif choice == '4':
            reset_auctions()
            reset_players()
        elif choice == '5': reset_all()
        elif choice == '0':
            print("  Bye!")
            break
        else:
            print("  Invalid choice. Enter 0-5.")

        print()
        input("  Press Enter to go back to menu...")
        print()

if __name__ == '__main__':
    main()