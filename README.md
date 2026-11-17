# Windows Screen Time Tracker & System Optimizer 🚀

[![Latest Release](https://img.shields.io/badge/Download-Latest%20Release%20(.exe)-brightgreen?style=for-the-badge&logo=windows)](https://github.com/tobeymarshell/Screen-Time-Tracker/releases/latest)

A lightweight, privacy-first desktop widget for Windows that tracks your screen time, visualizes your app usage, and features a 1-click system optimizer.

Inspired by Android's Digital Wellbeing and macOS aesthetics, it embeds itself natively into your Windows wallpaper (using the `WorkerW` layer), so it sits perfectly behind your open windows and never gets in the way of your work or games.

---

### 📦 Quick Download (For Everyone)
Don't want to install Python? Download the standalone executable directly:
👉 **[Download Latest ScreenTime.exe](https://github.com/tobeymarshell/Screen-Time-Tracker/releases/latest)** (No installation required)

---

<table>
  <tr>
    <td width="50%">
      <img width="306" height="327" alt="Desktop Widget" src="https://github.com/user-attachments/assets/df0d4dc7-16e4-4e0c-91a5-52eefb84bb4a" />
    </td>
    <td width="50%">
      <img width="325" height="285" alt="Speed Meter" src="https://github.com/user-attachments/assets/8d1708c0-db6e-4294-a355-f505dee552f9" />
    </td>
  </tr>
</table>

<img width="855" height="768" alt="Screen Time Dashboard" src="https://github.com/user-attachments/assets/ebcab186-ea49-4ce3-a498-249e3f73addb" />
<img width="967" height="788" alt="Data Usage Details" src="https://github.com/user-attachments/assets/cfeb7ed0-878c-425c-8d07-80501615bae9" />

## ✨ Features
- **Digital Wellbeing:** Tracks active window time and saves it locally to an SQLite database.
- **AFK Detection:** Automatically pauses tracking when you are idle for more than 60 seconds.
- **Live Traffic Speed Meters:** Real-time download and upload transfer counters directly on the widget.
- **Per-App Network Data Usage:** Measures daily and monthly data consumption on a per-application basis.
- **Interactive Dashboard:** Dark-themed UI with week-by-week bar charts and day-by-day drill-downs.
- **1-Click Optimizer (⚡ Button):**
  - Trims RAM working sets (`EmptyWorkingSet`).
  - Clears temporary files and flushes DNS cache.
- **100% Private:** All data is stored locally in `%LOCALAPPDATA%\ScreenTimeTracker`.

## 🛠️ Developer Installation & Setup (Run as Python Script)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/tobeymarshell/Screen-Time-Tracker.git
   cd Screen-Time-Tracker
   ```

2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the tracker & widget:**
   ```bash
   python screen_time.py both
   ```

4. **(Optional) Rebuild Standalone .exe:**
   ```bash
   pyinstaller --noconsole --onefile --name "ScreenTime" screen_time.py
   ```
