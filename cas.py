import random
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
import json
import os

# Пути к фотографиям
PHOTOS_DIR = "photos"
ROULETTE_TABLE = os.path.join(PHOTOS_DIR, "roulette_table.jpg")
PHOTO_WIN = os.path.join(PHOTOS_DIR, "win.jpg")
PHOTO_LOSE = os.path.join(PHOTOS_DIR, "lose.jpg")

# Токен вашего бота (получите у @BotFather)
BOT_TOKEN = "8202832824:AAFV9wKFYfUfxdZa2KPM63WkMX5MsBhZfIE"

# ID администратора
ADMIN_ID = 1915644408

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Файл для хранения данных пользователей
USERS_FILE = "users_data.json"

# Словарь для хранения выбранных ставок пользователей (для ввода суммы вручную)
user_bet_selection = {}

# Загрузка данных пользователей
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Сохранение данных пользователей
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# --- Работа с username для переводов ---
def normalize_username(name: str) -> str:
    if not name:
        return ""
    n = name.strip()
    if n.startswith('@'):
        n = n[1:]
    return n.lower()

def remember_user(user):
    try:
        uid = user.id
    except Exception:
        return
    users = load_users()
    if str(uid) not in users:
        users[str(uid)] = {'balance': 50000}
    try:
        uname = getattr(user, 'username', None)
        if uname:
            users[str(uid)]['username'] = normalize_username(uname)
    except Exception:
        pass
    save_users(users)

def find_user_id_by_username(username: str):
    if not username:
        return None
    uname = normalize_username(username)
    users = load_users()
    for uid, data in users.items():
        if normalize_username(data.get('username', '')) == uname:
            try:
                return int(uid)
            except Exception:
                continue
    return None

