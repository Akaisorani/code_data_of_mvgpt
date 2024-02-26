"""This module provides a ChatGPT-compatible Restful API for chat completion.

Usage:

python3 -m fastchat.serve.api

Reference: https://platform.openai.com/docs/api-reference/chat/create
"""

from typing import Union, Dict, List, Any

import argparse
import json
import logging

import time
import hmac
import hashlib
import base64
import urllib.parse
import fastapi
import httpx
import requests
import uvicorn
from langchain import PromptTemplate
from langchain.callbacks import StdOutCallbackHandler
from mama_langchain.chains.nl2sql_chain import Nl2sqlChain
from mama_langchain.llms.aurora_llm import AuroraLLM
from pydantic import BaseSettings

from fastchat.protocol.chat_completion import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatCompletionResponseChoice,
)
from fastchat.conversation import get_default_conv_template, SeparatorStyle
from fastchat.serve.chains.knowledge_search import get_prompt_embedding
from fastchat.serve.inference import compute_skip_echo_len

logger = logging.getLogger(__name__)


class AppSettings(BaseSettings):
    # The address of the model controller.
    FASTCHAT_CONTROLLER_URL: str = "http://localhost:21001"


app_settings = AppSettings()
app = fastapi.FastAPI()
headers = {"User-Agent": "FastChat API Server"}
from pydantic import BaseModel


class Param(BaseModel):
    conversationId: str = None
    atUsers: List[Dict[str, str]] = None
    chatbotUserId: str = None
    msgId: str = None
    senderNick: str = None
    isAdmin: bool = None
    sessionWebhookExpiredTime: int = None
    createAt: int = None
    conversationType: str = None
    senderId: str = None
    conversationTitle: str = None
    isInAtList: bool = None
    sessionWebhook: str = None
    text: Dict[str, str]
    robotCode: str = None
    msgtype: str = None
    SenderStaffId: str = None

class PromptGenEmb(BaseModel):
    prompt: str = None

def send_message(text):
    headers = {
        "Content-Type": "application/json",
    }
    data = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }
    requests.post("YOUR_DINGTALK_WEBHOOK_URL", headers=headers, json=data)

@app.post("/gen_prompt_embedding")
async def gen_prompt_embedding(request:PromptGenEmb):
    prompt = request.prompt
    emb_list = get_prompt_embedding(prompt)
    emb_list = ','.join(map(str, emb_list))
    return emb_list

@app.post("/receive_dingding")
async def receive_dingding(request: Param):
    content = request.text['content']
    print('content:' + str(content))
    logger.info('content' + str(content))
    sessionWebhook = request.sessionWebhook

    url = "http://localhost:8100/v1/chat/completions"

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
    response_content = "@" + request.senderNick + " \n" + response_content
    headers = {"Content-Type": "application/json"}

    data = {
        "msgtype": "text",
        "text": {"content": response_content},
        "at": {
            "atMobiles": "",
            "isAtAll": ""
        },
    }

    timestamp = str(round(time.time() * 1000))
    secret = 'SEC64024a25c686a29dc7e205773960affbcc7d5bc30a43c7e8196d19ceb8fe374d'
    secret_enc = secret.encode('utf-8')
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    response = requests.post("https://oapi.dingtalk.com/robot/send?timestamp=" + timestamp + "&sign=" + sign +"&access_token=ce535eaef36d4f1b2c880ea32a7c9b4d5c783378e91290656b0f66d6310ab4a2", data=json.dumps(data), headers=headers)
    print(response.text)
    print(request)


