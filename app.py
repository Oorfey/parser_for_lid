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

    # Нормализация URL: удаляем протокол и 'www.' из начала
    url_clean = re.sub(r'^https?://', '', url)
    url_clean = re.sub(r'^www\.', '', url_clean)

    # Добавляем 'http://' для выполнения запроса
    full_url = 'http://' + url_clean

    # Заголовки для имитации запроса из браузера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/117.0.0.0 Safari/537.36'
    }

    # Пытаемся выполнить запрос по 'http://'
    try:
        page = requests.get(full_url, headers=headers, timeout=15)
        page.raise_for_status()
    except requests.RequestException:
        # Если не удалось, пробуем по 'https://'
        full_url = 'https://' + url_clean
        try:
            page = requests.get(full_url, headers=headers, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            return jsonify({'error': f'Не удалось получить доступ к сайту: {str(e)}'}), 400

    # Удаляем протокол для парсера
    parser_url = re.sub(r'^https?://', '', full_url)

    # Парсим содержимое страницы с помощью BeautifulSoup
    soup = BeautifulSoup(page.content, "html.parser")

    # Извлекаем заголовок страницы
    title = soup.find('title')
    title_text = title.text.strip() if title else 'Заголовок не найден'

    # Получаем весь текст страницы
    text = soup.get_text(separator='\n')

    # Регулярное выражение для поиска email-адресов
    email_pattern = re.compile(
        r'[\w\.-]+@[\w\.-]+'
    )
    emails = email_pattern.findall(text)
    emails = list(set(emails))  # Удаляем дубликаты

    # Регулярное выражение для поиска номеров телефонов
    phone_pattern = re.compile(
        r'\+?\d[\d\s\-\(\)]{7,}\d'
    )
    phone_numbers = phone_pattern.findall(text)
    phone_numbers = list(set(phone_numbers))  # Удаляем дубликаты

    # Формируем результат
    result = {
        'title': title_text,
        'url': parser_url,
        'phone_numbers': phone_numbers,
        'emails': emails
    }

    return jsonify(result), 200

# Конечная точка для парсинга страниц 2GIS с добавленной функциональностью из /parse_email
@app.route('/parse_2gis', methods=['POST'])
def parse_2gis():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL не предоставлен'}), 400

    # Заголовки для имитации запроса из браузера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/117.0.0.0 Safari/537.36'
    }

    # Пытаемся выполнить запрос к странице
    try:
        page = requests.get(url, headers=headers, timeout=15)
        page.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': f'Не удалось получить доступ к сайту: {str(e)}'}), 400

    # Парсим содержимое страницы с помощью BeautifulSoup
    soup = BeautifulSoup(page.content, "html.parser")

    # Извлекаем номера телефонов
    phone_numbers = []
    phone_elements = soup.find_all('a', href=re.compile(r'^tel:'))
    for element in phone_elements:
        phone_number = element.get('href').replace('tel:', '').strip()
        phone_numbers.append(phone_number)
    phone_numbers = list(set(phone_numbers))  # Удаляем дубликаты

    # Список сайтов социальных сетей для фильтрации
    social_networks = []
    social_sites = [
        'facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com',
        'youtube.com', 'vk.com', 'ok.ru'
    ]

    # Инициализируем списки для веб-сайтов и email-адресов
    websites = []
    emails = []

    # Регулярное выражение для email-адресов
    email_pattern = re.compile(
        r'[\w\.-]+@[\w\.-]+'
    )

    # Регулярное выражение для доменных имен (без протокола)
    domain_pattern = re.compile(
        r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b', re.IGNORECASE
    )

    # Регулярное выражение для обнаружения P.O.Box в любых вариациях
    pobox_pattern = re.compile(
        r'P\.?\s*O\.?\s*Box', re.IGNORECASE
    )

    # Получаем весь текст страницы
    text = soup.get_text(separator='\n')

    # Поиск email-адресов в тексте страницы
    emails_in_text = email_pattern.findall(text)
    emails.extend(emails_in_text)

    # Удаляем дубликаты email-адресов
    emails = list(set(emails))

    # Поиск доменных имен в тексте страницы
    domains_in_text = domain_pattern.findall(text)

    # Фильтруем домены, исключая '2gis' и дубликаты
    for domain in domains_in_text:
        if '2gis' not in domain.lower():
            # Дополнительно исключаем 'P.O.Box' из списка websites
            if not pobox_pattern.search(domain):
                websites.append(domain)
    websites = list(set(websites))

    # Извлекаем ссылки на социальные сети и email-адреса из ссылок
    for link in soup.find_all('a', href=True):
        href = link['href'].strip()
        href_lower = href.lower()

        if any(site in href_lower for site in social_sites):
            # Проверяем, содержит ли ссылка P.O.Box
            if not pobox_pattern.search(href):
                social_networks.append(href)
            else:
                # Можно добавить логирование или обработку исключенных ссылок
                pass  # Здесь можно добавить код для логирования, если необходимо
        elif href_lower.startswith('mailto:'):
            # Извлекаем email из mailto-ссылки
            email = href.replace('mailto:', '').strip()
            emails.append(email)
        elif email_pattern.match(href):
            # Если href соответствует email-паттерну
            emails.append(href)
        # Не добавляем сайты, начинающиеся с http/https в список websites

    # Удаляем дубликаты в социальных сетях и email
    social_networks = list(set(social_networks))
    emails = list(set(emails))

    # Добавляем функциональность из /parse_email
    # Будем использовать первый сайт из списка websites, если он есть
    if websites:
        website_url = websites[0]
        # Нормализация URL: удаляем протокол и 'www.' из начала
        url_clean = re.sub(r'^https?://', '', website_url)
        url_clean = re.sub(r'^www\.', '', url_clean)

        # Добавляем 'http://' для выполнения запроса
        full_url = 'http://' + url_clean

        # Пытаемся выполнить запрос по 'http://'
        try:
            page_web = requests.get(full_url, headers=headers, timeout=15)
            page_web.raise_for_status()
        except requests.RequestException:
            # Если не удалось, пробуем по 'https://'
            full_url = 'https://' + url_clean
            try:
                page_web = requests.get(full_url, headers=headers, timeout=15)
                page_web.raise_for_status()
            except requests.RequestException as e:
                # Не удалось получить доступ к сайту
                parser_url = full_url
                emails_web = []
                title_text = 'Не удалось получить доступ к сайту'
            else:
                # Парсим содержимое страницы с помощью BeautifulSoup
                soup_web = BeautifulSoup(page_web.content, "html.parser")

                # Извлекаем заголовок страницы
                title = soup_web.find('title')
                title_text = title.text.strip() if title else 'Заголовок не найден'

                # Получаем весь текст страницы
                text_web = soup_web.get_text(separator='\n')

                # Поиск email-адресов в тексте страницы
                emails_web = email_pattern.findall(text_web)
                emails_web = list(set(emails_web))

                # Удаляем протокол для parser_url
                parser_url = re.sub(r'^https?://', '', full_url)
        else:
            # Парсим содержимое страницы с помощью BeautifulSoup
            soup_web = BeautifulSoup(page_web.content, "html.parser")

            # Извлекаем заголовок страницы
            title = soup_web.find('title')
            title_text = title.text.strip() if title else 'Заголовок не найден'

            # Получаем весь текст страницы
            text_web = soup_web.get_text(separator='\n')

            # Поиск email-адресов в тексте страницы
            emails_web = email_pattern.findall(text_web)
            emails_web = list(set(emails_web))

            # Удаляем протокол для parser_url
            parser_url = re.sub(r'^https?://', '', full_url)
    else:
        # Нет сайтов для обработки
        parser_url = ''
        emails_web = []
        title_text = 'Сайт не найден'

    # Формируем результат
    result = {
        'url': url,
        'phone_numbers': phone_numbers,
        'emails': emails,
        'websites': websites,
        'social_networks': social_networks,
        'url_web': parser_url,
        'emails_web': emails_web,
        'title': title_text
    }

    return jsonify(result), 200

