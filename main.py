import re
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from special_parsing_class import DualKeyDict

API_TOKEN = '7865333406:AAH24rbw85Y4qmCSrsGGNlEkfP5cRFN5ZmI'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Словарь для хранения сессий пользователей
user_sessions = {}

login_url = "https://lms.kgeu.ru/login/index.php"

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None, "src_course": None, "section_course_dict": None, "session": requests.Session()}
    await message.reply("Привет! Введите ваш логин или используйте команду /reset для сброса и перезапуска:")

@dp.message_handler(commands=['reset'])
async def reset_bot(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id] = {"username": "", "password": "", "payload": None, "courses_dict": None, "src_course": None, "section_course_dict": None, "session": requests.Session()}
    await message.reply("Бот сброшен. Введите ваш логин:")

@dp.message_handler(lambda message: not user_sessions[message.from_user.id]["username"])
async def get_username(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]["username"] = message.text
    await message.reply("Спасибо! Теперь введите ваш пароль:")

@dp.message_handler(lambda message: not user_sessions[message.from_user.id]["password"])
async def get_password(message: types.Message):
    user_id = message.from_user.id
    user_sessions[user_id]["password"] = message.text
    await message.reply("Спасибо! Авторизуюсь на сайте...")

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
        await message.reply('Успешная авторизация')
        await display_courses(message, response)
    else:
        await message.reply('Не удалось авторизоваться. Пожалуйста, проверьте ваш логин и пароль или используйте команду /reset для перезапуска.')

async def display_courses(message: types.Message, response):
    user_id = message.from_user.id
    soup = BeautifulSoup(response.text, "lxml")
    courses = soup.find_all("div", class_=re.compile("coursebox clearfix"))

    # Создание словаря с курсами и названиями
    user_sessions[user_id]["courses_dict"] = DualKeyDict()
    for course in courses:
        course_name = course.find(class_=re.compile("coursename")).find('a').text
        course_url = course.find(class_=re.compile("coursename")).find('a').get("href")
        user_sessions[user_id]["courses_dict"][course_name] = course_url

    course_list = "\n".join(course_name[0] if isinstance(course_name, tuple) else course_name for course_name in user_sessions[user_id]["courses_dict"]._store.keys())
    await message.reply(f"Вот список доступных курсов:\n\n{course_list}\n\nВведите название курса или ключевое слово, чтобы перейти к нему (или 'назад' для возврата):")

@dp.message_handler(lambda message: 'courses_dict' in user_sessions[message.from_user.id])
async def choose_course(message: types.Message):
    user_id = message.from_user.id
    string_course = message.text
    matched_courses = [name for name in user_sessions[user_id]["courses_dict"]._store.keys() if string_course in name[0]]

    if len(matched_courses) == 1:
        user_sessions[user_id]["src_course"] = user_sessions[user_id]["courses_dict"][matched_courses[0]]
    elif len(matched_courses) > 1:
        matched_list = "\n".join(course[0] if isinstance(course, tuple) else course for course in matched_courses)
        await message.reply(f"Найдено несколько курсов с подобным названием:\n\n{matched_list}\n\nУточните название или выберите из списка (или 'назад' для возврата):")
        return
    else:
        await message.reply(f'Курс, содержащий в названии "{string_course}", не найден. Попробуйте еще раз (или введите "назад" для возврата):')
        return

    # Парсинг секций в курсе
    in_courses = user_sessions[user_id]["session"].post(user_sessions[user_id]["src_course"], data=user_sessions[user_id]["payload"])
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

    section_keys = user_sessions[user_id]["section_course_dict"].get_keys()
    await message.reply(f"Все ключи секций:\n\n{section_keys}\n\nВведите номер секции, чтобы перейти в нее (или 'назад' для возврата):")

@dp.message_handler(lambda message: 'section_course_dict' in user_sessions[message.from_user.id])
async def choose_section(message: types.Message):
    user_id = message.from_user.id
    section_number = message.text

    if section_number.lower() == 'назад':
        await display_courses(message, response)
        return

    selected_section = next((key for key in user_sessions[user_id]["section_course_dict"]._store if key[0] == section_number), None)
    if selected_section:
        section_content = user_sessions[user_id]["section_course_dict"][selected_section].format_items()
        await message.reply(f"\nСодержимое секции {section_number}:\n\n{section_content}\n\nВведите номер секции, чтобы перейти в нее (или 'назад' для возврата):")
    else:
        await message.reply("Секция не найдена. Попробуйте еще раз (или введите 'назад' для возврата):")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