@app.post("/nl2sql_chain")
def nl2sql_chain(request: PromptGenEmb):
    endpoint_url = "http://ai-models-provider.alimama.com/v1/chat/completions"
    auroraLLM = AuroraLLM(
        endpoint_url=endpoint_url,
        model_name="analyticai-13b-mama_sql_v620"
    )

    chain = Nl2sqlChain(
        prompt=PromptTemplate.from_template('提案分析:{question}'),llm=auroraLLM, scene_id='1', context={}
    )

    print(chain.run({'question': request.prompt}))


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    """Creates a completion for the chat message"""
    payload, skip_echo_len = generate_payload(
        request.model,
        request.messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        stop=request.stop,
    )
    print(payload)
    choices = []
    # TODO: batch the requests. maybe not necessary if using CacheFlow worker
    for i in range(request.n):
        content, knowledge = await chat_completion(request.model, payload, skip_echo_len)
        choices.append(
            ChatCompletionResponseChoice(
                index=i,
                message=ChatMessage(role="assistant", content=content),
                # TODO: support other finish_reason
                finish_reason="stop",
            )
        )

    # TODO: support usage field
    # "usage": {
    #     "prompt_tokens": 9,
    #     "completion_tokens": 12,
    #     "total_tokens": 21
    # }
    return ChatCompletionResponse(choices=choices, knowledge=knowledge)


def generate_payload(
        model_name: str,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        stop: Union[str, None],
):
    is_chatglm = "chatglm" in model_name.lower()
    # TODO(suquark): The template is currently a reference. Here we have to make a copy.
    # We use create a template factory to avoid this.
    conv = get_default_conv_template(model_name).copy()

    # TODO(suquark): Conv.messages should be a list. But it is a tuple now.
    #  We should change it to a list.
    conv.messages = list(conv.messages)

    for message in messages:
        msg_role = message["role"]
        if msg_role == "system":
            conv.system = message["content"]
        elif msg_role == "user":
            conv.append_message(conv.roles[0], message["content"])
        elif msg_role == "assistant":
            conv.append_message(conv.roles[1], message["content"])
        else:
            raise ValueError(f"Unknown role: {msg_role}")

    # Add a blank message for the assistant.
    conv.append_message(conv.roles[1], None)

    if is_chatglm:
        prompt = conv.messages[conv.offset:]
    else:
        prompt = conv.get_prompt(model_name)
    skip_echo_len = compute_skip_echo_len(model_name, conv, prompt)

    if stop is None:
        stop = conv.sep if conv.sep_style == SeparatorStyle.SINGLE else conv.sep2

    # TODO(suquark): We should get the default `max_new_tokens`` from the model.
    if max_tokens is None:
        max_tokens = 512

    payload = {
        "model": model_name,
        "prompt": prompt,
        "temperature": temperature,
        "max_new_tokens": max_tokens,
        "stop": stop,
    }

    logger.debug(f"==== request ====\n{payload}")
    return payload, skip_echo_len


async def chat_completion(model_name: str, payload: Dict[str, Any], skip_echo_len: int):
    controller_url = app_settings.FASTCHAT_CONTROLLER_URL
    async with httpx.AsyncClient() as client:
        ret = await client.post(
            controller_url + "/get_worker_address", json={"model": model_name}
        )
        worker_addr = ret.json()["address"]
        # No available worker
        if worker_addr == "":
            raise ValueError(f"No available worker for {model_name}")

        logger.debug(f"model_name: {model_name}, worker_addr: {worker_addr}")

        output = ""
        delimiter = b"\0"
        async with client.stream(
                "POST",
                worker_addr + "/worker_generate_stream",
                headers=headers,
                json=payload,
                timeout=20,
        ) as response:
            content = await response.aread()

        for chunk in content.split(delimiter):
            if not chunk:
                continue
            data = json.loads(chunk.decode())
            if data["error_code"] == 0:
                output = data["text"][skip_echo_len:].strip()
                knowledge = data.get("knowledge", '')
        return output,knowledge


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FastChat ChatGPT-compatible Restful API server."
    )
    parser.add_argument("--host", type=str, default="localhost", help="host name")
    parser.add_argument("--port", type=int, default=8000, help="port number")

    args = parser.parse_args()
    uvicorn.run("fastchat.serve.api:app", host=args.host, port=args.port, reload=True)


