from flask import Flask, render_template, request, redirect, session
from flask_bcrypt import Bcrypt
import mysql.connector

from player_dashboard import init_player_routes
from admin_dashboard import init_admin_routes
from host_dashboard import init_host_routes   # ✅ NEW


app = Flask(__name__)
app.secret_key = "secretkey"
bcrypt = Bcrypt(app)

# ---------- DATABASE CONNECTION ----------
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
        password = bcrypt.generate_password_hash(
            request.form['password']
        ).decode('utf-8')
        role = request.form['role']

        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s,%s,%s,%s)",
            (username, email, password, role)
        )
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

        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND role=%s",
            (username, role)
        )
        user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']

            if role == 'player':
                return redirect('/player_dashboard')
            elif role == 'host':
                return redirect('/host_dashboard')
            elif role == 'admin':
                return redirect('/admin_dashboard')

        return "Invalid Credentials"

    return render_template('login.html')

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------- DASHBOARD ROUTES REGISTRATION ----------
init_player_routes(app, db, cursor)
init_host_routes(app, db, cursor)     # ✅ host routes now live here
init_admin_routes(app, db, cursor)


if __name__ == '__main__':
    app.run(debug=True)
