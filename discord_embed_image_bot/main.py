import discord
from discord.ext import commands
from threading import Thread
from flask import Flask
import os
import logging  # 🔒 도배 로그 방지를 위해 로깅 모듈 추가

# 1. Render 호환을 위한 가짜 웹 서버(Flask) 설정
app = Flask('')

# 🔒 UptimeRobot이 찌르는 무의미한 웹 접속 로그(Werkzeug) 숨기기
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()


# ------------------ [1. 인증 시스템 및 에페메럴 연동 구역] ------------------

# 유저가 버튼을 누른 상호작용(토큰)을 잠시 보관하는 저장소
user_interactions = {}


# 🆕 [추가] 관리자방 로그 밑에 달릴 [승인] 버튼 클래스
class AdminApprovalView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id # 사진을 올린 유저의 ID를 기억

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="admin_approve_btn")
    async def approve_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼을 누른 사람이 관리자 권한이 있는지 검사
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 이 버튼을 사용할 수 있습니다.", ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(self.applicant_id) # 사진을 올렸던 유저 찾기
        guild_role = discord.utils.get(guild.roles, name="길드원")

        if not guild_role:
            await interaction.response.send_message("❌ '길드원' 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        # 1. 유저에게 길드원 역할 부여
        if member:
            await member.add_roles(guild_role)

        # 2. 한국 표준시(KST) 시간 생성
        from zoneinfo import ZoneInfo
        from datetime import datetime
        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
        time_str = kst_now.strftime('%Y-%m-%d %H:%M:%S')

        # 3. ⭐️ [박제 로그] 관리자가 보는 로그 창을 "어떤 관리자가 승인했는지" 실시간으로 수정(Edit)
        approved_embed = discord.Embed(
            title="🔒 인증 완료",
            description=f"{member.mention if member else '퇴장한 유저'} 님의 인증이 성공적으로 완료되었습니다.\n\n"
                        f"⚙️ **처리 관리자:** {interaction.user.mention}\n"
                        f"⏰ **인증 일시:** {time_str}\n"
                        f"👑 **부여된 직책:** [길드원]",
            color=0x2ecc71 # 완료를 뜻하는 초록색으로 변환
        )
        # 유저가 제출했던 인증샷 이미지 깨지지 않게 그대로 유지
        if interaction.message.embeds and interaction.message.embeds[0].image:
            approved_embed.set_image(url=interaction.message.embeds[0].image.url)

        # 관리자 채널의 메시지를 업데이트 (버튼은 처리가 끝났으므로 소멸)
        await interaction.message.edit(embed=approved_embed, view=None)

        # 4. 동시에 유저가 보고 있던 에페메럴 가이드 창도 승인 완료 창으로 실시간 업데이트
        if self.applicant_id in user_interactions:
            saved_interaction = user_interactions[self.applicant_id]
            try:
                await saved_interaction.edit_original_response(
                    content=f"🎉 {member.mention if member else ''}님, 축하합니다!\n"
                            f"**{interaction.user.mention}(관리자)**님이 회원님의 인증을 확인하고 **[길드원]** 직책을 부여했습니다.\n"
                            f"⏰ **인증 일시:** {time_str}\n\n"
                            f"📌 이제 서버의 모든 채널을 이용하실 수 있습니다. 공지사항을 다시 확인해 주세요! 👉 [공지사항 확인하기](https://discord.com/channels/1497469875243847680/1501555795937202187/1511718041333927940)",
                    embed=None,
                    view=None
                )
            except Exception as e:
                print(f"유저 에페메럴 창 원격 수정 실패: {e}")
            
            del user_interactions[self.applicant_id]

        # 버튼을 누른 관리자 본인에게 성공 피드백 알림
        await interaction.response.send_message(f"✅ 승인 처리가 완료되었습니다.", ephemeral=True)


# 2단계: 손님 진입 후 에페메럴로 튀어나올 길드 인증 신청 버튼
class GuestFollowUpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="길드 인증 신청", style=discord.ButtonStyle.primary, custom_id="guild_auth_btn")
    async def guild_auth(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_interactions[interaction.user.id] = interaction

        admin_channel = discord.utils.get(interaction.guild.text_channels, name="인증채널-관리자")
        
        if admin_channel:
            admin_embed = discord.Embed(
                title="🔔 신규 길드 인증 요청",
                description=f"{interaction.user.mention} 님이 길드 인증을 요청했습니다.\n"
                            f"현재 유저가 사진 업로드를 진행 중입니다.",
                color=0xe67e22
            )
            await admin_channel.send(embed=admin_embed)
        
        user_embed = discord.Embed(
            title="📸 길드 인증사진 업로드 안내",
            description="왁타버스 관련 길드원이 맞는지 확인하기 위해 **인증사진**이 필요합니다.\n"
                        "**지금 현재 이 채널에 그대로 사진을 올려주세요!**\n",
            color=0x3498db
        )
        user_embed.add_field(
            name="📌 업로드 방법", 
            value="1. 아래의 예시 사진과 같이 길드창과 캐릭터창이 동시에 나온 사진을 캡쳐해서 올려주세요.\n"
                  "2. 사진이 올라가면 봇이 감지하여 이 안내 창을 성공 메시지로 변경합니다.\n\n"
                  "※ 채널 보안을 위해 유저님이 올리신 원본 사진은 즉시 삭제됩니다.", 
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
        guest_role = discord.utils.get(interaction.guild.roles, name="손님")
        if guest_role:
            await interaction.user.add_roles(guest_role)
        
        await interaction.response.send_message(
            content=" 임시 **[손님]** 역할이 부여되었습니다!\n 지금부터 음성채널에 참가하실 수 있습니다.\n 길드원이시라면 아래 버튼을 통해 길드 인증을 이어서 진행해주세요.",
            view=GuestFollowUpView(),
            ephemeral=True
        )

    @discord.ui.button(label="버추얼로 입장", style=discord.ButtonStyle.success, custom_id="welcome_vip_btn")
    async def vip_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        vip_role = discord.utils.get(interaction.guild.roles, name="버추얼") 
        
        if vip_role:
            await interaction.user.add_roles(vip_role)
            
            admin_channel = discord.utils.get(interaction.guild.text_channels, name="인증채널-관리자")
            if admin_channel:
                from zoneinfo import ZoneInfo
                from datetime import datetime
                kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
                
                admin_embed = discord.Embed(
                    title="👑 버추얼 역할 부여 알림",
                    description=f"{interaction.user.mention} 님이 **[버추얼로 입장]** 버튼을 눌러 **[버추얼]** 역할이 자동으로 부여되었습니다.",
                    color=0xe91e63 
                )
                admin_embed.set_footer(text=f"일시: {kst_now.strftime('%Y-%m-%d %H:%M:%S')}")
                await admin_channel.send(embed=admin_embed)
            
            await interaction.response.send_message(content="✨ 버추얼 인증이 완료되었습니다. **[버추얼]** 역할의 모든 권한이 활성화되었습니다! \n\n서버 공지사항을 필독해주세요! 👉 [공지사항 확인하기](https://discord.com/channels/1497469875243847680/1501555795937202187/1511718041333927940)", ephemeral=True)
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


# 사진 수집 시 관리자방 로그에 [승인] 버튼 뷰를 장착하여 전송하는 구역
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name == "인증채널": 
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    
                    admin_channel = discord.utils.get(message.guild.text_channels, name="인증채널-관리자")
                    if admin_channel:
                        file = await attachment.to_file()
                        
                        from zoneinfo import ZoneInfo
                        from datetime import datetime
                        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
                        
                        admin_embed = discord.Embed(
                            title="🖼️ 인증사진 로그 접수",
                            description=f"**신청자:** {message.author.mention}\n"
                                        f"**일시:** {kst_now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                        f"사진을 확인하신 후 아래 **[승인]** 버튼을 눌러주세요.",
                            color=0x9b59b6
                        )
                        admin_embed.set_image(url=f"attachment://{attachment.filename}")
                        
                        # 💡 [합체 완료] view=AdminApprovalView(...) 옵션을 추가해 로그 밑에 승인 버튼을 붙여 보냅니다.
                        await admin_channel.send(embed=admin_embed, file=file, view=AdminApprovalView(message.author.id))
                        
                        await message.delete()
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
                    "**• 버추얼로 입장:** [버추얼] 역할이 부여됩니다.\n"
                    "**• 손님으로 입장:** 음성 채널만 이용 가능한 임시 [손님] 역할이 부여됩니다.",
        color=0x2ecc71
    )
    await ctx.send(embed=embed, view=MainWelcomeView())
    await ctx.message.delete()


# ------------------ [5. 봇 구동부] ------------------
keep_alive()

token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
