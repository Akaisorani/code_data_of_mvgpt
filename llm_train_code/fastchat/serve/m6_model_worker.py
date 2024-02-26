"""
A model worker executes the model.
"""
import argparse
import asyncio
import dataclasses
import logging
import json
import time
import traceback
import threading
import uuid

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
import requests

from fastchat.constants import WORKER_HEART_BEAT_INTERVAL
from fastchat.serve.inference import load_model, generate_stream
from fastchat.serve.serve_chatglm import chatglm_generate_stream
from fastchat.utils import build_logger, server_error_msg, pretty_print_semaphore

from typing import Tuple, List, Generator
import os
import sys
import torch
torch.set_grad_enabled(False)
import copy
import uvicorn

import pathlib
from pathlib import Path

import deepspeed

from megatron.model import GPTModel
from megatron import get_args
from megatron import get_tokenizer
from megatron.initialize import initialize_megatron
from megatron.checkpointing import load_checkpoint
from megatron.tokenizer.tokenizer import AbstractTokenizer
from megatron.text_generation.tokenization import tokenize_prompts, detokenize_generations
from megatron.text_generation.generation import generate_tokens_probs_and_return_on_first_stage
# from megatron.text_generation_utils import get_token_stream

from transformer_tools.step_forwarder import PostProcessedStepForwarderWithStop
from transformer_tools.forwarder_manager import ForwarderManager

worker_id = str(uuid.uuid4())[:6]
logger = build_logger("model_worker", f"model_worker_{worker_id}.log")
global_counter = 0
model_semaphore = None

def heart_beat_worker(controller):
    while True:
        time.sleep(WORKER_HEART_BEAT_INTERVAL)
        controller.send_heart_beat()