# Получение баланса пользователя
def get_balance(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get('balance', 50000)

# Изменение баланса пользователя
def update_balance(user_id, amount):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {'balance': 50000}
    users[str(user_id)]['balance'] = users[str(user_id)]['balance'] + amount
    save_users(users)

# Номера на рулетке (00, 0, 1-36)
def spin_roulette():
    return random.randint(0, 37)  # 37 = 00 в нашей системе

# Получить цвет номера
def get_color(number):
    if number == 0 or number == 37:
        return "зеленый"
    
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    if number in red_numbers:
        return "красный"
    return "черный"

# Получить четность
def is_even(number):
    if number == 0 or number == 37:
        return None
    return number % 2 == 0

# Получить ряд (дюжина)
def get_dozen(number):
    if number == 0 or number == 37:
        return None
    if 1 <= number <= 12:
        return 1
    elif 13 <= number <= 24:
        return 2
    elif 25 <= number <= 36:
        return 3
    return None

# Стратегии ставок (возвращает полную сумму выигрыша включая ставку)
def calculate_payout(strategy, bet_amount, winning_number):
    color = get_color(winning_number)
    even = is_even(winning_number)
    bet_win_num = winning_number if winning_number != 37 else 0
    dozen = get_dozen(winning_number)
    
    # Цвета
    if strategy in ["color_red", "красное", "red", "ред"]:
        return bet_amount * 2 if color == "красный" else 0
    elif strategy in ["color_black", "черное", "black", "блек"]:
        return bet_amount * 2 if color == "черный" else 0
    
    # Зеленое
    elif strategy in ["green", "зеро", "0", "00"]:
        return bet_amount * 36 if (winning_number == 0 or winning_number == 37) else 0
    
    # Четность
    elif strategy in ["even", "чет", "четное"]:
        return bet_amount * 2 if even is True else 0
    elif strategy in ["odd", "нечет", "нечетное"]:
        return bet_amount * 2 if even is False else 0
    
    # Диапазоны
    elif strategy in ["low", "1-18"]:
        return bet_amount * 2 if (1 <= bet_win_num <= 18) else 0
    elif strategy in ["high", "19-36"]:
        return bet_amount * 2 if (19 <= bet_win_num <= 36) else 0
    
    # Сектора (дюжины)
    elif strategy.startswith("dozen_"):
        bet_dozen = int(strategy.split("_")[1])
        return bet_amount * 3 if dozen == bet_dozen else 0
    elif strategy in ["1д", "2д", "3д", "1ст", "2ст", "3ст", "1сектор", "2сектор", "3сектор"]:
        bet_dozen_map = {"1д": 1, "2д": 2, "3д": 3, "1ст": 1, "2ст": 2, "3ст": 3,
                         "1сектор": 1, "2сектор": 2, "3сектор": 3}
        bet_dozen = bet_dozen_map.get(strategy)
        return bet_amount * 3 if dozen == bet_dozen else 0
    
    # Конкретное число
    elif strategy.startswith("number_"):
        bet_number = int(strategy.split("_")[1])
        return bet_amount * 36 if bet_win_num == bet_number else 0
    
    # Прямой ввод числа
    elif strategy.isdigit():
        bet_number = int(strategy)
        if bet_number == 0 and (winning_number == 0 or winning_number == 37):
            return bet_amount * 36
        elif bet_number == bet_win_num:
            return bet_amount * 36
    
    return 0

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Запоминаем username пользователя
    try:
        remember_user(message.from_user)
    except Exception:
        pass
    user_id = message.from_user.id
    balance = get_balance(user_id)
    
    # Проверяем, админ ли это
    is_admin = user_id == ADMIN_ID
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette_menu")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="balance")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players")],
        [InlineKeyboardButton(text="🎁 Начать снова", callback_data="reset_confirm")],
    ]
    
    # Добавляем админ панель для админа
    if is_admin:
        keyboard_buttons.append([InlineKeyboardButton(text="🔧 Админ панель", callback_data="admin_panel")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = (
        f"🎰 Добро пожаловать в казино!\n\n"
        f"💰 Ваш баланс: {balance} монет\n\n"
        f"Выберите игру:"
    )
    
    # Пытаемся отправить с фото главного меню
    photo_path = os.path.join(PHOTOS_DIR, "main_menu.jpg")
    photo_exists = False
    
    if os.path.exists(photo_path):
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".png")):
        photo_path = photo_path.replace(".jpg", ".png")
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".jpeg")):
        photo_path = photo_path.replace(".jpg", ".jpeg")
        photo_exists = True
    
    if photo_exists:
        await message.answer_photo(FSInputFile(photo_path), caption=text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

@dp.callback_query(F.data == "balance")
async def show_balance(callback: CallbackQuery):
    await callback.answer()
    
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    
    # Получаем место в топе
    users = load_users()
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('balance', 0), reverse=True)
    
    # Находим место пользователя
    user_place = 1
    for i, (uid, data) in enumerate(sorted_users, 1):
        if str(uid) == str(user_id):
            user_place = i
            break
    
    # Получаем имя пользователя
    try:
        user_chat = await bot.get_chat(user_id)
        username = f"@{user_chat.username}" if user_chat.username else user_chat.first_name
    except:
        username = f"Игрок {user_id}"
    
    # Эмодзи для места
    medal = "🥇" if user_place == 1 else "🥈" if user_place == 2 else "🥉" if user_place == 3 else f"#{user_place}"
    
    text = (
        f"👤 ПРОФИЛЬ\n\n"
        f"Игрок: {username}\n"
        f"💰 Баланс: {balance} монет\n"
        f"🏆 Место в топе: {medal}\n"
        f"📊 Всего игроков: {len(sorted_users)}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    # Пытаемся отправить с фото
    photo_path = os.path.join(PHOTOS_DIR, "profile.jpg")
    photo_exists = False
    
    if os.path.exists(photo_path):
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".png")):
        photo_path = photo_path.replace(".jpg", ".png")
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".jpeg")):
        photo_path = photo_path.replace(".jpg", ".jpeg")
        photo_exists = True
    
    # Всегда удаляем старое сообщение и отправляем новое, чтобы фото заменялось правильно
    try:
        await callback.message.delete()
    except:
        pass
    
    if photo_exists:
        await bot.send_photo(user_id, FSInputFile(photo_path), caption=text, reply_markup=keyboard)
    else:
        await bot.send_message(user_id, text, reply_markup=keyboard)

