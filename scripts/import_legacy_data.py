import sys
import os
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load Environment and Path
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Asset, Branch, Employee, AssetHistory, User

app = create_app()

# --- 1. DEFINE PURCHASE SCHEDULE ---
# Format: (Date String DD-MM-YY, Count)
PURCHASE_BATCHES = [
    ("29-04-25", 10),
    ("15-05-25", 10),
    ("07-07-25", 10),
    ("21-07-25", 5),
    ("25-07-25", 5),
    ("25-08-25", 5),
    ("27-08-25", 5),
    ("12-09-25", 3),
    ("15-09-25", 7),
    ("15-11-25", 10)
]

def generate_purchase_date_list():
    """Expands the batches into a single list of 70 dates"""
    date_list = []
    for date_str, count in PURCHASE_BATCHES:
        dt = datetime.strptime(date_str, '%d-%m-%y')
        for _ in range(count):
            date_list.append(dt)
    # Sort just in case the input list wasn't chronological
    date_list.sort()
    return date_list

def parse_date(date_str):
    """Converts 10-06-25 or NA to datetime object or None"""
    if not date_str or date_str.upper().strip() == 'NA':
        return None
    try:
        # Assuming format DD-MM-YY
        return datetime.strptime(date_str.strip(), '%d-%m-%y')
    except ValueError:
        return None

def get_or_create_branch(name):
    clean_name = name.strip()
    branch = Branch.query.filter_by(name=clean_name).first()
    if not branch:
        branch = Branch(name=clean_name, location=clean_name)
        db.session.add(branch)
        db.session.commit()
    return branch

def get_or_create_employee(emp_id, name, branch_id):
    if not emp_id or not emp_id.strip():
        return None
    
    clean_id = emp_id.strip()
    emp = Employee.query.filter_by(emp_id=clean_id).first()
    if not emp:
        emp = Employee(emp_id=clean_id, name=name.strip(), branch_id=branch_id, status='Active')
        db.session.add(emp)
        db.session.commit()
    return emp

def import_data(filename):
    with app.app_context():
        # Get System Admin for logs
        admin = User.query.filter_by(email='admin@company.com').first()
        admin_id = admin.id if admin else None
        
        # Ensure HO branch exists for initial purchase logic
        ho_branch = get_or_create_branch("HO")

        # 1. READ AND SORT CSV DATA
        rows = []
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Add a sorting key: Use Issue Date. 
                # If NA, use max date (so they appear last and get latest purchase dates)
                issue_date = parse_date(row['ISSUE_DATE'])
                transfer_date = parse_date(row.get('TRANSFER_DATE')) # New Column
                
                sort_date = issue_date if issue_date else datetime.max
                rows.append({
                    'data': row,
                    'sort_date': sort_date,
                    'real_issue_date': issue_date,
                    'real_transfer_date': transfer_date
                })
        
        # Sort rows by Issue Date (Earliest allocation gets Earliest stock)
        rows.sort(key=lambda x: x['sort_date'])
        
        # Get Purchase Dates
        purchase_dates = generate_purchase_date_list()
        
        print(f"--- STARTING IMPORT: {len(rows)} Assets ---")
        
        for index, item in enumerate(rows):
            row = item['data']
            issue_date = item['real_issue_date']
            transfer_date = item['real_transfer_date']
            
            # Assign Purchase Date from schedule (cycle if we have more rows than dates)
            if index < len(purchase_dates):
                purchase_date = purchase_dates[index]
            else:
                purchase_date = purchase_dates[-1] # Fallback to last known date

            # If Issue Date is NA, use Purchase Date for logic, or Today
            # Logic: If it's stock (NA), it arrived on purchase date.
            effective_date = issue_date if issue_date else purchase_date

            # Data Extraction
            serial = row['S/N'].strip()
            brand = row['BRAND'].strip()
            model = row['MODEL'].strip()
            branch_name = row['BRANCH'].strip()
            emp_id = row['EMP_ID'].strip()
            emp_name = row['NAME'].strip()

            # Check duplicates
            if Asset.query.filter_by(serial_number=serial).first():
                print(f"  [Skip] {serial} exists.")
                continue

            # Resolve Entities
            target_branch = get_or_create_branch(branch_name)
            employee = get_or_create_employee(emp_id, emp_name, target_branch.id)

            # Determine Status
            if employee:
                status = 'Allocated'
                curr_emp_id = employee.id
            else:
                status = 'In Stock'
                curr_emp_id = None

            # --- CREATE ASSET ---
            asset = Asset(
                serial_number=serial,
                brand=brand,
                model=model,
                status=status,
                current_branch_id=target_branch.id,
                current_employee_id=curr_emp_id,
                purchase_date=purchase_date
            )
            db.session.add(asset)
            db.session.commit()

            # --- HISTORY JOURNEY ---
            
            # 1. PURCHASE (Always at HO)
            h1 = AssetHistory(
                asset_id=asset.id,
                action="Purchase",
                from_detail="Vendor",
                to_detail="Stock (HO)",
                timestamp=purchase_date, # Date from your schedule
                created_by_user_id=admin_id,
                post_action_status='In Stock',
                post_action_branch_id=ho_branch.id,
                post_action_employee_id=None
            )
            db.session.add(h1)

            # 2. TRANSFER (If Branch is NOT HO)
            # Logic: If current branch != HO, it must have moved.
            # Date Priority: Transfer Date > Issue Date > Purchase Date
            if target_branch.name.upper() != "HO":
                txn_date = transfer_date if transfer_date else effective_date
                
                h2 = AssetHistory(
                    asset_id=asset.id,
                    action="Branch Transfer",
                    from_detail="Stock (HO)",
                    to_detail=f"Stock ({target_branch.name})",
                    timestamp=txn_date, 
                    created_by_user_id=admin_id,
                    post_action_status='In Stock',
                    post_action_branch_id=target_branch.id,
                    post_action_employee_id=None
                )
                db.session.add(h2)

            # 3. ALLOCATION (If Employee exists)
            if employee:
                h3 = AssetHistory(
                    asset_id=asset.id,
                    action="Allocation",
                    from_detail=f"Stock ({target_branch.name})",
                    to_detail=f"{employee.name} ({employee.emp_id})",
                    timestamp=effective_date,
                    created_by_user_id=admin_id,
                    post_action_status='Allocated',
                    post_action_branch_id=target_branch.id,
                    post_action_employee_id=employee.id
                )
                db.session.add(h3)

            db.session.commit()
            print(f"  [OK] {serial}: Pur {purchase_date.date()} -> Loc {target_branch.name} -> {status}")

        print("--- IMPORT COMPLETE ---")

if __name__ == '__main__':
    csv_file = 'initial_data.csv'
    if os.path.exists(csv_file):
        import_data(csv_file)
    else:
        print(f"Error: {csv_file} not found. Please create it.")