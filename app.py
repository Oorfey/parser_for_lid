from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# Конечная точка для парсинга страниц VK
@app.route('/parse_vk', methods=['POST'])
def parse_vk():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL не предоставлен'}), 400

    # Нормализация URL
    url_clean = re.sub(r'^https?://', '', url)
    url_clean = re.sub(r'^www\.', '', url_clean)

    # Пробуем открыть URL (сначала http, потом https)
    full_url = 'http://' + url_clean
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/117.0.0.0 Safari/537.36'
    }

    try:
        page = requests.get(full_url, headers=headers, timeout=15)
        page.raise_for_status()
    except requests.RequestException:
        full_url = 'https://' + url_clean
        try:
            page = requests.get(full_url, headers=headers, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            return jsonify({'error': f'Не удалось получить доступ к сайту: {str(e)}'}), 400

    # Парсим страницу
    soup = BeautifulSoup(page.content, "html.parser")

    # Извлекаем заголовок страницы
    title = soup.find('title')
    title_text = title.text.strip() if title else 'Заголовок не найден'

    # Получаем текст страницы
    text = soup.get_text(separator='\n')

    # Регулярное выражение для поиска email-адресов
    email_pattern = re.compile(
        r'[\w\.-]+@[\w\.-]+'
    )
    emails = list(set(email_pattern.findall(text)))  # Удаляем дубликаты

    # Регулярное выражение для поиска номеров телефонов (исключаем годы)
    phone_pattern = re.compile(
        r'(?:(?:\+7|8)?[\s\-]?)?(?:\(\d{3}\)|\d{3})[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
    )
    phone_numbers = list(set(phone_pattern.findall(text)))

    # 🔥 **Фильтрация некорректных данных** 🔥
    phone_numbers = [num for num in phone_numbers if not re.match(r'^\d{4}$', num)]  # Исключаем 4-значные числа (годы)

    # Формируем результат
    result = {
        'title': title_text,
        'url': url_clean,
        'phone_numbers': phone_numbers,
        'emails': emails
    }

    return jsonify(result), 200

if __name__ == '__main__':
    app.run(debug=True)
