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
from special_parsing_class import DualKeyDict
import asyncio

API_TOKEN = '7865333406:AAH24rbw85Y4qmCSrsGGNlEkfP5cRFN5ZmI'
JSON_FILE = 'user_data.json'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
storage = MemoryStorage()
router = Router()
dp.include_router(router)

user_sessions = {}
login_url = "https://lms.kgeu.ru/login/index.php"
search_url = "https://lms.kgeu.ru/course/search.php?search="

back_button = KeyboardButton(text='Назад')
new_user_button = KeyboardButton(text='Новый пользователь')
auth_user_button = KeyboardButton(text='Авторизация по данным')
my_courses_button = KeyboardButton(text="Мои курсы")
new_course_registration_button = KeyboardButton(text='Регистрация на новый курс moodle')

def load_user_data():
    try:
        with open(JSON_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_data(data):
    with open(JSON_FILE, 'w') as file:
        json.dump(data, file, indent=2)

def paginate_text(content):
    chars_per_page = 4000
    pages = []
    current_page = ""
    for line in content.split("\n"):
        if len(current_page) + len(line) + 1 > chars_per_page:
            pages.append(current_page)
            current_page = line
        else:
            current_page += ("\n" if current_page else "") + line
    if current_page:
        pages.append(current_page)
    return pages

def get_pagination_keyboard(current_page, total_pages):
    keyboard = []
    if current_page > 1:
        keyboard.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page:{current_page - 1}"))
    if current_page < total_pages:
        keyboard.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"page:{current_page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[keyboard])

class CourseFindForm(StatesGroup):
    waiting_for_course_name_to_find = State()

class CourseParsingForm(StatesGroup):
    waiting_for_course_name_to_parse = State()
    waiting_course_selection = State()

class CourseRegistrationForm(StatesGroup):
    waiting_for_course_name_or_id = State()
    waiting_for_course_selection = State()
    waiting_confirmation = State()

@router.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "username": "", "password": "", "payload": None,
            "courses_dict": None, "src_course": None,
            "section_course_dict": None, "session": requests.Session(),
            "keyboard": [new_user_button, auth_user_button]
        }
    builder = ReplyKeyboardBuilder()
    builder.add(*user_sessions[user_id]["keyboard"])
    await message.answer("Привет! Выберите опцию:", reply_markup=builder.as_markup(resize_keyboard=True))

@router.message(lambda message: message.text == 'Новый пользователь')
async def handle_new_user(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id] = {
        "username": "", "password": "", "payload": None,
        "courses_dict": None, "src_course": None,
        "section_course_dict": None, "session": requests.Session(),
        "keyboard": [back_button]
    }
    await message.answer("Введите логин Moodle:")

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
                    "keyboard": [back_button, my_courses_button, new_course_registration_button]
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
    try:
        session = user_sessions[user_id]["session"]
        response = session.get("https://lms.kgeu.ru/my/")
        soup = BeautifulSoup(response.text, 'html.parser')

        courses = soup.find_all('div', class_=re.compile(r'coursebox\b'))
        user_sessions[user_id]["courses_dict"] = DualKeyDict()
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

            content = ""
            sections = soup.find_all('li', class_='section main clearfix')
            for section in sections:
                activities = section.find_all(class_='activityinstance')
                for act in activities:
                    title = act.find(class_='instancename').text
                    link = act.find('a')['href']
                    link = f"{link}?sesskey={session.cookies.get('MoodleSession')}"
                    content += f"🔗 {title}: {link}\n"

            pages = paginate_text(content)
            await state.update_data(pages=pages)
            text = pages[0] if pages else "Нет содержимого для отображения."
            keyboard = get_pagination_keyboard(1, len(pages)) if len(pages) > 1 else None
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer("❌ Неверный номер курса")

    except ValueError:
        await message.answer("🔢 Пожалуйста, введите число!")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    await state.clear()

async def check_enrollment(session, course_url):
    response = session.get("https://lms.kgeu.ru/my/")
    soup = BeautifulSoup(response.text, 'html.parser')
    courses = soup.find_all('div', class_='coursebox')
    for course in courses:
        url = course.find('a')['href']
        if url == course_url:
            return True
    return False

@router.message(lambda message: message.text == 'Регистрация на новый курс moodle')
async def handle_course_registration(message: types.Message, state: FSMContext):
    await message.answer("🔍 Введите название курса или его ID для поиска:")
    await state.set_state(CourseRegistrationForm.waiting_for_course_name_or_id)

