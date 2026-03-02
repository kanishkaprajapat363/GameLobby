from flask import render_template, session, redirect, flash
import mysql.connector
import datetime

def init_player_routes(app, db, cursor):

    @app.route('/player_dashboard')
    def player_dashboard():
        if 'role' in session and session['role'] == 'player':
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


    # ---------------- ACTIVE LOBBIES ----------------
    @app.route('/active_lobbies')
    def active_lobbies():
        if 'role' in session and session['role'] == 'player':

            cursor.execute("""
                SELECT l.lid, l.game_name, l.game_type, l.host_id,
                       l.current_players, l.max_players, l.status
                FROM game_lobbies l
                WHERE l.status IN ('waiting','in_progress')
                ORDER BY l.created_at ASC
            """)

            lobbies = cursor.fetchall()

            # If no lobbies exist → insert two default real lobbies into DB ONLY ONCE
            if not lobbies:
                default_lobbies = [
                    ("Valorant Deathmatch", "FPS", 10),
                    ("BGMI Arena TDM", "Battle Royale", 4)
                ]

                for game_name, game_type, max_players in default_lobbies:
                    cursor.execute("""
                        INSERT INTO game_lobbies (game_name, game_type, host_id, current_players, max_players, status)
                        VALUES (%s, %s, NULL, 0, %s, 'waiting')
                    """, (game_name, game_type, max_players))
                    db.commit()

                # Now fetch again
                cursor.execute("""
                    SELECT l.lid, l.game_name, l.game_type, l.host_id,
                           l.current_players, l.max_players, l.status
                    FROM game_lobbies l
                    WHERE l.status='waiting'
                    ORDER BY l.created_at ASC
                """)
                lobbies = cursor.fetchall()

            # No more is_demo flag
            for l in lobbies:
                l['is_demo'] = False


            # Real joined lobbies
            cursor.execute("""
                SELECT lid
                FROM lobby_players
                WHERE user_id=(SELECT id FROM users WHERE username=%s)
            """, (session['username'],))
            joined_lobbies = [r['lid'] for r in cursor.fetchall()]

            # Mark joined status
            for l in lobbies:
                l['joined'] = l['lid'] in joined_lobbies

            return render_template("active_lobbies.html",
                                   username=session['username'],
                                   lobbies=lobbies)

        return redirect('/login')


    # ---------------- JOIN LOBBY ----------------
    @app.route('/join_lobby/<int:lid>', methods=['POST'])
    def join_lobby(lid):

        if 'role' not in session or session['role'] != 'player':
            return redirect('/login')

        # Demo lobby click
        if lid < 0:
            flash("This is a demo lobby. Create a real lobby from Host Dashboard.", "info")
            return redirect('/active_lobbies')

        cursor.execute("SELECT id FROM users WHERE username=%s", (session['username'],))
        user_id = cursor.fetchone()['id']

        # Already joined
        cursor.execute("SELECT * FROM lobby_players WHERE lid=%s AND user_id=%s", (lid, user_id))
        if cursor.fetchone():
            return redirect(f'/lobby/{lid}')

        # Fetch lobby info
        cursor.execute("""
            SELECT current_players, max_players, status
            FROM game_lobbies WHERE lid=%s
        """, (lid,))
        lobby = cursor.fetchone()

        if not lobby:
            flash("Lobby not found.", "error")
            return redirect('/active_lobbies')

        # Check lobby capacity
        if lobby['current_players'] >= lobby['max_players'] or lobby['status'] != 'waiting':
            flash("Lobby full or already started.", "error")
            return redirect('/active_lobbies')

        # Add player
        cursor.execute("INSERT INTO lobby_players (lid, user_id) VALUES (%s,%s)", (lid, user_id))
        cursor.execute("UPDATE game_lobbies SET current_players=current_players+1 WHERE lid=%s", (lid,))
        db.commit()

        return redirect(f'/lobby/{lid}')


    # ---------------- LOBBY ROOM ----------------
    @app.route('/lobby/<int:lid>')
    def lobby_room(lid):
        if 'role' not in session or session['role'] != 'player':
            return redirect('/login')

        # Fetch lobby details
        cursor.execute("SELECT * FROM game_lobbies WHERE lid=%s", (lid,))
        lobby = cursor.fetchone()

        if not lobby:
            return "Lobby not found", 404

        # Fetch players currently in lobby
        cursor.execute("""
            SELECT u.username 
            FROM lobby_players lp
            JOIN users u ON lp.user_id = u.id
            WHERE lp.lid=%s
        """, (lid,))
        players = cursor.fetchall()

        return render_template(
            "lobby_room.html",
            lobby=lobby,
            players=players)

    @app.route('/tictactoe/<int:lid>')
    def tictactoe_game(lid):
        if 'role' not in session or session['role'] != 'player':
            return redirect('/login')

        cursor.execute("SELECT * FROM game_lobbies WHERE lid=%s", (lid,))
        lobby = cursor.fetchone()

        if not lobby or lobby['game_name'] != 'Tic Tac Toe':
            return "Invalid game", 404

        # 🔥 MARK GAME AS STARTED
        if lobby['status'] != 'in_progress':
            cursor.execute(
                "UPDATE game_lobbies SET status='in_progress' WHERE lid=%s",
                (lid,)
            )
            db.commit()

        return render_template(
            "tictactoe.html",
            lid=lid,
            username=session['username']
        )




