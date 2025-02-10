import os
import getpass
import json
from openai import OpenAI
import textwrap
import re
import json

from langchain_community.tools import DuckDuckGoSearchResults
from fake_useragent import UserAgent
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
import requests
from bs4 import BeautifulSoup
from langchain.callbacks import get_openai_callback
from openai import OpenAIError, AsyncOpenAI
from dotenv import load_dotenv


load_dotenv()

# Класс ProjectContext представляет контекст проекта, включая информацию о пользователе, проекте, историю диалогов и их краткое содержание.
class ProjectContext:
    def __init__(self, user, project):    #Инициализируем объект с данными о пользователе, проекте, истории диалога и краткое содержание диалога.
        self.user = user                  # информация о пользователе в виде словаря
        self.project = project            # информация о проекте в виде словаря.
        self.dialog_history = []          # представляет собой список сообщений.
        self.dialog_summary = ""          # краткое содержание всего диалога
        self.total_tokens = 0  # Новый атрибут для хранения общего числа токенов
        self.total_cost = 0.0  # Новый атрибут для хранения общей стоимости

# Функция update.
# Вызывается в двух местах: 1/При первоначальном приветствии консультанта в функции run_dialog.
# 2/Каждый раз при получении ответа от модели (generate_answer_dialog или generate_answer_dialog_search)
# Добавляет новую информацию (например, вопрос пользователя или ответ НК) в историю диалога (dialog_history) и
# вызывает обновление профиля проекта с помощью метода update_profile_with_gpt, используя новую информацию.

    def update(self, new_info):
        self.dialog_history.append(new_info)
        self.update_profile_with_gpt(new_info)

