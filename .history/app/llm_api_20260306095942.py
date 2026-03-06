"""
大模型 API 接口封装

本文件封装了与大语言模型交互的接口，包括：
1. "加持"模型 —— 润色学生观点
2. "反驳"模型 —— 反驳学生观点（随机抽取一个模型）
"""
import random
import requests


def call_llm_api(api_url, api_key, model, messages, temperature=0.7, max_tokens=1024):
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


def enhance_argument(config, topic_title, side, user_argument):
    """
    "加持"模型：润色学生的辩论观点

    参数:
        config: Flask app.config 对象
        topic_title: 辩题标题
        side: 学生选择的立场
        user_argument: 学生提交的原始观点

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

    user_prompt = (
        f"辩题：{topic_title}\n"
        f"学生立场：{side}\n"
        f"学生原始观点：{user_argument}\n\n"
        f"请帮助润色和加强这个观点，使其更有说服力："
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    return call_llm_api(
        api_url=config["ENHANCE_MODEL_API_URL"],
        api_key=config["ENHANCE_MODEL_API_KEY"],
        model=config["ENHANCE_MODEL_NAME"],
        messages=messages,
    )


def refute_argument(config, topic_title, side, enhanced_argument):
    """
    "反驳"模型：反驳学生的（已润色）观点
    从配置的多个反驳模型中随机抽取一个进行回答

    参数:
        config: Flask app.config 对象
        topic_title: 辩题标题
        side: 学生选择的立场
        enhanced_argument: 经过润色的观点

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
        "6. 不要人身攻击，只针对观点进行反驳"
    )

    user_prompt = (
        f"辩题：{topic_title}\n"
        f"对方立场：{side}\n"
        f"对方观点：{enhanced_argument}\n\n"
        f"请从相反的立场对这个观点进行反驳："
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = call_llm_api(
        api_url=config["REFUTE_MODEL_API_URL"],
        api_key=config["REFUTE_MODEL_API_KEY"],
        model=chosen_model_name,
        messages=messages,
    )

    return result, chosen_model_name
