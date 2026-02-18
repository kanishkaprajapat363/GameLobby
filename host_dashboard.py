from flask import (
    render_template,
    redirect,
    session,
    request,
    url_for,
    flash
)
import mysql.connector
import random
import math


def init_host_routes(app, db, cursor):

    # ======================================================
    # HELPER FUNCTIONS
    # ======================================================

    def get_current_user_id(username):
        cursor.execute(
            "SELECT id FROM users WHERE username=%s",
            (username,)
        )
        user = cursor.fetchone()
        return user['id'] if user else None

    def get_participant_count(tid):
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM participants WHERE tid=%s",
            (tid,)
        )
        result = cursor.fetchone()
        return result['cnt'] if result else 0

    def generate_single_elimination_bracket(tid):
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM matches WHERE tid=%s",
            (tid,)
        )
        if cursor.fetchone()["cnt"] > 0:
            flash("Bracket already generated for this tournament.", "error")
            return

        cursor.execute(
            "SELECT user_id FROM participants WHERE tid=%s",
            (tid,)
        )
        participants = [p["user_id"] for p in cursor.fetchall()]
        if not participants:
            flash("No participants selected! Cannot generate bracket.", "error")
            return

        random.shuffle(participants)
        n = len(participants)

        round_no = 1
        i = 0
        while i < n:
            p1 = participants[i]
            i += 1
            p2 = participants[i] if i < n else None
            i += 1 if p2 is not None else 0

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

    def generate_double_elimination_bracket(tid):
        cursor.execute(
            "SELECT user_id FROM participants WHERE tid=%s",
            (tid,)
        )
        players = [p['user_id'] for p in cursor.fetchall()]

        if len(players) < 2:
            flash("Not enough players", "error")
            return

        random.shuffle(players)

        round_no = 1
        for i in range(0, len(players), 2):
            p1 = players[i]
            p2 = players[i+1] if i+1 < len(players) else None

            if p2:
                cursor.execute("""
                    INSERT INTO matches
                    (tid, round_no, player1_id, player2_id, match_status)
                    VALUES (%s,%s,%s,%s,'pending')
                """, (tid, round_no, p1, p2))
            else:
                cursor.execute("""
                    INSERT INTO matches
                    (tid, round_no, player1_id, winner_id, match_status)
                    VALUES (%s,%s,%s,%s,'completed')
                """, (tid, round_no, p1, p1))

        db.commit()
        flash("Double Elimination (Round 1) generated", "success")


    # ======================================================
    # HOST DASHBOARD
    # ======================================================

    @app.route('/host_dashboard')
    def host_dashboard():
        if 'role' in session and session['role'] == 'host':
            cursor.execute(
                "SELECT * FROM tournaments WHERE host_id="
                "(SELECT id FROM users WHERE username=%s)",
                (session['username'],)
            )
            tournaments = cursor.fetchall()

            for t in tournaments:
                t['participant_count'] = get_participant_count(t['tid'])

            return render_template(
                "host_dashboard.html",
                username=session['username'],
                tournaments=tournaments
            )
        return redirect('/login')

    # ======================================================
    # CREATE TOURNAMENT
    # ======================================================

    @app.route('/create_tournament', methods=['GET', 'POST'])
    def create_tournament():
        if 'role' in session and session['role'] == 'host':
            if request.method == 'POST':
                tname = request.form['tname']
                game_type = request.form['game_type']
                game_format = request.form['format_type']
                t_date = request.form['t_date']
                host_id = get_current_user_id(session['username'])

                cursor.execute(
                    "INSERT INTO tournaments (tname, game_type, game_format, host_id, t_date) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (tname, game_type, game_format, host_id, t_date)
                )
                db.commit()
                return redirect('/host_dashboard')

            return render_template('create_tournament.html')
        return redirect('/login')

    # ======================================================
    # PARTICIPANTS
    # ======================================================

    @app.route('/add_participants/<int:tid>', methods=['GET', 'POST'])
    def add_participants(tid):
        if 'role' in session and session['role'] == 'host':
            cursor.execute("SELECT * FROM tournaments WHERE tid=%s", (tid,))
            tournament = cursor.fetchone()

            cursor.execute("SELECT id, username FROM users WHERE role='player'")
            players = cursor.fetchall()

            if request.method == 'POST':
                selected_users = request.form.getlist('players')
                for user_id in selected_users:
                    try:
                        cursor.execute(
                            "INSERT INTO participants (tid, user_id) VALUES (%s, %s)",
                            (tid, user_id)
                        )
                    except mysql.connector.IntegrityError:
                        continue

                db.commit()
                flash("Participants added successfully!", "success")
                return redirect('/host_dashboard')

            return render_template(
                'add_participants.html',
                tournament=tournament,
                players=players
            )
        return redirect('/login')

    @app.route('/remove_participants/<int:tid>', methods=['GET', 'POST'])
    def remove_participants(tid):
        if 'role' in session and session['role'] == 'host':
            cursor.execute("SELECT * FROM tournaments WHERE tid=%s", (tid,))
            tournament = cursor.fetchone()

            cursor.execute(
                "SELECT u.id, u.username FROM participants p "
                "JOIN users u ON p.user_id = u.id "
                "WHERE p.tid=%s",
                (tid,)
            )
            participants = cursor.fetchall()

            if request.method == 'POST':
                selected_users = request.form.getlist('participants')
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
            cursor.execute("DELETE FROM participants WHERE tid=%s", (tid,))
            cursor.execute("DELETE FROM matches WHERE tid=%s", (tid,))
            db.commit()
            flash("All participants and associated matches removed successfully!", "success")
            return redirect('/host_dashboard')
        return redirect('/login')

    # ======================================================
    # BRACKETS & MATCH FLOW
    # ======================================================

    @app.route('/generate_bracket/<int:tid>')
    def generate_bracket(tid):
        if session.get('role') != 'host':
            return redirect('/login')

        cursor.execute(
            "SELECT game_format FROM tournaments WHERE tid=%s",
            (tid,)
        )
        game_format = cursor.fetchone()['game_format']

        if game_format == 'single_elimination':
            generate_single_elimination_bracket(tid)

        elif game_format == 'double_elimination':
            generate_double_elimination_bracket(tid)   # stub for now

        elif game_format == 'swiss':
            generate_swiss_round_1(tid)                 # stub for now

        else:
            flash("Unknown format", "error")

        return redirect('/host_dashboard')


    @app.route('/view_bracket/<int:tid>')
    def view_bracket(tid):
        cursor.execute("SELECT * FROM tournaments WHERE tid=%s", (tid,))
        tournament = cursor.fetchone()
        if not tournament:
            return "Tournament not found", 404

        cursor.execute("""
            SELECT 
                m.mid, m.tid, m.round_no, m.player1_id, m.player2_id,
                m.winner_id, m.match_status,
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

        rounds = {}
        for r in rows:
            entry = {
                "mid": r["mid"],
                "player1": r["p1_name"],
                "player2": r["p2_name"],
                "player1_id": r["player1_id"],
                "player2_id": r["player2_id"],
                "winner": r["winner_name"],
                "winner_id": r["winner_id"],
                "match_status": r["match_status"]
            }
            rounds.setdefault(r["round_no"], []).append(entry)

        return render_template(
            "view_bracket.html",
            tournament=tournament,
            rounds=rounds
        )

    @app.route('/set_winner/<int:mid>', methods=['POST'])
    def set_winner(mid):
        if 'role' not in session or session['role'] != 'host':
            return redirect('/login')

        winner_id = request.form.get('winner_id')
        if winner_id:
            cursor.execute(
                "UPDATE matches SET winner_id=%s, match_status='completed' WHERE mid=%s",
                (winner_id, mid)
            )
            db.commit()
        return redirect(request.referrer)

    @app.route('/advance_round/<int:tid>', methods=['POST'])
    def advance_round(tid):
        if 'role' not in session or session['role'] != 'host':
            return redirect('/login')

        cursor.execute(
            "SELECT COALESCE(MAX(round_no), 0) AS max_round FROM matches WHERE tid=%s",
            (tid,)
        )
        current_round = cursor.fetchone()["max_round"]

        cursor.execute("""
            SELECT winner_id
            FROM matches
            WHERE tid=%s AND round_no=%s
            ORDER BY mid
        """, (tid, current_round))
        winners = [row["winner_id"] for row in cursor.fetchall() if row["winner_id"] is not None]

        if len(winners) <= 1:
            if winners:
                cursor.execute(
                    "UPDATE tournaments SET status='completed' WHERE tid=%s",
                    (tid,)
                )
                db.commit()
                flash("Tournament completed! Winner determined.", "success")
            else:
                flash("No winners to advance.", "error")
            return redirect(url_for('view_bracket', tid=tid))

        next_round = current_round + 1
        for i in range(0, len(winners), 2):
            p1 = winners[i]
            p2 = winners[i + 1] if i + 1 < len(winners) else None

            if p2 is None:
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
