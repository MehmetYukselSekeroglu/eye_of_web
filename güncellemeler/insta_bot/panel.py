import subprocess, os
import tkinter as tk
from tkinter import filedialog
import threading, time, os, requests, datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from PIL import Image, ImageTk

driver=None
running=False
auto_mode=False
targets=[]

FOLLOW_LIMIT=10
AUTO_WAIT=1800

follow_count=0
photo_count=0
def start_worker():
    subprocess.Popen("bash -c 'cd ~/insta_bot && source venv/bin/activate && python worker.py'",shell=True)

def stop_worker():
    if os.path.exists("worker_run.txt"):
        os.remove("worker_run.txt")

# ---------------- LOG ----------------
def log(msg):
    saat=datetime.datetime.now().strftime("%H:%M:%S")
    log_box.insert(tk.END,f"[{saat}] {msg}\n")
    log_box.see(tk.END)

    if int(log_box.index('end-1c').split('.')[0]) > 500:
        log_box.delete("1.0","200.0")

# ---------------- STATS ----------------
def update_stats():
    stats_label.config(text=f"Takipçi: {follow_count}   Foto: {photo_count}")

# ---------------- TARAYICI ----------------
def open_browser():
    global driver
    if driver:
        log("Tarayıcı zaten açık")
        return

    driver=webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get("https://instagram.com")
    log("Login yap")

# ---------------- HEDEF ----------------
def load_targets():
    global targets
    file=filedialog.askopenfilename(title="hedefler.txt")
    if not file:
        return

    with open(file) as f:
        targets=[x.strip() for x in f if x.strip()]

    log(f"{len(targets)} hedef yüklendi")

# ---------------- TAKİPÇİ ----------------
def scrape_target(target):
    global running, follow_count

    log(f"{target} açılıyor")

    driver.get(f"https://instagram.com/{target}/")
    time.sleep(5)

    try:
        driver.find_element(By.XPATH,"//a[contains(@href,'followers')]").click()
    except:
        log("takipçi listesi açılamadı")
        return

    time.sleep(5)
    scroll=driver.find_element(By.XPATH,"//div[@role='dialog']//div[contains(@style,'overflow')]")

    mevcut=set()
    if os.path.exists("takipciler.txt"):
        with open("takipciler.txt") as f:
            mevcut=set(x.strip() for x in f)

    count=0

    while count<FOLLOW_LIMIT and running:
        elems=driver.find_elements(By.XPATH,"//div[@role='dialog']//a")

        for e in elems:
            link=e.get_attribute("href")
            if not link:
                continue

            user=link.split("/")[-2]

            if user in mevcut:
                continue

            with open("takipciler.txt","a") as f:
                f.write(user+"\n")

            mevcut.add(user)
            count+=1
            follow_count+=1
            update_stats()

            log(f"{target} → {user} ({count}/10)")

            if count>=FOLLOW_LIMIT:
                break

        driver.execute_script("arguments[0].scrollTop=arguments[0].scrollHeight",scroll)
        time.sleep(2)

# ---------------- MANUEL ----------------
def manual_run():
    global running

    if not targets:
        log("hedef yükle")
        return

    running=True
    threading.Thread(target=manual_loop).start()

def manual_loop():
    global running

    for t in targets:
        if not running:
            break
        scrape_target(t)

    running=False
    log("manuel bitti")

# ---------------- OTOMATİK ----------------
def auto_loop():
    global running,auto_mode

    log("otomatik başladı")

    while auto_mode:
        running=True

        for t in targets:
            if not auto_mode:
                break
            scrape_target(t)

        running=False

        log("tur bitti → 30 dk bekleniyor")

        for i in range(AUTO_WAIT):
            if not auto_mode:
                break
            time.sleep(1)

def start_auto():
    global auto_mode

    if not targets:
        log("hedef yükle")
        return

    auto_mode=True
    threading.Thread(target=auto_loop).start()

# ---------------- FOTO ----------------
def download_photos():
    global photo_count

    if not os.path.exists("takipciler.txt"):
        log("takipciler.txt yok")
        return

    with open("takipciler.txt") as f:
        users=[x.strip() for x in f if x.strip()]

    os.makedirs("profil_fotolari",exist_ok=True)

    for user in users:
        path=f"profil_fotolari/{user}.jpg"
        if os.path.exists(path):
            continue

        try:
            log(f"foto: {user}")
            driver.get(f"https://instagram.com/{user}/")
            time.sleep(2)

            img=driver.find_element(By.XPATH,"//header//img").get_attribute("src")
            r=requests.get(img)
            open(path,"wb").write(r.content)

            photo_count+=1
            update_stats()

        except:
            log(f"{user} hata")

    log("foto bitti")

# ---------------- STOP ----------------
def stop_all():
    global running,auto_mode
    running=False
    auto_mode=False
    log("durduruldu")

# ---------------- GUI ----------------
root=tk.Tk()
root.title("BOT V1.3")
root.geometry("760x820")
root.configure(bg="#111")
tk.Button(root,text="WORKER BAŞLAT",bg="#0a7d3b",fg="white",width=25,height=2,command=start_worker).pack(pady=4)
tk.Button(root,text="WORKER DURDUR",bg="#a50000",fg="white",width=25,height=2,command=stop_worker).pack(pady=4)

# -------- LOGO --------
img=Image.open("logo.png").resize((160,160))
logo=ImageTk.PhotoImage(img)

tk.Label(root,image=logo,bg="#111").pack(pady=5)
tk.Label(root,text="Chechen Ichkeria Team",fg="white",bg="#111",font=("Arial",18,"bold")).pack(pady=2)

stats_label=tk.Label(root,text="Takipçi: 0   Foto: 0",bg="#111",fg="white",font=("Arial",12))
stats_label.pack(pady=5)

top=tk.Frame(root,bg="#111")
top.pack(pady=5)

tk.Button(top,text="Tarayıcı Aç",bg="#444",fg="white",width=25,height=2,command=open_browser).pack(pady=3)
tk.Button(top,text="hedefler.txt yükle",bg="#555",fg="white",width=25,height=2,command=load_targets).pack(pady=3)

main=tk.Frame(root,bg="#111")
main.pack(pady=10)

# SOL
left=tk.Frame(main,bg="#111")
left.grid(row=0,column=0,padx=40)

tk.Label(left,text="TAKİPÇİ",fg="white",bg="#111",font=("Arial",14)).pack(pady=5)
tk.Button(left,text="MANUEL",bg="#1f6aa5",fg="white",width=20,height=2,command=manual_run).pack(pady=5)
tk.Button(left,text="OTOMATİK",bg="#0a7d3b",fg="white",width=20,height=2,command=start_auto).pack(pady=5)
tk.Button(left,text="DURDUR",bg="#a50000",fg="white",width=20,height=2,command=stop_all).pack(pady=5)

# SAĞ
right=tk.Frame(main,bg="#111")
right.grid(row=0,column=1,padx=40)

tk.Label(right,text="FOTO",fg="white",bg="#111",font=("Arial",14)).pack(pady=5)
tk.Button(right,text="FOTO İNDİR",bg="#a57c00",fg="white",width=20,height=2,command=download_photos).pack(pady=5)

log_box=tk.Text(root,height=18,bg="black",fg="#00ff9c")
log_box.pack(fill="both",expand=True,padx=10,pady=10)

root.mainloop()
