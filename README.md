# Windows Screen Time Tracker & System Optimizer 🚀

A lightweight, privacy-first desktop widget for Windows that tracks your screen time, visualizes your app usage, and features a 1-click system optimizer. 

Inspired by Android's Digital Wellbeing and macOS aesthetics, it embeds itself natively into your Windows wallpaper (using the `WorkerW` layer), so it sits perfectly behind your open windows and never gets in the way of your work or games.



<table>
  <tr>
    <img width="306" height="327" alt="image" src="https://github.com/user-attachments/assets/df0d4dc7-16e4-4e0c-91a5-52eefb84bb4a" />

</td>
    <td width="50%"><img width="325" height="285" alt="image" src="https://github.com/user-attachments/assets/8d1708c0-db6e-4294-a355-f505dee552f9" />
</td>
  </tr>
</table>

<img width="855" height="768" alt="image" src="https://github.com/user-attachments/assets/ebcab186-ea49-4ce3-a498-249e3f73addb" />
<img width="967" height="788" alt="image" src="https://github.com/user-attachments/assets/cfeb7ed0-878c-425c-8d07-80501615bae9" />




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
