# Path: app/routes/admin.py
import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import AssetHistory, Asset, SystemSetting

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
def restrict_to_admin():
    if not current_user.is_authenticated or current_user.email != 'admin@company.com':
        flash('Access Denied: Admin privileges required.', 'error')
        return redirect(url_for('main.dashboard'))

@admin_bp.route('/transactions')
@login_required
def transactions():
    page = request.args.get('page', 1, type=int)
    history = AssetHistory.query.order_by(AssetHistory.timestamp.desc()).paginate(page=page, per_page=20)
    return render_template('admin/transactions.html', history=history)

@admin_bp.route('/transaction/<int:history_id>/revert', methods=['POST'])
@login_required
def revert_transaction(history_id):
    target_txn = AssetHistory.query.get_or_404(history_id)
    asset = Asset.query.get(target_txn.asset_id)
    
    latest_txn = AssetHistory.query.filter_by(asset_id=asset.id).order_by(AssetHistory.timestamp.desc()).first()
    if target_txn.id != latest_txn.id:
        flash('Failed: Can only revert latest action.', 'error')
        return redirect(request.referrer)

    previous_txn = AssetHistory.query.filter_by(asset_id=asset.id).order_by(AssetHistory.timestamp.desc()).offset(1).first()
    if previous_txn:
        if previous_txn.post_action_status is None:
            asset.status = 'In Stock'
        else:
            asset.status = previous_txn.post_action_status
            asset.current_branch_id = previous_txn.post_action_branch_id
            asset.current_employee_id = previous_txn.post_action_employee_id
    else:
        db.session.delete(asset)
        return redirect(url_for('admin.transactions'))

    if target_txn.document_path:
        try: os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], target_txn.document_path))
        except: pass 
    
    db.session.delete(target_txn)
    db.session.commit()
    flash('Transaction reverted.', 'success')
    return redirect(request.referrer)

@admin_bp.route('/asset/<int:asset_id>/reset_qr', methods=['POST'])
@login_required
def reset_qr_hash(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    old_hash = asset.qr_code_hash
    asset.qr_code_hash = uuid.uuid4().hex
    hist = AssetHistory(asset_id=asset.id, action="QR Reset", from_detail=f"Old: {old_hash[:8] if old_hash else 'None'}...", to_detail="New Hash", created_by_user_id=current_user.id, timestamp=datetime.now(), post_action_status=asset.status)
    db.session.add(hist)
    db.session.commit()
    flash('QR Reset.', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))

@admin_bp.route('/asset/<int:asset_id>/reassign_qr', methods=['POST'])
@login_required
def reassign_qr(asset_id):
    target_serial = request.form.get('target_serial')
    source_asset = Asset.query.get_or_404(asset_id)
    target_asset = Asset.query.filter_by(serial_number=target_serial).first()
    
    if not target_asset:
        flash(f'Target {target_serial} not found.', 'error')
        return redirect(request.referrer)
        
    qr_to_move = source_asset.qr_code_hash
    source_asset.qr_code_hash = None 
    target_asset.qr_code_hash = qr_to_move 
    
    h1 = AssetHistory(asset_id=source_asset.id, action="QR Unassigned", to_detail="Moved", created_by_user_id=current_user.id, timestamp=datetime.now(), post_action_status=source_asset.status)
    h2 = AssetHistory(asset_id=target_asset.id, action="QR Assigned", from_detail=f"From {source_asset.serial_number}", created_by_user_id=current_user.id, timestamp=datetime.now(), post_action_status=target_asset.status)
    
    db.session.add_all([h1, h2])
    db.session.commit()
    flash('QR Moved.', 'success')
    return redirect(url_for('assets.detail', asset_id=target_asset.id))

# --- GLOBAL TOGGLE ---
@admin_bp.route('/settings/toggle_scan', methods=['POST'])
@login_required
def toggle_global_scan():
    setting = SystemSetting.query.filter_by(key='global_qr_scan').first()
    if not setting:
        setting = SystemSetting(key='global_qr_scan', value='1')
        db.session.add(setting)
    
    # Toggle (1 -> 0, 0 -> 1)
    new_val = '0' if setting.value == '1' else '1'
    setting.value = new_val
    db.session.commit()
    
    status = "ENABLED" if new_val == '1' else "DISABLED"
    flash(f'Global QR Scanning is now {status}', 'success' if new_val == '1' else 'warning')
    return redirect(request.referrer)