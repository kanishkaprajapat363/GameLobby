from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_bcrypt import Bcrypt
import mysql.connector
import math
import random
from player_dashboard import init_player_routes


app = Flask(__name__)
app.secret_key = "secretkey"
bcrypt = Bcrypt(app)

# MySQL Connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="chiniSang$363",
    database="gamelobby"
)
cursor = db.cursor(dictionary=True)

# ---------- SIGNUP ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        role = request.form['role']

        cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s,%s,%s,%s)",
                       (username, email, password, role))
        db.commit()
        return redirect('/login')
    return render_template('signup.html')

# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username=%s AND role=%s", (username, role))
        user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']

            if user['role'] == 'player':
                return redirect('/player_dashboard')
            elif user['role'] == 'host':
                return redirect('/host_dashboard')
            elif user['role'] == 'admin':
                return redirect('/admin_dashboard')
        else:
            return "Invalid Credentials"
    return render_template('login.html')

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------- CREATE TOURNAMENT ----------
@app.route('/create_tournament', methods=['GET', 'POST'])
def create_tournament():
    if 'role' in session and session['role'] == 'host':
        if request.method == 'POST':
            tname = request.form['tname']
            game_type = request.form['game_type']
            game_format = request.form['format_type']  # renamed variable
            t_date = request.form['t_date']
            host_id = get_current_user_id(session['username'])

            cursor.execute(
                "INSERT INTO tournaments (tname, game_type, game_format, host_id, t_date) VALUES (%s,%s,%s,%s,%s)",
                (tname, game_type, game_format, host_id, t_date)
            )
            db.commit()
            return redirect('/host_dashboard')
        return render_template('create_tournament.html')
    return redirect('/login')




# Helper function to get current user ID from username
def get_current_user_id(username):
    cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    return user['id'] if user else None

#-----------ADDING PARTICIPANTS--------
@app.route('/add_participants/<int:tid>', methods=['GET', 'POST'])
def add_participants(tid):
    if 'role' in session and session['role'] == 'host':
        # Get tournament info
        cursor.execute("SELECT * FROM tournaments WHERE tid=%s", (tid,))
        tournament = cursor.fetchone()

        # Get all players
        cursor.execute("SELECT id, username FROM users WHERE role='player'")
        players = cursor.fetchall()

        if request.method == 'POST':
            selected_users = request.form.getlist('players')  # list of user IDs

            for user_id in selected_users:
                try:
                    cursor.execute(
                        "INSERT INTO participants (tid, user_id) VALUES (%s, %s)",
                        (tid, user_id)
                    )
                except mysql.connector.IntegrityError:
                    # Duplicate participant, skip
                    continue

            db.commit()
            flash("Participants added successfully!", "success")
            return redirect('/host_dashboard')

        return render_template('add_participants.html', tournament=tournament, players=players)
    return redirect('/login')


@app.route('/remove_participants/<int:tid>', methods=['GET', 'POST'])
def remove_participants(tid):
    if 'role' in session and session['role'] == 'host':
        # Get tournament info
        cursor.execute("SELECT * FROM tournaments WHERE tid=%s", (tid,))
        tournament = cursor.fetchone()

        # Get all participants for this tournament
        cursor.execute(
            "SELECT u.id, u.username FROM participants p "
            "JOIN users u ON p.user_id = u.id "
            "WHERE p.tid=%s", (tid,)
        )
        participants = cursor.fetchall()

        if request.method == 'POST':
            # Remove selected participants
            selected_users = request.form.getlist('participants')  # list of user IDs
            for user_id in selected_users:
                cursor.execute(
                    "DELETE FROM participants WHERE tid=%s AND user_id=%s",
                    (tid, user_id)
                )
            db.commit()
            flash("Selected participants removed successfully!", "success")
            return redirect('/host_dashboard')

        return render_template(
            'remove_participants.html',
            tournament=tournament,
            participants=participants
        )
    return redirect('/login')

