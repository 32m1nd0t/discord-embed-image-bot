import discord
from discord.ext import commands
from threading import Thread
from flask import Flask
import os

# 1. Render 호환을 위한 가짜 웹 서버(Flask) 설정
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Render는 포트(PORT)를 지정해주어야 하므로 환경변수에서 가져옴
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. 디스코드 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'봇 로그인 완료: {bot.user.name}')

@bot.event
async def on_guild_channel_create(channel):
    if isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-"):
        embed = discord.Embed(
            title="📸 인증 사진 업로드 안내",
            description="티켓이 정상적으로 접수되었습니다.\n아래 안내에 따라 인증 사진을 올려주세요!",
            color=0x3498db
        )
        embed.add_field(
            name="📌 업로드 방법", 
            value="1. 채팅창 왼쪽의 `+` 버튼을 누릅니다.\n2. 촬영한 인증 사진을 첨부합니다.\n3. 사진과 함께 필요한 정보를 적어 전송합니다.", 
            inline=False
        )
        # 이미지 URL이 있다면 아래 주석을 풀고 넣으세요
        # embed.set_image(url="여러분의_이미지_주소")
        await channel.send(embed=embed)

# 3. 실행부 (웹 서버를 먼저 켜고 봇을 실행)
keep_alive()

# 토큰은 보안을 위해 Render 환경변수에서 불러오도록 설정
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
