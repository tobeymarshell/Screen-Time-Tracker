# Windows Screen Time Tracker & System Optimizer 🚀

A lightweight, privacy-first desktop widget for Windows that tracks your screen time, visualizes your app usage, and features a 1-click system optimizer. 

Inspired by Android's Digital Wellbeing and macOS aesthetics, it embeds itself natively into your Windows wallpaper (using the `WorkerW` layer), so it sits perfectly behind your open windows and never gets in the way of your work or games.



<table>
  <tr>
    <td width="50%"><img width="282" height="188" alt="image" src="https://github.com/user-attachments/assets/688bfe84-47c3-4d48-917f-0f41add19938" />
</td>
    <td width="50%"><img width="325" height="285" alt="image" src="https://github.com/user-attachments/assets/8d1708c0-db6e-4294-a355-f505dee552f9" />
</td>
  </tr>
</table>

<img width="855" height="768" alt="image" src="https://github.com/user-attachments/assets/ebcab186-ea49-4ce3-a498-249e3f73addb" />



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

3. **create .exe file (optional)**
   ```bash
   pyinstaller --noconsole --onefile --name "ScreenTime" screen_time.py