@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    sender_id = message.from_user.id
    try:
        remember_user(message.from_user)
    except Exception:
        pass
    args_text = (message.text or "").strip()

    # Извлекаем сумму и получателя: поддержка форматов
    # 1) /pay @username 100
    # 2) /pay 100 @username
    # 3) Ответ на сообщение пользователя: /pay 100
    # 4) /pay user_id 100 (на случай прямого ID)

    # Ищем сумму как последнее или первое число в тексте
    tokens = args_text.split()
    # Удаляем саму команду
    if tokens and tokens[0].startswith('/pay'):
        tokens = tokens[1:]

    target_username = None
    target_id = None
    amount = None

    # Проверка, если это ответ на сообщение
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id

    # Ищем упоминание @username и text_mention в сущностях
    if not target_id and message.entities:
        for ent in message.entities:
            # В aiogram v3 тип сущности — строка, например 'mention'
            if ent.type == 'mention':
                target_username = message.text[ent.offset: ent.offset + ent.length]
                break
            if ent.type == 'text_mention' and getattr(ent, 'user', None):
                try:
                    target_id = ent.user.id
                    remember_user(ent.user)
                    break
                except Exception:
                    pass

    # Пытаемся найти числовые значения как сумму
    for t in tokens:
        if t.isdigit():
            amount = int(t)
            break

    # Если целевого пользователя нет, пробуем извлечь из токенов
    if not target_id and not target_username and tokens:
        for t in tokens:
            if t.startswith('@'):
                target_username = t
                break
            # Прямой user_id
            if t.isdigit() and int(t) > 10000:
                target_id = int(t)
                break

    # Проверки корректности
    if amount is None or amount <= 0:
        await message.answer("❌ Укажите сумму перевода. Пример: /pay @username 100 или ответьте /pay 100")
        return

    # Получаем chat по username, если нужно
    if not target_id and target_username:
        try:
            chat = await bot.get_chat(target_username)
            target_id = chat.id
        except Exception:
            # Резерв: поиск по сохранённым username, если бот не может получить чат по @
            fallback_id = find_user_id_by_username(target_username)
            if fallback_id is None:
                await message.answer("❌ Не удалось найти пользователя по указанному @username.")
                return
            target_id = fallback_id

    if not target_id:
        await message.answer("❌ Не указан получатель. Используйте @username, ответьте на сообщение или укажите ID.")
        return

    if target_id == sender_id:
        await message.answer("❌ Нельзя переводить монеты самому себе.")
        return

    # Проверяем баланс отправителя
    if get_balance(sender_id) < amount:
        await message.answer("❌ Недостаточно средств для перевода.")
        return

    # Выполняем перевод
    update_balance(sender_id, -amount)
    update_balance(target_id, amount)

    # Получаем отображаемые имена
    def format_username(uid: int, fallback: str) -> str:
        return fallback

    try:
        s_chat = await bot.get_chat(sender_id)
        sender_name = f"@{s_chat.username}" if s_chat.username else (s_chat.first_name or f"ID {sender_id}")
    except Exception:
        sender_name = f"ID {sender_id}"
    try:
        r_chat = await bot.get_chat(target_id)
        receiver_name = f"@{r_chat.username}" if r_chat.username else (r_chat.first_name or f"ID {target_id}")
    except Exception:
        receiver_name = f"ID {target_id}"

    await message.answer(
        f"✅ Перевод выполнен\n\n"
        f"Отправитель: {sender_name}\n"
        f"Получатель: {receiver_name}\n"
        f"Сумма: {amount} монет\n\n"
        f"Ваш новый баланс: {get_balance(sender_id)} монет"
    )

# Дополнительный перехватчик для формата /pay@bot
@dp.message(lambda message: message.text and message.text.strip().lower().startswith('/pay'))
async def cmd_pay_alias(message: Message):
    # Избегаем двойного срабатывания: если уже попали в Command("pay"), этот не нужен,
    # но aiogram сам дебаунсит по порядку, оставим простой вызов
    await cmd_pay(message)

@dp.callback_query(F.data == "reset_confirm")
async def reset_confirm(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сбросить", callback_data="reset_yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu")],
    ])
    text = (
        "⚠️ ВНИМАНИЕ!\n\n"
        "Вы уверены, что хотите сбросить баланс?\n"
        "Все монеты будут утрачены, и вы получите 30000 монет."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await bot.send_message(callback.from_user.id, text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "reset_yes")
async def reset_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id == ADMIN_ID
    
    update_balance(user_id, -get_balance(user_id) + 30000)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    text = (
        "✅ Баланс сброшен! Вы получили 30000 монет.\n\n"
        "💰 Новый баланс: 30000 монет"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await bot.send_message(user_id, text, reply_markup=keyboard)
    await callback.answer("Баланс сброшен!")

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    is_admin = user_id == ADMIN_ID
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette_menu")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="balance")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players")],
        [InlineKeyboardButton(text="🎁 Начать снова", callback_data="reset_confirm")],
    ]
    
    if is_admin:
        keyboard_buttons.append([InlineKeyboardButton(text="🔧 Админ панель", callback_data="admin_panel")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = (
        f"🎰 Добро пожаловать в казино!\n\n"
        f"💰 Ваш баланс: {balance} монет\n\n"
        f"Выберите игру:"
    )
    
    # Пытаемся отправить с фото главного меню
    photo_path = os.path.join(PHOTOS_DIR, "main_menu.jpg")
    photo_exists = False
    
    if os.path.exists(photo_path):
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".png")):
        photo_path = photo_path.replace(".jpg", ".png")
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".jpeg")):
        photo_path = photo_path.replace(".jpg", ".jpeg")
        photo_exists = True
    
    # Всегда удаляем старое сообщение и отправляем новое, чтобы фото заменялось правильно
    try:
        await callback.message.delete()
    except:
        pass
    
    if photo_exists:
        await bot.send_photo(user_id, FSInputFile(photo_path), caption=text, reply_markup=keyboard)
    else:
        await bot.send_message(user_id, text, reply_markup=keyboard)

