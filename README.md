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
- **User settings modal** — Gear icon in the header opens a settings panel for every user
  - **Change password** — Update your password with current-password verification
  - **Temperature unit** — Switch between °C and °F; all displayed values convert instantly
  - **Dashboard refresh rate** — Choose 2s / 5s / 10s / 30s polling interval
  - **Temperature alert** — Browser notifications when temperature exceeds a configurable threshold
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

PWM Fan         Raspberry Pi / Power
───────         ────────────────────
PWM  ────────── GPIO 18
GND  ────────── GND (shared with Pi)
+12V/+5V ───── External power supply (match your fan's voltage)
```

> **Note:** Most 4-pin PWM fans require 12V power. Do **not** power the fan from the Pi's GPIO pins — use an external supply and share a common ground with the Pi.

## Requirements

- **Raspberry Pi** running Raspberry Pi OS (Bookworm or later recommended)
- **Python 3.7+**
- I2C enabled (`sudo raspi-config` → Interface Options → I2C → Enable)

## Installation

```bash
# Clone the repo
git clone https://github.com/<your-username>/SparkFan.git
cd SparkFan

# Install dependencies
pip install -r requirements.txt

# Enable I2C on your Pi (if not already)
sudo raspi-config  # Interface Options → I2C → Enable

# Run
python app.py
```

Open `http://<pi-ip>:5000` in your browser. On first launch you'll be prompted to create an admin account.

> **Tip:** `RPi.GPIO` is pre-installed on Raspberry Pi OS. If you're on a minimal image and get an import error, `pip install RPi.GPIO` will fix it.

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

## Customization

### BME280 I2C Address

The default I2C address is `0x76`. If your sensor uses `0x77`, change this line in `app.py`:

```python
bme = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)  # ← change to 0x77
```

You can verify your sensor's address with `i2cdetect -y 1`.

### PWM GPIO Pin

The fan PWM signal defaults to **GPIO 18**. To use a different pin, update these lines in `app.py`:

```python
GPIO.setup(18, GPIO.OUT)    # ← change pin number
pwm = GPIO.PWM(18, 25000)   # ← change pin number
```

### Running on Boot (systemd)

To start SparkFan automatically on boot, create a systemd service:

```bash
sudo nano /etc/systemd/system/sparkfan.service
```

```ini
[Unit]
Description=SparkFan Fan Controller
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/SparkFan/app.py
WorkingDirectory=/home/pi/SparkFan
User=pi
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sparkfan
sudo systemctl start sparkfan
```

> **Note:** Adjust the paths above if you cloned the repo to a different location or use a different username.

## Project Structure

```
SparkFan/
├── app.py              # Flask server, sensor loop, API routes
├── requirements.txt    # Python dependencies
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
| `POST` | `/api/change-password` | Change current user's password |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'board'` | Install the Adafruit Blinka library: `pip install adafruit-blinka` |
| `ModuleNotFoundError: No module named 'RPi'` | Install RPi.GPIO: `pip install RPi.GPIO` |
| `TemplateNotFound` error | Make sure you're running `python app.py` from the SparkFan directory |
| BME280 not detected | Run `i2cdetect -y 1` to verify the sensor address; ensure I2C is enabled |
| Fan not spinning | Check that the fan has external power (12V/5V) and shares a ground with the Pi |
| Permission denied on GPIO | Run with `sudo` or add your user to the `gpio` group: `sudo usermod -aG gpio $USER` |

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE). You are free to use, modify, and distribute this software, but any derivative work must also be released under the GPL v3 with full source code.
