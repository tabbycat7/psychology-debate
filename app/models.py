"""
数据库模型定义
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class DebateSession(db.Model):
    """辩论会话记录"""
    __tablename__ = 'debate_sessions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 学生信息
    student_name = db.Column(db.String(100), nullable=False, default='匿名同学')

    # 辩题信息
    topic_id = db.Column(db.String(50), nullable=False)
    topic_title = db.Column(db.String(500), nullable=False)

    # 学生选择的立场 ('side_a' 或 'side_b')
    chosen_side = db.Column(db.String(10), nullable=False)
    chosen_side_text = db.Column(db.String(500), nullable=False)

    # 学生原始观点
    user_argument = db.Column(db.Text, nullable=False)

    # 加持模型润色后的观点
    enhanced_argument = db.Column(db.Text, nullable=True)

    # 反驳模型的反驳内容
    refutation = db.Column(db.Text, nullable=True)
    # 使用的反驳模型名称
    refute_model_name = db.Column(db.String(100), nullable=True)

    # ============================================================
    # 人工标注字段
    # ============================================================
    # 用户立场是否改变: None=未标注, True=改变, False=未改变
    stance_changed = db.Column(db.Boolean, nullable=True, default=None)
    # 标注备注
    annotation_note = db.Column(db.Text, nullable=True)
    # 标注时间
    annotated_at = db.Column(db.DateTime, nullable=True)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "student_name": self.student_name,
            "topic_id": self.topic_id,
            "topic_title": self.topic_title,
            "chosen_side": self.chosen_side,
            "chosen_side_text": self.chosen_side_text,
            "user_argument": self.user_argument,
            "enhanced_argument": self.enhanced_argument,
            "refutation": self.refutation,
            "refute_model_name": self.refute_model_name,
            "stance_changed": self.stance_changed,
            "annotation_note": self.annotation_note,
            "annotated_at": self.annotated_at.isoformat() if self.annotated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
