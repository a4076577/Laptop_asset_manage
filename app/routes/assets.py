import os
import uuid
import io
import csv
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, asc
from app.extensions import db
from app.models import Asset, Branch, Employee, AssetHistory

assets_bp = Blueprint('assets', __name__)

# --- HELPER: File Upload ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_proof(file_obj):
    if file_obj and allowed_file(file_obj.filename):
        filename = secure_filename(file_obj.filename)
        unique_name = f"proof_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}.{filename.rsplit('.', 1)[1].lower()}"
        file_obj.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name))
        return unique_name
    return None

# --- HELPER: Log History ---
def log_history(asset, action, from_d, to_d, courier="", notes="", doc_path=None):
    history = AssetHistory(
        asset_id=asset.id,
        action=action,
        from_detail=from_d,
        to_detail=to_d,
        courier_details=courier,
        notes=notes,
        document_path=doc_path,
        created_by_user_id=current_user.id,
        timestamp=datetime.now(),
        post_action_status=asset.status,
        post_action_branch_id=asset.current_branch_id,
        post_action_employee_id=asset.current_employee_id
    )
    db.session.add(history)

# --- NEW: API for Dynamic Dropdown ---
@assets_bp.route('/get_employees/<int:branch_id>')
@login_required
def get_employees_by_branch(branch_id):
    employees = Employee.query.filter_by(status='Active', branch_id=branch_id).all()
    return jsonify([{'id': e.id, 'name': f"{e.name} ({e.emp_id})"} for e in employees])

@assets_bp.route('/')
@login_required
def list_assets():
    status_filter = request.args.get('status')
    branch_filter = request.args.get('branch_id')
    search = request.args.get('search')
    
    # Sorting Parameters
    sort_by = request.args.get('sort', 'id')
    order = request.args.get('order', 'desc')
    
    query = Asset.query.outerjoin(Branch, Asset.current_branch_id == Branch.id)\
                       .outerjoin(Employee, Asset.current_employee_id == Employee.id)

    if status_filter:
        query = query.filter(Asset.status == status_filter)
    if branch_filter:
        query = query.filter(Asset.current_branch_id == branch_filter)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Asset.serial_number.ilike(search_term),
                Asset.model.ilike(search_term),
                Employee.name.ilike(search_term),
                Branch.name.ilike(search_term)
            )
        )
    
    # Sorting Logic
    if sort_by == 'serial':
        sort_col = Asset.serial_number
    elif sort_by == 'model':
        sort_col = Asset.model
    elif sort_by == 'status':
        sort_col = Asset.status
    elif sort_by == 'branch':
        sort_col = Branch.name
    elif sort_by == 'holder':
        sort_col = Employee.name
    else:
        sort_col = Asset.id

    if order == 'asc':
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))
        
    assets = query.all()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('assets/_table_rows.html', assets=assets)

    branches = Branch.query.all()
    employees = Employee.query.filter_by(status='Active').all()
    return render_template('assets/list.html', assets=assets, branches=branches, employees=employees)

@assets_bp.route('/<int:asset_id>')
@login_required
def detail(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    branches = Branch.query.all()
    
    if asset.current_branch_id:
        employees = Employee.query.filter_by(status='Active', branch_id=asset.current_branch_id).all()
    else:
        employees = Employee.query.filter_by(status='Active').all()
        
    return render_template('assets/detail.html', asset=asset, branches=branches, employees=employees)

@assets_bp.route('/add', methods=['POST'])
@login_required
def add():
    serial = request.form.get('serial')
    model = request.form.get('model')
    brand = request.form.get('brand')
    branch_id = request.form.get('branch_id')
    
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)
    
    branch = Branch.query.get(branch_id)
    new_asset = Asset(
        serial_number=serial, brand=brand, model=model, status='In Stock',
        current_branch_id=branch_id, purchase_date=datetime.now()
    )
    db.session.add(new_asset)
    db.session.commit()
    
    log_history(new_asset, "Purchase", "Vendor", f"Stock ({branch.name})", doc_path=doc_filename)
    db.session.commit()
    flash('Asset Created Successfully', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/branch/add', methods=['POST'])
@login_required
def add_branch():
    name = request.form.get('name')
    location = request.form.get('location')
    if Branch.query.filter_by(name=name).first():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Branch already exists'}), 400
        flash('Branch already exists', 'error')
        return redirect(request.referrer)
    new_branch = Branch(name=name, location=location)
    db.session.add(new_branch)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'id': new_branch.id, 'name': new_branch.name})
    flash('Branch Added', 'success')
    return redirect(request.referrer)