# Создаем функцию краткого содержания текущего диалога с помощью обращения к модели
# Сохраненный результат записывается в dialog_summary
# Вызывается внутри update_profile_with_gpt, чтобы обновить краткое содержание.

    def generate_summary(self):
        prompt = (f"Сделайте краткое саммари следующего диалога:\n{self.dialog_history}")

        messages = [
            {"role": "system", "content": "Вы — ИИ-консультант по проектам. Составьте краткое саммари следующего диалога."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
            )
            self.dialog_summary = response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Ошибка: {str(e)}")

# Обновляем профиль проекта на основе новой информации и текущего состояния проекта.
# Этот текст парсится потом с помощью from_text и обновляет данные внутри ProjectContext.
# Вызывается каждый раз, когда обновляется информация в диалоге. Вызов происходит в функции update

    def update_profile_with_gpt(self, new_info):
        self.generate_summary()
        prompt = (f"Обновите следующий профиль проекта на основе этой новой информации:\n{new_info}\n\n"
                  f"Профиль:\n{self.to_text()}\n\n"
                  f"Верните только обновленный профиль в виде простого текста.")

        messages = [
            {"role": "system", "content": "Вы — ИИ-консультант по проектам. Обновите профиль на основе следующей информации."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0,
            )
            answer_text = response.choices[0].message.content
            self.from_text(answer_text)

        except Exception as e:
            raise RuntimeError(f"Ошибка: {str(e)}")

# def to_text Преобразует текущую информацию о пользователе, проекте и истории диалогов в текстовый формат.
# Берет информацию о профиле проекта и истории диалога из внутренних данных объекта ProjectContext.
# Этот текст используется для хранения и передачи профиля проекта в другие функции.
# Вызывается в двух местах:
#1 В функции update_profile_with_gpt, чтобы передать текущий профиль в запрос для обновления.
#2 В функции generate_answer_dialog для формирования полного контекста диалога и профиля перед отправкой запроса в модель.

    def to_text(self):
        user_info = (f"Тип клиента: {self.user.get('type_user', 'N/A')}\n"
                     f"Контакт: {self.user.get('contact', 'N/A')}")
        project_info = (f"Тип проекта: {self.project.get('type', 'N/A')}\n"
                        f"Цель: {self.project.get('goal', 'N/A')}\n"
                        f"Текущая стадия: {self.project.get('current_stage', 'N/A')}\n"
                        f"Завершенные стадии: {', '.join(self.project.get('completed_stages', [])) or 'N/A'}\n"
                        f"Оставшиеся задачи: {', '.join(self.project.get('remaining_tasks', [])) or 'N/A'}\n"
                        f"План: {self.project.get('plan', 'N/A')}")
        return f"{user_info}\n{project_info}\nИстория диалога (саммари):\n{self.dialog_summary}"


# def from_text Парсит текстовую строку и восстанавливает из нее данные пользователя, проекта и историю диалогов и обновляет
# данные внутри ProjectContext,т.е. восстанавливает данные профиля из текстового формата. Вызывается для того, чтобы преобразовать текстовый ответ в формат данных, который можно
# использовать в объекте ProjectContext.
# Если диалог был прерван или нужно продолжить работу с проектом в другой сессии, контекст проекта восстанавливается из сохраненного файла с помощью from_text(). Это происходит в  функции load_profile()

    def from_text(self, text):
        user_type_match = re.search(r"Тип клиента: (.*)", text)
        contact_match = re.search(r"Контакт: (.*)", text)
        project_type_match = re.search(r"Тип проекта: (.*)", text)
        goal_match = re.search(r"Цель: (.*)", text)
        current_stage_match = re.search(r"Текущая стадия: (.*)", text)
        completed_stages_match = re.search(r"Завершенные стадии: (.*)", text)
        remaining_tasks_match = re.search(r"Оставшиеся задачи: (.*)", text)
        plan_match = re.search(r"План: (.*)", text)
        dialog_summary_match = re.search(r"История диалога \(саммари\):\n(.*)", text, re.DOTALL)
        dialog_history_match = re.search(r"Последние сообщения:\n(.*)", text, re.DOTALL)

        if user_type_match:
            self.user['type_user'] = user_type_match.group(1).strip()
        if contact_match:
            self.user['contact'] = contact_match.group(1).strip()
        if project_type_match:
            self.project['type'] = project_type_match.group(1).strip()
        if goal_match:
            self.project['goal'] = goal_match.group(1).strip()
        if current_stage_match:
            self.project['current_stage'] = current_stage_match.group(1).strip()
        if completed_stages_match:
            self.project['completed_stages'] = [stage.strip() for stage in completed_stages_match.group(1).split(",")]
        if remaining_tasks_match:
            self.project['remaining_tasks'] = [task.strip() for task in remaining_tasks_match.group(1).split(",")]
        if plan_match:
            self.project['plan'] = plan_match.group(1).strip()
        if dialog_summary_match:
            self.dialog_summary = dialog_summary_match.group(1).strip()
        if dialog_history_match:
            self.dialog_history = [entry.strip() for entry in dialog_history_match.group(1).strip().split("\n")]


# Сохраняем историю диалогов в файл dialog_history.txt. Это полезно для сохранения состояния диалога между сессиями или после завершения работы с программой.

    def save_dialog_history(self):
        with open("dialog_history.txt", "w", encoding='utf-8') as file:
            file.write("\n".join(self.dialog_history))

# Начальная информация о пользователе
user_info = {
    "type_user": "",
    "contact": ""
}

# Начальная информация о проекте
project_info = {
    "type": "",
    "goal": "",
    "current_stage": "",
    "completed_stages": [],
    "remaining_tasks": [],
    "plan": ""
}

# Инициализация контекста проекта
# context = ProjectContext(user_info, project_info)

import json
import os

# Функция для сохранения профиля
def save_profile(context):
    """Сохраняет профиль и историю диалога в файл."""
    try:
        # Формируем словарь для сохранения
        data = {
            "profile": context.to_text(),
            "dialog_history": context.dialog_history
        }
        with open("profile.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при сохранении профиля: {e}")

# Функция для загрузки профиля
def load_profile():
    """Загружает профиль и историю диалога из файла."""
    if os.path.exists("profile.json"):
        try:
            with open("profile.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                loaded_context = ProjectContext({}, {})
                loaded_context.from_text(data["profile"])
                loaded_context.dialog_history = data.get("dialog_history", [])
                return loaded_context
        except Exception as e:
            print(f"Ошибка при загрузке профиля: {e}")
    # Если файла нет или произошла ошибка, создаём новый контекст
    return ProjectContext(user_info, project_info)

# Функция для подсчета токенов и стоимости
def calculate_cost_and_tokens(response):
    prompt_tokens = response.usage.prompt_tokens
    completion_tokens = response.usage.completion_tokens
    total_tokens = response.usage.total_tokens

    if response.model == "gpt-4o":
        input_price, output_price = 5, 15
    else:  # "gpt-4o-mini"
        input_price, output_price = 0.15, 0.6

    price = (input_price * prompt_tokens / 1e6) + (output_price * completion_tokens / 1e6)

    return total_tokens, price

#### Агент-поисковик.
##### Шаг 1
# Модель для поисковика
web_model_name="gpt-4o-mini-2024-07-18"

# Функция для подсчета токенов и стоимости агента поисковика
def calculate_cost_and_tokens_web_agent(prompt_tokens, completion_tokens, web_model_name = web_model_name):

    if web_model_name == "gpt-4o":
        input_price, output_price = 5, 15
    else:  # "gpt-4o-mini"
        input_price, output_price = 0.15, 0.6

    price = (input_price * prompt_tokens / 1e6) + (output_price * completion_tokens / 1e6)
    total_tokens = prompt_tokens + completion_tokens

    return total_tokens, price

# Функция для парсинга сырых результатов поиска и извлечения ссылок
def parse_search_results(raw_results):
    pattern = r'\[snippet:.*?title:.*?link:\s(.*?)\]'
    links = re.findall(pattern, raw_results)
    # Очистка ссылок от возможных пробелов и символов новой строки
    cleaned_links = [link.strip() for link in links]
    return cleaned_links

# Функция для извлечения текстового содержимого веб-страницы по URL
def fetch_page_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0; +http://example.com/bot)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Проверка статуса ответа
        soup = BeautifulSoup(response.content, 'html.parser')
        # Извлечение текста из первых 15 параграфов, чтобы ограничить количество текста
        paragraphs = soup.find_all('p')[:15]
        text_content = "\n".join([p.get_text() for p in paragraphs])
        return text_content
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке {url}: {e}")
        return ""
    except Exception as e:
        print(f"Непредвиденная ошибка при обработке {url}: {e}")
        return ""

from duckduckgo_search import DDGS
from typing import List

def agent_web_search(search_query, web_model_name=web_model_name):
    #### ==== DDGS - DuckDuckGO Search ==== ####

    # Настройка User-Agent для маскировки запросов
    ua = UserAgent()
    session = requests.Session()
    session.headers.update({"User-Agent": ua.random})

    # Добавление уточнения к поисковому запросу
    search_query += ". Используемые библиотеки, фреймворки, примеры и URL ссылки на них"

    # Выполнение поиска с использованием DDGS
    try:
        with DDGS() as ddgs:
            raw_search_results = list(ddgs.text(
                search_query,
                region="wt-wt",  # Регион: всемирный
                safesearch="moderate",  # Умеренная фильтрация
                timelimit="y",  # Ограничение по времени: за год
                max_results=10  # Ограничение на количество результатов
            ))
    except Exception as e:
        print(f"Ошибка выполнения поиска через DDGS: {e}")
        return None, 0, 0

    print('--------------------------------------------------------------')
    print("\033[034mraw_search_results:\033[0m ", raw_search_results)
    print('--------------------------------------------------------------')

    # Извлечение ссылок из результатов поиска
    def parse_search_results_ddgs(results: List[dict]) -> List[str]:
        return [result.get("href") for result in results if "href" in result]

    extracted_links = parse_search_results_ddgs(raw_search_results)

    # Ограничение количества обрабатываемых ссылок
    max_links = 10
    limited_links = extracted_links[:max_links]

    # Извлечение содержимого всех страниц из списка ссылок
    pages_content = []
    for url in limited_links:
        try:
            content = fetch_page_content(url)
            if content:
                pages_content.append(content)
        except Exception as e:
            print(f"Ошибка загрузки содержимого из {url}: {e}")

    # Проверка наличия контента
    if not pages_content:
        print("Не удалось извлечь содержимое ни с одной страницы.")
        context = ""
    else:
        # Объединение содержимого всех страниц
        context = "\n\n".join(pages_content)


    #### ==== OpenAI ==== ####

    # Инициализация модели ChatOpenAI
    chat_model = ChatOpenAI(model_name=web_model_name, openai_api_key=openai_key)

    # Определение шаблона промпта
    template = """
    Дано следующее текстовое содержание, извлеки ответ на вопрос: "{query}".
    Если ответ не найден, ответь "не найден".

    Текст:
    <<<
    {context}
    >>>

    Ответ:
    """

    PROMPT = PromptTemplate(
        input_variables=["query", "context"],
        template=template,
    )

    # Создание последовательности для выполнения
    llm_sequence = PROMPT | chat_model

    # Использование get_openai_callback для получения информации о токенах
    with get_openai_callback() as cb:
        try:
            result = llm_sequence.invoke({
                "query": search_query,
                "context": context
            })
        except Exception as e:
            print(f"Ошибка выполнения последовательности LLM: {e}")
            return None, 0, 0

        print('=================================')
        print("Запрос в поисковик: ", search_query)
        print("Ответ поисковика: ", result)
        print('=================================')

        # Подсчет стоимости и токенов
        total_tokens, price = calculate_cost_and_tokens_web_agent(
            cb.prompt_tokens, cb.completion_tokens, web_model_name=web_model_name
        )

    return result, total_tokens, price


##### Шаг 2

    # Функция для генерации ответа в диалоге (С поисковиком)
def generate_answer_dialog_search(prompt, query, context, web_model_name=web_model_name ):
    input_text = f"информация о текущем профиле: {context.to_text()}\n\nИстория диалога:\n{' '.join(context.dialog_history)}\n\nТекущий вопрос: {query}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": input_text}
    ]

    response = client.chat.completions.create(
        model=web_model_name,
        messages=messages,
        temperature=0.1,
    )

    answer_text = response.choices[0].message.content
    total_tokens, price = calculate_cost_and_tokens(response)

    # Проверяем, нужно ли выполнить поиск в интернете
    if "Необходимо выполнить поиск в интернете" in answer_text:
        print('--------------------------------------------------------------')
        print("Обращение к поисковику", answer_text )
        print('--------------------------------------------------------------')
        web_serch_answer = ""

        # Извлекаем запрос для поиска из текста ответа
        # Регулярное выражение для поиска вопросов
        pattern = r'(?:Вопрос|Question):\s*(.*?)\s*(?=\d+\.\s|$)'
        # Используем re.findall для поиска всех совпадений
        questions = re.findall(pattern, answer_text)
        #print('--------------------------------------------------------------')
        #print("Вопросы ", questions )
        #print('--------------------------------------------------------------')

        # Запуск функции для каждого вопроса
        # Запуск функции для каждого вопроса и накопление результатов
        for i, question in enumerate(questions, 1):
            answer_from_web, total_tokens_web, price_web = agent_web_search(question)
            total_tokens += total_tokens_web
            price += price_web
            web_serch_answer += f"Ответ {i}. ({answer_from_web})\n"

        # Удаление последнего переноса строки
        web_serch_answer = web_serch_answer.strip()
        print('--------------------------------------------------------------')
        print("Ответы ", web_serch_answer )
        print('--------------------------------------------------------------')

        input_text = f"информация о текущем профиле: {context.to_text()}\n\nИстория диалога:\n{' '.join(context.dialog_history)}.\n\nТекущий вопрос: {query}. \n\nКонсультант: {answer_text}\n\n Ответ поисковика : {web_serch_answer}.\n\nОтветь на текущий вопрос."

        context.update(f"\n\nКонсультант: {answer_text}\n\n Ответ поисковика : {web_serch_answer}")

        messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": input_text }
        ]

        # Отправляем обновленный запрос, чтобы получить итоговый ответ
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.1,
        )

        #print('-------------конец шаг 2-------------------------------------------------')
        answer_text = response.choices[0].message.content
        total_tokens_, price_ = calculate_cost_and_tokens(response)
        total_tokens += total_tokens_
        price += price_

    context.update(f"Пользователь: {query}\n\nКонсультант: {answer_text}\n\n")
    save_profile(context)
    context.save_dialog_history()

    return answer_text, total_tokens, price


    # Функция для генерации ответа в диалоге (без поисковика)
    # Создает запрос к модели, используя текущий профиль и историю диалогов. Обновляет контекст и возвращает ответ модели, количество использованных токенов и стоимость
