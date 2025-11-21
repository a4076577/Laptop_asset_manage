from app import create_app, db
from app.models import User

app = create_app()

# Custom CLI command to create the initial Admin user
# Run via terminal: flask create-admin
@app.cli.command("create-admin")
def create_admin():
    """Creates the initial admin user."""
    db.create_all()
    if not User.query.filter_by(email='admin@company.com').first():
        user = User(email='admin@company.com', name='System Admin', password='admin123') # Use hashing in real prod!
        db.session.add(user)
        db.session.commit()
        print("Admin user created: admin@company.com / admin123")
    else:
        print("Admin user already exists.")

if __name__ == '__main__':
    app.run(debug=True)