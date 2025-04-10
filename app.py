import json
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

@app.route('/build/<int:build_id>')
def build_detail(build_id):
    """Show build details"""
    build = models.Build.query.get_or_404(build_id)
    return render_template(
        'build_detail.html',
        build=build,
        now=datetime.now()
    )

@app.route('/api/build/<int:build_id>', methods=['GET'])
def api_build(build_id):
    """API endpoint to get build details"""
    build = models.Build.query.get_or_404(build_id)
    return jsonify(build.to_dict())

@app.route('/config')
def config():
    """Configuration page for build settings"""
    openwrt_config = load_openwrt_config()
    packages_config = load_packages_config()
    
    # Get all targets from the config
    targets = openwrt_config.get('targets', [])
    
    return render_template(
        'config.html',
        targets=targets,
        packages_config=packages_config,
        now=datetime.now()
    )

@app.route('/save_config', methods=['POST'])
def save_config():
    """Save build configuration"""
    try:
        # Get basic build info
        target = request.form.get('target')
        subtarget = request.form.get('subtarget')
        profile = request.form.get('profile')
        openwrt_version = request.form.get('openwrt_version')
        build_version = request.form.get('build_version')
        
        # Get selected packages
        selected_packages = request.form.getlist('selected_packages[]')
        
        # Get repository info
        repo_names = request.form.getlist('repo_name[]')
        repo_urls = request.form.getlist('repo_url[]')
        repo_branches = request.form.getlist('repo_branch[]')
        repo_tokens = request.form.getlist('repo_token[]')
        repo_enabled = request.form.getlist('repo_enabled[]')
        repo_packages = request.form.getlist('repo_packages[]')
        
        # Create repositories list for the config
        repositories = []
        
        # Create a unique build ID
        build_id = f"{target}_{subtarget}_{int(datetime.now().timestamp())}"
        
        # Create a new build entry
        build = models.Build(
            build_id=build_id,
            target=target,
            subtarget=subtarget,
            profile=profile,
            version=build_version,
            openwrt_version=openwrt_version,
            status='pending',
            logs='Build configuration created',
            packages=selected_packages
        )
        db.session.add(build)
        db.session.flush()  # Get the ID without committing
        
        # Process and save repositories to the database
        for i in range(len(repo_names)):
            if repo_names[i] and repo_urls[i]:  # Only add if name and URL are provided
                repo_packages_list = [pkg.strip() for pkg in repo_packages[i].split(',') if pkg.strip()]
                
                # Check if this repository already exists
                existing_repo = models.Repository.query.filter_by(
                    name=repo_names[i], 
                    url=repo_urls[i]
                ).first()
                
                if existing_repo:
                    # Update existing repository
                    existing_repo.branch = repo_branches[i] or 'main'
                    if repo_tokens[i]:  # Only update token if provided
                        existing_repo.auth_token = repo_tokens[i]
                    existing_repo.enabled = i < len(repo_enabled)
                    existing_repo.packages = repo_packages_list
                    db.session.add(existing_repo)
                    repo_obj = existing_repo
                else:
                    # Create new repository
                    repo = models.Repository(
                        name=repo_names[i],
                        url=repo_urls[i],
                        branch=repo_branches[i] or 'main',
                        auth_token=repo_tokens[i] if repo_tokens[i] else None,
                        enabled=i < len(repo_enabled),
                        packages=repo_packages_list
                    )
                    db.session.add(repo)
                    db.session.flush()  # Get the ID without committing
                    repo_obj = repo
                
                # Add to the repositories list for config
                repo_config = repo_obj.to_dict()
                # Remove sensitive information
                if 'auth_token' in repo_config:
                    del repo_config['auth_token']
                repositories.append(repo_config)
        
        # Create config dictionary
        config = {
            'target': target,
            'subtarget': subtarget,
            'profile': profile,
            'openwrt_version': openwrt_version,
            'build_version': build_version,
            'packages': selected_packages,
            'repositories': repositories,
            'created_at': datetime.now().isoformat()
        }
        
        # Save the complete config to the build
        build.config = config
        
        # Save to a JSON file as backup
        config_path = os.path.join('instance', f'build_config_{build_id}.json')
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        db.session.commit()
        
        flash('Build configuration saved successfully. Build has been queued.', 'success')
        return redirect(url_for('builds'))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving configuration: {e}")
        flash(f"Error saving configuration: {str(e)}", 'danger')
        return redirect(url_for('config'))

@app.route('/repositories')
def repositories():
    """List all repositories"""
    repos = models.Repository.query.order_by(models.Repository.name).all()
    return render_template(
        'repositories.html',
        repositories=repos,
        now=datetime.now()
    )

