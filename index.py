from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello from Vercel!"

@app.route('/api/python')
def hello_world():
    return "Hello, World!"