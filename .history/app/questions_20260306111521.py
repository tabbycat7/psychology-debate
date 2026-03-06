"""
心理测评辩题接口文件

在此文件中添加心理测评问题，每个问题以辩题的形式呈现。
格式说明：
  - id: 辩题唯一标识
  - category: 分类标签（如"情绪管理"、"人际关系"等）
  - title: 辩题标题
  - description: 辩题描述/背景说明
  - side_a: 正方立场描述
  - side_b: 反方立场描述
  - psychological_dimension: 对应的心理测评维度（可选）
"""

DEBATE_TOPICS = [
    # ============================================================
    # 示例辩题 —— 请在下方按照格式添加更多心理测评辩题
    # ============================================================
    {
        "id": "Q001",
        "category": "情绪管理",
        "title": "遇到困难时，应该先处理情绪还是先解决问题？",
        "description": "小明考试没考好，心情很低落。他的好朋友建议他先让自己开心起来，但老师说应该马上分析错题。你觉得哪种做法更好？",
        "side_a": "应该先处理情绪，让自己平静下来再解决问题",
        "side_b": "应该先解决问题，问题解决了情绪自然就好了",
        "psychological_dimension": "情绪调节策略",
    },
    {
        "id": "Q002",
        "category": "人际关系",
        "title": "好朋友之间应该什么话都说还是有所保留？",
        "description": "小红和小丽是最好的朋友，小红画了一幅画觉得很满意，但小丽觉得画得不太好。小丽应该直接说出真实想法，还是说一些鼓励的话？",
        "side_a": "好朋友之间应该坦诚相告，真诚最重要",
        "side_b": "好朋友之间要注意说话方式，适当保留也是一种关心",
        "psychological_dimension": "社交技能",
    },
    {
        "id": "Q003",
        "category": "自我认知",
        "title": "一个人的性格是天生的还是可以改变的？",
        "description": "小刚是个比较内向的孩子，他的爸爸妈妈希望他变得更外向一些。小刚觉得内向没什么不好，但有时候也想变得更大方。性格到底能不能改变呢？",
        "side_a": "性格主要是天生的，应该接受并发挥自己性格的优势",
        "side_b": "性格是可以改变的，通过努力可以培养更好的性格",
        "psychological_dimension": "自我效能感",
    },

    # ============================================================
    # 请在此处继续添加更多辩题...
    # 格式参考上方示例
    # ============================================================
]


def get_all_topics():
    """获取所有辩题列表"""
    return DEBATE_TOPICS


def get_topic_by_id(topic_id):
    """根据ID获取单个辩题"""
    for topic in DEBATE_TOPICS:
        if topic["id"] == topic_id:
            return topic
    return None


def get_topics_by_category(category):
    """根据分类获取辩题"""
    return [t for t in DEBATE_TOPICS if t["category"] == category]


def get_all_categories():
    """获取所有分类"""
    return list(set(t["category"] for t in DEBATE_TOPICS))
