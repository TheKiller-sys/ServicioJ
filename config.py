    import os
    from dotenv import load_dotenv

    load_dotenv()

    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "ventas.db")
    GROUP_ID = os.getenv("GROUP_ID")
    UPTIMEROBOT_API_KEY = os.getenv("UPTIMEROBOT_API_KEY")
    UPTIMEROBOT_MONITOR_ID = os.getenv("UPTIMEROBOT_MONITOR_ID")