# Конечная точка для парсинга email-адресов с сайта
@app.route('/parse_email', methods=['POST'])
def parse_email():
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL не предоставлен'}), 400

    # Нормализация URL: удаляем протокол и 'www.' из начала
    url_clean = re.sub(r'^https?://', '', url)
    url_clean = re.sub(r'^www\.', '', url_clean)

    # Добавляем 'http://' для выполнения запроса
    full_url = 'http://' + url_clean

    # Заголовки для имитации запроса из браузера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/117.0.0.0 Safari/537.36'
    }

    # Пытаемся выполнить запрос по 'http://'
    try:
        page = requests.get(full_url, headers=headers, timeout=15)
        page.raise_for_status()
    except requests.RequestException:
        # Если не удалось, пробуем по 'https://'
        full_url = 'https://' + url_clean
        try:
            page = requests.get(full_url, headers=headers, timeout=15)
            page.raise_for_status()
        except requests.RequestException as e:
            return jsonify({'error': f'Не удалось получить доступ к сайту: {str(e)}'}), 400

    # Удаляем протокол для парсера
    parser_url = re.sub(r'^https?://', '', full_url)



    # Парсим содержимое страницы с помощью BeautifulSoup
    soup = BeautifulSoup(page.content, "html.parser")

    # Извлекаем заголовок страницы
    title = soup.find('title')
    title_text = title.text.strip() if title else 'Заголовок не найден'

    # Получаем весь текст страницы
    text = soup.get_text(separator='\n')

    # Используем то же регулярное выражение для email-адресов, что и в /parse_vk
    email_pattern = re.compile(
        r'[\w\.-]+@[\w\.-]+'
    )
    emails = email_pattern.findall(text)
    emails = list(set(emails))  # Удаляем дубликаты

    # Формируем результат
    result = {
        'url': parser_url,
        'emails': emails,
        'title': title_text
    }

    return jsonify(result), 200

if __name__ == '__main__':
    app.run(debug=True)
