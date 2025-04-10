import logging
import os
import subprocess
import yaml
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///openwrt_builds.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the database with the app
db.init_app(app)

# Import models after db is defined
import models

# Create database tables within app context
with app.app_context():
    db.create_all()

def load_openwrt_config():
    """Load OpenWrt configuration"""
    try:
        with open('config/openwrt.yml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading OpenWrt config: {e}")
        return {}

def load_packages_config():
    """Load packages configuration"""
    try:
        with open('config/packages.yml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading packages config: {e}")
        return {}

@app.route('/')
def index():
    """Home page with build status and information"""
    openwrt_config = load_openwrt_config()
    builds = models.Build.query.order_by(models.Build.created_at.desc()).limit(5).all()
    
    # Count builds by status
    build_stats = {
        'success': models.Build.query.filter_by(status='success').count(),
        'failed': models.Build.query.filter_by(status='failed').count(),
        'in_progress': models.Build.query.filter_by(status='in_progress').count(),
        'total': models.Build.query.count()
    }
    
    # Get latest release
    latest_release = models.Release.query.order_by(models.Release.created_at.desc()).first()
    
    return render_template(
        'index.html',
        openwrt_config=openwrt_config,
        builds=builds,
        build_stats=build_stats,
        latest_release=latest_release,
        now=datetime.now()
    )

@app.route('/builds')
def builds():
    """List all builds"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Filter by status if provided
    status = request.args.get('status')
    target = request.args.get('target')
    
    query = models.Build.query
    
    if status:
        query = query.filter_by(status=status)
    
    if target:
        query = query.filter_by(target=target)
    
    pagination = query.order_by(models.Build.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    return render_template(
        'builds.html',
        builds=pagination.items,
        pagination=pagination,
        status=status,
        target=target,
        targets=load_openwrt_config().get('targets', []),
        now=datetime.now()
    )

@app.route('/releases')
def releases():
    """List all releases"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    pagination = models.Release.query.order_by(models.Release.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    return render_template(
        'releases.html',
        releases=pagination.items,
        pagination=pagination,
        now=datetime.now()
    )

@app.route('/api/builds', methods=['GET'])
def api_builds():
    """API endpoint to get builds"""
    builds = models.Build.query.order_by(models.Build.created_at.desc()).limit(10).all()
    return jsonify([build.to_dict() for build in builds])

@app.route('/api/releases', methods=['GET'])
def api_releases():
    """API endpoint to get releases"""
    releases = models.Release.query.order_by(models.Release.created_at.desc()).limit(10).all()
    return jsonify([release.to_dict() for release in releases])

@app.route('/api/build/<int:build_id>', methods=['GET'])
def api_build(build_id):
    """API endpoint to get build details"""
    build = models.Build.query.get_or_404(build_id)
    return jsonify(build.to_dict())

@app.route('/api/webhook', methods=['POST'])
def api_webhook():
    """Webhook endpoint for GitHub Actions to update build status"""
    # Simple webhook secret validation
    webhook_secret = os.environ.get('WEBHOOK_SECRET')
    if webhook_secret and request.headers.get('X-Webhook-Secret') != webhook_secret:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    event_type = data.get('event_type')
    
    if event_type == 'build_status':
        build_id = data.get('build_id')
        status = data.get('status')
        
        # Update or create build status
        build = models.Build.query.filter_by(build_id=build_id).first()
        if build:
            build.status = status
            build.updated_at = datetime.utcnow()
            if 'logs' in data:
                build.logs = data['logs']
        else:
            build = models.Build(
                build_id=build_id,
                target=data.get('target', 'unknown'),
                subtarget=data.get('subtarget', 'unknown'),
                version=data.get('version', 'unknown'),
                status=status,
                logs=data.get('logs', '')
            )
            db.session.add(build)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Build {build_id} updated'})
    
    elif event_type == 'release_created':
        version = data.get('version')
        url = data.get('url')
        
        # Create or update release
        release = models.Release.query.filter_by(version=version).first()
        if release:
            release.url = url
            release.updated_at = datetime.utcnow()
        else:
            release = models.Release(
                version=version,
                url=url,
                assets=data.get('assets', [])
            )
            db.session.add(release)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Release {version} updated'})
    
    return jsonify({'error': 'Unknown event type'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