@dp.callback_query(F.data == "roulette_menu")
async def roulette_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 Красное (x2)", callback_data="bet_color_red")],
        [InlineKeyboardButton(text="⚫ Черное (x2)", callback_data="bet_color_black")],
        [InlineKeyboardButton(text="🟢 Зеленое 0/00 (x36)", callback_data="bet_green")],
        [InlineKeyboardButton(text="🔢 Четное (x2)", callback_data="bet_even"),
         InlineKeyboardButton(text="🔢 Нечетное (x2)", callback_data="bet_odd")],
        [InlineKeyboardButton(text="⬇️ 1-18 (x2)", callback_data="bet_low"),
         InlineKeyboardButton(text="⬆️ 19-36 (x2)", callback_data="bet_high")],
        [InlineKeyboardButton(text="📊 1-й сектор 1-12 (x3)", callback_data="bet_dozen_1")],
        [InlineKeyboardButton(text="📊 2-й сектор 13-24 (x3)", callback_data="bet_dozen_2")],
        [InlineKeyboardButton(text="📊 3-й сектор 25-36 (x3)", callback_data="bet_dozen_3")],
        [InlineKeyboardButton(text="🎯 На конкретное число (x36)", callback_data="bet_number")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    # Отправляем фото со столом или текст
    text = (f"🎰 Рулетка\n\n"
            f"💰 Ваш баланс: {balance} монет\n\n"
            f"Выберите тип ставки или введите текстом:\n"
            f"📝 Пример: «красное 100» или «1ст 50» или «зеро 500»")
    
    # Проверяем фото стола с разными расширениями
    table_photo = None
    if os.path.exists(ROULETTE_TABLE):
        table_photo = ROULETTE_TABLE
    elif os.path.exists(ROULETTE_TABLE.replace(".jpg", ".png")):
        table_photo = ROULETTE_TABLE.replace(".jpg", ".png")
    elif os.path.exists(ROULETTE_TABLE.replace(".jpg", ".jpeg")):
        table_photo = ROULETTE_TABLE.replace(".jpg", ".jpeg")
    
    # Удаляем старое сообщение и отправляем новое
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем новое сообщение
    if table_photo:
        await bot.send_photo(
            callback.from_user.id,
            FSInputFile(table_photo),
            caption=text,
            reply_markup=keyboard
        )
    else:
        await bot.send_message(
            callback.from_user.id,
            text,
            reply_markup=keyboard
        )
    
    await callback.answer()

# Профиль по сообщению "я" (в личке и в чатах)
@dp.message(lambda message: message.text and message.text.strip().lower() == "я")
async def show_self_profile_in_chat(message: Message):
    try:
        remember_user(message.from_user)
    except Exception:
        pass
    user_id = message.from_user.id
    balance = get_balance(user_id)

    users = load_users()
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('balance', 0), reverse=True)

    user_place = 1
    for i, (uid, data) in enumerate(sorted_users, 1):
        if str(uid) == str(user_id):
            user_place = i
            break

    try:
        user_chat = await bot.get_chat(user_id)
        username = f"@{user_chat.username}" if user_chat.username else user_chat.first_name
    except Exception:
        username = f"Игрок {user_id}"

    medal = "🥇" if user_place == 1 else "🥈" if user_place == 2 else "🥉" if user_place == 3 else f"#{user_place}"

    text = (
        f"👤 ПРОФИЛЬ\n\n"
        f"Игрок: {username}\n"
        f"💰 Баланс: {balance} монет\n"
        f"🏆 Место в топе: {medal}\n"
        f"📊 Всего игроков: {len(sorted_users)}"
    )

    await message.answer(text)