def generate_answer_dialog(prompt, query, context):
    input_text = f"информация о текущем профиле: {context.to_text()}\n\nИстория диалога:\n{' '.join(context.dialog_history)}\n\nТекущий вопрос: {query}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": input_text}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.1,
    )

    answer_text = response.choices[0].message.content
    total_tokens, price = calculate_cost_and_tokens(response)

    context.update(f"Пользователь: {query}\n\nКонсультант: {answer_text}\n\n")

    save_profile(context)  # обновляем профиль
    context.save_dialog_history()  # обновляем историю диалога

    return answer_text, total_tokens, price

# Функция для запуска диалога
def run_dialog(prompt, context):
    initial_prompt = "Здравствуйте! Чем я могу вам помочь сегодня?"
    print('Консультант ИИ:', initial_prompt)
    print('=================================')
    context.update(f"Консультант-Планировщик: {initial_prompt}\n\n")

    total_tokens = 0
    total_cost = 0

    while True:
        user_question = input('Пользователь: ')
        print('=================================')
        if user_question.lower() == 'stop':
            break
# ВЫБИРАЕМ режим с агентом-поисковиком или без него
        answer, used_tokens, cost = generate_answer_dialog_search(prompt, user_question, context)
        #answer, used_tokens, cost = generate_answer_dialog(prompt, user_question, context)

        total_tokens += used_tokens
        total_cost += cost

        print('Консультант ИИ:',answer)
        print('--------------------------------------------------------------')
        print(f"Использовано токенов: {used_tokens}, Стоимость: ${cost:.5f}")
        print('--------------------------------------------------------------')
        print(f"Всего использовано токенов: {total_tokens}, Общая стоимость: ${total_cost:.5f}")
        print('--------------------------------------------------------------')

# Храним всю историю диалогов и обновления профиля проекта.
    save_profile(context)
    context.save_dialog_history()


# Инициализация OpenAI
try:
    # Загружаем токен из .env
    os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    # Инициализация клиента OpenAI
    # client = AsyncOpenAI()
    client = OpenAI()
    print("Ключ API успешно установлен.")
except OpenAIError as e:
    print(f"Ошибка: {e}")


# # Проверка наличия сохраненного профиля и загрузка его или инициализация нового
# context = load_profile()
# print("Загружен профиль и диалог:\n", context.to_text())
# print('---------------------------------------')
# #@title Запуск диалогового интерфейса
# run_dialog(prompt_for_GPT_DS_5, context)