@assets_bp.route('/action/allocate', methods=['POST'])
@login_required
def allocate():
    asset_id = request.form.get('asset_id')
    emp_id = request.form.get('employee_id')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)

    asset = Asset.query.get(asset_id)
    employee = Employee.query.get(emp_id)
    
    old_loc = f"Stock ({asset.branch.name})" if asset.branch else "Unknown"
    asset.status = 'Allocated'
    asset.current_employee_id = emp_id
    
    log_history(asset, "Allocation", old_loc, f"{employee.name} ({employee.emp_id})", doc_path=doc_filename)
    db.session.commit()
    flash('Asset Allocated', 'success')
    if 'assets' in request.referrer and 'asset/' not in request.referrer:
         return redirect(url_for('assets.list_assets'))
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/action/return', methods=['POST'])
@login_required
def return_asset():
    asset_id = request.form.get('asset_id')
    branch_id = request.form.get('branch_id')
    remarks = request.form.get('remarks')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)
    
    asset = Asset.query.get(asset_id)
    branch = Branch.query.get(branch_id)
    old_holder = asset.holder.name if asset.holder else "Unknown"
    
    asset.status = 'In Stock'
    asset.current_employee_id = None
    asset.current_branch_id = branch_id
    
    log_history(asset, "Return", old_holder, f"Stock ({branch.name})", notes=remarks, doc_path=doc_filename)
    db.session.commit()
    flash('Asset Returned to Stock', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/action/transfer', methods=['POST'])
@login_required
def transfer():
    asset_id = request.form.get('asset_id')
    target_branch_id = request.form.get('branch_id')
    courier = request.form.get('courier')
    remarks = request.form.get('remarks')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)
    
    asset = Asset.query.get(asset_id)
    target_branch = Branch.query.get(target_branch_id)
    old_loc = asset.branch.name if asset.branch else "Transit"
    
    asset.status = 'In Transit'
    asset.current_employee_id = None
    asset.current_branch_id = target_branch_id 
    
    log_history(asset, "Transfer Initiated", f"Branch {old_loc}", f"Branch {target_branch.name}", courier=courier, notes=remarks, doc_path=doc_filename)
    db.session.commit()
    flash('Transfer Initiated', 'success')
    if request.referrer and 'asset/' not in request.referrer: 
         return redirect(url_for('assets.list_assets'))
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/action/receive', methods=['POST'])
@login_required
def receive():
    asset_id = request.form.get('asset_id')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)

    asset = Asset.query.get(asset_id)
    asset.status = 'In Stock'
    log_history(asset, "Transfer Received", "Courier", f"Stock ({asset.branch.name})", doc_path=doc_filename)
    db.session.commit()
    flash('Asset Received', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/action/repair', methods=['POST'])
@login_required
def repair():
    asset_id = request.form.get('asset_id')
    notes = request.form.get('notes')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)

    asset = Asset.query.get(asset_id)
    from_who = "Unknown"
    if asset.holder:
        from_who = f"{asset.holder.name} (Allocated)"
    elif asset.branch:
        from_who = f"Stock ({asset.branch.name})"
        
    asset.status = 'Repair'
    log_history(asset, "Sent to Repair", from_who, "Repair Center", notes=notes, doc_path=doc_filename)
    db.session.commit()
    flash('Asset marked as Under Repair', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/action/repair/complete', methods=['POST'])
@login_required
def complete_repair():
    asset_id = request.form.get('asset_id')
    notes = request.form.get('notes')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)

    asset = Asset.query.get(asset_id)
    if asset.current_employee_id:
        asset.status = 'Allocated'
        to_detail = f"{asset.holder.name} (Owner)"
        flash_msg = f'Repair Complete. Asset returned to {asset.holder.name}.'
    else:
        asset.status = 'In Stock'
        to_detail = f"Stock ({asset.branch.name})"
        flash_msg = 'Repair Complete. Asset returned to Stock.'
    
    log_history(asset, "Repair Completed", "Repair Center", to_detail, notes=notes, doc_path=doc_filename)
    db.session.commit()
    flash(flash_msg, 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/action/retire', methods=['POST'])
@login_required
def retire_asset():
    asset_id = request.form.get('asset_id')
    remarks = request.form.get('remarks')
    doc_file = request.files.get('document')
    doc_filename = save_proof(doc_file)

    asset = Asset.query.get_or_404(asset_id)
    if asset.holder:
        flash(f'Failed: Asset is currently allocated to {asset.holder.name}.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))
        
    old_status = asset.status
    asset.status = 'Retired'
    asset.current_employee_id = None 
    
    log_history(asset, "Retired/Scrapped", old_status, "Retired", notes=remarks, doc_path=doc_filename)
    db.session.commit()
    flash('Asset has been Retired/Scrapped.', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))

@assets_bp.route('/export')
@login_required
def export_csv():
    mode = request.args.get('mode', 'summary')
    status_filter = request.args.get('status')
    branch_filter = request.args.get('branch_id')
    search = request.args.get('search')

    query = Asset.query.outerjoin(Branch, Asset.current_branch_id == Branch.id)\
                       .outerjoin(Employee, Asset.current_employee_id == Employee.id)

    if status_filter and status_filter != 'undefined': 
        query = query.filter(Asset.status == status_filter)
    if branch_filter and branch_filter != 'undefined': 
        query = query.filter(Asset.current_branch_id == branch_filter)
    
    if search and search != 'undefined':
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Asset.serial_number.ilike(search_term),
                Asset.model.ilike(search_term),
                Employee.name.ilike(search_term),
                Branch.name.ilike(search_term)
            )
        )
    
    assets = query.all()

    si = io.StringIO()
    cw = csv.writer(si)
    
    if mode == 'detailed':
        cw.writerow(['Date', 'Serial', 'Brand', 'Model', 'Action', 'From', 'To', 'Courier', 'Remarks', 'Doc', 'User'])
        filtered_ids = [a.id for a in assets]
        history = AssetHistory.query.filter(AssetHistory.asset_id.in_(filtered_ids))\
            .order_by(AssetHistory.timestamp.desc()).all()
            
        for h in history:
            cw.writerow([
                h.timestamp.strftime('%Y-%m-%d %H:%M'),
                h.asset.serial_number, h.asset.brand, h.asset.model,
                h.action, h.from_detail, h.to_detail, h.courier_details, h.notes,
                "Yes" if h.document_path else "No",
                h.created_by_user_id
            ])
    else:
        cw.writerow(['Serial', 'Brand', 'Model', 'Status', 'Current Branch', 'Current Holder', 'Emp ID', 'Allocation Date'])
        for a in assets:
            branch_name = a.branch.name if a.branch else "N/A"
            holder_name = "N/A"
            emp_id = "N/A"
            allocation_date = "N/A"
            if a.holder:
                holder_name = a.holder.name
                emp_id = a.holder.emp_id
                last_alloc = AssetHistory.query.filter_by(asset_id=a.id, action='Allocation').order_by(AssetHistory.timestamp.desc()).first()
                if last_alloc:
                    allocation_date = last_alloc.timestamp.strftime('%Y-%m-%d')
            cw.writerow([a.serial_number, a.brand, a.model, a.status, branch_name, holder_name, emp_id, allocation_date])
        
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    fname = f'asset_{mode}_{datetime.now().date()}.csv'
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=fname)