from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3, os, datetime
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = "unik_secret_key"
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
socketio = SocketIO(app)

# --- Создание базы данных при первом запуске ---
if not os.path.exists('users.db'):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        about TEXT,
        avatar TEXT
    )''')
    c.execute('''CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_name TEXT,
        sender TEXT,
        content TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()


# --- Главная страница (регистрация/вход) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user' in session:
        return redirect(url_for('chats'))

    message = ''
    if request.method == 'POST':
        action = request.form.get('action')

        conn = sqlite3.connect('users.db')
        c = conn.cursor()

        if action == 'register':
            name = request.form['name']
            email = request.form['email']
            password = generate_password_hash(request.form['password'])
            try:
                c.execute("INSERT INTO users (name, email, password, about, avatar) VALUES (?, ?, ?, ?, ?)",
                          (name, email, password, '', 'default.png'))
                conn.commit()
                message = 'Регистрация успешна!'
            except sqlite3.IntegrityError:
                message = 'Такой email уже зарегистрирован.'
        elif action == 'login':
            email = request.form['email']
            password = request.form['password']
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            user = c.fetchone()
            if user and check_password_hash(user[3], password):
                session['user'] = {'id': user[0], 'name': user[1], 'email': user[2], 'avatar': user[5]}
                return redirect(url_for('chats'))
            else:
                message = 'Неверный email или пароль.'
        conn.close()

    return render_template('index.html', message=message)


# --- Список чатов ---
@app.route('/chats')
def chats():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('chats.html', user=session['user'])


# --- Открытие конкретного чата ---
@app.route('/chat/<chat_name>')
def chat_room(chat_name):
    if 'user' not in session:
        return redirect(url_for('index'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT sender, content, timestamp FROM messages WHERE chat_name=? ORDER BY id ASC", (chat_name,))
    messages = c.fetchall()
    conn.close()
    return render_template('chat_room.html', chat_name=chat_name, user=session['user'], messages=messages)


# --- Отправка сообщений ---
@socketio.on('send_message')
def handle_message(data):
    chat_name = data['chat']
    sender = data['sender']
    content = data['message']
    timestamp = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (chat_name, sender, content, timestamp) VALUES (?, ?, ?, ?)",
              (chat_name, sender, content, timestamp))
    conn.commit()
    conn.close()
    emit('receive_message', {'sender': sender, 'message': content, 'timestamp': timestamp}, broadcast=True)


# --- Профиль пользователя ---
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (session['user']['id'],))
    user = c.fetchone()

    if request.method == 'POST':
        about = request.form['about']
        avatar = user[5]
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file.filename != '':
                filename = secure_filename(file.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                avatar = filename
        c.execute("UPDATE users SET about=?, avatar=? WHERE id=?", (about, avatar, session['user']['id']))
        conn.commit()
        session['user']['avatar'] = avatar
    conn.close()
    return render_template('profile.html', user=user)


# --- Выход ---
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=10000, debug=True)
