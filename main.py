import telebot
from telebot import types
import datetime
import schedule
import time
import requests
import logging
import traceback

from config import TELEGRAM_TOKEN, ADMIN_PASSWORD, GROUP_ID, UPTIMEROBOT_API_KEY, UPTIMEROBOT_MONITOR_ID, LOG_GROUP_ID
from database import Database
from templates import bienvenida_template, venta_registrada_template, historial_diario_template, panel_admin_template

# Configuración del logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
db = Database()
usuarios_activos = {}  # Para rastrear el estado de autenticación
admin_panel_data = {}  # Para almacenar datos temporales del panel de administración

# --- Funciones Auxiliares ---
def generar_markup(botones):
    """Genera un teclado inline con los botones especificados."""
    markup = types.InlineKeyboardMarkup()
    for texto, callback_data in botones:
        markup.add(types.InlineKeyboardButton(text=texto, callback_data=callback_data))
    return markup

def monitorear_render():
    """Verifica el estado del bot en Render usando UptimeRobot."""
    url = f"https://api.uptimerobot.com/v2/getMonitors?api_key={UPTIMEROBOT_API_KEY}&format=json&monitors={UPTIMEROBOT_MONITOR_ID}"
    try:
        response = requests.post(url)
        data = response.json()
        if data["stat"] == "ok":
            status = data["monitors"][0]["status"]
            if status == 2:
                log_message = "El bot está funcionando correctamente."
                logging.info(log_message)
                enviar_log(log_message)
            else:
                log_message = "El bot puede estar inactivo."
                logging.warning(log_message)
                enviar_log(log_message)
        else:
            log_message = "Error al verificar el estado del bot."
            logging.error(log_message)
            enviar_log(log_message)
    except Exception as e:
        log_message = f"Error al conectar con UptimeRobot: {e}"
        logging.exception(log_message)  # Registra el error con stacktrace
        enviar_log(log_message)

def enviar_log(mensaje, tipo="INFO"):
    """Envía un mensaje de log al grupo de Telegram."""
    try:
        mensaje_formateado = f"[{tipo}] {mensaje}"
        bot.send_message(LOG_GROUP_ID, mensaje_formateado)
    except Exception as e:
        logging.error(f"Error al enviar log a Telegram: {e}")

# --- Manejadores de Comandos y Mensajes ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    """Maneja el comando /start."""
    markup = generar_markup([("Iniciar Sesión", "login")])
    bot.send_message(message.chat.id, "¡Bienvenido! Por favor, inicia sesión.", reply_markup=markup)
    logging.info(f"Usuario {message.chat.id} inició el bot.")
    enviar_log(f"Usuario {message.chat.id} inició el bot.", "INFO")

@bot.callback_query_handler(func=lambda call: call.data == 'login')
def callback_login(call):
    """Maneja el callback del botón 'Iniciar Sesión'."""
    bot.send_message(call.message.chat.id, "Ingresa tu usuario de vendedor:")
    bot.register_next_step_handler(call.message, pedir_contrasena)
    logging.info(f"Usuario {call.message.chat.id} solicitó inicio de sesión.")
    enviar_log(f"Usuario {call.message.chat.id} solicitó inicio de sesión.", "INFO")

def pedir_contrasena(message):
    """Pide la contraseña al usuario."""
    usuario = message.text
    vendedor = db.obtener_vendedor(usuario)
    if vendedor:
        usuarios_activos[message.chat.id] = {"usuario": usuario, "id": vendedor[0]}
        bot.send_message(message.chat.id, "Ingresa tu contraseña:")
        bot.register_next_step_handler(message, verificar_contrasena, vendedor[1])
        logging.info(f"Usuario {message.chat.id} ingresó usuario, solicitando contraseña.")
        enviar_log(f"Usuario {message.chat.id} ingresó usuario, solicitando contraseña.", "INFO")
    else:
        bot.send_message(message.chat.id, "Usuario no encontrado. Intenta de nuevo.")
        logging.warning(f"Usuario {message.chat.id} intentó iniciar sesión con usuario inexistente.")
        enviar_log(f"Usuario {message.chat.id} intentó iniciar sesión con usuario inexistente.", "WARNING")

