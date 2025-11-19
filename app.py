from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
import os
from functools import wraps

app = Flask(__name__)

# Clave para usar session
app.secret_key = "clave_secreta_para_la_app"

# Configuración base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/tienda_itr'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============================
# DECORADORES DE LOGIN Y ADMIN
# ============================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        if session.get("usuario_rol") != "admin":
            return render_template("acceso_restringido.html"), 403
        return f(*args, **kwargs)
    return decorated_function


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

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('cliente', 'admin'), default='cliente')
    fecha_registro = db.Column(db.DateTime, server_default=db.func.now())

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha = db.Column(db.DateTime, server_default=db.func.now())
    total = db.Column(db.Numeric(10, 2), nullable=False)
    estado = db.Column(db.Enum('pendiente','pagado','enviado','cancelado'), server_default='pendiente')

    usuario = db.relationship("Usuario", backref="pedidos")
    items = db.relationship("DetallePedido", backref="pedido", cascade="all, delete-orphan", lazy=True)

class DetallePedido(db.Model):
    __tablename__ = 'detalle_pedido'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)

    producto = db.relationship("Producto")

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

    if busqueda:
        query = query.filter(Producto.nombre.like(f'%{busqueda}%'))

    if categorias:
        query = query.filter(Producto.categoria_id.in_(categorias))

    query = query.filter(Producto.precio <= precio_max)

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
# CARRITO
# ============================

@app.route("/carrito")
def carrito():
    carrito = session.get("carrito", [])
    total = sum(item["precio"] * item.get("cantidad", 1) for item in carrito)
    return render_template("carrito.html", items=carrito, total=total)

@app.route("/agregar_carrito/<int:id>", methods=["POST"])
def agregar_carrito(id):
    producto = Producto.query.get_or_404(id)
    try:
        cantidad = int(request.form.get("cantidad", 1))
    except (ValueError, TypeError):
        cantidad = 1
    if cantidad < 1:
        cantidad = 1

    carrito = session.get("carrito", [])
    found = False
    for it in carrito:
        if it["id"] == producto.id:
            it["cantidad"] = it.get("cantidad", 1) + cantidad
            found = True
            break
    if not found:
        carrito.append({
            "id": producto.id,
            "nombre": producto.nombre,
            "precio": float(producto.precio),
            "imagen": producto.imagen,
            "cantidad": cantidad
        })
    session["carrito"] = carrito
    return redirect(url_for("carrito"))

@app.route("/carrito/eliminar/<int:id>", methods=["POST"])
def eliminar_carrito(id):
    carrito = session.get("carrito", [])
    eliminar_todo = request.form.get("toda", "0") == "1"
    nuevo = []
    for item in carrito:
        if item["id"] != id:
            nuevo.append(item)
        else:
            if eliminar_todo:
                pass
            else:
                if item.get("cantidad", 1) > 1:
                    item["cantidad"] = item.get("cantidad", 1) - 1
                    nuevo.append(item)
    session["carrito"] = nuevo
    return redirect(url_for("carrito"))

# ============================
# ADMIN
# ============================

@app.route('/admin')
@admin_required
def admin_dashboard():
    return redirect(url_for('admin_pedidos'))

@app.route('/admin/productos')
@admin_required
def admin_productos():
    productos = Producto.query.all()
    return render_template('admin_productos.html', productos=productos, section="productos")

