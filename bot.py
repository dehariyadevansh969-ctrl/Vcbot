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

# ==================== CONFIGURATION ====================

# 🔑 BOT TOKEN
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8623049096:AAEOwMuKZMibgWBEeMisPgmM0-IFSTaA21w")

# 🖼️ START IMAGE
START_IMAGE = "https://drive.google.com/uc?export=download&id=1u8u0poNZAOlR8KFI-aCSwuP82AcXFmVM"

# 🤖 BOT NAME
BOT_NAME = "NIGHTMARE™"

# 👑 BRAND NAME
BRAND = "💠⃟I𝕯єν 🖤࿐"

# ==================== API CONFIGURATION ====================
API_BASE_URL = "https://shivam-ultra-api.onrender.com/api"
API_KEY = "SHIVAM-786"
API_TIMEOUT = 6  # ⏱️ 6 seconds timeout

# ==================== 3 CHANNELS CONFIG ====================
GROUP_LINK = "https://t.me/+3I9rJfeh5XVkZDM1"
GROUP_ID = -1003758601788
CHANNEL_LINK = "https://t.me/+1Jqq3-0RKpEyNTM1"
CHANNEL_ID = -1003791928633
CHANNEL3_LINK = "https://t.me/teeamend"
CHANNEL3_ID = -1003704625256

# ===== OWNER CONFIG =====
OWNER_ID = 8066199853

# ==================== API COMMANDS LIST ====================
API_COMMANDS = {
    'numinfo': {'name': '📱 Phone', 'desc': 'Phone number details', 'example': '9876543210'},
    'aadhar': {'name': '🆔 Aadhar', 'desc': 'Aadhar card details', 'example': '123456789012'},
    'insta': {'name': '📸 Instagram', 'desc': 'Instagram account info', 'example': 'virat.kohli'},
    'rto': {'name': '🚗 RTO', 'desc': 'Vehicle RTO details', 'example': 'MP09AB1234'},
    'ffuid': {'name': '🎮 Free Fire', 'desc': 'Free Fire UID details', 'example': '123456789'},
    'tg': {'name': '💬 Telegram', 'desc': 'Telegram account info', 'example': '6722541415'},
    'family': {'name': '👨‍👩‍👧 Family', 'desc': 'Family details', 'example': '30985035'}
}

# Temporary storage for user inputs
user_input_state = {}

# ==================== DATABASE SETUP ====================
current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
db_path = os.path.join(current_dir, 'bot_database.db')

conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()

# Users table with referral system
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    username TEXT, 
    verified INTEGER DEFAULT 0, 
    is_admin INTEGER DEFAULT 0, 
    is_owner INTEGER DEFAULT 0, 
    is_banned INTEGER DEFAULT 0,
    joined_date TEXT,
    total_commands INTEGER DEFAULT 0,
    referred_by INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0
)''')

# Banned users table
c.execute('''CREATE TABLE IF NOT EXISTS banned_users (
    user_id INTEGER PRIMARY KEY, 
    banned_by INTEGER, 
    ban_reason TEXT, 
    ban_date TEXT
)''')

# Bot settings table
c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
    setting_name TEXT PRIMARY KEY, 
    setting_value TEXT, 
    changed_by INTEGER, 
    changed_date TEXT
)''')

# Insert default settings
c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('bot_active', 'true', ?, ?)", (OWNER_ID, datetime.now()))
c.execute("INSERT OR IGNORE INTO bot_settings VALUES ('join_check', 'true', ?, ?)", (OWNER_ID, datetime.now()))
conn.commit()

