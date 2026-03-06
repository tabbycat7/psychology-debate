"""
大模型 API 接口封装

本文件封装了与大语言模型交互的接口，包括：
1. "加持"模型 —— 润色学生观点
2. "反驳"模型 —— 反驳学生观点（随机抽取一个模型）
"""
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
        "你是一个辩论教练助手，专门帮助中小学生润色和加强他们的辩论观点。"
        "你的任务是保留学生观点的核心意思，但让论述更有逻辑性、更有说服力。"
        "注意：\n"
        "1. 保持语言通俗易懂，适合中小学生理解\n"
        "2. 保留学生原始观点的方向和核心论据\n"
        "3. 补充适当的论据和例子来加强论述\n"
        "4. 让语言更加流畅和有条理\n"
        "5. 回复长度适中，不要太长\n"
        "6. 以第一人称进行回复，不要包含任何冗余内容"
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
                f"请结合之前的辩论历史，帮助润色和加强这个观点，使其更有说服力，"
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
                f"请帮助润色和加强这个观点，使其更有说服力："
            ),
        })

    return call_llm_api(
        api_url=config["ENHANCE_MODEL_API_URL"],
        api_key=config["ENHANCE_MODEL_API_KEY"],
        model=config["ENHANCE_MODEL_NAME"],
        messages=messages,
    )


def refute_argument(config, topic_title, side, enhanced_argument, history=None):
    """
    "反驳"模型：反驳学生的（已润色）观点
    从配置的多个反驳模型中随机抽取一个进行回答

    参数:
        config: Flask app.config 对象
        topic_title: 辩题标题
        side: 学生选择的立场
        enhanced_argument: 经过润色的观点
        history: 历史辩论记录列表（可选），格式：
            [{"enhanced": "加持后观点", "refutation": "AI反驳"}, ...]

    返回:
        tuple: (反驳内容, 使用的模型名称)
    """
    # 从模型名称列表中随机抽取一个
    chosen_model_name = random.choice(config["REFUTE_MODEL_NAMES"])

    system_prompt = (
        "你是一个辩论对手，你的任务是针对对方的观点进行有力的反驳。"
        "注意：\n"
        "1. 语言要通俗易懂，适合中小学生理解\n"
        "2. 反驳要有逻辑性，提出有力的反面论据\n"
        "3. 可以用生活中的例子来支持你的反驳\n"
        "4. 态度要友好但立场要坚定\n"
        "5. 回复长度适中，不要太长\n"
        "6. 不要人身攻击，只针对观点进行反驳\n"
        "7. 不要重复之前已经使用过的论点，要提出新的反驳角度"
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
                f"请从相反的立场对这个新观点进行反驳，注意不要重复之前已经说过的论点，"
                f"要从新的角度进行反驳："
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
                f"请从相反的立场对这个观点进行反驳："
            ),
        })

    result = call_llm_api(
        api_url=config["REFUTE_MODEL_API_URL"],
        api_key=config["REFUTE_MODEL_API_KEY"],
        model=chosen_model_name,
        messages=messages,
    )

    return result, chosen_model_name