@app.route('/admin/productos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_editar_producto(id):
    producto = Producto.query.get_or_404(id)
    categorias = Categoria.query.all()
    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.precio = request.form['precio']
        producto.stock = request.form['stock']
        producto.descripcion = request.form['descripcion']
        producto.categoria_id = request.form['categoria_id']
        if "imagen" in request.files and request.files["imagen"].filename != "":
            archivo = request.files["imagen"]
            filename = secure_filename(archivo.filename)
            archivo.save(os.path.join("static/img", filename))
            producto.imagen = filename
        db.session.commit()
        return redirect(url_for('admin_productos'))
    return render_template('admin_editar_producto.html', producto=producto, categorias=categorias, section="productos")

@app.route('/admin/productos/eliminar/<int:id>', methods=['POST'])
@admin_required
def admin_eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    return redirect(url_for('admin_productos'))

@app.route('/admin/productos/agregar', methods=['GET', 'POST'])
@admin_required
def admin_agregar_producto():
    categorias = Categoria.query.all()
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = request.form['precio']
        stock = request.form['stock']
        categoria_id = request.form['categoria_id']
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

@app.route("/admin/usuarios")
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.all()
    return render_template("admin_usuarios.html", usuarios=usuarios, section="usuarios")

@app.route("/admin/usuarios/eliminar/<int:id>", methods=["POST"])
@admin_required
def admin_eliminar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    return redirect(url_for("admin_usuarios"))

@app.route("/admin/usuarios/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def admin_editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if request.method == "POST":
        usuario.nombre = request.form["nombre"]
        usuario.email = request.form["email"]
        usuario.rol = request.form["rol"]
        db.session.commit()
        return redirect(url_for("admin_usuarios"))
    return render_template("editar_usuario.html", usuario=usuario)

@app.route('/admin/reportes')
@admin_required
def admin_reportes():
    return render_template('admin_reportes.html', section="reportes")

@app.route("/admin/pedidos")
@admin_required
def admin_pedidos():
    pedidos = Pedido.query.order_by(Pedido.fecha.desc()).all()
    return render_template("admin_pedidos.html", pedidos=pedidos, section="pedidos")

# ============================
# FINALIZAR COMPRA
# ============================

@app.route("/finalizar_compra", methods=["POST"])
@login_required
def finalizar_compra():
    carrito = session.get("carrito", [])
    if not carrito:
        return redirect(url_for("carrito"))
    total = sum(item["precio"] * item.get("cantidad", 1) for item in carrito)
    insuficientes = []
    for item in carrito:
        prod = Producto.query.get(item["id"])
        cantidad = item.get("cantidad", 1)
        if not prod or prod.stock < cantidad:
            insuficientes.append((prod.nombre if prod else f"ID {item['id']}", prod.stock if prod else 0, cantidad))
    if insuficientes:
        mensaje = "Stock insuficiente para: " + ", ".join([f"{n} (stock {s}, pedido {c})" for n, s, c in insuficientes])
        total = sum(item["precio"] * item.get("cantidad", 1) for item in carrito)
        return render_template("carrito.html", items=carrito, total=total, error=mensaje)
    nuevo_pedido = Pedido(usuario_id=session["usuario_id"], total=total)
    db.session.add(nuevo_pedido)
    db.session.flush()
    for item in carrito:
        cantidad = item.get("cantidad", 1)
        pedido_item = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=item["id"],
            cantidad=cantidad,
            precio_unitario=item["precio"]
        )
        db.session.add(pedido_item)
        prod = Producto.query.get(item["id"])
        if prod:
            prod.stock = prod.stock - cantidad
    db.session.commit()
    session["carrito"] = []
    return redirect(url_for("pedido_confirmado", id=nuevo_pedido.id))

@app.route("/pedido/<int:id>/confirmado")
@login_required
def pedido_confirmado(id):
    pedido = Pedido.query.get_or_404(id)
    return render_template("pedido_confirmado.html", pedido=pedido)

# ============================
# LOGIN / LOGOUT / REGISTER
# ============================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    email = request.form["email"]
    password = request.form["password"]
    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario or not check_password_hash(usuario.password_hash, password):
        return render_template("login.html", error="Email o contraseña incorrectos")
    session["usuario_id"] = usuario.id
    session["usuario_nombre"] = usuario.nombre
    session["usuario_rol"] = usuario.rol  # <--- Guardamos rol
    return redirect("/")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route("/register")
def register():
    return render_template("register.html", active="register")

@app.route("/register", methods=["POST"])
def register_post():
    nombre = request.form["nombre"]
    email = request.form["email"]
    password = request.form["password"]
    password2 = request.form["password2"]
    if password != password2:
        return render_template("register.html", error="Las contraseñas no coinciden")
    existe = Usuario.query.filter_by(email=email).first()
    if existe:
        return render_template("register.html", error="El email ya está registrado")
    nuevo = Usuario(
        nombre=nombre,
        email=email,
        password_hash=generate_password_hash(password),
        rol="cliente"
    )
    db.session.add(nuevo)
    db.session.commit()
    return redirect("/login")

# ============================
# INICIAR SERVIDOR
# ============================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
