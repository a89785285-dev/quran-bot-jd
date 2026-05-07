import logging
import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8620574210:AAH4cpVvF8k5MlO9Nz5qmrUmbDOmImWMoak')
API_URL = 'https://api.alquran.cloud/v1'

# Store user schedules and channel schedules
user_schedules = {}  # {user_id: {'interval': minutes, 'task': asyncio.Task}}
channel_schedules = {}  # {channel_id: {'interval': minutes, 'task': asyncio.Task}}

async def fetch_random_verse():
    """Fetch a random verse from the Quran API"""
    try:
        async with aiohttp.ClientSession() as session:
            # Get total verses
            async with session.get(f'{API_URL}/quran/verses/count') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total_verses = data['data']
                    random_verse_number = random.randint(1, total_verses)
                    
                    # Get the random verse
                    async with session.get(f'{API_URL}/verses/by_number/{random_verse_number}') as verse_resp:
                        if verse_resp.status == 200:
                            verse_data = await verse_resp.json()
                            verse = verse_data['data']
                            surah_number = verse['surah']['number']
                            verse_number = verse['numberInSurah']
                            text = verse['text']
                            surah_name = verse['surah']['englishName']
                            surah_name_ar = verse['surah']['name']
                            
                            return {
                                'text': text,
                                'surah': f"{surah_name} ({surah_name_ar})",
                                'verse': f"{surah_number}:{verse_number}",
                                'full_info': f"سورة {surah_name_ar} - الآية {verse_number}"
                            }
    except Exception as e:
        logger.error(f"Error fetching verse: {e}")
    
    return None

async def fetch_verse_by_surah(surah_query):
    """Fetch a verse from a specific surah"""
    try:
        async with aiohttp.ClientSession() as session:
            # First, search for the surah
            async with session.get(f'{API_URL}/surah') as resp:
                if resp.status == 200:
                    surahs_data = await resp.json()
                    surahs = surahs_data['data']
                    
                    # Find matching surah by name or number
                    matching_surah = None
                    if surah_query.isdigit():
                        surah_num = int(surah_query)
                        matching_surah = next((s for s in surahs if s['number'] == surah_num), None)
                    else:
                        surah_lower = surah_query.lower()
                        matching_surah = next((s for s in surahs if 
                                            surah_lower in s['englishName'].lower() or 
                                            surah_lower in s['name'].lower()), None)
                    
                    if matching_surah:
                        surah_num = matching_surah['number']
                        async with session.get(f'{API_URL}/surah/{surah_num}') as surah_resp:
                            if surah_resp.status == 200:
                                surah_detail = await surah_resp.json()
                                verses = surah_detail['data']['ayahs']
                                random_verse = random.choice(verses)
                                
                                return {
                                    'text': random_verse['text'],
                                    'surah': f"{matching_surah['englishName']} ({matching_surah['name']})",
                                    'verse': f"{matching_surah['number']}:{random_verse['numberInSurah']}",
                                    'full_info': f"سورة {matching_surah['name']} - الآية {random_verse['numberInSurah']}"
                                }
    except Exception as e:
        logger.error(f"Error fetching verse by surah: {e}")
    
    return None

async def send_verse(context, chat_id, is_channel=False):
    """Send a verse to a chat or channel"""
    verse = await fetch_random_verse()
    if verse:
        message = f"""
🌙 *آية من القرآن الكريم* 🌙

{verse['text']}

📖 *{verse['full_info']}*
__{verse['verse']}__

✨ بسم الله الرحمن الرحيم ✨
"""
        try:
            if is_channel:
                await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
            logger.info(f"Verse sent to {chat_id}")
        except Exception as e:
            logger.error(f"Error sending verse: {e}")

