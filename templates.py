def bienvenida_template(nombre_vendedor):
    return f"""
¡Hola, {nombre_vendedor}! 💪 ¡Preparado para conquistar el día? 🚀
Registra tus ventas y ¡vamos a superar esos objetivos! 🎯
"""

def venta_registrada_template(cantidad, producto):
    return f"""
¡Venta registrada! 🎉
Has vendido {cantidad} unidades de {producto}. ¡Sigue así! 💰
"""

def historial_diario_template(ventas, ganancias_brutas, ganancias_personales, porcentaje, inventario):
    template = f"""
📈 *Resumen del día* 📈
Ventas totales: {ventas}
Ganancias brutas: ${ganancias_brutas:.2f}
Tu ganancia (20%): ${ganancias_personales:.2f}
Tu porcentaje de ventas: {porcentaje:.2f}%
Inventario disponible: {inventario}
"""
    return template

def panel_admin_template(datos):
    template = f"""
📊 *Panel de Administración* 📊
Ganancias diarias totales: ${datos['ganancias_diarias_totales']:.2f}
Ventas brutas totales: ${datos['ventas_brutas_totales']:.2f}

*Ventas por Vendedor*
"""
    for vendedor, detalles in datos['ventas_por_vendedor'].items():
        template += f"\n{vendedor}: {detalles['cantidad_productos']} productos (${detalles['ganancia']:.2f})"

    return template
