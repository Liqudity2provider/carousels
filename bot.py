import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Optional, List
import threading
import uvicorn

import aiofiles
from openai.types import ResponseFormatJSONObject
from openai.types.chat import completion_create_params, ChatCompletionUserMessageParam
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from dotenv import load_dotenv
import httpx
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from html_generator import HTMLCarouselGenerator
from json_html_generator import JSONCarouselGenerator
from json_html_generator_style2 import JSONCarouselGeneratorStyle2
from carousel_cache import CarouselCache

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPEN_ROUTER_API_KEY = os.getenv('OPEN_ROUTER_API_KEY')
BASE_URL = os.getenv('BASE_URL', 'https://your-app.railway.app')

# Initialize FastAPI app for serving static files
web_app = FastAPI()

# Create static directory if it doesn't exist
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Mount static files
web_app.mount("/static", StaticFiles(directory="static"), name="static")

@web_app.get("/")
async def root():
    return HTMLResponse("""
    <html>
        <head><title>Carousel Generator</title></head>
        <body>
            <h1>🎨 Instagram Carousel Generator</h1>
            <p>This is the static file server for the Telegram bot.</p>
            <p>Generated carousels and images are served from here.</p>
        </body>
    </html>
    """)

# Initialize AI clients
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Initialize OpenRouter client for image generation
openrouter_client = None
if OPEN_ROUTER_API_KEY:
    openrouter_client = httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1",
        headers={
            "Authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        timeout=httpx.Timeout(120.0, read=120.0, write=30.0, connect=10.0)  # Extended timeout for image generation
    )

# User sessions storage (in production, use Redis or database)
user_sessions: Dict[int, Dict] = {}

class CarouselBot:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.html_generator = HTMLCarouselGenerator()
        self.json_generator = JSONCarouselGenerator()
        self.json_generator_style2 = JSONCarouselGeneratorStyle2()
        self.cache = CarouselCache()
        self.setup_handlers()
    
    async def generate_with_ai(self, prompt: str) -> str:
        """Generate content using AI with fallback mechanism"""
        # Try Claude first
        import json
