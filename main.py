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

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
storage = MemoryStorage() # для использования переменных между обрабработчиками
router = Router()
dp.include_router(router)

# Словарь для хранения сессий пользователей
user_sessions = {}

login_url = "https://lms.kgeu.ru/login/index.php"

# Создание кнопок и клавиатуры
back_button = KeyboardButton(text='Назад')
new_user_button = KeyboardButton(text='Новый пользователь')
auth_user_button = KeyboardButton(text='Авторизация по данным')
parse_course_button = KeyboardButton(text="Перейти к курсу")
new_course_registration_button = KeyboardButton(text='Регистрация на новый курс moodle')


def load_user_data():
    try:
        with open(JSON_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_user_data(data):
    with open(JSON_FILE, 'w') as file:
        json.dump(data, file)


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


user_data = load_user_data()


class CourseRegistrationForm(StatesGroup):
    waiting_for_course_name_to_registration = State()

class CourseParsingForm(StatesGroup):
    waiting_for_course_name_to_parse = State()


@router.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None,
                                  "src_course": None, "section_course_dict": None, "session": requests.Session(),
                                  "keyboard": [new_user_button, auth_user_button]}
    keyboard_builder = ReplyKeyboardBuilder()
    keyboard_builder.add(*user_sessions[user_id]["keyboard"])
    main_keyboard = keyboard_builder.as_markup(resize_keyboard=True)
    await message.reply("Привет! Выберите опцию ниже или введите логин:", reply_markup=main_keyboard)



@router.message(lambda message: message.text == 'Новый пользователь')
async def new_user(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None, "src_course": None,
                              "section_course_dict": None, "session": requests.Session(),
                              "keyboard": [new_user_button, auth_user_button]}
    await message.reply("Введите ваш логин:")


