import telebot
import requests
import json
import time
import sqlite3
import os
import threading
import re
from flask import Flask, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from datetime import datetime, timedelta

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8756118508:AAGA06F7DfF9A0T_bYQ1ymoGfNRe_UfGgNY")

# ===== APNI API CONFIG =====
API_BASE_URL = "https://apple-apixdev.onrender.com/api"
API_KEY = "DevKing77"

# GROUP & CHANNEL
GROUP_LINK = "https://t.me/+3I9rJfeh5XVkZDM1"
GROUP_ID = -1003758601788
CHANNEL_LINK = "https://t.me/+1Jqq3-0RKpEyNTM1"
CHANNEL_ID = -1003791928633

# IMAGE & VIDEO
START_IMAGE = "https://i.ibb.co/LjY2dHQ/Picsart-26-02-23-10-49-39-278.jpg"
WELCOME_VIDEO = "https://drive.google.com/uc?export=download&id=1FBbOYsTzDF5gN170A-pDAn3jGb2IcVNi"
INFO_VIDEO = "https://drive.google.com/uc?export=download&id=1l4piMX7BMlQiwRAjeemKsQTSJTZCjUy0"

# BRAND
BRAND = "꧁💠⃟‌⃟ 𝕯єν꧂"
CREATOR = "Dev"

# ===== OWNER & ADMIN CONFIG =====
OWNER_ID = 8066199853
ADMIN_USERNAME = "@Crownbattlesupport"

# ===== BOT CONFIGURATIONS =====
FREE_CREDITS = 2
REFERRAL_BONUS = 2
REFERRALS_NEEDED = 5

# ===== BOT STATUS =====
BOT_ACTIVE = True  # Bot on/off status
MAINTENANCE_MODE = False  # Maintenance mode

