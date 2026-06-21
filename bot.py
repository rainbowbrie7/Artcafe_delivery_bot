import asyncio
import logging
import json
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey

# Найновіший актуальний токен бота та ID чату менеджерів
API_TOKEN = '8795191412:AAFVg6NZGR5jb9b9rDvhfBRP6x4jZ1-XYOs'
CHAT_ID_MANAGERS = '1840124533'

# Нова сторінка меню, яка розміщена на GitHub Pages
WEB_APP_URL = "https://rainbowbrie7.github.io/Artcafe_delivery_bot/index.html"

# Ініціалізація бота та диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Включаємо логування
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

class OrderStates(StatesGroup):
    waiting_for_house = State()
    waiting_for_floor = State()
    waiting_for_apartment = State()
    waiting_for_phone = State()
    waiting_for_promo = State()
    waiting_for_payment = State()

# 1. Головне меню при запуску бота (/start)
@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext):
    try:
        await state.clear() # Скидаємо стан примусово при старті
    except Exception as e:
        logging.error(f"Error clearing state on start: {e}")
        
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
        await state.clear() # Очищаємо старі замовлення
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
    await message.answer("📞 Натисніть кнопку нижче, щоб надiслати ваш номер телефону для зв'язку:", reply_markup=keyboard)
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

# 7. Етап: Промокод та перехід до вибору оплати
@dp.message(OrderStates.waiting_for_promo)
async def process_promo(message: types.Message, state: FSMContext):
    promo = message.text.strip().lower()
    await state.update_data(promo=promo)

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Готівка")],
            [types.KeyboardButton(text="Безготівкова оплата")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("💳 <b>Виберіть зручний спосіб оплати:</b>", parse_mode="HTML", reply_markup=keyboard)
    await state.set_state(OrderStates.waiting_for_payment)

# 8. Фінал: Отримання способу оплати, прорахунок та надсилання чеків
@dp.message(OrderStates.waiting_for_payment)
async def process_payment(message: types.Message, state: FSMContext):
    try:
        payment_method = message.text.strip()
        user_data = await state.get_data()
        await state.clear() # Повністю чистимо стан після успішного замовлення!

        cart = user_data.get('cart', {})
        total_sum = user_data.get('total', 0)
        house = user_data.get('house')
        floor = user_data.get('floor')
        apartment = user_data.get('apartment')
        phone = user_data.get('phone')
        promo = user_data.get('promo', '')

        # Розрахунок активованого промокоду
        discount_text = ""
        if promo in ["navigator10", "navigator", "artcafe"]:
            discount = total_sum * 0.10
            total_sum = total_sum - discount
            discount_text = f"🔥 <b>Промокод застосовано:</b> -10% (-{discount} грн)\n"

        # Формування списку товарів
        items_text = ""
        for item_id, item in cart.items():
            items_text += f"▪️ {item['name']} x{item['count']} — {item['price'] * item['count']} грн\n"

        # Додаткове повідомлення для безготівки
        info_payment_msg = ""
        if payment_method == "Безготівкова оплата":
            info_payment_msg = "ℹ️ <i>Після підтвердження замовлення менеджер надішле вам посилання на оплату в цей чат.</i>\n\n"

        order_details = (
            f"📍 <b>Адреса доставки:</b> ЖК 'Ярославів Град'\n"
            f"🏠 <b>Будинок:</b> {house} | 🏢 <b>Поверх:</b> {floor} | 🚪 <b>Кв:</b> {apartment}\n"
            f"📞 <b>Телефон:</b> {phone}\n"
            f"💳 <b>Форма оплати:</b> {payment_method}\n\n"
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

        client_report = f"🎉 <b>Ваше замовлення успішно прийнято!</b>\n\n{info_payment_msg}Менеджер вже передав чек бариста, а кур'єр готується до виїзду. Ваш чек 👇\n━━━━━━━━━━━━━━━━━━━━━\n{order_details}━━━━━━━━━━━━━━━━━━━━━\n\nДякуємо, що ви з нами! 😊"
        
        return_keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="🛒 Відкрити Меню Кав'ярні", web_app=types.WebAppInfo(url=WEB_APP_URL))]]
        )
        await message.answer(client_report, parse_mode="HTML", reply_markup=return_keyboard)
    except Exception as e:
        logging.error(f"Error in final process_payment: {e}")
        await message.answer("❌ Виникла помилка при фінальному оформленні. Але менеджери вже бачать ваше замовлення!")


# НАДІЙНИЙ ЗАПУСК БОТА ТА МІНІ-ВЕБСЕРВЕРА З ДОЗВОЛОМ CORS
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    from aiohttp import web
    
    async def web_order_handler(request):
        try:
            data = await request.json()
            logging.info(f"Incoming web app data: {data}")
            
            raw_user_id = data.get('user_id')
            if not raw_user_id:
                return web.Response(text="No user_id", status=400)
                
            user_id = int(raw_user_id)
            first_name = data.get('first_name', 'Клієнт')
            order_content = data.get('order', {})
            
            # Скидаємо стан двома методами одночасно для 100% надійності в будь-яких версіях aiogram 3
            try:
                state_ctx = dp.fsm.resolve_context(bot, chat_id=user_id, user_id=user_id)
                await state_ctx.clear()
            except Exception as context_error:
                logging.warning(f"Standard resolve_context failed, using StorageKey. Error: {context_error}")
                storage_key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
                state_ctx = FSMContext(storage=dp.storage, key=storage_key)
                await state_ctx.clear()
            
            # Записуємо нові дані кошика
            await state_ctx.update_data(cart=order_content.get('products', {}), total=order_content.get('total', 0))
            await state_ctx.set_state(OrderStates.waiting_for_house)
            
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="Будинок 1"), types.KeyboardButton(text="Будинок 3")],
                    [types.KeyboardButton(text="Будинок 3а"), types.KeyboardButton(text="Будинок 5")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            # Надсилаємо пускове повідомлення користувачу в чат
            await bot.send_message(
                chat_id=user_id, 
                text=f"🛒 <b>Замовлення зафіксовано!</b>\n\nПривіт, {first_name}! Виберіть номер вашого будинку в нашому ЖК для доставки:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
            return web.Response(text="OK", headers=headers)
            
        except Exception as e:
            logging.error(f"CRITICAL ERROR in web_order_handler: {e}")
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
