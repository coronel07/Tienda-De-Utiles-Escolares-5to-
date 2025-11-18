from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Clave para usar session
app.secret_key = "clave_secreta_para_la_app"

# Configuración base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/tienda_itr'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============================
# MODELOS
# ============================

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    productos = db.relationship('Producto', backref='categoria', lazy=True)

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    imagen = db.Column(db.String(255))
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'))


# ============================
# HOME
# ============================

@app.route('/')
def index():
    busqueda = request.args.get('q', '').strip()
    orden = request.args.get('orden', '')
    categorias = request.args.getlist('categoria')
    precio_max = request.args.get('precio', 50000)

    query = Producto.query

    # Búsqueda
    if busqueda:
        query = query.filter(Producto.nombre.like(f'%{busqueda}%'))

    # Categorías
    if categorias:
        query = query.filter(Producto.categoria_id.in_(categorias))

    # Precio
    query = query.filter(Producto.precio <= precio_max)

    # Orden
    if orden == 'mayor':
        query = query.order_by(Producto.precio.desc())
    elif orden == 'menor':
        query = query.order_by(Producto.precio.asc())
    elif orden == 'antiguo':
        query = query.order_by(Producto.id.asc())
    else:
        query = query.order_by(Producto.id.desc())

    productos = query.all()
    categorias_db = Categoria.query.all()

    return render_template(
        "index.html",
        productos=productos,
        categorias=categorias_db,
        busqueda=busqueda,
        precio_max=precio_max
    )


# ============================
# PRODUCTO INDIVIDUAL
# ============================

@app.route("/producto/<int:id>")
def producto(id):
    prod = Producto.query.get_or_404(id)
    return render_template("producto.html", producto=prod)


# ============================
# CARRITO (SESSION)
# ============================

@app.route("/carrito")
def carrito():
    carrito = session.get("carrito", [])
    total = sum(item["precio"] for item in carrito)

    return render_template(
        "carrito.html",
        items=carrito,
        total=total,
        active="carrito"
    )


@app.route("/agregar_carrito/<int:id>", methods=["POST"])
def agregar_carrito(id):
    producto = Producto.query.get(id)

    if not producto:
        return redirect(url_for("index"))

    carrito = session.get("carrito", [])

    carrito.append({
        "id": producto.id,
        "nombre": producto.nombre,
        "precio": float(producto.precio),
        "imagen": producto.imagen
    })

    session["carrito"] = carrito
    return redirect(url_for("carrito"))


@app.route("/carrito/eliminar/<int:id>", methods=["POST"])
def eliminar_carrito(id):
    carrito = session.get("carrito", [])
    carrito = [item for item in carrito if item["id"] != id]

    session["carrito"] = carrito
    return redirect(url_for("carrito"))


# ============================
# ADMIN
# ============================

@app.route('/admin')
def admin_dashboard():
    return redirect(url_for('admin_pedidos'))


@app.route('/admin/pedidos')
def admin_pedidos():
    return render_template('admin_pedidos.html', section="pedidos")


@app.route('/admin/productos')
def admin_productos():
    productos = Producto.query.all()
    return render_template('admin_productos.html', productos=productos, section="productos")


# ====== ✔ ESTA ES LA FUNCIÓN CORRECTA FINAL (SIN DUPLICADOS) ======

@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
def admin_editar_producto(id):
    producto = Producto.query.get_or_404(id)
    categorias = Categoria.query.all()

    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.precio = request.form['precio']
        producto.stock = request.form['stock']
        producto.descripcion = request.form['descripcion']
        producto.categoria_id = request.form['categoria_id']

        # Imagen nueva
        if "imagen" in request.files and request.files["imagen"].filename != "":
            archivo = request.files["imagen"]
            filename = secure_filename(archivo.filename)
            archivo.save(os.path.join("static/img", filename))
            producto.imagen = filename

        db.session.commit()
        return redirect(url_for('admin_productos'))

    return render_template('admin_editar_producto.html', producto=producto, categorias=categorias, section="productos")


@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
def admin_eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    return redirect(url_for('admin_productos'))


@app.route('/admin/productos/agregar', methods=['GET', 'POST'])
def admin_agregar_producto():
    categorias = Categoria.query.all()

    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        categoria_id = request.form['categoria_id']

        # Imagen subida
        imagen_archivo = request.files.get("imagen")
        filename = None

        if imagen_archivo and imagen_archivo.filename != "":
            filename = secure_filename(imagen_archivo.filename)
            imagen_archivo.save(os.path.join("static/img", filename))

        nuevo = Producto(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            stock=stock,
            categoria_id=categoria_id,
            imagen=filename
        )

        db.session.add(nuevo)
        db.session.commit()

        return redirect(url_for('admin_productos'))

    return render_template('admin_agregar_producto.html', categorias=categorias, section="productos")


@app.route('/admin/reportes')
def admin_reportes():
    return render_template('admin_reportes.html', section="reportes")


@app.route('/admin/usuarios')
def admin_usuarios():
    return render_template('admin_usuarios.html', section="usuarios")


# ============================
# INICIAR SERVIDOR
# ============================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)
