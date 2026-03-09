import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests
from routes.rank import rank_bp
from routes.news import news_bp

app = Flask(__name__)

app.register_blueprint(rank_bp)
app.register_blueprint(news_bp)

@app.route("/")
def index():
    return render_template("index.html" )

if __name__ == "__main__":
    app.run(debug=True)