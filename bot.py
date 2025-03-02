#!/usr/bin/env python
import logging
import os
from dotenv import load_dotenv
import telnetlib
import time
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

ADMIN_ID = int(os.getenv("ADMIN_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")
HOST = os.getenv("HOST")
PORTS = os.getenv("PORTS")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
TIMEOUT = int(os.getenv("TIMEOUT"))

ports = [int(port.strip()) for port in PORTS.split(",") if port.strip()]
modules = [(port, f"module{i}") for port in ports for i in (1, 2)]

def decode_sms_text(text: str) -> str:

    if re.fullmatch(r"[0-9A-Fa-f]+", text) and len(text) % 4 == 0:
        try:
            decoded = bytes.fromhex(text).decode("utf-16-be")
            return decoded
        except Exception as e:
            logging.error("SMS Decode Error: %s", e)
            return text
    return text

def get_sms(module_index: int):
    if module_index < 1 or module_index > len(modules):
        return None, "Invalid module index"
    
    port, module_name = modules[module_index - 1]
    try:
        tn = telnetlib.Telnet(HOST, port, TIMEOUT)
        tn.read_until(b"username: ")
        tn.write((USERNAME + "\r\n").encode())
        tn.read_until(b"password: ")
        tn.write((PASSWORD + "\r\n").encode())

        tn.write((module_name + "\r\n").encode())
        tn.write(b"0\r\n")
        tn.write(b"ate1\r\n")
        tn.write(b"at+cmgf=1\r\n")
        time.sleep(1)

        tn.write(b'at+cmgl="ALL"\r\n')
        response = tn.read_until(b"OK", TIMEOUT)
        resp_str = response.decode("utf-8", errors="ignore")
        
        sms_list = []
        pattern = r'\+CMGL: (\d+),".*?","(.*?)".*?\n(.*?)\n'
        matches = re.findall(pattern, resp_str)
        for sms_index, phone, text in matches:
            decoded_text = decode_sms_text(text.strip())
            sms_list.append((sms_index, phone, decoded_text))
        
        for sms_index, phone, text in sms_list:
            tn.write(f'at+cmgd={sms_index}\r\n'.encode())
            time.sleep(0.5)
            tn.read_until(b"OK", TIMEOUT)
        tn.close()
        return sms_list, None
    except Exception as e:
        return None, str(e)

async def getsms_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /getsms <module_index>")
        return

    try:
        module_index = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Module index must be an integer.")
        return

    await update.message.reply_text(f"Connecting to module {module_index}...")
    sms_list, error = get_sms(module_index)
    if error:
        await update.message.reply_text(f"Error: {error}")
        return

    if sms_list:
        for sms_index, phone, text in sms_list:
            message = f"SMS from {phone}:\n{text}"
            await update.message.reply_text(message)
    else:
        await update.message.reply_text("No SMS messages found.")

def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.ERROR
    )
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("getsms", getsms_command))
    application.run_polling()

if __name__ == "__main__":
    main()