@app.route('/repository/add', methods=['GET', 'POST'])
def add_repository():
    """Add a new repository"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            url = request.form.get('url')
            branch = request.form.get('branch', 'main')
            auth_token = request.form.get('auth_token')
            enabled = 'enabled' in request.form
            packages_str = request.form.get('packages', '')
            
            # Parse packages list
            packages = [pkg.strip() for pkg in packages_str.split(',') if pkg.strip()]
            
            # Create repository
            repo = models.Repository(
                name=name,
                url=url,
                branch=branch,
                auth_token=auth_token,
                enabled=enabled,
                packages=packages
            )
            
            db.session.add(repo)
            db.session.commit()
            
            flash('Repository added successfully.', 'success')
            return redirect(url_for('repositories'))
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding repository: {e}")
            flash(f"Error adding repository: {str(e)}", 'danger')
    
    return render_template(
        'repository_form.html',
        repository=None,
        now=datetime.now()
    )

@app.route('/repository/edit/<int:repo_id>', methods=['GET', 'POST'])
def edit_repository(repo_id):
    """Edit a repository"""
    repo = models.Repository.query.get_or_404(repo_id)
    
    if request.method == 'POST':
        try:
            repo.name = request.form.get('name')
            repo.url = request.form.get('url')
            repo.branch = request.form.get('branch', 'main')
            auth_token = request.form.get('auth_token')
            repo.enabled = 'enabled' in request.form
            packages_str = request.form.get('packages', '')
            
            # Only update token if provided
            if auth_token:
                repo.auth_token = auth_token
            
            # Parse packages list
            packages = [pkg.strip() for pkg in packages_str.split(',') if pkg.strip()]
            repo.packages = packages
            
            db.session.commit()
            
            flash('Repository updated successfully.', 'success')
            return redirect(url_for('repositories'))
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating repository: {e}")
            flash(f"Error updating repository: {str(e)}", 'danger')
    
    return render_template(
        'repository_form.html',
        repository=repo,
        now=datetime.now()
    )

@app.route('/repository/toggle/<int:repo_id>', methods=['POST'])
def toggle_repository(repo_id):
    """Toggle repository enabled/disabled status"""
    repo = models.Repository.query.get_or_404(repo_id)
    
    try:
        repo.enabled = not repo.enabled
        db.session.commit()
        
        status = "enabled" if repo.enabled else "disabled"
        flash(f"Repository {repo.name} {status} successfully.", 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling repository status: {e}")
        flash(f"Error updating repository status: {str(e)}", 'danger')
    
    return redirect(url_for('repositories'))

@app.route('/repository/delete/<int:repo_id>', methods=['POST'])
def delete_repository(repo_id):
    """Delete a repository"""
    repo = models.Repository.query.get_or_404(repo_id)
    
    try:
        db.session.delete(repo)
        db.session.commit()
        
        flash(f"Repository {repo.name} deleted successfully.", 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting repository: {e}")
        flash(f"Error deleting repository: {str(e)}", 'danger')
    
    return redirect(url_for('repositories'))

@app.route('/api/targets', methods=['GET'])
def api_targets():
    """API endpoint to get available targets"""
    openwrt_config = load_openwrt_config()
    return jsonify(openwrt_config.get('targets', []))

@app.route('/api/packages', methods=['GET'])
def api_packages():
    """API endpoint to get available packages for a target/subtarget"""
    target = request.args.get('target')
    subtarget = request.args.get('subtarget')
    
    # Mock data for now - in a real implementation, this would fetch packages from OpenWrt
    packages = [
        {'name': 'luci', 'description': 'OpenWrt Web UI'},
        {'name': 'curl', 'description': 'URL retrieval utility'},
        {'name': 'wget', 'description': 'Network utility to retrieve files'},
        {'name': 'nano', 'description': 'Small editor for config files'},
        {'name': 'htop', 'description': 'Interactive process viewer'},
        {'name': 'iperf3', 'description': 'Network bandwidth measuring tool'},
        {'name': 'vim', 'description': 'VI improved text editor'},
        {'name': 'tmux', 'description': 'Terminal multiplexer'},
        {'name': 'kmod-usb-net', 'description': 'USB net support'},
        {'name': 'luci-app-firewall', 'description': 'Firewall configuration UI'},
        {'name': 'wireguard', 'description': 'VPN protocol'},
        {'name': 'openvpn', 'description': 'OpenVPN client/server'}
    ]
    
    return jsonify(packages)

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