async def schedule_verses(context, user_id, interval_minutes, is_channel=False):
    """Schedule automatic verse sending"""
    while True:
        try:
            await send_verse(context, user_id, is_channel)
            await asyncio.sleep(interval_minutes * 60)
        except asyncio.CancelledError:
            logger.info(f"Scheduled task cancelled for {user_id}")
            break
        except Exception as e:
            logger.error(f"Error in schedule_verses: {e}")
            await asyncio.sleep(interval_minutes * 60)

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    await update.message.reply_text(
        "🌙 السلام عليكم ورحمة الله وبركاته\n\n"
        "أهلا بك في بوت القرآن الكريم!\n\n"
        "الأوامر المتاحة:\n"
        "/startquran - بدء إرسال آية كل 5 دقائق\n"
        "/schedule <دقائق> - تخصيص الفترة الزمنية\n"
        "/stopquran - إيقاف الإرسال\n"
        "/verse - جلب آية عشوائية الآن\n"
        "/surah <اسم أو رقم> - آية من سورة محددة\n"
        "/setchannel <@قناة> <دقائق> - إرسال في قناة\n"
        "/stopchannel <@قناة> - إيقاف الإرسال في قناة",
        parse_mode='Markdown'
    )

async def start_quran(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start sending verses every 5 minutes"""
    user_id = update.effective_user.id
    
    if user_id in user_schedules:
        await update.message.reply_text("⚠️ البوت يرسل آيات بالفعل. استخدم /stopquran لإيقاف الإرسال.")
        return
    
    # Send first verse immediately
    await send_verse(context, user_id)
    
    # Schedule verses every 5 minutes
    task = asyncio.create_task(schedule_verses(context, user_id, 5))
    user_schedules[user_id] = {'interval': 5, 'task': task}
    
    await update.message.reply_text("✅ تم بدء إرسال الآيات كل 5 دقائق. استخدم /stopquran لإيقاف الإرسال.")
    logger.info(f"Started scheduled verses for user {user_id}")

async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set custom interval for verses"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ استخدام: /schedule <دقائق>\nمثال: /schedule 10")
        return
    
    try:
        interval = int(context.args[0])
        if interval < 1:
            await update.message.reply_text("❌ الفترة الزمنية يجب أن تكون أكثر من دقيقة واحدة.")
            return
        
        # Stop existing schedule if any
        if user_id in user_schedules:
            user_schedules[user_id]['task'].cancel()
        
        # Send first verse immediately
        await send_verse(context, user_id)
        
        # Schedule with new interval
        task = asyncio.create_task(schedule_verses(context, user_id, interval))
        user_schedules[user_id] = {'interval': interval, 'task': task}
        
        await update.message.reply_text(f"✅ تم ضبط الإرسال كل {interval} دقيقة.")
        logger.info(f"User {user_id} set interval to {interval} minutes")
    except ValueError:
        await update.message.reply_text("❌ يجب إدخال رقم صحيح.")

async def stop_quran(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop sending verses"""
    user_id = update.effective_user.id
    
    if user_id not in user_schedules:
        await update.message.reply_text("⚠️ لا يوجد جدول نشط حالياً.")
        return
    
    user_schedules[user_id]['task'].cancel()
    del user_schedules[user_id]
    
    await update.message.reply_text("✅ تم إيقاف الإرسال.")
    logger.info(f"Stopped scheduled verses for user {user_id}")

async def get_verse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a random verse immediately"""
    await send_verse(context, update.effective_chat.id)

async def get_surah_verse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a verse from a specific surah"""
    if not context.args:
        await update.message.reply_text("❌ استخدام: /surah <اسم أو رقم>\nمثال: /surah البقرة أو /surah 2")
        return
    
    surah_query = ' '.join(context.args)
    verse = await fetch_verse_by_surah(surah_query)
    
    if verse:
        message = f"""
🌙 *آية من القرآن الكريم* 🌙

{verse['text']}

📖 *{verse['full_info']}*
__{verse['verse']}__
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ لم أتمكن من العثور على السورة. تأكد من كتابة الاسم بشكل صحيح.")

async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set channel for automatic posting"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ استخدام: /setchannel <@قناة أو ID> <دقائق>\n"
            "مثال: /setchannel @mychannel 30"
        )
        return
    
    channel_identifier = context.args[0]
    try:
        interval = int(context.args[1])
        if interval < 1:
            await update.message.reply_text("❌ الفترة الزمنية يجب أن تكون أكثر من دقيقة واحدة.")
            return
    except ValueError:
        await update.message.reply_text("❌ يجب إدخال رقم صحيح للفترة الزمنية.")
        return
    
    # Convert channel identifier
    if channel_identifier.startswith('@'):
        channel_id = channel_identifier
    else:
        try:
            channel_id = int(channel_identifier)
        except ValueError:
            channel_id = channel_identifier
    
    # Stop existing schedule if any
    if channel_id in channel_schedules:
        channel_schedules[channel_id]['task'].cancel()
    
    # Send first verse immediately
    await send_verse(context, channel_id, is_channel=True)
    
    # Schedule with interval
    task = asyncio.create_task(schedule_verses(context, channel_id, interval, is_channel=True))
    channel_schedules[channel_id] = {'interval': interval, 'task': task}
    
    await update.message.reply_text(f"✅ تم ضبط الإرسال في القناة كل {interval} دقيقة.")
    logger.info(f"Channel {channel_id} set to receive verses every {interval} minutes")

async def stop_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop posting to a channel"""
    if not context.args:
        await update.message.reply_text(
            "❌ استخدام: /stopchannel <@قناة أو ID>\n"
            "مثال: /stopchannel @mychannel"
        )
        return
    
    channel_identifier = context.args[0]
    
    # Convert channel identifier
    if channel_identifier.startswith('@'):
        channel_id = channel_identifier
    else:
        try:
            channel_id = int(channel_identifier)
        except ValueError:
            channel_id = channel_identifier
    
    if channel_id not in channel_schedules:
        await update.message.reply_text("⚠️ لا يوجد جدول نشط لهذه القناة.")
        return
    
    channel_schedules[channel_id]['task'].cancel()
    del channel_schedules[channel_id]
    
    await update.message.reply_text(f"✅ تم إيقاف الإرسال في القناة.")
    logger.info(f"Stopped scheduled verses for channel {channel_id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message"""
    help_text = """
🌙 *بوت القرآن الكريم* 🌙

*الأوامر المتاحة:*

🔹 *للمحادثات الخاصة والمجموعات:*
/startquran - بدء إرسال آية كل 5 دقائق
/schedule <دقائق> - تخصيص الفترة الزمنية (مثال: /schedule 10)
/stopquran - إيقاف الإرسال
/verse - جلب آية عشوائية الآن
/surah <اسم أو رقم> - آية من سورة محددة

🔹 *للقنوات:*
/setchannel <@قناة أو ID> <دقائق> - بدء الإرسال في قناة
مثال: /setchannel @mychannel 30
/stopchannel <@قناة أو ID> - إيقاف الإرسال في قناة

✨ *بسم الله الرحمن الرحيم* ✨
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("startquran", start_quran))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(CommandHandler("stopquran", stop_quran))
    application.add_handler(CommandHandler("verse", get_verse))
    application.add_handler(CommandHandler("surah", get_surah_verse))
    application.add_handler(CommandHandler("setchannel", set_channel))
    application.add_handler(CommandHandler("stopchannel", stop_channel))

    # Set bot commands
    await application.bot.set_my_commands([
        BotCommand("start", "بدء البوت"),
        BotCommand("help", "عرض المساعدة"),
        BotCommand("startquran", "بدء إرسال آيات تلقائي"),
        BotCommand("schedule", "ضبط الفترة الزمنية"),
        BotCommand("stopquran", "إيقاف الإرسال"),
        BotCommand("verse", "جلب آية عشوائية"),
        BotCommand("surah", "آية من سورة محددة"),
        BotCommand("setchannel", "إرسال في قناة"),
        BotCommand("stopchannel", "إيقاف الإرسال في قناة"),
    ])

    # Start the Bot
    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