# Обработка ставок
@dp.callback_query(F.data.startswith("bet_"))
async def handle_bet_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    balance = get_balance(user_id)
    
    if balance <= 0:
        await callback.answer("❌ У вас нет средств для игры!", show_alert=True)
        return
    
    bet_type = callback.data.replace("bet_", "")
    
    # Сохраняем выбранную ставку для возможности ввода суммы вручную
    user_bet_selection[str(user_id)] = bet_type
    
    # Создаем клавиатуру для выбора суммы ставки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5к", callback_data=f"amount_{bet_type}_5000"),
         InlineKeyboardButton(text="10к", callback_data=f"amount_{bet_type}_10000"),
         InlineKeyboardButton(text="15к", callback_data=f"amount_{bet_type}_15000")],
        [InlineKeyboardButton(text="20к", callback_data=f"amount_{bet_type}_20000"),
         InlineKeyboardButton(text="25к", callback_data=f"amount_{bet_type}_25000")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="roulette_menu")]
    ])
    
    bet_name = {
        "color_red": "Красное",
        "color_black": "Черное",
        "green": "Зеленое (0/00)",
        "even": "Четное",
        "odd": "Нечетное",
        "low": "1-18",
        "high": "19-36",
        "dozen_1": "1-й сектор (1-12)",
        "dozen_2": "2-й сектор (13-24)",
        "dozen_3": "3-й сектор (25-36)",
        "number": "Конкретное число"
    }.get(bet_type, "Неизвестно")
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем новое сообщение
    await bot.send_message(
        user_id,
        f"🎰 Ставка: {bet_name}\n\n"
        f"💰 Ваш баланс: {balance} монет\n\n"
        f"Выберите сумму ставки (или выберите сумму вручную):",
        reply_markup=keyboard
    )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("amount_"))
async def handle_amount_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    # Последний элемент - это сумма
    amount = int(parts[-1])
    # Всё что между "amount" и последним - это тип ставки
    bet_type = "_".join(parts[1:-1])  # color_red, color_black, etc.
    balance = get_balance(user_id)
    
    if balance < amount:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Очищаем сохраненную ставку, так как пользователь выбрал сумму кнопкой
    if str(user_id) in user_bet_selection:
        del user_bet_selection[str(user_id)]
    
    if bet_type == "number":
        # Создаем клавиатуру для выбора конкретного числа (1-36, 0, 00)
        buttons = []
        
        # Числа 1-36 по 6 в ряд
        for row in range(6):
            row_buttons = []
            for col in range(6):
                num = row * 6 + col + 1
                if num <= 36:
                    row_buttons.append(InlineKeyboardButton(text=str(num), callback_data=f"num_{num}_{amount}"))
            if row_buttons:
                buttons.append(row_buttons)
        
        # Добавляем 0 и 00
        buttons.append([
            InlineKeyboardButton(text="00", callback_data=f"num_37_{amount}"),
            InlineKeyboardButton(text="0", callback_data=f"num_0_{amount}")
        ])
        
        # Добавляем кнопку назад
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="roulette_menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Удаляем старое сообщение
        try:
            await callback.message.delete()
        except:
            pass
        
        # Отправляем новое сообщение
        await bot.send_message(
            user_id,
            f"🎯 Ставка: {amount} монет на конкретное число\n\n"
            f"💰 Ваш баланс: {balance} монет\n\n"
            f"Выберите число:",
            reply_markup=keyboard
        )
    else:
        # Прямо запускаем игру
        await spin_roulette_game(callback, bet_type, amount, user_id)
    
    await callback.answer()

@dp.callback_query(F.data.startswith("num_"))
async def handle_number_choice(callback: CallbackQuery):
    parts = callback.data.split("_")
    number = int(parts[1])
    amount = int(parts[2])
    user_id = callback.from_user.id
    
    bet_type = f"number_{number}"
    await spin_roulette_game(callback, bet_type, amount, user_id)
    await callback.answer()

