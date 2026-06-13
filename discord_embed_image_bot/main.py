import discord
from discord.ext import commands
from threading import Thread
from flask import Flask
import os
import logging

# 1. Render 웹 서버 및 도배 로그 방지 설정
app = Flask('')
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


# ------------------ [1. 데이터 실시간 저장소] ------------------

# 📸 유저의 사진 대기 가이드 창 상호작용(토큰) 보관소
user_interactions = {}

# 🗺️ "임시 [손님] 역할..." 최초 에페메럴 창 상호작용 보관소
guest_interactions = {}

# 🔔 관리자 채널에 뜨는 오렌지색 예비 알림 메시지 객체 보관소
pending_admin_messages = {}


# ------------------ [2. 관리자방 독립형 [승인] 시스템] ------------------

class AdminApprovalView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="admin_approve_btn")
    async def approve_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 관리자 권한 예외 검사
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 이 버튼을 사용할 수 있습니다.", ephemeral=True)
            return

        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        guild_role = discord.utils.get(guild.roles, name="길드원")

        if not guild_role:
            await interaction.response.send_message("❌ '길드원' 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        # 2. 유저에게 길드원 역할 부여
        if member:
            await member.add_roles(guild_role)

        # 3. 한국 표준시(KST) 시간 생성
        from zoneinfo import ZoneInfo
        from datetime import datetime
        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
        time_str = kst_now.strftime('%Y-%m-%d %H:%M:%S')

        # 4. [오렌지색 알림 삭제] "🔔 신규 길드 인증 요청" 메시지 삭제
        if self.applicant_id in pending_admin_messages:
            try:
                await pending_admin_messages[self.applicant_id].delete()
            except:
                pass
            del pending_admin_messages[self.applicant_id]

        # 5. ⭐️ [옛날 방식으로의 복원 핵심] 
        # 메시지를 수정하려다 버그를 내지 않고, 기존 보라색 메시지에서 사진 파일을 다시 추출한 뒤
        # 기존 보라색 창은 완전히 삭제(delete)하고, 정갈한 초록색 창을 새로 전송(send)합니다.
        
        # 기존 메시지에 들어있는 와우 스크린샷 추출
        existing_img_url = None
        if interaction.message.embeds and interaction.message.embeds[0].image:
            existing_img_url = interaction.message.embeds[0].image.url

        # 초록색 인증 완료 박스 구성
        approved_embed = discord.Embed(
            title="🔒 인증 완료",
            description=f"{member.mention if member else '퇴장한 유저'} 님의 인증이 성공적으로 완료되었습니다.\n\n"
                        f"⚙️ **처리 관리자:** {interaction.user.mention}\n"
                        f"⏰ **인증 일시:** {time_str}\n"
                        f"👑 **부여된 직책:** [길드원]",
            color=0x2ecc71
        )
        
        # 추출한 와우 스크린샷을 초록색 박스 내부에 완벽하게 결합
        if existing_img_url:
            approved_embed.set_image(url=existing_img_url)

        # 💡 관리자용 상호작용 피드백을 주면서, 기존 보라색 메시지는 시원하게 파기하고 새 초록색 메시지를 쏩니다.
        await interaction.response.defer() # 팝업 창 안 뜨게 대기 처리
        await interaction.channel.send(embed=approved_embed) # 깔끔한 1장짜리 완료 로그 전송
        await interaction.message.delete() # 기존 보라색 버튼 메시지 영구 파기

        # 6. 유저방 청소: "임시 [손님] 역할이 부여되었습니다!..." 최초 에페메럴 가이드 창 삭제
        if self.applicant_id in guest_interactions:
            try:
                await guest_interactions[self.applicant_id].delete_original_response()
            except:
                pass
            del guest_interactions[self.applicant_id]

        # 7. 유저 사진 대기 창을 최종 완료 안내 창으로 실시간 수정
        if self.applicant_id in user_interactions:
            try:
                await user_interactions[self.applicant_id].edit_original_response(
                    content=f"🎉 {member.mention if member else ''}님께 **[길드원]** 직책이 부여되었습니다.\n"
                            f"⏰ **인증 일시:** {time_str}\n\n"
                            f"📌 이제 서버의 모든 채널을 이용하실 수 있습니다. 공지사항을 확인해 주세요! 👉 [공지사항 확인하기](https://discord.com/channels/1497469875243847680/1501555795937202187/1511718041333927940)",
                    embed=None, view=None
                )
            except:
                pass
            del user_interactions[self.applicant_id]


# ------------------ [3. 유저 진입 패널 및 버튼 이벤트 구역] ------------------

class GuestFollowUpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="길드 인증 신청", style=discord.ButtonStyle.primary, custom_id="guild_auth_btn")
    async def guild_auth(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 중복 체크
        if discord.utils.get(interaction.user.roles, name="길드원"):
            await interaction.response.send_message(content="이미 **[길드원]** 역할이 부여되었습니다!", ephemeral=True)
            return

        user_interactions[interaction.user.id] = interaction

        # 관리자 채널에 오렌지색 대기 알림 생성
        admin_channel = discord.utils.get(interaction.guild.text_channels, name="인증채널-관리자")
        if admin_channel:
            admin_embed = discord.Embed(
                title="🔔 신규 길드 인증 요청",
                description=f"{interaction.user.mention} 님이 길드 인증을 요청했습니다.\n현재 유저가 사진 업로드를 진행 중입니다.",
                color=0xe67e22
            )
            sent_msg = await admin_channel.send(embed=admin_embed)
            pending_admin_messages[interaction.user.id] = sent_msg
        
        user_embed = discord.Embed(
            title="📸 길드 인증사진 업로드 안내",
            description="왁타버스 관련 길드원이 맞는지 확인하기 위해 **인증사진**이 필요합니다.\n"
                        "**지금 현재 이 채널에 그대로 사진을 올려주세요!**\n",
            color=0x3498db
        )
        user_embed.add_field(
            name="📌 업로드 방법", 
            value="1. 길드창과 캐릭터창이 동시에 나온 사진을 캡쳐해서 올려주세요.\n"
                  "2. 사진이 올라가면 봇이 관리자에게 전달하며, 승인 시 이 안내 창이 완료 메시지로 자동 변경됩니다.\n\n"
                  "※ 원본 사진은 보안을 위해 즉시 삭제됩니다.", 
            inline=False
        )
        user_embed.set_image(url="https://message.style/cdn/images/797cb342c135ad2f3a755c479532c55a2f20db4211c751c8b0b6ccbd63d24e00.png")
        await interaction.response.send_message(embed=user_embed, ephemeral=True)


class MainWelcomeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="손님으로 입장", style=discord.ButtonStyle.secondary, custom_id="welcome_guest_btn")
    async def guest_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        guest_role = discord.utils.get(interaction.guild.roles, name="손님")
        if guest_role:
            await interaction.user.add_roles(guest_role)
            
        # 나중에 지우기 위해 손님 입장 상호작용 보관
        guest_interactions[interaction.user.id] = interaction
        
        await interaction.response.send_message(
            content="임시 **[손님]** 역할이 부여되었습니다!\n지금부터 음성채널에 참가하실 수 있습니다.\n길드원이시라면 아래 버튼을 통해 길드 인증을 이어서 진행해주세요.",
            view=GuestFollowUpView(),
            ephemeral=True
        )

    @discord.ui.button(label="버추얼로 입장", style=discord.ButtonStyle.success, custom_id="welcome_vip_btn")
    async def vip_entry(self, interaction: discord.Interaction, button: discord.ui.Button):
        if discord.utils.get(interaction.user.roles, name="버추얼"):
            await interaction.response.send_message(content="이미 **[버추얼]** 역할이 부여되었습니다!", ephemeral=True)
            return

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
            await interaction.response.send_message(content="✨ 버추얼 인증이 완료되었습니다! 공지사항을 필독해주세요.", ephemeral=True)
        else:
            await interaction.response.send_message(content="❌ '버추얼' 역할을 찾을 수 없습니다.", ephemeral=True)


