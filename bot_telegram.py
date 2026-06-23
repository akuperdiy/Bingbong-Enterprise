import sys
import asyncio
import nest_asyncio
import random
import os
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
nest_asyncio.apply()

# --- DUMMY SERVER UNTUK MENGAKALI RENDER ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot Scraper is Alive and Running 24/7!"

def run_web():
    # Render memberikan port secara dinamis lewat Environment Variable
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

# --- FUNGSI SCRAPING UTAMA ---
async def scrape_netflix(country_code: str, target_qty: int):
    valid_accounts = []
    
    async with async_playwright() as p:
        # WAJIB TRUE AGAR BISA JALAN DI SERVER TANPA MONITOR
        browser = await p.chromium.launch(headless=True) 
        page = await browser.new_page()
        
        try:
            print(f"DEBUG: Memulai target {target_qty} akun dari negara {country_code}")
            await page.goto("https://www.shrestha.live/", wait_until="networkidle")
            
            flag = page.locator(f"img[alt*='{country_code}' i]")
            await flag.wait_for(state="visible", timeout=10000)
            await flag.click(force=True)
            await page.wait_for_timeout(1000) 
            
            copy_btns = page.locator('button[aria-label="Copy cookie for Netflix"]')
            cookie_texts = page.locator("div.font-mono.break-all")
            count = await copy_btns.count()
            
            indices = list(range(count))
            random.shuffle(indices)
            
            for i in indices:
                if len(valid_accounts) >= target_qty:
                    break
                    
                if not await copy_btns.nth(i).is_visible():
                    await page.goto("https://www.shrestha.live/", wait_until="networkidle")
                    await flag.click(force=True)
                    await page.wait_for_timeout(1000)
                
                await copy_btns.nth(i).click(force=True)
                await page.wait_for_timeout(500)
                cookie_text = await cookie_texts.nth(i).text_content()
                
                await page.locator('button[aria-label="Close cookie panel"]').click(force=True)
                await page.wait_for_timeout(500)
                
                await page.locator("div.cursor-pointer:has-text('CHECKER')").click(force=True)
                await page.wait_for_url("**/checker", timeout=15000)
                await page.wait_for_timeout(500)
                
                await page.locator("textarea.w-full.h-48.bg-transparent").fill(cookie_text)
                
                try:
                    async with page.expect_response("**/check", timeout=15000) as response_info:
                        await page.locator("button:has-text('INITIATE VERIFICATION')").click(force=True)
                    
                    resp = await response_info.value
                    json_data = await resp.json()
                    
                    if json_data.get("status") == "SUCCESS":
                        links = [json_data.get("x_l1"), json_data.get("x_l2"), json_data.get("x_l3")]
                        details = f"Email: {json_data.get('x_mail')} | Plan: {json_data.get('x_tier')}"
                        valid_accounts.append({"details": details, "links": links})
                except Exception:
                    pass
                
                if len(valid_accounts) < target_qty:
                    await page.goto("https://www.shrestha.live/", wait_until="networkidle")
                    await page.wait_for_timeout(1000)
                    await flag.click(force=True)
                    await page.wait_for_timeout(1000)

            await browser.close()
            return valid_accounts

        except Exception as e:
            try: await browser.close()
            except: pass
            return valid_accounts 

# --- LOGIKA TELEGRAM BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇮🇩 ID", callback_data="country_ID"), InlineKeyboardButton("🇺🇸 US", callback_data="US")],
        [InlineKeyboardButton("🇸🇬 SG", callback_data="country_SG"), InlineKeyboardButton("🇯🇵 JP", callback_data="JP")],
        [InlineKeyboardButton("🇧🇷 BR", callback_data="country_BR"), InlineKeyboardButton("🇩🇪 DE", callback_data="DE")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🌍 **Pilih negara yang ingin di-scrape:**", reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith("country_") or data in ["US", "JP", "DE"]: 
        country_code = data.split("_")[1] if "country_" in data else data
        context.user_data['country'] = country_code
        
        keyboard = [
            [InlineKeyboardButton("1 Akun", callback_data="qty_1"), InlineKeyboardButton("3 Akun", callback_data="qty_3")],
            [InlineKeyboardButton("5 Akun", callback_data="qty_5"), InlineKeyboardButton("10 Akun", callback_data="qty_10")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Negara terpilih: **{country_code}**\n🔢 **Pilih jumlah akun yang diinginkan:**", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("qty_"):
        qty = int(data.split("_")[1])
        country_code = context.user_data.get('country', 'US') 
        
        await query.edit_message_text(f"🚀 **MEMULAI SCRAPING**\n\nNegara: `{country_code}`\nTarget: `{qty} Akun`\n\n_Mohon tunggu, bot sedang ngebut mencari akun yang valid..._", parse_mode='Markdown')
        
        hasil_akun = await scrape_netflix(country_code, qty)
        
        if len(hasil_akun) > 0:
            await query.edit_message_text(f"✅ **SELESAI!**\nBerhasil mendapatkan **{len(hasil_akun)}/{qty}** akun valid.", parse_mode='Markdown')
            for idx, akun in enumerate(hasil_akun):
                pesan = f"🍿 **AKUN #{idx+1}**\n📝 `{akun['details']}`\n\n💻 **PC:**\n`{akun['links'][0]}`\n\n📱 **Mobile:**\n`{akun['links'][1]}`\n\n📺 **TV:**\n`{akun['links'][2]}`"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=pesan, parse_mode='Markdown')
        else:
            await query.edit_message_text(f"❌ **GAGAL**\nMaaf, tidak ada akun yang ALIVE untuk negara {country_code}.", parse_mode='Markdown')

if __name__ == "__main__":
    # Menjalankan Dummy Web Server di Background
    Thread(target=run_web).start()
    
    # Mengambil Token dari Render Environment Variable (Fallback untuk tes lokal)
    TOKEN = os.environ.get("BOT_TOKEN", "MASUKKAN_TOKEN_LOCAL_JIKA_PERLU")
    
    print("Memulai Bot Telegram...")
    app_bot = Application.builder().token(TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    
    app_bot.run_polling()