async def spin_roulette_game(callback: CallbackQuery, bet_type: str, amount: int, user_id: int):
    # Обновляем баланс (списываем ставку)
    update_balance(user_id, -amount)
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем анимацию
    message = await bot.send_message(
        user_id,
        "🎰 Крутим рулетку...\n"
        "⏳ Результат обрабатывается..."
    )
    
    # Имитация вращения
    await asyncio.sleep(2)
    
    # Крутим рулетку
    winning_number = spin_roulette()
    
    # Отображаем номер выигрыша
    number_display = "00" if winning_number == 37 else str(winning_number)
    color = get_color(winning_number)
    
    # Удаляем сообщение анимации
    try:
        await message.delete()
    except:
        pass
    
    # Вычисляем выигрыш
    payout = calculate_payout(bet_type, amount, winning_number)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Играть снова", callback_data="roulette_menu")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
    ])
    
    if payout > 0:
        update_balance(user_id, payout)
        new_balance = get_balance(user_id)
        
        text = (
            f"🎉 Поздравляем! Вы выиграли!\n\n"
            f"💰 Выигрыш: {payout} монет\n"
            f"📊 Ставка: {amount} монет\n"
            f"💎 Новый баланс: {new_balance} монет\n\n"
            f"Выпало: {number_display} ({color})"
        )
        
        # Отправляем фото с текстом и кнопками одним сообщением
        photo_win = None
        if os.path.exists(PHOTO_WIN):
            photo_win = PHOTO_WIN
        elif os.path.exists(PHOTO_WIN.replace(".jpg", ".png")):
            photo_win = PHOTO_WIN.replace(".jpg", ".png")
        elif os.path.exists(PHOTO_WIN.replace(".jpg", ".jpeg")):
            photo_win = PHOTO_WIN.replace(".jpg", ".jpeg")
        
        if photo_win:
            await bot.send_photo(user_id, FSInputFile(photo_win), caption=text, reply_markup=keyboard)
        else:
            await bot.send_message(user_id, text, reply_markup=keyboard)
    else:
        new_balance = get_balance(user_id)
        
        text = (
            f"😞 Вы проиграли\n\n"
            f"📊 Потеряно: {amount} монет\n"
            f"💎 Ваш баланс: {new_balance} монет\n\n"
            f"Выпало: {number_display} ({color})"
        )
        
        # Отправляем фото с текстом и кнопками одним сообщением
        photo_lose = None
        if os.path.exists(PHOTO_LOSE):
            photo_lose = PHOTO_LOSE
        elif os.path.exists(PHOTO_LOSE.replace(".jpg", ".png")):
            photo_lose = PHOTO_LOSE.replace(".jpg", ".png")
        elif os.path.exists(PHOTO_LOSE.replace(".jpg", ".jpeg")):
            photo_lose = PHOTO_LOSE.replace(".jpg", ".jpeg")
        
        if photo_lose:
            await bot.send_photo(user_id, FSInputFile(photo_lose), caption=text, reply_markup=keyboard)
        else:
            await bot.send_message(user_id, text, reply_markup=keyboard)

