## Imports
# General
import json
import random
from functools import partial
from math import ceil

# Telegram API library
from telegram import Update, ParseMode, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import PARSEMODE_HTML
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

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
            if worst_severity == "Special Service" and "strike" in line['lineStatuses'][0]['reason'].lower(): worst_severity = "Strike Action (/strikes)"
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
            if status == "Special Service" and "strike" in api_status[0]['lineStatuses'][0]['reason'].lower(): status = "Strike Action (/strikes)"

            # If we have an emoji configured to be associated with the status, add it
            if status in sev_formats.keys(): message = f"{sev_formats[status]} <b>{status}</b> on <b>{api_status[0]['name']}</b> services."
            # Otherwise, use the default emoji
            else: message = f"\n\n{sev_formats['*']} <b>{status}</b> on <b>{api_status[0]['name']}</b> services"

            # If there is a 'reason', there is a disruption so we should tell the user what's going on
            if 'reason' in api_status[0]['lineStatuses'][0].keys():
                for disruption in api_status[0]['lineStatuses']:
                    message += f"\n\n<pre>{disruption['reason'].rstrip()}</pre>"
                # Append the TfL Status page only if a disruption has been identified
                message += "\n\nMore info and alternative routes available on the <a href=\"https://tfl.gov.uk/tube-dlr-overground/status\">TfL website</a>."
            # Send the reply, disabling message previews to make the message cleaner
            context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
dispatcher.add_handler(CommandHandler('status', service_status))

# Strike info
# TODO: Document code
def strikes(update: Update, context: CallbackContext):
    api_status = requests.get("https://api.tfl.gov.uk/line/mode/tube,overground,dlr,tflrail/status").json()
    lines_on_strike = {}
    for line in api_status:
        for status_message in line['lineStatuses']:
            if status_message['statusSeverityDescription'] == 'Special Service' and "strike" in status_message['reason'].lower():
                if status_message['reason'] in lines_on_strike.keys(): lines_on_strike[status_message['reason']].append(line['name'])
                else: lines_on_strike[status_message['reason']] = [line['name']]

    num_on_strike = sum([len(lines_on_strike[x]) for x in lines_on_strike])
    if lines_on_strike == {}:
        message = f"<b>✅ Good news!</b> I can't see any strikes affecting the network right now.\n\nYou can use /status to check for other incidents."
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        message = f"🪧 <b>Heads up!</b> {num_on_strike} line" + ("s" if num_on_strike != 1 else "") + " might be affected. Here's what you need to know."
        for reason in lines_on_strike.keys():
            message += f"\n\n⚠️ <b>{', '.join(lines_on_strike[reason][:-1])} and {lines_on_strike[reason][-1]}</b>"
            message += f"\n<pre>{reason.rstrip()}</pre>"
        message += "\n\nMore info and alternative routes available on the <a href=\"https://tfl.gov.uk/tube-dlr-overground/status\">TfL website</a>."
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
dispatcher.add_handler(CommandHandler('strikes', strikes))
dispatcher.add_handler(CommandHandler('strike', strikes))

# Next departures
# TODO: Write proper user messages for each stage
LOCATION, STATION_SELECTED, LINE_SELECTED = range(3)
def now(update: Update, context: CallbackContext):
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(text="📍 Send Location", request_location=True)]], one_time_keyboard=True, resize_keyboard=True)
    context.bot.send_message(chat_id=update.effective_chat.id, text="📍 <b>Let's get moving!</b> I'll need your location to find your nearest station.", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=reply_markup)
    return LOCATION
