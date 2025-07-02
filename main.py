import telebot
import sqlite3
import datetime
import time
import schedule
import os
from telebot import types
from dotenv import load_dotenv

# --- Configuración ---
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
GRUPO_ID = os.getenv("GRUPO_ID")
DATABASE = os.getenv("DATABASE_NAME")

bot = telebot.TeleBot(TOKEN)

# --- Funciones de Base de Datos ---
def crear_conexion():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Para acceder a las columnas por nombre
    return conn

def crear_tablas():
    conn = crear_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            contraseña TEXT NOT NULL,
            rol TEXT NOT NULL,
            nombre TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio_compra REAL NOT NULL,
            precio_venta REAL NOT NULL,
            inventario INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vendedor INTEGER NOT NULL,
            id_producto INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id_vendedor) REFERENCES usuarios(id),
            FOREIGN KEY (id_producto) REFERENCES productos(id)
        )
    """)

    conn.commit()
    conn.close()

crear_tablas()

# --- Estados del Usuario ---
user_states = {}

# --- Funciones Auxiliares ---
def mostrar_menu_principal(chat_id):
    markup = types.InlineKeyboardMarkup()
    boton_venta = types.InlineKeyboardButton("💰 Venta", callback_data="venta")
    boton_historial = types.InlineKeyboardButton("📊 Historial Diario", callback_data="historial")
    markup.add(boton_venta, boton_historial)
    bot.send_message(chat_id, "¡Bienvenido, vendedor estrella! ✨ ¿Qué quieres hacer hoy?", reply_markup=markup)

def enviar_recordatorio_ventas():
    conn = crear_conexion()
    cursor = conn.cursor()
    ahora = datetime.datetime.now()
    hora_minuto = ahora.strftime("%H:%M")

    cursor.execute("""
        SELECT
            u.id AS id_vendedor,
            u.nombre AS nombre_vendedor,
            SUM(v.cantidad) AS total_ventas
        FROM ventas v
        JOIN usuarios u ON v.id_vendedor = u.id
        WHERE DATE(v.fecha) = DATE('now')
        GROUP BY u.id
    """)
    ventas_hoy = cursor.fetchall()
    conn.close()

    if ventas_hoy:
        for venta in ventas_hoy:
            mensaje = f"🕰️ {hora_minuto}: ¡Hola, {venta['nombre_vendedor']}! Hasta ahora has vendido {venta['total_ventas']} productos hoy. ¡Sigue así! 💪"
            bot.send_message(venta['id_vendedor'], mensaje)

def enviar_resumen_semanal():
    conn = crear_conexion()
    cursor = conn.cursor()

    # ... Lógica para calcular el resumen semanal (similar a lo que ya tenías) ...
    fecha_inicio = datetime.date.today() - datetime.timedelta(days=7)
    cursor.execute("""
            SELECT
                SUM(v.cantidad) AS total_ventas,
                SUM(p.precio_venta * v.cantidad) AS total_bruto,
                SUM((p.precio_venta - p.precio_compra) * v.cantidad) AS total_ganancias
            FROM ventas v
            JOIN productos p ON v.id_producto = p.id
            WHERE DATE(v.fecha) >= ?
        """, (fecha_inicio,))
    historial = cursor.fetchone()

    cursor.execute("""
                SELECT p.nombre, p.inventario FROM productos p
            """)
    inventario = cursor.fetchall()
    total_ventas = historial['total_ventas'] or 0  # Manejar el caso de None
    total_bruto = historial['total_bruto'] or 0
    total_ganancias = historial['total_ganancias'] or 0

    mensaje = f"""
    📊 **Resumen de la Semana ({fecha_inicio} - {datetime.date.today()})** 📊

    ¡Aquí está el resumen de las ventas de la semana! ¡Gracias por su arduo trabajo! 💪
    Ventas Totales: {total_ventas}
    Venta Bruta: ${total_bruto:.2f}
    Ganancias: ${total_ganancias:.2f}

    **Inventario:**
    """
    for producto in inventario:
        mensaje += f"\n- {producto['nombre']}: {producto['inventario']} unidades"
    mensaje += "\n¡Sigan vendiendo! 🚀"

    # Enviar al grupo de Telegram
    bot.send_message(GRUPO_ID, mensaje, parse_mode="Markdown")
    conn.close()

# --- Handlers ---
@bot.message_handler(commands=['start'])
def comando_start(message):
    user_states[message.chat.id] = {'state': 'inicio'}
    bot.send_message(message.chat.id, "¡Hola! Para comenzar, ingresa tu usuario de vendedor:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'inicio')
def pedir_contraseña(message):
    usuario = message.text
    conn = crear_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,))
    user = cursor.fetchone()
    conn.close()

    if user:
        user_states[message.chat.id]['state'] = 'contraseña'
        user_states[message.chat.id]['usuario'] = usuario
        bot.send_message(message.chat.id, "Ingresa tu contraseña:")
    else:
        bot.send_message(message.chat.id, "Usuario no encontrado. Por favor, inténtalo de nuevo o contacta al administrador.")
        user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'contraseña')
def validar_contraseña(message):
    contraseña = message.text
    usuario = user_states[message.chat.id]['usuario']

    conn = crear_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND contraseña = ?", (usuario, contraseña))
    user = cursor.fetchone()
    conn.close()

    if user:
        user_states[message.chat.id]['user_data'] = user
        user_states[message.chat.id]['state'] = 'menu'
        mostrar_menu_principal(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Contraseña incorrecta. Por favor, inténtalo de nuevo.")
        user_states[message.chat.id]['state'] = 'inicio'

@bot.callback_query_handler(func=lambda call: call.data == 'venta')
def seleccionar_producto(call):
    markup = types.InlineKeyboardMarkup()
    conn = crear_conexion()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM productos")
    productos = cursor.fetchall()
    conn.close()

    for producto in productos:
        boton = types.InlineKeyboardButton(producto['nombre'], callback_data=f"producto_{producto['id']}")
        markup.add(boton)

    boton_atras = types.InlineKeyboardButton("Atrás", callback_data="atras_menu")
    markup.add(boton_atras)
    bot.send_message(call.message.chat.id, "Selecciona un producto:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('producto_'))
def pedir_cantidad(call):
    producto_id = call.data.split('_')[1]
    user_states[call.message.chat.id]['state'] = 'cantidad'
    user_states[call.message.chat.id]['producto_id'] = producto_id
    bot.send_message(call.message.chat.id, "Ingresa la cantidad vendida:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'cantidad')
def registrar_venta(message):
    cantidad = message.text
    try:
        cantidad = int(cantidad)
    except ValueError:
        bot.send_message(message.chat.id, "Cantidad inválida. Por favor, ingresa un número.")
        return

    producto_id = user_states[message.chat.id]['producto_id']
    vendedor_id = user_states[message.chat.id]['user_data']['id']

    conn = crear_conexion()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO ventas (id_vendedor, id_producto, cantidad) VALUES (?, ?, ?)", (vendedor_id, producto_id, cantidad))
        cursor.execute("UPDATE productos SET inventario = inventario - ? WHERE id = ?", (cantidad, producto_id))
        conn.commit()
        bot.send_message(message.chat.id, "¡Venta registrada con éxito! 🎉")
    except sqlite3.Error as e:
        print(f"Error al registrar la venta: {e}")
        bot.send_message(message.chat.id, "Hubo un error al registrar la venta. Por favor, inténtalo de nuevo.")
    finally:
        conn.close()

    user_states[message.chat.id]['state'] = 'menu'
    mostrar_menu_principal(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == 'historial')
def mostrar_historial(call):
    vendedor_id = user_states[call.message.chat.id]['user_data']['id']
    fecha_hoy = datetime.date.today()

    conn = crear_conexion()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            SUM(v.cantidad) AS total_ventas,
            SUM(p.precio_venta * v.cantidad) AS total_bruto,
            SUM((p.precio_venta - p.precio_compra) * v.cantidad) AS total_ganancias
        FROM ventas v
        JOIN productos p ON v.id_producto = p.id
        WHERE v.id_vendedor = ? AND DATE(v.fecha) = ?
    """, (vendedor_id, fecha_hoy))
    historial = cursor.fetchone()

    cursor.execute("""
        SELECT p.nombre, p.inventario FROM productos p
    """)
    inventario = cursor.fetchall()
    conn.close()

    total_ventas = historial['total_ventas'] or 0  # Manejar el caso de None
    total_bruto = historial['total_bruto'] or 0
    total_ganancias = historial['total_ganancias'] or 0
    comision = total_ganancias * 0.20

    mensaje = f"""
    📊 **Historial de Hoy ({fecha_hoy})** 📊

    Ventas Totales: {total_ventas}
    Venta Bruta: ${total_bruto:.2f}
    Ganancias: ${total_ganancias:.2f}
    Comisión (20%): ${comision:.2f}

    **Inventario:**
    """
    for producto in inventario:
        mensaje += f"\n- {producto['nombre']}: {producto['inventario']} unidades"

    markup = types.InlineKeyboardMarkup()
    boton_atras = types.InlineKeyboardButton("Atrás", callback_data="atras_menu")
    markup.add(boton_atras)
    bot.send_message(call.message.chat.id, mensaje, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'atras_menu')
