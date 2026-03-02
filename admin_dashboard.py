from flask import render_template, session, redirect

def init_admin_routes(app, db, cursor):

    # ---------------- DASHBOARD ----------------
    @app.route('/admin_dashboard')
    def admin_dashboard():
        if session.get('role') != 'admin':
            return redirect('/login')

        cursor.execute("SELECT COUNT(*) AS c FROM users")
        total_users = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM tournaments")
        total_tournaments = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM matches")
        total_matches = cursor.fetchone()['c']

        return render_template(
            "admin_dashboard.html",
            username=session['username'],
            total_users=total_users,
            total_tournaments=total_tournaments,
            total_matches=total_matches
        )

    # ---------------- USERS ----------------
    @app.route('/admin/users')
    def admin_users():
        if session.get('role') != 'admin':
            return redirect('/login')

        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role='player'")
        players = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role='host'")
        hosts = cursor.fetchone()['c']

        return render_template(
            "admin_users.html",
            players=players,
            hosts=hosts
        )

    # ---------------- TOURNAMENTS ----------------
    @app.route('/admin/tournaments')
    def admin_tournaments():
        if session.get('role') != 'admin':
            return redirect('/login')

        cursor.execute("SELECT COUNT(*) AS c FROM tournaments")
        total_tournaments = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM tournaments WHERE status='active'")
        active_tournaments = cursor.fetchone()['c']

        cursor.execute("SELECT COUNT(*) AS c FROM tournaments WHERE status='completed'")
        completed_tournaments = cursor.fetchone()['c']

        return render_template(
            "admin_tournaments.html",
            total_tournaments=total_tournaments,
            active_tournaments=active_tournaments,
            completed_tournaments=completed_tournaments
        )


    # ---------------- MATCHES ----------------
    @app.route('/admin/matches')
    def admin_matches():
        if session.get('role') != 'admin':
            return redirect('/login')

        # Total matches
        cursor.execute("SELECT COUNT(*) AS total FROM matches")
        total_matches = cursor.fetchone()['total']

        # Ongoing matches
        cursor.execute("""
            SELECT COUNT(*) AS ongoing
            FROM matches
            WHERE match_status = 'ongoing'
        """)
        ongoing_matches = cursor.fetchone()['ongoing']

        # Completed matches
        cursor.execute("""
            SELECT COUNT(*) AS completed
            FROM matches
            WHERE match_status = 'completed'
        """)
        completed_matches = cursor.fetchone()['completed']

        return render_template(
            'admin_matches.html',
            total_matches=total_matches,
            ongoing_matches=ongoing_matches,
            completed_matches=completed_matches
        )





    # ---------------- SYSTEM ----------------
    @app.route('/admin/system')
    def admin_system():
        if session.get('role') != 'admin':
            return redirect('/login')

        return render_template("admin_system.html")
