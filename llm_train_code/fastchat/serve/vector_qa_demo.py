import json

import requests



if __name__ == '__main__':
    content = 'hello'
    url = "https://ai-models-provider.alimama.com/v1/chat/completions"

    payload = {
        "model": "chatglm_6B",
        "messages": [{"role": "user", "content": content}]
    }
    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    response_entity = json.loads(response.text)
    print(response_entity)
    response_content = response_entity['choices'][0]["message"]['content']
    print(response_content)