def verificar_contrasena(message, contrasena_correcta):
    """Verifica la contraseña ingresada por el usuario."""
    contrasena = message.text
    if contrasena == contrasena_correcta:
        vendedor_id = usuarios_activos[message.chat.id]["id"]
        nombre_vendedor = db.obtener_vendedor(usuarios_activos[message.chat.id]["usuario"])[2]
        markup = generar_markup([("Venta", "venta"), ("Historial Diario", "historial")])
        bot.send_message(message.chat.id, bienvenida_template(nombre_vendedor), reply_markup=markup, parse_mode="Markdown")
        logging.info(f"Usuario {message.chat.id} inició sesión con éxito.")
        enviar_log(f"Usuario {message.chat.id} inició sesión con éxito.", "INFO")
    else:
        bot.send_message(message.chat.id, "Contraseña incorrecta. Intenta de nuevo.")
        del usuarios_activos[message.chat.id]
        logging.warning(f"Usuario {message.chat.id} intentó iniciar sesión con contraseña incorrecta.")
        enviar_log(f"Usuario {message.chat.id} intentó iniciar sesión con contraseña incorrecta.", "WARNING")

@bot.callback_query_handler(func=lambda call: call.data == 'venta')
def callback_venta(call):
    """Muestra la lista de productos disponibles."""
    productos = db.obtener_productos()
    botones = [(producto[1], f"producto_{producto[0]}") for producto in productos]
    botones.append(("Regresar", "inicio"))
    markup = generar_markup(botones)
    bot.send_message(call.message.chat.id, "Selecciona un producto:", reply_markup=markup)
    logging.info(f"Usuario {call.message.chat.id} solicitó registrar venta.")
    enviar_log(f"Usuario {call.message.chat.id} solicitó registrar venta.", "INFO")

@bot.callback_query_handler(func=lambda call: call.data.startswith('producto_'))
def callback_producto(call):
    """Maneja la selección de un producto."""
    producto_id = call.data.split('_')[1]
    usuarios_activos[call.message.chat.id]["producto_id"] = producto_id
    bot.send_message(call.message.chat.id, "Ingresa la cantidad vendida:")
    bot.register_next_step_handler(call.message, registrar_venta)
    logging.info(f"Usuario {call.message.chat.id} seleccionó el producto con ID {producto_id}.")
    enviar_log(f"Usuario {call.message.chat.id} seleccionó el producto con ID {producto_id}.", "INFO")

def registrar_venta(message):
    """Registra la venta ingresada por el usuario."""
    try:
        cantidad = int(message.text)
        if cantidad <= 0:
            bot.send_message(message.chat.id, "La cantidad debe ser mayor que cero. Intenta de nuevo.")
            logging.warning(f"Usuario {message.chat.id} ingresó cantidad de venta inválida (<= 0).")
            enviar_log(f"Usuario {message.chat.id} ingresó cantidad de venta inválida (<= 0).", "WARNING")
            return
    except ValueError:
        bot.send_message(message.chat.id, "Cantidad inválida. Ingresa un número entero.")
        logging.warning(f"Usuario {message.chat.id} ingresó cantidad de venta no numérica.")
        enviar_log(f"Usuario {message.chat.id} ingresó cantidad de venta no numérica.", "WARNING")
        return

    vendedor_id = usuarios_activos[message.chat.id]["id"]
    producto_id = usuarios_activos[message.chat.id]["producto_id"]
    producto = db.obtener_producto(producto_id)
    try:
        db.registrar_venta(vendedor_id, producto_id, cantidad)
        markup = generar_markup([("Regresar", "inicio")])
        bot.send_message(message.chat.id, venta_registrada_template(cantidad, producto[1]), reply_markup=markup)
        logging.info(f"Venta registrada para el usuario {message.chat.id}: Producto {producto[1]}, Cantidad {cantidad}.")
        enviar_log(f"Venta registrada para el usuario {message.chat.id}: Producto {producto[1]}, Cantidad {cantidad}.", "INFO")
    except Exception as e:
        bot.send_message(message.chat.id, "Error al registrar la venta.")
        logging.exception(f"Error al registrar la venta para el usuario {message.chat.id}: {e}")
        enviar_log(f"Error al registrar la venta para el usuario {message.chat.id}: {e}", "ERROR")

