# SparkFan

A Raspberry Pi-powered smart fan controller with a live web dashboard. SparkFan reads temperature, humidity, and pressure from a BME280 sensor and automatically adjusts PWM fan speed using a configurable fan curve — all managed through a clean, dark-themed web UI.

## Features

- **Automatic fan control** — PWM fan speed scales linearly between configurable low/high temperature thresholds
- **Fan profiles** — Switch between Silent, Default, and Performance presets with one click
- **Manual override** — Lock the fan to any speed, bypassing the automatic curve
- **Humidity trigger** — Optionally ramp fans when humidity exceeds a configurable threshold
- **Live dashboard** — Real-time temperature, humidity, pressure, and fan speed readings
- **12-hour history chart** — Visualizes temperature and fan speed trends (Chart.js)
- **System stats** — CPU temperature, uptime, and memory usage at a glance
- **Dark / Light theme** — Toggle between themes; preference saved in browser
- **Configurable fan curve** — Set low/high temp thresholds, minimum duty cycle, and sensor poll interval from the UI
- **User authentication** — Secure login with bcrypt-hashed passwords
- **User management** — Add and remove users from the admin panel
- **First-run setup** — Guided admin account creation on first launch

## Hardware

| Component | Details |
|-----------|---------|
| **Board** | Raspberry Pi (any model with GPIO + I2C) |
| **Sensor** | BME280 (I2C, address `0x76`) |
| **Fan** | 4-pin PWM fan on GPIO 18 (25 kHz) |

### Wiring

```
BME280          Raspberry Pi
───────         ────────────
VIN  ────────── 3.3V
GND  ────────── GND
SCL  ────────── GPIO 3 (SCL)
SDA  ────────── GPIO 2 (SDA)

PWM Fan         Raspberry Pi
───────         ────────────
PWM  ────────── GPIO 18
```

## Installation

```bash
# Clone the repo
git clone https://github.com/<your-username>/SparkFan.git
cd SparkFan

# Install dependencies
pip install flask flask-login bcrypt adafruit-circuitpython-bme280

# Enable I2C on your Pi (if not already)
sudo raspi-config  # Interface Options → I2C → Enable

# Run
python app.py
```

Open `http://<pi-ip>:5000` in your browser. On first launch you'll be prompted to create an admin account.

## Configuration

Fan curve settings are stored in `config.json` and can be changed from the dashboard:

| Setting | Default | Description |
|---------|---------|-------------|
| `temp_low` | 25.0 °C | Fans off below this temperature |
| `temp_high` | 45.0 °C | 100% fan speed at this temperature |
| `min_duty` | 20% | Minimum duty cycle when fans are active |
| `poll_interval` | 5s | Sensor polling frequency |
| `humidity_trigger` | off | Enable humidity-based fan activation |
| `humidity_high` | 70% | Humidity threshold for fan trigger |
| `active_profile` | default | Currently active fan profile |

## Project Structure

```
SparkFan/
├── app.py              # Flask server, sensor loop, API routes
├── config.json         # Fan curve & poll settings (auto-generated)
├── users.json          # User credentials (auto-generated)
├── dashboard.html      # Main dashboard template
├── login.html          # Login page template
├── setup.html          # First-run setup template
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/data` | Current sensor readings + fan speed + override state |
| `GET` | `/api/history` | Last 12 hours of readings |
| `GET/POST` | `/api/config` | Get or update fan curve & humidity settings |
| `GET/POST` | `/api/override` | Get or set manual override (speed + enabled) |
| `POST` | `/api/profiles/<name>` | Apply a fan profile (silent, default, performance) |
| `GET` | `/api/system` | Pi system stats (CPU temp, uptime, memory) |
| `GET` | `/api/users` | List all usernames |
| `POST` | `/api/users` | Add a new user |
| `DELETE` | `/api/users/<username>` | Delete a user |

## License

MIT