@router.message(CourseRegistrationForm.waiting_for_course_name_or_id)
async def process_course_registration(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    user_input = message.text.strip()

    if user_input.lower() == 'назад':
        await show_main_menu(message)
        await state.clear()
        return

    try:
        session = user_sessions[user_id]["session"]
        payload = user_sessions[user_id]["payload"]

        if user_input.isdigit():
            course_id = user_input
            course_url = f"https://lms.kgeu.ru/course/view.php?id={course_id}"
            response = session.get(course_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                course_name = soup.find('h1').text.strip() if soup.find('h1') else f"Курс с ID {course_id}"
                await state.update_data(course_url=course_url, course_name=course_name)
                await ask_for_enrollment(message, state)
            else:
                await message.answer("❌ Курс с таким ID не найден.")
                await state.clear()
            return

        search_response = session.get(f"{search_url}{user_input}")
        soup = BeautifulSoup(search_response.text, 'html.parser')
        courses = soup.find_all('div', class_='coursebox')

        if not courses:
            await message.answer("❌ Курсы не найдены.")
            await state.clear()
            return

        if len(courses) == 1:
            course_name = courses[0].find(class_=re.compile("coursename")).find('a').text
            course_url = courses[0].find(class_=re.compile("coursename")).find('a').get("href")
            await state.update_data(course_url=course_url, course_name=course_name)
            await ask_for_enrollment(message, state)
            return

        course_list = []
        for idx, course in enumerate(courses, 1):
            course_name = course.find(class_=re.compile("coursename")).find('a').text
            course_url = course.find(class_=re.compile("coursename")).find('a').get("href")
            course_list.append((idx, course_name, course_url))

        await state.update_data(course_list=course_list)
        courses_text = "\n".join([f"{idx}. {name}" for idx, name, _ in course_list])
        await message.answer(f"📚 Найдено несколько курсов:\n{courses_text}\n🔢 Введите номер курса для записи:")
        await state.set_state(CourseRegistrationForm.waiting_for_course_selection)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
        await state.clear()

@router.message(CourseRegistrationForm.waiting_for_course_selection)
async def process_course_selection(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    user_input = message.text.strip()

    if user_input.lower() == 'назад':
        await show_main_menu(message)
        await state.clear()
        return

    try:
        data = await state.get_data()
        course_list = data.get("course_list", [])

        if not course_list:
            await message.answer("❌ Ошибка: список курсов пуст.")
            await state.clear()
            return

        try:
            selection = int(user_input)
            if 1 <= selection <= len(course_list):
                _, course_name, course_url = course_list[selection - 1]
                await state.update_data(course_url=course_url, course_name=course_name)
                await ask_for_enrollment(message, state)
            else:
                await message.answer("❌ Неверный номер курса. Попробуйте снова.")
        except ValueError:
            await message.answer("🔢 Пожалуйста, введите номер курса цифрами.")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
        await state.clear()

async def ask_for_enrollment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    course_name = data.get("course_name", "курс")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="enroll_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="enroll_no")]
    ])
    await message.answer(f"📝 Вы хотите записаться на курс «{course_name}»?", reply_markup=keyboard)
    await state.set_state(CourseRegistrationForm.waiting_confirmation)

@router.callback_query(lambda c: c.data in ["enroll_yes", "enroll_no"])
async def handle_enrollment_decision(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = str(callback_query.from_user.id)
    data = await state.get_data()
    course_url = data.get("course_url")
    course_name = data.get("course_name", "курс")

    if callback_query.data == "enroll_yes":
        try:
            session = user_sessions[user_id]["session"]
            course_page = session.get(course_url)
            soup = BeautifulSoup(course_page.text, 'html.parser')

            enroll_form = soup.find('form', {'action': re.compile(r'enrol/index\.php')})
            if not enroll_form:
                await callback_query.message.answer("❌ Не удалось найти форму записи на курс.")
                return

            form_action = enroll_form.get('action')
            form_data = {}
            for input_tag in enroll_form.find_all('input'):
                input_name = input_tag.get('name')
                input_value = input_tag.get('value')
                if input_name:
                    form_data[input_name] = input_value

            enroll_url = f"https://lms.kgeu.ru{form_action}" if form_action.startswith('/') else form_action
            response = session.post(enroll_url, data=form_data)

            if response.status_code == 200:
                if await check_enrollment(session, course_url):
                    await callback_query.message.answer(f"✅ Вы успешно записаны на курс «{course_name}»!")
                else:
                    await callback_query.message.answer("❌ Не удалось записаться на курс. Попробуйте позже.")
            else:
                await callback_query.message.answer("⚠️ Ошибка при отправке запроса")

        except Exception as e:
            await callback_query.message.answer(f"⚠️ Ошибка: {str(e)}")
    else:
        await callback_query.message.answer("🚫 Запись на курс отменена.")

    await state.clear()

@router.message(Command("reset"))
async def handle_reset(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions.pop(user_id, None)
    await message.answer("🔄 Сессия сброшена. Используйте /start для начала.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