@app.route('/remove_all_participants/<int:tid>')
def remove_all_participants(tid):
    if 'role' in session and session['role'] == 'host':
        # 1️⃣ Delete all participants
        cursor.execute("DELETE FROM participants WHERE tid=%s", (tid,))

        # 2️⃣ Delete all matches for this tournament
        cursor.execute("DELETE FROM matches WHERE tid=%s", (tid,))

        db.commit()
        flash("All participants and associated matches removed successfully!", "success")
        return redirect('/host_dashboard')
    return redirect('/login')



import random, math
from flask import flash
def generate_single_elimination_bracket(tid):
    # Avoid duplicate generation
    cursor.execute("SELECT COUNT(*) AS cnt FROM matches WHERE tid=%s", (tid,))
    if cursor.fetchone()["cnt"] > 0:
        flash("Bracket already generated for this tournament.", "error")
        return

    # Participants
    cursor.execute("SELECT user_id FROM participants WHERE tid=%s", (tid,))
    participants = [p["user_id"] for p in cursor.fetchall()]
    if not participants:
        flash("No participants selected! Cannot generate bracket.", "error")
        return

    random.shuffle(participants)
    n = len(participants)

    # Round 1
    round_no = 1
    i = 0
    while i < n:
        p1 = participants[i]
        i += 1
        p2 = participants[i] if i < n else None
        i += 1 if p2 is not None else 0

        # Handle BYE automatically
        if p1 is not None and p2 is None:
            cursor.execute(
                "INSERT INTO matches (tid, round_no, player1_id, player2_id, winner_id, match_status) "
                "VALUES (%s, %s, %s, %s, %s, 'completed')",
                (tid, round_no, p1, None, p1)
            )
        elif p1 is not None and p2 is not None:
            cursor.execute(
                "INSERT INTO matches (tid, round_no, player1_id, player2_id, match_status) "
                "VALUES (%s, %s, %s, %s, 'pending')",
                (tid, round_no, p1, p2)
            )

    db.commit()
    flash(f"Bracket generated for {n} players.", "success")


@app.route('/generate_bracket/<int:tid>')
def generate_bracket(tid):
    if 'role' in session and session['role'] == 'host':
        generate_single_elimination_bracket(tid)
        return redirect('/host_dashboard')
    return redirect('/login')

def get_participant_count(tid):
    cursor.execute("SELECT COUNT(*) as cnt FROM participants WHERE tid=%s", (tid,))
    result = cursor.fetchone()
    return result['cnt'] if result else 0

from flask import render_template, redirect, url_for, request, flash

@app.route('/view_bracket/<int:tid>')
def view_bracket(tid):
    # Tournament info
    cursor.execute("SELECT * FROM tournaments WHERE tid=%s", (tid,))
    tournament = cursor.fetchone()
    if not tournament:
        return "Tournament not found", 404

    # Fetch matches with player names and winner name
    cursor.execute("""
        SELECT 
            m.mid, m.tid, m.round_no, m.player1_id, m.player2_id, m.winner_id, m.match_status,
            u1.username AS p1_name,
            u2.username AS p2_name,
            uw.username AS winner_name
        FROM matches m
        LEFT JOIN users u1 ON m.player1_id = u1.id
        LEFT JOIN users u2 ON m.player2_id = u2.id
        LEFT JOIN users uw ON m.winner_id = uw.id
        WHERE m.tid=%s
        ORDER BY m.round_no, m.mid
    """, (tid,))
    rows = cursor.fetchall()

    # Group by round for the template
    rounds = {}
    for r in rows:
        entry = {
            "mid": r["mid"],
            "player1": r["p1_name"],           # may be None -> BYE
            "player2": r["p2_name"],           # may be None -> BYE
            "player1_id": r["player1_id"],
            "player2_id": r["player2_id"],
            "winner": r["winner_name"],        # may be None until set
            "winner_id": r["winner_id"],
            "match_status": r["match_status"]
        }
        rounds.setdefault(r["round_no"], []).append(entry)

    return render_template("view_bracket.html", tournament=tournament, rounds=rounds)