@bot.callback_query_handler(func=lambda call: call.data == 'historial')
def callback_historial(call):
    """Muestra el historial diario de ventas del vendedor."""
    vendedor_id = usuarios_activos[call.message.chat.id]["id"]
    ventas = db.obtener_ventas_diarias(vendedor_id)
    ganancias_brutas = sum(venta[1] * venta[2] for venta in ventas)
    ganancias_personales = ganancias_brutas * 0.20

    # Calcular el porcentaje de ventas del vendedor
    total_ventas_hoy = sum(venta[1] * venta[2] for venta in db.obtener_ventas_diarias(None))  # Todas las ventas diarias
    porcentaje = (ganancias_brutas / total_ventas_hoy) * 100 if total_ventas_hoy > 0 else 0

    inventario = db.obtener_inventario()  # Obtener el inventario
    inventario_str = ", ".join(item[0] for item in inventario)

    markup = generar_markup([("Regresar", "inicio")])
    historial_mensaje = historial_diario_template(len(ventas), ganancias_brutas, ganancias_personales, porcentaje, inventario_str)
    bot.send_message(call.message.chat.id, historial_mensaje, reply_markup=markup, parse_mode="Markdown")
    logging.info(f"Usuario {call.message.chat.id} solicitó el historial diario.")
    enviar_log(f"Usuario {call.message.chat.id} solicitó el historial diario.", "INFO")

@bot.callback_query_handler(func=lambda call: call.data == 'inicio')
def callback_inicio(call):
    """Regresa al menú principal."""
    nombre_vendedor = db.obtener_vendedor(usuarios_activos[call.message.chat.id]["usuario"])[2]
    markup = generar_markup([("Venta", "venta"), ("Historial Diario", "historial")])
    bot.send_message(call.message.chat.id, bienvenida_template(nombre_vendedor), reply_markup=markup, parse_mode="Markdown")
    logging.info(f"Usuario {call.message.chat.id} regresó al menú principal.")
    enviar_log(f"Usuario {call.message.chat.id} regresó al menú principal.", "INFO")

# --- Admin Panel ---
@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    """Maneja el comando /admin."""
    bot.send_message(message.chat.id, "Ingresa la contraseña de administrador:")
    bot.register_next_step_handler(message, verificar_admin)
    logging.info(f"Usuario {message.chat.id} intentó acceder al panel de administración.")
    enviar_log(f"Usuario {message.chat.id} intentó acceder al panel de administración.", "INFO")

def verificar_admin(message):
    """Verifica la contraseña del administrador."""
    contrasena = message.text
    if contrasena == ADMIN_PASSWORD:
        markup = generar_markup([
            ("Agregar Producto", "admin_agregar_producto"),
            ("Restar Producto", "admin_restar_producto"),
            ("Añadir Vendedor", "admin_anadir_vendedor"),
            ("Ver Datos", "admin_ver_datos")
        ])
        bot.send_message(message.chat.id, "Panel de Administración", reply_markup=markup)
        logging.info(f"Administrador accedió al panel de administración.")
        enviar_log(f"Administrador accedió al panel de administración.", "INFO")
    else:
        bot.send_message(message.chat.id, "Contraseña incorrecta.")
        logging.warning(f"Intento fallido de acceso al panel de administración.")
        enviar_log(f"Intento fallido de acceso al panel de administración.", "WARNING")

# --- Admin: Agregar Producto ---
@bot.callback_query_handler(func=lambda call: call.data == 'admin_agregar_producto')
def admin_agregar_producto(call):
    """Inicia el proceso para agregar un producto."""
    admin_panel_data[call.message.chat.id] = {}
    bot.send_message(call.message.chat.id, "Ingresa el nombre del producto:")
    bot.register_next_step_handler(call.message, admin_agregar_producto_nombre)
    logging.info(f"Administrador inició el proceso de agregar producto.")
    enviar_log(f"Administrador inició el proceso de agregar producto.", "INFO")

def admin_agregar_producto_nombre(message):
    """Guarda el nombre del producto."""
    admin_panel_data[message.chat.id]['nombre'] = message.text
    bot.send_message(message.chat.id, "Ingresa el precio de compra:")
    bot.register_next_step_handler(message, admin_agregar_producto_precio_compra)

def admin_agregar_producto_precio_compra(message):
    """Guarda el precio de compra del producto."""
    try:
        admin_panel_data[message.chat.id]['precio_compra'] = float(message.text)
        bot.send_message(message.chat.id, "Ingresa el precio de venta:")
        bot.register_next_step_handler(message, admin_agregar_producto_precio_venta)
    except ValueError:
        bot.send_message(message.chat.id, "Precio de compra inválido. Ingresa un número.")
        del admin_panel_data[message.chat.id]
        logging.warning(f"Administrador ingresó precio de compra inválido.")
        enviar_log(f"Administrador ingresó precio de compra inválido.", "WARNING")