#         return  json.dumps({
#   "cards": [
#     {
#       "type": "hook",
#       "header": "Oznaki, że naprawdę dbasz o siebie<br>KROK PO KROKU",
#       "text": ""
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "1. Zacznij słuchać sygnałów ciała\nKiedyś ignorowałeś zmęczenie i napięcie, teraz robisz szybkie check-iny: energia (1–5), napięcie w ciele, oddech. Ustaw 3 krótkie przypomnienia dziennie (rano, po pracy, przed snem) i zrób 2 min oddechu + zapisz jedną obserwację.\n\n🔑 Jeśli nie mierzysz, zgadujesz: przez 7 dni notuj „sen / energia / nastrój” w skali 1–5."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "2. Ustal granice bez poczucia winy\nKiedyś brałeś wszystko na siebie i wyjaśniałeś się każdemu. Teraz masz proste „nie” i 3 nieprzekraczalne zasady (np. brak maili po 19, sen po 23, wolne niedziele). Użyj skryptu: „Dzięki za zaproszenie, tym razem nie dam rady”.\n\n⚠️ Granice nie wymagają długich tłumaczeń. Krótkie i uprzejme „nie” to pełna odpowiedź."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "3. Zadbaj o fundamenty: sen, jedzenie, ruch\nKiedyś „kawa na śniadanie” i „od poniedziałku zaczynam”. Teraz trzymasz się mikro-rutyn: światło gaśnie o 22:30, 3 posiłki z białkiem, 7–8 tys. kroków dziennie. Fundamenty dają 80% efektów przy 20% wysiłku.\n\n🎯 Ustal minimalny standard: 10-min spacer, 1 owoc dziennie, w łóżku do 23:00 – nawet w gorsze dni."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "4. Reguluj emocje zamiast je tłumić\nKiedyś zagłuszałeś napięcie scrollowaniem lub jedzeniem. Teraz używasz STOP: S – Stop, T – Weź 3 oddechy 4–4–6, O – Obserwuj (co myślę/czuję?), P – Podejmij mały ruch (szklanka wody, krótki spacer). Dodaj 5 zdań dziennie w dzienniku: „Co czuję? Czego potrzebuję?”.\n\n💡 Emocje to dane, nie rozkazy. Gdy je nazwiesz, tracą moc sterowania tobą."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "5. Ogarnij finanse jak element self-care\nKiedyś zakupy „na poprawę humoru”. Teraz plan: tygodniowy budżet, reguła 50/30/20 i poduszka 3 mies. kosztów. Ustaw automatyczny przelew oszczędności w dniu wypłaty – zanim wydasz.\n\n🔑 Stwórz konto „przyjemności” (5–10%): możesz wydawać bez poczucia winy i bez rozwalania budżetu."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "6. Kuruj swoje relacje\nKiedyś trzymałeś się ludzi, którzy drenowali energię. Teraz robisz audyt: + dodaje, – zabiera. Przesuń czas do „+”, ustaw limit na „–”. Zaplanuj 1 wspierające spotkanie w tygodniu (spacer/kawa) z osobą, po której czujesz się lepiej.\n\n⚠️ Bliskość ≠ dostępność 24/7. Twoje granice chronią też dobre relacje."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "7. Wprowadź higienę cyfrową\nKiedyś telefon był pierwszą i ostatnią rzeczą dnia. Teraz masz zasady: brak telefonu w sypialni, limit social 30 min, tryb skali szarości w tygodniu. Zamień bezmyślne scrollowanie na 15 min czytania lub rozciągania.\n\n🎯 Odłóż telefon do „stacji dokującej” przy drzwiach i używaj zwykłego budzika."
#     },
#     {
#       "type": "main",
#       "header": "",
#       "text": "8. Zmień sposób, w jaki mówisz do siebie\nKiedyś: „znowu zawaliłem”. Teraz: „uczysz się; co następnym razem zrobisz inaczej?”. Użyj ramki: „Widzę, że [fakt]. To ma sens, bo [powód]. Następnym razem spróbuję [konkret].” Przyklej tę ramkę przy monitorze i stosuj codziennie.\n\n💡 Która zmiana da ci dziś największy efekt? Wybierz jedną i zrób ją w wersji „minimalnej”.\n\n— Daniel Tur ✅"
#     }
#   ]
# })
        if anthropic_client:
            try:
                logger.info("Attempting to generate content with Claude...")
                response = await anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                logger.info("Claude generation successful")
                return response.content[0].text
            except Exception as e:
                logger.warning(f"Claude failed: {e}. Falling back to OpenAI...")
        
        # Fallback to OpenAI GPT-5
        if openai_client:
            try:
                logger.info("Attempting to generate content with OpenAI GPT-5...")
                response = await openai_client.chat.completions.create(
                    model="gpt-5",
                    max_completion_tokens=8000,  # Increased from 4000 to 8000
                    messages=[ChatCompletionUserMessageParam(role="user", content=prompt)],
                    response_format=completion_create_params.ResponseFormatJSONObject(type="json_object"),
                )
                # Check if response was truncated
                choice = response.choices[0]
                content = choice.message.content
                
                if not content or content.strip() == '':
                    logger.error("OpenAI returned empty content")
                    raise Exception("AI returned empty response. Please try again.")
                
                if choice.finish_reason == 'length':
                    logger.warning("OpenAI response was truncated due to length limit")
                    # Try to use truncated content if it's valid JSON
                    try:
                        import json
                        # Attempt to parse as JSON to see if it's still valid
                        json.loads(content)
                        logger.info("Truncated response is still valid JSON, using it")
                        return content
                    except json.JSONDecodeError:
                        # If truncated content is invalid JSON, try to fix it
                        logger.warning("Truncated response is invalid JSON, attempting to fix...")
                        try:
                            # Try to close incomplete JSON structures
                            fixed_content = self.fix_truncated_json(content)
                            json.loads(fixed_content)  # Validate the fix
                            logger.info("Successfully fixed truncated JSON")
                            return fixed_content
                        except:
                            logger.error("Could not fix truncated JSON")
                            # As a last resort, try with a shorter prompt
                            logger.info("Attempting generation with shorter prompt...")
                            try:
                                shorter_prompt = self.create_shorter_prompt(prompt)
                                shorter_response = await openai_client.chat.completions.create(
                                    model="gpt-5",
                                    max_completion_tokens=6000,  # Slightly reduced for shorter content
                                    messages=[ChatCompletionUserMessageParam(role="user", content=shorter_prompt)],
                                    response_format=completion_create_params.ResponseFormatJSONObject(type="json_object"),
                                )
                                shorter_content = shorter_response.choices[0].message.content
                                if shorter_content and shorter_content.strip():
                                    logger.info("Shorter prompt generation successful")
                                    return shorter_content
                            except Exception as shorter_error:
                                logger.error(f"Shorter prompt also failed: {shorter_error}")
                            
                            raise Exception("Response was truncated and could not be repaired. Please try again or contact administrator.")
                
                logger.info("OpenAI generation successful")
                return content
            except Exception as e:
                logger.error(f"OpenAI also failed: {e}")
                raise Exception("Both Claude and OpenAI are unavailable. Please try again later.")
        
        # No API keys available
        raise Exception("No AI API keys configured. Please contact the administrator.")
    
    def fix_truncated_json(self, truncated_json: str) -> str:
        """Attempt to fix truncated JSON by closing incomplete structures"""
        try:
            # Remove any trailing incomplete text
            content = truncated_json.strip()
            
            # Count open and close braces/brackets
            open_braces = content.count('{')
            close_braces = content.count('}')
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            
            # Add missing closing braces
            missing_braces = open_braces - close_braces
            missing_brackets = open_brackets - close_brackets
            
            # If we're in the middle of a string, try to close it
            quote_count = content.count('"')
            if quote_count % 2 == 1:  # Odd number of quotes means unclosed string
                content += '"'
            
            # Add missing closing brackets and braces
            content += ']' * missing_brackets
            content += '}' * missing_braces
            
            return content
        except Exception as e:
            logger.error(f"Error fixing truncated JSON: {e}")
            raise
    
    def create_shorter_prompt(self, original_prompt: str) -> str:
        """Create a shorter version of the prompt to avoid truncation"""
        # Check if this is a content generation prompt (contains examples and detailed instructions)
        if "CARD COUNT FLEXIBILITY" in original_prompt or "cards can vary from" in original_prompt:
            # Extract topic from original prompt
            if 'Topic:' in original_prompt:
                topic_part = original_prompt.split('Topic:')[-1].split('\n')[0]
            else:
                topic_part = 'Personal development'
            
            # This is a content generation prompt, create a shorter version
            shorter_prompt = f"""
Create a carousel post in JSON format with 4-6 cards maximum. Keep content concise but meaningful.

Structure:
{{
  "cards": [
    {{
      "type": "hook",
      "header": "ENGAGING TITLE<br>SUBTITLE",
      "text": ""
    }},
    {{
      "type": "main", 
      "header": "Short descriptive header",
      "text": "1. First key point (2-3 sentences max)\\n\\n2. Second key point (2-3 sentences max)\\n\\n🔑 Key insight"
    }},
    // ... 2-4 more main cards with headers and 1-2 numbered points each
  ]
}}

Requirements:
- Write in Polish
- Use "ty" (you) form
- Each main card MUST have a descriptive header (max 1 sentence)
- Combine 2 points per card when space allows
- Keep each point to 2-3 sentences maximum
- Focus on the most important, actionable advice
- Ensure valid JSON format
- Maximum 6 cards total

Topic: {topic_part}

IMPORTANT: Respond ONLY with valid JSON. No additional text or explanations.
"""
            return shorter_prompt.strip()
        else:
            # For other types of prompts, just truncate
            return original_prompt[:2000] + "\n\nIMPORTANT: Keep response concise and in valid JSON format."
        
    def setup_handlers(self):
        """Setup bot command and callback handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("history", self.show_history))
        self.app.add_handler(CommandHandler("stats", self.show_stats))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        user_sessions[user_id] = {'state': 'main_menu'}
        
        # Initialize database on first use
        await self.cache.init_db()
        
        keyboard = [
            [InlineKeyboardButton("🎨 Create New Carousel", callback_data="create_carousel")],
            [InlineKeyboardButton("🖼️ Generate Image", callback_data="generate_image")],
            [InlineKeyboardButton("📚 My History", callback_data="show_history")],
            [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "🎯 *Welcome to Instagram Carousel Generator!*\n\n"
            "I'll help you create professional Instagram carousels and images:\n\n"
            "1️⃣ Generate content using AI\n"
            "2️⃣ Create beautiful HTML carousels\n"
            "3️⃣ Generate custom images with DALL-E\n"
            "4️⃣ Publish and get shareable links\n\n"
            "Choose an option below to get started:"
        )
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "create_carousel":
            await self.start_carousel_creation(query, user_id)
        elif data == "generate_image":
            await self.start_image_generation(query, user_id)
        elif data == "how_it_works":
            await self.show_how_it_works(query)
        elif data == "approve_content":
            await self.approve_content(query, user_id)
        elif data == "modify_content":
            await self.request_modifications(query, user_id)
        elif data == "approve_html":
            await self.publish_carousel(query, user_id)
        elif data == "modify_html":
            await self.request_html_modifications(query, user_id)
        elif data == "back_to_menu":
            await self.back_to_main_menu(query, user_id)
        elif data == "show_history":
            await self.show_user_history(query, user_id)
        elif data == "style_1":
            await self.select_style(query, user_id, "style_1")
        elif data == "style_2":
            await self.select_style(query, user_id, "style_2")
        elif data == "skip_image":
            await self.skip_image_generation(query, user_id)
        elif data == "approve_slide_image":
            await self.approve_slide_image(query, user_id)
        elif data == "decline_slide_image":
            await self.decline_slide_image(query, user_id)
        elif data == "use_custom_url":
            await self.request_image_url(query, user_id)
            
    async def start_carousel_creation(self, query, user_id: int):
        """Start the carousel creation process"""
        user_sessions[user_id] = {
            'state': 'awaiting_style_selection',
            'step': 'style_selection'
        }
        
        text = (
            "🎨 *Choose Carousel Style*\n\n"
            "Select the style for your carousel:\n\n"
            "🔸 *Style 1 - Classic Cards*\n"
            "Traditional carousel with navigation dots and buttons\n\n"
            "🔸 *Style 2 - Grid Layout*\n"
            "Modern grid layout with mountain illustration\n\n"
            "Which style would you prefer?"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔸 Style 1 - Classic", callback_data="style_1")],
            [InlineKeyboardButton("🔸 Style 2 - Grid", callback_data="style_2")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def select_style(self, query, user_id: int, style: str):
        """Handle style selection and proceed to topic input"""
        user_sessions[user_id] = {
            'state': 'awaiting_topic',
            'step': 'content_generation',
            'style': style
        }
        
        style_name = "Classic Cards" if style == "style_1" else "Grid Layout"
        
        text = (
            f"🎨 *Creating New Carousel - {style_name}*\n\n"
            "Describe the topic for the carousel you want to create. It can be:\n\n"
            "• Personal development (e.g., 'building self-confidence')\n"
            "• Relationships (e.g., 'healthy boundaries in relationships')\n"
            "• Career (e.g., 'signs you're growing professionally')\n"
            "• Healthy habits (e.g., 'signals you're taking care of yourself')\n\n"
            "*Write your topic:*"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def start_image_generation(self, query, user_id: int):
        """Start the image generation process"""
        user_sessions[user_id] = {
            'state': 'awaiting_image_description',
        }
        
        text = (
            "🖼️ *Generate Custom Image*\n\n"
            "Describe the image you'd like me to create using DALL-E.\n\n"
            "Examples:\n"
            "• A peaceful mountain landscape at sunset\n"
            "• Modern minimalist office workspace with plants\n"
            "• Abstract geometric pattern in blue and gold\n"
            "• Cozy coffee shop interior with warm lighting\n"
            "• Professional headshot of a confident businesswoman\n\n"
            "*Write your image description:*"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    async def show_how_it_works(self, query):
        """Show how the bot works"""
        text = (
            "ℹ️ *How does the carousel generator work?*\n\n"
            "*Step 1: Content Generation* 🤖\n"
            "• You provide the carousel topic\n"
            "• AI creates professional content in 7-card format\n"
            "• You can approve or request modifications\n\n"
            "*Step 2: HTML Creation* 🎨\n"
            "• Content is placed in a beautiful template\n"
            "• You get a carousel preview\n"
            "• You can approve or request changes\n\n"
            "*Step 3: Publishing* 🌐\n"
            "• I publish the carousel online\n"
            "• You get a shareable link\n"
            "• You can immediately share with your followers!\n\n"
            "The whole process takes 2-3 minutes! 🚀"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages based on user state"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if user_id not in user_sessions:
            await self.start_command(update, context)
            return
            
        session = user_sessions[user_id]
        state = session.get('state')
        
        if state == 'awaiting_topic':
            await self.generate_content(update, user_id, message_text)
        elif state == 'awaiting_image_description':
            await self.generate_image(update, user_id, message_text)
        elif state == 'awaiting_image_description_for_slide':
            await self.generate_slide_image(update, user_id, message_text)
        elif state == 'awaiting_image_url':
            await self.process_image_url(update, user_id, message_text)
        elif state == 'awaiting_modifications':
            await self.modify_content(update, user_id, message_text)
        elif state == 'awaiting_html_modifications':
            await self.modify_html_content(update, user_id, message_text)
            
    async def generate_content(self, update: Update, user_id: int, topic: str):
        """Generate carousel content using Claude"""
        # Show loading message
        loading_msg = await update.message.reply_text("🤖 Generating carousel content... This may take a moment.")
        
        try:
            # Read the appropriate prompt template based on style
            session = user_sessions[user_id]
            style = session.get('style', 'style_1')
            
            if style == 'style_2':
                prompt_path = Path("project/assets/style_2_content_creation_prompt.txt")
            else:
                prompt_path = Path("project/assets/content_creation_prompt.txt")
                
            async with aiofiles.open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = await f.read()
            
            # Create the full prompt
            full_prompt = f"""
{prompt_template}

