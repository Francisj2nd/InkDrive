from flask import Flask

app = Flask(__name__)

# Import admin blueprint
from admin import admin_bp

# Register admin blueprint
app.register_blueprint(admin_bp)

# Other blueprints registration would go here

if __name__ == '__main__':
    app.run(debug=True)
