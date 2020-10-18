from __future__ import absolute_import
from flask_mongoengine import MongoEngine
db = MongoEngine()

class User(db.Document):
    user_id = db.StringField(required=True, unique=True)
    username = db.StringField(required=True, unique=True)
    password = db.StringField()
    role = db.IntField()

class Contest(db.Document):
    contest_id = db.StringField(required=True, unique=True)
    contest_name = db.StringField()
    metrics = db.ListField()
    user_id = db.StringField(required=True)
    contest_status = db.StringField(required=True)
class Problem(db.Document):
    problem_id = db.StringField(required=True, unique=True)
    problem_name = db.StringField(required=True)
    problem_status = db.StringField(required=True)
    sources = db.ListField()
    metrics = db.ListField()
    similarity_list = db.ListField()
    alignment_list = db.ListField()
    similarity_smoss_list = db.ListField()
    alignment_smoss_list = db.ListField()
    contest_id = db.StringField()
    user_id = db.StringField()

