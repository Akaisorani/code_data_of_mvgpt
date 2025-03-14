import dataclasses
from enum import auto, Enum
from typing import List, Tuple, Any

from fastchat.serve.chains.knowledge_search import get_prompt_dim_info, trans_prompt


class SeparatorStyle(Enum):
    """Different separator style."""

    SINGLE = auto()
    TWO = auto()
    DOLLY = auto()
    OASST_PYTHIA = auto()
    M6 = auto()


@dataclasses.dataclass
class Conversation:
    """A class that keeps all conversation history."""

    system: str
    roles: List[str]
    messages: List[List[str]]
    offset: int
    sep_style: SeparatorStyle = SeparatorStyle.SINGLE
    sep: str = "###"
    sep2: str = None

    # Used for gradio server
    skip_next: bool = False
    conv_id: Any = None

    def get_prompt(self, model_name):
        if self.sep_style == SeparatorStyle.SINGLE:
            ret = self.system
            for role, message in self.messages:
                if message:
                    ret += self.sep + " " + role + ": " + message
                else:
                    ret += self.sep + " " + role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.TWO:
            seps = [self.sep, self.sep2]
            ret = self.system + seps[0]
            for i, (role, message) in enumerate(self.messages):
                if i < len(self.messages) - 2:
                    continue
                if message:
                    message = trans_prompt(message.strip(), model_name)

                    ret = self.system + seps[0] + role + ": " + message + seps[i % 2]
                else:
                    ret += role + ":"
            return ret
        elif self.sep_style == SeparatorStyle.M6:
            seps = [self.sep, self.sep2]
            ret = self.system + seps[0]
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret = self.system + seps[0] + role + ": " + message + seps[i % 2] + "\n\n"
                    print("ret:" + ret)
            return ret
        elif self.sep_style == SeparatorStyle.DOLLY:
            seps = [self.sep, self.sep2]
            ret = self.system
            for i, (role, message) in enumerate(self.messages):
                if message:
                    ret += role + ":\n" + message + seps[i % 2]
                    if i % 2 == 1:
                        ret += "\n\n"
                else:
                    ret += role + ":\n"
            return ret
        elif self.sep_style == SeparatorStyle.OASST_PYTHIA:
            ret = ""
            for role, message in self.messages:
                if message:
                    ret += role + message + self.sep
                else:
                    ret += role
            return ret
        else:
            raise ValueError(f"Invalid style: {self.sep_style}")

    def append_message(self, role, message):
        self.messages.append([role, message])

    def to_gradio_chatbot(self):
        ret = []
        for i, (role, msg) in enumerate(self.messages[self.offset:]):
            if i % 2 == 0:
                ret.append([msg, None])
            else:
                ret[-1][-1] = msg
        return ret

    def copy(self):
        return Conversation(
            system=self.system,
            roles=self.roles,
            messages=[[x, y] for x, y in self.messages],
            offset=self.offset,
            sep_style=self.sep_style,
            sep=self.sep,
            sep2=self.sep2,
            conv_id=self.conv_id,
        )

    def dict(self):
        return {
            "system": self.system,
            "roles": self.roles,
            "messages": self.messages,
            "offset": self.offset,
            "sep": self.sep,
            "sep2": self.sep2,
            "conv_id": self.conv_id,
        }


conv_one_shot = Conversation(
    system="A chat between a curious human and an artificial intelligence assistant. "
           "The assistant gives helpful, detailed, and polite answers to the human's questions.",
    roles=("Human", "Assistant"),
    messages=(
        (
            "Human",
            "What are the key differences between renewable and non-renewable energy sources?",
        ),
        (
            "Assistant",
            "Renewable energy sources are those that can be replenished naturally in a relatively "
            "short amount of time, such as solar, wind, hydro, geothermal, and biomass. "
            "Non-renewable energy sources, on the other hand, are finite and will eventually be "
            "depleted, such as coal, oil, and natural gas. Here are some key differences between "
            "renewable and non-renewable energy sources:\n"
            "1. Availability: Renewable energy sources are virtually inexhaustible, while non-renewable "
            "energy sources are finite and will eventually run out.\n"
            "2. Environmental impact: Renewable energy sources have a much lower environmental impact "
            "than non-renewable sources, which can lead to air and water pollution, greenhouse gas emissions, "
            "and other negative effects.\n"
            "3. Cost: Renewable energy sources can be more expensive to initially set up, but they typically "
            "have lower operational costs than non-renewable sources.\n"
            "4. Reliability: Renewable energy sources are often more reliable and can be used in more remote "
            "locations than non-renewable sources.\n"
            "5. Flexibility: Renewable energy sources are often more flexible and can be adapted to different "
            "situations and needs, while non-renewable sources are more rigid and inflexible.\n"
            "6. Sustainability: Renewable energy sources are more sustainable over the long term, while "
            "non-renewable sources are not, and their depletion can lead to economic and social instability.",
        ),
    ),
    offset=2,
    sep_style=SeparatorStyle.SINGLE,
    sep="###",
)

