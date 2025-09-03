from flask import render_template, session, redirect, flash
import mysql.connector
import datetime

# You can pass the database connection and cursor from app.py
def init_player_routes(app, db, cursor):

    @app.route('/player_dashboard')
    def player_dashboard():
        if 'role' in session and session['role'] == 'player':
            # Example: Fetch tournaments the player is participating in
            cursor.execute("""
                SELECT t.tid, t.tname, t.game_type, t.game_format, t.t_date
                FROM tournaments t
                JOIN participants p ON t.tid = p.tid
                JOIN users u ON p.user_id = u.id
                WHERE u.username = %s
            """, (session['username'],))
            tournaments = cursor.fetchall()
            return render_template("player_dashboard.html",
                                   username=session['username'],
                                   tournaments=tournaments)
        return redirect('/login')
    
    # You can define more player-related routes here

    @app.route('/upcoming_tournaments')
    def upcoming_tournaments():
        if 'role' in session and session['role'] == 'player':
            today = datetime.date.today()

            # Fetch only tournaments with date today or in the future
            cursor.execute("""
                SELECT t.tid, t.tname, t.game_type, t.game_format, t.t_date
                FROM tournaments t
                WHERE t.t_date >= %s
                ORDER BY t.t_date ASC
            """, (today,))
            tournaments = cursor.fetchall()

            # Check if player is already registered
            for t in tournaments:
                cursor.execute("""
                    SELECT COUNT(*) AS cnt
                    FROM participants
                    WHERE tid=%s AND user_id=(SELECT id FROM users WHERE username=%s)
                """, (t['tid'], session['username']))
                t['registered'] = cursor.fetchone()['cnt'] > 0

            return render_template("upcoming_tournaments.html",
                                   username=session['username'],
                                   tournaments=tournaments)
        return redirect('/login')

    @app.route('/my_matches')
    def my_matches():
        if 'role' in session and session['role'] == 'player':
            # Get current player's ID
            cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
            user_id = cursor.fetchone()['id']

            # Fetch all matches where player is either player1 or player2
            cursor.execute("""
                SELECT m.mid, m.tid, m.round_no, m.player1_id, m.player2_id, m.winner_id, m.match_status,
                       t.tname
                FROM matches m
                JOIN tournaments t ON m.tid = t.tid
                WHERE m.player1_id=%s OR m.player2_id=%s
                ORDER BY t.t_date ASC, m.round_no ASC
            """, (user_id, user_id))

            matches = cursor.fetchall()

            # Get opponent usernames and winner names
            for m in matches:
                # Opponent
                opponent_id = m['player2_id'] if m['player1_id'] == user_id else m['player1_id']
                if opponent_id:
                    cursor.execute("SELECT username FROM users WHERE id=%s", (opponent_id,))
                    m['opponent'] = cursor.fetchone()['username']
                else:
                    m['opponent'] = 'BYE'

                # Winner
                if m['winner_id']:
                    cursor.execute("SELECT username FROM users WHERE id=%s", (m['winner_id'],))
                    m['winner_name'] = cursor.fetchone()['username']
                else:
                    m['winner_name'] = None

            return render_template('my_matches.html', username=session['username'], matches=matches)
        return redirect('/login')

    @app.route('/player_profile', methods=['GET'])
    def player_profile():
        if 'role' in session and session['role'] == 'player':
            # Fetch player details (id, username, email)
            cursor.execute("""
                SELECT id, username, email, role
                FROM users
                WHERE username=%s
            """, (session['username'],))
            player = cursor.fetchone()

            if not player:
                flash("Player not found.", "error")
                return redirect('/player_dashboard')

            return render_template('player_profile.html',
                                   username=session['username'],
                                   player=player)
        return redirect('/login')

    @app.route('/active_lobbies')
    def active_lobbies():
        if 'role' in session and session['role'] == 'player':
            # Fetch all lobbies which are open or in progress
            cursor.execute("""
                SELECT l.lid, l.game_name, l.game_type, l.host_id, l.current_players, l.max_players
                FROM game_lobbies l
                WHERE l.status IN ('waiting','in_progress')
                ORDER BY l.created_at ASC
            """)
            lobbies = cursor.fetchall()

            # Optionally: show if current player has already joined each lobby
            cursor.execute("SELECT lid FROM lobby_players WHERE user_id=(SELECT id FROM users WHERE username=%s)", (session['username'],))
            joined_lobbies = [row['lid'] for row in cursor.fetchall()]

            for l in lobbies:
                l['joined'] = l['lid'] in joined_lobbies

            return render_template("active_lobbies.html", username=session['username'], lobbies=lobbies)
        return redirect('/login')

    @app.route('/join_lobby/<int:lid>', methods=['POST'])
    def join_lobby(lid):
        if 'role' in session and session['role'] == 'player':
            cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
            user_id = cursor.fetchone()['id']

            # Check if already joined
            cursor.execute("SELECT * FROM lobby_players WHERE lid=%s AND user_id=%s", (lid, user_id))
            if cursor.fetchone():
                flash("Already joined!", "error")
            else:
                # Increment current_players only if lobby has space
                cursor.execute("SELECT current_players, max_players, status FROM game_lobbies WHERE lid=%s", (lid,))
                lobby = cursor.fetchone()
                if lobby['current_players'] < lobby['max_players'] and lobby['status'] == 'waiting':
                    cursor.execute("INSERT INTO lobby_players (lid, user_id) VALUES (%s,%s)", (lid, user_id))
                    cursor.execute("UPDATE game_lobbies SET current_players=current_players+1 WHERE lid=%s", (lid,))
                    db.commit()
                    flash("Joined lobby successfully!", "success")
                else:
                    flash("Lobby is full or already started!", "error")
            return redirect('/active_lobbies')
        return redirect('/login')





