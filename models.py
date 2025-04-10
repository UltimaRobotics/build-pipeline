from datetime import datetime
import json
from app import db
from sqlalchemy.types import Text, JSON

class Build(db.Model):
    """OpenWrt build model"""
    id = db.Column(db.Integer, primary_key=True)
    build_id = db.Column(db.String(64), unique=True, nullable=False)
    target = db.Column(db.String(64), nullable=False)
    subtarget = db.Column(db.String(64), nullable=False)
    version = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='pending')
    logs = db.Column(Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Build {self.build_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'build_id': self.build_id,
            'target': self.target,
            'subtarget': self.subtarget,
            'version': self.version,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Release(db.Model):
    """OpenWrt release model"""
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(64), unique=True, nullable=False)
    url = db.Column(db.String(256), nullable=False)
    assets = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Release {self.version}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'url': self.url,
            'assets': self.assets,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
