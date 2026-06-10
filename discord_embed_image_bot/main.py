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
        # 1. 메인 임베드 (텍스트 안내문 + 첫 번째 사진)
        embed1 = discord.Embed(
            title="📸 인증 사진 업로드 안내",
            description="티켓이 정상적으로 접수되었습니다.\n아래 안내에 따라 인증 사진을 올려주세요!\n",
            color=0x3498db
        )
        embed1.add_field(
            name="📌 업로드 방법", 
            value="1. 채팅창 왼쪽의 `+` 버튼을 누릅니다.\n2. 촬영한 인증 사진을 첨부합니다.", 
            inline=False
        )
        # 첫 번째 이미지 URL 설정
        embed1.set_image(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")

        # 2. 서브 임베드 (텍스트 없이 두 번째 사진만 담음)
        # ⚠️ 중요: 메인 임베드와 완전히 '동일한 URL 주소'를 적어줘야 한 묶음으로 인식해!
        embed2 = discord.Embed(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")
        
        # 두 번째 이미지 URL 설정
        embed2.set_image(url="https://message.style/cdn/images/f625a312aa1c5e6cb63dc27b8faa1908c4a3a7abea3b12a3bcfec6619e9b6579.png")

        # 3. 두 임베드를 리스트로 묶어서 단 '한 번만' 전송!
        await channel.send(embeds=[embed1, embed2])

# 3. 실행부 (웹 서버를 먼저 켜고 봇을 실행)
keep_alive()

# 토큰은 보안을 위해 Render 환경변수에서 불러오도록 설정
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