# Обработка текстовых ставок и чата: реагируем ТОЛЬКО на ставки/цифры после выбора и игнорируем прочее
@dp.message(lambda message: message.text and not message.text.startswith('/'))
async def handle_text_bet(message: Message):
    user_id = message.from_user.id
    try:
        remember_user(message.from_user)
    except Exception:
        pass
    balance = get_balance(user_id)
    
    # Проверка на админ команду для изменения баланса
    if user_id == ADMIN_ID:
        text_raw = message.text.strip()
        words = text_raw.split()
        
        # Проверяем, является ли это командой админа (ID число) 
        if len(words) == 2:
            try:
                target_user_id = int(words[0])
                new_amount = int(words[1])
                
                # Устанавливаем новый баланс
                old_balance = get_balance(target_user_id)
                users = load_users()
                users[str(target_user_id)] = {'balance': new_amount}
                save_users(users)
                
                await message.answer(
                    f"✅ Баланс изменен!\n\n"
                    f"👤 ID: {target_user_id}\n"
                    f"💰 Было: {old_balance}\n"
                    f"💰 Стало: {new_amount}"
                )
                return
            except ValueError:
                pass  # Не команда админа, продолжаем как обычную ставку
    
    # Сообщение "я" обрабатывается отдельным хендлером — здесь игнорируем
    if message.text.strip().lower() == "я":
        return

    # Проверяем, выбрал ли пользователь ставку кнопкой и вводит только сумму
    if str(user_id) in user_bet_selection and message.text.strip().isdigit():
        amount = int(message.text.strip())
        bet_type = user_bet_selection[str(user_id)]
        
        if balance < amount:
            await message.answer("❌ Недостаточно средств!")
            return
        
        if amount <= 0:
            await message.answer("❌ Минимальная ставка - 1 монета!")
            return
        
        # Запускаем игру с выбранной ставкой и введенной суммой
        await message.answer("⏳ Запускаю рулетку...")
        
        # Создаем фиктивный callback для использования существующей функции
        class FakeCallback:
            def __init__(self, message):
                self.message = message
        
        fake_callback = FakeCallback(message)
        await spin_roulette_game(fake_callback, bet_type, amount, user_id)
        
        # Удаляем сохраненную ставку
        if str(user_id) in user_bet_selection:
            del user_bet_selection[str(user_id)]
        
        return
    
    # Парсим текст ставки
    text = message.text.strip().lower()
    words = text.split()
    
    if len(words) < 2:
        # Не ставка — молча игнорируем
        return
    
    try:
        amount = int(words[-1])
        # Все слова кроме последнего - это тип ставки
        bet_strategy = " ".join(words[:-1])
    except ValueError:
        # Не ставка — игнорируем
        return
    
    if balance < amount:
        await message.answer("❌ Недостаточно средств!")
        return
    
    if amount <= 0:
        await message.answer("❌ Минимальная ставка - 1 монета!")
        return
    
    # Список допустимых типов ставок (удаляем пробелы)
    valid_bets = ["красное", "черное", "red", "black", "ред", "блек",
                   "чет", "нечет", "четное", "нечетное",
                   "зеро", "0", "00",
                   "1-18", "19-36",
                   "1д", "2д", "3д", "1ст", "2ст", "3ст", "1сектор", "2сектор", "3сектор"]
    
    # Убираем пробелы из bet_strategy для проверки
    bet_strategy_clean = bet_strategy.replace(" ", "")
    
    # Проверяем, является ли это числом (прямая ставка)
    is_number_bet = bet_strategy_clean.isdigit() or bet_strategy_clean in ["0", "00"]
    
    # Запускаем игру
    if bet_strategy_clean in valid_bets or is_number_bet:
        # Обновляем баланс (списываем ставку)
        update_balance(user_id, -amount)
        
        # Отправляем анимацию "крутим рулетку"
        anim_message = await message.answer(
            "🎰 Крутим рулетку...\n"
            "⏳ Результат обрабатывается..."
        )
        
        # Имитация вращения
        await asyncio.sleep(2)
        
        # Крутим рулетку
        winning_number = spin_roulette()
        number_display = "00" if winning_number == 37 else str(winning_number)
        color = get_color(winning_number)
        
        # Удаляем сообщение анимации
        try:
            await anim_message.delete()
        except:
            pass
        
        # Вычисляем выигрыш (используем очищенную версию для точного соответствия)
        payout = calculate_payout(bet_strategy_clean, amount, winning_number)
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Играть снова", callback_data="roulette_menu")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
        ])
        
        if payout > 0:
            update_balance(user_id, payout)
            new_balance = get_balance(user_id)
            
            text = (
                f"🎉 Поздравляем! Вы выиграли!\n\n"
                f"💰 Выигрыш: {payout} монет\n"
                f"📊 Ставка: {amount} монет\n"
                f"💎 Новый баланс: {new_balance} монет\n\n"
                f"Выпало: {number_display} ({color})"
            )
            
            # Отправляем фото с текстом и кнопками одним сообщением
            photo_win = None
            if os.path.exists(PHOTO_WIN):
                photo_win = PHOTO_WIN
            elif os.path.exists(PHOTO_WIN.replace(".jpg", ".png")):
                photo_win = PHOTO_WIN.replace(".jpg", ".png")
            elif os.path.exists(PHOTO_WIN.replace(".jpg", ".jpeg")):
                photo_win = PHOTO_WIN.replace(".jpg", ".jpeg")
            
            if photo_win:
                await message.answer_photo(FSInputFile(photo_win), caption=text, reply_markup=keyboard)
            else:
                await message.answer(text, reply_markup=keyboard)
        else:
            new_balance = get_balance(user_id)
            
            text = (
                f"😞 Вы проиграли\n\n"
                f"📊 Потеряно: {amount} монет\n"
                f"💎 Ваш баланс: {new_balance} монет\n\n"
                f"Выпало: {number_display} ({color})"
            )
            
            # Отправляем фото с текстом и кнопками одним сообщением
            photo_lose = None
            if os.path.exists(PHOTO_LOSE):
                photo_lose = PHOTO_LOSE
            elif os.path.exists(PHOTO_LOSE.replace(".jpg", ".png")):
                photo_lose = PHOTO_LOSE.replace(".jpg", ".png")
            elif os.path.exists(PHOTO_LOSE.replace(".jpg", ".jpeg")):
                photo_lose = PHOTO_LOSE.replace(".jpg", ".jpeg")
            
            if photo_lose:
                await message.answer_photo(FSInputFile(photo_lose), caption=text, reply_markup=keyboard)
            else:
                await message.answer(text, reply_markup=keyboard)
    else:
        # Не ставка — игнорируем, чтобы чат мог разговаривать
        return

