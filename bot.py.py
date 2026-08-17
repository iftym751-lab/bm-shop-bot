import telebot
import requests
import threading
import json
import os
from flask import Flask, request

# আপনার বট টোকেন ও আইডি
TOKEN = "6643117201:AAGx5PBrsFdCmIRlk0uJ8fQ9cOW9edmJpek"
ADMIN_ID = 6204079163

bot = telebot.TeleBot(TOKEN)

# ক্লাউড ডাটাবেস
CLOUD_DB_ID = "a0f1e64fd12417de396d"
CLOUD_DB_URL = f"https://api.npoint.io/{CLOUD_DB_ID}"

db_lock = threading.Lock()
BM_PRICE = 100

# ============ Flask Web Server (২৪/৭ রান রাখার জন্য) ============
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ BM Shop Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
# =========================================================

def load_db():
    try:
        res = requests.get(CLOUD_DB_URL)
        if res.status_code == 200 and res.json():
            return res.json()
    except:
        pass
    return {"users": {}, "bms": []}

def save_db(data):
    try:
        requests.put(CLOUD_DB_URL, json=data)
    except:
        pass

# ============ ইউজার কমান্ড ============

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "N/A"
    
    with db_lock:
        data = load_db()
        if user_id not in data["users"]:
            data["users"][user_id] = {"username": username, "balance": 0}
            save_db(data)
    
    text = (
        f"👋 স্বাগতম {message.from_user.first_name}!\n\n"
        f"এখান থেকে আপনি ফেসবুক বি এম (BM) কিনতে পারবেন।\n"
        f"💰 বি এম এর দাম: {BM_PRICE} টাকা\n\n"
        f"👉 ব্যালেন্স চেক করতে: /balance\n"
        f"👉 বি এম কিনতে: /buy\n"
        f"👉 টাকা রিচার্জ করতে এডমিনের সাথে যোগাযোগ করুন।"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['balance'])
def check_balance(message):
    user_id = str(message.from_user.id)
    with db_lock:
        data = load_db()
        user = data["users"].get(user_id)
    
    if user:
        bot.reply_to(message, f"💰 আপনার বর্তমান ব্যালেন্স: {user['balance']} টাকা")
    else:
        bot.reply_to(message, "❌ আপনি এখনও রেজিস্টার্ড নন। /start দিন।")

@bot.message_handler(commands=['buy'])
def buy_bm(message):
    user_id = str(message.from_user.id)
    
    with db_lock:
        data = load_db()
        user = data["users"].get(user_id)
        
        if not user:
            bot.reply_to(message, "❌ আপনি রেজিস্টার্ড নন। /start দিন।")
            return
            
        if user["balance"] < BM_PRICE:
            bot.reply_to(message, f"❌ পর্যাপ্ত ব্যালেন্স নেই!\n💰 আপনার ব্যালেন্স: {user['balance']}\nদাম: {BM_PRICE}\n\nএডমিনের সাথে যোগাযোগ করে টাকা রিচার্জ করুন।")
            return
            
        available_bm = None
        for bm in data["bms"]:
            if bm["status"] == "available":
                available_bm = bm
                break
                
        if not available_bm:
            bot.reply_to(message, "😔 দুঃখিত! বর্তমানে স্টকে কোনো বি এম নেই। এডমিন স্টক আপডেট করা পর্যন্ত অপেক্ষা করুন।")
            return
            
        # টাকা কাটা এবং বি এম আপডেট
        user["balance"] -= BM_PRICE
        available_bm["status"] = "sold"
        available_bm["buyer_id"] = user_id
        
        save_db(data)
        bm_link = available_bm["link"]
        new_balance = user["balance"]
        
    bot.reply_to(message, f"✅ বি এম সফলভাবে কেনা হয়েছে!\n\n🔗 আপনার বি এম লিংক:\n{bm_link}\n\n💰 বর্তমান ব্যালেন্স: {new_balance}")
    bot.send_message(ADMIN_ID, f"🛒 নতুন বি এম বিক্রি হয়েছে!\n👤 ইউজার: {user_id}\n🔗 লিংক: {bm_link}")

# ============ এডমিন কমান্ড ============

@bot.message_handler(commands=['addbm'])
def add_bm(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    try:
        bm_link = message.text.split(' ', 1)[1]
        with db_lock:
            data = load_db()
            data["bms"].append({"link": bm_link, "status": "available", "buyer_id": None})
            save_db(data)
        
        bot.reply_to(message, "✅ নতুন বি এম স্টকে যুক্ত করা হয়েছে!")
    except IndexError:
        bot.reply_to(message, "⚠️ সঠিক ফরম্যাট: `/addbm <link>`", parse_mode="Markdown")

@bot.message_handler(commands=['addbalance'])
def add_balance(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    try:
        parts = message.text.split()
        user_id = str(parts[1])
        amount = int(parts[2])
        
        with db_lock:
            data = load_db()
            if user_id not in data["users"]:
                bot.reply_to(message, "❌ এই আইডির কোনো ইউজার খুঁজে পাওয়া যায়নি।")
                return
                
            data["users"][user_id]["balance"] += amount
            new_bal = data["users"][user_id]["balance"]
            save_db(data)
            
        bot.reply_to(message, f"✅ ব্যালেন্স যুক্ত হয়েছে!\n👤 ইউজার: {user_id}\n💰 যোগ হয়েছে: {amount}\n🆕 নতুন ব্যালেন্স: {new_bal}")
        bot.send_message(int(user_id), f"💰 আপনার ব্যালেন্স যুক্ত হয়েছে!\n🆕 বর্তমান ব্যালেন্স: {new_bal}")
    except (IndexError, ValueError):
        bot.reply_to(message, "⚠️ সঠিক ফরম্যাট: `/addbalance <user_id> <amount>`", parse_mode="Markdown")

@bot.message_handler(commands=['stock'])
def check_stock(message):
    if message.from_user.id != ADMIN_ID:
        return
        
    with db_lock:
        data = load_db()
        count = sum(1 for bm in data["bms"] if bm["status"] == "available")
        
    bot.reply_to(message, f"📦 বর্তমান স্টকে উপলব্ধ বি এম: {count} টি")

if __name__ == "__main__":
    # প্রথমে ফ্লাস্ক সার্ভার ব্যাকগ্রাউন্ডে চালু করবে
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # এরপর বট চালু করবে
    print("Cloud BM Shop Bot is running 24/7...")
    bot.infinity_polling()