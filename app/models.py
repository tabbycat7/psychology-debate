"""
数据库模型定义
"""
import uuid
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def generate_session_id():
    """生成 S- 前缀的会话ID"""
    return f"S-{uuid.uuid4().hex[:12]}"


def generate_round_id():
    """生成 R- 前缀的轮次ID"""
    return f"R-{uuid.uuid4().hex[:12]}"


class DebateSession(db.Model):
    """辩论会话记录"""
    __tablename__ = 'debate_sessions'

    id = db.Column(db.String(20), primary_key=True, default=generate_session_id)
    # 学生信息
    student_name = db.Column(db.String(100), nullable=False, default='匿名同学')
    student_age = db.Column(db.Integer, nullable=True)
    student_gender = db.Column(db.String(10), nullable=True)       # 男 / 女 / 其他
    student_grade = db.Column(db.String(20), nullable=True)        # 如：小学三年级、初中一年级

    # 辩题信息
    topic_id = db.Column(db.String(50), nullable=False)
    topic_title = db.Column(db.String(500), nullable=False)
    # 辩题对应的测评“命中”立场（如 side_a / side_b），来自 questions 中的 hit 字段
    topic_hit = db.Column(db.String(20), nullable=True)

    # 学生选择的立场 ('side_a' 或 'side_b')
    chosen_side = db.Column(db.String(10), nullable=False)
    chosen_side_text = db.Column(db.String(500), nullable=False)

    # 学生原始观点（第一轮）
    user_argument = db.Column(db.Text, nullable=False)

    # 加持模型润色后的观点（第一轮）
    enhanced_argument = db.Column(db.Text, nullable=True)
    enhance_regenerate_count = db.Column(db.Integer, default=0)
    enhance_approved = db.Column(db.Boolean, nullable=True)

    # 反驳模型的反驳内容（第一轮）
    refutation = db.Column(db.Text, nullable=True)
    # 使用的反驳模型名称
    refute_model_name = db.Column(db.String(100), nullable=True)

    # 辩论轮数
    total_rounds = db.Column(db.Integer, default=1)

    # 每轮测评（第1轮）
    quiz_question = db.Column(db.Text, nullable=True)
    quiz_options = db.Column(db.Text, nullable=True)       # JSON: ["A. ...", "B. ...", ...]
    quiz_correct_answer = db.Column(db.String(10), nullable=True)  # "A" / "B" / "C" / "D"
    quiz_student_answer = db.Column(db.String(10), nullable=True)
    quiz_is_correct = db.Column(db.Boolean, nullable=True)
    inspired_by_ai = db.Column(db.Boolean, nullable=True)
    stance_changed = db.Column(db.Boolean, nullable=True)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联多轮辩论记录
    rounds = db.relationship('DebateRound', backref='session', lazy=True, order_by='DebateRound.round_number')

    def to_dict(self):
        return {
            "id": self.id,
            "student_name": self.student_name,
            "student_age": self.student_age,
            "student_gender": self.student_gender,
            "student_grade": self.student_grade,
            "topic_id": self.topic_id,
            "topic_title": self.topic_title,
            "topic_hit": self.topic_hit,
            "chosen_side": self.chosen_side,
            "chosen_side_text": self.chosen_side_text,
            "user_argument": self.user_argument,
            "enhanced_argument": self.enhanced_argument,
            "enhance_regenerate_count": self.enhance_regenerate_count,
            "enhance_approved": self.enhance_approved,
            "refutation": self.refutation,
            "refute_model_name": self.refute_model_name,
            "total_rounds": self.total_rounds,
            "quiz_question": self.quiz_question,
            "quiz_options": self.quiz_options,
            "quiz_correct_answer": self.quiz_correct_answer,
            "quiz_student_answer": self.quiz_student_answer,
            "quiz_is_correct": self.quiz_is_correct,
            "inspired_by_ai": self.inspired_by_ai,
            "stance_changed": self.stance_changed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "rounds": [r.to_dict() for r in self.rounds],
        }


class DebateRound(db.Model):
    """辩论轮次记录（第2轮起）"""
    __tablename__ = 'debate_rounds'

    id = db.Column(db.String(20), primary_key=True, default=generate_round_id)
    session_id = db.Column(db.String(20), db.ForeignKey('debate_sessions.id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)  # 轮次编号，从2开始

    # 学生本轮的回应
    user_argument = db.Column(db.Text, nullable=False)
    # 加持后的观点
    enhanced_argument = db.Column(db.Text, nullable=True)
    enhance_regenerate_count = db.Column(db.Integer, default=0)
    enhance_approved = db.Column(db.Boolean, nullable=True)
    # AI 的反驳
    refutation = db.Column(db.Text, nullable=True)
    refute_model_name = db.Column(db.String(100), nullable=True)

    # 每轮测评
    quiz_question = db.Column(db.Text, nullable=True)
    quiz_options = db.Column(db.Text, nullable=True)
    quiz_correct_answer = db.Column(db.String(10), nullable=True)
    quiz_student_answer = db.Column(db.String(10), nullable=True)
    quiz_is_correct = db.Column(db.Boolean, nullable=True)
    inspired_by_ai = db.Column(db.Boolean, nullable=True)
    stance_changed = db.Column(db.Boolean, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "round_number": self.round_number,
            "user_argument": self.user_argument,
            "enhanced_argument": self.enhanced_argument,
            "enhance_regenerate_count": self.enhance_regenerate_count,
            "enhance_approved": self.enhance_approved,
            "refutation": self.refutation,
            "refute_model_name": self.refute_model_name,
            "quiz_question": self.quiz_question,
            "quiz_options": self.quiz_options,
            "quiz_correct_answer": self.quiz_correct_answer,
            "quiz_student_answer": self.quiz_student_answer,
            "quiz_is_correct": self.quiz_is_correct,
            "inspired_by_ai": self.inspired_by_ai,
            "stance_changed": self.stance_changed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