# Игнорируем неизвестные команды, чтобы не мешать чату; /start уже обработан отдельным хендлером
@dp.message(lambda message: message.text and message.text.startswith('/') and not message.text.startswith('/start') and not message.text.startswith('/pay'))
async def handle_unknown_command(message: Message):
    return

# Топ игроков
@dp.callback_query(F.data == "top_players")
async def show_top_players(callback: CallbackQuery):
    await callback.answer()
    
    users = load_users()
    
    # Сортируем игроков по балансу
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('balance', 0), reverse=True)
    
    # Берем топ 10
    top_users = sorted_users[:10]
    
    if not top_users:
        text = "🏆 Топ игроков\n\n" \
               "Пока нет игроков в системе."
    else:
        text = "🏆 ТОП ИГРОКОВ\n\n"
        for i, (user_id, data) in enumerate(top_users, 1):
            balance = data.get('balance', 0)
            
            # Получаем имя пользователя из callback
            username = f"Игрок {user_id}"
            try:
                user_chat = await bot.get_chat(int(user_id))
                if user_chat.username:
                    username = f"@{user_chat.username}"
                elif user_chat.first_name:
                    username = user_chat.first_name
            except:
                pass
            
            # Эмодзи для места
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            text += f"{medal} {username}: {balance} монет\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    # Пытаемся отправить с фото топ-листа
    photo_path = os.path.join(PHOTOS_DIR, "top_players.jpg")
    photo_exists = False
    
    if os.path.exists(photo_path):
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".png")):
        photo_path = photo_path.replace(".jpg", ".png")
        photo_exists = True
    elif os.path.exists(photo_path.replace(".jpg", ".jpeg")):
        photo_path = photo_path.replace(".jpg", ".jpeg")
        photo_exists = True
    
    # Удаляем старое сообщение и отправляем новое
    try:
        await callback.message.delete()
    except:
        pass
    
    if photo_exists:
        await bot.send_photo(callback.from_user.id, FSInputFile(photo_path), caption=text, reply_markup=keyboard)
    else:
        await bot.send_message(callback.from_user.id, text, reply_markup=keyboard)

# Админ панель
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа к админ панели!", show_alert=True)
        return
    
    users = load_users()
    total_users = len(users)
    
    # Получаем статистику
    total_balance = sum(user_data.get('balance', 0) for user_data in users.values())
    
    text = (
        f"🔧 АДМИН ПАНЕЛЬ\n\n"
        f"📊 Статистика:\n"
        f"👥 Всего игроков: {total_users}\n"
        f"💰 Общий баланс: {total_balance} монет\n\n"
        f"Выберите действие:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все игроки", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="admin_change_balance")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_menu")]
    ])
    
    # Убираем фото из админ панели
    await callback.message.edit_text(text, reply_markup=keyboard)
    
    await callback.answer()

# Просмотр всех игроков (админ)
@dp.callback_query(F.data == "admin_all_users")
async def admin_all_users(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа!", show_alert=True)
        return
    
    users = load_users()
    
    if not users:
        text = "📋 СПИСОК ИГРОКОВ\n\nПока нет игроков."
    else:
        text = "📋 СПИСОК ВСЕХ ИГРОКОВ\n\n"
        # Сортируем по балансу
        sorted_users = sorted(users.items(), key=lambda x: x[1].get('balance', 0), reverse=True)
        
        for user_id_str, data in sorted_users:
            balance = data.get('balance', 0)
            
            username = f"ID: {user_id_str}"
            try:
                user_chat = await bot.get_chat(int(user_id_str))
                if user_chat.username:
                    username = f"@{user_chat.username} ({user_id_str})"
                elif user_chat.first_name:
                    username = f"{user_chat.first_name} ({user_id_str})"
            except:
                pass
            
            text += f"👤 {username}: {balance} монет\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Админ панель", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Изменить баланс пользователя
@dp.callback_query(F.data == "admin_change_balance")
async def admin_change_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id != ADMIN_ID:
        await callback.answer("❌ У вас нет доступа!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 ИЗМЕНИТЬ БАЛАНС\n\n"
        "Для изменения баланса пользователя отправьте сообщение в формате:\n"
        "`ID_пользователя сумма`\n\n"
        "Пример: `123456789 5000`\n\n"
        "Для отмены отправьте /start"
    )
    await callback.answer()

async def main():
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

