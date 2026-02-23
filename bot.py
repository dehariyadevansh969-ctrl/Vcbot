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
API_TOKEN = os.environ.get('API_TOKEN', "e7bb86fade6290a73ae6bb35a85f3725")
API_BASE_URL = "https://shivam-ultra-api.onrender.com/api"
API_KEY = "SHIVAM-786"

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

# ==================== DATABASE SETUP ====================
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

# Users table
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              username TEXT,
              first_used TEXT,
              verified INTEGER DEFAULT 0,
              verified_date TEXT)''')

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

# ==================== DATABASE FUNCTIONS ====================
def get_user_limit(user_id):
    """Get user's command limit"""
    c.execute("SELECT commands_used, max_commands, referrals_count FROM user_limits WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result:
        return {
            'used': result[0],
            'max': result[1],
            'referrals': result[2],
            'remaining': result[1] - result[0]
        }
    else:
        # New user
        c.execute("INSERT INTO user_limits (user_id, commands_used, max_commands, referrals_count, last_reset) VALUES (?, ?, ?, ?, ?)",
                 (user_id, 0, 3, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return {'used': 0, 'max': 3, 'referrals': 0, 'remaining': 3}

def increment_command_usage(user_id):
    """Increment command usage count"""
    c.execute("UPDATE user_limits SET commands_used = commands_used + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def add_referral(referrer_id, referred_id):
    """Add a referral"""
    # Check if already referred
    c.execute("SELECT * FROM referrals WHERE referrer_id = ? AND referred_id = ?", (referrer_id, referred_id))
    if c.fetchone():
        return False
    
    # Add referral
    c.execute("INSERT INTO referrals VALUES (?, ?, ?)",
             (referrer_id, referred_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # Update referrals count
    c.execute("UPDATE user_limits SET referrals_count = referrals_count + 1 WHERE user_id = ?", (referrer_id,))
    
    # Check if reached 3 referrals
    c.execute("SELECT referrals_count FROM user_limits WHERE user_id = ?", (referrer_id,))
    count = c.fetchone()[0]
    
    if count % 3 == 0:  # Har 3 referrals par limit badhao
        c.execute("UPDATE user_limits SET max_commands = max_commands + 3, commands_used = 0 WHERE user_id = ?", (referrer_id,))
        conn.commit()
        return True  # Limit increased
    else:
        conn.commit()
        return False  # Just referral added

def can_use_command(user_id):
    """Check if user can use command"""
    limit = get_user_limit(user_id)
    return limit['remaining'] > 0

# ==================== MESSAGES WITH BRAND ====================
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
║   ⭐ Version: 2.0             ║
║                               ║
║     ❤️【 ABOUT 】❤️            ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   📱 Number Info              ║
║   📸 Instagram Info           ║
║   🚗 RTO Details              ║
║   🎮 Free Fire ID Info        ║
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
║   📱 /num [number]            ║
║   📸 /insta [username]        ║
║   🚗 /rto [vehicle_number]    ║
║   🎮 /ff [freefire_uid]       ║
║                               ║
║   💡 FREE: 3 Commands         ║
║   🔄 Share to get more!       ║
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
    c.execute("SELECT verified FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    return result and result[0] == 1

def mark_user_verified(user_id):
    c.execute("INSERT OR REPLACE INTO users (user_id, verified, verified_date) VALUES (?, ?, ?)",
             (user_id, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

# ==================== API FETCH WITH BRAND FILTER ====================
def filter_brand(data):
    """Recursively replace SHIVAM with BRAND in JSON"""
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            # Replace in keys
            new_key = key
            if isinstance(key, str):
                new_key = key.replace("SHIVAM", "DEV").replace("Shivam", "Dev").replace("shivam", "dev")
            
            # Replace in values
            if isinstance(value, str):
                new_value = value.replace("SHIVAM", BRAND).replace("Shivam", "Dev").replace("shivam", "dev")
                new_dict[new_key] = new_value
            elif isinstance(value, (dict, list)):
                new_dict[new_key] = filter_brand(value)
            else:
                new_dict[new_key] = value
        
        # Add brand info at top level
        if "brand" not in new_dict:
            new_dict["brand"] = BRAND
        if "creator" not in new_dict:
            new_dict["creator"] = CREATOR
        if "powered_by" not in new_dict:
            new_dict["powered_by"] = "Tatsumaki Bot"
        
        return new_dict
    
    elif isinstance(data, list):
        return [filter_brand(item) for item in data]
    
    elif isinstance(data, str):
        return data.replace("SHIVAM", BRAND).replace("Shivam", "Dev").replace("shivam", "dev")
    
    else:
        return data

def fetch_data(endpoint, query):
    try:
        url = f"{API_BASE_URL}/{endpoint}?key={API_KEY}&num={query}"
        print(f"Fetching: {url}")
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        # Apply brand filter
        filtered_data = filter_brand(data)
        
        # Convert to pretty JSON
        formatted_data = json.dumps(filtered_data, indent=2, ensure_ascii=False)
        
        # Return with brand header
        return f"**{BRAND}**\n\n```json\n{formatted_data}\n```"
        
    except Exception as e:
        error_data = {
            "brand": BRAND,
            "creator": CREATOR,
            "status": "error",
            "message": str(e)
        }
        return f"**{BRAND}**\n\n```json\n{json.dumps(error_data, indent=2)}\n```"

# ==================== START COMMAND ====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check for referral
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1].replace('ref_', ''))
            if referrer_id != user_id:  # Self referral not allowed
                add_referral(referrer_id, user_id)
                try:
                    bot.send_message(referrer_id, f"🎉 **New Referral!**\n\nSomeone joined using your link!\n{BRAND}", parse_mode="Markdown")
                except:
                    pass
        except:
            pass
    
    # Check if already verified
    if is_user_verified(user_id):
        # Already verified, direct welcome
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
        # Save to database
        mark_user_verified(user_id)
        
        # Initialize user limits
        get_user_limit(user_id)
        
        # Delete verify message
        bot.delete_message(chat_id, call.message.message_id)
        
        # Send WELCOME VIDEO + WELCOME MSG TOGETHER
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

# ==================== SHARE COMMAND ====================
@bot.message_handler(commands=['share'])
def share_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Generate referral link
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
║   ✅ Commands Used: {limit['used']}/{limit['max']}  ║
║   👥 Referrals: {limit['referrals']}               ║
║   💡 Remaining: {limit['remaining']}                ║
╠══════════════════════════════╣
║   🔥 How it works:            ║
║   ━━━━━━━━━━━━━━━━━━━━━       ║
║   • 3 friends refer =         ║
║   • +3 extra commands!        ║
║   • Unlimited times!          ║
╠══════════════════════════════╣
║   🔗 Your Referral Link:      ║
║   `{referral_link}`          ║
╠══════════════════════════════╣
║   📤 Share this link to       ║
║   your friends & get more!    ║
╚══════════════════════════════╝
"""
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 Share Now", switch_inline_query=f"Join {BRAND} Bot! {referral_link}"))
    
    bot.send_message(chat_id, share_msg, parse_mode="Markdown", reply_markup=markup)

# ==================== MY LIMIT COMMAND ====================
@bot.message_handler(commands=['mylimit'])
def mylimit_command(message):
    user_id = message.from_user.id
    limit = get_user_limit(user_id)
    
    msg = f"""
╔══════════════════════════════╗
║     📊 YOUR LIMIT STATUS     ║
╠══════════════════════════════╣
║   {BRAND}                    ║
╠══════════════════════════════╣
║   ✅ Used: {limit['used']}/{limit['max']}           ║
║   👥 Referrals: {limit['referrals']}               ║
║   💡 Remaining: {limit['remaining']}                ║
╠══════════════════════════════╣
║   🔄 Share to get more!       ║
║   /share - Get your link      ║
╚══════════════════════════════╝
"""
    bot.reply_to(message, msg, parse_mode="Markdown")

# ==================== COMMAND HANDLER ====================
@bot.message_handler(commands=['num', 'insta', 'rto', 'ff'])
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
    
    # Check command limit
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
    
    # Show typing indicator
    bot.send_chat_action(chat_id, 'typing')
    
    # Map commands
    endpoint_map = {
        'num': 'numinfo',
        'insta': 'insta',
        'rto': 'rto',
        'ff': 'ffuid'
    }
    
    # Fetch data
    result = fetch_data(endpoint_map[cmd], args)
    
    # Increment command usage
    increment_command_usage(user_id)
    
    # Get updated limit
    new_limit = get_user_limit(user_id)
    
    # Add limit info to result
    limit_info = f"\n\n📊 **Remaining:** {new_limit['remaining']}/{new_limit['max']}"
    
    # Send INFO VIDEO + RESULT TOGETHER
    try:
        bot.send_video(
            chat_id,
            INFO_VIDEO,
            caption=result + limit_info,
            parse_mode="Markdown",
            supports_streaming=True
        )
    except Exception as e:
        bot.send_message(chat_id, result + limit_info, parse_mode="Markdown")

# ==================== ERROR HANDLER ====================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    bot.reply_to(
        message,
        f"❌ **Invalid Command!**\n\nUse /start to see available commands.\n\n{BRAND}",
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
    print("📊 Status: Online")
    print("✅ Database connected")
    print("✅ Limit System: 3 commands free")
    print("✅ Referral System: 3 shares = +3 commands")
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
    # Flask server alag thread mein chalao
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Bot chalao
    run_bot()
