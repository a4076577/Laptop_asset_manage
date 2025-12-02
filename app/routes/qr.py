# Path: app/routes/qr.py
import uuid
import io
import base64
import qrcode
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Asset, Branch, AssetHistory, PreGeneratedQR, ScanLog, SystemSetting

qr_bp = Blueprint('qr', __name__)

def log_scan_event(qr_hash, asset_id=None):
    try:
        # Get real IP if behind Nginx proxy
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
            
        agent = request.headers.get('User-Agent')
        log = ScanLog(qr_hash=qr_hash, ip_address=ip, user_agent=agent[:200], linked_asset_id=asset_id)
        db.session.add(log)
        db.session.commit()
    except: pass

@qr_bp.route('/manage')
@login_required
def manage():
    branch_id = request.args.get('branch_id')
    status_filter = request.args.get('status')
    
    query = Asset.query
    if branch_id: query = query.filter(Asset.current_branch_id == branch_id)
    if status_filter and status_filter != 'All': query = query.filter(Asset.status == status_filter)
    assets = query.all()
    
    unassigned_qrs = PreGeneratedQR.query.filter_by(status='Available').order_by(PreGeneratedQR.created_at.desc()).all()
    branches = Branch.query.all()
    statuses = db.session.query(Asset.status).distinct().all()
    unique_statuses = [s[0] for s in statuses]
    
    global_scan = SystemSetting.query.filter_by(key='global_qr_scan').first()
    global_scan_enabled = True if not global_scan or global_scan.value == '1' else False
    
    return render_template('qr/manage.html', assets=assets, unassigned_qrs=unassigned_qrs, branches=branches, statuses=unique_statuses, global_scan_enabled=global_scan_enabled)

# --- NEW: SCAN HISTORY (Admin Only) ---
@qr_bp.route('/history')
@login_required
def scan_history():
    if current_user.email != 'admin@company.com':
        flash('Access Denied', 'error')
        return redirect(url_for('qr.manage'))
        
    page = request.args.get('page', 1, type=int)
    # Join with Asset to show serial numbers
    logs = db.session.query(ScanLog, Asset).outerjoin(Asset, ScanLog.linked_asset_id == Asset.id)\
        .order_by(ScanLog.timestamp.desc())\
        .paginate(page=page, per_page=50)
        
    return render_template('qr/history.html', logs=logs)

@qr_bp.route('/generate/<int:asset_id>', methods=['POST'])
@login_required
def generate(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    if not asset.qr_code_hash:
        asset.qr_code_hash = uuid.uuid4().hex
        asset.is_qr_active = True
        db.session.commit()
        flash('QR Code Generated', 'success')
    return redirect(request.referrer)

@qr_bp.route('/generate_batch', methods=['POST'])
@login_required
def generate_batch():
    count = int(request.form.get('count', 10))
    if count > 100: count = 100
    for _ in range(count):
        db.session.add(PreGeneratedQR(qr_hash=uuid.uuid4().hex, created_by=current_user.id))
    db.session.commit()
    flash(f'{count} Unassigned QR Codes generated.', 'success')
    return redirect(url_for('qr.manage'))

@qr_bp.route('/toggle/<int:asset_id>', methods=['POST'])
@login_required
def toggle_status(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    asset.is_qr_active = not asset.is_qr_active
    db.session.commit()
    return jsonify({'success': True, 'new_status': asset.is_qr_active})

@qr_bp.route('/scan/<qr_hash>')
def public_scan(qr_hash):
    global_scan = SystemSetting.query.filter_by(key='global_qr_scan').first()
    if global_scan and global_scan.value == '0':
        return render_template('qr/public_error.html', message="SYSTEM LOCKDOWN: Scanning is temporarily disabled.")

    asset = Asset.query.filter_by(qr_code_hash=qr_hash).first()
    
    if asset:
        log_scan_event(qr_hash, asset.id)
        if not asset.is_qr_active:
            return render_template('qr/public_error.html', message="This QR Code has been deactivated.")
        allocation_date = "N/A"
        if asset.holder:
            last_alloc = AssetHistory.query.filter_by(asset_id=asset.id, action='Allocation').order_by(AssetHistory.timestamp.desc()).first()
            if last_alloc: allocation_date = last_alloc.timestamp.strftime('%d %b %Y')
        return render_template('qr/public_view.html', asset=asset, allocation_date=allocation_date)

    pre_gen = PreGeneratedQR.query.filter_by(qr_hash=qr_hash, status='Available').first()
    if pre_gen:
        log_scan_event(qr_hash, None)
        if current_user.is_authenticated:
            available_assets = Asset.query.filter(Asset.qr_code_hash == None, Asset.status != 'Retired').all()
            return render_template('qr/link_sticker.html', qr_hash=qr_hash, assets=available_assets)
        else:
            return render_template('qr/public_error.html', message="Unassigned Tag. Contact IT Admin.")

    return render_template('qr/public_error.html', message="Invalid QR Code.")

@qr_bp.route('/link', methods=['POST'])
@login_required
def link_qr():
    qr_hash = request.form.get('qr_hash')
    asset_id = request.form.get('asset_id')
    pre_gen = PreGeneratedQR.query.filter_by(qr_hash=qr_hash, status='Available').first()
    asset = Asset.query.get(asset_id)
    
    if not pre_gen or not asset or asset.qr_code_hash:
        flash('Linking Failed.', 'error')
        return redirect(url_for('qr.manage'))

    asset.qr_code_hash = pre_gen.qr_hash
    asset.is_qr_active = True
    pre_gen.status = 'Consumed'
    
    hist = AssetHistory(asset_id=asset.id, action="QR Linked", from_detail="Unassigned Sticker", to_detail=f"Linked Hash", created_by_user_id=current_user.id, timestamp=datetime.now(), post_action_status=asset.status)
    db.session.add(hist)
    db.session.commit()
    flash(f'Sticker linked to {asset.serial_number}', 'success')
    return redirect(url_for('assets.detail', asset_id=asset.id))

@qr_bp.route('/print', methods=['POST'])
@login_required
def print_stickers():
    asset_ids = request.form.getlist('asset_ids')
    pregen_ids = request.form.getlist('pregen_ids')
    start_pos = int(request.form.get('start_position', 1)) - 1
    cols = int(request.form.get('grid_columns', 3))
    rows = int(request.form.get('grid_rows', 8))
    
    qr_data = []
    for _ in range(start_pos): qr_data.append(None)
        
    if asset_ids:
        assets = Asset.query.filter(Asset.id.in_(asset_ids)).all()
        for asset in assets:
            if not asset.qr_code_hash: asset.qr_code_hash = uuid.uuid4().hex
            scan_url = url_for('qr.public_scan', qr_hash=asset.qr_code_hash, _external=True)
            qr_data.append(generate_qr_img(scan_url, asset.serial_number, f"{asset.brand} {asset.model}"))
        db.session.commit()

    if pregen_ids:
        stickers = PreGeneratedQR.query.filter(PreGeneratedQR.id.in_(pregen_ids)).all()
        for sticker in stickers:
            scan_url = url_for('qr.public_scan', qr_hash=sticker.qr_hash, _external=True)
            qr_data.append(generate_qr_img(scan_url, "UNASSIGNED", "Scan to Link"))

    return render_template('qr/print.html', qr_items=qr_data, cols=cols, rows=rows)

def generate_qr_img(url, text1, text2):
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return {
        'img': base64.b64encode(buffer.getvalue()).decode(),
        'serial': text1,
        'model': text2
    }