@router.message(lambda message: message.text == 'Авторизация по данным')
async def auth_by_data(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id in user_data:
        user_sessions[user_id] = {"username": user_data[user_id]['username'],
                                  "password": user_data[user_id]['password'], "payload": None, "courses_dict": None,
                                  "src_course": None, "section_course_dict": None, "session": requests.Session(),
                                  "keyboard": [new_user_button, auth_user_button]}
        await message.reply("Данные найдены. Авторизуюсь на сайте...")
        await authenticate_user(message)
    else:
        await message.reply(
            "Данные для авторизации не найдены. Пожалуйста, создайте нового пользователя или введите логин и пароль.",)


async def authenticate_user(message: types.Message):
    user_id = str(message.from_user.id)

    # Получение страницы входа для извлечения токена
    login_page = user_sessions[user_id]["session"].get(login_url)
    login_soup = BeautifulSoup(login_page.content, 'html.parser')
    logintoken = login_soup.find('input', {'name': 'logintoken'})['value']

    # Данные авторизации
    user_sessions[user_id]["payload"] = {
        'username': user_sessions[user_id]["username"],
        'password': user_sessions[user_id]["password"],
        'logintoken': logintoken
    }

    # Авторизация
    response = user_sessions[user_id]["session"].post(login_url, data=user_sessions[user_id]["payload"])

    # Проверка авторизации
    if "Выход" in response.text:
        # Сохранение данных в JSON-файл
        user_data[user_id] = {'username': user_sessions[user_id]["username"],
                              'password': user_sessions[user_id]["password"]}
        save_user_data(user_data)
        if back_button not in user_sessions[user_id]["keyboard"]:
            user_sessions[user_id]["keyboard"].append(back_button)
        if parse_course_button not in user_sessions[user_id]["keyboard"]:
            user_sessions[user_id]["keyboard"].append(parse_course_button)
        if new_course_registration_button not in user_sessions[user_id]["keyboard"]:
            user_sessions[user_id]["keyboard"].append(new_course_registration_button)
        keyboard_builder = ReplyKeyboardBuilder()
        keyboard_builder.add(*user_sessions[user_id]["keyboard"])
        keyboard_builder.adjust(3)
        main_keyboard = keyboard_builder.as_markup(resize_keyboard=True)
        await message.reply('Успешная авторизация', reply_markup=main_keyboard)
        await display_courses(message, response)
    else:
        await message.reply(
            'Не удалось авторизоваться. Пожалуйста, проверьте ваш логин и пароль или используйте команду /reset для перезапуска.')


@router.message(Command("reset"))
async def reset_bot(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None, "src_course": None,
                              "section_course_dict": None, "session": requests.Session(), "keyboard": [new_user_button, auth_user_button]}
    keyboard_builder = ReplyKeyboardBuilder()
    keyboard_builder.add(*user_sessions[user_id]["keyboard"])
    main_keyboard = keyboard_builder.as_markup(resize_keyboard=True)
    await message.reply("Бот сброшен. Введите ваш логин или выберите опцию ниже:", reply_markup=main_keyboard)


@router.message(lambda message: not user_sessions[str(message.from_user.id)]["username"])
async def get_username(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id]["username"] = message.text
    await message.reply("Спасибо! Теперь введите ваш пароль:")


@router.message(lambda message: not user_sessions[str(message.from_user.id)]["password"])
async def get_password(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id]["password"] = message.text
    await message.reply("Спасибо! Авторизуюсь на сайте...")

    await authenticate_user(message)


async def display_courses(message: types.Message, response):
    user_id = str(message.from_user.id)
    soup = BeautifulSoup(response.text, "lxml")
    courses = soup.find_all("div", class_=re.compile("coursebox clearfix"))

    # Создание словаря с курсами и названиями
    user_sessions[user_id]["courses_dict"] = DualKeyDict()
    for course in courses:
        course_name = course.find(class_=re.compile("coursename")).find('a').text
        course_url = course.find(class_=re.compile("coursename")).find('a').get("href")
        user_sessions[user_id]["courses_dict"][course_name] = course_url

    course_list = "\n".join(course_name[0] if isinstance(course_name, tuple) else course_name for course_name in
                            user_sessions[user_id]["courses_dict"]._store.keys())
    await message.reply(
        f"Вот список доступных курсов:\n\n{course_list}\n\nВыберите опцию ниже для продолжения:")


@router.message(lambda message: message.text == 'Перейти к курсу')
async def new_user(message: types.Message, state: FSMContext):
    await message.reply("Введите название курса или ключевое слово, чтобы перейти к нему (или 'Назад' для возврата):")
    await state.set_state(CourseParsingForm.waiting_for_course_name_to_parse)


@router.message(lambda message: user_sessions[str(message.from_user.id)]["courses_dict"], CourseParsingForm.waiting_for_course_name_to_parse)
async def choose_course(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    string_course = message.text

    if string_course.lower() == 'назад':
        await send_welcome(message)
        return

    matched_courses = [name for name in user_sessions[user_id]["courses_dict"]._store.keys() if
                       string_course in name[0]]

    if len(matched_courses) == 1:
        user_sessions[user_id]["src_course"] = user_sessions[user_id]["courses_dict"][matched_courses[0]]
    elif len(matched_courses) > 1:
        matched_list = "\n".join(course[0] if isinstance(course, tuple) else course for course in matched_courses)
        await message.reply(
            f"Найдено несколько курсов с подобным названием:\n\n{matched_list}\n\n"
            f"Уточните название или выберите из списка (или 'Назад' для возврата):",)
        return
    else:
        await message.reply(
            f'Курс, содержащий в названии "{string_course}", не найден. '
            f'Попробуйте еще раз (или введите "Назад" для возврата):',)
        return


    # Парсинг секций в курсе
    in_courses = user_sessions[user_id]["session"].post(user_sessions[user_id]["src_course"],
                                                        data=user_sessions[user_id]["payload"])
    soup = BeautifulSoup(in_courses.text, "lxml")
    section_course = soup.find('ul', class_="topics").find_all('li', class_="section main clearfix")

    # Создание словаря с секциями и содержимым секций
    user_sessions[user_id]["section_course_dict"] = DualKeyDict()
    count = 1
    course_content = ''
    for section in section_course:
        count2 = 0
        course_content += "\n\n"
        for item in section.find_all(class_="activityinstance"):
            instancename = item.find(class_="instancename").text
            link = item.find("a").get("href")
            count2 += 1
            course_content += f"{count2}. {instancename}. {link}\n"
        count += 1
    pages = paginate_text(course_content)
    await state.update_data(pages=pages)  # Сохраняем страницы в состоянии пользователя

    total_pages = len(pages)
    current_page = 1

    text = pages[current_page - 1]
    keyboard = get_pagination_keyboard(current_page, total_pages)
    await message.answer('Содержимое курса:')
    await message.answer(text, reply_markup=keyboard)
    await message.answer('Выберите опцию ниже для продолжения:')
    await state.set_state(None)


# Обработчик для нажатий на кнопки пагинации
@router.callback_query(lambda c: c.data and c.data.startswith("page:"))
async def handle_pagination(callback_query: types.CallbackQuery, state: FSMContext):
    content = await state.get_data()
    pages = content.get("pages")
    current_page = int(callback_query.data.split(":")[1])
    total_pages = len(pages)

    text = pages[current_page - 1]
    keyboard = get_pagination_keyboard(current_page, total_pages)

    await callback_query.message.edit_text(text, reply_markup=keyboard)


# обработчик нажатия на кнопку регистрации на новый курс
@router.message(lambda message: message.text == 'Регистрация на курс')
async def new_user(message: types.Message, state: FSMContext):
    await message.reply("Введите название или id курса на который необходимо зарегестрироваться")
    await state.set_state(CourseRegistrationForm.waiting_for_course_name_to_registration)

# обработчик ввода курса на который необходимо зарегестрироваться
@router.message(CourseRegistrationForm.waiting_for_course_name_to_registration)
async def process_course_name(message: types.Message, state: FSMContext):
    course_name = message.text
    user_id = str(message.from_user.id)
    response = user_sessions[user_id]["session"].post(login_url, data=user_sessions[user_id]["payload"])
    await message.reply(f"Вы ввели название курса: {course_name}")
    # Булат, пиши здесь регистрацию на курс
    await state.set_state(None)


async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
#     Azat тут 123