# ==================== DATABASE SETUP ====================
db_path = '/tmp/premium_bot.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# Users table with all features
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              username TEXT,
              first_used TEXT,
              verified INTEGER DEFAULT 0,
              is_admin INTEGER DEFAULT 0,
              is_owner INTEGER DEFAULT 0,
              is_banned INTEGER DEFAULT 0,
              credits_used INTEGER DEFAULT 0,
              total_credits INTEGER DEFAULT 2,
              referrals_count INTEGER DEFAULT 0,
              batch_type TEXT DEFAULT 'free',  -- free, premium, star, admin
              batch_expiry TEXT,
              last_reset TEXT)''')

# Referrals table
c.execute('''CREATE TABLE IF NOT EXISTS referrals
             (referrer_id INTEGER,
              referred_id INTEGER,
              referred_date TEXT,
              bonus_given INTEGER DEFAULT 0,
              PRIMARY KEY (referrer_id, referred_id))''')

# Banned users table
c.execute('''CREATE TABLE IF NOT EXISTS banned_users
             (user_id INTEGER PRIMARY KEY,
              banned_by INTEGER,
              ban_reason TEXT,
              ban_date TEXT,
              unban_date TEXT)''')

# Block list (admin block)
c.execute('''CREATE TABLE IF NOT EXISTS block_list
             (user_id INTEGER PRIMARY KEY,
              blocked_by INTEGER,
              block_reason TEXT,
              block_date TEXT)''')

# Bot status table
c.execute('''CREATE TABLE IF NOT EXISTS bot_status
             (id INTEGER PRIMARY KEY CHECK (id = 1),
              is_active INTEGER DEFAULT 1,
              maintenance_mode INTEGER DEFAULT 0,
              last_changed_by INTEGER,
              last_changed_date TEXT)''')

# Insert bot status if not exists
c.execute("INSERT OR IGNORE INTO bot_status (id, is_active, maintenance_mode) VALUES (1, 1, 0)")

conn.commit()

# ==================== DATABASE FUNCTIONS ====================

def ensure_owner_in_db():
    c.execute("INSERT OR REPLACE INTO users (user_id, is_owner, is_admin, verified, total_credits, batch_type) VALUES (?, 1, 1, 1, 999999, 'owner')", (OWNER_ID,))
    conn.commit()

ensure_owner_in_db()

# ==================== BOT STATUS FUNCTIONS ====================

def get_bot_status():
    c.execute("SELECT is_active, maintenance_mode FROM bot_status WHERE id = 1")
    result = c.fetchone()
    if result:
        return {'active': result[0] == 1, 'maintenance': result[1] == 1}
    return {'active': True, 'maintenance': False}

def set_bot_status(active=None, maintenance=None, changed_by=None):
    current = get_bot_status()
    new_active = current['active'] if active is None else active
    new_maintenance = current['maintenance'] if maintenance is None else maintenance
    
    c.execute('''UPDATE bot_status 
                 SET is_active = ?, maintenance_mode = ?, last_changed_by = ?, last_changed_date = ? 
                 WHERE id = 1''',
              (1 if new_active else 0, 1 if new_maintenance else 0, changed_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    global BOT_ACTIVE, MAINTENANCE_MODE
    BOT_ACTIVE = new_active
    MAINTENANCE_MODE = new_maintenance

# ==================== BATCH FUNCTIONS ====================

BATCH_FEATURES = {
    'free': {
        'name': '👤 Free User',
        'credits': FREE_CREDITS,
        'can_refer': True,
        'can_use_commands': True,
        'color': '⚪'
    },
    'premium': {
        'name': '💎 Premium User',
        'credits': 50,
        'can_refer': True,
        'can_use_commands': True,
        'can_bypass_limit': True,
        'color': '💜'
    },
    'star': {
        'name': '⭐ Star User',
        'credits': 100,
        'can_refer': True,
        'can_use_commands': True,
        'can_bypass_limit': True,
        'priority_support': True,
        'color': '✨'
    },
    'admin': {
        'name': '👑 Admin',
        'credits': 999999,
        'can_refer': True,
        'can_use_commands': True,
        'can_bypass_limit': True,
        'can_manage_users': True,
        'color': '🔥'
    },
    'owner': {
        'name': '👑 OWNER',
        'credits': 999999,
        'can_refer': True,
        'can_use_commands': True,
        'can_bypass_limit': True,
        'can_manage_users': True,
        'can_manage_bot': True,
        'color': '👑'
    }
}

def get_user_batch(user_id):
    c.execute("SELECT batch_type FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        return result[0]
    return 'free'

def set_user_batch(user_id, batch_type, set_by=None):
    if batch_type in BATCH_FEATURES:
        c.execute("UPDATE users SET batch_type = ? WHERE user_id = ?", (batch_type, user_id))
        
        # Update credits based on batch
        if batch_type == 'premium':
            c.execute("UPDATE users SET total_credits = 50 WHERE user_id = ?", (user_id,))
        elif batch_type == 'star':
            c.execute("UPDATE users SET total_credits = 100 WHERE user_id = ?", (user_id,))
        elif batch_type == 'admin':
            c.execute("UPDATE users SET total_credits = 999999, is_admin = 1 WHERE user_id = ?", (user_id,))
        elif batch_type == 'owner':
            c.execute("UPDATE users SET total_credits = 999999, is_admin = 1, is_owner = 1 WHERE user_id = ?", (user_id,))
        
        conn.commit()
        return True
    return False

# ==================== BAN/UNBAN FUNCTIONS ====================

def is_user_banned(user_id):
    c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def ban_user(user_id, banned_by, reason="No reason"):
    c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?, ?, ?)",
              (user_id, banned_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), None))
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def unban_user(user_id):
    c.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== BLOCK FUNCTIONS ====================

def is_user_blocked(user_id):
    c.execute("SELECT * FROM block_list WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def block_user(user_id, blocked_by, reason="No reason"):
    c.execute("INSERT OR REPLACE INTO block_list VALUES (?, ?, ?, ?)",
              (user_id, blocked_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def unblock_user(user_id):
    c.execute("DELETE FROM block_list WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== USER CREDITS FUNCTIONS ====================

def is_admin_user(user_id):
    if user_id == OWNER_ID:
        return True
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def get_user_credits(user_id):
    if is_user_banned(user_id):
        return {'used': 0, 'total': 0, 'left': 0, 'referrals': 0, 'batch': 'banned'}
    
    c.execute("SELECT credits_used, total_credits, referrals_count, batch_type FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        used, total, referrals, batch = result
        return {
            'used': used,
            'total': total,
            'left': total - used,
            'referrals': referrals,
            'batch': batch
        }
    else:
        # New user
        c.execute("INSERT INTO users (user_id, first_used, total_credits, batch_type) VALUES (?, ?, ?, 'free')",
                 (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), FREE_CREDITS))
        conn.commit()
        return {'used': 0, 'total': FREE_CREDITS, 'left': FREE_CREDITS, 'referrals': 0, 'batch': 'free'}

def use_credit(user_id):
    if user_id == OWNER_ID or is_admin_user(user_id):
        return True
    
    if is_user_banned(user_id):
        return False
    
    credits = get_user_credits(user_id)
    if credits['left'] > 0:
        c.execute("UPDATE users SET credits_used = credits_used + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    return False

def add_referral(referrer_id, referred_id):
    c.execute("SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, referred_id))
    if c.fetchone():
        return False
    
    c.execute("INSERT INTO referrals VALUES (?, ?, ?, 0)",
             (referrer_id, referred_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
    
    c.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
    count = c.fetchone()[0]
    
    if count % REFERRALS_NEEDED == 0:
        c.execute("UPDATE users SET total_credits = total_credits + ? WHERE user_id = ?", 
                 (REFERRAL_BONUS, referrer_id))
        conn.commit()
        return True
    else:
        conn.commit()
        return False

# ==================== MESSAGES STYLES ====================

WELCOME_CAPTION = f"""
╔══════════════════════════════╗
║     🌀 PREMIUM HUNTER 🌀     ║
╠══════════════════════════════╣
║   💎 PREMIUM BOT 💎          ║
║   {BRAND}                    ║
╠══════════════════════════════╣
║   📹 WELCOME VIDEO           ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║                               ║
║   🎯 WHAT WE OFFER:           ║
║   • Telegram ID to Number    ║
║   • Fast & Accurate          ║
║   • 100% Working             ║
║                               ║
╠══════════════════════════════╣
║   💰 PRICING:                 ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ✨ FREE: {FREE_CREDITS} Credits     ║
║   💎 PREMIUM: 50 Credits     ║
║   ⭐ STAR: 100 Credits       ║
║                               ║
║   🔥 REFER: {REFERRALS_NEEDED} = +{REFERRAL_BONUS} ║
║                               ║
╠══════════════════════════════╣
║   📌 COMMANDS:                ║
║   /tg [id] - Get Number      ║
║   /profile - Your Stats      ║
║   /share - Referral Link     ║
║   /admins - Contact Team     ║
║                               ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

BOT_OFF_MSG = f"""
╔══════════════════════════════╗
║     ⚠️ BOT UNDER MAINTENANCE ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   Currently bot is turned    ║
║   OFF by owner.              ║
║                               ║
║   🔴 Status: INACTIVE        ║
║                               ║
║   Please contact owner:      ║
║   👑 {OWNER_ID}               ║
║   📞 @Crownbattlesupport     ║
╠══════════════════════════════╣
║   🔗 Click below to message  ║
╚══════════════════════════════╝
"""

USER_BANNED_MSG = f"""
╔══════════════════════════════╗
║     🚫 ACCOUNT BANNED       ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   You are currently banned   ║
║   from using this bot.       ║
║                               ║
║   Reason: {{reason}}          ║
║   Banned by: Admin           ║
║                               ║
║   Contact owner to appeal:   ║
║   @Crownbattlesupport        ║
╚══════════════════════════════╝
"""

# ==================== BOT INIT ====================
bot = telebot.TeleBot(BOT_TOKEN)

# ==================== CHECK BOT STATUS DECORATOR ====================
def bot_active_check(func):
    def wrapper(message):
        status = get_bot_status()
        
        # Owner always bypass
        if message.from_user.id == OWNER_ID:
            return func(message)
        
        # Check if bot is active
        if not status['active'] or status['maintenance']:
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("👑 Contact Owner", url=f"tg://user?id={OWNER_ID}"),
                InlineKeyboardButton("📞 Support", url="https://t.me/Crownbattlesupport")
            )
            bot.reply_to(message, BOT_OFF_MSG, parse_mode="Markdown", reply_markup=markup)
            return
        
        # Check if user is banned
        if is_user_banned(message.from_user.id):
            c.execute("SELECT ban_reason FROM banned_users WHERE user_id = ?", (message.from_user.id,))
            reason = c.fetchone()
            reason_text = reason[0] if reason else "Violation of rules"
            bot.reply_to(message, USER_BANNED_MSG.format(reason=reason_text), parse_mode="Markdown")
            return
        
        return func(message)
    return wrapper

# ==================== CHECK MEMBERSHIP ====================
def check_membership(user_id):
    try:
        group_member = bot.get_chat_member(GROUP_ID, user_id)
        group_ok = group_member.status in ['member', 'administrator', 'creator']
        
        channel_member = bot.get_chat_member(CHANNEL_ID, user_id)
        channel_ok = channel_member.status in ['member', 'administrator', 'creator']
        
        return group_ok and channel_ok
    except:
        return False

def is_user_verified(user_id):
    c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def mark_user_verified(user_id):
    c.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== API FUNCTION ====================
def id_to_number(user_id):
    try:
        url = f"{API_BASE_URL}/tginfo?key={API_KEY}&id={user_id}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == 'success':
            return {
                'user_id': user_id,
                'number': data.get('number', 'Not Found'),
                'name': data.get('name', 'Unknown'),
                'country': data.get('country', 'Unknown'),
                'status': 'success'
            }
        else:
            return {
                'user_id': user_id,
                'number': 'Not Found',
                'name': 'Unknown',
                'country': 'Unknown',
                'status': 'error'
            }
    except Exception as e:
        return {
            'user_id': user_id,
            'number': 'API Error',
            'name': 'Error',
            'country': 'Error',
            'status': 'error'
        }

# ==================== START COMMAND ====================
@bot.message_handler(commands=['start'])
@bot_active_check
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    ensure_owner_in_db()
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user_id and not is_user_banned(referrer_id):
                bonus_given = add_referral(referrer_id, user_id)
                if bonus_given:
                    try:
                        bot.send_message(referrer_id, 
                            f"🎉 **Bonus Unlocked!**\n\nYou got +{REFERRAL_BONUS} credits for {REFERRALS_NEEDED} referrals!\n{BRAND}", 
                            parse_mode="Markdown")
                    except:
                        pass
        except:
            pass
    
    # Check if already verified
    if is_user_verified(user_id):
        try:
            bot.send_video(
                chat_id,
                WELCOME_VIDEO,
                caption=WELCOME_CAPTION,
                parse_mode="Markdown",
                supports_streaming=True
            )
        except:
            bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
        return
    
    # Pehle image bhejo
    try:
        bot.send_photo(chat_id, START_IMAGE, caption="🌀 **Premium Number Hunter**", parse_mode="Markdown")
    except:
        pass
    
    # Membership check button
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
        InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK),
        InlineKeyboardButton("✅ Verify Membership", callback_data="verify")
    )
    
    bot.send_message(
        chat_id,
        "**🔒 Membership Required!**\n\nPlease join our Group & Channel first, then click Verify:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==================== VERIFY CALLBACK ====================
@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        bot.delete_message(chat_id, call.message.message_id)
        
        try:
            bot.send_video(
                chat_id,
                WELCOME_VIDEO,
                caption=WELCOME_CAPTION,
                parse_mode="Markdown",
                supports_streaming=True
            )
        except:
            bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
        
        bot.answer_callback_query(call.id, "✅ Verification Successful! Welcome to Premium Bot!")
    else:
        bot.answer_callback_query(
            call.id,
            "❌ You haven't joined yet! Please join Group & Channel first.",
            show_alert=True
        )

# ==================== TG COMMAND ====================
@bot.message_handler(commands=['tg'])
@bot_active_check
def tg_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check membership
    if not is_user_verified(user_id):
        if not check_membership(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
                InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
            )
            bot.reply_to(
                message,
                "❌ **Access Denied!**\n\nPlease join our Group & Channel first.",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return
        else:
            mark_user_verified(user_id)
    
    # Parse command
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(
            message,
            f"❌ **Usage:** `/tg [TARGET_ID]`\n\nExample: `/tg 123456789`",
            parse_mode="Markdown"
        )
        return
    
    target_id = args[1]
    
    if not target_id.isdigit():
        bot.reply_to(
            message,
            f"❌ **Invalid ID!**\n\nPlease enter a valid numeric ID.\nExample: `/tg 123456789`",
            parse_mode="Markdown"
        )
        return
    
    # Check credits
    credits = get_user_credits(user_id)
    if credits['left'] <= 0:
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        no_credits_msg = f"""
╔══════════════════════════════╗
║     ⚠️ NO CREDITS LEFT       ║
╠══════════════════════════════╣
║   💎 {BRAND} 💎              ║
╠══════════════════════════════╣
║   You have used all your     ║
║   {FREE_CREDITS} free credits!     ║
╠══════════════════════════════╣
║   🔥 Upgrade to Premium:     ║
║   💎 Premium: 50 Credits    ║
║   ⭐ Star: 100 Credits      ║
╠══════════════════════════════╣
║   🔗 Your referral link:     ║
║   `{referral_link}`          ║
╚══════════════════════════════╝
"""
        bot.reply_to(message, no_credits_msg, parse_mode="Markdown")
        return
    
    # Searching message
    searching = bot.reply_to(message, "🔍 **Searching for number...**", parse_mode="Markdown")
    
    # Call API
    result = id_to_number(target_id)
    
    # Delete searching message
    bot.delete_message(chat_id, searching.message_id)
    
    # Use credit
    use_credit(user_id)
    
    # Get updated credits
    new_credits = get_user_credits(user_id)
    
    if result['status'] == 'success':
        success_msg = f"""
╔══════════════════════════════╗
║     ✅ LOOKUP RESULT ✅      ║
╠══════════════════════════════╣
║   💎 {BRAND} 💎              ║
╠══════════════════════════════╣
║   🆔 USER ID: {result['user_id']}     ║
║   📱 NUMBER: {result['number']}       ║
║   📛 NAME: {result['name']}           ║
║   🌍 COUNTRY: {result['country']}     ║
╠══════════════════════════════╣
║   ⚡ CREDITS LEFT: {new_credits['left']} ║
║   🏷️ BATCH: {new_credits['batch'].upper()} ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""
        bot.reply_to(message, success_msg, parse_mode="Markdown")
    else:
        error_msg = f"""
╔══════════════════════════════╗
║     ❌ LOOKUP FAILED         ║
╠══════════════════════════════╣
║   💎 {BRAND} 💎              ║
╠══════════════════════════════╣
║   • ID not found             ║
║   • Private account          ║
║   • API Error                ║
╠══════════════════════════════╣
║   ⚡ CREDITS LEFT: {new_credits['left']} ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""
        bot.reply_to(message, error_msg, parse_mode="Markdown")

# ==================== PROFILE COMMAND ====================
@bot.message_handler(commands=['profile'])
@bot_active_check
def profile_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    
    credits = get_user_credits(user_id)
    batch = credits['batch']
    batch_info = BATCH_FEATURES.get(batch, BATCH_FEATURES['free'])
    
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    if next_bonus == REFERRALS_NEEDED:
        next_bonus = 0
    
    profile_msg = f"""
╔══════════════════════════════╗
║     📊 PREMIUM PROFILE       ║
╠══════════════════════════════╣
║   💎 {BRAND} 💎              ║
╠══════════════════════════════╣
║   👤 USER: @{username}       ║
║   🆔 ID: {user_id}           ║
║   🏷️ BATCH: {batch_info['color']} {batch_info['name']} ║
╠══════════════════════════════╣
║   💰 CREDIT STATUS:           ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   📊 Used: {credits['used']}/{credits['total']} ║
║   💎 Left: {credits['left']} credits    ║
║                               ║
║   👥 REFERRALS: {credits['referrals']}   ║
║   🔥 Next Bonus: {next_bonus} referrals  ║
╠══════════════════════════════╣
║   ✨ Features:                ║
"""
    if batch_info.get('can_bypass_limit'):
        profile_msg += "║   ✅ Unlimited Commands    ║\n"
    if batch_info.get('priority_support'):
        profile_msg += "║   ⭐ Priority Support     ║\n"
    if batch_info.get('can_manage_users'):
        profile_msg += "║   👥 Can Manage Users    ║\n"
    
    profile_msg += f"""
╠══════════════════════════════╣
║   💡 Get more: /share        ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""
    
    bot.reply_to(message, profile_msg, parse_mode="Markdown")

# ==================== SHARE COMMAND ====================
@bot.message_handler(commands=['share'])
@bot_active_check
def share_command(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    
    share_msg = f"""
╔══════════════════════════════╗
║     🔗 REFERRAL LINK        ║
╠══════════════════════════════╣
║   💎 {BRAND} 💎              ║
╠══════════════════════════════╣
║   👥 Your Referrals: {credits['referrals']} ║
║   🔥 Need {next_bonus} more for  ║
║   ✨ +{REFERRAL_BONUS} Credits      ║
╠══════════════════════════════╣
║   🔗 `{referral_link}`        ║
╠══════════════════════════════╣
║   📤 Share this link with    ║
║   your friends & earn!       ║
╚══════════════════════════════╝
"""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 Share Now", switch_inline_query=f"Join Premium Bot! {referral_link}"))
    
    bot.reply_to(message, share_msg, parse_mode="Markdown", reply_markup=markup)

# ==================== ADMINS COMMAND ====================
@bot.message_handler(commands=['admins'])
@bot_active_check
def admins_command(message):
    c.execute("SELECT user_id, batch_type FROM users WHERE is_admin = 1 OR is_owner = 1")
    admins = c.fetchall()
    
    msg = f"""
╔══════════════════════════════╗
║     👑 ADMIN TEAM 👑        ║
╠══════════════════════════════╣
║   💎 {BRAND} 💎              ║
╠══════════════════════════════╣
"""
    
    markup = InlineKeyboardMarkup()
    for admin_id, batch in admins:
        role = "👑 OWNER" if admin_id == OWNER_ID else "👥 ADMIN"
        msg += f"║   {role}: `{admin_id}`\n"
        markup.add(InlineKeyboardButton(f"📩 Message {admin_id}", url=f"tg://user?id={admin_id}"))
    
    msg += f"""
╠══════════════════════════════╣
║   Click below to contact    ║
║   any team member directly! ║
╚══════════════════════════════╝
"""
    
    bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=markup)

# ==================== VERIFY COMMAND ====================
@bot.message_handler(commands=['verify'])
@bot_active_check
def verify_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        bot.reply_to(message, "✅ **Verification Successful!** You can now use the bot.", parse_mode="Markdown")
    else:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
            InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
        )
        bot.reply_to(
            message,
            "❌ **Not a member!**\n\nPlease join our Group & Channel first.",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ==================== OWNER/ADMIN COMMANDS ====================

# -------------------- BOT CONTROL COMMANDS --------------------
@bot.message_handler(commands=['botoff'])
def bot_off(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this!")
        return
    
    set_bot_status(active=False, changed_by=OWNER_ID)
    bot.reply_to(message, "🔴 **Bot is now OFF!**\n\nUsers will see maintenance message.", parse_mode="Markdown")

@bot.message_handler(commands=['boton'])
def bot_on(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this!")
        return
    
    set_bot_status(active=True, changed_by=OWNER_ID)
    bot.reply_to(message, "🟢 **Bot is now ON!**", parse_mode="Markdown")

@bot.message_handler(commands=['maintenance'])
def maintenance_mode(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this!")
        return
    
    current = get_bot_status()
    set_bot_status(maintenance=not current['maintenance'], changed_by=OWNER_ID)
    status = "ON" if not current['maintenance'] else "OFF"
    bot.reply_to(message, f"🛠️ **Maintenance mode is now {status}!**", parse_mode="Markdown")

# -------------------- BAN/UNBAN COMMANDS --------------------
@bot.message_handler(commands=['ban'])
def ban_user_cmd(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /ban [user_id] [reason]")
        return
    
    try:
        target_id = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "No reason"
        
        if target_id == OWNER_ID:
            bot.reply_to(message, "❌ Cannot ban owner!")
            return
        
        ban_user(target_id, message.from_user.id, reason)
        bot.reply_to(message, f"✅ User {target_id} has been banned!\nReason: {reason}")
        
        # Notify user
        try:
            bot.send_message(target_id, f"🚫 You have been banned!\nReason: {reason}\n\nContact @Crownbattlesupport")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['unban'])
def unban_user_cmd(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /unban [user_id]")
        return
    
    try:
        target_id = int(args[1])
        unban_user(target_id)
        bot.reply_to(message, f"✅ User {target_id} has been unbanned!")
        
        # Notify user
        try:
            bot.send_message(target_id, f"✅ You have been unbanned! You can now use the bot again.")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['block'])
def block_user_cmd(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /block [user_id] [reason]")
        return
    
    try:
        target_id = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "No reason"
        
        if target_id == OWNER_ID:
            bot.reply_to(message, "❌ Cannot block owner!")
            return
        
        block_user(target_id, message.from_user.id, reason)
        bot.reply_to(message, f"✅ User {target_id} has been blocked!\nReason: {reason}")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['unblock'])
def unblock_user_cmd(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /unblock [user_id]")
        return
    
    try:
        target_id = int(args[1])
        unblock_user(target_id)
        bot.reply_to(message, f"✅ User {target_id} has been unblocked!")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

# -------------------- BATCH COMMANDS --------------------
@bot.message_handler(commands=['givepremium'])
def give_premium(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /givepremium [user_id]")
        return
    
    try:
        target_id = int(args[1])
        set_user_batch(target_id, 'premium', message.from_user.id)
        bot.reply_to(message, f"✅ User {target_id} is now 💎 PREMIUM!")
        
        try:
            bot.send_message(target_id, f"🎉 **Congratulations!**\n\nYou have been upgraded to 💎 PREMIUM batch!\nYou now have 50 credits!", parse_mode="Markdown")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['givestar'])
def give_star(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /givestar [user_id]")
        return
    
    try:
        target_id = int(args[1])
        set_user_batch(target_id, 'star', message.from_user.id)
        bot.reply_to(message, f"✅ User {target_id} is now ⭐ STAR!")
        
        try:
            bot.send_message(target_id, f"🎉 **Congratulations!**\n\nYou have been upgraded to ⭐ STAR batch!\nYou now have 100 credits with priority support!", parse_mode="Markdown")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['giveadmin'])
def give_admin(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /giveadmin [user_id]")
        return
    
    try:
        target_id = int(args[1])
        set_user_batch(target_id, 'admin', message.from_user.id)
        bot.reply_to(message, f"✅ User {target_id} is now 👑 ADMIN!")
        
        try:
            bot.send_message(target_id, f"🎉 **Congratulations!**\n\nYou have been made 👑 ADMIN!\nYou now have unlimited credits and admin powers!", parse_mode="Markdown")
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

# -------------------- LIST COMMANDS --------------------
@bot.message_handler(commands=['blocklist'])
def block_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT user_id, block_reason, block_date FROM block_list")
    blocked = c.fetchall()
    
    if not blocked:
        bot.reply_to(message, "📝 **Block List is empty!**", parse_mode="Markdown")
        return
    
    msg = "🚫 **BLOCK LIST** 🚫\n\n"
    for user_id, reason, date in blocked:
        msg += f"• `{user_id}` - {reason}\n  📅 {date[:10]}\n\n"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['banlist'])
def ban_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT user_id, ban_reason, ban_date FROM banned_users")
    banned = c.fetchall()
    
    if not banned:
        bot.reply_to(message, "📝 **Ban List is empty!**", parse_mode="Markdown")
        return
    
    msg = "🔨 **BAN LIST** 🔨\n\n"
    for user_id, reason, date in banned:
        msg += f"• `{user_id}` - {reason}\n  📅 {date[:10]}\n\n"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['memberlist'])
def member_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    
    c.execute("SELECT user_id, batch_type FROM users ORDER BY first_used DESC LIMIT 50")
    members = c.fetchall()
    
    msg = f"📋 **MEMBER LIST** (Last 50)\nTotal Members: {total}\n\n"
    for user_id, batch in members:
        emoji = "👑" if batch == 'owner' else "🔥" if batch == 'admin' else "⭐" if batch == 'star' else "💎" if batch == 'premium' else "👤"
        msg += f"{emoji} `{user_id}` - {batch}\n"
    
    # Send in chunks if too long
    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            bot.reply_to(message, msg[i:i+4000], parse_mode="Markdown")
    else:
        bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['premiumlist'])
def premium_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT user_id FROM users WHERE batch_type IN ('premium', 'star', 'admin', 'owner')")
    premium = c.fetchall()
    
    if not premium:
        bot.reply_to(message, "📝 **No premium members!**", parse_mode="Markdown")
        return
    
    msg = "💎 **PREMIUM MEMBERS** 💎\n\n"
    for (user_id,) in premium:
        msg += f"• `{user_id}`\n"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['freelist'])
def free_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT user_id FROM users WHERE batch_type = 'free'")
    free_users = c.fetchall()
    
    if not free_users:
        bot.reply_to(message, "📝 **No free members!**", parse_mode="Markdown")
        return
    
    msg = "👤 **FREE MEMBERS** 👤\n\n"
    for (user_id,) in free_users[:50]:  # Limit to 50
        msg += f"• `{user_id}`\n"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['adminlist'])
def admin_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT user_id, batch_type FROM users WHERE is_admin = 1 OR is_owner = 1")
    admins = c.fetchall()
    
    msg = "👑 **ADMIN TEAM** 👑\n\n"
    markup = InlineKeyboardMarkup()
    
    for user_id, batch in admins:
        role = "👑 OWNER" if user_id == OWNER_ID else "👥 ADMIN"
        msg += f"{role}: `{user_id}`\n"
        markup.add(InlineKeyboardButton(f"📩 Message {user_id}", url=f"tg://user?id={user_id}"))
    
    bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=markup)

# -------------------- OTHER ADMIN COMMANDS --------------------
@bot.message_handler(commands=['addcredits'])
def add_credits(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: /addcredits [user_id] [amount]")
        return
    
    try:
        target = int(args[1])
        amount = int(args[2])
        c.execute("UPDATE users SET total_credits = total_credits + ? WHERE user_id = ?", (amount, target))
        conn.commit()
        bot.reply_to(message, f"✅ Added {amount} credits to user {target}!")
    except:
        bot.reply_to(message, "❌ Invalid input!")

@bot.message_handler(commands=['botstatus'])
def bot_status_cmd(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    status = get_bot_status()
    status_msg = f"""
📊 **BOT STATUS**
━━━━━━━━━━━━━━━━
🟢 Active: {'YES' if status['active'] else 'NO'}
🛠️ Maintenance: {'YES' if status['maintenance'] else 'NO'}

👑 Owner: {OWNER_ID}
💎 Brand: {BRAND}
"""
    bot.reply_to(message, status_msg, parse_mode="Markdown")

# ==================== ERROR HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    # Check if bot is active first
    status = get_bot_status()
    if not status['active'] or status['maintenance']:
        if message.from_user.id != OWNER_ID:
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("👑 Contact Owner", url=f"tg://user?id={OWNER_ID}"),
                InlineKeyboardButton("📞 Support", url="https://t.me/Crownbattlesupport")
            )
            bot.reply_to(message, BOT_OFF_MSG, parse_mode="Markdown", reply_markup=markup)
            return
    
    bot.reply_to(
        message,
        f"❌ **Invalid Command!**\n\nUse /start to see available commands.\n\n{BRAND}",
        parse_mode="Markdown"
    )

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    status = get_bot_status()
    return jsonify({
        "status": "online",
        "bot": "Premium Number Hunter",
        "brand": BRAND,
        "bot_active": status['active'],
        "maintenance": status['maintenance'],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== START BOT ====================
def run_bot():
    print("🚀 Premium Number Hunter Bot is starting...")
    print(f"👑 Created by {BRAND}")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"💰 Free Credits: {FREE_CREDITS}")
    print(f"🔥 Referral Bonus: {REFERRALS_NEEDED} referrals = +{REFERRAL_BONUS} credits")
    print("📊 Status: Online")
    print("=" * 30)
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ Bot crashed: {e}")
            time.sleep(5)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
