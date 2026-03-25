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
    "poll_interval": 5,
    "humidity_trigger": False,
    "humidity_high": 70.0,
    "active_profile": "default",
    "profiles": {
        "silent": {"temp_low": 30.0, "temp_high": 50.0, "min_duty": 15},
        "default": {"temp_low": 25.0, "temp_high": 45.0, "min_duty": 20},
        "performance": {"temp_low": 20.0, "temp_high": 40.0, "min_duty": 30}
    }
}

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if k == "profiles" and isinstance(v, dict):
                for pk, pv in v.items():
                    cfg["profiles"][pk] = pv
            else:
                cfg[k] = v
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        # Migrate flat format {"user": "hash"} → {"user": {"password": "hash", "role": "admin"}}
        migrated = False
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = {"password": v, "role": "admin"}
                migrated = True
        if migrated:
            save_users(data)
        return data
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
    def __init__(self, username, role="user"):
        self.id = username
        self.role = role

    @property
    def is_admin(self):
        return self.role == "admin"

@login_manager.user_loader
def load_user(username):
    users = load_users()
    if username in users:
        role = users[username].get("role", "user") if isinstance(users[username], dict) else "user"
        return User(username, role)
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
history = deque(maxlen=8640)  # 12 hours at 5s intervals
override = {"enabled": False, "speed": 50}
current_data = {
    "temp": 0.0,
    "humidity": 0.0,
    "pressure": 0.0,
    "fan_speed": 0,
    "timestamp": ""
}
controller_running = True

def get_fan_speed(temp, humidity):
    if override["enabled"]:
        return override["speed"]
    humidity_boost = (config.get("humidity_trigger") and
                      humidity >= config.get("humidity_high", 70))
    if temp < config["temp_low"]:
        return config["min_duty"] if humidity_boost else 0
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
            speed = get_fan_speed(temp, humidity)
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
                users[username] = {"password": hashed, "role": "admin"}
                save_users(users)
                login_user(User(username, "admin"))
                return redirect(url_for("index"))
        return render_template("setup.html")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username in users:
            pw_hash = users[username]["password"] if isinstance(users[username], dict) else users[username]
            if bcrypt.checkpw(password.encode(), pw_hash.encode()):
                role = users[username].get("role", "user") if isinstance(users[username], dict) else "user"
                login_user(User(username, role))
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
    data = dict(current_data)
    data["override"] = override["enabled"]
    data["override_speed"] = override["speed"]
    return jsonify(data)

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
        if "humidity_trigger" in data:
            config["humidity_trigger"] = bool(data["humidity_trigger"])
        if "humidity_high" in data:
            config["humidity_high"] = float(data["humidity_high"])
        save_config(config)
        return jsonify({"status": "ok", "config": config})
    return jsonify(config)

# ─── User management (admin only) ───
@app.route("/api/me")
@login_required
def api_me():
    return jsonify({"username": current_user.id, "role": current_user.role})

@app.route("/api/users", methods=["GET"])
@login_required
def api_users_list():
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    users = load_users()
    return jsonify([{"username": u, "role": d.get("role", "user") if isinstance(d, dict) else "user"}
                     for u, d in users.items()])

@app.route("/api/users", methods=["POST"])
@login_required
def api_users_add():
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user").strip()
    if role not in ("admin", "user"):
        role = "user"
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    users = load_users()
    if username in users:
        return jsonify({"error": "User already exists"}), 409
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed, "role": role}
    save_users(users)
    return jsonify({"status": "ok", "username": username, "role": role}), 201

@app.route("/api/users/<username>", methods=["DELETE"])
@login_required
def api_users_delete(username):
    if not current_user.is_admin:
        return jsonify({"error": "Admin access required"}), 403
    users = load_users()
    if username not in users:
        return jsonify({"error": "User not found"}), 404
    if username == current_user.id:
        return jsonify({"error": "Cannot delete yourself"}), 400
    if len(users) <= 1:
        return jsonify({"error": "Cannot delete the last user"}), 400
    del users[username]
    save_users(users)
    return jsonify({"status": "ok"})

# ─── System & Override & Profiles ───
@app.route("/api/system")
@login_required
def api_system():
    stats = {}
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            stats["cpu_temp"] = round(int(f.read().strip()) / 1000, 1)
    except Exception:
        stats["cpu_temp"] = 0.0
    try:
        with open("/proc/uptime", "r") as f:
            secs = int(float(f.read().split()[0]))
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)
        stats["uptime"] = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m"
    except Exception:
        stats["uptime"] = "N/A"
    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split()
            if parts[0] in ("MemTotal:", "MemAvailable:"):
                mem[parts[0]] = int(parts[1])
        total = mem.get("MemTotal:", 0)
        avail = mem.get("MemAvailable:", 0)
        stats["mem_total"] = round(total / 1024)
        stats["mem_used"] = round((total - avail) / 1024)
    except Exception:
        stats["mem_total"] = 0
        stats["mem_used"] = 0
    return jsonify(stats)

@app.route("/api/override", methods=["GET", "POST"])
@login_required
def api_override():
    if request.method == "POST":
        data = request.get_json()
        if "enabled" in data:
            override["enabled"] = bool(data["enabled"])
        if "speed" in data:
            override["speed"] = max(0, min(100, int(data["speed"])))
        if override["enabled"]:
            pwm.ChangeDutyCycle(override["speed"])
        return jsonify({"status": "ok", "override": override})
    return jsonify(override)

@app.route("/api/profiles/<name>", methods=["POST"])
@login_required
def api_profile_apply(name):
    profiles = config.get("profiles", {})
    if name not in profiles:
        return jsonify({"error": "Profile not found"}), 404
    p = profiles[name]
    config["temp_low"] = p["temp_low"]
    config["temp_high"] = p["temp_high"]
    config["min_duty"] = p["min_duty"]
    config["active_profile"] = name
    override["enabled"] = False
    save_config(config)
    return jsonify({"status": "ok", "config": config})

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