class ModelWorker:
    def __init__(
        self,
        controller_addr,
        worker_addr,
        model_path,
        no_register
    ):
        self.controller_addr = controller_addr
        self.worker_addr = worker_addr
        self.model_name = "nebula_m6"

        logger.info(f"Loading the model {self.model_name} on worker {worker_id} ...")

        self.context_len = 2048

        if not no_register:
            self.register_to_controller()
            self.heart_beat_thread = threading.Thread(
                target=heart_beat_worker, args=(self,)
            )
            self.heart_beat_thread.start()

        manual_random_seed = int(os.environ.get('M6_RANDOM_SEED', -1))
        torch.random.manual_seed(manual_random_seed)

        self.user_name = 'Human'
        self.generate_splitter = f'{self.user_name}'

        current_file_path = Path(__file__).parent.absolute()
        m6_params = {
            "no_load_rng": True,
            "no_load_optim": True,
            "make_vocab_size_divisible_by": 65408,
            "tensor_model_parallel_size": 1,
            "num_layers": 40,
            "hidden_size": 5120,
            "num_attention_heads": 40,
            "max_position_embeddings": 4096,
            "tokenizer_type": "GPT2ZHBPETokenizer",
            "activation": "geglu",
            "pos_emb": "rotary",
            "apply_magneto": True,
            "remove_ffn_bias": True,
            "num_experts": None,
            "micro_batch_size": 1,
            "seq_length": 1024,
            "vocab_file": f"{current_file_path}/resources/vocab/m6/gpt2-zhcn3-v4.json",
            "merge_file": f"{current_file_path}/resources/vocab/m6/gpt2-zhcn3-v4.bpe",
            "log_interval": 1,
            "fp16": True,
            "async_tensor_model_parallel_allreduce": False,
            "model_type": "GPT",
            "gradient_accumulation_fusion": False,
            "load": model_path
        }
        initialize_megatron(args_defaults=m6_params, ignore_unknown_args=True)
        self.megatron_args = get_args()
        logging.info(f'megatron initialize done.')

        tokenizer = get_tokenizer()
        if tokenizer is None:
            raise Exception("Tokenizer not found")
        self.tokenizer: AbstractTokenizer = tokenizer
        self.model = GPTModel(
            num_tokentypes=0,
            parallel_output=False,
            pre_process=True,
            post_process=True,
        ).half().cuda()
        load_checkpoint([self.model], None, None, strict=False)
        logging.info(f'load ckpt done')

        self.forwarder_manager = ForwarderManager()

    def process_output_tokens(self, output_tokens, raw_text_len) -> str:
        if not isinstance(output_tokens, list):
            if len(output_tokens) < 1:
                return ''
            output_tokens = output_tokens[0].cpu().numpy().tolist()
        trim_decode_tokens = self.tokenizer.detokenize(output_tokens)[raw_text_len:]
        trim_decode_tokens = trim_decode_tokens.replace('<|endoftext|>', '')
        trim_decode_tokens = trim_decode_tokens.split(self.generate_splitter)[0]
        trim_decode_tokens = trim_decode_tokens.strip()
        return trim_decode_tokens

    def test_stop(self, tokens, raw_text_len) -> bool:
        tokens = tokens[0].cpu().numpy().tolist()
        trim_decode_tokens = self.tokenizer.detokenize(tokens)[raw_text_len:]
        trim_decode_tokens = trim_decode_tokens.replace('<|endoftext|>', '')
        return len(trim_decode_tokens.split(self.generate_splitter)) > 1

    def get_model_inputs_new(self, request_args: dict) -> str:
        prompt = request_args.get("prompt", "")
        if prompt != "":
            return prompt
        else:
            raise Exception("prompt is empty")

    def register_to_controller(self):
        logger.info("Register to controller")

        url = self.controller_addr + "/register_worker"
        data = {
            "worker_name": self.worker_addr,
            "check_heart_beat": True,
            "worker_status": self.get_status(),
        }
        print("url" + url + "json " + json.dumps(data))
        r = requests.post(url, json=data)
        print("resonse" + str(r))
        assert r.status_code == 200

    def send_heart_beat(self):
        logger.info(
            f"Send heart beat. Models: {[self.model_name]}. "
            f"Semaphore: {pretty_print_semaphore(model_semaphore)}. "
            f"global_counter: {global_counter}"
        )

        url = self.controller_addr + "/receive_heart_beat"

        while True:
            try:
                ret = requests.post(
                    url,
                    json={
                        "worker_name": self.worker_addr,
                        "queue_length": self.get_queue_length(),
                    },
                    timeout=5,
                )
                exist = ret.json()["exist"]
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"heart beat error: {e}")
            time.sleep(5)

        if not exist:
            self.register_to_controller()

    def get_queue_length(self):
        if (
            model_semaphore is None
            or model_semaphore._value is None
            or model_semaphore._waiters is None
        ):
            return 0
        else:
            return (
                args.limit_model_concurrency
                - model_semaphore._value
                + len(model_semaphore._waiters)
            )

    def get_status(self):
        return {
            "model_names": [self.model_name],
            "speed": 1,
            "queue_length": self.get_queue_length(),
        }

    def generate_stream_gate(self, params):
        try:
            finished = False
            prompt = params.get("prompt", "")
            temperature = params.get("temperature", 0.7)
            max_window_size = params.get("max_new_tokens", 512)
            chat_session_id = int(time.time())
            while not finished:
                response = worker.inference(prompt, temperature, max_window_size, chat_session_id)
                finished = response["finished"]
                ret = {
                    "text": response["response"],
                    "error_code": 0,
                }
                yield json.dumps(ret).encode() + b"\0"
        except Exception as e:
            print(e)
            ret = {
                "text": server_error_msg,
                "error_code": 1,
            }
            yield json.dumps(ret).encode() + b"\0"

    def inference(self, prompt, temperature = 0.7, max_window_size = 512, chat_session_id = None) -> dict:
        input_pattern = { "chat_config": {
                "generate_config": {
                    "num_beams": 1,
                    "min_length": 1,
                    "num_return_sequences": 1,
                    "no_repeat_ngram_size": 6,
                    "do_sample": True,
                    "early_stopping": True,
                    "top_k": 0,
                    "top_p": 0.9,
                    "temperature": temperature,
                    "repetition_penalty": 2,
                    "length_penalty": 1.2,
                    "max_length": 512,
                    "unfinished_wait_sec": 0.1,
                }
            },
            "prompt": prompt
        }
        generate_config: dict = input_pattern.get("chat_config", {}).get("generate_config", {})

        model_inputs = self.get_model_inputs_new(input_pattern)
        input_tokens, input_lengths = tokenize_prompts([model_inputs], max_window_size)

        raw_len = len(model_inputs)
        forward_creator_func = lambda: PostProcessedStepForwarderWithStop(
            post_processor = lambda ids: self.process_output_tokens(ids, raw_len),
            stop_criteria = lambda ids: self.test_stop(ids, raw_len)
        )

        forward_starter = lambda fwd: generate_tokens_probs_and_return_on_first_stage(
                self.model, input_tokens, input_lengths,
                forwarder = fwd,
                **generate_config
        )

        if chat_session_id:
            # async run
            forwarder = self.forwarder_manager.get_forwarder_or_start(
                chat_session_id, forward_creator_func, forward_starter
            )
            assert isinstance(forwarder, PostProcessedStepForwarderWithStop)
            if forwarder.generate_future.done():
                exception = forwarder.generate_future.exception()
                if exception:
                    raise exception
                if not forwarder.finished:
                    forwarder.done()
            else:
                unfinished_wait_sec: float = generate_config.get("unfinished_wait_sec", None)
                if unfinished_wait_sec:
                    time.sleep(unfinished_wait_sec)
                    forwarder = self.forwarder_manager.get_forwarder_or_start(
                        chat_session_id, forward_creator_func, forward_starter
                    )
        else:
            # synced
            forwarder = forward_creator_func()
            forward_starter(forwarder)

        return {
            "response": forwarder.get_post_processed_response(),
            "finished": forwarder.finished
        }

app = FastAPI()

def release_model_semaphore():
    model_semaphore.release()


@app.post("/worker_generate_stream")
async def api_generate_stream(request: Request):
    global model_semaphore, global_counter
    global_counter += 1
    params = await request.json()

    if model_semaphore is None:
        model_semaphore = asyncio.Semaphore(args.limit_model_concurrency)
    await model_semaphore.acquire()
    generator = worker.generate_stream_gate(params)
    background_tasks = BackgroundTasks()
    background_tasks.add_task(release_model_semaphore)
    return StreamingResponse(generator, background=background_tasks)


@app.post("/worker_get_status")
async def api_get_status(request: Request):
    return worker.get_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=21002)
    parser.add_argument("--worker-address", type=str, default="http://127.0.0.1:21002")
    parser.add_argument(
        "--controller-address", type=str, default="http://models-controller.alimama.com"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="/home/admin/nebula_m6",
        help="The path to the weights",
    )
    parser.add_argument("--no-register", action="store_true")
    parser.add_argument("--limit-model-concurrency", type=int, default=5)
    args = parser.parse_args()
    logger.info(f"args: {args}")

    worker = ModelWorker(
        args.controller_address,
        args.worker_address,
        args.model_path,
        args.no_register,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