conv_vicuna_v1_1 = Conversation(
    system="A chat between a curious user and an artificial intelligence assistant. "
           "The assistant gives detailed, and polite answers to the user's questions.",
    roles=("USER", "ASSISTANT"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.TWO,
    sep=" ",
    sep2="</s>",
)

conv_m6 = Conversation(
    system="请根据工具描述与用户输入来确定是否需要调用工具，若需要调用工具且用户输入了合理的参数请以Tool开头输出一段JSON格式的包含特定工具id与对应参数的工具信息，否则请以Assistant"
           "开头输出正常回答，或以ToolParam开头引导用户描述参数。\n工具描述: "
           "diagnosis，参数为单元id-adgroup_id与日期-date，可诊断展现、点击相关投放效果问题；kr，参数为单元id-adgroup_id，可进行关键词推荐。\n\n",
    roles=("Human", ""),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.M6,
    sep=" ",
    sep2="</s>",
)

conv_koala_v1 = Conversation(
    system="BEGINNING OF CONVERSATION:",
    roles=("USER", "GPT"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.TWO,
    sep=" ",
    sep2="</s>",
)

conv_dolly = Conversation(
    system="Below is an instruction that describes a task. Write a response that appropriately completes the request.\n\n",
    roles=("### Instruction", "### Response"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.DOLLY,
    sep="\n\n",
    sep2="### End",
)

conv_oasst = Conversation(
    system="",
    roles=("<|prompter|>", "<|assistant|>"),
    messages=(),
    offset=0,
    sep_style=SeparatorStyle.OASST_PYTHIA,
    sep="<|endoftext|>",
)

conv_templates = {
    "conv_one_shot": conv_one_shot,
    "vicuna_v1.1": conv_vicuna_v1_1,
    "koala_v1": conv_koala_v1,
    "dolly": conv_dolly,
    "oasst": conv_oasst,
    'm6':conv_m6
}


def get_default_conv_template(model_name):
    model_name = model_name.lower()
    if "m6" in model_name:
        return conv_m6
    elif "vicuna" in model_name or "output" in model_name or "analyticai" in model_name:
        return conv_vicuna_v1_1
    elif "koala" in model_name:
        return conv_koala_v1
    elif "dolly-v2" in model_name:
        return conv_dolly
    elif "oasst" in model_name and "pythia" in model_name:
        return conv_oasst
    print("conv_one_shot")
    return conv_one_shot


def compute_skip_echo_len(model_name, conv, prompt):
    model_name = model_name.lower()
    if "chatglm" in model_name:
        skip_echo_len = len(conv.messages[-2][1]) + 1
    elif "dolly-v2" in model_name:
        special_toks = ["### Instruction:", "### Response:", "### End"]
        skip_echo_len = len(prompt)
        for tok in special_toks:
            skip_echo_len -= prompt.count(tok) * len(tok)
    elif "oasst" in model_name and "pythia" in model_name:
        special_toks = ["<|prompter|>", "<|assistant|>", "<|endoftext|>"]
        skip_echo_len = len(prompt)
        for tok in special_toks:
            skip_echo_len -= prompt.count(tok) * len(tok)
    elif "m6" in model_name:
        skip_echo_len = 0
    else:
        skip_echo_len = len(prompt) + 1 - prompt.count("</s>") * 3
    return skip_echo_len

conv_qa_prompt_template = """ 基于以下已知的信息, 专业、简要的回答用户的问题,
            如果无法从提供的恶内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题" 禁止胡乱编造。 
            已知历史问答内容: 
            问：{context_question}
            答：{context_answer}
            用户问题:
            {question}
"""

if __name__ == "__main__":
    print(default_conversation.get_prompt())
