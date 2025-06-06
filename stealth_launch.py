import os
import requests
import logging
from telegram import Bot, Update
from telegram.ext import CallbackContext
from time import time

logger = logging.getLogger(__name__)

# Track alerted tokens to avoid spam (token_symbol: last_alert_time)
_alerted_tokens = {}

# Cooldown period in seconds (e.g. 30 minutes)
ALERT_COOLDOWN_SECONDS = 1800

def fetch_new_tokens():
    url = "https://api.dexscreener.com/latest/dex/tokens?chain=solana"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        tokens = resp.json().get("tokens", [])
        return tokens
    except Exception as e:
        logger.error(f"[StealthLaunch] Failed fetching tokens: {e}")
        return []

def check_token_risk(token):
    lp = token.get("liquidity", 0)
    locked = token.get("locked", False)
    social_score = token.get("socialScore", 0)

    risk_flags = []
    if lp < 5000:
        risk_flags.append("Low LP")
    if not locked:
        risk_flags.append("No LP Lock")
    if social_score < 10:
        risk_flags.append("Low Social")

    return risk_flags

def should_alert(token_symbol):
    now = time()
    last_alert = _alerted_tokens.get(token_symbol)
    if last_alert and now - last_alert < ALERT_COOLDOWN_SECONDS:
        return False
    _alerted_tokens[token_symbol] = now
    return True

def scan_new_tokens(bot: Bot):
    chat_id = os.getenv("CHAT_ID")
    tokens = fetch_new_tokens()
    for token in tokens:
        symbol = token.get("symbol", "").upper()
        if not symbol:
            continue

        if not should_alert(symbol):
            continue

        risk_flags = check_token_risk(token)
        if risk_flags:
            lp = token.get("liquidity", 0)
            price = token.get("price", 0)
            url = token.get("url", "https://dexscreener.com")
            flags_text = ", ".join(risk_flags)

            msg = (
                f"🚨 <b>New Token Alert: ${symbol}</b>\n"
                f"Price: ${price:.6f}\n"
                f"Liquidity: ${lp:,.0f}\n"
                f"Risk Flags: {flags_text}\n"
                f"More info: {url}"
            )
            bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")

def handle_scannew_command(update: Update, context: CallbackContext):
    scan_new_tokens(context.bot)
    update.message.reply_text("Manual stealth launch scan triggered.")
