from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv('SECRET_KEY')

app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))

mysql = MySQL(app)

# 로그인 페이지
@app.route('/')
def index():
    return render_template('index_login.html')

# 로그인 처리
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE email = %s AND password_hash = %s', (email, password))
    user = cursor.fetchone()

    if user:
        session['nickname'] = user['nickname']
        return redirect(url_for('main'))
    else:
        return render_template('index_login.html', error='이메일 또는 비밀번호가 일치하지 않습니다.')

# 회원가입 페이지
@app.route('/signup')
def signup():
    return render_template('signup_login.html')

# 회원가입 처리
@app.route('/register', methods=['POST'])
def register():
    email = request.form['email']
    password = request.form['password']
    nickname = request.form['nickname']

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 이메일 중복 확인
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    existing_email = cursor.fetchone()
    if existing_email:
        return render_template('signup_login.html', error='이미 사용 중인 이메일이에요!')

    # 닉네임 중복 확인
    cursor.execute('SELECT * FROM users WHERE nickname = %s', (nickname,))
    existing_nickname = cursor.fetchone()
    if existing_nickname:
        return render_template('signup_login.html', error='이미 사용 중인 닉네임이에요!')

    cursor.execute('INSERT INTO users (email, password_hash, nickname) VALUES (%s, %s, %s)', (email, password, nickname))
    mysql.connection.commit()

    return redirect(url_for('index'))

# 메인 페이지
@app.route('/main')
def main():
    if 'nickname' not in session:
        return redirect(url_for('index'))
    return render_template('main_login.html')

# 로그아웃
@app.route('/logout')
def logout():
    session.pop('nickname', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)