def admin_agregar_producto_precio_venta(message):
    """Guarda el precio de venta del producto y confirma la creación."""
    try:
        precio_venta = float(message.text)
        if 'precio_compra' in admin_panel_data[message.chat.id] and precio_venta <= admin_panel_data[message.chat.id]['precio_compra']:
            bot.send_message(message.chat.id, "El precio de venta debe ser mayor que el precio de compra. Intenta de nuevo.")
            del admin_panel_data[message.chat.id]
            logging.warning(f"Administrador ingresó precio de venta menor o igual al precio de compra.")
            enviar_log(f"Administrador ingresó precio de venta menor o igual al precio de compra.", "WARNING")
            return

        admin_panel_data[message.chat.id]['precio_venta'] = precio_venta
        producto_nombre = admin_panel_data[message.chat.id]['nombre']
        precio_compra = admin_panel_data[message.chat.id]['precio_compra']

        if db.agregar_producto(producto_nombre, precio_compra, precio_venta):
            bot.send_message(message.chat.id, f"Producto '{producto_nombre}' agregado con éxito.")
            logging.info(f"Administrador agregó el producto '{producto_nombre}'.")
            enviar_log(f"Administrador agregó el producto '{producto_nombre}'.", "INFO")
        else:
            bot.send_message(message.chat.id, f"Ya existe un producto con el nombre '{producto_nombre}'.")
            logging.warning(f"Administrador intentó agregar producto con nombre existente.")
            enviar_log(f"Administrador intentó agregar producto con nombre existente.", "WARNING")
    except ValueError:
        bot.send_message(message.chat.id, "Precio de venta inválido. Ingresa un número.")
        logging.warning(f"Administrador ingresó precio de venta inválido.")
        enviar_log(f"Administrador ingresó precio de venta inválido.", "WARNING")
    finally:
        if message.chat.id in admin_panel_data:
            del admin_panel_data[message.chat.id]

# --- Admin: Añadir Vendedor ---
@bot.callback_query_handler(func=lambda call: call.data == 'admin_anadir_vendedor')
def admin_anadir_vendedor(call):
    """Inicia el proceso para añadir un vendedor."""
    admin_panel_data[call.message.chat.id] = {}
    bot.send_message(call.message.chat.id, "Ingresa el usuario del nuevo vendedor:")
    bot.register_next_step_handler(call.message, admin_anadir_vendedor_usuario)
    logging.info(f"Administrador inició el proceso de añadir vendedor.")
    enviar_log(f"Administrador inició el proceso de añadir vendedor.", "INFO")

def admin_anadir_vendedor_usuario(message):
    """Guarda el usuario del nuevo vendedor."""
    admin_panel_data[message.chat.id]['usuario'] = message.text
    bot.send_message(message.chat.id, "Ingresa la contraseña del nuevo vendedor:")
    bot.register_next_step_handler(message, admin_anadir_vendedor_contrasena)

def admin_anadir_vendedor_contrasena(message):
    """Guarda la contraseña del nuevo vendedor."""
    admin_panel_data[message.chat.id]['contrasena'] = message.text
    bot.send_message(message.chat.id, "Ingresa el nombre del nuevo vendedor:")
    bot.register_next_step_handler(message, admin_anadir_vendedor_nombre)

def admin_anadir_vendedor_nombre(message):
    """Guarda el nombre del nuevo vendedor y confirma la creación."""
    nombre = message.text
    usuario = admin_panel_data[message.chat.id]['usuario']
    contrasena = admin_panel_data[message.chat.id]['contrasena']
    try:
        if db.agregar_vendedor(usuario, contrasena, nombre):
            bot.send_message(message.chat.id, f"Vendedor '{nombre}' agregado con éxito.")
            logging.info(f"Administrador agregó el vendedor '{nombre}'.")
            enviar_log(f"Administrador agregó el vendedor '{nombre}'.", "INFO")
        else:
            bot.send_message(message.chat.id, f"Ya existe un vendedor con el usuario '{usuario}'.")
            logging.warning(f"Administrador intentó agregar vendedor con usuario existente.")
            enviar_log(f"Administrador intentó agregar vendedor con usuario existente.", "WARNING")
    except Exception as e:
        bot.send_message(message.chat.id, "Error al agregar vendedor.")
        logging.exception(f"Error al agregar vendedor: {e}")
        enviar_log(f"Error al agregar vendedor: {e}", "ERROR")
    finally:
        del admin_panel_data[message.chat.id]