def volver_al_menu(call):
    user_states[call.message.chat.id]['state'] = 'menu'
    mostrar_menu_principal(call.message.chat.id)

# --- Admin Panel ---
@bot.message_handler(commands=['admin'])
def comando_admin(message):
    bot.send_message(message.chat.id, "Ingresa la contraseña de administrador:")
    user_states[message.chat.id] = {'state': 'admin_password'}

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'admin_password')
def validar_admin(message):
    password = message.text
    if password == ADMIN_PASSWORD:
        user_states[message.chat.id]['state'] = 'admin_menu'
        mostrar_admin_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "Contraseña incorrecta.")
        user_states.pop(message.chat.id, None)

def mostrar_admin_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    boton_ventas = types.InlineKeyboardButton("📈 Ventas por Vendedor", callback_data="admin_ventas")
    boton_productos = types.InlineKeyboardButton("📦 Gestionar Productos", callback_data="admin_productos")
    boton_usuarios = types.InlineKeyboardButton("👤 Gestionar Usuarios", callback_data="admin_usuarios")
    markup.add(boton_ventas, boton_productos, boton_usuarios)
    bot.send_message(chat_id, "¡Panel de administración!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_ventas')
def mostrar_ventas_por_vendedor(call):
    #TODO: Mostrar las ventas por vendedor
    bot.send_message(call.message.chat.id, "Función en desarrollo.")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_productos')
def gestionar_productos(call):
    #TODO: Gestionar los productos
    bot.send_message(call.message.chat.id, "Función en desarrollo.")

@bot.callback_query_handler(func=lambda call: call.data == 'admin_usuarios')
def gestionar_usuarios(call):
    #TODO: Gestionar los usuarios
    bot.send_message(call.message.chat.id, "Función en desarrollo.")

# --- Tareas Programadas ---
schedule.every(5).minutes.do(enviar_recordatorio_ventas)
schedule.every().sunday.do(enviar_resumen_semanal)

# --- Polling ---
if __name__ == '__main__':
    try:
        # Iniciar las tareas programadas en un hilo separado
        import threading
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)

        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True  # Para que el hilo se cierre cuando el programa principal termine
        scheduler_thread.start()

        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Error durante el polling: {e}")
        time.sleep(15)
