import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
import time
from PIL import Image
import os
import logging
from bs4 import BeautifulSoup
from io import BytesIO

# Токен от BotFather
TOKEN = '7544295352:AAEdrCNQR3JiRjz6SpxPOQYfj_9EPSAXHaQ'

# ID твоего чата (оставляем для возможного использования, но не для статуса)
YOUR_CHAT_ID = '850489887'

# Словарь для хранения привязанных никнеймов (user_id: artist_nickname)
user_settings = {}

# Настройка логирования (в файл и терминал)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),  # Логи в файл
        logging.StreamHandler()          # Логи в терминал
    ]
)
logger = logging.getLogger(__name__)

# Счётчик запросов
REQUEST_COUNT_FILE = 'request_count.txt'
request_count = 0

def update_request_count():
    global request_count
    request_count += 1
    with open(REQUEST_COUNT_FILE, 'w') as f:
        f.write(str(request_count))
    logger.info(f"Обновлён счётчик запросов: {request_count}")

# Настройка Selenium для скриншотов
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# Функция для скриншота всей страницы
def full_page_screenshot(driver, file_path):
    total_height = driver.execute_script("return document.body.scrollHeight")
    viewport_height = driver.execute_script("return window.innerHeight")
    width = 1920

    driver.set_window_size(width, viewport_height)

    screenshots = []
    for i in range(0, total_height, viewport_height):
        driver.execute_script(f"window.scrollTo(0, {i});")
        time.sleep(0.5)
        screenshot = driver.get_screenshot_as_png()
        screenshots.append(Image.open(BytesIO(screenshot)))

    full_image = Image.new('RGB', (width, total_height))
    offset = 0
    for img in screenshots:
        full_image.paste(img, (0, offset))
        offset += img.size[1]

    full_image.save(file_path)
    logger.info(f"Полный скриншот сохранён: {file_path}")

# Функция для парсинга и скриншота одного артиста
def scan_bandlink(artist_name):
    logger.info(f"Начинаю поиск для артиста: {artist_name}")
    url = "https://band.link/scanner"
    driver = setup_driver()
    
    try:
        driver.get(url)
        logger.info(f"Открыта страница: {url}")
        search_box = driver.find_element("css selector", "[data-testid='search-input']")
        search_box.send_keys(artist_name)
        logger.info(f"Введён ник: {artist_name}")
        search_box.send_keys(Keys.RETURN)
        logger.info("Нажата клавиша Enter")
        time.sleep(3)
        
        screenshot_path = f"{artist_name}_screenshot.png"
        full_page_screenshot(driver, screenshot_path)
        
        return screenshot_path
    
    except Exception as e:
        logger.error(f"Ошибка при поиске {artist_name}: {str(e)}")
        return None
    
    finally:
        driver.quit()
        logger.info("Браузер закрыт")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    user_id = user.id
    logger.info(f"Пользователь {user_id} вызвал /start")
    
    keyboard = [
        [InlineKeyboardButton("Начать поиск", callback_data='search')],
        [InlineKeyboardButton("Настройки", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "Привет! Я бот для парсинга BandLink Scanner.\n"
        "Я могу искать артистов по никнейму.\n\n"
        "Инструкция:\n"
        "1. Нажми 'Начать поиск' и введи ник артиста.\n"
        "2. Или настрой привязку ника в 'Настройки'.\n"
        "3. Используй /search <ник> для поиска (например, /search Metallica)."
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    logger.info(f"Отправлено приветственное сообщение пользователю {user_id}")

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    logger.info(f"Пользователь {user_id} нажал кнопку: {query.data}")
    
    if query.data == 'search':
        if user_id in user_settings:
            artist_name = user_settings[user_id]
            await query.edit_message_text(f"Ищу по привязанному нику: {artist_name}")
            screenshot_path = scan_bandlink(artist_name)
            if screenshot_path:
                with open(screenshot_path, 'rb') as photo:
                    await context.bot.send_photo(chat_id=user_id, photo=photo)
                    logger.info(f"Скриншот отправлен пользователю {user_id} для {artist_name}")
                log = f"Поиск выполнен: {artist_name} | Время: {time.ctime()}"
                logger.info(log)
                os.remove(screenshot_path)
                logger.info(f"Временный файл {screenshot_path} удалён")
                update_request_count()
            else:
                await context.bot.send_message(chat_id=user_id, text=f"Ошибка при поиске {artist_name}.")
                logger.error(f"Не удалось выполнить поиск для {artist_name}")
        else:
            await query.edit_message_text("Введи ник артиста для поиска (например: /search Metallica)")
            logger.info(f"Запрошен ник у пользователя {user_id}")
    
    elif query.data == 'settings':
        current = user_settings.get(user_id, "не установлен")
        await query.edit_message_text(f"Текущий ник: {current}\nВведи новый ник через /settings <ник>")
        logger.info(f"Показаны настройки пользователю {user_id}")

# Команда /search для одного артиста
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    logger.info(f"Пользователь {user_id} вызвал /search с аргументами: {context.args}")
    
    if user_id in user_settings and not context.args:
        artist_name = user_settings[user_id]
        await update.message.reply_text(f"Ищу по привязанному нику: {artist_name}")
        logger.info(f"Использую привязанный ник: {artist_name}")
    elif context.args:
        artist_name = " ".join(context.args)  # Объединяем аргументы в одно имя
        await update.message.reply_text(f"Ищу артиста: {artist_name}")
        logger.info(f"Поиск по введённому нику: {artist_name}")
    else:
        await update.message.reply_text("Введи ник артиста после /search (например: /search Metallica)")
        logger.warning(f"Пользователь {user_id} не указал ник")
        return
    
    screenshot_path = scan_bandlink(artist_name)
    if screenshot_path:
        with open(screenshot_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo)
            logger.info(f"Скриншот отправлен пользователю {user_id} для {artist_name}")
        log = f"Поиск выполнен: {artist_name} | Время: {time.ctime()}"
        logger.info(log)
        os.remove(screenshot_path)
        logger.info(f"Временный файл {screenshot_path} удалён")
        update_request_count()
    else:
        await update.message.reply_text(f"Ошибка при поиске {artist_name}. Попробуй позже.")
        logger.error(f"Не удалось выполнить поиск для {artist_name}")

# Команда /settings
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    logger.info(f"Пользователь {user_id} вызвал /settings с аргументами: {context.args}")
    
    if context.args:
        artist_name = " ".join(context.args)
        user_settings[user_id] = artist_name
        await update.message.reply_text(f"Ник артиста привязан: {artist_name}")
        logger.info(f"Установлен ник {artist_name} для пользователя {user_id}")
    else:
        current = user_settings.get(user_id, "не установлен")
        await update.message.reply_text(f"Текущий ник: {current}\nВведи новый ник после /settings.")
        logger.info(f"Показан текущий ник пользователю {user_id}: {current}")

# Основная функция
def main() -> None:
    logger.info("Бот запускается...")
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Бот запущен, начинаю polling с увеличенным интервалом")
    application.run_polling(drop_pending_updates=True, timeout=60)  # Увеличиваем timeout
    logger.info("Бот остановлен")

if __name__ == '__main__':
    main()