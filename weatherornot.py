import discord
from discord.ext import commands, tasks
from datetime import datetime
import requests
import json
import logging
import re

REPORT_SETTINGS_FILE = 'report_settings.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    with open(REPORT_SETTINGS_FILE, 'r') as file:
        report_settings = json.load(file)
        for user_id, (city, hour) in report_settings.items():
            logging.info(f"Loaded report task for user {user_id} for city {city} at {hour}")
except FileNotFoundError:
    report_settings = {}
    logging.warning("No report task settings found.")


def read_tokens(file_path='settings.json'):
    with open(file_path, 'r') as file:
        data = json.load(file)
        discord_token = data['discord_token']
        weather_api_key = data['weather_api_key']
    return discord_token, weather_api_key

discord_token, weather_api_key = read_tokens()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='/', intents=intents)

weather_emojis = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Smoke": "🌫️",
    "Haze": "🌫️",
    "Dust": "🌫️",
    "Fog": "🌫️",
    "Sand": "🌫️",
    "Ash": "🌋",
    "Squall": "🌬️",
    "Tornado": "🌪️"
}

def get_hourly_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city},fr&appid={weather_api_key}&units=metric"
    response = requests.get(url)
    data = response.json()

    if data.get('cod') == '200':
        return data
    else:
        print(f"Error fetching weather data for {city}: {data}")
        return None

def generate_weather_message(forecast, city_name):
    message = f"**Voici la météo pour les prochaines 24H à: {city_name}**\n"
    for entry in forecast:
        time = datetime.strptime(entry['dt_txt'], '%Y-%m-%d %H:%M:%S').strftime('%Hh')
        weather = entry['weather'][0]['main']
        temperature = round(entry['main']['temp'])
        emoji = weather_emojis.get(weather, '')
        
        message += f"- **`{time}`**       {emoji}       **{temperature}°C**\n"

    return message

@bot.command(name='weather')
async def weather(ctx, *city: str):
    city = ' '.join(city)
    data = get_hourly_weather(city)
    if data is None:
        await ctx.send(f"Je n'ai pas trouvé {city}.")
        return

    forecast = data['list'][:8]
    city_name = data['city']['name']
    message = generate_weather_message(forecast, city_name)

    await ctx.send(message)

@bot.command(name='report')
async def report(ctx, city: str, time: str = None):
    logging.info(f"Received report command for city {city} at time {time}")
    if city.lower() == 'cancel':
        if str(ctx.author.id) in report_settings:
            del report_settings[str(ctx.author.id)]
            await ctx.send("Très bien, j'annule le bulletin journalier.")
        else:
            await ctx.send("Pas de bulletin journalier prévu.")
    elif time is None:
        await ctx.send("Je ne comprend que le format heureHminute ou heureH (**`9h30`**, **`06h15`**, **`12h`**, **`23H32`**).")
    else:
        hour, minute = time.split('h')
        time = f"{hour.zfill(2)}h{minute.zfill(2)}"
        match = re.match(r'^(\d{1,2})h(\d{2})$', time, re.I)
        if match is None:
            await ctx.send("Invalid time format. Please use 'hourH' or 'hourHminute'.")
            return

        hour, minute = match.groups()
        if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
            await ctx.send("Temps invalide dans cette dimension.")
            return

        report_settings[str(ctx.author.id)] = (city, time)
        await ctx.send(f"Bulletin journalier activé pour {city} à {time}.")
        logging.info(f"Set up report for user {ctx.author.id} for city {city} at time {time}")

    with open(REPORT_SETTINGS_FILE, 'w') as file:
        json.dump(report_settings, file)

@tasks.loop(minutes=1)
async def send_reports():
    now = datetime.now()
    now_formatted = now.strftime('%Hh%M' if now.minute != 0 else '%Hh')
    logging.info(f"Running send_reports task at time {now_formatted}")
    for user_id, (city, time) in report_settings.items():
        logging.info(f"Checking report for user {user_id} for city {city} at time {time}")
        if now_formatted == time:
            user = bot.get_user(int(user_id))
            if user is not None:
                data = get_hourly_weather(city)
                if data is not None:
                    forecast = data['list'][:8]
                    city_name = data['city']['name']
                    message = generate_weather_message(forecast, city_name)
                    try:
                        await user.send(message)
                        logging.info(f"Sent report to user {user_id} for city {city}")
                    except Exception as e:
                        logging.error(f"Error sending message to user {user_id}: {e}")

@bot.event
async def on_ready():
    send_reports.start()
    logging.info(f"Bot is ready as {bot.user}")

bot.run(discord_token)
