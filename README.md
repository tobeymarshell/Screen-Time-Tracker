# Windows Screen Time Tracker & System Optimizer 🚀

A lightweight, privacy-first desktop widget for Windows that tracks your screen time, visualizes your app usage, and features a 1-click system optimizer. 

Inspired by Android's Digital Wellbeing and macOS aesthetics, it embeds itself natively into your Windows wallpaper (using the `WorkerW` layer), so it sits perfectly behind your open windows and never gets in the way of your work or games.

<img width="280" height="178" alt="image" src="https://github.com/user-attachments/assets/46dc6c82-8e39-4358-b78c-626715d0876c" />

<img width="792" height="770" alt="image" src="https://github.com/user-attachments/assets/36d30bef-2ca8-482f-89bd-5cda0daed7ae" />


## ✨ Features
- **Digital Wellbeing:** Tracks active window time and saves it locally to an SQLite database.
- **AFK Detection:** Automatically pauses tracking when you are idle for more than 60 seconds.
- **Interactive Dashboard:** A sleek, dark-themed UI showing your top apps and a week-by-week (Sunday to Saturday) history chart. Click any bar to see that specific day's stats.
- **1-Click Optimizer (🚀 Button):** 
  - Gracefully closes visible applications.
  - Force-kills heavy background bloatware (Discord, Steam, WhatsApp, etc.).
  - Trims RAM usage (EmptyWorkingSet).
  - Clears Temp files, empties the Recycle Bin, and flushes DNS.
- **100% Private:** All data is stored locally on your machine in `%LOCALAPPDATA%\ScreenTimeTracker`.

## 🛠️ Installation (Run as Python Script)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tobeymarshell/Screen-Time-Tracker.git
   cd Screen-Time-Tracker
   ```
   or else you can run the .exe file and that's it.
2. **create .exe file (optional)**
   ```bash
   pyinstaller --noconsole --onefile --name "ScreenTime" screen_time.py
