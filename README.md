# ✈️ RSS Flight Promo Bot (Telegram)

A Python bot that monitors flight promotion websites via RSS feeds and sends a **daily digest** of relevant deals directly to Telegram.

This is a personal automation project focused on reliability, simplicity, and zero scraping (RSS-only).

---

## 🚀 Features

- Automatic monitoring of flight promotion RSS feeds
- Keyword-based filtering (flight deals, promotions, international trips)
- Daily Telegram digest (no spam)
- Local persistence with SQLite to avoid duplicate alerts
- Designed to run in background on Windows (Task Scheduler)

---

## 🧰 Tech Stack

- Python 3.12+
- Feedparser (RSS parsing)
- Requests (HTTP)
- Telegram Bot API
- SQLite
- Windows Task Scheduler

---

## ⚙️ Setup & Usage

### 1️⃣ Clone the repository
bash
git clone https://github.com/sergiomoita/flight-bot.git
cd flight-bot

### 2️⃣ Install dependencies
pip install -r requirements.txt

### 3️⃣ Configure environment variables

Set the following variables in your system or in a local (non-versioned) script:

TELEGRAM_BOT_TOKEN

TELEGRAM_CHAT_ID

### 4️⃣ Run manually
python rss_flight_alert_bot.py

---

## 🖥️ Run in Background (Windows)

The bot can be configured to run automatically using Windows Task Scheduler, allowing it to operate silently in the background.

---

## 🔒 Security

This repository does not contain any API keys, tokens, or sensitive data.
All local state and secrets are excluded via .gitignore.

---

## 📌 Notes

The bot sends one message per day (digest format)

Flight deals depend on the availability and content of RSS feeds

Intended for personal and educational use

---

## 📄 License

Personal / educational use.

