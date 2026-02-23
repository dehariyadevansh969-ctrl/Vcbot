import telebot
import requests
import json
import time
import sqlite3
import os
import threading
from flask import Flask, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8293717672:AAHcFODkqpQsOAdlJe2gueHSU0YEvH4eNXw")

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

# ===== OWNER & ADMIN CONFIG - FIXED =====
OWNER_ID = 8066199853  # Aapka ID
ADMIN_USERNAME = "@Crownbattlesupport"

# ==================== DATABASE SETUP ====================
# Render free ke liye /tmp use karo
db_path = '/tmp/users.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              username TEXT,
              first_used TEXT,
              verified INTEGER DEFAULT 0,
              verified_date TEXT,
              is_admin INTEGER DEFAULT 0,
              is_owner INTEGER DEFAULT 0)''')

# Commands count table
c.execute('''CREATE TABLE IF NOT EXISTS command_usage
             (user_id INTEGER,
              command TEXT,
              used_count INTEGER DEFAULT 0,
              last_used TEXT,
              total_commands INTEGER DEFAULT 0,
              PRIMARY KEY (user_id, command))''')

# Referrals table
c.execute('''CREATE TABLE IF NOT EXISTS referrals
             (referrer_id INTEGER,
              referred_id INTEGER,
              referred_date TEXT,
              PRIMARY KEY (referrer_id, referred_id))''')

# User limits table
c.execute('''CREATE TABLE IF NOT EXISTS user_limits
             (user_id INTEGER PRIMARY KEY,
              commands_used INTEGER DEFAULT 0,
              max_commands INTEGER DEFAULT 3,
              referrals_count INTEGER DEFAULT 0,
              last_reset TEXT)''')

conn.commit()

# ==================== OWNER/ADMIN FIX - YAHAN SE ====================

def ensure_owner_in_db():
    """Ensure owner is always in database with proper flags"""
    try:
        # Check if owner exists
        c.execute("SELECT * FROM users WHERE user_id = ?", (OWNER_ID,))
        owner = c.fetchone()
        
        if not owner:
            # Owner nahi hai to add karo
            c.execute("INSERT INTO users (user_id, is_owner, is_admin, verified) VALUES (?, 1, 1, 1)", (OWNER_ID,))
            print(f"✅ Owner {OWNER_ID} added to database")
        else:
            # Owner hai to flags sahi karo
            c.execute("UPDATE users SET is_owner = 1, is_admin = 1 WHERE user_id = ?", (OWNER_ID,))
            print(f"✅ Owner {OWNER_ID} flags updated")
        
        # Check owner limits
        c.execute("SELECT * FROM user_limits WHERE user_id = ?", (OWNER_ID,))
        limit = c.fetchone()
        
        if not limit:
            c.execute("INSERT INTO user_limits (user_id, commands_used, max_commands, referrals_count) VALUES (?, 0, 999999, 0)", (OWNER_ID,))
            print(f"✅ Owner {OWNER_ID} unlimited limit set")
        else:
            c.execute("UPDATE user_limits SET max_commands = 999999 WHERE user_id = ?", (OWNER_ID,))
            print(f"✅ Owner {OWNER_ID} limit updated to unlimited")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Error ensuring owner: {e}")

# Bot start pe owner ko ensure karo
ensure_owner_in_db()

def is_admin_user(user_id):
    """Check if user is admin or owner - FIXED VERSION"""
    # Owner ko hamesha admin maano
    if user_id == OWNER_ID:
        return True
    
    # Database se check karo
    try:
        c.execute("SELECT is_owner, is_admin FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if user:
            return user[0] == 1 or user[1] == 1
        return False
    except:
        return False

def get_user_limit(user_id):
    """Get user's command limit - FIXED FOR OWNER"""
    # Owner ke liye unlimited
    if user_id == OWNER_ID:
        return {
            'used': 0,
            'max': 999999,
            'referrals': 0,
            'remaining': 999999,
            'is_admin': True
        }
    
    # Admin check
    if is_admin_user(user_id):
        return {
            'used': 0,
            'max': 999999,
            'referrals': 0,
            'remaining': 999999,
            'is_admin': True
        }
    
    # Normal users ke liye
    try:
        c.execute("SELECT commands_used, max_commands, referrals_count FROM user_limits WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        
        if result:
            return {
                'used': result[0],
                'max': result[1],
                'referrals': result[2],
                'remaining': result[1] - result[0],
                'is_admin': False
            }
        else:
            # New user
            c.execute("INSERT INTO user_limits (user_id, commands_used, max_commands, referrals_count, last_reset) VALUES (?, ?, ?, ?, ?)",
                     (user_id, 0, 3, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            return {'used': 0, 'max': 3, 'referrals': 0, 'remaining': 3, 'is_admin': False}
    except Exception as e:
        print(f"Error in get_user_limit: {e}")
        return {'used': 0, 'max': 3, 'referrals': 0, 'remaining': 3, 'is_admin': False}

def increment_command_usage(user_id):
    """Increment command usage count - SKIP FOR OWNER/ADMIN"""
    # Owner/admin ke liye count mat karo
    if user_id == OWNER_ID or is_admin_user(user_id):
        return
    
    try:
        c.execute("UPDATE user_limits SET commands_used = commands_used + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception as e:
        print(f"Error incrementing usage: {e}")

def can_use_command(user_id):
    """Check if user can use command"""
    limit = get_user_limit(user_id)
    return limit['remaining'] > 0

# Admin commands ke liye extra check
def is_owner(user_id):
    """Check if user is owner"""
    return user_id == OWNER_ID

# ==================== API COMMANDS LIST ====================
API_COMMANDS = {
    'num': '📱 Phone Lookup',
    'aadhar': '🆔 Aadhar Info',
    'vehicle': '🚗 Vehicle Details',
    'ip': '🌐 IP Geolocation',
    'insta': '📸 Instagram Profile',
    'pan': '💳 PAN Card',
    'ifsc': '🏦 IFSC Code',
    'ffuid': '🎮 Free Fire UID',
    'mail': '📧 Email Lookup',
    'rto': '🚦 RTO Info'
}

# ==================== MESSAGES ====================
INTRODUCTION = f"""
╔══════════════════════════════╗
║     🌀 TATSUMAKI PROFILE 🌀   ║
╠══════════════════════════════╣
║     ❤️【 BOT INFO 】❤️         ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ⚡ Name    : Tatsumaki Bot   ║
║   👑 Creator : {BRAND}        ║
║   💚 Power  : Multi-API       ║
║   🌪️ Type   : Info Bot        ║
║   ⭐ Version: 3.0             ║
║                               ║
║     ❤️【 ABOUT 】❤️            ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   📱 10+ APIs Available       ║
║   👤 Profile System          ║
║   🔄 Refer & Earn            ║
║   👑 Admin Panel             ║
╚══════════════════════════════╝
"""

WELCOME_MSG = f"""
╔══════════════════════════════╗
║     🌀 TATSUMAKI WELCOME 🌀   ║
╠══════════════════════════════╣
║   ✨ Welcome to the Family!   ║
║   {BRAND}                    ║
╠══════════════════════════════╣
║     ⚡ AVAILABLE COMMANDS ⚡   ║
╠══════════════════════════════╣
║   /help - All Commands       ║
║   /profile - Your Profile    ║
║   /share - Referral Link     ║
║   /owner - Contact Owner     ║
║                               ║
║   💡 FREE: 3 Commands         ║
║   🔄 Share to get more!       ║
╚══════════════════════════════╝
"""

HELP_MSG = f"""
╔══════════════════════════════╗
║     🌀 AVAILABLE COMMANDS 🌀  ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   🔹 BASIC COMMANDS:         ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   /start - Start Bot         ║
║   /help - This Menu          ║
║   /profile - Your Stats      ║
║   /share - Get Referral      ║
║   /owner - Contact Owner     ║
╠══════════════════════════════╣
║   🔹 API COMMANDS:           ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
"""

for cmd, desc in API_COMMANDS.items():
    HELP_MSG += f"║   /{cmd} [value] - {desc}\n"

HELP_MSG += """
╠══════════════════════════════╣
║   💡 Examples:               ║
║   /num 9876543210            ║
║   /insta virat.kohli         ║
║   /ip 8.8.8.8               ║
║   /vehicle MH01AB1234        ║
╚══════════════════════════════╝
"""

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
    try:
        c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        return result and result[0] == 1
    except:
        return False

def mark_user_verified(user_id):
    try:
        c.execute("INSERT OR REPLACE INTO users (user_id, verified, verified_date) VALUES (?, ?, ?)",
                 (user_id, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except:
        pass

# ==================== API FETCH ====================
def fetch_data(endpoint, query):
    try:
        url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&num={query}"
        print(f"Fetching: {url}")
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Add brand
        if isinstance(data, dict):
            data['brand'] = BRAND
            data['creator'] = CREATOR
        
        formatted_data = json.dumps(data, indent=2, ensure_ascii=False)
        return f"**{BRAND}**\n\n```json\n{formatted_data}\n```"
        
    except Exception as e:
        error_data = {
            "brand": BRAND,
            "creator": CREATOR,
            "status": "error",
            "message": str(e)
        }
        return f"**{BRAND}**\n\n```json\n{json.dumps(error_data, indent=2)}\n```"

# ==================== ADMIN FUNCTIONS ====================
def add_admin(user_id):
    try:
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False

def remove_admin(user_id):
    if user_id != OWNER_ID:  # Owner ko nahi hata sakte
        try:
            c.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
        except:
            return False
    return False

def set_user_limit(user_id, new_limit):
    try:
        c.execute("UPDATE user_limits SET max_commands = ?, commands_used = 0 WHERE user_id = ?", (new_limit, user_id))
        conn.commit()
        return True
    except:
        return False

# ==================== START COMMAND ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Ensure owner in DB on every start
    ensure_owner_in_db()
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user_id:
                # Add referral logic here
                try:
                    bot.send_message(referrer_id, f"🎉 **New Referral!**\n\nSomeone joined using your link!\n{BRAND}", parse_mode="Markdown")
                except:
                    pass
        except:
            pass
    
    # Check if already verified
    if is_user_verified(user_id):
        bot.send_video(
            chat_id,
            WELCOME_VIDEO,
            caption=WELCOME_MSG,
            parse_mode="Markdown",
            supports_streaming=True
        )
        return
    
    # Step 1: Image with caption
    try:
        bot.send_photo(
            chat_id, 
            START_IMAGE, 
            caption=INTRODUCTION,
            parse_mode="Markdown"
        )
    except:
        bot.send_message(chat_id, INTRODUCTION, parse_mode="Markdown")
    
    # Step 2: Membership button
    markup = InlineKeyboardMarkup(row_width=2)
    btn1 = InlineKeyboardButton("📢 Join Group", url=GROUP_LINK)
    btn2 = InlineKeyboardButton("📣 Join Channel", url=CHANNEL_LINK)
    btn3 = InlineKeyboardButton("✅ Verify Membership", callback_data="verify")
    markup.add(btn1, btn2)
    markup.add(btn3)
    
    bot.send_message(
        chat_id,
        "**🔒 Membership Required!**\n\nPlease join our Group & Channel first, then click Verify:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ==================== VERIFY ====================
@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if check_membership(user_id):
        mark_user_verified(user_id)
        get_user_limit(user_id)
        bot.delete_message(chat_id, call.message.message_id)
        
        bot.send_video(
            chat_id, 
            WELCOME_VIDEO,
            caption=WELCOME_MSG,
            parse_mode="Markdown",
            supports_streaming=True
        )
        
        bot.answer_callback_query(call.id, "✅ Verification Successful! Welcome!")
    else:
        bot.answer_callback_query(
            call.id,
            "❌ You haven't joined yet! Please join Group & Channel first.",
            show_alert=True
        )

# ==================== HELP COMMAND ====================
@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, HELP_MSG, parse_mode="Markdown")

# ==================== OWNER COMMAND ====================
@bot.message_handler(commands=['owner'])
def owner_command(message):
    chat_id = message.chat.id
    
    markup = InlineKeyboardMarkup()
    btn = InlineKeyboardButton("📩 Message Owner", url=f"tg://user?id={OWNER_ID}")
    markup.add(btn)
    
    msg = f"""
╔══════════════════════════════╗
║     👑 BOT OWNER 👑          ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   Owner ID: {OWNER_ID}       ║
║   Admin: {ADMIN_USERNAME}    ║
╠══════════════════════════════╣
║   Click below to contact     ║
║   owner directly!            ║
╚══════════════════════════════╝
"""
    bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)

# ==================== PROFILE COMMAND ====================
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username or "N/A"
    
    limit = get_user_limit(user_id)
    is_admin = is_admin_user(user_id)
    
    # Get referral count
    try:
        c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        referral_count = c.fetchone()[0]
    except:
        referral_count = 0
    
    # Get total commands used
    try:
        c.execute("SELECT SUM(used_count) FROM command_usage WHERE user_id = ?", (user_id,))
        total_cmds = c.fetchone()[0] or 0
    except:
        total_cmds = 0
    
    profile_msg = f"""
╔══════════════════════════════╗
║     🌀 USER PROFILE 🌀        ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   👤 Name: {first_name}      ║
║   🆔 ID: {user_id}           ║
║   📛 Username: @{username}   ║
╠══════════════════════════════╣
║   📊 STATISTICS:             ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   👑 Admin: {'✅' if is_admin else '❌'}          ║
║   📱 Commands: {total_cmds}  ║
║   👥 Referrals: {referral_count}    ║
╠══════════════════════════════╣
║   ⚡ LIMIT STATUS:            ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ✅ Used: {limit['used']}/{limit['max']}        ║
║   💡 Remaining: {limit['remaining']}             ║
╠══════════════════════════════╣
║   🔗 Referral Link:          ║
║   /share to get your link    ║
╚══════════════════════════════╝
"""
    
    bot.send_message(message.chat.id, profile_msg, parse_mode="Markdown")

# ==================== SHARE COMMAND ====================
@bot.message_handler(commands=['share'])
def share_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    limit = get_user_limit(user_id)
    
    share_msg = f"""
╔══════════════════════════════╗
║     🌀 SHARE & EARN 🌀        ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   📊 Your Stats:             ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   ✅ Used: {limit['used']}/{limit['max']}         ║
║   👥 Referrals: {limit['referrals']}              ║
║   💡 Remaining: {limit['remaining']}               ║
╠══════════════════════════════╣
║   🔥 How it works:           ║
║   • 3 friends refer =        ║
║   • +3 extra commands!       ║
║   • Unlimited times!         ║
╠══════════════════════════════╣
║   🔗 Your Referral Link:     ║
║   `{referral_link}`          ║
╚══════════════════════════════╝
"""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 Share Now", switch_inline_query=f"Join {BRAND} Bot! {referral_link}"))
    
    bot.send_message(chat_id, share_msg, parse_mode="Markdown", reply_markup=markup)

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    user_id = message.from_user.id
    
    # Only owner can add admin
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Only owner can use this command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /addadmin [user_id]")
        return
    
    try:
        new_admin_id = int(args[1])
        if add_admin(new_admin_id):
            bot.reply_to(message, f"✅ User `{new_admin_id}` is now admin!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Failed to add admin!")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_command(message):
    user_id = message.from_user.id
    
    # Only owner can remove admin
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Only owner can use this command!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: /removeadmin [user_id]")
        return
    
    try:
        remove_id = int(args[1])
        if remove_admin(remove_id):
            bot.reply_to(message, f"✅ User `{remove_id}` is no longer admin!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Failed to remove admin (cannot remove owner?)")
    except:
        bot.reply_to(message, "❌ Invalid user ID!")

@bot.message_handler(commands=['setlimit'])
def set_limit_command(message):
    user_id = message.from_user.id
    
    # Only admin/owner can set limits
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: /setlimit [user_id] [new_limit]")
        return
    
    try:
        target_id = int(args[1])
        new_limit = int(args[2])
        if set_user_limit(target_id, new_limit):
            bot.reply_to(message, f"✅ User `{target_id}` limit set to {new_limit}!", parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ Failed to set limit!")
    except:
        bot.reply_to(message, "❌ Invalid input!")

@bot.message_handler(commands=['adminslist'])
def admins_list(message):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ Admin only command!")
        return
    
    try:
        c.execute("SELECT user_id, is_owner FROM users WHERE is_admin = 1 OR is_owner = 1")
        admins = c.fetchall()
        
        msg = f"**👑 Admin List**\n\n{BRAND}\n\n"
        for admin_id, is_owner in admins:
            role = "👑 OWNER" if is_owner else "👥 ADMIN"
            msg += f"{role}: `{admin_id}`\n"
        
        bot.reply_to(message, msg, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Error fetching admin list!")

# ==================== COMMAND HANDLER ====================
@bot.message_handler(commands=list(API_COMMANDS.keys()))
def handle_commands(message):
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
    
    # Check command limit (skip for admin/owner)
    if not can_use_command(user_id):
        limit = get_user_limit(user_id)
        bot.reply_to(
            message,
            f"❌ **Limit Reached!**\n\nYou've used {limit['used']}/{limit['max']} commands.\n\nShare with 3 friends to get +3 more commands!\n\n/share - Get your referral link",
            parse_mode="Markdown"
        )
        return
    
    # Parse command
    parts = message.text.split()
    cmd = parts[0][1:]
    args = parts[1] if len(parts) > 1 else None
    
    if not args:
        bot.reply_to(
            message,
            f"❌ Please provide a value.\n\nExample: `/{cmd} [value]`",
            parse_mode="Markdown"
        )
        return
    
    bot.send_chat_action(chat_id, 'typing')
    
    # Fetch data
    result = fetch_data(cmd, args)
    
    # Increment usage (skip for admin/owner)
    increment_command_usage(user_id)
    
    # Get updated limit
    new_limit = get_user_limit(user_id)
    limit_info = "" if is_admin_user(user_id) else f"\n\n📊 **Remaining:** {new_limit['remaining']}/{new_limit['max']}"
    
    # Send INFO VIDEO + RESULT
    try:
        bot.send_video(
            chat_id,
            INFO_VIDEO,
            caption=result + limit_info,
            parse_mode="Markdown",
            supports_streaming=True
        )
    except:
        bot.send_message(chat_id, result + limit_info, parse_mode="Markdown")

# ==================== ERROR HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    bot.reply_to(
        message,
        f"❌ **Invalid Command!**\n\nUse /help to see available commands.\n\n{BRAND}",
        parse_mode="Markdown"
    )

# ==================== FLASK APP FOR KEEP ALIVE ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Tatsumaki Bot",
        "brand": BRAND,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== START BOT FUNCTION ====================
def run_bot():
    print("🚀 Tatsumaki Bot is starting...")
    print(f"👑 Created by {BRAND}")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"👑 Admin: {ADMIN_USERNAME}")
    print("📊 Status: Online")
    print("✅ Database connected")
    print("✅ 10+ APIs Active")
    print("=" * 30)
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ Bot crashed: {e}")
            time.sleep(5)
            print("🔄 Restarting bot...")

# ==================== MAIN ====================
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
