import asyncio
import logging
import json
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Актуальний токен бота та ID чату менеджерів
API_TOKEN = '8795191412:AAFVg6NZGR5jb9b9rDvhfBRP6x4jZ1-XYOs'
CHAT_ID_MANAGERS = '1840124533'

# Сторінка меню на GitHub Pages
WEB_APP_URL = "https://rainbowbrie7.github.io/Artcafe_delivery_bot/index.html"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Тимчасове сховище для замовлень в пам'яті (щоб уникнути багів з FSM)
USER_ORDERS = {}

class OrderStates(StatesGroup):
    waiting_for_floor = State()
    waiting_for_apartment = State()
    waiting_for_phone = State()
    waiting_for_promo = State()
    waiting_for_payment = State()

# 1. Головне меню при запуску бота (/start)
@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    await state.clear()
    inline_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🛒 Відкрити Меню Кав'ярні", web_app=types.WebAppInfo(url=WEB_APP_URL))]
        ]
    )
    await message.answer(
        f"Привіт, {message.from_user.first_name}! 👋\n\n"
        f"Раді вітати тебе у нашій кав'ярні! Обережно, тут найсмачніша випічка та кава! 🥐☕\n\n"
        f"Натискай кнопку нижче, щоб відкрити меню та зробити замовлення. Доставка прямо до дверей безкоштовна! 🚀",
        reply_markup=inline_keyboard
    )

# 2. Обробка вибору будинку через Inline-кнопки
@dp.callback_query(F.data.startswith("house_"))
async def process_house_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    house_name = callback.data.replace("house_", "")
    user_id = callback.from_user.id
    
    if user_id in USER_ORDERS:
        USER_ORDERS[user_id]['house'] = house_name
        
    await state.set_state(OrderStates.waiting_for_floor)
    await callback.message.answer("🏢 <b>Введіть номер вашого поверху:</b>", parse_mode="HTML")

