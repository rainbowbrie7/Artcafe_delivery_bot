import asyncio
import logging
import json
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Токен бота та ID чату менеджерів
API_TOKEN = '8795191412:AAGSKwjh_HYtZrurDq4A-OikTYblBmBDl4Y'
CHAT_ID_MANAGERS = '1840124533'

# Актуальне посилання на твоє Web App меню
WEB_APP_URL = "https://irinamanik.com/cafe/index.html"

# Ініціалізація бота та диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Включаємо логування, щоб бачити помилки в консолі облака
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

class OrderStates(StatesGroup):
    waiting_for_house = State()
    waiting_for_floor = State()
    waiting_for_apartment = State()
    waiting_for_phone = State()
    waiting_for_promo = State()

# 1. Головне меню при запуску бота (/start)
@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    inline_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🛒 Відкрити Меню Кав'ярні", web_app=types.WebAppInfo(url=WEB_APP_URL))]
        ]
    )
    await message.answer(
        f"Привіт, {message.from_user.first_name}! ☕\n\n"
        "Раді вітати тебе у нашій кав'ярні.\n"
        "Натискай на кнопку нижче, щоб обрати улюблені напої та свіжу випічку з доставкою по ЖК!",
        reply_markup=inline_keyboard
    )

# 2. Обробка даних з Web App (Працює автоматично у режимі Polling)
@dp.message(F.web_app_data)
async def parse_web_app_data(message: types.Message, state: FSMContext):
    try:
        raw_data = message.web_app_data.data
        order_json = json.loads(raw_data)
        
        products = order_json.get("products", {})
        total_sum = order_json.get("total", 0)

        if not products:
            await message.answer("Здається, ваш кошик порожній. Спробуйте ще раз!")
            return

        await state.update_data(cart=products, total=total_sum)
        await state.set_state(OrderStates.waiting_for_house)

        house_keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="1"), types.KeyboardButton(text="3")],
                [types.KeyboardButton(text="3а"), types.KeyboardButton(text="5")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await message.answer(
            "🛵 <b>Увага!</b> Доставка здійснюється <u>тільки</u> по території <b>ЖК Навігатор (провулок Балтійський)</b>.\n\n"
            "Будь ласка, оберіть <b>номер вашого будинку</b> за допомогою кнопок нижче:",
            parse_mode="HTML",
            reply_markup=house_keyboard
        )
    except Exception as e:
        await message.answer("Ой, виникла помилка при зчитуванні кошика. Спробуйте ще раз.")

# 3. Обробка вибору будинку
@dp.message(OrderStates.waiting_for_house, F.text.in_({"1", "3", "3а", "5"}))
async def process_house_button(message: types.Message, state: FSMContext):
    await state.update_data(house=message.text)
    await state.set_state(OrderStates.waiting_for_floor)
    await message.answer(
        f"Будинок {message.text} прийнято. 👍\n"
        "Напишіть, будь ласка, ваш <b>поверх</b>:",
        parse_mode="HTML",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message(OrderStates.waiting_for_house)
async def process_house_invalid(message: types.Message):
    await message.answer("Будь ласка, оберіть будинок із запропонованих кнопок (1, 3, 3а або 5).")

# 4. Приймаємо поверх
@dp.message(OrderStates.waiting_for_floor)
async def process_floor(message: types.Message, state: FSMContext):
    await state.update_data(floor=message.text)
    await state.set_state(OrderStates.waiting_for_apartment)
    await message.answer("Дякую! Вкажіть <b>номер вашої квартири</b>:", parse_mode="HTML")

# 5. Приймаємо квартиру
@dp.message(OrderStates.waiting_for_apartment)
async def process_apartment(message: types.Message, state: FSMContext):
    await state.update_data(apartment=message.text)
    await state.set_state(OrderStates.waiting_for_phone)

    phone_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📱 Поділитися моїм номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "Тепер вкажіть <b>номер телефону</b> для зв'язку.\n\n"
        "Менеджер зателефонує для підтвердження, а також цей номер буде потрібен кур'єру.",
        parse_mode="HTML",
        reply_markup=phone_keyboard
    )

# 6. Приймаємо телефон
@dp.message(OrderStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text

    await state.update_data(phone=phone)
    await state.set_state(OrderStates.waiting_for_promo)

    promo_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="⏩ Пропустити")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "Маєте <b>промокод</b> на знижку? 🎁\n"
        "Введіть його нижче або натисніть кнопку «Пропустити»:",
        parse_mode="HTML",
        reply_markup=promo_keyboard
    )

# 7. Фінал
@dp.message(OrderStates.waiting_for_promo)
async def process_promo_and_finish(message: types.Message, state: FSMContext):
    promo_entered = message.text.strip().upper()
    user_data = await state.get_data()
    cart = user_data.get("cart", {})
    total_sum = int(user_data.get("total", 0))
    house = user_data.get("house", "")
    floor = user_data.get("floor", "")
    apartment = user_data.get("apartment", "")
    phone = user_data.get("phone", "")

    discount_text = ""
    if promo_entered == "NAVIGATOR10":
        discount = int(total_sum * 0.10)
        total_sum = total_sum - discount
        discount_text = f"🎁 <b>Промокод активовано:</b> NAVIGATOR10 (-{discount} грн)\n"

    items_text = ""
    for item_id, item_info in cart.items():
        name = item_info.get("name", "Товар")
        price = item_info.get("price", 0)
        count = item_info.get("count", 1)
        items_text += f"• {name} x{count} — {price * count} грн\n"

    order_details = (
        f"📍 <b>Адреса:</b> ЖК Навігатор, пров. Балтійський\n"
        f"🏠 <b>Будинок:</b> {house} | 🏢 <b>Поверх:</b> {floor} | 🚪 <b>Кв:</b> {apartment}\n"
        f"📞 <b>Телефон:</b> {phone}\n\n"
        f"📦 <b>Склад замовлення:</b>\n"
        f"{items_text}\n"
        f"{discount_text}"
        f"💵 <b>Разом до сплати:</b> {total_sum} грн\n"
    )

    manager_report = f"🔔 <b>НОВЕ ЗАМОВЛЕННЯ З КАВ'ЯРНІ!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n👤 <b>Клієнт:</b> {message.from_user.full_name}\n{order_details}━━━━━━━━━━━━━━━━━━━━━"
    try:
        await bot.send_message(chat_id=CHAT_ID_MANAGERS, text=manager_report, parse_mode="HTML")
    except:
        pass

    client_report = f"🎉 <b>Ваше замовлення успішно прийнято!</b>\n\nМенеджер вже передав чек бариста, а кур'єр готується до виїзду. Ваш чек 👇\n━━━━━━━━━━━━━━━━━━━━━\n{order_details}━━━━━━━━━━━━━━━━━━━━━\n\nДякуємо, що ви з нами! 😊"
    return_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="🛒 Відкрити Меню Кав'ярні", web_app=types.WebAppInfo(url=WEB_APP_URL))]]
    )

    await message.answer(text=client_report, parse_mode="HTML", reply_markup=return_keyboard)
    await state.clear()

# НАДЁЖНЫЙ ЗАПУСК В РЕЖИМЕ POLLING (ДЛЯ ОБЛАЧНЫХ ХОСТИНГОВ)
async def main():
    # Удаляем старый вебхук с хостинга, чтобы он не мешал принимать сообщения
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем бесконечный опрос
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())