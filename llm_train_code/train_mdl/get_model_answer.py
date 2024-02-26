import argparse
from transformers import AutoTokenizer, AutoModelForCausalLM, LlamaForCausalLM
import torch
import os
import json
from tqdm import tqdm
import shortuuid
import ray
import shutil
import pathlib
import time

from conversation import get_default_conv_template, compute_skip_echo_len
from utils import disable_torch_init


def run_eval(model_path, model_id, question_file, question_begin, question_end, answer_file, num_gpus):
    local_rank = int(os.environ['RANK'])

    # split question file into num_gpus files
    ques_jsons = []
    # with open(os.path.expanduser(question_file), "r") as ques_file:
    #     for line in ques_file:
    #         ques_jsons.append(line)
    with open(os.path.expanduser(question_file), "r") as ques_file:
        ques_jsons=json.load(ques_file) # list of conversations

        # for line in ques_file:
        #     ques_jsons.append(line)

    if question_begin is None: question_begin=0
    if question_end is None: question_end=len(ques_jsons)
    if question_begin!=0 or question_end!=len(ques_jsons):
        ques_jsons=ques_jsons[question_begin:question_end]
    # small test
    # ques_jsons=ques_jsons[:32]

    chunk_size = (len(ques_jsons)-1) // num_gpus +1
    worker_begin, worker_end=local_rank*chunk_size, (local_rank+1)*chunk_size
    # ans_handles = []
    # for i in range(0, len(ques_jsons), chunk_size):
    #     ans_handles.append(
    #         get_model_answers.remote(
    #             model_path, model_id, ques_jsons[i : i + chunk_size]
    #         )
    #     )
    # ans_jsons = []
    # for ans_handle in ans_handles:
    #     ans_jsons.extend(ray.get(ans_handle))

    ans_jsons = get_model_answers(model_path, model_id, ques_jsons[worker_begin: worker_end])

    range_flag=f"_{worker_begin}-{worker_end}" if worker_begin is not None or worker_end is not None else ""
    path_parts=os.path.splitext(os.path.expanduser(answer_file))
    filename=path_parts[0]+range_flag+path_parts[1]
    with open(filename, "w") as ans_file:
        for line in ans_jsons:
            ans_file.write(json.dumps(line) + "\n")


# @ray.remote(num_gpus=1)
@torch.inference_mode()
def get_model_answers(model_path, model_id, question_jsons):
    disable_torch_init()
    model_path = os.path.expanduser(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, torch_dtype=torch.float16
    ).cuda()

    ans_jsons = []
    for i, ques_json in enumerate(tqdm(question_jsons)):
        # ques_json = json.loads(line)     # already loads
        idx = ques_json["id"]
        qs = ques_json["conversations"][0]["value"]
        conv = get_default_conv_template(model_id).copy()
        conv.append_message(conv.roles[0], qs)
        conv.append_message(conv.roles[1], None)
        prompt = conv.get_prompt()
        inputs = tokenizer([prompt], truncation=True)
        input_token_number=len(inputs['input_ids'][0])
        output_ids = model.generate(
            torch.as_tensor(inputs.input_ids).cuda(),
            do_sample=True,
            temperature=0.7,
            max_new_tokens=2048-input_token_number,
        )
        outputs = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
        skip_echo_len = compute_skip_echo_len(model_id, conv, prompt)

        outputs = outputs[skip_echo_len:].strip()
        ans_id = shortuuid.uuid()
        ans_jsons.append(
            {
                "question_id": idx,
                "text": outputs,
                "answer_id": ans_id,
                "model_id": model_id,
                "metadata": {},
            }
        )
    return ans_jsons

def copy_model_to_local(args):
    # copy model to local
    local_rank = int(os.environ['RANK'])
    print("local_rank =", local_rank, flush=True)
    flag_filename=os.getcwd()+'/flag_copied_model_file_to_local.txt'
    if local_rank==0:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())}] copying model file...", flush=True)
        model_name=os.path.basename(args.model_path)
        model_dst_path=os.getcwd()+'/models/'+model_name
        destination = shutil.copytree(args.model_path, model_dst_path)
        args.model_path=destination
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())}] copied model file to "+destination, flush=True)
        pathlib.Path(flag_filename).touch()
    else:
        print("Waiting for master worker 0 copying model file", flush=True)
        while not os.path.exists(flag_filename):
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--model_id", type=str, required=True)
    parser.add_argument("--question_file", type=str, required=True)
    parser.add_argument("--question_begin", type=int, default=None)
    parser.add_argument("--question_end", type=int, default=None)
    parser.add_argument("--answer_file", type=str, default="answer.jsonl")
    parser.add_argument("--num_gpus", type=int, default=1)
    args = parser.parse_args()

    copy_model_to_local(args)

    # local_rank = int(os.environ['RANK'])
    # if local_rank==0:
    # ray.init()
    run_eval(
        args.model_path,
        args.model_id,
        args.question_file,
        args.question_begin,
        args.question_end,
        args.answer_file,
        args.num_gpus,
    )