@app.route('/set_winner/<int:mid>', methods=['POST'])
def set_winner(mid):
    if 'role' not in session or session['role'] != 'host':
        return redirect('/login')

    winner_id = request.form.get('winner_id')
    if winner_id:
        cursor.execute("UPDATE matches SET winner_id=%s, match_status='completed' WHERE mid=%s", (winner_id, mid))
        db.commit()
    return redirect(request.referrer)



@app.route('/advance_round/<int:tid>', methods=['POST'])
def advance_round(tid):
    if 'role' not in session or session['role'] != 'host':
        return redirect('/login')

    # 1️⃣ Find current max round
    cursor.execute("SELECT COALESCE(MAX(round_no), 0) AS max_round FROM matches WHERE tid=%s", (tid,))
    current_round = cursor.fetchone()["max_round"]

    if current_round == 0:
        flash("No matches found to advance.", "error")
        return redirect(url_for('view_bracket', tid=tid))

    # 2️⃣ Ensure all matches in current round are completed
    cursor.execute("""
        SELECT COUNT(*) AS pending_cnt
        FROM matches
        WHERE tid=%s AND round_no=%s AND match_status <> 'completed'
    """, (tid, current_round))
    if cursor.fetchone()["pending_cnt"] > 0:
        flash("Finish all matches in the current round before advancing.", "error")
        return redirect(url_for('view_bracket', tid=tid))

    # 3️⃣ Collect winners of current round
    cursor.execute("""
        SELECT winner_id
        FROM matches
        WHERE tid=%s AND round_no=%s
        ORDER BY mid
    """, (tid, current_round))
    winners = [row["winner_id"] for row in cursor.fetchall() if row["winner_id"] is not None]

    if len(winners) <= 1:
        # Tournament complete
        if winners:
            cursor.execute("UPDATE tournaments SET status='completed' WHERE tid=%s", (tid,))
            db.commit()
            flash("Tournament completed! Winner determined.", "success")
        else:
            flash("No winners to advance.", "error")
        return redirect(url_for('view_bracket', tid=tid))

    # 4️⃣ Pair winners for next round
    next_round = current_round + 1
    for i in range(0, len(winners), 2):
        p1 = winners[i]
        p2 = winners[i + 1] if i + 1 < len(winners) else None  # BYE if odd number
        if p2 is None:
            # Auto-advance the single player
            cursor.execute(
                "INSERT INTO matches (tid, round_no, player1_id, player2_id, winner_id, match_status) "
                "VALUES (%s, %s, %s, %s, %s, 'completed')",
                (tid, next_round, p1, None, p1)
            )
        else:
            cursor.execute(
                "INSERT INTO matches (tid, round_no, player1_id, player2_id, match_status) "
                "VALUES (%s, %s, %s, %s, 'pending')",
                (tid, next_round, p1, p2)
            )

    db.commit()
    flash(f"Advanced to Round {next_round}.", "success")
    return redirect(url_for('view_bracket', tid=tid))









# ---------- DASHBOARDS ----------

#accessing player dashboard
init_player_routes(app, db, cursor)


@app.route('/host_dashboard')
def host_dashboard():
    if 'role' in session and session['role'] == 'host':
        # Get tournaments created by this host
        cursor.execute("SELECT * FROM tournaments WHERE host_id=(SELECT id FROM users WHERE username=%s)", (session['username'],))
        tournaments = cursor.fetchall()

        # Get participant counts for each tournament
        for t in tournaments:
            t['participant_count'] = get_participant_count(t['tid'])

        return render_template("host_dashboard.html", username=session['username'], tournaments=tournaments)
    return redirect('/login')


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        return render_template("admin_dashboard.html", username=session['username'])
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
