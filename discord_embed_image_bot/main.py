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


# ------------------ [여기서부터 인증 시스템 클래스 삽입] ------------------

# 2단계: 손님 진입 후 에페메럴로 튀어나올 길드 인증 신청 버튼
class GuestFollowUpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="길드 인증 신청", style=discord.ButtonStyle.primary, custom_id="guild_auth_btn")
    async def guild_auth(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 관리자 전용 채널로 실시간 알림 발송
        admin_channel = discord.utils.get(interaction.guild.text_channels, name="⚙️관리자-인증방")
        
        if admin_channel:
            admin_embed = discord.Embed(
                title="🔔 신규 길드 인증 요청",
                description=f"{interaction.user.mention} (`{interaction.user.name}`) 님이 길드 인증을 요청했습니다.\n"
                            f"현재 유저에게 인증사진 업로드 안내가 전송되었습니다.",
                color=0xe67e22
            )
            await admin_channel.send(embed=admin_embed)
        
        # 2. 신청한 손님 유저에게만 보이는 에페메럴(본인 전용) 안내 메시지 및 사진 요청
        # 💡 팁: 기존에 만들어두신 티켓 사진 가이드가 있다면, 그 이미지 URL을 여기에 그대로 활용하셔도 좋습니다!
        user_embed = discord.Embed(
            title="📸 길드원 인증사진 업로드 안내",
            description="우리 길드원이 맞는지 확인하기 위해 **인증사진**이 필요합니다.\n"
                        "아래 안내에 따라 현재 화면 혹은 별도로 안내받은 채널에 사진을 올려주세요!\n",
            color=0x3498db
        )
        user_embed.add_field(
            name="📌 업로드 방법", 
            value="1. 채팅창 왼쪽의 `+` 버튼을 누릅니다.\n"
                  "2. 촬영한 **길드 가입 증명 사진**을 첨부하여 전송합니다.\n\n"
                  "※ 사진이 확인되면 관리자가 검토 후 즉시 정식 회원 역할을 부여해 드립니다.", 
            inline=False
        )
        # 필요 시 예시 사진 가이드라인 이미지가 있다면 아래에 추가 가능합니다.
        user_embed.set_image(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")

        # 유저 화면에만 연속 메시지로 띄워줌
        await interaction.response.send_message(embed=user_embed, ephemeral=True)

# 1단계: 메인 안내 채널에 박혀있을 입장 패널 버튼
class MainWelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 중요: 버튼 만료 방지

    @discord.ui.button(label="손님으로 입장", style=discord.ButtonStyle.secondary, custom_id="welcome_guest_btn")
    async def guest_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 서버에서 '손님' 역할 찾기
        guest_role = discord.utils.get(interaction.guild.roles, name="손님")
        if guest_role:
            await interaction.user.add_roles(guest_role)
        
        # 에페메럴(본인전용) 연속 메시지 및 다음 단계 버튼 출력
        await interaction.response.send_message(
            content="임시 [손님] 역할이 부여되었습니다!\n우리 길드원이시라면 아래 버튼을 눌러 정식 회원 인증을 이어서 진행해주세요.",
            view=GuestFollowUpView(),
            ephemeral=True
        )

    @discord.ui.button(label="VIP로 입장", style=discord.ButtonStyle.success, custom_id="welcome_vip_btn")
    async def vip_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 💡 리스트 대조 없이 즉시 최고 일반 역할 부여
        # '일반유저' 자리에 실제 디스코드 서버의 최고 일반 역할 이름을 적어주세요.
        vip_role = discord.utils.get(interaction.guild.roles, name="일반유저") 
        
        if vip_role:
            await interaction.user.add_roles(vip_role)
            await interaction.response.send_message(
                content="✨ VIP 인증이 완료되었습니다. 서버의 모든 권한이 활성화되었습니다!", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                content="❌ 역할을 찾을 수 없습니다. 서버 설정의 역할 이름을 확인해주세요.", 
                ephemeral=True
            )

# ------------------ [인증 시스템 클래스 끝] ------------------


# 2. 디스코드 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True # 💡 역할을 주고받기 위해 멤버 관련 인텐트 추가 활성화

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f'봇 로그인 완료: {bot.user.name}')
    
    # ⭐️ 핵심: 봇이 재시작되어도 채널에 있는 버튼들을 계속 기억하고 감시하도록 등록
    bot.add_view(MainWelcomeView())
    bot.add_view(GuestFollowUpView())


# ------------------ [추가] 관리자가 최초 1회 버튼 패널을 생성하는 명령어 ------------------
@bot.command()
@commands.has_permissions(administrator=True)
async def 입장패널생성(ctx):
    embed = discord.Embed(
        title="⚔️ 서버 입장 안내",
        description="방문 목적에 맞는 버튼을 눌러주세요.\n\n"
                    "**• VIP로 입장:** 별도의 인증 없이 일반 최고 권한이 열립니다.\n"
                    "**• 손님으로 입장:** 음성 채널만 이용 가능한 임시 역할이 부여됩니다.",
        color=0x2ecc71
    )
    # 버튼 뷰를 장착하여 전송
    await ctx.send(embed=embed, view=MainWelcomeView())
    await ctx.message.delete() # 명령어를 입력한 메시지는 깔끔하게 삭제


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


# 3. 실행부 (웹 서버를 먼저 켜고 봇을 실행)
keep_alive()

token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