# 3. Етап: Введення поверху
@dp.message(OrderStates.waiting_for_floor)
async def process_floor(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in USER_ORDERS:
        USER_ORDERS[user_id]['floor'] = message.text
        
    await message.answer("🚪 <b>Введіть номер квартири (або офісу):</b>", parse_mode="HTML")
    await state.set_state(OrderStates.waiting_for_apartment)

# 4. Етап: Введення квартири
@dp.message(OrderStates.waiting_for_apartment)
async def process_apartment(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in USER_ORDERS:
        USER_ORDERS[user_id]['apartment'] = message.text
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Поділитися контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("📞 <b>Натисніть кнопку нижче, щоб надіслати ваш номер телефону для зв'язку:</b>", parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_phone)

# 5. Етап: Отримання телефону
@dp.message(OrderStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.contact.phone_number if message.contact else message.text

    if user_id in USER_ORDERS:
        USER_ORDERS[user_id]['phone'] = phone
    
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Пропустити")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("🎟️ <b>Якщо у вас є промокод, напишіть його. Якщо немає — натисніть 'Пропустити':</b>", parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_promo)

# 6. Етап: Промокод
@dp.message(OrderStates.waiting_for_promo)
async def process_promo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    promo = message.text.strip().lower()
    
    if user_id in USER_ORDERS:
        USER_ORDERS[user_id]['promo'] = promo
    
    inline_pay = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💵 Готівка", callback_data="pay_cash")],
            [types.InlineKeyboardButton(text="💳 Безготівкова оплата", callback_data="pay_card")]
        ]
    )
    await message.answer("💳 <b>Виберіть зручний спосіб оплати:</b>", parse_mode="HTML", reply_markup=inline_pay)
    await state.set_state(OrderStates.waiting_for_payment)

# 7. Фінал: Обробка вибору оплати та генерація чеку
@dp.callback_query(F.data.startswith("pay_"))
async def process_payment_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    
    user_id = callback.from_user.id
    pay_method = "Готівка" if callback.data == "pay_cash" else "Безготівкова оплата"
    
    if user_id not in USER_ORDERS:
        await callback.message.answer("❌ Сесія замовлення застаріла. Будь ласка, відкрийте меню заново.")
        return

    order_data = USER_ORDERS[user_id]
    cart = order_data.get('cart', {})
    total_sum = order_data.get('total', 0)
    house = order_data.get('house', '-')
    floor = order_data.get('floor', '-')
    apartment = order_data.get('apartment', '-')
    phone = order_data.get('phone', '-')
    promo = order_data.get('promo', '')

    discount_text = ""
    if promo in ["navigator10", "navigator", "artcafe"]:
        discount = total_sum * 0.10
        total_sum = total_sum - discount
        discount_text = f"🔥 <b>Промокод застосовано:</b> -10% (-{discount} грн)\n"

    items_text = ""
    for item_id, item in cart.items():
        items_text += f"▪️ {item['name']} x{item['count']} — {item['price'] * item['count']} грн\n"

    info_payment_msg = ""
    if pay_method == "Безготівкова оплата":
        info_payment_msg = "ℹ️ <i>Після підтвердження замовлення менеджер надішле вам посилання на оплату в цей чат.</i>\n\n"

    # Встановлено ЖК НАВІГАТОР
    order_details = (
        f"📍 <b>Адреса доставки:</b> ЖК 'Навігатор'\n"
        f"🏠 <b>Будинок:</b> {house} | 🏢 <b>Поверх:</b> {floor} | 🚪 <b>Кв:</b> {apartment}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"💳 <b>Форма оплати:</b> {pay_method}\n\n"
        f"📦 <b>Склад замовлення:</b>\n"
        f"{items_text}\n"
        f"{discount_text}"
        f"💵 <b>Разом до сплати:</b> {total_sum} грн\n"
    )

    manager_report = f"🔔 <b>НОВЕ ЗАМОВЛЕННЯ З КАВ'ЯРНІ!</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n👤 <b>Клієнт:</b> {callback.from_user.full_name}\n{order_details}━━━━━━━━━━━━━━━━━━━━━"
    try:
        await bot.send_message(chat_id=CHAT_ID_MANAGERS, text=manager_report, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error sending to manager: {e}")

    client_report = f"🎉 <b>Ваше замовлення успішно прийнято!</b>\n\n{info_payment_msg}Менеджер вже передав чек бариста, а кур'єр готується до виїзду. Ваш чек 👇\n━━━━━━━━━━━━━━━━━━━━━\n{order_details}━━━━━━━━━━━━━━━━━━━━━\n\nДякуємо, що ви з нами! 😊"
    
    return_keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="🛒 Відкрити Меню Кав'ярні", web_app=types.WebAppInfo(url=WEB_APP_URL))]]
    )
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(client_report, parse_mode="HTML", reply_markup=return_keyboard)
    
    if user_id in USER_ORDERS:
        del USER_ORDERS[user_id]


# ЗАПУСК ВЕБ-СЕРВЕРУ
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    from aiohttp import web
    
    async def web_order_handler(request):
        try:
            data = await request.json()
            logging.info(f"Received order: {data}")
            
            user_id = int(data['user_id'])
            first_name = data.get('first_name', 'Клієнт')
            order_content = data.get('order', {})
            
            USER_ORDERS[user_id] = {
                'cart': order_content.get('products', {}),
                'total': order_content.get('total', 0),
                'house': None,
                'floor': None,
                'apartment': None,
                'phone': None,
                'promo': None
            }
            
            inline_houses = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="🏠 Будинок 1", callback_data="house_1"),
                     types.InlineKeyboardButton(text="🏠 Будинок 3", callback_data="house_3")],
                    [types.InlineKeyboardButton(text="🏠 Будинок 3а", callback_data="house_3а"),
                     types.InlineKeyboardButton(text="🏠 Будинок 5", callback_data="house_5")]
                ]
            )
            
            await bot.send_message(
                chat_id=user_id, 
                text=f"🛒 <b>Замовлення зафіксовано!</b>\n\nПривіт, {first_name}! Виберіть номер вашого будинку в нашому <b>ЖК 'Навігатор'</b> для безкоштовної доставки прямо до дверей:",
                reply_markup=inline_houses,
                parse_mode="HTML"
            )
            
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
            return web.Response(text="OK", headers=headers)
            
        except Exception as e:
            logging.error(f"Error in web_order_handler: {e}")
            return web.Response(text="Error", status=500, headers={"Access-Control-Allow-Origin": "*"})

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

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