def now_loc(update: Update, context: CallbackContext):
    lon, lat = update.message.location['longitude'], update.message.location['latitude']
    station_search = requests.get(f'https://api.tfl.gov.uk/StopPoint/?lat={lat}&lon={lon}&stopTypes=NaptanMetroStation,NaptanRailStation&radius=1000&modes=tube,dlr,overground,tflrail').json()
    stations = {}
    while len(stations) < 4:
        for current_station in station_search['stopPoints']: stations[current_station['commonName']] = current_station['id']
        break
    if len(stations) == 0:
        context.bot.send_message(chat_id=update.effective_chat.id, text="🗺 <b>Sorry!</b> I can't see any stations nearby...", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    context.user_data['station_ids'] = stations
    station_names = list(stations.keys())[::-1]
    buttons, this_row = [], []
    # TODO: Spin this out in to it's own function for keyboard generation
    while station_names != []:
        this_row.append(KeyboardButton(text=f"{station_names[-1]}"))
        station_names.pop()
        if len(this_row) == 2 or station_names == []:
            buttons.append(this_row)
            this_row = []
    reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
    context.bot.send_message(chat_id=update.effective_chat.id, text="🚏 <b>Great!</b> Now, pick the station you're travelling from.", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=reply_markup)
    return STATION_SELECTED
def now_results(update: Update, context: CallbackContext):
    if update.message.text not in context.user_data['station_ids'].keys():
        context.bot.send_message(chat_id=update.effective_chat.id, text="😵‍💫 <b>I don't recognise that station!</b> Make sure you tap the button on your screen instead of typing the station name.", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    context.user_data['chosen_station'] = update.message.text
    arrivals = requests.get(f"https://api.tfl.gov.uk/StopPoint/{context.user_data['station_ids'][context.user_data['chosen_station']]}/Arrivals").json()
    if arrivals == []:
        context.bot.send_message(chat_id=update.effective_chat.id, text="😴 <b>No arrivals coming up.</b> The station might be closed. (/status)", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        message = f"🚝 <b>Next trains</b> at <b>{context.user_data['chosen_station']}</b>\n"
        lines = {}
        # TODO: Refactor this - change to group by Line -> Platform -> Destination -> [Times] (not Line -> Destination -> {Platform and Times})
        for arrival in arrivals:
            if 'destinationName' not in arrival.keys():
                lineName, destinationName, timeToStation, platformName = arrival['lineName'], arrival['towards'].replace("Check Front of Train", f"{arrival['platformName'].split(' ')[0]} ⚠️"), arrival['timeToStation'], arrival['platformName']
            else:
                lineName, destinationName, timeToStation, platformName = arrival['lineName'], arrival['destinationName'].replace(" Underground Station", "").replace(" DLR Station", " DLR").replace(" (H&C Line)", "").replace(" (Circle Line)", ""), arrival['timeToStation'], arrival['platformName']
            
            if lineName not in lines.keys(): lines[lineName] = {destinationName: {'platform': platformName, 'times': [timeToStation]}}
            else:
                if destinationName not in lines[lineName]: lines[lineName][destinationName] = {'platform': platformName, 'times': [timeToStation]}
                else: lines[lineName][destinationName]['times'].append(timeToStation)
        
        for line in lines.keys():
            message += f"\n<b>{line}</b>\n"
            for destination in lines[line].keys():
                formatted_times = [("Due") if (x//60 == 0) else ((str(x//60) + " mins")) for x in sorted(lines[line][destination]['times'])]
                formatted_times[0] = "<b>" + formatted_times[0] + "</b>"
                if len(formatted_times) > 3: formatted_times = formatted_times[:3]
                message += f"<b>{destination}</b> ({lines[line][destination]['platform']}): {', '.join(formatted_times)}\n"
        context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
def now_cancel(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Cancelled.", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
def clear_kb(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Cleared.", parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=ReplyKeyboardRemove())

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('now', now)],
    states={
        LOCATION: [MessageHandler(Filters.location, now_loc)],
        STATION_SELECTED: [MessageHandler(Filters.text & ~(Filters.command), now_results)]
    },
    fallbacks=[CommandHandler('cancel', now_cancel)]
)

dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CommandHandler('clearkb', clear_kb))

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
updater.idle()