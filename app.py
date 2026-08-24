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
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

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
    def to_dict(self):
        return dict(plate=self.plate, name=self.name, initMiles=self.init_miles)

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
    if not User.query.first():
        for u in data.get('users', []):
            if not User.query.filter_by(username=u.get('username','')).first():
                db.session.add(User(id=u.get('id',str(uuid.uuid4())), name=u.get('name',''),
                    username=u.get('username',''), password=u.get('password','driver123'),
                    role=u.get('role','driver'), status=u.get('status','active')))
        db.session.commit()
        print(f"Seeded {User.query.count()} users")
    if not Vehicle.query.first():
        for v in data.get('vehicles', []):
            if not Vehicle.query.get(v.get('plate','')):
                db.session.add(Vehicle(plate=v.get('plate',''), name=v.get('name',''), init_miles=v.get('initMiles',0)))
        db.session.commit()
        print(f"Seeded {Vehicle.query.count()} vehicles")
    if not Entry.query.first():
        batch = [Entry(id=e.get('id',str(uuid.uuid4())), date=e.get('date',''), driver=e.get('driver',''),
            plate=e.get('plate',''), prev_miles=e.get('prevMiles',0), curr_miles=e.get('currMiles',0),
            miles=e.get('miles',0), liters=e.get('liters',0), price=e.get('price',0),
            total=e.get('total',0), added_by=e.get('by','import')) for e in data.get('entries',[])]
        db.session.bulk_save_objects(batch)
        db.session.commit()
        print(f"Seeded {Entry.query.count()} entries")

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
    v = Vehicle(plate=d['plate'].upper(), name=d.get('name',''), init_miles=d.get('initMiles',0))
    db.session.add(v); db.session.commit()
    return jsonify(v.to_dict()), 201

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
