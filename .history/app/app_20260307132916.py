"""
心理测评辩论平台 —— Flask 主应用
"""
import os
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from config import Config
from models import db, DebateSession, DebateRound
from questions import get_all_topics, get_topic_by_id, get_all_categories
from llm_api import enhance_argument, refute_argument


def _ensure_database_exists(db_uri: str) -> None:
    """
    检测数据库是否存在，若不存在则自动创建。
    支持 SQLite / MySQL / PostgreSQL。
    """
    if db_uri.startswith("sqlite"):
        # sqlite:///relative/path.db  或  sqlite:////absolute/path.db
        # 取出文件路径部分（去掉 sqlite:/// 前缀）
        if db_uri.startswith("sqlite:////"):
            db_path = db_uri[len("sqlite:////"):]
            db_path = "/" + db_path          # 绝对路径
        elif db_uri.startswith("sqlite:///"):
            db_path = db_uri[len("sqlite:///"):]  # 相对路径
        else:
            db_path = None

        if db_path and db_path != ":memory:":
            db_dir = os.path.dirname(os.path.abspath(db_path))
            if not os.path.isdir(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                print(f"[DB] 已创建目录: {db_dir}")
            if not os.path.exists(db_path):
                print(f"[DB] SQLite 数据库文件将在首次写入时自动创建: {db_path}")
            else:
                print(f"[DB] 已找到 SQLite 数据库: {db_path}")

    elif db_uri.startswith("mysql") or db_uri.startswith("postgresql") or db_uri.startswith("postgres"):
        try:
            from sqlalchemy import create_engine, text
            from sqlalchemy.engine import make_url
            from sqlalchemy.exc import OperationalError

            url = make_url(db_uri)
            db_name = url.database

            # 连接到服务器（不指定数据库）
            server_url = url.set(database=None)
            engine = create_engine(server_url)

            with engine.connect() as conn:
                if db_uri.startswith("mysql"):
                    # DDL 语句需要 AUTOCOMMIT，否则 pymysql 默认事务不会提交
                    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                    result = conn.execute(
                        text(f"SHOW DATABASES LIKE '{db_name}'")
                    )
                    exists = result.fetchone() is not None
                    if not exists:
                        conn.execute(text(
                            f"CREATE DATABASE `{db_name}` "
                            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                        ))
                        print(f"[DB] 已创建 MySQL 数据库: {db_name}")
                    else:
                        print(f"[DB] 已找到 MySQL 数据库: {db_name}")
                else:
                    conn.execution_options(isolation_level="AUTOCOMMIT")
                    result = conn.execute(
                        text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
                    )
                    exists = result.fetchone() is not None
                    if not exists:
                        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                        print(f"[DB] 已创建 PostgreSQL 数据库: {db_name}")
                    else:
                        print(f"[DB] 已找到 PostgreSQL 数据库: {db_name}")

            engine.dispose()
        except Exception as e:
            print(f"[DB] 检测/创建数据库时出错（将继续尝试连接）: {e}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    _ensure_database_exists(db_uri)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        print("[DB] 所有数据表已就绪（不存在的表已自动创建）")

    return app


app = create_app()


# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    """首页 —— 辩题列表（每次刷新随机排序）"""
    topics = get_all_topics().copy()
    random.shuffle(topics)
    categories = get_all_categories()
    return render_template('index.html', topics=topics, categories=categories)


@app.route('/api/random_topic')
def random_topic():
    """随机抽取一个辩题"""
    topics = get_all_topics()
    if not topics:
        return jsonify({"success": False, "message": "暂无辩题"}), 404
    topic = random.choice(topics)
    return jsonify({"success": True, "topic": topic})


@app.route('/debate/<topic_id>')
def debate_page(topic_id):
    """辩论页面 —— 选择立场并提交观点"""
    topic = get_topic_by_id(topic_id)
    if not topic:
        return redirect(url_for('index'))
    return render_template('debate.html', topic=topic)


@app.route('/result/<session_id>')
def result_page(session_id):
    """辩论结果页面"""
    session = DebateSession.query.get_or_404(session_id)
    topic = get_topic_by_id(session.topic_id)
    rounds = DebateRound.query.filter_by(session_id=session_id).order_by(DebateRound.round_number).all()
    return render_template('result.html', session=session, topic=topic, rounds=rounds)


@app.route('/history')
def history_page():
    """历史记录页面"""
    sessions = DebateSession.query.order_by(DebateSession.created_at.desc()).all()
    annotated_count = sum(1 for s in sessions if s.stance_changed is not None)
    pending_count = len(sessions) - annotated_count
    return render_template('history.html', sessions=sessions,
                           annotated_count=annotated_count, pending_count=pending_count)


@app.route('/annotate/<session_id>')
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
    student_age = data.get('student_age')
    student_gender = data.get('student_gender')
    student_grade = data.get('student_grade')
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
        student_age=student_age,
        student_gender=student_gender,
        student_grade=student_grade,
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


@app.route('/api/debate/enhance/<session_id>', methods=['POST'])
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


@app.route('/api/debate/refute/<session_id>', methods=['POST'])
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


@app.route('/api/debate/continue/<session_id>', methods=['POST'])
def continue_debate(session_id):
    """
    继续辩论（新一轮）
    请求参数:
        user_argument: 学生针对AI反驳的回应
    """
    session = DebateSession.query.get_or_404(session_id)
    data = request.json
    user_argument = data.get('user_argument')

    if not user_argument:
        return jsonify({"success": False, "message": "请输入你的回应"}), 400

    # 计算新轮次编号
    new_round_number = session.total_rounds + 1

    # 创建新轮次记录
    debate_round = DebateRound(
        session_id=session.id,
        round_number=new_round_number,
        user_argument=user_argument,
    )
    db.session.add(debate_round)
    session.total_rounds = new_round_number
    db.session.commit()

    return jsonify({
        "success": True,
        "round_id": debate_round.id,
        "round_number": new_round_number,
        "message": "回应提交成功",
    })


def _build_debate_history(session, up_to_round=None):
    """
    构建辩论历史记录列表，供大模型参考。

    参数:
        session: DebateSession 对象
        up_to_round: 构建到第几轮之前的历史（不含该轮），None 表示全部

    返回:
        list: [{"enhanced": ..., "refutation": ..., "user_reply": ...}, ...]
    """
    history = []

    # 第1轮
    history.append({
        "enhanced": session.enhanced_argument,
        "refutation": session.refutation,
        "user_reply": None,  # 第1轮没有"回应"，后续轮次的 user_argument 才是回应
    })

    # 第2轮起
    rounds = DebateRound.query.filter_by(session_id=session.id).order_by(DebateRound.round_number).all()
    for r in rounds:
        if up_to_round is not None and r.round_number >= up_to_round:
            break
        # 上一轮的 user_reply 就是本轮学生的 user_argument
        if history:
            history[-1]["user_reply"] = r.user_argument
        history.append({
            "enhanced": r.enhanced_argument,
            "refutation": r.refutation,
            "user_reply": None,
        })

    return history


@app.route('/api/debate/enhance_round/<round_id>', methods=['POST'])
def enhance_round(round_id):
    """加持新一轮的学生观点（携带历史对话）"""
    debate_round = DebateRound.query.get_or_404(round_id)
    session = DebateSession.query.get_or_404(debate_round.session_id)

    # 构建到当前轮次之前的历史
    history = _build_debate_history(session, up_to_round=debate_round.round_number)

    enhanced = enhance_argument(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        user_argument=debate_round.user_argument,
        history=history,
    )

    debate_round.enhanced_argument = enhanced
    db.session.commit()

    return jsonify({
        "success": True,
        "enhanced_argument": enhanced,
    })


@app.route('/api/debate/refute_round/<round_id>', methods=['POST'])
def refute_round(round_id):
    """反驳新一轮的学生观点（携带历史对话，复用第一轮的反驳模型）"""
    debate_round = DebateRound.query.get_or_404(round_id)
    session = DebateSession.query.get_or_404(debate_round.session_id)

    if not debate_round.enhanced_argument:
        return jsonify({"success": False, "message": "请先进行加持润色"}), 400

    # 构建到当前轮次之前的历史
    history = _build_debate_history(session, up_to_round=debate_round.round_number)

    # 复用第一轮选定的反驳模型
    refutation, model_name = refute_argument(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        enhanced_argument=debate_round.enhanced_argument,
        history=history,
        fixed_model_name=session.refute_model_name,
    )

    debate_round.refutation = refutation
    debate_round.refute_model_name = model_name
    db.session.commit()

    return jsonify({
        "success": True,
        "refutation": refutation,
        "model_name": model_name,
    })


@app.route('/api/annotate/<session_id>', methods=['POST'])
def annotate(session_id):
    """
    人工标注 + 学生测评接口
    请求参数:
        stance_changed: bool, 用户立场是否改变
        annotation_note: str, 标注备注（可选）
        eval_understandable: int (1-5), 能理解
        eval_seen: int (1-5), 被看见
        eval_educational: int (1-5), 懂教育
        eval_comment: str, 学生对 AI 的自由评价（可选）
    """
    session = DebateSession.query.get_or_404(session_id)
    data = request.json

    # 学生测评
    session.eval_understandable = data.get('eval_understandable')
    session.eval_seen = data.get('eval_seen')
    session.eval_educational = data.get('eval_educational')
    session.eval_comment = data.get('eval_comment', '')

    # 人工标注
    session.stance_changed = data.get('stance_changed')
    session.annotation_note = data.get('annotation_note', '')
    session.annotated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "保存成功",
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
