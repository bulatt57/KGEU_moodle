import re
import requests
import json
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import os

API_TOKEN = '7865333406:AAH24rbw85Y4qmCSrsGGNlEkfP5cRFN5ZmI'
JSON_FILE = 'user_data.json'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

user_sessions = {}
login_url = "https://lms.kgeu.ru/login/index.php"

back_button = KeyboardButton(text='Назад')
new_user_button = KeyboardButton(text='Новый пользователь')
auth_user_button = KeyboardButton(text='Авторизация по данным')
my_courses_button = KeyboardButton(text="Мои курсы")

def load_user_data():
    try:
        with open(JSON_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_data(data):
    with open(JSON_FILE, 'w') as file:
        json.dump(data, file, indent=2)

class LoginForm(StatesGroup):
    waiting_for_username = State()
    waiting_for_password = State()

class CourseParsingForm(StatesGroup):
    waiting_course_selection = State()
    waiting_link_selection = State()

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "username": "", "password": "", "payload": None,
            "courses_dict": {}, "session": requests.Session(),
            "keyboard": [new_user_button, auth_user_button]
        }
    builder = ReplyKeyboardBuilder()
    builder.add(*user_sessions[user_id]["keyboard"])
    await message.answer("Привет! Выберите опцию:", reply_markup=builder.as_markup(resize_keyboard=True))

