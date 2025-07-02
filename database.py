import sqlite3

class Database:
    def __init__(self, db_name="ventas.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE,
                contrasena TEXT,
                nombre TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE,
                precio_compra REAL,
                precio_venta REAL
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendedor_id INTEGER,
                producto_id INTEGER,
                cantidad INTEGER,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vendedor_id) REFERENCES vendedores(id),
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
        """)
        self.conn.commit()

    # Métodos para añadir, obtener, actualizar y eliminar datos (vendedores, productos, ventas)
    def agregar_vendedor(self, usuario, contrasena, nombre):
        try:
            self.cursor.execute("INSERT INTO vendedores (usuario, contrasena, nombre) VALUES (?, ?, ?)", (usuario, contrasena, nombre))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Usuario ya existe

    def obtener_vendedor(self, usuario):
        self.cursor.execute("SELECT id, contrasena, nombre FROM vendedores WHERE usuario = ?", (usuario,))
        return self.cursor.fetchone()

    def agregar_producto(self, nombre, precio_compra, precio_venta):
        try:
            self.cursor.execute("INSERT INTO productos (nombre, precio_compra, precio_venta) VALUES (?, ?, ?)", (nombre, precio_compra, precio_venta))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Producto ya existe

    def obtener_productos(self):
        self.cursor.execute("SELECT id, nombre, precio_venta FROM productos")
        return self.cursor.fetchall()

    def obtener_producto(self, producto_id):
        self.cursor.execute("SELECT id, nombre, precio_compra, precio_venta FROM productos WHERE id = ?", (producto_id,))
        return self.cursor.fetchone()

    def registrar_venta(self, vendedor_id, producto_id, cantidad):
        self.cursor.execute("INSERT INTO ventas (vendedor_id, producto_id, cantidad) VALUES (?, ?, ?)", (vendedor_id, producto_id, cantidad))
        self.conn.commit()

    def obtener_ventas_diarias(self, vendedor_id):
        self.cursor.execute("""
            SELECT p.nombre, v.cantidad, p.precio_venta
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            WHERE v.vendedor_id = ? AND DATE(v.fecha) = DATE('now')
        """, (vendedor_id,))
        return self.cursor.fetchall()

    def obtener_inventario(self):
          self.cursor.execute("SELECT nombre FROM productos")
          return self.cursor.fetchall()

    def close(self):
        self.conn.close()
