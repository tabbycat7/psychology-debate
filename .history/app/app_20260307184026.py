"""
心理测评辩论平台 —— Flask 主应用
"""
import os
import random
from flask import Flask, render_template, request, jsonify, redirect, url_for
from config import Config
from models import db, DebateSession, DebateRound
from questions import get_all_topics, get_topic_by_id, get_all_categories
from llm_api import enhance_argument, refute_argument, generate_quiz
import json


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


def _migrate_add_missing_columns(app):
    """
    对比 SQLAlchemy 模型定义与数据库中实际存在的列，
    自动为已有表补充缺失的列（仅做 ADD COLUMN，不删不改）。
    适用于 MySQL / PostgreSQL / SQLite。
    """
    from sqlalchemy import inspect as sa_inspect, text

    engine = db.engine
    inspector = sa_inspect(engine)

    for table_name, model_class in db.Model.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue

        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in model_class.columns:
            if col.name in existing_cols:
                continue

            col_type = col.type.compile(dialect=engine.dialect)
            nullable = "NULL" if col.nullable else "NOT NULL"
            default_clause = ""
            if col.default is not None and col.default.is_scalar:
                val = col.default.arg
                if isinstance(val, bool):
                    default_clause = f" DEFAULT {1 if val else 0}"
                elif isinstance(val, (int, float)):
                    default_clause = f" DEFAULT {val}"
                elif isinstance(val, str):
                    default_clause = f" DEFAULT '{val}'"

            sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col.name}` {col_type} {nullable}{default_clause}"
            try:
                with engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
                print(f"[DB] 已为表 {table_name} 添加列: {col.name}")
            except Exception as e:
                print(f"[DB] 添加列 {table_name}.{col.name} 时出错: {e}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    _ensure_database_exists(db_uri)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        _migrate_add_missing_columns(app)
        print("[DB] 所有数据表已就绪（不存在的表已自动创建，缺失列已补充）")

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
    return render_template('history.html', sessions=sessions)


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

    is_regenerate = session.enhanced_argument is not None

    enhanced = enhance_argument(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        user_argument=session.user_argument,
    )

    session.enhanced_argument = enhanced
    if is_regenerate:
        session.enhance_regenerate_count = (session.enhance_regenerate_count or 0) + 1
    db.session.commit()

    return jsonify({
        "success": True,
        "enhanced_argument": enhanced,
    })


@app.route('/api/debate/update_enhanced/<session_id>', methods=['POST'])
def update_enhanced(session_id):
    """学生手动修改润色后的观点"""
    session = DebateSession.query.get_or_404(session_id)
    data = request.json
    edited = data.get('enhanced_argument', '').strip()
    if not edited:
        return jsonify({"success": False, "message": "内容不能为空"}), 400
    session.enhanced_argument = edited
    db.session.commit()
    return jsonify({"success": True, "enhanced_argument": edited})


@app.route('/api/debate/update_enhanced_round/<round_id>', methods=['POST'])
def update_enhanced_round(round_id):
    """学生手动修改某一轮润色后的观点"""
    debate_round = DebateRound.query.get_or_404(round_id)
    data = request.json
    edited = data.get('enhanced_argument', '').strip()
    if not edited:
        return jsonify({"success": False, "message": "内容不能为空"}), 400
    debate_round.enhanced_argument = edited
    db.session.commit()
    return jsonify({"success": True, "enhanced_argument": edited})


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

    is_regenerate = debate_round.enhanced_argument is not None

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
    if is_regenerate:
        debate_round.enhance_regenerate_count = (debate_round.enhance_regenerate_count or 0) + 1
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


@app.route('/api/debate/quiz/<session_id>', methods=['POST'])
def quiz_for_session(session_id):
    """为第 1 轮生成理解力选择题"""
    session = DebateSession.query.get_or_404(session_id)
    if not session.refutation:
        return jsonify({"success": False, "message": "还没有反驳内容"}), 400

    quiz = generate_quiz(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        refutation=session.refutation,
    )
    if not quiz:
        return jsonify({"success": False, "message": "出题失败，请重试"}), 500

    session.quiz_question = quiz["question"]
    session.quiz_options = json.dumps(quiz["options"], ensure_ascii=False)
    session.quiz_correct_answer = quiz["answer"]
    db.session.commit()

    return jsonify({
        "success": True,
        "question": quiz["question"],
        "options": quiz["options"],
    })


@app.route('/api/debate/quiz_round/<round_id>', methods=['POST'])
def quiz_for_round(round_id):
    """为第 2 轮及之后生成理解力选择题"""
    debate_round = DebateRound.query.get_or_404(round_id)
    session = DebateSession.query.get_or_404(debate_round.session_id)
    if not debate_round.refutation:
        return jsonify({"success": False, "message": "还没有反驳内容"}), 400

    quiz = generate_quiz(
        config=app.config,
        topic_title=session.topic_title,
        side=session.chosen_side_text,
        refutation=debate_round.refutation,
    )
    if not quiz:
        return jsonify({"success": False, "message": "出题失败，请重试"}), 500

    debate_round.quiz_question = quiz["question"]
    debate_round.quiz_options = json.dumps(quiz["options"], ensure_ascii=False)
    debate_round.quiz_correct_answer = quiz["answer"]
    db.session.commit()

    return jsonify({
        "success": True,
        "question": quiz["question"],
        "options": quiz["options"],
    })


@app.route('/api/debate/answer/<session_id>', methods=['POST'])
def answer_quiz_session(session_id):
    """提交第 1 轮的测评数据（选择题答案 / 是否被启发 / 立场变化，可分步提交）"""
    session = DebateSession.query.get_or_404(session_id)
    data = request.json

    student_answer = data.get('answer', '').strip().upper() if data.get('answer') else ''
    inspired_by_ai = data.get('inspired_by_ai')
    stance_changed = data.get('stance_changed')

    if student_answer:
        session.quiz_student_answer = student_answer
        session.quiz_is_correct = (student_answer == session.quiz_correct_answer)

    if inspired_by_ai is not None:
        session.inspired_by_ai = inspired_by_ai

    if stance_changed is not None:
        session.stance_changed = stance_changed

    db.session.commit()

    return jsonify({
        "success": True,
        "is_correct": session.quiz_is_correct,
        "correct_answer": session.quiz_correct_answer,
    })


@app.route('/api/debate/answer_round/<round_id>', methods=['POST'])
def answer_quiz_round(round_id):
    """提交第 2 轮及之后的测评数据（选择题答案 / 是否被启发 / 立场变化，可分步提交）"""
    debate_round = DebateRound.query.get_or_404(round_id)
    data = request.json

    student_answer = data.get('answer', '').strip().upper() if data.get('answer') else ''
    inspired_by_ai = data.get('inspired_by_ai')
    stance_changed = data.get('stance_changed')

    if student_answer:
        debate_round.quiz_student_answer = student_answer
        debate_round.quiz_is_correct = (student_answer == debate_round.quiz_correct_answer)

    if inspired_by_ai is not None:
        debate_round.inspired_by_ai = inspired_by_ai

    if stance_changed is not None:
        debate_round.stance_changed = stance_changed

    db.session.commit()

    return jsonify({
        "success": True,
        "is_correct": debate_round.quiz_is_correct,
        "correct_answer": debate_round.quiz_correct_answer,
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
    """导出所有辩论数据"""
    sessions = DebateSession.query.order_by(
        DebateSession.created_at.desc()
    ).all()
    return jsonify({
        "success": True,
        "data": [s.to_dict() for s in sessions],
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
