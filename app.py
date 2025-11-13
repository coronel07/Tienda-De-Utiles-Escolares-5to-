from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuración de conexión a MySQL (XAMPP)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/tienda_itr'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============================
# MODELO DE BASE DE DATOS
# ============================
class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    imagen = db.Column(db.String(255))

# ============================
# RUTA PRINCIPAL (HOME)
# ============================
@app.route('/')
def index():
    # Parámetros GET: búsqueda y orden
    busqueda = request.args.get('q', '').strip()
    orden = request.args.get('orden', '')

    # Base query
    query = Producto.query

    # Filtrar por búsqueda (si hay texto)
    if busqueda:
        query = query.filter(Producto.nombre.like(f'%{busqueda}%'))

    # Ordenar según parámetro
    if orden == 'mayor':
        query = query.order_by(Producto.precio.desc())
    elif orden == 'menor':
        query = query.order_by(Producto.precio.asc())
    elif orden == 'antiguo':
        query = query.order_by(Producto.id.asc())
    else:
        query = query.order_by(Producto.id.desc())  # por defecto, más nuevo primero

    productos = query.all()

    return render_template(
        'index.html',
        title='Tienda Digital',
        productos=productos,
        busqueda=busqueda
    )

# ============================
# RUTA DE INICIO DEL SERVIDOR
# ============================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # crea la tabla si no existe
    app.run(debug=True)
