import re
import requests
import json
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from special_parsing_class import DualKeyDict
import asyncio

API_TOKEN = '7865333406:AAH24rbw85Y4qmCSrsGGNlEkfP5cRFN5ZmI'
JSON_FILE = 'user_data.json'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Словарь для хранения сессий пользователей
user_sessions = {}

login_url = "https://lms.kgeu.ru/login/index.php"

# Создание кнопок и клавиатуры
back_button = KeyboardButton(text='Назад')
new_user_button = KeyboardButton(text='Новый пользователь')
auth_user_button = KeyboardButton(text='Авторизация по данным')

keyboard_builder = ReplyKeyboardBuilder()
keyboard_builder.add(back_button).add(new_user_button).add(auth_user_button)
main_menu = keyboard_builder.as_markup(resize_keyboard=True)

def load_user_data():
    try:
        with open(JSON_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_user_data(data):
    with open(JSON_FILE, 'w') as file:
        json.dump(data, file)


user_data = load_user_data()


@router.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None,
                                  "src_course": None, "section_course_dict": None, "session": requests.Session()}
    await message.reply("Привет! Выберите опцию ниже или введите логин:", reply_markup=main_menu)


@router.message(lambda message: message.text == 'Новый пользователь')
async def new_user(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None, "src_course": None,
                              "section_course_dict": None, "session": requests.Session()}
    await message.reply("Введите ваш логин:")


@router.message(lambda message: message.text == 'Авторизация по данным')
async def auth_by_data(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id in user_data:
        user_sessions[user_id] = {"username": user_data[user_id]['username'],
                                  "password": user_data[user_id]['password'], "payload": None, "courses_dict": None,
                                  "src_course": None, "section_course_dict": None, "session": requests.Session()}
        await message.reply("Данные найдены. Авторизуюсь на сайте...")
        await authenticate_user(message)
    else:
        await message.reply(
            "Данные для авторизации не найдены. Пожалуйста, создайте нового пользователя или введите логин и пароль.",
            reply_markup=main_menu)


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

        await message.reply('Успешная авторизация')
        await display_courses(message, response)
    else:
        await message.reply(
            'Не удалось авторизоваться. Пожалуйста, проверьте ваш логин и пароль или используйте команду /reset для перезапуска.')


@router.message(Command("reset"))
async def reset_bot(message: types.Message):
    user_id = str(message.from_user.id)
    user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None, "src_course": None,
                              "section_course_dict": None, "session": requests.Session()}
    await message.reply("Бот сброшен. Введите ваш логин или выберите опцию ниже:", reply_markup=main_menu)


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
        f"Вот список доступных курсов:\n\n{course_list}\n\nВведите название курса или ключевое слово, чтобы перейти к нему (или 'Назад' для возврата):",
        reply_markup=main_menu)


@router.message(lambda message: user_sessions[str(message.from_user.id)]["courses_dict"])
async def choose_course(message: types.Message):
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
            f"Найдено несколько курсов с подобным названием:\n\n{matched_list}\n\nУточните название или выберите из списка (или 'Назад' для возврата):",
            reply_markup=main_menu)
        return
    else:
        await message.reply(
            f'Курс, содержащий в названии "{string_course}", не найден. Попробуйте еще раз (или введите "Назад" для возврата):',
            reply_markup=main_menu)
        return

    # Парсинг секций в курсе
    in_courses = user_sessions[user_id]["session"].post(user_sessions[user_id]["src_course"],
                                                        data=user_sessions[user_id]["payload"])
    soup = BeautifulSoup(in_courses.text, "lxml")
    section_course = soup.find('ul', class_="topics").find_all('li', class_="section main clearfix")

    # Создание словаря с секциями и содержимым секций
    user_sessions[user_id]["section_course_dict"] = DualKeyDict()
    count = 1
    for section in section_course:
        key_section = section.find("span", class_="hidden sectionname").text
        material = DualKeyDict()
        count2 = 1
        for item in section.find_all(class_="activityinstance"):
            instancename = item.find(class_="instancename").text
            link = item.find("a").get("href")
            material[(str(count2), instancename)] = link
            count2 += 1
        user_sessions[user_id]["section_course_dict"][(str(count), key_section)] = material
        count += 1

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
