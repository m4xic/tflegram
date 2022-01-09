## Imports
# General
import json
import random
from functools import partial

# Telegram API library
from telegram import Update, ParseMode
from telegram.constants import PARSEMODE_HTML
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# TfL API library
import requests

# Environment variable loading
from dotenv import load_dotenv
from os import getenv
load_dotenv()

## Telegram API setup
updater = Updater(token=getenv('TFLG_TELEGRAM_TOKEN'), use_context=True)
dispatcher = updater.dispatcher

## Config setup
with open('config.json') as f: config = f.read()
sev_formats = json.loads(config)['severities']
aliases = json.loads(config)['aliases']
recognised_lines = json.loads(config)['lines']
bot_settings = json.loads(config)['settings']

## Telegram commands

# /help
def help(update: Update, context: CallbackContext):
    message = f"""🤖 <b>Hi, I'm {bot_settings['name']} 🚝🚍🚟</b>
    
I'm here to help you get around on TfL

<b>/status</b>
Check the status of the whole network.

<b>/status &lt;line&gt;</b>
Check the status of a specific line.

⚡️ Powered by <b><a href="https://tfl.gov.uk/info-for/open-data-users/">TfL Open Data</a></b>
👨🏽‍🔧 Maintained by <b><a href="https://github.com/m4xic">@m4xic</a></b>
🏙 Made with 🤍 (and 🐍) in London... obviously"""
    context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=PARSEMODE_HTML, disable_web_page_preview=True)
dispatcher.add_handler(CommandHandler('start', help))
dispatcher.add_handler(CommandHandler('help', help))

# Ping
def ping(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Pong! 🏓")
dispatcher.add_handler(CommandHandler('ping', ping))

# Overall service status
def service_status(update: Update, context: CallbackContext, requested_line=None):
    # If there are no arguments, get the whole network status
    if context.args == [] and requested_line == None:
        api_status = requests.get("https://api.tfl.gov.uk/line/mode/tube,overground,dlr,tflrail/status").json()
        # Create an empty dict to store the current statuses in
        statuses = {}
        # For each line in the API response...
        for line in api_status:
            # Get the worst (first) severity status on the line
            worst_severity = line['lineStatuses'][0]['statusSeverityDescription']
            # Create a list for this status if it doesn't already exist
            if worst_severity not in statuses.keys(): statuses[worst_severity] = [line['name']]
            else: statuses[worst_severity].append(line['name'])
        # Create the message 
        message = "👋 Here's the current status across the network (via <a href=\"https://tfl.gov.uk/tube-dlr-overground/status\">tfl.gov.uk</a>)"
        message += f"\n💭 You can also ask me about a specific line, like <code>/status {random.choice(['dlr', 'wac', 'hammersmith', 'hac', 'jubilee', 'bakerloo', 'overground', 'tflrail'])}</code>"
        # For each status...
        for status in statuses.keys():
            # If we have an emoji configured to be associated with the status, add it
            if status in sev_formats.keys(): message += f"\n\n<b>{sev_formats[status]} {status}</b>"
            # Otherwise, use the default emoji
            else: message += f"\n\n<b>{sev_formats['*']} {status}</b>"
            # Add each line that has the chosen severity status
            message += '\n' + ', '.join(statuses[status])
        # Send the message
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        if requested_line == None:
            # Check if a line alias has been used, and if so substitute it
            arg = context.args[0].split()[0].lower()
            if arg in aliases.keys(): line = aliases[arg]
            else: line = arg
        else:
            line = requested_line

        # Make a request to the API and check if the line exists
        api_status = requests.get(f"https://api.tfl.gov.uk/Line/{line}/Status").json()
        # If the line doesn't exist, stop here and tell the user
        if requests.get(f"https://api.tfl.gov.uk/Line/{line}/Status").status_code == 404: context.bot.send_message(chat_id=update.effective_chat.id, text="🤷 Sorry, I didn't recognise that line. ")

        # If the line does exist...
        else:
            # Get the status description ('Good Service', 'Minor Delays') for the line
            status = api_status[0]['lineStatuses'][0]['statusSeverityDescription']

            # If we have an emoji configured to be associated with the status, add it
            if status in sev_formats.keys(): message = f"{sev_formats[status]} <b>{status}</b> on <b>{api_status[0]['name']}</b> services."
            # Otherwise, use the default emoji
            else: message = f"\n\n{sev_formats['*']} <b>{status}</b> on <b>{api_status[0]['name']}</b> services"

            # If there is a 'reason', there is a disruption so we should tell the user what's going on
            if 'reason' in api_status[0]['lineStatuses'][0].keys():
                for disruption in api_status[0]['lineStatuses']:
                    message += f"\n\n<pre>{disruption['reason']}</pre>"
                # Append the TfL Status page only if a disruption has been identified
                message += "\n\nMore info and alternative routes available on the <a href=\"https://tfl.gov.uk/tube-dlr-overground/status\">TfL website</a>."
            # Send the reply, disabling message previews to make the message cleaner
            context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
dispatcher.add_handler(CommandHandler('status', service_status))

# Add handlers for direct / commands for each line and alias
for line in recognised_lines:
    if "-" not in line:
        dispatcher.add_handler(CommandHandler(line, partial(service_status, requested_line=line)))
for alias in aliases.keys():
    if "-" not in alias:
        dispatcher.add_handler(CommandHandler(alias, partial(service_status, requested_line=aliases[alias])))

# Fallback
def unknown(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="🤷 Sorry, I'm not sure what command you want. Try /help to see what you can do.")
dispatcher.add_handler(MessageHandler(Filters.command, unknown))

## Start the Telegram bot
updater.start_polling()
print("✅ Started TfLegram")