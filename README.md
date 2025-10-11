# 🛜 Simple Wi-Fi Hotspot via Dongle

Turn your Windows PC into a **custom Wi-Fi hotspot** with a **modern web interface** —  
no external router software required.

![preview]([https://github.com/user-attachments/assets/example.png](https://github.com/sinanyuzgulec/simple_wifi_hotspot_via_dongle/blob/main/img/ss1.png
))
---

## 🚀 Features
- Share Ethernet internet over USB Wi-Fi dongle  
- Manage hotspot via web panel (`Flask`)  
- WPA2-AES encryption (built-in by Windows `netsh`)  
- Set per-user and global bandwidth limits  
- Block/unblock connected users  
- Real-time traffic chart (per Ethernet interface)  
- Persistent configuration (auto-saves JSON)

---

## ⚙️ Requirements

### 🔧 System
- Windows 10/11 (Admin rights required)
- At least one **Ethernet** and one **USB Wi-Fi dongle**

### 🐍 Python
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
