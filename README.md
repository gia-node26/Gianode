# 🌿 Gia-Node

**Gianode** is a modular, open-source AI-based plant care system.

It is made of two connected components:

- 🧠 **Gia** – the AI engine (image classification + GPT-based guidance)
- 🌱 **Node** – the hardware unit (camera + sensors for moisture, temp, etc.)

Together, they monitor plant health, analyze conditions, and provide context-aware care suggestions or actions — all with low-cost components and custom AI logic.

---

## 🧰 Features

- 📷 ESP32-CAM image capture
- 🌱 Soil moisture, temp, and pH sensors
- 🧠 Image classification (droopy, yellowing, healthy)
- 🧬 GPT-based daily plant analysis (JSON → response)
- 🔌 Smart plug support for automation
- 📡 Optional Firebase or MQTT integration

---

## 🔌 Sensors Directory

<pre>
Node/
└── sensors/
    ├── read_temp_humidity.py    # DHT11/DHT22 or BME280
    ├── read_soil_moisture.py    # Capacitive sensor
    ├── read_ph.py               # Analog pH (optional)
    └── mock_data.py             # Simulated values for local dev/testing
</pre>

---

## 🗂️ Repo Structure
<pre>
gianode/
├── Gia/                   # AI + learning engine
│   ├── classify_image.py
│   ├── analyze_data.py
│   ├── gpt_response.py
│   ├── training/
│   │   ├── dataset/
│   │   └── notes.md
│   └── utils/
│       └── __init__.py
│
├── Node/                  # Hardware & sensor-side logic
│   ├── read_sensors.py
│   ├── capture_image.py
│   ├── control_plug.py
│   ├── build_json.py
│   └── config/
│       └── node_config.json
│
├── pipeline/              # Master controller scripts
│   ├── run_pipeline.py
│   └── cronjob.sh
│
├── data/                  # Logs + image capture
│   ├── images/
│   └── logs/
│
├── dashboard/             # (Optional) Local Flask UI
│   └── app.py
│
├── docs/                  # Diagrams, notes, and planning
│   └── architecture.png
│
├── index.html             # GitHub Pages homepage
├── CNAME                  # Domain reference
├── README.md
├── requirements.txt       # Dependencies
└── LICENSE
</pre>
---

## 🔁 How It Works

1. `Node` collects sensor data and a plant image
2. Data is combined into a JSON payload
3. `Gia` classifies the image and interprets the environment
4. A care recommendation or action is returned
5. Optional smart plug or alert is triggered

---

## 🧠 Sample Output (JSON)

{
  "timestamp": "2025-06-24T08:00:00",
  "class": "droopy",
  "temp": 24.7,
  "humidity": 53.2,
  "moisture": 42,
  "pH": 6.3,
  "growth_stage": "veg"
}
---
## 📝 License

This project is licensed under the [MIT License](LICENSE) with an added ethical clause.

Please credit the creator and do not commercially exploit this work without permission.

- 🔓 Open Source: This project is available under the [MIT License](./LICENSE)
- 💼 Commercial: See the [Commercial License Terms](./COMMERCIAL_LICENSE.md)