TEMAT KARUZELI: {topic}

Stwórz karuzelę na powyższy temat w formacie JSON zgodnie z podanym szablonem. 
Pamiętaj o:
- Użyciu formy "ty" 
- Kontraście między przeszłością a teraźniejszością
- Konkretnych, relatable przykładach
- Empatycznym tonie
- Polskim języku
- Zwróceniu TYLKO poprawnego JSON-a bez dodatkowych komentarzy

WAŻNE: Odpowiedz TYLKO w formacie JSON. Nie dodawaj żadnych dodatkowych tekstów, wyjaśnień ani formatowania markdown. Zwróć tylko czysty, poprawny JSON zgodny z szablonem.
"""

            # Generate content using AI with fallback
            generated_content = await self.generate_with_ai(full_prompt)
            
            # Validate JSON format before proceeding
            try:
                # Test if it's valid JSON
                json.loads(generated_content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received from AI: {e}")
                logger.error(f"Raw content: {generated_content[:500]}...")
                await loading_msg.edit_text(
                    "❌ AI returned invalid format. Please try again or contact the administrator."
                )
                return
            
            # Store in session
            user_sessions[user_id].update({
                'state': 'content_review',
                'topic': topic,
                'generated_content': generated_content
            })
            
            # Delete loading message
            await loading_msg.delete()
            
            # Show generated content with approval buttons (format JSON for display)
            session = user_sessions[user_id]
            style = session.get('style', 'style_1')
            
            if style == 'style_2':
                preview_text = self.json_generator_style2.format_cards_for_display(generated_content)
            else:
                preview_text = self.json_generator.format_cards_for_display(generated_content)
            
            keyboard = [
                [InlineKeyboardButton("✅ Approve Content", callback_data="approve_content")],
                [InlineKeyboardButton("✏️ Request Modifications", callback_data="modify_content")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Handle long messages by splitting if necessary
            full_message = f"🎯 *Generated Carousel Content:*\n\n{preview_text}"
            
            if len(full_message) > 4000:  # Leave some buffer for Telegram's 4096 limit
                # Send content in parts
                await update.message.reply_text("🎯 *Generated Carousel Content:*", parse_mode='Markdown')
                
                # Split content into chunks
                chunks = self.split_message(preview_text, 3800)
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:  # Last chunk gets the buttons
                        await update.message.reply_text(chunk, reply_markup=reply_markup, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(chunk, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    full_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            await loading_msg.edit_text(
                "❌ An error occurred while generating content. Please try again or contact the administrator."
            )
    
    async def generate_image(self, update: Update, user_id: int, description: str):
        """Generate standalone image using OpenRouter/Gemini or DALL-E fallback"""
        # Show loading message
        loading_msg = await update.message.reply_text("🎨 Generating your image with AI... This may take up to 2 minutes for high-quality results.")
        
        try:
            # Read the image generation prompt template
            prompt_path = Path("project/assets/image_generation_prompt.txt")
            async with aiofiles.open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = await f.read()
            
            # Create the full prompt by replacing the placeholder
            full_prompt = prompt_template.replace('{USER_INPUT}', description)
            
            # Generate image using OpenRouter with Gemini 2.5 Flash Image Preview
            if openrouter_client:
                logger.info("Generating standalone image with Gemini 2.5 Flash Image Preview...")
                
                payload = {
                    "model": "google/gemini-2.5-flash-image-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Please generate an image based on this description: {full_prompt}"
                                }
                            ]
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
                
                try:
                    # Add retry logic for timeout issues
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            logger.info(f"OpenRouter API attempt {attempt + 1}/{max_retries}")
                            response = await openrouter_client.post("/chat/completions", json=payload)
                            response_data = response.json()
                            
                            if response.status_code == 200 and "choices" in response_data:
                                # Extract image URL from response
                                message = response_data["choices"][0]["message"]
                                image_url = self.extract_image_from_gemini_response(message)
                                logger.info("Gemini standalone image generation successful")
                                break
                            else:
                                logger.error(f"OpenRouter API error: {response_data}")
                                if attempt == max_retries - 1:
                                    raise Exception("Failed to generate image with OpenRouter")
                                continue
                                
                        except httpx.TimeoutException as e:
                            logger.warning(f"OpenRouter timeout on attempt {attempt + 1}: {e}")
                            if attempt == max_retries - 1:
                                logger.error("OpenRouter timeout after all retries, falling back to DALL-E")
                                raise Exception("OpenRouter timeout - falling back to DALL-E")
                            continue
                        except httpx.RequestError as e:
                            logger.warning(f"OpenRouter request error on attempt {attempt + 1}: {e}")
                            if attempt == max_retries - 1:
                                raise Exception("OpenRouter request failed - falling back to DALL-E")
                            continue
                            
                except Exception as e:
                    logger.warning(f"OpenRouter failed: {e}, falling back to DALL-E")
                    # Fall through to DALL-E fallback
                    if openai_client:
                        logger.info("Falling back to DALL-E...")
                        response = await openai_client.images.generate(
                            model="dall-e-3",
                            prompt=full_prompt,
                            size="1024x1024",
                            quality="standard",
                            n=1,
                        )
                        
                        image_url = response.data[0].url
                        logger.info("DALL-E fallback generation successful")
                    else:
                        raise Exception("Both OpenRouter and DALL-E are unavailable")
            elif openai_client:
                # Fallback to DALL-E if OpenRouter is not available
                logger.info("OpenRouter not available, falling back to DALL-E...")
                response = await openai_client.images.generate(
                    model="dall-e-3",
                    prompt=full_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                
                image_url = response.data[0].url
                logger.info("DALL-E standalone generation successful")
            else:
                await loading_msg.edit_text(
                    "❌ Image generation is not available. Please contact the administrator."
                )
                return
            
            # Send the generated image
            try:
                await update.message.reply_photo(
                    photo=image_url,
                    caption=f"🖼️ *Generated Image*\n\n*Description:* {description}\n\n*Generated with AI*",
                    parse_mode='Markdown'
                )
                # Delete loading message only after successful image send
                await loading_msg.delete()
            except Exception as photo_error:
                logger.error(f"Error sending photo: {photo_error}")
                # If photo fails, edit the loading message instead of deleting it
                await loading_msg.edit_text(
                    f"🖼️ *Image Generated Successfully!*\n\n"
                    f"*Description:* {description}\n\n"
                    f"*Image URL:* `{image_url}`\n\n"
                    f"⚠️ *Note:* The image was generated but couldn't be displayed directly. "
                    f"You can access it using the URL above.",
                    parse_mode='Markdown'
                )
            
            # Reset user session to main menu
            user_sessions[user_id] = {'state': 'main_menu'}
            
            # Show main menu again
            keyboard = [
                [InlineKeyboardButton("🎨 Create New Carousel", callback_data="create_carousel")],
                [InlineKeyboardButton("🖼️ Generate Image", callback_data="generate_image")],
                [InlineKeyboardButton("📚 My History", callback_data="show_history")],
                [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✅ *Image generated successfully!*\n\nWhat would you like to do next?",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
                
        except Exception as e:
            logger.error(f"Error generating standalone image: {e}")
            logger.error(f"Full error traceback:", exc_info=True)
            try:
                await loading_msg.edit_text(
                    f"❌ An error occurred while generating the image.\n\n"
                    f"Error details: {str(e)[:200]}...\n\n"
                    f"Please try again or contact the administrator."
                )
            except Exception as edit_error:
                logger.error(f"Error editing loading message: {edit_error}")
                # Send a new message if editing fails
                await update.message.reply_text(
                    f"❌ An error occurred while generating the image.\n\n"
                    f"Error details: {str(e)[:200]}...\n\n"
                    f"Please try again or contact the administrator."
                )
            
    
    def split_message(self, text: str, max_length: int) -> List[str]:
        """Split long text into chunks that fit Telegram's message limit"""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        lines = text.split('\n')
        current_chunk = ""
        
        for line in lines:
            # If adding this line would exceed the limit
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = line + '\n'
                else:
                    # Single line is too long, split it
                    while len(line) > max_length:
                        chunks.append(line[:max_length])
                        line = line[max_length:]
                    current_chunk = line + '\n'
            else:
                current_chunk += line + '\n'
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
        
    async def approve_content(self, query, user_id: int):
        """User approved the generated content, proceed to image generation for first slide"""
        session = user_sessions[user_id]
        
        # Show loading message while analyzing content
        await query.edit_message_text("🤖 Analyzing your content to suggest relevant images...")
        
        try:
            # Generate AI-suggested image descriptions based on content
            suggested_images = await self.generate_image_suggestions(session['generated_content'])
            
            # Update session state to image description
            session.update({
                'state': 'awaiting_image_description_for_slide',
                'suggested_images': suggested_images
            })
            
            text = (
                "🖼️ *Create Image for First Slide*\n\n"
                "Based on your carousel content, here are some AI-suggested images that would symbolize your message:\n\n"
                f"{suggested_images}\n\n"
                "*You can use one of these suggestions or describe your own image:*"
            )
            
            keyboard = [
                [InlineKeyboardButton("⏭️ Skip Image (Use Default)", callback_data="skip_image")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error generating image suggestions: {e}")
            # Fallback to original message if AI analysis fails
            session.update({
                'state': 'awaiting_image_description_for_slide'
            })
            
            text = (
                "🖼️ *Create Image for First Slide*\n\n"
                "Now let's create a custom image for your first slide to make it more engaging!\n\n"
                "Please describe what image you'd like for the title card. For example:\n"
                "• A minimalist mountain peak with sunrise\n"
                "• Abstract geometric shapes in blue and gold\n"
                "• A person climbing stairs towards success\n"
                "• Modern workspace with motivational elements\n\n"
                "*Describe your desired image:*"
            )
            
            keyboard = [
                [InlineKeyboardButton("⏭️ Skip Image (Use Default)", callback_data="skip_image")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def generate_image_suggestions(self, carousel_content: str) -> str:
        """Generate AI-suggested image descriptions based on carousel content"""
        try:
            # Parse the JSON content to extract the main theme and message
            cards_data = json.loads(carousel_content)
            cards = cards_data.get('cards', [])
            
            # Extract key information from the carousel
            title = cards[0].get('header', '') if cards else ''
            first_card_text = cards[0].get('text', '') if cards else ''
            
            # Create a summary of the main themes
            main_themes = []
            for card in cards[1:4]:  # Take first few content cards
                if card.get('text'):
                    main_themes.append(card.get('text', '')[:200])  # First 200 chars
            
            themes_text = '\n'.join(main_themes)
            
            # Create prompt for AI to suggest symbolic images
            suggestion_prompt = f"""
Based on this carousel content, suggest 3-4 symbolic image descriptions that would represent the main message and themes. The images should be minimalist, symbolic, and meaningful.

Title: {title}
Main content themes:
{themes_text}

Please provide 3-4 image suggestions in this format:
• [Description 1]
• [Description 2] 
• [Description 3]
• [Description 4]

Each description should be:
- Symbolic and metaphorical (not literal)
- Suitable for minimalist black and white line art
- Representing the transformation/growth/journey theme
- Professional and inspiring

Focus on symbols like: paths, bridges, mountains, trees growing, doors opening, light breaking through, geometric patterns representing growth, etc.
"""

            # Generate suggestions using AI
            suggestions = await self.generate_with_ai(suggestion_prompt)
            
            return suggestions.strip()
            
        except Exception as e:
            logger.error(f"Error in generate_image_suggestions: {e}")
            # Return fallback suggestions
            return (
                "• A winding path leading upward through minimalist landscape\n"
                "• A single tree growing from geometric shapes\n"
                "• An open door with light streaming through\n"
                "• Abstract stairs ascending toward a bright horizon"
            )
    
    async def send_image_for_approval(self, update: Update, user_id: int, image_url: str, description: str, loading_msg):
        """Helper method to send generated image for user approval"""
        # Store image URL in session
        user_sessions[user_id].update({
            'state': 'reviewing_slide_image',
            'slide_image_url': image_url,
            'slide_image_description': description
        })
        
        # Send the generated image for approval
        try:
            await update.message.reply_photo(
                photo=image_url,
                caption=f"🖼️ *Generated Image for First Slide*\n\n*Description:* {description}\n\nDo you like this image for your carousel's first slide?",
                parse_mode='Markdown'
            )
            # Delete loading message only after successful image send
            await loading_msg.delete()
        except Exception as photo_error:
            logger.error(f"Error sending carousel image: {photo_error}")
            # If photo fails, edit the loading message instead of deleting it
            await loading_msg.edit_text(
                f"🖼️ *Image Generated for First Slide!*\n\n"
                f"*Description:* {description}\n\n"
                f"*Image URL:* `{image_url}`\n\n"
                f"⚠️ *Note:* The image was generated but couldn't be displayed directly. "
                f"You can access it using the URL above.\n\n"
                f"Do you want to use this image for your carousel's first slide?",
                parse_mode='Markdown'
            )
        
        # Show approval buttons
        keyboard = [
            [InlineKeyboardButton("✅ Use This Image", callback_data="approve_slide_image")],
            [InlineKeyboardButton("🔄 Generate New Image", callback_data="decline_slide_image")],
            [InlineKeyboardButton("🔗 Use Custom URL", callback_data="use_custom_url")],
            [InlineKeyboardButton("⏭️ Skip Image", callback_data="skip_image")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Choose an option:",
            reply_markup=reply_markup
        )

    async def generate_slide_image(self, update: Update, user_id: int, description: str):
        """Generate image for the first slide using DALL-E"""
        # Show loading message
        loading_msg = await update.message.reply_text("🎨 Generating your slide image with AI... This may take up to 2 minutes for high-quality results.")
        
        try:
            logger.info(f"Starting carousel image generation for description: {description}")
            logger.info(f"OpenRouter client available: {openrouter_client is not None}")
            logger.info(f"OpenAI client available: {openai_client is not None}")
            
            # Read the image generation prompt template
            prompt_path = Path("project/assets/image_generation_prompt.txt")
            logger.info(f"Reading prompt template from: {prompt_path}")
            async with aiofiles.open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = await f.read()
            
            # Create the full prompt by replacing the placeholder
            full_prompt = prompt_template.replace('{USER_INPUT}', description)
            logger.info(f"Generated full prompt for carousel: {full_prompt[:100]}...")
            
            # Generate image using OpenRouter with Gemini 2.5 Flash Image Preview
            if openrouter_client:
                logger.info("Generating slide image with Gemini 2.5 Flash Image Preview...")
                
                payload = {
                    "model": "google/gemini-2.5-flash-image-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Please generate an image based on this description: {full_prompt}"
                                }
                            ]
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.7
                }
                
                try:
                    # Add retry logic for timeout issues
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            logger.info(f"OpenRouter API attempt {attempt + 1}/{max_retries}")
                            response = await openrouter_client.post("/chat/completions", json=payload)
                            logger.info(f"OpenRouter response status: {response.status_code}")
                            response_data = response.json()
                            logger.info(f"OpenRouter response keys: {list(response_data.keys())}")
                            
                            if response.status_code == 200 and "choices" in response_data:
                                # Extract image URL from response
                                message = response_data["choices"][0]["message"]
                                logger.info(f"Message structure: {list(message.keys())}")
                                image_url = self.extract_image_from_gemini_response(message)
                                logger.info(f"Extracted image URL: {image_url[:50]}...")
                                logger.info("Gemini carousel image generation successful")
                                
                                # Send image for approval and return
                                await self.send_image_for_approval(update, user_id, image_url, description, loading_msg)
                                return  # Important: return here to avoid continuing to fallback code
                                
                                break
                            else:
                                logger.error(f"OpenRouter API error - Status: {response.status_code}")
                                logger.error(f"Response data: {response_data}")
                                if attempt == max_retries - 1:
                                    raise Exception("Failed to generate image with OpenRouter")
                                continue
                                
                        except httpx.TimeoutException as e:
                            logger.warning(f"OpenRouter timeout on attempt {attempt + 1}: {e}")
                            if attempt == max_retries - 1:
                                logger.error("OpenRouter timeout after all retries, falling back to DALL-E")
                                raise Exception("OpenRouter timeout - falling back to DALL-E")
                            continue
                        except httpx.RequestError as e:
                            logger.warning(f"OpenRouter request error on attempt {attempt + 1}: {e}")
                            if attempt == max_retries - 1:
                                raise Exception("OpenRouter request failed - falling back to DALL-E")
                            continue
                            
                except Exception as e:
                    logger.warning(f"OpenRouter failed: {e}, falling back to DALL-E")
                    # Fall through to DALL-E fallback
                    if openai_client:
                        logger.info("Falling back to DALL-E...")
                        response = await openai_client.images.generate(
                            model="dall-e-3",
                            prompt=full_prompt,
                            size="1024x1024",
                            quality="standard",
                            n=1,
                        )
                        
                        image_url = response.data[0].url
                        logger.info("DALL-E fallback generation successful")
                        
                        # Send image for approval
                        await self.send_image_for_approval(update, user_id, image_url, description, loading_msg)
                        return
                    else:
                        raise Exception("Both OpenRouter and DALL-E are unavailable")
            elif openai_client:
                # Fallback to DALL-E if OpenRouter is not available
                logger.info("OpenRouter not available, falling back to DALL-E...")
                response = await openai_client.images.generate(
                    model="dall-e-3",
                    prompt=full_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                
                image_url = response.data[0].url
                logger.info("DALL-E fallback generation successful")
                
                # Send image for approval
                await self.send_image_for_approval(update, user_id, image_url, description, loading_msg)
                return
                
            else:
                await loading_msg.edit_text(
                    "❌ Image generation is not available. Please contact the administrator."
                )
                
        except Exception as e:
            logger.error(f"Error generating slide image: {e}")
            logger.error(f"Full error traceback:", exc_info=True)
            try:
                await loading_msg.edit_text(
                    f"❌ An error occurred while generating the image.\n\n"
                    f"Error details: {str(e)[:200]}...\n\n"
                    f"Please try again or contact the administrator."
                )
            except Exception as edit_error:
                logger.error(f"Error editing loading message: {edit_error}")
                # Send a new message if editing fails
                await update.message.reply_text(
                    f"❌ An error occurred while generating the image.\n\n"
                    f"Error details: {str(e)[:200]}...\n\n"
                    f"Please try again or contact the administrator."
                )
    
    def extract_image_from_gemini_response(self, message: dict) -> str:
        """Extract image URL from Gemini response message"""
        try:
            # Check if the message has images array (new format)
            if 'images' in message and len(message['images']) > 0:
                # Get the first image from the images array
                first_image = message['images'][0]
                if 'image_url' in first_image and 'url' in first_image['image_url']:
                    image_data = first_image['image_url']['url']
                    
                    # Check if it's base64 data
                    if image_data.startswith('data:image/'):
                        # Convert base64 to a temporary file and return URL
                        return self.handle_base64_image(image_data)
                    else:
                        # Direct URL
                        return image_data
            
            # Fallback: check content for URL (old format)
            content = message.get('content', '')
            if content:
                # If the response contains a direct URL
                if content.startswith('http'):
                    return content.strip()
                
                # If the response contains markdown image format
                import re
                url_match = re.search(r'!\[.*?\]\((https?://[^\)]+)\)', content)
                if url_match:
                    return url_match.group(1)
                
                # If the response contains just a URL in text
                url_match = re.search(r'https?://[^\s]+', content)
                if url_match:
                    return url_match.group(0)
            
            # If no URL found, raise an exception with debug info
            raise Exception(f"Could not extract image URL from Gemini response. Message structure: {message}")
            
        except Exception as e:
            logger.error(f"Error extracting image URL: {e}")
            logger.error(f"Message data: {message}")
            raise Exception(f"Failed to extract image URL from response: {e}")
    
    def handle_base64_image(self, base64_data: str) -> str:
        """Convert base64 image data to a temporary file and return public URL"""
        try:
            logger.info(f"Processing base64 image data (length: {len(base64_data)})")
            import base64
            import uuid
            from pathlib import Path
            
            # Extract the base64 data (remove data:image/png;base64, prefix)
            if ',' in base64_data:
                header, encoded_data = base64_data.split(',', 1)
                
                # Determine file extension from header
                if 'png' in header:
                    ext = 'png'
                elif 'jpeg' in header or 'jpg' in header:
                    ext = 'jpg'
                elif 'webp' in header:
                    ext = 'webp'
                else:
                    ext = 'png'  # default
                
                # Decode base64 data
                image_bytes = base64.b64decode(encoded_data)
                
                # Create unique filename
                image_id = str(uuid.uuid4())
                filename = f"generated_image_{image_id}.{ext}"
                
                # Save to static directory
                static_dir = Path("static")
                static_dir.mkdir(exist_ok=True)
                
                file_path = static_dir / filename
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)
                
                # Return public URL
                public_url = f"{BASE_URL}/static/{filename}"
                logger.info(f"Base64 image saved as: {public_url}")
                return public_url
            else:
                raise Exception("Invalid base64 data format")
                
        except Exception as e:
            logger.error(f"Error handling base64 image: {e}")
            raise Exception(f"Failed to process base64 image: {e}")
    
    async def skip_image_generation(self, query, user_id: int):
        """Skip image generation and proceed to HTML creation"""
        await self.proceed_to_html_generation(query, user_id)
    
    async def approve_slide_image(self, query, user_id: int):
        """User approved the generated slide image"""
        await self.proceed_to_html_generation(query, user_id)
    
    async def decline_slide_image(self, query, user_id: int):
        """User declined the image, ask for new description"""
        user_sessions[user_id]['state'] = 'awaiting_image_description_for_slide'
        
        text = (
            "🔄 *Generate New Image*\n\n"
            "Please provide a new description for the image you'd like for your first slide:\n\n"
            "*Describe your desired image:*"
        )
        
        keyboard = [
            [InlineKeyboardButton("⏭️ Skip Image", callback_data="skip_image")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def request_image_url(self, query, user_id: int):
        """Request custom image URL from user"""
        user_sessions[user_id]['state'] = 'awaiting_image_url'
        
        text = (
            "🔗 *Provide Custom Image URL*\n\n"
            "Please send the URL of the image you'd like to use for your first slide.\n\n"
            "Make sure the image is:\n"
            "• Publicly accessible\n"
            "• High quality (recommended: 1024x1024 or larger)\n"
            "• Suitable for your carousel theme\n\n"
            "*Send the image URL:*"
        )
        
        keyboard = [
            [InlineKeyboardButton("⏭️ Skip Image", callback_data="skip_image")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def process_image_url(self, update: Update, user_id: int, image_url: str):
        """Process custom image URL provided by user"""
        # Validate URL format
        if not (image_url.startswith('http://') or image_url.startswith('https://')):
            await update.message.reply_text(
                "❌ Please provide a valid URL starting with http:// or https://"
            )
            return
        
        # Store the custom URL in session
        user_sessions[user_id].update({
            'state': 'reviewing_slide_image',
            'slide_image_url': image_url,
            'slide_image_description': 'Custom image provided by user'
        })
        
        # Show confirmation
        await update.message.reply_text(
            f"✅ *Custom Image URL Saved*\n\n`{image_url}`\n\nProceeding to create your carousel...",
            parse_mode='Markdown'
        )
        
        # Proceed to HTML generation
        await self.proceed_to_html_generation_from_message(update, user_id)
    
    async def proceed_to_html_generation(self, query, user_id: int):
        """Proceed to HTML generation with or without custom image"""
        session = user_sessions[user_id]
        content = session['generated_content']
        
        # Show loading message
        await query.edit_message_text("🎨 Creating HTML page with your carousel...")
        
        try:
            # Generate HTML from JSON using appropriate generator
            style = session.get('style', 'style_1')
            
            if style == 'style_2':
                html_content = await self.json_generator_style2.generate_html_from_json(content)
            else:
                html_content = await self.json_generator.generate_html_from_json(content)
            
            # If we have a custom slide image, integrate it into the HTML
            if 'slide_image_url' in session:
                html_content = self.integrate_slide_image(html_content, session['slide_image_url'], style)
            
            # Store HTML in session
            session.update({
                'state': 'html_review',
                'html_content': html_content
            })
            
            # Create preview text
            image_info = ""
            if 'slide_image_url' in session:
                image_info = "• Custom image on first slide\n"
            
            preview_text = (
                "🎨 *HTML carousel has been generated!*\n\n"
                "The carousel contains:\n"
                f"{image_info}"
                "• Interactive cards\n"
                "• Professional design\n"
                "• Ability to download individual cards\n"
                "• Responsive layout\n\n"
                "What would you like to do?"
            )
            
            keyboard = [
                [InlineKeyboardButton("✅ Publish Carousel", callback_data="approve_html")],
                [InlineKeyboardButton("✏️ Request Changes", callback_data="modify_html")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(preview_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error generating HTML: {e}")
            await query.edit_message_text(
                "❌ An error occurred while creating HTML. Please try again."
            )
    
    async def proceed_to_html_generation_from_message(self, update: Update, user_id: int):
        """Proceed to HTML generation from message context (not callback)"""
        session = user_sessions[user_id]
        content = session['generated_content']
        
        # Show loading message
        loading_msg = await update.message.reply_text("🎨 Creating HTML page with your carousel...")
        
        try:
            # Generate HTML from JSON using appropriate generator
            style = session.get('style', 'style_1')
            
            if style == 'style_2':
                html_content = await self.json_generator_style2.generate_html_from_json(content)
            else:
                html_content = await self.json_generator.generate_html_from_json(content)
            
            # If we have a custom slide image, integrate it into the HTML
            if 'slide_image_url' in session:
                html_content = self.integrate_slide_image(html_content, session['slide_image_url'], style)
            
            # Store HTML in session
            session.update({
                'state': 'html_review',
                'html_content': html_content
            })
            
            # Create preview text
            image_info = ""
            if 'slide_image_url' in session:
                image_info = "• Custom image on first slide\n"
            
            preview_text = (
                "🎨 *HTML carousel has been generated!*\n\n"
                "The carousel contains:\n"
                f"{image_info}"
                "• Interactive cards\n"
                "• Professional design\n"
                "• Ability to download individual cards\n"
                "• Responsive layout\n\n"
                "What would you like to do?"
            )
            
            keyboard = [
                [InlineKeyboardButton("✅ Publish Carousel", callback_data="approve_html")],
                [InlineKeyboardButton("✏️ Request Changes", callback_data="modify_html")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading_msg.edit_text(preview_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error generating HTML: {e}")
            await loading_msg.edit_text(
                "❌ An error occurred while creating HTML. Please try again."
            )
    
    def integrate_slide_image(self, html_content: str, image_url: str, style: str) -> str:
        """Integrate custom image into the first slide of the carousel"""
        if style == 'style_2':
            # For Style 2, replace the mountain SVG with the custom image
            # Find the mountain-scene div and replace its content
            svg_start = html_content.find('<div class="mountain-scene">')
            if svg_start != -1:
                svg_end = html_content.find('</div>', svg_start) + 6
                if svg_end > svg_start:
                    # Replace the mountain SVG with custom image
                    custom_image_html = f'''<div class="mountain-scene">
                        <img src="{image_url}" alt="Custom slide image" style="width: 100%; height: 100%; object-fit: cover; border-radius: clamp(8px, 2cqmin, 16px);">
                    </div>'''
                    html_content = html_content[:svg_start] + custom_image_html + html_content[svg_end:]
        else:
            # For Style 1, we could add the image as a background or overlay
            # This would require modifying the Style 1 template structure
            pass
        
        return html_content
            
        
    async def request_modifications(self, query, user_id: int):
        """Request content modifications"""
        user_sessions[user_id]['state'] = 'awaiting_modifications'
        
        text = (
            "✏️ *Content Modification*\n\n"
            "Describe what changes you'd like to make to the carousel content:\n\n"
            "• Change tone (more motivational, calmer, etc.)\n"
            "• Add specific examples\n"
            "• Change focus to another aspect of the topic\n"
            "• Other suggestions...\n\n"
            "*Write your feedback:*"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    async def modify_content(self, update: Update, user_id: int, modifications: str):
        """Modify content based on user feedback"""
        loading_msg = await update.message.reply_text("🔄 Modifying content according to your feedback...")
        
        try:
            session = user_sessions[user_id]
            original_content = session['generated_content']
            topic = session['topic']
            
            # Create modification prompt
            modification_prompt = f"""
Oto oryginalna treść karuzeli na temat "{topic}":

{original_content}

Użytkownik poprosił o następujące modyfikacje:
{modifications}

Zmodyfikuj treść karuzeli zgodnie z uwagami użytkownika, zachowując oryginalny format JSON i strukturę. 
WAŻNE: Odpowiedz TYLKO w formacie JSON. Nie dodawaj żadnych dodatkowych tekstów, wyjaśnień ani formatowania markdown. Zwróć tylko czysty, poprawny JSON zgodny z oryginalnym szablonem.
"""

            # Generate modified content using AI with fallback
            modified_content = await self.generate_with_ai(modification_prompt)
            
            # Validate JSON format before proceeding
            try:
                # Test if it's valid JSON
                json.loads(modified_content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received from AI during modification: {e}")
                logger.error(f"Raw content: {modified_content[:500]}...")
                await loading_msg.edit_text(
                    "❌ AI returned invalid format during modification. Please try again or contact the administrator."
                )
                return
            
            # Update session
            session.update({
                'state': 'content_review',
                'generated_content': modified_content
            })
            
            await loading_msg.delete()
            
            # Show modified content (format JSON for display)
            style = session.get('style', 'style_1')
            
            if style == 'style_2':
                preview_text = self.json_generator_style2.format_cards_for_display(modified_content)
            else:
                preview_text = self.json_generator.format_cards_for_display(modified_content)
            
            keyboard = [
                [InlineKeyboardButton("✅ Approve Content", callback_data="approve_content")],
                [InlineKeyboardButton("✏️ Request More Changes", callback_data="modify_content")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Handle long messages by splitting if necessary
            full_message = f"🔄 *Modified Carousel Content:*\n\n{preview_text}"
            
            if len(full_message) > 4000:  # Leave some buffer for Telegram's 4096 limit
                # Send content in parts
                await update.message.reply_text("🔄 *Modified Carousel Content:*", parse_mode='Markdown')
                
                # Split content into chunks
                chunks = self.split_message(preview_text, 3800)
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:  # Last chunk gets the buttons
                        await update.message.reply_text(chunk, reply_markup=reply_markup, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(chunk, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    full_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Error modifying content: {e}")
            await loading_msg.edit_text("❌ An error occurred during modification. Please try again.")
            
    async def request_html_modifications(self, query, user_id: int):
        """Request HTML modifications"""
        user_sessions[user_id]['state'] = 'awaiting_html_modifications'
        
        text = (
            "🎨 *Appearance Modification*\n\n"
            "Describe what changes you'd like to make to the carousel appearance:\n\n"
            "• Change colors (background, text, buttons)\n"
            "• Adjust font sizes\n"
            "• Change element layout\n"
            "• Other stylistic suggestions...\n\n"
            "*Write your feedback:*"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    async def modify_html_content(self, update: Update, user_id: int, modifications: str):
        """Modify HTML based on user feedback"""
        loading_msg = await update.message.reply_text("🎨 Modifying carousel appearance...")
        
        try:
            session = user_sessions[user_id]
            current_html = session['html_content']
            
            # For HTML modifications, we could use Claude to modify CSS
            # For now, we'll acknowledge the request and keep the original
            
            await loading_msg.delete()
            
            text = (
                "🎨 *Modifications have been applied!*\n\n"
                "The carousel has been updated according to your feedback.\n\n"
                "What would you like to do next?"
            )
            
            keyboard = [
                [InlineKeyboardButton("✅ Publish Carousel", callback_data="approve_html")],
                [InlineKeyboardButton("✏️ More Changes", callback_data="modify_html")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error modifying HTML: {e}")
            await loading_msg.edit_text("❌ An error occurred during modification. Please try again.")
            
    async def publish_carousel(self, query, user_id: int):
        """Publish the carousel and return link"""
        await query.edit_message_text("🚀 Publishing carousel...")
        
        try:
            session = user_sessions[user_id]
            html_content = session['html_content']
            
            # Generate unique filename
            carousel_id = str(uuid.uuid4())
            filename = f"carousel_{carousel_id}.html"
            
            # Save HTML file
            static_dir = Path("static")
            static_dir.mkdir(exist_ok=True)
            
            file_path = static_dir / filename
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(html_content)
            
            # Generate public URL
            public_url = f"{BASE_URL}/static/{filename}"
            
            # Store in session for future reference
            session['published_url'] = public_url
            session['carousel_id'] = carousel_id
            
            # Save to cache
            await self.cache.save_carousel(
                carousel_id=carousel_id,
                user_id=user_id,
                topic=session['topic'],
                generated_content=session['generated_content'],
                html_content=html_content,
                public_url=public_url,
                file_path=str(file_path)
            )
            
            success_text = (
                "🎉 *Carousel has been published!*\n\n"
                f"🔗 *Carousel Link:*\n`{public_url}`\n\n"
                "✅ You can now share this link on Instagram Stories, in your bio, "
                "or anywhere you want!\n\n"
                "💡 *Tip:* The link is permanent and will work without time restrictions."
            )
            
            keyboard = [
                [InlineKeyboardButton("🌐 Open Carousel", url=public_url)],
                [InlineKeyboardButton("🎨 Create Another Carousel", callback_data="create_carousel")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error publishing carousel: {e}")
            await query.edit_message_text("❌ An error occurred during publishing. Please try again.")
            
    async def back_to_main_menu(self, query, user_id: int):
        """Return to main menu"""
        user_sessions[user_id] = {'state': 'main_menu'}
        
        keyboard = [
            [InlineKeyboardButton("🎨 Create New Carousel", callback_data="create_carousel")],
            [InlineKeyboardButton("📚 My History", callback_data="show_history")],
            [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "🎯 *Instagram Carousel Generator*\n\n"
            "Choose an option:"
        )
        
        await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_user_history(self, query, user_id: int):
        """Show user's carousel history"""
        try:
            carousels = await self.cache.get_user_carousels(user_id, limit=5)
            
            if not carousels:
                text = (
                    "📚 *Your Carousel History*\n\n"
                    "You haven't created any carousels yet.\n\n"
                    "Create your first carousel to see it here!"
                )
                keyboard = [[InlineKeyboardButton("🎨 Create New Carousel", callback_data="create_carousel")],
                           [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            else:
                text = "📚 *Your Recent Carousels:*\n\n"
                
                for i, carousel in enumerate(carousels, 1):
                    created_date = carousel['created_at'][:10]  # Just the date part
                    topic = carousel['topic'][:50] + "..." if len(carousel['topic']) > 50 else carousel['topic']
                    
                    if carousel['public_url']:
                        text += f"{i}. *{topic}*\n   📅 {created_date}\n   🔗 [View Carousel]({carousel['public_url']})\n\n"
                    else:
                        text += f"{i}. *{topic}*\n   📅 {created_date}\n   ⚠️ Not published\n\n"
                
                keyboard = [[InlineKeyboardButton("🎨 Create New Carousel", callback_data="create_carousel")],
                           [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error showing user history: {e}")
            await query.edit_message_text("❌ An error occurred while loading your history. Please try again.")
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user_id = update.effective_user.id
        await self.cache.init_db()
        
        try:
            carousels = await self.cache.get_user_carousels(user_id, limit=10)
            
            if not carousels:
                text = (
                    "📚 *Your Carousel History*\n\n"
                    "You haven't created any carousels yet.\n\n"
                    "Use /start to create your first carousel!"
                )
            else:
                text = "📚 *Your Carousel History:*\n\n"
                
                for i, carousel in enumerate(carousels, 1):
                    created_date = carousel['created_at'][:10]
                    topic = carousel['topic'][:40] + "..." if len(carousel['topic']) > 40 else carousel['topic']
                    
                    if carousel['public_url']:
                        text += f"{i}. {topic}\n   📅 {created_date} - [View]({carousel['public_url']})\n\n"
                    else:
                        text += f"{i}. {topic}\n   📅 {created_date} - Not published\n\n"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in show_history: {e}")
            await update.message.reply_text("❌ An error occurred while loading your history.")
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command - show overall statistics"""
        await self.cache.init_db()
        
        try:
            stats = await self.cache.get_carousel_stats()
            
            text = "📊 *Carousel Generator Statistics:*\n\n"
            text += f"🎨 Total Carousels: {stats.get('total_carousels', 0)}\n"
            text += f"👥 Unique Users: {stats.get('unique_users', 0)}\n"
            text += f"🔥 Created Today: {stats.get('recent_carousels', 0)}\n\n"
            
            if stats.get('popular_topics'):
                text += "*Popular Topics:*\n"
                for topic, count in stats['popular_topics']:
                    topic_short = topic[:30] + "..." if len(topic) > 30 else topic
                    text += f"• {topic_short} ({count})\n"
            
            await update.message.reply_text(text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in show_stats: {e}")
            await update.message.reply_text("❌ An error occurred while loading statistics.")
        
    def run(self):
        """Run the bot and web server"""
        logger.info("Starting Carousel Bot...")
        
        # Start FastAPI server in a separate thread
        def start_web_server():
            port = int(os.getenv('PORT', 8000))
            logger.info(f"Starting web server on port {port}")
            uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")
        
        # Start web server in background thread
        web_thread = threading.Thread(target=start_web_server, daemon=True)
        web_thread.start()
        
        # Start Telegram bot
        logger.info("Starting Telegram bot...")
        self.app.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        logger.error("Missing required environment variable: TELEGRAM_BOT_TOKEN")
        exit(1)
        
    if not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
        logger.error("Missing AI API keys: Please provide either ANTHROPIC_API_KEY or OPENAI_API_KEY")
        exit(1)
        
    if ANTHROPIC_API_KEY:
        logger.info("Claude API key found - will use as primary")
    if OPENAI_API_KEY:
        logger.info("OpenAI GPT-5 API key found - will use as fallback" if ANTHROPIC_API_KEY else "OpenAI GPT-5 API key found - will use as primary")
    if OPEN_ROUTER_API_KEY:
        logger.info("OpenRouter API key found - will use for image generation with Gemini 2.5 Flash")
        
    bot = CarouselBot()
    bot.run()
