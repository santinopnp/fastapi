from fastapi import FastAPI, Request, status
import httpx
import os
from datetime import datetime, timedelta

app = FastAPI()

# --- Configuración ---
TELEGRAM_BOT_TOKEN = "7899263814:AAFfIAxbqwscUUZgEgXcPLCfcH9g53dtpoE"
CHANNELS_AND_GROUPS = [
    -1002201821366,   # Canal/grupo 1
    -1002258831170,   # Canal/grupo 2
    -1001834990266    # Canal/grupo 3
]

# Puedes usar una base de datos, pero para pruebas guardamos las membresías en memoria
user_memberships = {}

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/webhook")
async def bold_webhook(request: Request):
    data = await request.json()
    print("Pago recibido de Bold:", data)

    # --- Ajusta estos campos a cómo Bold te los envía ---
    try:
        telegram_user_id = int(data["metadata"]["telegram_user_id"])  # Bold debe mandarte el user_id
        username = data["metadata"].get("username", "")
        plan = data["product"]["name"]
    except Exception as e:
        print("Error leyendo campos:", e)
        return {"error": "Campos faltantes"}, status.HTTP_400_BAD_REQUEST

    # --- Calcula fecha de expiración ---
    days = 7
    if "Month" in plan:
        days = 30
    elif "Frequent" in plan or "3 meses" in plan or "3 Month" in plan:
        days = 90
    elif "Year" in plan or "Año" in plan or "Année" in plan:
        days = 365
    expires_at = datetime.now() + timedelta(days=days)

    # --- Guarda membresía ---
    user_memberships[telegram_user_id] = {
        "username": username,
        "expires_at": expires_at,
        "plan": plan
    }

    # --- Agrega al usuario a todos los canales/grupos ---
    for chat_id in CHANNELS_AND_GROUPS:
        await add_user_to_chat(telegram_user_id, chat_id)

    print(f"Usuario {telegram_user_id} agregado a grupos hasta {expires_at}")

    return {"status": "usuario registrado y añadido a canales"}, 200

async def add_user_to_chat(user_id, chat_id):
    """
    Usa el método Telegram para invitar a usuario a canal/grupo. 
    El bot debe ser admin en cada chat.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/inviteToChat"
    payload = {"chat_id": chat_id, "user_id": user_id}
    # ¡Atención! Este endpoint oficial para invitar a grupos privados puede requerir el método correcto.
    # En algunos casos deberás usar addChatMember o generar links de invitación.
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        print("Invite:", r.status_code, r.text)

# --- Tarea de expiración automática ---
from fastapi_utils.tasks import repeat_every

@app.on_event("startup")
@repeat_every(seconds=60 * 60 * 24)  # Cada 24 horas
async def check_expired_memberships():
    print("Verificando membresías expiradas...")
    now = datetime.now()
    to_remove = [uid for uid, info in user_memberships.items() if info["expires_at"] < now]
    for user_id in to_remove:
        for chat_id in CHANNELS_AND_GROUPS:
            await remove_user_from_chat(user_id, chat_id)
        print(f"Usuario {user_id} removido de todos los canales por expiración.")
        del user_memberships[user_id]

async def remove_user_from_chat(user_id, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/kickChatMember"
    payload = {"chat_id": chat_id, "user_id": user_id}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        print("Kick:", r.status_code, r.text)
