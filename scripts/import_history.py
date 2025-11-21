import sys
import os
import csv
from datetime import datetime

# Add parent directory to path so we can import the app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Asset, Branch, Employee, AssetHistory, User

app = create_app()

def get_or_create_branch(name):
    branch = Branch.query.filter_by(name=name).first()
    if not branch:
        # Default location to name if not specified
        branch = Branch(name=name, location=name)
        db.session.add(branch)
        db.session.commit()
        print(f"  [+] Created Branch: {name}")
    return branch

def get_or_create_employee(emp_id, name, branch_id):
    emp = Employee.query.filter_by(emp_id=emp_id).first()
    if not emp:
        emp = Employee(emp_id=emp_id, name=name, branch_id=branch_id)
        db.session.add(emp)
        db.session.commit()
        print(f"  [+] Created Employee: {name} ({emp_id})")
    return emp

def process_csv(filename):
    with app.app_context():
        # Ensure we have a system user for the logs
        system_user = User.query.filter_by(email='admin@company.com').first()
        sys_user_id = system_user.id if system_user else None

        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            
            print("--- STARTING HISTORICAL IMPORT ---")
            
            for row in reader:
                # Parse Date (Format: YYYY-MM-DD)
                event_date = datetime.strptime(row['Date'], '%Y-%m-%d')
                action = row['Action'].upper() # PURCHASE, ALLOCATE, RETURN, TRANSFER, REPAIR
                serial = row['Serial']
                
                print(f"Processing {row['Date']}: {action} for {serial}")

                # 1. Handle PURCHASE (Creates the Asset)
                if action == 'PURCHASE':
                    branch = get_or_create_branch(row['Location_Branch'])
                    
                    asset = Asset(
                        serial_number=serial,
                        brand=row['Brand'],
                        model=row['Model'],
                        status='In Stock',
                        current_branch_id=branch.id,
                        purchase_date=event_date
                    )
                    db.session.add(asset)
                    db.session.commit()
                    
                    # Log History manually with PAST date
                    hist = AssetHistory(
                        asset_id=asset.id,
                        action="Purchase",
                        from_detail="Vendor",
                        to_detail=f"Stock ({branch.name})",
                        timestamp=event_date,
                        created_by_user_id=sys_user_id
                    )
                    db.session.add(hist)

                # 2. Handle ALLOCATION
                elif action == 'ALLOCATE':
                    asset = Asset.query.filter_by(serial_number=serial).first()
                    if not asset:
                        print(f"  [!] Error: Asset {serial} not found.")
                        continue
                        
                    # Get Employee details
                    branch = get_or_create_branch(row['Location_Branch']) # Emp Branch
                    emp = get_or_create_employee(row['Emp_ID'], row['Emp_Name'], branch.id)
                    
                    old_loc = f"Stock ({asset.branch.name})" if asset.branch else "Unknown"
                    
                    # Update Asset State
                    asset.status = 'Allocated'
                    asset.current_employee_id = emp.id
                    
                    # Log History
                    hist = AssetHistory(
                        asset_id=asset.id,
                        action="Allocation",
                        from_detail=old_loc,
                        to_detail=f"{emp.name} ({emp.emp_id})",
                        timestamp=event_date,
                        created_by_user_id=sys_user_id
                    )
                    db.session.add(hist)

                # 3. Handle RETURN (To Stock)
                elif action == 'RETURN':
                    asset = Asset.query.filter_by(serial_number=serial).first()
                    branch = get_or_create_branch(row['Location_Branch'])
                    
                    from_who = asset.holder.name if asset.holder else "Unknown"
                    
                    asset.status = 'In Stock'
                    asset.current_employee_id = None
                    asset.current_branch_id = branch.id
                    
                    hist = AssetHistory(
                        asset_id=asset.id,
                        action="Return",
                        from_detail=from_who,
                        to_detail=f"Stock ({branch.name})",
                        timestamp=event_date,
                        created_by_user_id=sys_user_id
                    )
                    db.session.add(hist)

                # 4. Handle TRANSFER
                elif action == 'TRANSFER':
                    asset = Asset.query.filter_by(serial_number=serial).first()
                    target_branch = get_or_create_branch(row['Location_Branch'])
                    
                    old_loc = asset.branch.name if asset.branch else "Transit"
                    
                    # Assumption: Historic data implies transfer completed.
                    # We set it to 'In Stock' at new branch for simplicity of "History Replay"
                    asset.status = 'In Stock' 
                    asset.current_branch_id = target_branch.id
                    asset.current_employee_id = None
                    
                    hist = AssetHistory(
                        asset_id=asset.id,
                        action="Transfer",
                        from_detail=f"Branch {old_loc}",
                        to_detail=f"Branch ({target_branch.name})",
                        courier_details=row.get('Courier', ''),
                        timestamp=event_date,
                        created_by_user_id=sys_user_id
                    )
                    db.session.add(hist)

                db.session.commit()
            
            print("--- IMPORT COMPLETE ---")

if __name__ == '__main__':
    # Point this to your CSV file
    csv_file = 'old_data.csv' 
    if os.path.exists(csv_file):
        process_csv(csv_file)
    else:
        print(f"File {csv_file} not found. Please create it first.")