import telebot
import requests
import json
import time
import sqlite3
import os
import threading
from flask import Flask, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import re

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

# BRAND
BRAND = "꧁💠⃟‌⃟ 𝕯єν꧂"
CREATOR = "Dev"

# ===== OWNER CONFIG =====
OWNER_ID = 8066199853

# ===== BOT CONFIG =====
FREE_CREDITS = 2
REFERRAL_BONUS = 2
REFERRALS_NEEDED = 5

# ==================== DATABASE SETUP ====================
db_path = '/tmp/bot_database.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              username TEXT,
              verified INTEGER DEFAULT 0,
              is_admin INTEGER DEFAULT 0,
              is_owner INTEGER DEFAULT 0,
              is_banned INTEGER DEFAULT 0,
              credits_used INTEGER DEFAULT 0,
              total_credits INTEGER DEFAULT 2,
              referrals_count INTEGER DEFAULT 0,
              batch_type TEXT DEFAULT 'free',
              joined_date TEXT)''')

# Referrals table
c.execute('''CREATE TABLE IF NOT EXISTS referrals
             (referrer_id INTEGER,
              referred_id INTEGER,
              referred_date TEXT,
              PRIMARY KEY (referrer_id, referred_id))''')

# Banned users table
c.execute('''CREATE TABLE IF NOT EXISTS banned_users
             (user_id INTEGER PRIMARY KEY,
              banned_by INTEGER,
              ban_reason TEXT,
              ban_date TEXT)''')

conn.commit()

# ==================== DATABASE FUNCTIONS ====================

def ensure_owner_in_db():
    c.execute("INSERT OR REPLACE INTO users (user_id, is_owner, is_admin, verified, total_credits, batch_type, joined_date) VALUES (?, 1, 1, 1, 999999, 'owner', ?)",
              (OWNER_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

ensure_owner_in_db()

def is_admin_user(user_id):
    if user_id == OWNER_ID:
        return True
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def is_owner_user(user_id):
    return user_id == OWNER_ID

def is_user_banned(user_id):
    c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

# ==================== BAN/UNBAN FUNCTIONS ====================

def ban_user(user_id, banned_by, reason="No reason"):
    c.execute("INSERT OR REPLACE INTO banned_users VALUES (?, ?, ?, ?)",
              (user_id, banned_by, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def unban_user(user_id):
    c.execute("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()

# ==================== ADMIN FUNCTIONS ====================

def add_admin(user_id):
    c.execute("UPDATE users SET is_admin = 1, batch_type = 'admin', total_credits = 999999 WHERE user_id = ?", (user_id,))
    conn.commit()

def remove_admin(user_id):
    if user_id != OWNER_ID:
        c.execute("UPDATE users SET is_admin = 0, batch_type = 'free', total_credits = ? WHERE user_id = ?", (FREE_CREDITS, user_id))
        conn.commit()

# ==================== USER CREDITS FUNCTIONS ====================

def get_user_credits(user_id):
    if is_user_banned(user_id):
        return {'used': 0, 'total': 0, 'left': 0, 'referrals': 0}
    
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
        c.execute("INSERT INTO users (user_id, total_credits, joined_date) VALUES (?, ?, ?)",
                 (user_id, FREE_CREDITS, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
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
    
    c.execute("INSERT INTO referrals VALUES (?, ?, ?)",
             (referrer_id, referred_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
    
    c.execute("SELECT referrals_count FROM users WHERE user_id = ?", (referrer_id,))
    count = c.fetchone()[0]
    
    if count % REFERRALS_NEEDED == 0:
        c.execute("UPDATE users SET total_credits = total_credits + ? WHERE user_id = ?", (REFERRAL_BONUS, referrer_id))
        conn.commit()
        return True
    else:
        conn.commit()
        return False

def set_user_credits(user_id, amount):
    c.execute("UPDATE users SET total_credits = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

# ==================== BOT INIT ====================
bot = telebot.TeleBot(BOT_TOKEN)

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

# ==================== API FUNCTION - FIXED ====================
def fetch_data(endpoint, query):
    start_time = time.time()
    try:
        url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&num={query}"
        print(f"Fetching: {url}")
        
        response = requests.get(url, timeout=15)
        data = response.json()
        
        # Calculate time taken
        elapsed = round(time.time() - start_time, 2)
        
        # Add brand
        final_data = {
            "brand": BRAND,
            "creator": CREATOR,
            "time": f"{elapsed}s",
            "success": True
        }
        
        # Handle different response formats
        if isinstance(data, dict):
            if 'data' in data:
                final_data['data'] = data['data']
            else:
                final_data['data'] = data
        elif isinstance(data, list):
            final_data['data'] = data
        else:
            final_data['data'] = {"result": data}
        
        # Format nicely
        formatted = json.dumps(final_data, indent=2, ensure_ascii=False)
        return f"**{BRAND}**\n\n```json\n{formatted}\n```"
        
    except requests.exceptions.Timeout:
        return f"**{BRAND}**\n\n❌ API Timeout! Server slow."
    except requests.exceptions.ConnectionError:
        return f"**{BRAND}**\n\n❌ Connection Error! API down."
    except Exception as e:
        return f"**{BRAND}**\n\n❌ Error: {str(e)}"

# ==================== API COMMANDS LIST ====================
API_COMMANDS = {
    'num': '📱 Phone Number Lookup',
    'insta': '📸 Instagram Profile Info',
    'rto': '🚗 RTO Vehicle Details',
    'ff': '🎮 Free Fire UID Info',
    'ip': '🌐 IP Address Geolocation',
    'pan': '💳 PAN Card Details',
    'ifsc': '🏦 IFSC Code Bank Info',
    'aadhar': '🆔 Aadhar Card Info',
    'vehicle': '🚘 Vehicle Registration Details',
    'mail': '📧 Email Address Lookup'
}

# ==================== MESSAGES ====================

HELP_MESSAGE = f"""
╔══════════════════════════════╗
║     🌀 HELP MENU 🌀          ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   📌 BASIC COMMANDS:         ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   /start - Start Bot         ║
║   /help - This Menu          ║
║   /profile - Your Stats      ║
║   /share - Referral Link     ║
║   /verify - Verify Member    ║
║   /admins - Contact Team     ║
╠══════════════════════════════╣
║   🔍 INFO COMMANDS:          ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
"""

for cmd, desc in API_COMMANDS.items():
    HELP_MESSAGE += f"║   /{cmd} [value] - {desc}\n"

HELP_MESSAGE += f"""
╠══════════════════════════════╣
║   💡 Examples:               ║
║   /num 9876543210           ║
║   /insta virat.kohli        ║
║   /aadhar 123456789012      ║
╠══════════════════════════════╣
║   ⚡ FREE: {FREE_CREDITS} Credits     ║
║   🔥 Refer {REFERRALS_NEEDED} = +{REFERRAL_BONUS} ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

WELCOME_CAPTION = f"""
╔══════════════════════════════╗
║     🌀 WELCOME TO BOT 🌀     ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   ✅ VERIFICATION SUCCESSFUL ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ✨ You can now use the bot! ║
║   ⚡ Free: {FREE_CREDITS} Credits    ║
║   📌 Use /help for commands   ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""

SEARCH_ANIMATIONS = [
    "🔍 Searching",
    "🔍 Searching.",
    "🔍 Searching..",
    "🔍 Searching..."
]

# ==================== START COMMAND ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 You are banned from using this bot!")
        return
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user_id:
                add_referral(referrer_id, user_id)
        except:
            pass
    
    # Step 1: Image bhejo
    try:
        bot.send_photo(chat_id, START_IMAGE, caption="🌀 **Tatsumaki Bot**", parse_mode="Markdown")
    except:
        bot.send_message(chat_id, "🌀 **Tatsumaki Bot**", parse_mode="Markdown")
    
    time.sleep(1)
    
    # Step 2: Check if already verified
    if is_user_verified(user_id):
        try:
            bot.send_video(chat_id, WELCOME_VIDEO, caption=WELCOME_CAPTION, parse_mode="Markdown", supports_streaming=True)
        except:
            bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
        return
    
    # Step 3: Membership button
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
        InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
    )
    markup.add(InlineKeyboardButton("✅ Verify Membership", callback_data="verify"))
    
    bot.send_message(
        chat_id,
        "**🔒 Membership Required!**\n\n1️⃣ Join Group & Channel\n2️⃣ Click Verify button",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==================== VERIFY CALLBACK ====================
@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.answer_callback_query(call.id, "❌ You are banned!", show_alert=True)
        return
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        
        try:
            bot.send_video(chat_id, WELCOME_VIDEO, caption=WELCOME_CAPTION, parse_mode="Markdown", supports_streaming=True)
        except:
            bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
        
        bot.answer_callback_query(call.id, "✅ Verified! Welcome!")
    else:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
            InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
        )
        markup.add(InlineKeyboardButton("✅ Try Again", callback_data="verify"))
        
        bot.send_message(
            chat_id,
            "❌ **Not a member!**\n\nPlease join both Group & Channel first.",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        
        bot.answer_callback_query(call.id, "❌ Not verified")

# ==================== HELP COMMAND ====================
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, HELP_MESSAGE, parse_mode="Markdown")

# ==================== PROFILE COMMAND ====================
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 You are banned!")
        return
    
    username = message.from_user.username or "unknown"
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    if next_bonus == REFERRALS_NEEDED:
        next_bonus = 0
    
    profile_msg = f"""
╔══════════════════════════════╗
║     📊 YOUR PROFILE         ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👤 ID: {user_id}           ║
║   📛 @{username}             ║
║   🏷️ Batch: {credits['batch'].upper()} ║
╠══════════════════════════════╣
║   💰 CREDITS:                ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   📊 Used: {credits['used']}/{credits['total']}  ║
║   💎 Left: {credits['left']}           ║
║                               ║
║   👥 Referrals: {credits['referrals']}   ║
║   🔥 Next Bonus: {next_bonus}          ║
╠══════════════════════════════╣
║   🔗 /share - Get Referral   ║
║   👑 {BRAND}                  ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, profile_msg, parse_mode="Markdown")

# ==================== SHARE COMMAND ====================
@bot.message_handler(commands=['share'])
def share_command(message):
    user_id = message.from_user.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 You are banned!")
        return
    
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    credits = get_user_credits(user_id)
    next_bonus = REFERRALS_NEEDED - (credits['referrals'] % REFERRALS_NEEDED)
    
    share_msg = f"""
╔══════════════════════════════╗
║     🔗 YOUR REFERRAL LINK   ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👥 Referrals: {credits['referrals']}   ║
║   🔥 Need {next_bonus} more    ║
║   ✨ +{REFERRAL_BONUS} Credits    ║
╠══════════════════════════════╣
║   `{referral_link}`          ║
╠══════════════════════════════╣
║   📤 Share with friends!     ║
╚══════════════════════════════╝
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 Share", switch_inline_query=f"Join Bot! {referral_link}"))
    
    bot.reply_to(message, share_msg, parse_mode="Markdown", reply_markup=markup)

# ==================== ADMINS COMMAND ====================
@bot.message_handler(commands=['admins'])
def admins_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Contact Owner", url=f"tg://user?id={OWNER_ID}"))
    
    msg = f"""
╔══════════════════════════════╗
║     👑 CONTACT TEAM 👑      ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   Owner ID: {OWNER_ID}       ║
╠══════════════════════════════╣
║   Click below to message     ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=markup)

# ==================== VERIFY COMMAND ====================
@bot.message_handler(commands=['verify'])
def verify_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 You are banned!")
        return
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        
        try:
            bot.send_video(chat_id, WELCOME_VIDEO, caption=WELCOME_CAPTION, parse_mode="Markdown", supports_streaming=True)
        except:
            bot.send_message(chat_id, WELCOME_CAPTION, parse_mode="Markdown")
    else:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
            InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
        )
        bot.reply_to(
            message,
            "❌ **Not a member!**\n\nPlease join Group & Channel first.",
            reply_markup=markup,
            parse_mode="Markdown"
        )

# ==================== INFO COMMANDS WITH SEARCH ANIMATION ====================
@bot.message_handler(commands=list(API_COMMANDS.keys()))
def info_commands(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 You are banned from using this bot!")
        return
    
    if not is_user_verified(user_id):
        if not check_membership(user_id):
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton("📢 Join Group", url=GROUP_LINK),
                InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
            )
            bot.reply_to(
                message,
                "❌ **Access Denied!**\n\nPlease join Group & Channel first.\nThen use /verify",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return
        else:
            mark_user_verified(user_id)
    
    if not use_credit(user_id):
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        bot.reply_to(
            message,
            f"❌ **No Credits Left!**\n\nShare with {REFERRALS_NEEDED} friends to get +{REFERRAL_BONUS} credits!\n\n/share\n\n{referral_link}",
            parse_mode="Markdown"
        )
        return
    
    cmd = message.text.split()[0][1:]
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if not args:
        bot.reply_to(message, f"❌ Usage: /{cmd} [value]\n\nExample: /{cmd} 9876543210")
        return
    
    # Send typing action
    bot.send_chat_action(chat_id, 'typing')
    
    # Send search animation
    search_msg = bot.reply_to(message, "🔍 **Searching**", parse_mode="Markdown")
    
    # Animate search (4 quick updates)
    for i in range(4):
        time.sleep(0.5)
        try:
            bot.edit_message_text(f"🔍 **Searching{'.' * (i+1)}**", chat_id, search_msg.message_id, parse_mode="Markdown")
        except:
            pass
    
    # Fetch data
    result = fetch_data(cmd, args)
    
    # Delete search message
    try:
        bot.delete_message(chat_id, search_msg.message_id)
    except:
        pass
    
    # Get credits
    credits = get_user_credits(user_id)
    
    # Send result with remaining credits
    final_msg = result + f"\n\n⚡ Remaining: {credits['left']}"
    bot.reply_to(message, final_msg, parse_mode="Markdown")

# ==================== ADMIN COMMANDS ====================

@bot.message_handler(commands=['ban'])
def ban_command(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /ban [user_id] [reason]")
        return
    
    try:
        target = int(args[1])
        reason = " ".join(args[2:]) if len(args) > 2 else "No reason"
        
        if target == OWNER_ID:
            bot.reply_to(message, "❌ Cannot ban owner!")
            return
        
        ban_user(target, message.from_user.id, reason)
        bot.reply_to(message, f"✅ User {target} banned!\nReason: {reason}")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['unban'])
def unban_command(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /unban [user_id]")
        return
    
    try:
        target = int(args[1])
        unban_user(target)
        bot.reply_to(message, f"✅ User {target} unbanned!")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /addadmin [user_id]")
        return
    
    try:
        target = int(args[1])
        if target == OWNER_ID:
            bot.reply_to(message, "❌ User is already owner!")
            return
        add_admin(target)
        bot.reply_to(message, f"✅ User {target} is now ADMIN!")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_command(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /removeadmin [user_id]")
        return
    
    try:
        target = int(args[1])
        if target == OWNER_ID:
            bot.reply_to(message, "❌ Cannot remove owner!")
            return
        remove_admin(target)
        bot.reply_to(message, f"✅ User {target} is no longer admin!")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

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
        set_user_credits(target, get_user_credits(target)['total'] + amount)
        bot.reply_to(message, f"✅ Added {amount} credits to user {target}!")
    except:
        bot.reply_to(message, "❌ Invalid input!")

@bot.message_handler(commands=['memberlist'])
def member_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    
    c.execute("SELECT user_id, batch_type, is_banned FROM users ORDER BY joined_date DESC LIMIT 20")
    members = c.fetchall()
    
    msg = f"📋 **MEMBER LIST** (Last 20)\nTotal Members: {total}\n\n"
    for user_id, batch, banned in members:
        emoji = "👑" if user_id == OWNER_ID else "🔥" if batch == 'admin' else "⭐" if batch == 'star' else "💎" if batch == 'premium' else "👤"
        ban_emoji = "🔴" if banned else "🟢"
        msg += f"{ban_emoji} {emoji} `{user_id}` - {batch}\n"
    
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['adminlist'])
def admin_list(message):
    if not is_admin_user(message.from_user.id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    c.execute("SELECT user_id FROM users WHERE is_admin = 1 OR is_owner = 1")
    admins = c.fetchall()
    
    msg = "👑 **ADMIN TEAM** 👑\n\n"
    markup = InlineKeyboardMarkup()
    
    for (user_id,) in admins:
        role = "👑 OWNER" if user_id == OWNER_ID else "👥 ADMIN"
        msg += f"{role}: `{user_id}`\n"
        if user_id != OWNER_ID:
            markup.add(InlineKeyboardButton(f"📩 Message {user_id}", url=f"tg://user?id={user_id}"))
    
    bot.reply_to(message, msg, parse_mode="Markdown", reply_markup=markup)

# ==================== OWNER ONLY COMMANDS ====================

@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this!")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "Usage: /broadcast [message]")
        return
    
    broadcast_msg = args[1]
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = c.fetchall()
    
    sent = 0
    for (user_id,) in users:
        try:
            bot.send_message(user_id, f"📢 **BROADCAST**\n\n{broadcast_msg}\n\n{BRAND}", parse_mode="Markdown")
            sent += 1
            time.sleep(0.05)
        except:
            continue
    
    bot.reply_to(message, f"✅ Broadcast sent to {sent} users!")

@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only owner can use this!")
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    total_admins = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM banned_users")
    total_banned = c.fetchone()[0]
    
    c.execute("SELECT SUM(credits_used) FROM users")
    total_commands = c.fetchone()[0] or 0
    
    msg = f"""
📊 **BOT STATISTICS**
━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
👑 Total Admins: {total_admins}
🔴 Banned Users: {total_banned}
📊 Commands Used: {total_commands}
"""
    bot.reply_to(message, msg, parse_mode="Markdown")

# ==================== ERROR HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    bot.reply_to(message, f"❌ Invalid Command!\n\nUse /help\n\n{BRAND}", parse_mode="Markdown")

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Tatsumaki",
        "brand": BRAND,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== START BOT ====================
def run_bot():
    print("🚀 Tatsumaki Bot starting...")
    print(f"👑 {BRAND}")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"📊 Total Commands: {len(API_COMMANDS)} APIs")
    print("=" * 30)
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