# --- Admin: Ver Datos ---
@bot.callback_query_handler(func=lambda call: call.data == 'admin_ver_datos')
def admin_ver_datos(call):
    """Muestra los datos del panel de administración."""
    datos = obtener_datos_admin()
    bot.send_message(call.message.chat.id, panel_admin_template(datos), parse_mode="Markdown")
    logging.info(f"Administrador solicitó ver los datos del panel de administración.")
    enviar_log(f"Administrador solicitó ver los datos del panel de administración.", "INFO")

# --- Admin: Restar Producto ---
@bot.callback_query_handler(func=lambda call: call.data == 'admin_restar_producto')
def admin_restar_producto(call):
    """Inicia el proceso para restar producto (IMPLEMENTACIÓN INCOMPLETA)."""
    bot.send_message(call.message.chat.id, "Ingresa el nombre del producto que deseas restar:")
    bot.register_next_step_handler(call.message, admin_restar_producto_nombre)
    logging.info(f"Administrador inició el proceso para restar producto.")
    enviar_log(f"Administrador inició el proceso para restar producto.", "INFO")

def admin_restar_producto_nombre(message):
    """Guarda el nombre del producto que se va a restar (IMPLEMENTACIÓN INCOMPLETA)."""
    producto_nombre = message.text
    producto = db.obtener_producto_por_nombre(producto_nombre)
    if producto:
        admin_panel_data[message.chat.id] = {'producto_id': producto[0]}
        bot.send_message(message.chat.id, f"Ingresa la cantidad que deseas restar del producto '{producto_nombre}':")
        bot.register_next_step_handler(message, admin_restar_producto_cantidad)
    else:
        bot.send_message(message.chat.id, f"No se encontró un producto con el nombre '{producto_nombre}'.")
        logging.warning(f"Administrador intentó restar producto con nombre inexistente.")
        enviar_log(f"Administrador intentó restar producto con nombre inexistente.", "WARNING")

def admin_restar_producto_cantidad(message):
    """Guarda la cantidad que se va a restar del producto (IMPLEMENTACIÓN INCOMPLETA)."""
    try:
        cantidad = int(message.text)
        if cantidad <= 0:
            bot.send_message(message.chat.id, "La cantidad debe ser mayor que cero. Intenta de nuevo.")
            logging.warning(f"Administrador ingresó cantidad de resta de producto inválida (<= 0).")
            enviar_log(f"Administrador ingresó cantidad de resta de producto inválida (<= 0).", "WARNING")
            return

        producto_id = admin_panel_data[message.chat.id]['producto_id']
        # Aquí iría la lógica para restar la cantidad del producto en la base de datos
        # (IMPLEMENTACIÓN INCOMPLETA)
        bot.send_message(message.chat.id, f"Cantidad {cantidad} restada del producto (IMPLEMENTACIÓN INCOMPLETA).")
        logging.info(f"Administrador restó cantidad {cantidad} del producto (IMPLEMENTACIÓN INCOMPLETA).")
        enviar_log(f"Administrador restó cantidad {cantidad} del producto (IMPLEMENTACIÓN INCOMPLETA).", "INFO")

    except ValueError:
        bot.send_message(message.chat.id, "Cantidad inválida. Ingresa un número entero.")
        logging.warning(f"Administrador ingresó cantidad de resta de producto no numérica.")
        enviar_log(f"Administrador ingresó cantidad de resta de producto no numérica.", "WARNING")
    finally:
        if message.chat.id in admin_panel_data:
            del admin_panel_data[message.chat.id]

# --- Obtener Datos Admin ---
def obtener_datos_admin():
    """Obtiene datos para el panel de administración."""
    hoy = datetime.date.today()
    ganancias_diarias_totales = 0
    ventas_brutas_totales = 0
    ventas_por_vendedor = {}

    for vendedor in db.cursor.execute("SELECT id, nombre FROM vendedores").fetchall():
        vendedor_id = vendedor[0]
        ventas_diarias = db.obtener_ventas_diarias(vendedor_id)
        ganancia_vendedor = sum(venta[1] * venta[2] for venta in ventas_diarias)
        cantidad_productos_vendidos = sum(venta[1] for venta in ventas_diarias)

        ganancias_diarias_totales += ganancia_vendedor
        ventas_brutas_totales += ganancia_vendedor
        ventas_por_vendedor[vendedor[1]] = {
            'cantidad_productos': cantidad_productos_vendidos,
            'ganancia': ganancia_vendedor
        }

    datos = {
        'ganancias_diarias_totales': ganancias_diarias_totales,
        'ventas_brutas_totales': ventas_brutas_totales,
        'ventas_por_vendedor': ventas_por_vendedor
    }
    return datos

