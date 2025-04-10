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
    profile = db.Column(db.String(64), nullable=True)
    version = db.Column(db.String(64), nullable=False)
    openwrt_version = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default='pending')
    logs = db.Column(Text, nullable=True)
    packages = db.Column(JSON, nullable=True)  # Selected packages
    config = db.Column(JSON, nullable=True)    # Complete configuration
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
            'profile': self.profile,
            'version': self.version,
            'openwrt_version': self.openwrt_version,
            'status': self.status,
            'packages': self.packages,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Repository(db.Model):
    """Git repository for custom packages"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    url = db.Column(db.String(256), nullable=False)
    branch = db.Column(db.String(64), default="main")
    auth_token = db.Column(db.String(128), nullable=True)  # Token for private repos
    enabled = db.Column(db.Boolean, default=True)
    packages = db.Column(JSON, nullable=True)  # List of packages in this repo
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Repository {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'branch': self.branch,
            'enabled': self.enabled,
            'packages': self.packages,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def get_url_with_token(self):
        """Returns the URL with auth token embedded if present"""
        if not self.auth_token:
            return self.url
            
        # For GitHub URLs
        if 'github.com' in self.url:
            # Check format of URL (https or git protocol)
            if self.url.startswith('https://'):
                parts = self.url.split('://')
                return f"{parts[0]}://{self.auth_token}@{parts[1]}"
            elif self.url.startswith('git@'):
                return self.url  # SSH key auth doesn't need token in URL
        
        # For other URLs, generic handling
        if self.url.startswith('https://'):
            parts = self.url.split('://')
            return f"{parts[0]}://{self.auth_token}@{parts[1]}"
            
        return self.url

class Release(db.Model):
    """OpenWrt release model"""
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(64), unique=True, nullable=False)
    url = db.Column(db.String(256), nullable=False)
    assets = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with Build
    build_id = db.Column(db.Integer, db.ForeignKey('build.id'), nullable=True)
    build = db.relationship('Build', backref=db.backref('releases', lazy=True))
    
    def __repr__(self):
        return f'<Release {self.version}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'version': self.version,
            'url': self.url,
            'assets': self.assets,
            'build_id': self.build_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
