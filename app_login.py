from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)

# 세션 암호화 키 (아무 문자나 넣으면 돼요)
app.secret_key = 'aiquant2024'

# MySQL 연결 설정
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'angelina11!!'  # ← 본인 비밀번호
app.config['MYSQL_DB'] = 'aiquant'
app.config['MYSQL_PORT'] = 3307  # ← 본인이 설정한 포트번호

mysql = MySQL(app)

# 로그인 페이지
@app.route('/')
def index():
    return render_template('index_login.html')

# 로그인 처리
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
    user = cursor.fetchone()

    if user:
        session['username'] = user['username']
        return redirect(url_for('main'))
    else:
        return render_template('index_login.html', error='아이디 또는 비밀번호가 일치하지 않습니다.')

# 회원가입 페이지
@app.route('/signup')
def signup():
    return render_template('signup.html')

# 회원가입 처리
@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
    existing_user = cursor.fetchone()

    if existing_user:
        return render_template('signup_login.html', error='이미 존재하는 아이디예요!')

    cursor.execute('INSERT INTO users VALUES (NULL, %s, %s, %s)', (username, email, password))
    mysql.connection.commit()

    return redirect(url_for('index'))

# 메인 페이지
@app.route('/main')
def main():
    if 'username' not in session:
        return redirect(url_for('index'))
    return render_template('main_login.html')

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)