import os
import subprocess
import threading
import time
import json
import re
import socket
import psutil
from flask import Flask, render_template_string, request, redirect, jsonify

app = Flask(__name__)

CONFIG_FILE = "router_config.json"
SSID = "router"
PASSWORD = "12345678"
ETHERNET_IF = "Ethernet"
WIFI_IF = None
GENERAL_LIMIT = "Yok"
LIMITS = {}
BLOCKED = set()

# ===================================================
# HTML (Bootstrap + sekmeler + grafik)
# ===================================================
PAGE = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Wi-Fi Yönetim Paneli</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { background-color:#f8f9fa; }
.card { border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
small.gray { color:#6c757d; }
.table td, .table th { vertical-align: middle; }
</style>
</head>
<body class="p-4">
<div class="container">
<h2 class="mb-4 text-center">📡 Wi-Fi Yönetim Paneli</h2>

<ul class="nav nav-tabs mb-3">
  <li class="nav-item"><a class="nav-link active" data-bs-toggle="tab" href="#tab-users">Kullanıcılar</a></li>
  <li class="nav-item"><a class="nav-link" data-bs-toggle="tab" href="#tab-settings">Ayarlar</a></li>
</ul>

<div class="tab-content">
<div id="tab-users" class="tab-pane fade show active">

  <div class="d-flex justify-content-center mb-3 gap-2">
    <form method="post" action="/hotspot">
      <button name="action" value="start" class="btn btn-success">Hotspot Başlat</button>
      <button name="action" value="stop" class="btn btn-danger">Durdur</button>
      <button name="action" value="restart" class="btn btn-warning">Yeniden Başlat</button>
    </form>
  </div>

  <div class="row text-center mb-4">
    <div class="col-md-3"><div class="card p-3"><h6>Aktif Kullanıcılar</h6><h3>{{ clients|length }}</h3></div></div>
    <div class="col-md-3"><div class="card p-3"><h6>Limitli Kullanıcı</h6><h3>{{ limits|length }}</h3></div></div>
    <div class="col-md-3"><div class="card p-3"><h6>Engellenen</h6><h3>{{ blocked|length }}</h3></div></div>
    <div class="col-md-3"><div class="card p-3"><h6>Genel Limit</h6><h3>{{ general_limit }}</h3></div></div>
  </div>

  <div class="card p-3 mb-4">
    <h5>Kullanıcılar</h5>
    <table class="table table-striped">
      <thead><tr><th>IP</th><th>MAC</th><th>Limit (KB/s)</th><th>İşlem</th></tr></thead>
      <tbody>
      {% for ip, mac in clients %}
      <tr>
        <td>{{ip}}</td><td>{{mac}}</td><td>{{limits.get(mac, "Yok")}}</td>
        <td>
          <form action="/limit" method="post" class="d-inline">
            <input type="hidden" name="mac" value="{{mac}}">
            <input type="number" name="limit" placeholder="KB/s" class="form-control d-inline w-50">
            <button class="btn btn-primary btn-sm">Ayarla</button>
          </form>
          <form action="/block" method="post" class="d-inline">
            <input type="hidden" name="mac" value="{{mac}}">
            {% if mac in blocked %}
              <button name="action" value="unblock" class="btn btn-success btn-sm">Serbest</button>
            {% else %}
              <button name="action" value="block" class="btn btn-warning btn-sm">Engelle</button>
            {% endif %}
          </form>
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
    <small class="gray">Not: Host makinenin IP/MAC, broadcast ve multicast adresleri gösterilmez.</small>
  </div>

  <div class="card p-3">
    <h5>Gerçek Zamanlı Trafik ({{ ethernet_if }})</h5>
    <canvas id="chart" height="100"></canvas>
  </div>

</div>

<div id="tab-settings" class="tab-pane fade p-3">
  <h5>Hotspot & Sistem Ayarları</h5>
  <form method="post" action="/settings" class="mb-3">
    <div class="mb-2">
      <label class="form-label">SSID Adı</label>
      <input type="text" class="form-control" name="ssid" value="{{ssid}}">
    </div>
    <div class="mb-2">
      <label class="form-label">Parola</label>
      <input type="text" class="form-control" name="password" value="{{password}}">
    </div>
    <div class="mb-2">
      <label class="form-label">Genel Hız Limiti (KB/s)</label>
      <input type="text" class="form-control" name="general_limit" value="{{general_limit}}">
    </div>
    <div class="mb-2">
      <label class="form-label">Wi-Fi Dongle</label>
      <select name="wifi_if" class="form-select">
        <option value="">(Otomatik)</option>
        {% for iface in ifaces %}
          <option value="{{iface}}" {% if iface==wifi_if %}selected{% endif %}>{{iface}}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-2">
      <label class="form-label">Ethernet (trafik ölçümü)</label>
      <select name="eth_if" class="form-select">
        {% for iface in ifaces %}
          <option value="{{iface}}" {% if iface==ethernet_if %}selected{% endif %}>{{iface}}</option>
        {% endfor %}
      </select>
    </div>
    <button class="btn btn-primary">Kaydet</button>
  </form>
</div>
</div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
let ctx = document.getElementById('chart');
let chart = new Chart(ctx,{
  type:'line',
  data:{labels:[],datasets:[{label:'KB/s',data:[],borderColor:'#007bff',fill:false}]},
  options:{animation:false,scales:{y:{beginAtZero:true}}}
});
setInterval(()=>{
 fetch('/traffic').then(r=>r.json()).then(d=>{
   chart.data.labels.push('');
   chart.data.datasets[0].data.push(d.speed);
   if(chart.data.labels.length>25){chart.data.labels.shift();chart.data.datasets[0].data.shift();}
   chart.update();
 });
},2000);
</script>
</body></html>
"""

# ===================================================
# Yardımcı Fonksiyonlar
# ===================================================

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return res.stdout
    except Exception:
        return ""

def normalize_mac(mac):
    return mac.lower().replace(":", "-").replace(".", "-")

def get_local_ips():
    ips = set()
    for iface, addrlist in psutil.net_if_addrs().items():
        for addr in addrlist:
            if addr.family == socket.AF_INET:
                ips.add(addr.address)
    return ips

def get_local_macs():
    macs = set()
    for iface, addrlist in psutil.net_if_addrs().items():
        for addr in addrlist:
            if hasattr(addr, "address") and re.match(r"^[0-9a-fA-F:-]{11,}$", addr.address):
                macs.add(normalize_mac(addr.address))
    return macs

def get_ifaces():
    return list(psutil.net_if_addrs().keys())

# ===================================================
# Config dosyası
# ===================================================
def load_config():
    global SSID, PASSWORD, ETHERNET_IF, WIFI_IF, GENERAL_LIMIT, LIMITS, BLOCKED
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        SSID = data.get("ssid", SSID)
        PASSWORD = data.get("password", PASSWORD)
        ETHERNET_IF = data.get("ethernet_if", ETHERNET_IF)
        WIFI_IF = data.get("wifi_if", WIFI_IF)
        GENERAL_LIMIT = data.get("general_limit", GENERAL_LIMIT)
        LIMITS = data.get("limits", LIMITS)
        BLOCKED = set(data.get("blocked", []))

def save_config():
    data = {
        "ssid": SSID, "password": PASSWORD,
        "ethernet_if": ETHERNET_IF, "wifi_if": WIFI_IF,
        "general_limit": GENERAL_LIMIT, "limits": LIMITS,
        "blocked": list(BLOCKED)
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===================================================
# Ağ İşlemleri
# ===================================================
def start_hotspot():
    os.system(f'netsh wlan set hostednetwork mode=allow ssid="{SSID}" key="{PASSWORD}"')
    os.system('netsh wlan start hostednetwork')
    print("[+] Hotspot başlatıldı:", SSID)

def stop_hotspot():
    os.system('netsh wlan stop hostednetwork')
    print("[!] Hotspot durduruldu.")

def restart_hotspot():
    stop_hotspot()
    time.sleep(1)
    start_hotspot()

# ===================================================
# Kullanıcı Listesi (ARP + Filtre)
# ===================================================
def parse_arp():
    output = run_cmd("arp -a")
    clients = []
    local_ips = get_local_ips()
    local_macs = get_local_macs()
    for line in output.splitlines():
        m = re.match(r'\s*([\d\.]+)\s+([0-9a-fA-F\-\:]{11,})\s+\w+', line)
        if not m: 
            continue
        ip = m.group(1)
        mac = normalize_mac(m.group(2))
        # filtreler
        if ip in local_ips: continue
        if mac in local_macs: continue
        if ip.startswith(("224.", "239.")): continue   # multicast
        if ip.endswith(".255") or ip == "255.255.255.255": continue  # broadcast
        if ip.startswith("127.") or ip.startswith("0."): continue
        if mac.startswith(("ff-ff-ff", "01-00-5e")): continue  # broadcast/multicast MAC
        clients.append((ip, mac))
    return clients

# ===================================================
# Trafik Ölçümü
# ===================================================
_last_bytes = None
_last_time = None

def get_ethernet_kbs():
    global _last_bytes, _last_time
    counters = psutil.net_io_counters(pernic=True)
    if ETHERNET_IF not in counters:
        return 0.0
    total = counters[ETHERNET_IF].bytes_sent + counters[ETHERNET_IF].bytes_recv
    now = time.time()
    if _last_bytes is None:
        _last_bytes = total
        _last_time = now
        return 0.0
    dt = now - _last_time
    kb_s = (total - _last_bytes) / 1024 / dt if dt > 0 else 0
    _last_bytes, _last_time = total, now
    return round(max(kb_s, 0), 2)

# ===================================================
# Flask Rotaları
# ===================================================
@app.route("/")
def index():
    clients = parse_arp()
    return render_template_string(PAGE,
        clients=clients, limits=LIMITS, blocked=BLOCKED,
        general_limit=GENERAL_LIMIT, ssid=SSID, password=PASSWORD,
        wifi_if=WIFI_IF, ethernet_if=ETHERNET_IF, ifaces=get_ifaces()
    )

@app.route("/hotspot", methods=["POST"])
def hotspot_control():
    action = request.form.get("action")
    if action == "start": threading.Thread(target=start_hotspot).start()
    elif action == "stop": threading.Thread(target=stop_hotspot).start()
    elif action == "restart": threading.Thread(target=restart_hotspot).start()
    return redirect("/")

@app.route("/limit", methods=["POST"])
def set_limit():
    mac = request.form.get("mac")
    limit = request.form.get("limit")
    if mac:
        if limit: LIMITS[mac] = limit
        else: LIMITS.pop(mac, None)
        save_config()
    return redirect("/")

@app.route("/block", methods=["POST"])
def block_user():
    mac = request.form.get("mac")
    action = request.form.get("action")
    if mac:
        if action == "block": BLOCKED.add(mac)
        elif action == "unblock": BLOCKED.discard(mac)
        save_config()
    return redirect("/")

@app.route("/settings", methods=["POST"])
def save_settings():
    global SSID, PASSWORD, GENERAL_LIMIT, WIFI_IF, ETHERNET_IF
    SSID = request.form.get("ssid") or SSID
    PASSWORD = request.form.get("password") or PASSWORD
    GENERAL_LIMIT = request.form.get("general_limit") or "Yok"
    WIFI_IF = request.form.get("wifi_if") or None
    ETHERNET_IF = request.form.get("eth_if") or ETHERNET_IF
    save_config()
    return redirect("/")

@app.route("/traffic")
def traffic_data():
    return jsonify({"speed": get_ethernet_kbs()})

# ===================================================
# Başlat
# ===================================================
if __name__ == "__main__":
    load_config()
    _ = get_ethernet_kbs()
    print("Panel açık: http://127.0.0.1:5000 (Yönetici olarak çalıştırın)")
    app.run(host="0.0.0.0", port=5000, debug=False)