# ------------------ [4. 디스코드 봇 구동 및 사진 감지 엔진] ------------------

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'봇 로그인 완료: {bot.user.name}')
    bot.add_view(MainWelcomeView())
    bot.add_view(GuestFollowUpView())

@bot.event
async def on_message(message):
    if message.author.bot: return

    if message.channel.name == "인증채널": 
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    admin_channel = discord.utils.get(message.guild.text_channels, name="인증채널-관리자")
                    if admin_channel:
                        # 파일 첨부 바이너리 복사
                        file = await attachment.to_file()
                        from zoneinfo import ZoneInfo
                        from datetime import datetime
                        kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
                        
                        # 예전 정상적이던 보라색 레이아웃 전송 구조
                        admin_embed = discord.Embed(
                            title="🖼️ 인증사진 로그 접수",
                            description=f"**신청자:** {message.author.mention}\n**일시:** {kst_now.strftime('%Y-%m-%d %H:%M:%S')}\n\n길드원이 맞다면 **[길드원]** 역할을 부여해주세요.",
                            color=0x9b59b6
                        )
                        admin_embed.set_image(url=f"attachment://{attachment.filename}")
                        
                        # 유저 화면 실시간 접수 중 문구로 교체
                        if message.author.id in user_interactions:
                            try:
                                await user_interactions[message.author.id].edit_original_response(
                                    content="✅ **인증사진 접수 완료!**\n현재 관리자가 확인 중입니다. 잠시만 기다려주세요... ⏰",
                                    embed=None, view=None
                                )
                            except: pass
                        
                        # 예전 완벽했던 방식대로 발송
                        await admin_channel.send(embed=admin_embed, file=file, view=AdminApprovalView(message.author.id))
                        await message.delete()
                        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ {ctx.author.mention}님, 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=3)
        await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def 입장패널생성(ctx):
    embed = discord.Embed(
        title="⚔️ 서버 입장 안내",
        description="방문 목적에 맞는 버튼을 눌러주세요.\n\n**• 버추얼로 입장:** [버추얼] 역할 부여\n**• 손님으로 입장:** 임시 [손님] 역할 부여",
        color=0x2ecc71
    )
    await ctx.send(embed=embed, view=MainWelcomeView())
    await ctx.message.delete()

# ------------------ [5. 봇 구동부] ------------------
keep_alive()
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
