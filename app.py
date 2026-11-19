from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
import sqlite3, os, random, csv, io
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.secret_key = 'cricbid_pro_2024'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXT = {'png','jpg','jpeg','gif','webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# ── DB ────────────────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect('auction.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS organizer (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
            department TEXT NOT NULL, photo TEXT DEFAULT '',
            base_price INTEGER DEFAULT 100, price_round INTEGER DEFAULT 1,
            is_sold INTEGER DEFAULT 0,
            sold_to_team INTEGER DEFAULT NULL, sold_price INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, logo TEXT DEFAULT '',
            owner_name TEXT NOT NULL, captain_name TEXT NOT NULL,
            owner_player_id INTEGER DEFAULT NULL,
            captain_player_id INTEGER DEFAULT NULL,
            reserve_player TEXT DEFAULT '',
            budget INTEGER DEFAULT 1000, remaining_budget INTEGER DEFAULT 1000,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS auctions (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            current_player_id INTEGER DEFAULT NULL,
            current_bid INTEGER DEFAULT 0,
            current_bidder_team INTEGER DEFAULT NULL,
            bid_increment INTEGER DEFAULT 50,
            total_budget_per_team INTEGER DEFAULT 1000,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bid_history (
            id INTEGER PRIMARY KEY, auction_id INTEGER, player_id INTEGER,
            team_id INTEGER, bid_amount INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS auction_players (
            id INTEGER PRIMARY KEY, auction_id INTEGER, player_id INTEGER,
            status TEXT DEFAULT 'pending', order_index INTEGER,
            price_round INTEGER DEFAULT 1
        );
        INSERT OR IGNORE INTO organizer (username, password, name)
        VALUES ('admin', 'admin123', 'Auction Organizer');
    ''')
    db.commit()
    db.close()

init_db()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def allowed_file(f): return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXT

def save_photo(file, sub):
    if file and allowed_file(file.filename):
        fn = str(int(datetime.now().timestamp())) + '_' + secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, sub, fn)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file.save(path)
        return f'uploads/{sub}/{fn}'
    return ''

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'organizer_id' not in session: return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

TYPES = ['Batsman','Bowler','Fielder','All-Rounder','Wicket-Keeper']
DEPTS = ['R&D','QA','Development','DevOps','Design','Data Science','Management','Sales','Marketing','HR','Finance','Support']

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.route('/')
def index(): return redirect(url_for('dashboard') if 'organizer_id' in session else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        org = db.execute('SELECT * FROM organizer WHERE username=? AND password=?',
                         (request.form['username'], request.form['password'])).fetchone()
        db.close()
        if org:
            session['organizer_id'] = org['id']
            session['organizer_name'] = org['name']
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    players = db.execute('SELECT * FROM players ORDER BY created_at DESC').fetchall()
    teams   = db.execute('SELECT * FROM teams ORDER BY created_at DESC').fetchall()
    auctions= db.execute('SELECT * FROM auctions ORDER BY created_at DESC').fetchall()
    stats = {
        'total_players': len(players),
        'sold_players':  sum(1 for p in players if p['is_sold']),
        'total_teams':   len(teams),
        'active_auctions': sum(1 for a in auctions if a['status']=='active'),
    }
    db.close()
    return render_template('dashboard.html', stats=stats, players=players[:5], teams=teams[:5], auctions=auctions)

# ── PLAYERS ───────────────────────────────────────────────────────────────────
@app.route('/players')
@login_required
def players():
    db = get_db()
    rows = db.execute('''SELECT p.*, t.name as team_name FROM players p
        LEFT JOIN teams t ON p.sold_to_team=t.id ORDER BY p.created_at DESC''').fetchall()
    db.close()
    return render_template('players.html', players=rows, types=TYPES, departments=DEPTS)

@app.route('/players/add', methods=['GET','POST'])
@login_required
def add_player():
    if request.method == 'POST':
        photo = save_photo(request.files.get('photo'), 'players')
        db = get_db()
        base_price = int(request.form.get('base_price', 100000))
        # Determine price_round from base_price
        if base_price >= 100000:
            price_round = 1
        elif base_price >= 70000:
            price_round = 2
        else:
            price_round = 3
        db.execute('INSERT INTO players (name,type,department,photo,base_price,price_round) VALUES (?,?,?,?,?,?)',
                   (request.form['name'], request.form['type'], request.form['department'],
                    photo, base_price, price_round))
        db.commit(); db.close()
        flash('Player registered!', 'success')
        return redirect(url_for('players'))
    return render_template('player_form.html', types=TYPES, departments=DEPTS, player=None)

@app.route('/players/<int:pid>', methods=['GET'])
@login_required
def player_profile(pid):
    db = get_db()
    player = db.execute('''SELECT p.*, t.name as team_name, t.logo as team_logo, t.owner_name
        FROM players p LEFT JOIN teams t ON p.sold_to_team=t.id WHERE p.id=?''', (pid,)).fetchone()
    history = db.execute('''SELECT bh.*, t.name as team_name, a.title as auction_title
        FROM bid_history bh JOIN teams t ON bh.team_id=t.id JOIN auctions a ON bh.auction_id=a.id
        WHERE bh.player_id=? ORDER BY bh.timestamp DESC''', (pid,)).fetchall()
    db.close()
    return render_template('player_profile.html', player=player, bid_history=history)

@app.route('/players/edit/<int:pid>', methods=['GET','POST'])
@login_required
def edit_player(pid):
    db = get_db()
    player = db.execute('SELECT * FROM players WHERE id=?', (pid,)).fetchone()
    if request.method == 'POST':
        photo = save_photo(request.files.get('photo'), 'players') or player['photo']
        base_price = int(request.form.get('base_price', 100000))
        price_round = 1 if base_price >= 100000 else (2 if base_price >= 70000 else 3)
        db.execute('UPDATE players SET name=?,type=?,department=?,photo=?,base_price=?,price_round=? WHERE id=?',
                   (request.form['name'], request.form['type'], request.form['department'],
                    photo, base_price, price_round, pid))
        db.commit(); db.close()
        flash('Player updated!', 'success')
        return redirect(url_for('players'))
    db.close()
    return render_template('player_form.html', types=TYPES, departments=DEPTS, player=player)

@app.route('/players/delete/<int:pid>')
@login_required
def delete_player(pid):
    db = get_db()
    db.execute('DELETE FROM players WHERE id=?', (pid,))
    db.commit(); db.close()
    flash('Player deleted.', 'info')
    return redirect(url_for('players'))

# ── TEAMS ─────────────────────────────────────────────────────────────────────
@app.route('/teams')
@login_required
def teams():
    db = get_db()
    rows = db.execute('''SELECT t.*, COUNT(p.id) as player_count
        FROM teams t LEFT JOIN players p ON p.sold_to_team=t.id
        GROUP BY t.id ORDER BY t.created_at DESC''').fetchall()
    db.close()
    return render_template('teams.html', teams=rows)

@app.route('/teams/add', methods=['GET','POST'])
@login_required
def add_team():
    db = get_db()
    if request.method == 'POST':
        logo = save_photo(request.files.get('logo'), 'teams')
        budget = int(request.form.get('budget', 1000))
        captain_pid = request.form.get('captain_player_id') or None
        owner_pid   = request.form.get('owner_player_id') or None
        # Get captain & owner names and deduct base prices from budget
        deduction = 0
        captain_name = ''
        owner_name = ''
        if captain_pid:
            cp = db.execute('SELECT * FROM players WHERE id=?', (captain_pid,)).fetchone()
            if cp:
                captain_name = cp['name']
                deduction += cp['base_price']
        if owner_pid:
            op = db.execute('SELECT * FROM players WHERE id=?', (owner_pid,)).fetchone()
            if op:
                owner_name = op['name']
                if owner_pid != captain_pid:  # don't double-deduct if same person
                    deduction += op['base_price']
        remaining = max(0, budget - deduction)
        db.execute('''INSERT INTO teams
            (name,logo,owner_name,captain_name,owner_player_id,captain_player_id,reserve_player,budget,remaining_budget)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (request.form['name'], logo, owner_name or request.form.get('owner_name',''),
             captain_name or request.form.get('captain_name',''),
             owner_pid, captain_pid,
             request.form.get('reserve_player',''), budget, remaining))
        # Mark captain and owner as pre-assigned (is_sold=2 means pre-assigned to team)
        tid = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        if captain_pid:
            db.execute('UPDATE players SET is_sold=1, sold_to_team=?, sold_price=? WHERE id=?',
                       (tid, cp['base_price'] if cp else 0, captain_pid))
        if owner_pid and owner_pid != captain_pid:
            db.execute('UPDATE players SET is_sold=1, sold_to_team=?, sold_price=? WHERE id=?',
                       (tid, op['base_price'] if op else 0, owner_pid))
        db.commit(); db.close()
        flash(f'Team registered! Budget ₹{budget} - ₹{deduction} (captain/owner) = ₹{remaining} remaining.', 'success')
        return redirect(url_for('teams'))
    players_list = db.execute('SELECT id, name, type, department, base_price FROM players WHERE is_sold=0 ORDER BY base_price DESC, name').fetchall()
    db.close()
    return render_template('team_form.html', team=None, players=players_list)

@app.route('/teams/edit/<int:tid>', methods=['GET','POST'])
@login_required
def edit_team(tid):
    db = get_db()
    team = db.execute('SELECT * FROM teams WHERE id=?', (tid,)).fetchone()
    if request.method == 'POST':
        logo = save_photo(request.files.get('logo'), 'teams') or team['logo']
        budget = int(request.form.get('budget', team['budget']))
        captain_pid = request.form.get('captain_player_id') or None
        owner_pid   = request.form.get('owner_player_id') or None
        # Release old captain/owner if changed
        old_cap = team['captain_player_id']
        old_own = team['owner_player_id']
        if old_cap and str(old_cap) != str(captain_pid):
            db.execute('UPDATE players SET is_sold=0, sold_to_team=NULL, sold_price=NULL WHERE id=? AND sold_to_team=?', (old_cap, tid))
        if old_own and str(old_own) != str(owner_pid) and old_own != old_cap:
            db.execute('UPDATE players SET is_sold=0, sold_to_team=NULL, sold_price=NULL WHERE id=? AND sold_to_team=?', (old_own, tid))
        # Deduct new captain/owner
        deduction = 0
        captain_name = team['captain_name']
        owner_name = team['owner_name']
        cp = op = None
        if captain_pid:
            cp = db.execute('SELECT * FROM players WHERE id=?', (captain_pid,)).fetchone()
            if cp: captain_name = cp['name']; deduction += cp['base_price']
        if owner_pid:
            op = db.execute('SELECT * FROM players WHERE id=?', (owner_pid,)).fetchone()
            if op: owner_name = op['name']
            if op and owner_pid != captain_pid: deduction += op['base_price']
        remaining = max(0, budget - deduction)
        db.execute('''UPDATE teams SET name=?,logo=?,owner_name=?,captain_name=?,
            owner_player_id=?,captain_player_id=?,reserve_player=?,budget=?,remaining_budget=? WHERE id=?''',
            (request.form['name'], logo, owner_name, captain_name,
             owner_pid, captain_pid,
             request.form.get('reserve_player',''), budget, remaining, tid))
        if captain_pid:
            db.execute('UPDATE players SET is_sold=1, sold_to_team=?, sold_price=? WHERE id=?',
                       (tid, cp['base_price'] if cp else 0, captain_pid))
        if owner_pid and owner_pid != captain_pid:
            db.execute('UPDATE players SET is_sold=1, sold_to_team=?, sold_price=? WHERE id=?',
                       (tid, op['base_price'] if op else 0, owner_pid))
        db.commit(); db.close()
        flash('Team updated!', 'success')
        return redirect(url_for('teams'))
    # Players available + current captain/owner (to keep them in dropdown)
    players_list = db.execute('''
        SELECT id, name, type, department, base_price FROM players
        WHERE is_sold=0 OR id=? OR id=?
        ORDER BY base_price DESC, name''',
        (team['captain_player_id'] or 0, team['owner_player_id'] or 0)).fetchall()
    db.close()
    return render_template('team_form.html', team=team, players=players_list)

@app.route('/teams/delete/<int:tid>')
@login_required
def delete_team(tid):
    db = get_db()
    db.execute('DELETE FROM teams WHERE id=?', (tid,))
    db.commit(); db.close()
    flash('Team deleted.', 'info')
    return redirect(url_for('teams'))

@app.route('/teams/<int:tid>/squad')
@login_required
def team_squad(tid):
    db = get_db()
    team  = db.execute('SELECT * FROM teams WHERE id=?', (tid,)).fetchone()
    squad = db.execute('SELECT * FROM players WHERE sold_to_team=?', (tid,)).fetchall()
    history = db.execute('''SELECT bh.*, p.name as player_name FROM bid_history bh
        JOIN players p ON bh.player_id=p.id WHERE bh.team_id=? ORDER BY bh.timestamp DESC''', (tid,)).fetchall()
    db.close()
    return render_template('squad.html', team=team, squad=squad, history=history)

# ── TEAM VIEW (read-only live dashboard for team owners) ──────────────────────
@app.route('/team-view/<int:tid>')
def team_view(tid):
    db = get_db()
    team   = db.execute('SELECT * FROM teams WHERE id=?', (tid,)).fetchone()
    if not team: return "Team not found", 404
    squad  = db.execute('SELECT * FROM players WHERE sold_to_team=? ORDER BY type', (tid,)).fetchall()
    # Get active auction if any
    auction = db.execute("SELECT * FROM auctions WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
    all_teams = db.execute('SELECT id, name, logo, remaining_budget, budget FROM teams ORDER BY name').fetchall()
    db.close()
    return render_template('team_view.html', team=team, squad=squad, auction=auction, all_teams=all_teams)

# ── AUCTIONS ──────────────────────────────────────────────────────────────────
@app.route('/auctions')
@login_required
def auctions():
    db = get_db()
    rows = db.execute('SELECT * FROM auctions ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('auctions.html', auctions=rows)

@app.route('/auctions/create', methods=['GET','POST'])
@login_required
def create_auction():
    if request.method == 'POST':
        budget = int(request.form.get('budget_per_team', 1000))
        incr   = int(request.form.get('bid_increment', 50))
        db = get_db()
        aid = db.execute("INSERT INTO auctions (title,bid_increment,total_budget_per_team,status) VALUES (?,?,?,'pending')",
                         (request.form['title'], incr, budget)).lastrowid
        db.execute('UPDATE teams SET budget=?, remaining_budget=?', (budget, budget))
        # Group players by price_round, shuffle within each round
        # Round 1 (₹1,00,000) goes first, then Round 2 (₹70,000), then Round 3 (₹50,000)
        all_players = []
        for rnd in [1, 2, 3]:
            rnd_players = list(db.execute(
                'SELECT id, price_round FROM players WHERE is_sold=0 AND price_round=?', (rnd,)
            ).fetchall())
            random.shuffle(rnd_players)
            all_players.extend(rnd_players)
        # If any players have no round set (old data), append them randomly at end
        no_round = list(db.execute(
            'SELECT id, price_round FROM players WHERE is_sold=0 AND price_round NOT IN (1,2,3)'
        ).fetchall())
        random.shuffle(no_round)
        all_players.extend(no_round)
        for i, p in enumerate(all_players):
            db.execute('INSERT INTO auction_players (auction_id,player_id,order_index,status,price_round) VALUES (?,?,?,?,?)',
                       (aid, p['id'], i, 'pending', p['price_round'] or 1))
        db.commit(); db.close()
        flash('Auction created!', 'success')
        return redirect(url_for('auction_room', aid=aid))
    db = get_db()
    teams = db.execute('SELECT * FROM teams').fetchall()
    db.close()
    return render_template('create_auction.html', teams=teams)

@app.route('/auctions/<int:aid>')
@login_required
def auction_room(aid):
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    teams   = db.execute('SELECT * FROM teams ORDER BY name').fetchall()
    pending = db.execute('''SELECT p.* FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='pending' ORDER BY ap.order_index''', (aid,)).fetchall()
    sold    = db.execute('''SELECT p.*, t.name as team_name FROM auction_players ap
        JOIN players p ON ap.player_id=p.id LEFT JOIN teams t ON p.sold_to_team=t.id
        WHERE ap.auction_id=? AND ap.status='sold' ORDER BY ap.order_index DESC''', (aid,)).fetchall()
    unsold  = db.execute('''SELECT p.* FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='unsold' ORDER BY p.name''', (aid,)).fetchall()
    current_player, current_bidder = None, None
    if auction['current_player_id']:
        current_player = db.execute('SELECT * FROM players WHERE id=?', (auction['current_player_id'],)).fetchone()
    if auction['current_bidder_team']:
        current_bidder = db.execute('SELECT * FROM teams WHERE id=?', (auction['current_bidder_team'],)).fetchone()
    bid_log = db.execute('''SELECT bh.*, t.name as team_name, p.name as player_name
        FROM bid_history bh JOIN teams t ON bh.team_id=t.id JOIN players p ON bh.player_id=p.id
        WHERE bh.auction_id=? ORDER BY bh.timestamp DESC LIMIT 20''', (aid,)).fetchall()
    # Safe sold total — handle None sold_price
    sold_total = sum(p['sold_price'] for p in sold if p['sold_price'] is not None)
    db.close()
    return render_template('auction_room.html', auction=auction, teams=teams,
                           pending=pending, sold=sold, unsold=unsold,
                           current_player=current_player, current_bidder=current_bidder,
                           bid_log=bid_log, sold_total=sold_total)

@app.route('/auctions/<int:aid>/results')
@login_required
def auction_results(aid):
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    teams   = db.execute('SELECT * FROM teams ORDER BY name').fetchall()
    sold_players = db.execute('''SELECT p.*, t.name as team_name, t.logo as team_logo
        FROM auction_players ap JOIN players p ON ap.player_id=p.id
        LEFT JOIN teams t ON p.sold_to_team=t.id
        WHERE ap.auction_id=? AND ap.status='sold' ORDER BY p.sold_price DESC''', (aid,)).fetchall()
    unsold_players = db.execute('''SELECT p.* FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='unsold' ORDER BY p.name''', (aid,)).fetchall()
    team_summary = []
    for t in teams:
        squad = db.execute('SELECT * FROM players WHERE sold_to_team=?', (t['id'],)).fetchall()
        spent = sum(p['sold_price'] for p in squad if p['sold_price'])
        types_count = {}
        for p in squad: types_count[p['type']] = types_count.get(p['type'],0)+1
        team_summary.append({'team':dict(t),'squad':[dict(p) for p in squad],
                              'total_spent':spent,'player_count':len(squad),'types':types_count})
    team_summary.sort(key=lambda x: x['total_spent'], reverse=True)
    top_bids = db.execute('''SELECT p.name as player_name, p.type, p.department, p.sold_price, t.name as team_name
        FROM players p JOIN teams t ON p.sold_to_team=t.id
        WHERE p.sold_price IS NOT NULL ORDER BY p.sold_price DESC LIMIT 5''').fetchall()
    sold_total = sum(p['sold_price'] for p in sold_players if p['sold_price'])
    db.close()
    return render_template('auction_results.html', auction=auction, teams=teams,
                           sold_players=sold_players, unsold_players=unsold_players,
                           team_summary=team_summary, top_bids=top_bids, sold_total=sold_total)

# ── SPECTATOR VIEW ────────────────────────────────────────────────────────────
@app.route('/watch/<int:aid>')
def spectator_view(aid):
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    teams   = db.execute('SELECT * FROM teams ORDER BY name').fetchall()
    db.close()
    if not auction: return "Auction not found", 404
    return render_template('spectator.html', auction=auction, teams=teams)

# ── CSV EXPORT ────────────────────────────────────────────────────────────────
@app.route('/auctions/<int:aid>/export')
@login_required
def export_results(aid):
    db = get_db()
    rows = db.execute('''SELECT p.name, p.type, p.department, p.base_price,
               COALESCE(p.sold_price,'UNSOLD') as final_price,
               COALESCE(t.name,'UNSOLD') as team, ap.status
        FROM auction_players ap JOIN players p ON ap.player_id=p.id
        LEFT JOIN teams t ON p.sold_to_team=t.id
        WHERE ap.auction_id=? ORDER BY ap.status, p.sold_price DESC''', (aid,)).fetchall()
    db.close()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Player','Type','Department','Base','Final Price','Team','Status'])
    for r in rows: w.writerow([r['name'],r['type'],r['department'],r['base_price'],r['final_price'],r['team'],r['status']])
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=auction_{aid}.csv'})

# ── SETTINGS ──────────────────────────────────────────────────────────────────
@app.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    db = get_db()
    org = db.execute('SELECT * FROM organizer WHERE id=?', (session['organizer_id'],)).fetchone()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            db.execute('UPDATE organizer SET name=? WHERE id=?', (request.form['name'], session['organizer_id']))
            session['organizer_name'] = request.form['name']
            flash('Profile updated!', 'success')
        elif action == 'change_password':
            if request.form['old_password'] == org['password']:
                db.execute('UPDATE organizer SET password=? WHERE id=?', (request.form['new_password'], session['organizer_id']))
                flash('Password changed!', 'success')
            else: flash('Wrong current password', 'error')
        elif action == 'reset_all':
            db.execute('UPDATE players SET is_sold=0, sold_to_team=NULL, sold_price=NULL')
            db.execute('UPDATE teams SET remaining_budget=budget')
            flash('All statuses reset!', 'info')
        db.commit(); db.close()
        return redirect(url_for('settings'))
    db.close()
    return render_template('settings.html', org=org)

# ══════════════════════════════════════════════════════════════════════════════
# ── JSON APIS ─────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/auction/<int:aid>/start', methods=['POST'])
@login_required
def auction_start(aid):
    db = get_db()
    db.execute("UPDATE auctions SET status='active' WHERE id=?", (aid,))
    db.commit(); db.close()
    return jsonify({'ok': True})

@app.route('/api/auction/<int:aid>/next_player', methods=['POST'])
@login_required
def next_player(aid):
    db = get_db()
    nxt = db.execute('''SELECT p.* FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='pending' ORDER BY ap.order_index LIMIT 1''', (aid,)).fetchone()
    if not nxt:
        db.execute("UPDATE auctions SET status='completed', current_player_id=NULL WHERE id=?", (aid,))
        db.commit(); db.close()
        return jsonify({'ok':True,'done':True})
    db.execute('UPDATE auctions SET current_player_id=?, current_bid=?, current_bidder_team=NULL WHERE id=?',
               (nxt['id'], nxt['base_price'], aid))
    db.commit()
    player = dict(nxt); db.close()
    return jsonify({'ok':True,'player':player})

@app.route('/api/auction/<int:aid>/bid', methods=['POST'])
@login_required
def place_bid(aid):
    data = request.json
    team_id = int(data['team_id'])
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    team    = db.execute('SELECT * FROM teams WHERE id=?', (team_id,)).fetchone()
    new_bid = auction['current_bid'] + auction['bid_increment']
    if team['remaining_budget'] < new_bid:
        db.close(); return jsonify({'ok':False,'error':'Insufficient budget'})
    db.execute('UPDATE auctions SET current_bid=?, current_bidder_team=? WHERE id=?', (new_bid, team_id, aid))
    db.execute('INSERT INTO bid_history (auction_id,player_id,team_id,bid_amount) VALUES (?,?,?,?)',
               (aid, auction['current_player_id'], team_id, new_bid))
    db.commit(); db.close()
    return jsonify({'ok':True,'new_bid':new_bid})

@app.route('/api/auction/<int:aid>/sell', methods=['POST'])
@login_required
def sell_player(aid):
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    if not auction['current_bidder_team'] or not auction['current_player_id']:
        db.close(); return jsonify({'ok':False,'error':'No active bid'})
    pid, tid, price = auction['current_player_id'], auction['current_bidder_team'], auction['current_bid']
    db.execute('UPDATE players SET is_sold=1, sold_to_team=?, sold_price=? WHERE id=?', (tid, price, pid))
    db.execute('UPDATE teams SET remaining_budget=remaining_budget-? WHERE id=?', (price, tid))
    db.execute("UPDATE auction_players SET status='sold' WHERE auction_id=? AND player_id=?", (aid, pid))
    db.execute('UPDATE auctions SET current_player_id=NULL, current_bid=0, current_bidder_team=NULL WHERE id=?', (aid,))
    db.commit()
    team   = dict(db.execute('SELECT * FROM teams WHERE id=?', (tid,)).fetchone())
    player = dict(db.execute('SELECT * FROM players WHERE id=?', (pid,)).fetchone())
    db.close()
    return jsonify({'ok':True,'player':player,'team':team,'price':price})

@app.route('/api/auction/<int:aid>/unsold', methods=['POST'])
@login_required
def mark_unsold(aid):
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    pid = auction['current_player_id']
    if pid:
        db.execute("UPDATE auction_players SET status='unsold' WHERE auction_id=? AND player_id=?", (aid, pid))
        db.execute('UPDATE auctions SET current_player_id=NULL, current_bid=0, current_bidder_team=NULL WHERE id=?', (aid,))
        db.commit()
    db.close()
    return jsonify({'ok':True})

@app.route('/api/auction/<int:aid>/rebid_unsold', methods=['POST'])
@login_required
def rebid_unsold(aid):
    data = request.json
    player_id = int(data['player_id'])
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    if auction['current_player_id']:
        db.close(); return jsonify({'ok':False,'error':'Finish current player first'})
    max_order = db.execute('SELECT MAX(order_index) FROM auction_players WHERE auction_id=?', (aid,)).fetchone()[0] or 0
    db.execute("UPDATE auction_players SET status='pending', order_index=? WHERE auction_id=? AND player_id=?",
               (max_order+1, aid, player_id))
    player = dict(db.execute('SELECT * FROM players WHERE id=?', (player_id,)).fetchone())
    db.commit(); db.close()
    return jsonify({'ok':True,'player':player})

@app.route('/api/auction/<int:aid>/rtm', methods=['POST'])
@login_required
def use_rtm(aid):
    data = request.json
    team_id = int(data['team_id'])
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    team    = db.execute('SELECT * FROM teams WHERE id=?', (team_id,)).fetchone()
    cur_bid = auction['current_bid']
    if team['remaining_budget'] < cur_bid:
        db.close(); return jsonify({'ok':False,'error':'Insufficient budget'})
    if not auction['current_bidder_team'] or auction['current_bidder_team'] == team_id:
        db.close(); return jsonify({'ok':False,'error':'Cannot RTM your own bid'})
    db.execute('UPDATE auctions SET current_bidder_team=? WHERE id=?', (team_id, aid))
    db.execute('INSERT INTO bid_history (auction_id,player_id,team_id,bid_amount) VALUES (?,?,?,?)',
               (aid, auction['current_player_id'], team_id, cur_bid))
    db.commit(); db.close()
    return jsonify({'ok':True,'matched_bid':cur_bid})

@app.route('/api/auction/<int:aid>/unsold_list')
def get_unsold_list(aid):
    db = get_db()
    rows = db.execute('''SELECT p.id, p.name, p.type, p.department, p.photo, p.base_price
        FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='unsold' ORDER BY p.name''', (aid,)).fetchall()
    db.close()
    return jsonify({'unsold':[dict(r) for r in rows]})

# Master state API — /state and /full_state both work
@app.route('/api/auction/<int:aid>/state')
@app.route('/api/auction/<int:aid>/full_state')
def auction_full_state(aid):
    db = get_db()
    auction = db.execute('SELECT * FROM auctions WHERE id=?', (aid,)).fetchone()
    if not auction:
        db.close()
        return jsonify({'error': 'Auction not found', 'status': 'unknown',
                        'current_player': None, 'current_bid': 0, 'current_bidder': None,
                        'bid_increment': 50, 'teams': [], 'team_counts': {}, 'bid_log': [],
                        'pending_count': 0, 'sold_count': 0, 'unsold_count': 0,
                        'pending_players': [], 'sold_players': [], 'unsold_players': []})
    current_player, current_bidder = None, None
    if auction['current_player_id']:
        p = db.execute('SELECT * FROM players WHERE id=?', (auction['current_player_id'],)).fetchone()
        current_player = dict(p) if p else None
    if auction['current_bidder_team']:
        t = db.execute('SELECT * FROM teams WHERE id=?', (auction['current_bidder_team'],)).fetchone()
        current_bidder = dict(t) if t else None
    teams = db.execute('SELECT id, name, remaining_budget, budget, logo FROM teams').fetchall()
    bid_log = db.execute('''SELECT bh.bid_amount, t.name as team_name, p.name as player_name, bh.timestamp
        FROM bid_history bh JOIN teams t ON bh.team_id=t.id JOIN players p ON bh.player_id=p.id
        WHERE bh.auction_id=? ORDER BY bh.timestamp DESC LIMIT 15''', (aid,)).fetchall()
    pending_count = db.execute("SELECT COUNT(*) FROM auction_players WHERE auction_id=? AND status='pending'", (aid,)).fetchone()[0]
    sold_count    = db.execute("SELECT COUNT(*) FROM auction_players WHERE auction_id=? AND status='sold'", (aid,)).fetchone()[0]
    unsold_count  = db.execute("SELECT COUNT(*) FROM auction_players WHERE auction_id=? AND status='unsold'", (aid,)).fetchone()[0]
    pending_players = db.execute('''SELECT p.id, p.name, p.type, p.department, p.photo, p.base_price
        FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='pending' ORDER BY ap.order_index LIMIT 30''', (aid,)).fetchall()
    sold_players = db.execute('''SELECT p.id, p.name, p.type, p.photo, p.sold_price, t.name as team_name, t.logo as team_logo
        FROM auction_players ap JOIN players p ON ap.player_id=p.id
        LEFT JOIN teams t ON p.sold_to_team=t.id
        WHERE ap.auction_id=? AND ap.status='sold' ORDER BY ap.order_index DESC LIMIT 20''', (aid,)).fetchall()
    unsold_players = db.execute('''SELECT p.id, p.name, p.type, p.department, p.photo, p.base_price
        FROM auction_players ap JOIN players p ON ap.player_id=p.id
        WHERE ap.auction_id=? AND ap.status='unsold' ORDER BY p.name''', (aid,)).fetchall()
    team_counts = {}
    for r in db.execute('SELECT sold_to_team, COUNT(*) as cnt FROM players WHERE sold_to_team IS NOT NULL GROUP BY sold_to_team').fetchall():
        team_counts[r['sold_to_team']] = r['cnt']
    db.close()
    return jsonify({
        'status': auction['status'],
        'current_player': current_player,
        'current_bid': auction['current_bid'],
        'current_bidder': current_bidder,
        'bid_increment': auction['bid_increment'],
        'teams': [dict(t) for t in teams],
        'team_counts': team_counts,
        'bid_log': [dict(b) for b in bid_log],
        'pending_count': pending_count, 'sold_count': sold_count, 'unsold_count': unsold_count,
        'pending_players': [dict(p) for p in pending_players],
        'sold_players':    [dict(p) for p in sold_players],
        'unsold_players':  [dict(p) for p in unsold_players],
    })

# Team-specific state (for team view)
@app.route('/api/team/<int:tid>/state')
def team_state(tid):
    db = get_db()
    team  = db.execute('SELECT * FROM teams WHERE id=?', (tid,)).fetchone()
    if not team:
        db.close()
        return jsonify({'error': 'Team not found'}), 404
    squad = db.execute('''SELECT p.* FROM players p WHERE p.sold_to_team=?
        ORDER BY p.type, p.sold_price DESC''', (tid,)).fetchall()
    auction = db.execute("SELECT * FROM auctions WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
    result = {
        'team': dict(team),
        'squad': [dict(p) for p in squad],
        'squad_count': len(squad),
    }
    if auction:
        aid = auction['id']
        current_player, current_bidder = None, None
        if auction['current_player_id']:
            p = db.execute('SELECT * FROM players WHERE id=?', (auction['current_player_id'],)).fetchone()
            current_player = dict(p) if p else None
        if auction['current_bidder_team']:
            t = db.execute('SELECT * FROM teams WHERE id=?', (auction['current_bidder_team'],)).fetchone()
            current_bidder = dict(t) if t else None
        bid_log = db.execute('''SELECT bh.bid_amount, t.name as team_name, p.name as player_name
            FROM bid_history bh JOIN teams t ON bh.team_id=t.id JOIN players p ON bh.player_id=p.id
            WHERE bh.auction_id=? ORDER BY bh.timestamp DESC LIMIT 10''', (aid,)).fetchall()
        all_teams = db.execute('SELECT id, name, logo, remaining_budget, budget FROM teams ORDER BY name').fetchall()
        # Similar players to current — suggest bid
        suggestion = None
        cur_bid = auction['current_bid'] or 0
        if current_player and team['remaining_budget'] >= cur_bid + auction['bid_increment']:
            # Find how many of this type the team already has
            type_count = sum(1 for p in squad if p['type'] == current_player['type'])
            needs_type = type_count < 3
            can_afford = team['remaining_budget'] >= cur_bid + auction['bid_increment']
            pct_budget_left = team['remaining_budget'] / team['budget'] if team['budget'] else 0
            if needs_type and pct_budget_left > 0.2:
                suggestion = {'recommend': True, 'reason': f'You need more {current_player["type"]}s ({type_count} so far). Budget OK.'}
            elif not needs_type and pct_budget_left < 0.3:
                suggestion = {'recommend': False, 'reason': f'You already have {type_count} {current_player["type"]}s and budget is low.'}
            elif can_afford:
                suggestion = {'recommend': True, 'reason': f'You can afford to bid. Current bid: ₹{cur_bid}.'}
            else:
                suggestion = {'recommend': False, 'reason': 'Budget tight — consider skipping.'}
        # Pending players for queue
        pending_players = db.execute('''
            SELECT p.id, p.name, p.type, p.department, p.photo, p.base_price
            FROM auction_players ap JOIN players p ON ap.player_id=p.id
            WHERE ap.auction_id=? AND ap.status='pending'
            ORDER BY ap.order_index''', (aid,)).fetchall()

        # Unsold players
        unsold_players = db.execute('''
            SELECT p.id, p.name, p.type, p.department, p.photo, p.base_price
            FROM auction_players ap JOIN players p ON ap.player_id=p.id
            WHERE ap.auction_id=? AND ap.status='unsold'
            ORDER BY p.name''', (aid,)).fetchall()

        # All sold players in auction
        sold_in_auction = db.execute('''
            SELECT p.id, p.name, p.type, p.photo, p.sold_price,
                   t.name as team_name, t.logo as team_logo, t.id as team_id
            FROM auction_players ap
            JOIN players p ON ap.player_id=p.id
            LEFT JOIN teams t ON p.sold_to_team=t.id
            WHERE ap.auction_id=? AND ap.status='sold'
            ORDER BY ap.order_index DESC''', (aid,)).fetchall()

        result.update({
            'auction_id': aid,
            'auction_title': auction['title'],
            'auction_status': auction['status'],
            'current_player': current_player,
            'current_bid': auction['current_bid'],
            'bid_increment': auction['bid_increment'],
            'current_bidder': current_bidder,
            'bid_log': [dict(b) for b in bid_log],
            'all_teams': [dict(t) for t in all_teams],
            'suggestion': suggestion,
            'pending_players':  [dict(p) for p in pending_players],
            'unsold_players':   [dict(p) for p in unsold_players],
            'sold_players':     [dict(p) for p in sold_in_auction],
            'pending_count':    len(pending_players),
            'sold_count':       len(sold_in_auction),
            'unsold_count':     len(unsold_players),
        })
    db.close()
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
