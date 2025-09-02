from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_bcrypt import Bcrypt
import mysql.connector
import math
import random

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



def generate_single_elimination_bracket(tid):
    # 1️⃣ Check if matches already exist
    cursor.execute("SELECT COUNT(*) as cnt FROM matches WHERE tid=%s", (tid,))
    if cursor.fetchone()['cnt'] > 0:
        flash("Bracket already generated for this tournament.", "error")
        return

    # 2️⃣ Fetch participants
    cursor.execute("SELECT user_id FROM participants WHERE tid=%s", (tid,))
    participants = [p['user_id'] for p in cursor.fetchall()]

    if not participants:
        flash("No participants selected! Cannot generate bracket.", "error")
        return

    # 3️⃣ Shuffle participants for fairness
    random.shuffle(participants)

    # 4️⃣ Calculate next power of 2 and add BYEs
    n_players = len(participants)
    next_pow2 = 2 ** math.ceil(math.log2(n_players))
    byes = next_pow2 - n_players
    participants.extend([None] * byes)  # None = BYE

    # 5️⃣ Generate first round matches (each player exactly one match)
    round_no = 1
    matches = []
    for i in range(0, len(participants), 2):
        p1 = participants[i]
        p2 = participants[i + 1]
        matches.append((p1, p2))

    # 6️⃣ Insert first round matches into database
    for p1, p2 in matches:
        cursor.execute(
            "INSERT INTO matches (tid, round_no, player1_id, player2_id, match_status) VALUES (%s, %s, %s, %s, 'pending')",
            (tid, round_no, p1, p2)
        )
    db.commit()

    flash(f"Single Elimination bracket generated for {n_players - byes} players with {byes} BYEs.", "success")



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


@app.route('/view_bracket/<int:tid>')
def view_bracket(tid):
    cursor.execute(
        "SELECT m.round_no, m.mid, u1.username AS player1, u2.username AS player2, m.winner_id "
        "FROM matches m "
        "LEFT JOIN users u1 ON m.player1_id = u1.id "
        "LEFT JOIN users u2 ON m.player2_id = u2.id "
        "WHERE m.tid=%s "
        "ORDER BY m.round_no, m.mid",
        (tid,)
    )
    matches = cursor.fetchall()

    # Group matches by round
    rounds = {}
    for match in matches:
        rounds.setdefault(match['round_no'], []).append(match)

    return render_template("view_bracket.html", rounds=rounds)








# ---------- DASHBOARDS ----------
@app.route('/player_dashboard')
def player_dashboard():
    if 'role' in session and session['role'] == 'player':
        return render_template("player_dashboard.html", username=session['username'])
    return redirect('/login')

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
