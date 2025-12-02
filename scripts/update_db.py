# Path: scripts/update_db.py
import sys
import os
from sqlalchemy import text, inspect
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import PreGeneratedQR, ScanLog, SystemSetting

app = create_app()

if __name__ == '__main__':
    print("--- UPDATING DATABASE SCHEMA ---")
    
    with app.app_context():
        # Create new tables (including SystemSetting)
        db.create_all()
        
        # Seed Global Scan Setting
        if not SystemSetting.query.filter_by(key='global_qr_scan').first():
            db.session.add(SystemSetting(key='global_qr_scan', value='1'))
            db.session.commit()
            print("  [OK] Global Scan Setting Seeded")

        # Check for existing column additions
        inspector = inspect(db.engine)
        if 'asset_history' in inspector.get_table_names():
            existing_cols = [c['name'] for c in inspector.get_columns('asset_history')]
            if 'document_path' not in existing_cols:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE asset_history ADD COLUMN document_path VARCHAR(200)"))
                    conn.commit()
            if 'post_action_status' not in existing_cols:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE asset_history ADD COLUMN post_action_status VARCHAR(50)"))
                    conn.execute(text("ALTER TABLE asset_history ADD COLUMN post_action_branch_id INTEGER"))
                    conn.execute(text("ALTER TABLE asset_history ADD COLUMN post_action_employee_id INTEGER"))
                    conn.commit()

        if 'asset' in inspector.get_table_names():
            existing_cols = [c['name'] for c in inspector.get_columns('asset')]
            if 'qr_code_hash' not in existing_cols:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE asset ADD COLUMN qr_code_hash VARCHAR(64)"))
                    conn.execute(text("ALTER TABLE asset ADD COLUMN is_qr_active BOOLEAN DEFAULT 1"))
                    conn.commit()

    print("--- UPDATE COMPLETE ---")