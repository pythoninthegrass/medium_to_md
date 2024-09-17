#!/usr/bin/env python

import time
import json
import requests
from bs4 import BeautifulSoup
from decouple import config
from fasthtml.common import *
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from starlette.responses import JSONResponse
from webdriver_manager.chrome import ChromeDriverManager

app, rt = fast_app(
    static_path='static',
    hdrs=(
        Link(rel="stylesheet", href="/static/styles.css"),
        Script(src="/static/script.js", defer=True),
    )
)

OPENAI_API_KEY = config('OPENAI_API_KEY')
ASSISTANT_ID = config('ASSISTANT_ID')


def get_website_html(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)

    time.sleep(5)
    html_content = driver.page_source
    driver.quit()

    return html_content


@rt('/')
def get():
    return Titled("HTML Parser",
        Form(
            Input(type="url", name="url", placeholder="Enter URL", required=True),
            Button("Parse", type="submit"),
            hx_post="/parse",
            hx_target="#result"
        ),
        Div(id="result")
    )


@rt('/parse')
async def post(request):
    form = await request.form()
    url = form.get('url')

    if not url:
        return JSONResponse({'error': 'URL is required'}, status_code=400)

    html_content = get_website_html(url)
    soup = BeautifulSoup(html_content, 'html.parser')
    sections = soup.find_all('article')

    if sections:
        openai_response = await process_with_openai(str(sections[0]))
        return Div(Markdown(openai_response), id="parsed-content")
    else:
        return Div("No article content found", id="parsed-content")


async def process_with_openai(content):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v1"
    }

    # Create a thread
    thread_response = requests.post(
        "https://api.openai.com/v1/threads",
        headers=headers,
        json={}
    )
    thread_id = thread_response.json()['id']

    # Add a message to the thread
    message_response = requests.post(
        f"https://api.openai.com/v1/threads/{thread_id}/messages",
        headers=headers,
        json={"role": "user", "content": content}
    )

    # Run the assistant
    run_response = requests.post(
        f"https://api.openai.com/v1/threads/{thread_id}/runs",
        headers=headers,
        json={"assistant_id": ASSISTANT_ID}
    )
    run_id = run_response.json()['id']

    # Wait for the run to complete
    while True:
        run_status_response = requests.get(
            f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}",
            headers=headers
        )
        if run_status_response.json()['status'] == 'completed':
            break
        time.sleep(1)

    # Retrieve the messages
    messages_response = requests.get(
        f"https://api.openai.com/v1/threads/{thread_id}/messages",
        headers=headers
    )
    messages = messages_response.json()['data']

    # Return the latest assistant message
    for message in messages:
        if message['role'] == 'assistant':
            return message['content'][0]['text']['value']

    return "No response from assistant"


if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
