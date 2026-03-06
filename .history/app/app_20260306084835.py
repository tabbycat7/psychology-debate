"""
心理测评辩论平台 —— Flask 主应用
"""
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from config import Config
from models import db, DebateSession
from questions import get_all_topics, get_topic_by_id, get_all_categories
from llm_api import enhance_argument, refute_argument


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化数据库
    db.init_app(app)
    with app.app_context():
        db.create_all()

    return app


app = create_app()


# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    """首页 —— 辩题列表"""
    topics = get_all_topics()
    categories = get_all_categories()
    return render_template('index.html', topics=topics, categories=categories)


@app.route('/debate/<topic_id>')
def debate_page(topic_id):
    """辩论页面 —— 选择立场并提交观点"""
    topic = get_topic_by_id(topic_id)
    if not topic:
        return redirect(url_for('index'))
    return render_template('debate.html', topic=topic)


@app.route('/result/<int:session_id>')
def result_page(session_id):
    """辩论结果页面"""
    session = DebateSession.query.get_or_404(session_id)
    topic = get_topic_by_id(session.topic_id)
    return render_template('result.html', session=session, topic=topic)


@app.route('/history')
def history_page():
    """历史记录页面"""
    sessions = DebateSession.query.order_by(DebateSession.created_at.desc()).all()
    annotated_count = sum(1 for s in sessions if s.stance_changed is not None)
    pending_count = len(sessions) - annotated_count
    return render_template('history.html', sessions=sessions,
                           annotated_count=annotated_count, pending_count=pending_count)


@app.route('/annotate/<int:session_id>')
def annotate_page(session_id):
    """标注页面"""
    session = DebateSession.query.get_or_404(session_id)
    topic = get_topic_by_id(session.topic_id)
    return render_template('annotate.html', session=session, topic=topic)


# ============================================================
# API 路由
# ============================================================

@app.route('/api/debate/submit', methods=['POST'])
def submit_debate():
    """
    提交辩论观点
    请求参数:
        topic_id: 辩题ID
        student_name: 学生姓名
        chosen_side: 选择的立场 ('side_a' 或 'side_b')
        user_argument: 学生的辩论观点
    """
    data = request.json
    topic_id = data.get('topic_id')
    student_name = data.get('student_name', '匿名同学')
    chosen_side = data.get('chosen_side')
    user_argument = data.get('user_argument')

    # 参数校验
    if not all([topic_id, chosen_side, user_argument]):
        return jsonify({"success": False, "message": "缺少必要参数"}), 400

    topic = get_topic_by_id(topic_id)
    if not topic:
        return jsonify({"success": False, "message": "辩题不存在"}), 404

    chosen_side_text = topic['side_a'] if chosen_side == 'side_a' else topic['side_b']

    # 创建辩论会话
    session = DebateSession(
        student_name=student_name,
        topic_id=topic_id,
        topic_title=topic['title'],
        chosen_side=chosen_side,
        chosen_side_text=chosen_side_text,
        user_argument=user_argument,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        "success": True,
        "session_id": session.id,
        "message": "观点提交成功，正在进行加持润色..."
    })


@app.route('/api/debate/enhance/<int:session_id>', methods=['POST'])
def enhance(session_id):
    """
    调用"加持"模型润色学生观点
    """
    session = DebateSession.query.get_or_404(session_id)

    enhanced = enhance_argument(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        user_argument=session.user_argument,
    )

    session.enhanced_argument = enhanced
    db.session.commit()

    return jsonify({
        "success": True,
        "enhanced_argument": enhanced,
    })


@app.route('/api/debate/refute/<int:session_id>', methods=['POST'])
def refute(session_id):
    """
    调用"反驳"模型反驳学生观点
    """
    session = DebateSession.query.get_or_404(session_id)

    if not session.enhanced_argument:
        return jsonify({"success": False, "message": "请先进行加持润色"}), 400

    refutation, model_name = refute_argument(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        enhanced_argument=session.enhanced_argument,
    )

    session.refutation = refutation
    session.refute_model_name = model_name
    db.session.commit()

    return jsonify({
        "success": True,
        "refutation": refutation,
        "model_name": model_name,
    })


@app.route('/api/annotate/<int:session_id>', methods=['POST'])
def annotate(session_id):
    """
    人工标注接口
    请求参数:
        stance_changed: bool, 用户立场是否改变
        annotation_note: str, 标注备注（可选）
    """
    session = DebateSession.query.get_or_404(session_id)
    data = request.json

    session.stance_changed = data.get('stance_changed')
    session.annotation_note = data.get('annotation_note', '')
    session.annotated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "标注保存成功",
    })


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """获取所有辩论会话记录"""
    sessions = DebateSession.query.order_by(DebateSession.created_at.desc()).all()
    return jsonify({
        "success": True,
        "sessions": [s.to_dict() for s in sessions],
    })


@app.route('/api/export', methods=['GET'])
def export_data():
    """导出所有已标注的数据"""
    sessions = DebateSession.query.filter(
        DebateSession.stance_changed.isnot(None)
    ).order_by(DebateSession.created_at.desc()).all()
    return jsonify({
        "success": True,
        "data": [s.to_dict() for s in sessions],
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