# ==================== DATABASE FUNCTIONS ====================
def ensure_owner_in_db():
    c.execute("INSERT OR REPLACE INTO users (user_id, is_owner, is_admin, verified, joined_date) VALUES (?, 1, 1, 1, ?)",
              (OWNER_ID, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

ensure_owner_in_db()

def is_admin_user(user_id):
    if user_id == OWNER_ID:
        return True
    c.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def is_user_banned(user_id):
    c.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def get_setting(setting_name):
    c.execute("SELECT setting_value FROM bot_settings WHERE setting_name = ?", (setting_name,))
    result = c.fetchone()
    return result[0] if result else 'true'

def is_user_verified(user_id):
    c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def mark_user_verified(user_id):
    c.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def increment_user_commands(user_id):
    c.execute("UPDATE users SET total_commands = total_commands + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def add_referral(user_id, referrer_id):
    # Check if already referred
    c.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result and result[0] == 0:
        # Update referred_by
        c.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))
        # Increment referrer's referral count
        c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        return True
    return False

def get_user_stats(user_id):
    c.execute("SELECT verified, is_admin, is_owner, joined_date, total_commands, referrals, referred_by FROM users WHERE user_id = ?", (user_id,))
    return c.fetchone()

# ==================== BOT INIT ====================
bot = telebot.TeleBot(BOT_TOKEN)

# ==================== CHECK MEMBERSHIP ====================
def check_membership(user_id):
    if get_setting('join_check') == 'false':
        return True
    
    try:
        group_ok = bot.get_chat_member(GROUP_ID, user_id).status in ['member', 'administrator', 'creator']
        channel_ok = bot.get_chat_member(CHANNEL_ID, user_id).status in ['member', 'administrator', 'creator']
        channel3_ok = bot.get_chat_member(CHANNEL3_ID, user_id).status in ['member', 'administrator', 'creator']
        return group_ok and channel_ok and channel3_ok
    except:
        return False

def get_missing_channels(user_id):
    missing = []
    try:
        if not bot.get_chat_member(GROUP_ID, user_id).status in ['member', 'administrator', 'creator']:
            missing.append("📢 Group")
    except:
        missing.append("📢 Group")
    
    try:
        if not bot.get_chat_member(CHANNEL_ID, user_id).status in ['member', 'administrator', 'creator']:
            missing.append("📣 Channel 1")
    except:
        missing.append("📣 Channel 1")
    
    try:
        if not bot.get_chat_member(CHANNEL3_ID, user_id).status in ['member', 'administrator', 'creator']:
            missing.append("📢 Personal Channel")
    except:
        missing.append("📢 Personal Channel")
    
    return missing

# ==================== API FUNCTION - 6 SECOND TIMEOUT ====================
def fetch_api_data(endpoint, query):
    try:
        query = str(query).strip()
        
        # Handle different parameter names
        if endpoint in ['tg', 'family']:
            url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&id={query}"
        else:
            url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&num={query}"
        
        print(f"🌐 API Call: {url}")
        
        # ⏱️ 6 second timeout
        response = requests.get(url, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Check if data exists
                if data.get('success'):
                    if data.get('data'):
                        # Format the response
                        result_text = f"**{BRAND}**\n\n"
                        result_text += f"**📍 {API_COMMANDS[endpoint]['name']} Result**\n"
                        result_text += "━━━━━━━━━━━━━━━━\n\n"
                        
                        # Format data array
                        if isinstance(data['data'], list):
                            if len(data['data']) > 0:
                                for idx, item in enumerate(data['data'], 1):
                                    if item and isinstance(item, dict):
                                        result_text += f"**📊 Record {idx}**\n"
                                        for key, value in item.items():
                                            if value and value != "null":
                                                clean_key = key.replace('_', ' ').title()
                                                result_text += f"• **{clean_key}:** {value}\n"
                                        result_text += "━━━━━━━━━━━━━━━━\n"
                            else:
                                return f"**{BRAND}**\n\n❌ **No data found**"
                        else:
                            # Single item
                            if data['data']:
                                for key, value in data['data'].items():
                                    if value and value != "null":
                                        clean_key = key.replace('_', ' ').title()
                                        result_text += f"• **{clean_key}:** {value}\n"
                            else:
                                return f"**{BRAND}**\n\n❌ **No data found**"
                        
                        if data.get('time'):
                            result_text += f"\n⏱️ Time: {data['time']}"
                        
                        return result_text
                    else:
                        return f"**{BRAND}**\n\n❌ **No data found**"
                else:
                    return f"**{BRAND}**\n\n❌ **No data found**"
                    
            except Exception as e:
                return f"**{BRAND}**\n\n❌ **Error parsing data**"
        else:
            return f"**{BRAND}**\n\n❌ **Error {response.status_code}**"
            
    except requests.exceptions.Timeout:
        return f"**{BRAND}**\n\n❌ **Request timeout!**\nAPI took more than {API_TIMEOUT} seconds to respond."
    except requests.exceptions.ConnectionError:
        return f"**{BRAND}**\n\n❌ **Connection Error**\nCould not connect to API server."
    except Exception as e:
        return f"**{BRAND}**\n\n❌ **Error**\n{str(e)}"

# ==================== MESSAGE HANDLER - ONLY PRIVATE CHAT ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    # Agar group ya channel mein message hai to ignore karo
    if chat_type in ['group', 'supergroup', 'channel']:
        # Group/channel messages ko ignore karo - koi reply nahi
        print(f"📨 Ignored group message from {chat_id}")
        return
    
    # Yahan se sirf private messages handle honge
    user_id = message.from_user.id
    text = message.text.strip()
    
    print(f"📨 Private message from {user_id}: {text}")
    
    # Handle commands
    if text.startswith('/'):
        parts = text.split()
        cmd = parts[0][1:].lower()
        
        if cmd == 'start':
            send_welcome(message)
        elif cmd in API_COMMANDS:
            handle_api_command(message, cmd, parts)
        elif cmd == 'profile':
            show_profile_command(message)
        elif cmd == 'referral':
            show_referral_command(message)
        elif cmd == 'help':
            show_help_command(message)
        elif cmd == 'admins':
            show_admins_command(message)
        elif cmd in ['ban', 'unban', 'stats', 'broadcast']:
            handle_admin_commands(message, cmd)
        else:
            bot.reply_to(message, "❌ **Unknown command!** Use /start", parse_mode="Markdown")
    else:
        # Check if user is waiting for input
        if user_id in user_input_state and user_input_state[user_id].get('waiting'):
            handle_user_input(message)
        else:
            bot.reply_to(message, "❌ **Please use the buttons or commands!**\nUse /start to see the menu.", parse_mode="Markdown")

def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "User"
    
    # Check if banned
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.reply_to(message, "🚫 **You are banned!**", parse_mode="Markdown")
        return
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref'):
        try:
            referrer_id = int(args[1].replace('ref', ''))
            if referrer_id != user_id:
                add_referral(user_id, referrer_id)
        except:
            pass
    
    # Add user to database
    c.execute("INSERT OR IGNORE INTO users (user_id, joined_date) VALUES (?, ?)",
              (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    # Check if verified
    if is_user_verified(user_id):
        show_main_menu(chat_id, first_name)
        return
    
    # Show verification prompt
    verify_markup = InlineKeyboardMarkup(row_width=2)
    verify_markup.add(
        InlineKeyboardButton("📢 Group", url=GROUP_LINK),
        InlineKeyboardButton("📣 Channel 1", url=CHANNEL_LINK),
        InlineKeyboardButton("📢 Personal", url=CHANNEL3_LINK)
    )
    verify_markup.add(InlineKeyboardButton("✅ Verify Now", callback_data="verify_now"))
    
    try:
        bot.send_photo(
            chat_id,
            START_IMAGE,
            caption=f"**Hello {first_name}!**\n\n🔒 **3 Channels Required**\n\nPlease join ALL 3 channels below, then click Verify:",
            reply_markup=verify_markup,
            parse_mode="Markdown"
        )
    except:
        bot.send_message(
            chat_id,
            f"**Hello {first_name}!**\n\n🔒 **3 Channels Required**\n\nPlease join ALL 3 channels below, then click Verify:",
            reply_markup=verify_markup,
            parse_mode="Markdown"
        )

def show_main_menu(chat_id, first_name):
    """Show main menu after verification"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    # Add API command buttons
    buttons = []
    for cmd, info in API_COMMANDS.items():
        buttons.append(InlineKeyboardButton(info['name'], callback_data=f"cmd_{cmd}"))
    
    # Arrange in rows of 2
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            markup.row(buttons[i], buttons[i+1])
        else:
            markup.row(buttons[i])
    
    # Add utility buttons
    markup.row(
        InlineKeyboardButton("📚 Help", callback_data="help"),
        InlineKeyboardButton("👤 Profile", callback_data="profile")
    )
    markup.row(
        InlineKeyboardButton("👥 Referral", callback_data="referral"),
        InlineKeyboardButton("👑 Admins", callback_data="admins")
    )
    
    try:
        bot.send_photo(
            chat_id, 
            START_IMAGE,
            caption=f"**Welcome to {BOT_NAME}, {first_name}!**\n\nChoose an option below:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    except:
        bot.send_message(
            chat_id,
            f"**Welcome to {BOT_NAME}, {first_name}!**\n\nChoose an option below:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

def handle_api_command(message, cmd, parts):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if len(parts) < 2:
        info = API_COMMANDS[cmd]
        bot.reply_to(message, 
                    f"**{info['name']}**\n\n{info['desc']}\n\n📝 **Usage:** `/{cmd} {info['example']}`",
                    parse_mode="Markdown")
        return
    
    if not is_user_verified(user_id):
        if not check_membership(user_id):
            bot.reply_to(message, "❌ **Please verify first!** Use /start", parse_mode="Markdown")
            return
        else:
            mark_user_verified(user_id)
    
    query = parts[1]
    bot.send_chat_action(chat_id, 'typing')
    result = fetch_api_data(cmd, query)
    increment_user_commands(user_id)
    bot.reply_to(message, result, parse_mode="Markdown")

def show_profile_command(message):
    user_id = message.from_user.id
    stats = get_user_stats(user_id)
    
    if stats:
        verified, is_admin, is_owner, joined_date, total_commands, referrals, referred_by = stats
        role = "👑 OWNER" if is_owner else "👥 ADMIN" if is_admin else "👤 USER"
        
        profile_text = f"""
📊 **USER PROFILE**
━━━━━━━━━━━━━━━━
👤 **ID:** `{user_id}`
🏷️ **Role:** {role}
✅ **Verified:** {'Yes' if verified else 'No'}
📊 **Commands:** {total_commands}
👥 **Referrals:** {referrals}
📅 **Joined:** {joined_date[:10]}
"""
        bot.reply_to(message, profile_text, parse_mode="Markdown")

def show_referral_command(message):
    user_id = message.from_user.id
    bot_username = bot.get_me().username
    referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
    
    c.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    referrals = result[0] if result else 0
    
    ref_text = f"""
👥 **REFERRAL SYSTEM**
━━━━━━━━━━━━━━━━
**Your Referrals:** {referrals}

**Your Link:**
`{referral_link}`

Share this link with friends!
"""
    bot.reply_to(message, ref_text, parse_mode="Markdown")

def show_help_command(message):
    help_text = f"""
╔══════════════════════════════╗
║ 📚 **HELP MENU** 📚 ║
╠══════════════════════════════╣
║ **{BOT_NAME}** ║
╠══════════════════════════════╣
║ **AVAILABLE COMMANDS:** ║
"""
    for cmd, info in API_COMMANDS.items():
        help_text += f"║ /{cmd} - {info['name']}\n"
    
    help_text += f"""
╠══════════════════════════════╣
║ **UTILITY:** ║
║ /start - Main menu ║
║ /profile - Your stats ║
║ /referral - Get link ║
║ /admins - Contact team ║
╠══════════════════════════════╣
║ 👑 **{BRAND}** ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, help_text, parse_mode="Markdown")

def show_admins_command(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👑 Contact Owner", url=f"tg://user?id={OWNER_ID}"))
    
    msg_text = f"""
╔══════════════════════════════╗
║ 👑 **CONTACT TEAM** 👑 ║
╠══════════════════════════════╣
║ **{BOT_NAME}** ║
╠══════════════════════════════╣
║ **Owner ID:** `{OWNER_ID}` ║
╠══════════════════════════════╣
║ Click below to message ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, msg_text, parse_mode="Markdown", reply_markup=markup)

def handle_user_input(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    
    cmd = user_input_state[user_id]['cmd']
    del user_input_state[user_id]
    
    # Check verification
    if not is_user_verified(user_id):
        if not check_membership(user_id):
            bot.reply_to(message, "❌ **Please verify first!** Use /start", parse_mode="Markdown")
            return
        else:
            mark_user_verified(user_id)
    
    # Send typing action
    bot.send_chat_action(chat_id, 'typing')
    
    # Fetch and send data
    result = fetch_api_data(cmd, text)
    increment_user_commands(user_id)
    bot.reply_to(message, result, parse_mode="Markdown")
    
    # Show main menu
    first_name = message.from_user.first_name or "User"
    show_main_menu(chat_id, first_name)

def handle_admin_commands(message, cmd):
    user_id = message.from_user.id
    
    if not is_admin_user(user_id):
        bot.reply_to(message, "❌ **Admin only!**", parse_mode="Markdown")
        return
    
    if cmd == 'stats':
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE verified = 1")
        total_verified = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM banned_users")
        total_banned = c.fetchone()[0]
        c.execute("SELECT SUM(total_commands) FROM users")
        total_commands = c.fetchone()[0] or 0
        c.execute("SELECT SUM(referrals) FROM users")
        total_referrals = c.fetchone()[0] or 0
        
        msg_text = f"""
📊 **BOT STATISTICS**
━━━━━━━━━━━━━━━━
👥 **Total Users:** {total_users}
✅ **Verified:** {total_verified}
🔴 **Banned:** {total_banned}
📊 **Commands:** {total_commands}
👥 **Referrals:** {total_referrals}
"""
        bot.reply_to(message, msg_text, parse_mode="Markdown")
    
    elif cmd == 'broadcast':
        if user_id != OWNER_ID:
            bot.reply_to(message, "❌ **Only owner!**", parse_mode="Markdown")
            return
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "**Usage:** /broadcast [message]", parse_mode="Markdown")
            return
        broadcast_msg = args[1]
        c.execute("SELECT user_id FROM users WHERE is_banned = 0")
        users = c.fetchall()
        sent = 0
        for (uid,) in users:
            try:
                bot.send_message(uid, f"📢 **BROADCAST**\n\n{broadcast_msg}\n\n{BRAND}", parse_mode="Markdown")
                sent += 1
                time.sleep(0.05)
            except:
                continue
        bot.reply_to(message, f"✅ **Broadcast sent to {sent} users!**")

# ==================== CALLBACK HANDLER ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    # Sirf private chat ke callbacks handle karo
    if call.message.chat.type in ['group', 'supergroup', 'channel']:
        bot.answer_callback_query(call.id, "Please use bot in private chat!")
        return
    
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data
    
    print(f"📞 Callback: {data}")
    
    # Check if banned
    if is_user_banned(user_id) and user_id != OWNER_ID:
        bot.answer_callback_query(call.id, "🚫 You are banned!", show_alert=True)
        return
    
    # Handle verification
    if data == "verify_now":
        if check_membership(user_id):
            mark_user_verified(user_id)
            
            # Get user's first name
            first_name = call.from_user.first_name or "User"
            
            # Delete verification message
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            
            # Show main menu
            show_main_menu(chat_id, first_name)
            bot.answer_callback_query(call.id, "✅ Verified! Welcome!")
        else:
            missing = get_missing_channels(user_id)
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("📢 Group", url=GROUP_LINK),
                InlineKeyboardButton("📣 Channel 1", url=CHANNEL_LINK),
                InlineKeyboardButton("📢 Personal", url=CHANNEL3_LINK)
            )
            markup.add(InlineKeyboardButton("🔄 Try Again", callback_data="verify_now"))
            
            missing_text = "\n".join([f"❌ {ch}" for ch in missing])
            
            try:
                bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=f"❌ **Not a member!**\n\n**Missing:**\n{missing_text}",
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            except:
                pass
            
            bot.answer_callback_query(call.id, "❌ Not verified")
    
    # Handle command buttons
    elif data.startswith("cmd_"):
        if not is_user_verified(user_id):
            bot.answer_callback_query(call.id, "❌ Please verify first!", show_alert=True)
            return
        
        cmd = data.replace("cmd_", "")
        if cmd in API_COMMANDS:
            info = API_COMMANDS[cmd]
            user_input_state[user_id] = {'cmd': cmd, 'waiting': True}
            
            back_markup = InlineKeyboardMarkup()
            back_markup.add(InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main"))
            
            try:
                bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=f"**{info['name']}**\n\n{info['desc']}\n\n📝 **Example:** `{info['example']}`\n\nPlease send your input:",
                    parse_mode="Markdown",
                    reply_markup=back_markup
                )
            except:
                bot.send_message(
                    chat_id,
                    f"**{info['name']}**\n\n{info['desc']}\n\n📝 **Example:** `{info['example']}`\n\nPlease send your input:",
                    parse_mode="Markdown",
                    reply_markup=back_markup
                )
            
            bot.answer_callback_query(call.id, f"Selected: {info['name']}")
    
    # Handle back to main menu
    elif data == "back_main":
        if user_id in user_input_state:
            del user_input_state[user_id]
        
        # Delete current message
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
        
        # Show main menu
        first_name = call.from_user.first_name or "User"
        show_main_menu(chat_id, first_name)
        bot.answer_callback_query(call.id, "Main Menu")
    
    # Handle help
    elif data == "help":
        help_text = f"""
╔══════════════════════════════╗
║ 📚 **HELP MENU** 📚 ║
╠══════════════════════════════╣
║ **{BOT_NAME}** ║
╠══════════════════════════════╣
║ **AVAILABLE COMMANDS:** ║
"""
        for cmd, info in API_COMMANDS.items():
            help_text += f"║ /{cmd} - {info['name']}\n"
        
        help_text += f"""
╠══════════════════════════════╣
║ **UTILITY:** ║
║ /start - Main menu ║
║ /profile - Your stats ║
║ /referral - Get link ║
║ /admins - Contact team ║
╠══════════════════════════════╣
║ 👑 **{BRAND}** ║
╚══════════════════════════════╝
"""
        back_markup = InlineKeyboardMarkup()
        back_markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_main"))
        
        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=help_text,
                parse_mode="Markdown",
                reply_markup=back_markup
            )
        except:
            pass
        
        bot.answer_callback_query(call.id, "Help Menu")
    
    # Handle profile
    elif data == "profile":
        stats = get_user_stats(user_id)
        
        if stats:
            verified, is_admin, is_owner, joined_date, total_commands, referrals, referred_by = stats
            role = "👑 OWNER" if is_owner else "👥 ADMIN" if is_admin else "👤 USER"
            
            profile_text = f"""
╔══════════════════════════════╗
║ 📊 **USER PROFILE** 📊 ║
╠══════════════════════════════╣
║ **{BOT_NAME}** ║
╠══════════════════════════════╣
║ 👤 **ID:** `{user_id}` ║
║ 🏷️ **Role:** {role} ║
║ ✅ **Verified:** {'Yes' if verified else 'No'} ║
║ 📊 **Commands:** {total_commands} ║
║ 👥 **Referrals:** {referrals} ║
║ 📅 **Joined:** {joined_date[:10]} ║
╠══════════════════════════════╣
║ 👑 **{BRAND}** ║
╚══════════════════════════════╝
"""
            back_markup = InlineKeyboardMarkup()
            back_markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_main"))
            
            try:
                bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=profile_text,
                    parse_mode="Markdown",
                    reply_markup=back_markup
                )
            except:
                pass
        
        bot.answer_callback_query(call.id, "Your Profile")
    
    # Handle referral
    elif data == "referral":
        bot_username = bot.get_me().username
        referral_link = f"https://t.me/{bot_username}?start=ref{user_id}"
        
        c.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        referrals = result[0] if result else 0
        
        ref_text = f"""
╔══════════════════════════════╗
║ 👥 **REFERRAL SYSTEM** 👥 ║
╠══════════════════════════════╣
║ **{BOT_NAME}** ║
╠══════════════════════════════╣
║ **Your Referrals:** {referrals} ║
╠══════════════════════════════╣
║ **Your Link:** ║
║ `{referral_link}` ║
╠══════════════════════════════╣
║ Share this link with friends! ║
║ When they join, you'll get ║
║ referral credit. ║
╚══════════════════════════════╝
"""
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("📤 Share", switch_inline_query=f"Join {BOT_NAME} Bot! {referral_link}"),
            InlineKeyboardButton("🔙 Back", callback_data="back_main")
        )
        
        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=ref_text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except:
            pass
        
        bot.answer_callback_query(call.id, "Your Referral Link")
    
    # Handle admins
    elif data == "admins":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("👑 Contact Owner", url=f"tg://user?id={OWNER_ID}"),
            InlineKeyboardButton("🔙 Back", callback_data="back_main")
        )
        
        msg_text = f"""
╔══════════════════════════════╗
║ 👑 **CONTACT TEAM** 👑 ║
╠══════════════════════════════╣
║ **{BOT_NAME}** ║
╠══════════════════════════════╣
║ **Owner ID:** `{OWNER_ID}` ║
╠══════════════════════════════╣
║ Click below to message ║
╚══════════════════════════════╝
"""
        try:
            bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=msg_text,
                parse_mode="Markdown",
                reply_markup=markup
            )
        except:
            pass
        
        bot.answer_callback_query(call.id, "Contact Team")

# ==================== FLASK APP ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": BOT_NAME,
        "brand": BRAND,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ==================== START BOT ====================
def run_bot():
    print("🚀 Bot Starting...")
    print(f"🤖 Bot Name: {BOT_NAME}")
    print(f"👑 Brand: {BRAND}")
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"🌐 API URL: {API_BASE_URL}")
    print(f"📊 API Commands: {len(API_COMMANDS)}")
    print(f"⏱️ API Timeout: {API_TIMEOUT} seconds")
    print("📢 Bot will ONLY respond in private chat")
    print("=" * 30)
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
    
    print("✅ Bot is running!")
    
    while True:
        try:
            bot.infinity_polling(timeout=30, skip_pending=True)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    run_bot()
