import os
import json
import urllib.request
import discord
from discord.ext import commands
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# 1. Keep-Alive Web Server for Render Free Tier
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

# 2. Configuration from Environment Variables
WEB_APP_URL = os.environ.get("WEB_APP_URL")
SUGGEST_CHANNEL = os.environ.get("SUGGEST_CHANNEL_NAME", "suggest-artists").lower()
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

if not WEB_APP_URL:
    raise ValueError("Missing WEB_APP_URL environment variable!")
if not DISCORD_TOKEN:
    raise ValueError("Missing DISCORD_TOKEN environment variable!")

# 3. Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Listening in channel: #{SUGGEST_CHANNEL}")

@bot.event
async def on_message(message):
    # Ignore messages sent by bots
    if message.author.bot:
        return

    # Only listen in the suggestions channel
    if message.channel.name.lower() != SUGGEST_CHANNEL:
        return

    artist_query = message.content.strip()
    if not artist_query:
        return

    async with message.channel.typing():
        try:
            payload = json.dumps({
                "artist": artist_query,
                "user": str(message.author)
            }).encode("utf-8")

            req = urllib.request.Request(
                WEB_APP_URL,
                data=payload,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            status = result.get("status")

            if status == "already_tracked":
                embed = discord.Embed(
                    title="Artist Already Tracked",
                    description=f"🎶 **{artist_query}** is already being monitored on our release tracker!",
                    color=0x3498DB
                )
            elif status == "already_suggested":
                embed = discord.Embed(
                    title="Already in Queue",
                    description=f"⏳ **{artist_query}** has already been suggested and is currently awaiting review.",
                    color=0xF1C40F
                )
            elif status == "added":
                embed = discord.Embed(
                    title="Suggestion Submitted",
                    description=f"✅ Thanks {message.author.mention}! **{artist_query}** has been added to our suggestion queue for review.",
                    color=0x2ECC71
                )
            else:
                embed = discord.Embed(
                    title="Notice",
                    description=f"Could not process suggestion: {result.get('message', 'Unknown response')}",
                    color=0xE74C3C
                )

            embed.set_footer(text="Release Radar • Artist Tracker")
            await message.reply(embed=embed)

        except Exception as e:
            print(f"Error calling Apps Script Web App: {e}")
            await message.reply("⚠️ Sorry, there was an issue logging your suggestion. Please try again.")

bot.run(DISCORD_TOKEN)
