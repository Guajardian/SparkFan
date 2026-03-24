import os
import json
import time
import threading
from datetime import datetime
from collections import deque
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import bcrypt

# ─── Hardware imports ───
# Comment these out for testing without Pi hardware
import board
import adafruit_bme280.basic as adafruit_bme280
import RPi.GPIO as GPIO

# ─── Config file ───
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")

DEFAULT_CONFIG = {
    "temp_low": 25.0,
    "temp_high": 45.0,
    "min_duty": 20,
    "poll_interval": 5
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# ─── App setup ───
app = Flask(__name__)
app.secret_key = os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    users = load_users()
    if username in users:
        return User(username)
    return None

# ─── Hardware setup ───
i2c = board.I2C()
bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)

GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.OUT)
pwm = GPIO.PWM(18, 25000)
pwm.start(0)

# ─── State ───
config = load_config()
history = deque(maxlen=720)  # 1 hour at 5s intervals
current_data = {
    "temp": 0.0,
    "humidity": 0.0,
    "pressure": 0.0,
    "fan_speed": 0,
    "timestamp": ""
}
controller_running = True

def get_fan_speed(temp):
    if temp < config["temp_low"]:
        return 0
    elif temp >= config["temp_high"]:
        return 100
    else:
        ratio = (temp - config["temp_low"]) / (config["temp_high"] - config["temp_low"])
        speed = config["min_duty"] + ratio * (100 - config["min_duty"])
        return int(speed)

def controller_loop():
    global current_data
    while controller_running:
        try:
            temp = bme.temperature
            humidity = bme.humidity
            pressure = bme.pressure
            speed = get_fan_speed(temp)
            pwm.ChangeDutyCycle(speed)

            now = datetime.now()
            current_data = {
                "temp": round(temp, 1),
                "humidity": round(humidity, 1),
                "pressure": round(pressure, 1),
                "fan_speed": speed,
                "timestamp": now.strftime("%H:%M:%S")
            }
            history.append({
                "temp": round(temp, 1),
                "humidity": round(humidity, 1),
                "fan_speed": speed,
                "time": now.strftime("%H:%M:%S")
            })
        except Exception as e:
            print(f"Sensor read error: {e}")

        time.sleep(config["poll_interval"])

# ─── Routes ───
@app.route("/")
@login_required
def index():
    return render_template("dashboard.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    users = load_users()

    # First run — no users exist, show setup
    if not users:
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            if username and password:
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
                users[username] = hashed
                save_users(users)
                login_user(User(username))
                return redirect(url_for("index"))
        return render_template("setup.html")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username in users and bcrypt.checkpw(password.encode(), users[username].encode()):
            login_user(User(username))
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html", error=None)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/api/data")
@login_required
def api_data():
    return jsonify(current_data)

@app.route("/api/history")
@login_required
def api_history():
    return jsonify(list(history))

@app.route("/api/config", methods=["GET", "POST"])
@login_required
def api_config():
    global config
    if request.method == "POST":
        data = request.get_json()
        if "temp_low" in data:
            config["temp_low"] = float(data["temp_low"])
        if "temp_high" in data:
            config["temp_high"] = float(data["temp_high"])
        if "min_duty" in data:
            config["min_duty"] = int(data["min_duty"])
        if "poll_interval" in data:
            config["poll_interval"] = max(2, int(data["poll_interval"]))
        save_config(config)
        return jsonify({"status": "ok", "config": config})
    return jsonify(config)

# ─── Start ───
if __name__ == "__main__":
    # Create first user prompt
    users = load_users()
    if not users:
        print("No users configured — create one at the login page.")

    # Start sensor loop
    t = threading.Thread(target=controller_loop, daemon=True)
    t.start()
    print("Fan controller + dashboard started")
    print(f"Config: {config}")

    try:
        app.run(host="0.0.0.0", port=5000)
    finally:
        controller_running = False
        pwm.ChangeDutyCycle(0)
        pwm.stop()
        GPIO.cleanup()
