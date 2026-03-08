"""
大模型 API 接口封装

本文件封装了与大语言模型交互的接口，包括：
1. "加持"模型 —— 润色学生观点
2. "反驳"模型 —— 反驳学生观点（随机抽取一个模型）
3. "出题"模型 —— 每轮反驳后生成理解力选择题
"""
import json
import random
import requests


def call_llm_api(api_url, api_key, model, messages, temperature=0.7, max_tokens=4096):
    """
    通用的大模型 API 调用函数（兼容 OpenAI 格式）

    参数:
        api_url: API 端点地址（如果只提供基础 URL，会自动补全 /chat/completions）
        api_key: API 密钥
        model: 模型名称
        messages: 消息列表，格式 [{"role": "user", "content": "..."}]
        temperature: 温度参数
        max_tokens: 最大输出 token 数

    返回:
        str: 模型的回复文本；如果调用失败则返回错误信息
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # 检查响应格式
        if "choices" not in data or len(data["choices"]) == 0:
            return f"[API响应格式错误] 响应中未找到 choices 字段: {data}"
        
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        error_detail = ""
        try:
            error_data = e.response.json()
            error_detail = f" - {error_data}"
        except:
            error_detail = f" - {e.response.text[:200]}"
        return f"[API调用失败] HTTP {e.response.status_code}: {str(e)}{error_detail}"
    except requests.exceptions.RequestException as e:
        return f"[API调用失败] {str(e)}"
    except (KeyError, IndexError) as e:
        return f"[响应解析失败] {str(e)} - 响应数据: {data if 'data' in locals() else 'N/A'}"


def enhance_argument(config, topic_title, side, user_argument, history=None):
    """
    "加持"模型：润色学生的辩论观点

    参数:
        config: Flask app.config 对象
        topic_title: 辩题标题
        side: 学生选择的立场
        user_argument: 学生提交的原始观点
        history: 历史辩论记录列表（可选），格式：
            [{"enhanced": "加持后观点", "refutation": "AI反驳", "user_reply": "学生回应"}, ...]

    返回:
        str: 润色后的观点
    """
    system_prompt = (
        """
        # Role
            你是一个思维敏捷、特别能共情、且说话很有感染力的。你的任务是站在学生这边，帮他把心里想说但表达不清楚的话，用更有力、更走心的方式说出来。

        # Task
            1. **说“人话”**：严禁使用“综上所述”、“首先其次”、“心理学认为”等死板词汇。要像在课间休息或社团讨论时聊天。
            2. **场景代入**：结合给出的题目场景，用具体的细节来增强代入感。
            3. **情绪撑腰**：不仅要给逻辑，还要给情绪。让学生觉得：“对！我就是这个意思，你太懂我了！”

        # Tone & Style
            - 使用自然口语。
            - 适当使用语气词，但不要过头。
            - 逻辑隐藏在叙述中，而不是列条目。

        # Constraints
            - 以第一人称输出观点，不要输出任何额外的内容
            - 字数控制在120-150字左右
        """
    )

    messages = [{"role": "system", "content": system_prompt}]

    if history:
        # 构建历史对话上下文
        messages.append({
            "role": "user",
            "content": (
                f"辩题：{topic_title}\n"
                f"学生立场：{side}\n\n"
                f"以下是之前的辩论过程，请了解上下文：\n"
            ),
        })

        for i, h in enumerate(history):
            round_num = i + 1
            # 学生的加持观点（assistant 角色，因为是加持模型之前输出的）
            if h.get("enhanced"):
                messages.append({
                    "role": "assistant",
                    "content": f"[第{round_num}轮加持观点] {h['enhanced']}",
                })
            # AI 的反驳（作为上下文信息）
            if h.get("refutation"):
                messages.append({
                    "role": "user",
                    "content": f"[第{round_num}轮对方反驳] {h['refutation']}",
                })
            # 学生的新回应
            if h.get("user_reply"):
                messages.append({
                    "role": "user",
                    "content": f"[学生针对反驳的回应] {h['user_reply']}",
                })

        # 当前轮次的润色请求
        messages.append({
            "role": "user",
            "content": (
                f"学生最新的观点：{user_argument}\n\n"
                f"请结合之前的辩论历史，帮助润色和加强这个观点"
                f"注意要针对对方之前的反驳进行回应和反击："
            ),
        })
    else:
        # 第一轮，无历史
        messages.append({
            "role": "user",
            "content": (
                f"辩题：{topic_title}\n"
                f"学生立场：{side}\n"
                f"学生原始观点：{user_argument}\n\n"
            ),
        })

    return call_llm_api(
        api_url=config["ENHANCE_MODEL_API_URL"],
        api_key=config["ENHANCE_MODEL_API_KEY"],
        model=config["ENHANCE_MODEL_NAME"],
        messages=messages,
    )


def refute_argument(config, topic_title, side, enhanced_argument, history=None, fixed_model_name=None):
    """
    "反驳"模型：反驳学生的（已润色）观点
    第一轮从配置的多个反驳模型中随机抽取一个，后续轮次复用同一模型

    参数:
        config: Flask app.config 对象
        topic_title: 辩题标题
        side: 学生选择的立场
        enhanced_argument: 经过润色的观点
        history: 历史辩论记录列表（可选），格式：
            [{"enhanced": "加持后观点", "refutation": "AI反驳"}, ...]
        fixed_model_name: 指定使用的模型名称（用于多轮辩论中保持模型一致）

    返回:
        tuple: (反驳内容, 使用的模型名称)
    """
    # 如果指定了模型则复用，否则随机抽取
    chosen_model_name = fixed_model_name if fixed_model_name else random.choice(config["REFUTE_MODEL_NAMES"])

    system_prompt = (
        """
        # Role
            你是一个心思细腻、说话直率但不失温柔的思考伙伴。你不是为了驳倒学生，而是通过分享你的“困惑”和“担心”，引导他们进行更深层的自我探索。

        # Task
            情绪同频： 别只说“有道理”，要点出对方选择背后的那份不容易

            策略性示弱：不要直接反驳。把你担忧的对立视角，包装成你自己的“思维卡壳”。比如：“我最近也在纠结一个点，如果真的按你说的做了，那以后遇到某某情况该怎么办呢？”

            生活化的“小坑”： 讲一个咱们学生平时都会遇到的尴尬瞬间或麻烦，自然地引出对立面的风险。


        # Constraints
            - 禁用晦涩的学术词汇。
            - 以第一人称输出观点，不要输出任何额外的内容
            - 字数控制在100-150字左右
        """
    )

    messages = [{"role": "system", "content": system_prompt}]

    if history:
        # 构建历史对话上下文——以多轮对话形式呈现
        for i, h in enumerate(history):
            round_num = i + 1
            # 对方的加持观点（user 角色）
            if h.get("enhanced"):
                messages.append({
                    "role": "user",
                    "content": f"[第{round_num}轮] 对方观点：{h['enhanced']}",
                })
            # 自己之前的反驳（assistant 角色）
            if h.get("refutation"):
                messages.append({
                    "role": "assistant",
                    "content": h["refutation"],
                })

        # 当前轮次的反驳请求
        messages.append({
            "role": "user",
            "content": (
                f"[第{len(history) + 1}轮] 对方针对你的反驳做出了新的回应，"
                f"加持后的观点如下：\n\n{enhanced_argument}\n\n"
                f"辩题：{topic_title}\n"
                f"对方立场：{side}\n\n"
            ),
        })
    else:
        # 第一轮，无历史
        messages.append({
            "role": "user",
            "content": (
                f"辩题：{topic_title}\n"
                f"对方立场：{side}\n"
                f"对方观点：{enhanced_argument}\n\n"
            ),
        })

    result = call_llm_api(
        api_url=config["REFUTE_MODEL_API_URL"],
        api_key=config["REFUTE_MODEL_API_KEY"],
        model=chosen_model_name,
        messages=messages,
    )

    return result, chosen_model_name


def generate_quiz(config, topic_title, side, refutation):
    """
    "出题"模型：根据 AI 的反驳内容生成一道四选一的理解力选择题。

    返回:
        dict: {"question": str, "options": ["A. ...", ...], "answer": "A"}
              解析失败时返回 None
    """
    system_prompt = (
        "你是一个面向中小学生的阅读理解出题专家。\n"
        "根据给定的一段文字（AI 在辩论中的反驳），出一道四选一的选择题来检验学生是否理解了这段话的核心意思。\n\n"
        "要求：\n"
        "1. 题目用通俗易懂的语言，适合中小学生\n"
        "2. 四个选项中只有一个正确答案，其余三个为干扰项\n"
        "3. 干扰项要有一定迷惑性，但不要过于刁钻\n"
        "4. 严格按照下面的 JSON 格式输出，不要输出任何其他内容：\n"
        '{"question": "题目内容", "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"], "answer": "A"}\n'
        "其中 answer 只填选项字母（A/B/C/D）。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"辩题：{topic_title}\n"
            f"学生立场：{side}\n\n"
            f"AI 的反驳内容：\n{refutation}\n\n"
            f"请根据这段反驳内容出一道选择题。"
        )},
    ]

    raw = call_llm_api(
        api_url=config["QUIZ_MODEL_API_URL"],
        api_key=config["QUIZ_MODEL_API_KEY"],
        model=config["QUIZ_MODEL_NAME"],
        messages=messages,
        temperature=0.3,
    )

    # 解析 JSON —— 模型可能包裹 ```json ... ```
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        if "question" in data and "options" in data and "answer" in data:
            return data
    except (json.JSONDecodeError, KeyError, IndexError):
        pass

    return None
