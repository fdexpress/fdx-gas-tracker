# v6 - force fresh build
import os, json
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__, static_folder='static')
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///fdx.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif 'postgresql' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

# CRITICAL: Log which database we're actually using
if 'postgresql' in DATABASE_URL:
    print("=" * 60)
    print("USING POSTGRESQL - data will persist across deploys")
    print("=" * 60)
else:
    print("!" * 60)
    print("WARNING: USING SQLITE - DATA WILL BE LOST ON DEPLOY!")
    print("DATABASE_URL env var is not set correctly!")
    print("!" * 60)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id       = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name     = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role     = db.Column(db.String(20), nullable=False, default='driver')
    status   = db.Column(db.String(20), nullable=False, default='active')
    def to_dict(self):
        return dict(id=self.id, name=self.name, username=self.username, role=self.role, status=self.status)

class Vehicle(db.Model):
    plate      = db.Column(db.String(20), primary_key=True)
    name       = db.Column(db.String(120))
    init_miles = db.Column(db.Integer, default=0)
    status     = db.Column(db.String(20), default='active')
    def to_dict(self):
        return dict(plate=self.plate, name=self.name, initMiles=self.init_miles, status=self.status or 'active')

class Entry(db.Model):
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    date       = db.Column(db.String(10), nullable=False)
    driver     = db.Column(db.String(120), default='')
    plate      = db.Column(db.String(20), nullable=False)
    prev_miles = db.Column(db.Float, default=0)
    curr_miles = db.Column(db.Float, default=0)
    miles      = db.Column(db.Float, default=0)
    liters     = db.Column(db.Float, default=0)
    price      = db.Column(db.Float, default=0)
    total      = db.Column(db.Float, default=0)
    added_by   = db.Column(db.String(60), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def to_dict(self):
        return dict(id=self.id, date=self.date, driver=self.driver, plate=self.plate,
                    prevMiles=self.prev_miles, currMiles=self.curr_miles, miles=self.miles,
                    liters=self.liters, price=self.price, total=self.total, by=self.added_by)

def seed_db():
    seed_file = os.path.join(os.path.dirname(__file__), 'seed_data.json')
    if not os.path.exists(seed_file):
        return
    with open(seed_file) as f:
        data = json.load(f)
    # Seed users
    if not User.query.first():
        for u in data.get('users', []):
            uname = u.get('username','').lower().strip()
            if uname and not User.query.filter_by(username=uname).first():
                try:
                    db.session.add(User(id=u.get('id',str(uuid.uuid4())), name=u.get('name',''),
                        username=uname, password=u.get('password','driver123'),
                        role=u.get('role','driver'), status=u.get('status','active')))
                    db.session.flush()
                except Exception as e:
                    db.session.rollback()
                    print(f"Skip user {uname}: {e}")
        db.session.commit()
        print(f"Seeded {User.query.count()} users")
    # Seed vehicles
    if not Vehicle.query.first():
        for v in data.get('vehicles', []):
            try:
                db.session.add(Vehicle(plate=v.get('plate',''), name=v.get('name',''), init_miles=v.get('initMiles',0), status=v.get('status','active')))
            except: pass
        db.session.commit()
        print(f"Seeded {Vehicle.query.count()} vehicles")
    # Seed entries in batches of 100
    if not Entry.query.first():
        entries_data = data.get('entries', [])
        BATCH = 100
        for i in range(0, len(entries_data), BATCH):
            batch = entries_data[i:i+BATCH]
            objs = []
            for e in batch:
                try:
                    objs.append(Entry(id=e.get('id',str(uuid.uuid4())), date=e.get('date',''),
                        driver=e.get('driver',''), plate=e.get('plate',''),
                        prev_miles=e.get('prevMiles',0), curr_miles=e.get('currMiles',0),
                        miles=e.get('miles',0), liters=e.get('liters',0),
                        price=e.get('price',0), total=e.get('total',0), added_by=e.get('by','import')))
                except: pass
            db.session.bulk_save_objects(objs)
            db.session.commit()
            print(f"Seeded entries batch {i//BATCH + 1}/{(len(entries_data)+BATCH-1)//BATCH}")
        print(f"Total entries seeded: {Entry.query.count()}")

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    u = User.query.filter_by(username=d.get('username','').lower().strip(), password=d.get('password',''), status='active').first()
    if not u: return jsonify(error='Invalid username or password'), 401
    return jsonify(user=u.to_dict())

@app.route('/api/entries', methods=['GET'])
def get_entries():
    return jsonify([e.to_dict() for e in Entry.query.order_by(Entry.date.desc(), Entry.created_at.desc()).all()])

@app.route('/api/entries', methods=['POST'])
def add_entry():
    d = request.json
    e = Entry(date=d['date'], driver=d.get('driver',''), plate=d['plate'],
        prev_miles=d.get('prevMiles',0), curr_miles=d.get('currMiles',0),
        miles=d.get('miles',0), liters=d.get('liters',0), price=d.get('price',0),
        total=d.get('total',0), added_by=d.get('by',''))
    db.session.add(e); db.session.commit()
    return jsonify(e.to_dict()), 201

@app.route('/api/entries/<id>', methods=['PUT'])
def update_entry(id):
    e = Entry.query.get_or_404(id)
    d = request.json
    e.date = d.get('date', e.date)
    e.driver = d.get('driver', e.driver)
    e.plate = d.get('plate', e.plate)
    e.prev_miles = d.get('prevMiles', e.prev_miles)
    e.curr_miles = d.get('currMiles', e.curr_miles)
    e.miles = d.get('miles', e.miles)
    e.liters = d.get('liters', e.liters)
    e.price = d.get('price', e.price)
    e.total = d.get('total', e.total)
    db.session.commit()
    return jsonify(e.to_dict())

@app.route('/api/entries/<id>', methods=['DELETE'])
def del_entry(id):
    e = Entry.query.get_or_404(id); db.session.delete(e); db.session.commit()
    return jsonify(ok=True)

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    return jsonify([v.to_dict() for v in Vehicle.query.order_by(Vehicle.plate).all()])

@app.route('/api/vehicles', methods=['POST'])
def add_vehicle():
    d = request.json
    if Vehicle.query.get(d['plate'].upper()): return jsonify(error='Plate already exists'), 400
    v = Vehicle(plate=d['plate'].upper(), name=d.get('name',''), init_miles=d.get('initMiles',0), status=d.get('status','active'))
    db.session.add(v); db.session.commit()
    return jsonify(v.to_dict()), 201

@app.route('/api/vehicles/<plate>', methods=['PUT'])
def update_vehicle(plate):
    v = Vehicle.query.get_or_404(plate)
    d = request.json
    if 'name' in d: v.name = d['name']
    if 'initMiles' in d: v.init_miles = d['initMiles']
    if 'status' in d: v.status = d['status']
    db.session.commit()
    return jsonify(v.to_dict())

@app.route('/api/vehicles/<plate>', methods=['DELETE'])
def del_vehicle(plate):
    v = Vehicle.query.get_or_404(plate); db.session.delete(v); db.session.commit()
    return jsonify(ok=True)

@app.route('/api/users', methods=['GET'])
def get_users():
    return jsonify([u.to_dict() for u in User.query.order_by(User.name).all()])

@app.route('/api/users', methods=['POST'])
def add_user():
    d = request.json; uname = d['username'].lower().strip()
    if User.query.filter_by(username=uname).first(): return jsonify(error='Username already taken'), 400
    u = User(name=d['name'], username=uname, password=d.get('password','driver123'),
             role=d.get('role','driver'), status=d.get('status','active'))
    db.session.add(u); db.session.commit()
    return jsonify(u.to_dict()), 201

@app.route('/api/users/<id>', methods=['PUT'])
def update_user(id):
    u = User.query.get_or_404(id); d = request.json
    u.name=d.get('name',u.name); u.username=d.get('username',u.username).lower().strip()
    u.role=d.get('role',u.role); u.status=d.get('status',u.status)
    if d.get('password'): u.password=d['password']
    db.session.commit(); return jsonify(u.to_dict())

@app.route('/api/users/<id>', methods=['DELETE'])
def del_user(id):
    u = User.query.get_or_404(id)
    if u.username=='admin': return jsonify(error='Cannot delete main admin'), 400
    db.session.delete(u); db.session.commit(); return jsonify(ok=True)

# ── Run on startup (works with both gunicorn and direct) ──────
with app.app_context():
    try:
        db.create_all()
        # Safe migration: add status column to vehicle table if missing
        try:
            from sqlalchemy import text, inspect
            insp = inspect(db.engine)
            cols = [c['name'] for c in insp.get_columns('vehicle')]
            if 'status' not in cols:
                db.session.execute(text("ALTER TABLE vehicle ADD COLUMN status VARCHAR(20) DEFAULT 'active'"))
                db.session.execute(text("UPDATE vehicle SET status='active' WHERE status IS NULL"))
                db.session.commit()
                print("Added status column to vehicle table")
        except Exception as mig_err:
            print(f"Vehicle migration note: {mig_err}")
        # Only seed if database is COMPLETELY empty (first-ever startup)
        # This protects all user-added data from ever being overwritten
        if not Entry.query.first() and not User.query.first():
            print("Empty database detected - seeding initial data")
            seed_db()
        else:
            print(f"Database has data ({Entry.query.count()} entries) - skipping seed")
    except Exception as e:
        print(f"Startup error (non-fatal): {e}")


@app.route('/api/bulk_update_passwords', methods=['POST'])
def bulk_update_passwords():
    """One-time endpoint to update passwords from Excel data"""
    updates = request.json.get('updates', [])
    results = {'updated': 0, 'not_found': 0}
    for u in updates:
        uname = u.get('username','').lower().strip()
        pwd = u.get('password','')
        if not uname or not pwd:
            continue
        user = User.query.filter_by(username=uname).first()
        if user:
            user.password = pwd
            results['updated'] += 1
        else:
            results['not_found'] += 1
    db.session.commit()
    return jsonify(results)

@app.route('/')
def index(): return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def static_files(path): return send_from_directory('static', path)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