# --- Resumen Semanal ---
def enviar_resumen_semanal():
    """Calcula y envía un resumen semanal al grupo de Telegram."""
    hoy = datetime.date.today()
    inicio_semana = hoy - datetime.timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + datetime.timedelta(days=6)

    ganancias_semanales_totales = 0
    ventas_semanales_totales = 0
    productos_vendidos = {}
    ventas_por_vendedor = {}

    for vendedor in db.cursor.execute("SELECT id, nombre FROM vendedores").fetchall():
        vendedor_id = vendedor[0]
        ventas_semanales = db.obtener_ventas_semanales(vendedor_id, inicio_semana, fin_semana)
        ganancia_vendedor = sum(venta[1] * venta[2] for venta in ventas_semanales)
        cantidad_productos_vendidos = sum(venta[1] for venta in ventas_semanales)

        ganancias_semanales_totales += ganancia_vendedor
        ventas_semanales_totales += cantidad_productos_vendidos
        ventas_por_vendedor[vendedor[1]] = {
            'cantidad_productos': cantidad_productos_vendidos,
            'ganancia': ganancia_vendedor
        }

        for venta in ventas_semanales:
            producto_nombre = venta[0]  # Assuming venta[0] is the product name
            cantidad = venta[1]
            if producto_nombre in productos_vendidos:
                productos_vendidos[producto_nombre] += cantidad
            else:
                productos_vendidos[producto_nombre] = cantidad

    # Find the best seller
    best_seller = max(ventas_por_vendedor, key=lambda k: ventas_por_vendedor[k]['ganancia']) if ventas_por_vendedor else "N/A"

    # Find the best selling product
    best_selling_product = max(productos_vendidos, key=productos_vendidos.get) if productos_vendidos else "N/A"

    resumen_mensaje = f"""
📊 *Resumen Semanal ({inicio_semana} - {fin_semana})* 📊
Ganancias semanales totales: ${ganancias_semanales_totales:.2f}
Ventas semanales totales: {ventas_semanales_totales} productos
Producto más vendido: {best_selling_product}

*Ventas por Vendedor:*
"""
    for vendedor, datos in ventas_por_vendedor.items():
        resumen_mensaje += f"\n{vendedor}: {datos['cantidad_productos']} productos (${datos['ganancia']:.2f})"

    resumen_mensaje += f"""\n\nEl vendedor de la semana: {best_seller}"""

    try:
        bot.send_message(GROUP_ID, resumen_mensaje, parse_mode="Markdown")
        logging.info("Resumen semanal enviado al grupo.")
        enviar_log("Resumen semanal enviado al grupo.", "INFO")
    except Exception as e:
        logging.error(f"Error al enviar resumen semanal al grupo: {e}")
        enviar_log(f"Error al enviar resumen semanal al grupo: {e}", "ERROR")

# --- Consultas a la base de datos ---
    """Obtiene las ventas semanales de un vendedor desde la base de datos."""
def obtener_ventas_semanales(self, vendedor_id, inicio_semana, fin_semana):
    """Obtiene las ventas semanales de un vendedor desde la base de datos."""
    self.cursor.execute("""
        SELECT p.nombre, v.cantidad, p.precio_venta
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        WHERE v.vendedor_id = ? AND DATE(v.fecha) BETWEEN ? AND ?
    """, (vendedor_id, inicio_semana.strftime('%Y-%m-%d'), fin_semana.strftime('%Y-%m-%d')))
    return self.cursor.fetchall()

def obtener_producto_por_nombre(self, producto_nombre):
    """Obtiene un producto por nombre desde la base de datos."""
    self.cursor.execute("SELECT id FROM productos WHERE nombre = ?", (producto_nombre,))
    return self.cursor.fetchone()
Database.obtener_ventas_semanales = obtener_ventas_semanales
Database.obtener_producto_por_nombre = obtener_producto_por_nombre

# --- Tareas Programadas ---
schedule.every().sunday.at("20:00").do(enviar_resumen_semanal)
schedule.every(20).minutes.do(monitorear_render)

# --- Bucle Principal ---
if __name__ == '__main__':
    print("Bot iniciado...")
    enviar_log("Bot iniciado.", "INFO")  # Envía un log al iniciar el bot
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            log_message = f"Error de conexión: {e}"
            logging.exception(log_message)  # Registra el error con stacktrace
            enviar_log(log_message, "ERROR")
            time.sleep(15)
        schedule.run_pending()
        time.sleep(1)
