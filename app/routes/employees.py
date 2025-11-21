# Path: app/routes/employees.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from sqlalchemy import or_
from app.extensions import db
from app.models import Employee, AssetHistory, Branch, Asset

employees_bp = Blueprint('employees', __name__)

@employees_bp.route('/')
@login_required
def list_employees():
    search = request.args.get('search')
    status_filter = request.args.get('status', 'Active') # Default to Active
    
    query = Employee.query.outerjoin(Branch, Employee.branch_id == Branch.id)\
                          .outerjoin(Asset, Employee.id == Asset.current_employee_id)

    # Apply Status Filter
    if status_filter and status_filter != 'All':
        query = query.filter(Employee.status == status_filter)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Employee.name.ilike(search_term),
                Employee.emp_id.ilike(search_term),
                Branch.name.ilike(search_term),
                Asset.serial_number.ilike(search_term),
                Asset.model.ilike(search_term)
            )
        )
    
    employees = query.distinct().all()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('employees/_table_rows.html', employees=employees)

    branches = Branch.query.all()
    return render_template('employees/list.html', employees=employees, branches=branches, current_status=status_filter)

@employees_bp.route('/<int:emp_id>')
@login_required
def detail(emp_id):
    employee = Employee.query.get_or_404(emp_id)
    current_assets = employee.assets_holding
    history_entries = AssetHistory.query.filter(
        or_(AssetHistory.to_detail.contains(f"{employee.name}"),
            AssetHistory.from_detail.contains(f"{employee.name}"))
    ).order_by(AssetHistory.timestamp.desc()).all()
    return render_template('employees/detail.html', employee=employee, current_assets=current_assets, history=history_entries)

@employees_bp.route('/add', methods=['POST'])
@login_required
def add_employee():
    name = request.form.get('name')
    emp_id = request.form.get('emp_id')
    branch_id = request.form.get('branch_id')
    
    if Employee.query.filter_by(emp_id=emp_id).first():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Employee ID already exists'}), 400
        flash('Employee ID already exists', 'error')
        return redirect(request.referrer)
        
    new_emp = Employee(name=name, emp_id=emp_id, branch_id=branch_id, status='Active')
    db.session.add(new_emp)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'id': new_emp.id, 'name': f"{new_emp.name} ({new_emp.emp_id})"})

    flash('Employee Added', 'success')
    return redirect(request.referrer)

# --- EMPLOYEE STATUS ACTIONS ---

@employees_bp.route('/action/resign', methods=['POST'])
@login_required
def resign_employee():
    emp_id = request.form.get('emp_id')
    employee = Employee.query.get_or_404(emp_id)
    
    # Validation: Cannot resign if they hold assets
    if employee.assets_holding:
        flash(f'Action Failed: {employee.name} still holds {len(employee.assets_holding)} asset(s). Please return them to stock first.', 'error')
    else:
        employee.status = 'Inactive'
        db.session.commit()
        flash(f'Employee {employee.name} marked as Inactive/Resigned.', 'success')
        
    return redirect(url_for('employees.detail', emp_id=emp_id))

@employees_bp.route('/action/activate', methods=['POST'])
@login_required
def activate_employee():
    emp_id = request.form.get('emp_id')
    employee = Employee.query.get_or_404(emp_id)
    
    employee.status = 'Active'
    db.session.commit()
    flash(f'Employee {employee.name} marked as Active.', 'success')
    
    return redirect(url_for('employees.detail', emp_id=emp_id))