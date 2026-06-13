import asyncio
import logging
import json
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Найновіший актуальний токен бота та ID чату менеджерів
API_TOKEN = '8795191412:AAFVg6NZGR5jb9b9rDvhfBRP6x4jZ1-XYOs'
CHAT_ID_MANAGERS = '1840124533'

# Нова сторінка меню, яка тепер розміщена на GitHub Pages
WEB_APP_URL = "https://rainbowbrie7.github.io/Artcafe_delivery_bot/index.html"

# Ініціалізація бота та диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Включаємо логування, щоб бачити все в консолі Render
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
        f"Привіт, {message.from_user.first_name}! 👋\n\n"
        f"Раді вітати тебе у нашій кав'ярні! Обережно, тут найсмачніша випічка та кава у всьому ЖК! 🥐☕\n\n"
        f"Натискай кнопку нижче, щоб відкрити меню та зробити замовлення. Доставка прямо до дверей безкоштовна! 🚀",
        reply_markup=inline_keyboard
    )

# 2. Резервна обробка корзини (якщо кошик прилетить через стандартний метод Telegram)
@dp.message(F.web_app_data)
async def handle_web_app_data(message: types.Message, state: FSMContext):
    try:
        raw_data = message.web_app_data.data
        order_json = json.loads(raw_data)
        await state.update_data(cart=order_json['products'], total=order_json['total'])
        
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Будинок 1"), types.KeyboardButton(text="Будинок 3")],
                [types.KeyboardButton(text="Будинок 3а"), types.KeyboardButton(text="Будинок 5")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("📍 Чудово! Виберіть номер вашого будинку в нашому ЖК:", reply_markup=keyboard)
        await state.set_state(OrderStates.waiting_for_house)
    except Exception as e:
        logging.error(f"Error in handle_web_app_data: {e}")
        await message.answer("❌ Виникла помилка при обробці кошика. Спробуйте ще раз.")

# 3. Етап: Вибір будинку
@dp.message(OrderStates.waiting_for_house)
async def process_house(message: types.Message, state: FSMContext):
    await state.update_data(house=message.text)
    await message.answer("🏢 Введіть номер вашого поверху:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(OrderStates.waiting_for_floor)

# 4. Етап: Введення поверху
@dp.message(OrderStates.waiting_for_floor)
async def process_floor(message: types.Message, state: FSMContext):
    await state.update_data(floor=message.text)
    await message.answer("🚪 Введіть номер квартири (або офісу):")
    await state.set_state(OrderStates.waiting_for_apartment)

# 5. Етап: Введення квартири
@dp.message(OrderStates.waiting_for_apartment)
async def process_apartment(message: types.Message, state: FSMContext):
    await state.update_data(apartment=message.text)
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Поділитися контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("📞 Натисніть кнопку нижче, щоб надіслати ваш номер телефону для зв'язку:", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_phone)

# 6. Етап: Отримання телефону
@dp.message(OrderStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text

    await state.update_data(phone=phone)
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Пропустити")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("🎟️ Якщо у вас є промокод, напишіть його. Якщо немає — натисніть 'Пропустити':", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_promo)

# 7. Фінал: Промокод, прорахунок знижки та надсилання замовлення
@dp.message(OrderStates.waiting_for_promo)
async def process_promo(message: types.Message, state: FSMContext):
    promo = message.text.strip().lower()
    user_data = await state.get_data()
    await state.clear()

    cart = user_data.get('cart', {})
    total_sum = user_data.get('total', 0)
    house = user_data.get('house')
    floor = user_data.get('floor')
    apartment = user_data.get('apartment')
    phone = user_data.get('phone')

    discount_text = ""
    if promo == "artcafe":
        discount = total_sum * 0.10
        total_sum = total_sum - discount
        discount_text = f"🔥 <b>Промокод застосовано:</b> -10% (-{discount} грн)\n"

    items_text = ""
    for item_id, item in cart.items():
        items_text += f"▪️ {item['name']} x{item['count']} — {item['price'] * item['count']} грн\n"

    order_details = (
        f"📍 <b>Адреса доставки:</b> ЖК 'Навігатор'\n"
        f"🏠 <b>Будинок:</b> {house} | 🏢 <b>Поверх:</b> {floor} | 🚪 <b>Кв:</b> {apartment}\n"
        f"📞 <b>Телефон:</b> {phone}\n\n"
        f"📦 <b>Склад замовлення:</b>\n"
        f"{items_text}\n"
        f"{discount_text}"
        f"💵 <b>Разом до сплати:</b> {total_sum} грн\n"
    )

    manager_report = f"🔔 <b>НОВЕ ЗАМОВЛЕННЯ З КАВ'ЯРНІ!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n👤 <b>Клієнт:</b> {message.from_user.full_name if message.from_user.full_name else 'Користувач'}\n{order_details}━━━━━━━━━━━━━━━━━━━━━"
    try:
        await bot.send_message(chat_id=CHAT_ID_MANAGERS, text=manager_report, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error sending to manager: {e}")

    client_report = f"🎉 <b>Ваше замовлення успішно прийнято!</b>\n\nМенеджер вже передав чек бариста, а кур'єр готується до виїзду. Ваш чек 👇\n━━━━━━━━━━━━━━━━━━━━━\n{order_details}━━━━━━━━━━━━━━━━━━━━━\n\nДякуємо, що ви з нами! 😊"
    
    return_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="🛒 Відкрити Меню Кав'ярні", web_app=types.WebAppInfo(url=WEB_APP_URL))]]
    )
    await message.answer(client_report, parse_mode="HTML", reply_markup=return_keyboard)


# НАДІЙНИЙ ЗАПУСК БОТА ТА МІНІ-ВЕБСЕРВЕРА З ДОЗВОЛОМ CORS ДЛЯ RENDER
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    from aiohttp import web
    
    # Головний обробник замовлень, який викликається сайтом через fetch
    async def web_order_handler(request):
        try:
            data = await request.json()
            user_id = data['user_id']
            first_name = data['first_name']
            order_content = data['order']
            
            # Встановлюємо FSM контекст для клієнта, зберігаємо кошик і переводимо на крок вибору будинку
            state_ctx = dp.fsm.resolve_context(bot, chat_id=user_id, user_id=user_id)
            await state_ctx.update_data(cart=order_content['products'], total=order_content['total'])
            await state_ctx.set_state(OrderStates.waiting_for_house)
            
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="Будинок 1"), types.KeyboardButton(text="Будинок 3")],
                    [types.KeyboardButton(text="Будинок 3а"), types.KeyboardButton(text="Будинок 5")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            # Пишемо користувачу в чат Телеграм
            await bot.send_message(
                chat_id=user_id, 
                text=f"🛒 <b>Замовлення зафіксовано!</b>\n\nПривіт, {first_name}! Виберіть номер вашого будинку в нашому ЖК для доставки:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Додаємо CORS заголовки відповіді
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
            return web.Response(text="OK", headers=headers)
            
        except Exception as e:
            logging.error(f"Error in web_order_handler: {e}")
            return web.Response(text="Error", status=500, headers={"Access-Control-Allow-Origin": "*"})

    # Обробник для попередніх CORS-запитів браузера (OPTIONS)
    async def web_options_handler(request):
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return web.Response(status=200, headers=headers)
        
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    app.router.add_post("/submit-order", web_order_handler)      
    app.router.add_options("/submit-order", web_options_handler)   
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    asyncio.create_task(site.start()) 

    # Починаємо забирати повідомлення з Telegram
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
