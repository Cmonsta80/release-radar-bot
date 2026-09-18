import os
import json
import discord
from discord.ext import commands
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# -------------------------------------------------------------
# 1. Keep-Alive Web Server (Required for Render Free Web Service)
# -------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Release Radar Bot is running.")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Health check server listening on port {port}")
    server.serve_forever()

Thread(target=run_health_server, daemon=True).start()

# -------------------------------------------------------------
# 2. Google Sheets Authentication (from Environment Variable)
# -------------------------------------------------------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1deJ70gvMunU9DOBvTAqx_ekKFOJgogcMaTw-GeNomlg")
SUGGEST_CHANNEL = os.environ.get("SUGGEST_CHANNEL_NAME", "suggest-artists").lower()

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Load Google credentials from Render environment variable
creds_json_str = os.environ.get("GOOGLE_CREDS_JSON")
if not creds_json_str:
    raise ValueError("Missing GOOGLE_CREDS_JSON environment variable!")

creds_dict = json.loads(creds_json_str)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)
ss = gc.open_by_key(SPREADSHEET_ID)

followed_sheet = ss.worksheet("Followed Artists")
suggestions_sheet = ss.worksheet("Suggestions")

# -------------------------------------------------------------
# 3. Discord Bot Setup
# -------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True  # Ensure 'Message Content Intent' is enabled in Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Listening in channel: #{SUGGEST_CHANNEL}")

@bot.event
async def on_message(message):
    # Ignore messages sent by bots (prevents infinite loop with itself)
    if message.author.bot:
        return

    # Only process messages in the target suggestions channel
    if message.channel.name.lower() != SUGGEST_CHANNEL:
        return

    artist_query = message.content.strip()
    if not artist_query:
        return

    # Acknowledge with a typing indicator while checking Google Sheets
    async with message.channel.typing():
        try:
            # Check 1: Is artist in 'Followed Artists'? (Column A, skipping header)
            all_followed = followed_sheet.col_values(1)[1:]
            if any(artist_query.lower() == a.strip().lower() for a in all_followed if a):
                embed = discord.Embed(
                    title="Artist Already Tracked",
                    description=f"🎶 **{artist_query}** is already being monitored on our release tracker!",
                    color=0x3498DB
                )
                embed.set_footer(text="Release Radar • Artist Tracker")
                await message.reply(embed=embed)
                return

            # Check 2: Has artist already been suggested? (Column B in 'Suggestions')
            existing_suggestions = suggestions_sheet.col_values(2)[1:]
            if any(artist_query.lower() == s.strip().lower() for s in existing_suggestions if s):
                embed = discord.Embed(
                    title="Already in Queue",
                    description=f"⏳ **{artist_query}** has already been suggested and is currently awaiting review.",
                    color=0xF1C40F
                )
                embed.set_footer(text="Release Radar • Artist Tracker")
                await message.reply(embed=embed)
                return

            # Action: Append new row to 'Suggestions'
            # Columns: Timestamp, Suggested Artist, Submitted By (Discord User), Status, Notes
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            username = str(message.author)
            suggestions_sheet.append_row([timestamp, artist_query, username, "Pending Review", ""])

            embed = discord.Embed(
                title="Suggestion Submitted",
                description=f"✅ Thanks {message.author.mention}! **{artist_query}** has been added to our suggestion queue for review.",
                color=0x2ECC71
            )
            embed.set_footer(text="Release Radar • Artist Tracker")
            await message.reply(embed=embed)

        except Exception as e:
            print(f"Error processing suggestion: {e}")
            await message.reply("⚠️ Sorry, there was an issue logging your suggestion. Please try again later.")

# Run Discord Bot
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("Missing DISCORD_TOKEN environment variable!")

bot.run(DISCORD_TOKEN)