@router.message(lambda message: message.text == 'Новый пользователь')
async def handle_new_user(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    user_sessions[user_id] = {
        "username": "", "password": "", "payload": None,
        "courses_dict": {}, "session": requests.Session(),
        "keyboard": [back_button]
    }
    await message.answer("Введите логин Moodle:")
    await state.set_state(LoginForm.waiting_for_username)

@router.message(LoginForm.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    username = message.text.strip()
    user_sessions[user_id]["username"] = username
    await message.answer("Введите пароль Moodle:")
    await state.set_state(LoginForm.waiting_for_password)

@router.message(LoginForm.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    password = message.text.strip()
    user_sessions[user_id]["password"] = password

    try:
        session = user_sessions[user_id]["session"]
        login_page = session.get(login_url)
        soup = BeautifulSoup(login_page.content, 'html.parser')
        logintoken = soup.find('input', {'name': 'logintoken'})['value']

        payload = {
            'username': user_sessions[user_id]["username"],
            'password': user_sessions[user_id]["password"],
            'logintoken': logintoken
        }

        response = session.post(login_url, data=payload)
        if "Выход" in response.text:
            user_sessions[user_id]["payload"] = payload
            user_data = load_user_data()
            user_data[user_id] = {
                "username": user_sessions[user_id]["username"],
                "password": user_sessions[user_id]["password"]
            }
            save_user_data(user_data)
            await message.answer("✅ Авторизация успешна!")
            user_sessions[user_id]["keyboard"] = [back_button, my_courses_button]
            await show_main_menu(message)
        else:
            await message.answer("❌ Ошибка авторизации. Проверьте данные.")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    finally:
        await state.clear()

@router.message(lambda message: message.text == 'Авторизация по данным')
async def handle_auth(message: types.Message):
    user_id = str(message.from_user.id)
    user_data = load_user_data()
    if user_id in user_data:
        try:
            session = requests.Session()
            login_page = session.get(login_url)
            soup = BeautifulSoup(login_page.content, 'html.parser')
            logintoken = soup.find('input', {'name': 'logintoken'})['value']

            payload = {
                'username': user_data[user_id]['username'],
                'password': user_data[user_id]['password'],
                'logintoken': logintoken
            }

            response = session.post(login_url, data=payload)
            if "Выход" in response.text:
                user_sessions[user_id] = {
                    "username": user_data[user_id]['username'],
                    "password": user_data[user_id]['password'],
                    "payload": payload,
                    "session": session,
                    "keyboard": [back_button, my_courses_button]
                }
                await message.answer("✅ Авторизация успешна!")
                await show_main_menu(message)
            else:
                await message.answer("❌ Ошибка авторизации. Проверьте данные.")
        except Exception as e:
            await message.answer(f"⚠️ Ошибка: {str(e)}")
    else:
        await message.answer("🔍 Данные для авторизации не найдены.")

async def show_main_menu(message: types.Message):
    user_id = str(message.from_user.id)
    builder = ReplyKeyboardBuilder()
    builder.add(*user_sessions[user_id]["keyboard"])
    await message.answer("Выберите действие:", reply_markup=builder.as_markup(resize_keyboard=True))

@router.message(lambda message: message.text == 'Мои курсы')
async def handle_my_courses(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    url = "https://lms.kgeu.ru/"
    try:
        session = user_sessions[user_id]["session"]
        response = session.get(url)
        soup = BeautifulSoup(response.text, "lxml")

        courses = soup.find_all("div", class_=re.compile("coursebox"))
        user_sessions[user_id]["courses_dict"] = {}
        course_order = []
        for course in courses:
            course_name_element = course.find(class_=re.compile(r'coursename'))
            if course_name_element:
                course_link = course_name_element.find('a')
                if course_link:
                    course_name = course_link.text.strip()
                    course_url = course_link.get('href')
                    user_sessions[user_id]["courses_dict"][course_name] = course_url
                    course_order.append(course_name)

        if not course_order:
            await message.answer("📭 У вас нет активных курсов")
            return

        await state.update_data(course_order=course_order)
        course_list = "\n".join([f"{idx}. {name}" for idx, name in enumerate(course_order, 1)])
        await message.answer(f"📚 Ваши курсы:\n{course_list}\n🔢 Введите номер курса для просмотра:")
        await state.set_state(CourseParsingForm.waiting_course_selection)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@router.message(CourseParsingForm.waiting_course_selection)
async def process_course_selection(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    try:
        data = await state.get_data()
        course_order = data.get("course_order", [])
        choice = int(message.text) - 1

        if 0 <= choice < len(course_order):
            course_name = course_order[choice]
            course_url = user_sessions[user_id]["courses_dict"][course_name]
            session = user_sessions[user_id]["session"]
            response = session.get(course_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            sections = soup.find_all('li', class_='section main clearfix')
            links = []
            content = f"📚 Содержимое курса «{course_name}»:\n\n"
            for idx, section in enumerate(sections, 1):
                activities = section.find_all(class_='activityinstance')
                for act in activities:
                    title = act.find(class_='instancename').text.strip()
                    link = act.find('a')['href']
                    links.append((title, link))
                    content += f"{len(links)}. {title}\n"

            await state.update_data(links=links)
            await message.answer(content)
            await message.answer("🔢 Введите номер ссылки для обработки:")
            await state.set_state(CourseParsingForm.waiting_link_selection)
        else:
            await message.answer("❌ Неверный номер курса")

    except ValueError:
        await message.answer("🔢 Пожалуйста, введите число!")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@router.message(CourseParsingForm.waiting_link_selection)
async def process_link_selection(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    try:
        data = await state.get_data()
        links = data.get("links", [])
        choice = int(message.text) - 1

        if 0 <= choice < len(links):
            title, url = links[choice]
            session = user_sessions[user_id]["session"]
            final_url = get_final_url(session, url)

            if 'moodle' in final_url.lower():
                await message.answer("❌ Ошибка: это не внешний сайт, а внутренний раздел Moodle.")
            else:
                if final_url.endswith('.pdf'):
                    await send_pdf_file(message, session, final_url, title)
                else:
                    await send_external_link(message, final_url, title)
        else:
            await message.answer("❌ Неверный номер ссылки")

    except ValueError:
        await message.answer("🔢 Пожалуйста, введите число!")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    await state.clear()

def get_final_url(session, url):
    try:
        response = session.head(url, allow_redirects=True)
        return response.url
    except Exception:
        try:
            response = session.get(url, allow_redirects=True)
            return response.url
        except Exception:
            return url

async def send_pdf_file(message: types.Message, session, pdf_url, title):
    try:
        response = session.get(pdf_url)
        if response.status_code == 200:
            pdf_content = response.content
            with open("temp.pdf", "wb") as f:
                f.write(pdf_content)
            with open("temp.pdf", "rb") as f:
                await bot.send_document(message.chat.id, f, caption=f"📄 {title}")
            os.remove("temp.pdf")
        else:
            await message.answer(f"❌ Не удалось скачать PDF-файл: {pdf_url}")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при отправке PDF: {str(e)}")

async def send_external_link(message: types.Message, link, title):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Открыть сайт", url=link)]
    ])
    await message.answer(f"🔗 {title}:", reply_markup=keyboard)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
