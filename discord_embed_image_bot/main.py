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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ------------------ [1. 인증 시스템 버튼 클래스 구역] ------------------

# 2단계: 손님 진입 후 에페메럴로 튀어나올 길드 인증 신청 버튼
class GuestFollowUpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="길드 인증 신청", style=discord.ButtonStyle.primary, custom_id="guild_auth_btn")
    async def guild_auth(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ⚠️ 중요: 관리자 알림 및 사진 로그가 찍힐 채널명을 정확히 적어주세요.
        admin_channel = discord.utils.get(interaction.guild.text_channels, name="⚙️관리자-인증방")
        
        if admin_channel:
            admin_embed = discord.Embed(
                title="🔔 신규 길드 인증 요청",
                description=f"{interaction.user.mention} (`{interaction.user.name}`) 님이 길드 인증을 요청했습니다.\n"
                            f"현재 유저에게 인증사진 업로드 안내가 전송되었습니다.",
                color=0xe67e22
            )
            await admin_channel.send(embed=admin_embed)
        
        user_embed = discord.Embed(
            title="📸 길드원 인증사진 업로드 안내",
            description="우리 길드원이 맞는지 확인하기 위해 **인증사진**이 필요합니다.\n"
                        "현재 이 채널에 그대로 사진을 올려주시면 관리자방으로 안전하게 전송됩니다!\n",
            color=0x3498db
        )
        user_embed.add_field(
            name="📌 업로드 방법", 
            value="1. 채팅창 왼쪽의 `+` 버튼을 누릅니다.\n"
                  "2. 촬영한 **길드 가입 증명 사진**을 첨부하여 전송합니다.\n\n"
                  "※ 사진이 전송되면 봇이 자동으로 수집하며, 채널 보호를 위해 원본 사진은 잠시 후 삭제됩니다.", 
            inline=False
        )
        user_embed.set_image(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")

        await interaction.response.send_message(embed=user_embed, ephemeral=True)


# 1단계: 메인 안내 채널에 박혀있을 입장 패널 버튼
class MainWelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="손님으로 입장", style=discord.ButtonStyle.secondary, custom_id="welcome_guest_btn")
    async def guest_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # '손님' 역할 자동 부여
        guest_role = discord.utils.get(interaction.guild.roles, name="손님")
        if guest_role:
            await interaction.user.add_roles(guest_role)
        
        await interaction.response.send_message(
            content="임시 **[손님]** 역할이 부여되었습니다!\n우리 길드원이시라면 아래 버튼을 눌러 정식 회원 인증을 이어서 진행해주세요.",
            view=GuestFollowUpView(),
            ephemeral=True
        )

    @discord.ui.button(label="VIP로 입장", style=discord.ButtonStyle.success, custom_id="welcome_vip_btn")
    async def vip_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1등 역할인 '버추얼' 역할 즉시 부여
        vip_role = discord.utils.get(interaction.guild.roles, name="버추얼") 
        
        if vip_role:
            await interaction.user.add_roles(vip_role)
            await interaction.response.send_message(content="✨ VIP 인증이 완료되었습니다. **[버추얼]** 역할의 모든 권한이 활성화되었습니다!", ephemeral=True)
        else:
            await interaction.response.send_message(content="❌ '버추얼' 역할을 찾을 수 없습니다. 서버 설정의 역할 이름을 확인해주세요.", ephemeral=True)


# ------------------ [2. 디스코드 봇 기본 설정] ------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)


# ------------------ [3. 봇 이벤트 및 감지 로직 구역] ------------------

@bot.event
async def on_ready():
    print(f'봇 로그인 완료: {bot.user.name}')
    bot.add_view(MainWelcomeView())
    bot.add_view(GuestFollowUpView())


# 손님이 올린 인증사진을 감지해서 관리자방으로 배달하는 로그 시스템 (수정본)
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # ⚠️ 중요: 실제 사진을 올릴 대기방 채널명과 일치하는지 꼭 확인하세요.
    if message.channel.name == "인증채널": 
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    
                    admin_channel = discord.utils.get(message.guild.text_channels, name="⚙️관리자-인증방")
                    if admin_channel:
                        # 1. 원본 파일 데이터를 봇이 임시로 변환하여 들고 옵니다.
                        file = await attachment.to_file()
                        
                        # 2. 관리자 방에 보낼 이쁜 임베드를 만듭니다.
                        admin_embed = discord.Embed(
                            title="🖼️ 인증사진 로그 접수",
                            description=f"**신청자:** {message.author.mention} (`{message.author.name}`)\n"
                                        f"**일시:** {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                        f"정식 길드원이 맞다면 수동으로 **[길드원]** 역할을 부여해주세요.",
                            color=0x9b59b6
                        )
                        # 💡 핵심: 첨부한 파일 이름을 임베드 이미지로 지정합니다.
                        admin_embed.set_image(url=f"attachment://{attachment.filename}")
                        
                        # 3. 임베드와 실제 파일 데이터를 '동시에' 관리자 채널로 전송합니다.
                        # 이렇게 하면 관리자 채널 자체에 파일이 저장되므로 원본이 지워져도 깨지지 않습니다.
                        await admin_channel.send(embed=admin_embed, file=file)
                        
                        # 4. 유저 채널의 원본 사진은 예정대로 깔끔하게 삭제 (채널 청결 유지)
                        await message.delete(delay=2)
                        await message.channel.send(f"✅ {message.author.mention}님, 사진이 관리자에게 안전하게 전달되었습니다!", delete_after=5)
                        return

    await bot.process_commands(message)


# 기존에 사용하시던 티켓 채널 감지 이벤트 (그대로 유지)
@bot.event
async def on_guild_channel_create(channel):
    if isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-"):
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
        embed1.set_image(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")

        embed2 = discord.Embed(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")
        embed2.set_image(url="https://message.style/cdn/images/f625a312aa1c5e6cb63dc27b8faa1908c4a3a7abea3b12a3bcfec6619e9b6579.png")

        await channel.send(embeds=[embed1, embed2])


# 일반 유저가 명령어 입력 시 권한 부족 경고 에러 처리 이벤트
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ {ctx.author.mention}님, 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=3)
        await ctx.message.delete()


# ------------------ [4. 관리자 명령어 구역] ------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def 입장패널생성(ctx):
    embed = discord.Embed(
        title="⚔️ 서버 입장 안내",
        description="방문 목적에 맞는 버튼을 눌러주세요.\n\n"
                    "**• VIP로 입장:** 아무 인증 없이 가장 높은 [버추얼] 역할이 부여됩니다.\n"
                    "**• 손님으로 입장:** 음성 채널만 이용 가능한 임시 [손님] 역할이 부여됩니다.",
        color=0x2ecc71
    )
    await ctx.send(embed=embed, view=MainWelcomeView())
    await ctx.message.delete()


# ------------------ [5. 봇 구동부] ------------------
keep_alive()

token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
