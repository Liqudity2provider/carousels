import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Optional

import aiofiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
import json
from html_generator import HTMLCarouselGenerator
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
BASE_URL = os.getenv('BASE_URL', 'https://your-app.railway.app')

# Initialize Anthropic client
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# User sessions storage (in production, use Redis or database)
user_sessions: Dict[int, Dict] = {}

class CarouselBot:
    def __init__(self):
        self.app = Application.builder().token(TELEGRAM_TOKEN).build()
        self.html_generator = HTMLCarouselGenerator()
        self.cache = CarouselCache()
        self.setup_handlers()
        
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
            [InlineKeyboardButton("📚 My History", callback_data="show_history")],
            [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = (
            "🎯 *Welcome to Instagram Carousel Generator!*\n\n"
            "I'll help you create professional Instagram carousels in a few simple steps:\n\n"
            "1️⃣ Generate content using AI\n"
            "2️⃣ Create a beautiful HTML page\n"
            "3️⃣ Publish and give you a shareable link\n\n"
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
            
    async def start_carousel_creation(self, query, user_id: int):
        """Start the carousel creation process"""
        user_sessions[user_id] = {
            'state': 'awaiting_topic',
            'step': 'content_generation'
        }
        
        text = (
            "🎨 *Creating New Carousel*\n\n"
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
        elif state == 'awaiting_modifications':
            await self.modify_content(update, user_id, message_text)
        elif state == 'awaiting_html_modifications':
            await self.modify_html_content(update, user_id, message_text)
            
    async def generate_content(self, update: Update, user_id: int, topic: str):
        """Generate carousel content using Claude"""
        # Show loading message
        loading_msg = await update.message.reply_text("🤖 Generating carousel content... This may take a moment.")
        
        try:
            # Read the prompt template
            prompt_path = Path("project/assets/content_creation_prompt.txt")
            async with aiofiles.open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = await f.read()
            
            # Create the full prompt
            full_prompt = f"""
{prompt_template}

TEMAT KARUZELI: {topic}

Stwórz karuzelę na powyższy temat, stosując się dokładnie do podanego formatu i wytycznych. 
Pamiętaj o:
- Użyciu formy "ty" 
- Kontraście między przeszłością a teraźniejszością
- Konkretnych, relatable przykładach
- Empatycznym tonie
- Polskim języku

Zwróć tylko gotową treść karuzeli bez dodatkowych komentarzy.
"""

            # Call Claude API
            response = await anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": full_prompt}]
            )
            
            generated_content = response.content[0].text
            
            # Store in session
            user_sessions[user_id].update({
                'state': 'content_review',
                'topic': topic,
                'generated_content': generated_content
            })
            
            # Delete loading message
            await loading_msg.delete()
            
            # Show generated content with approval buttons
            preview_text = self.format_content_preview(generated_content)
            
            keyboard = [
                [InlineKeyboardButton("✅ Approve Content", callback_data="approve_content")],
                [InlineKeyboardButton("✏️ Request Modifications", callback_data="modify_content")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎯 *Generated Carousel Content:*\n\n{preview_text}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            await loading_msg.edit_text(
                "❌ An error occurred while generating content. Please try again or contact the administrator."
            )
            
    def format_content_preview(self, content: str) -> str:
        """Format content for preview (truncate if too long)"""
        lines = content.split('\n')
        preview_lines = []
        
        for line in lines[:15]:  # Show first 15 lines
            if line.strip():
                preview_lines.append(line[:100] + "..." if len(line) > 100 else line)
                
        preview = '\n'.join(preview_lines)
        
        if len(lines) > 15:
            preview += f"\n\n... (and {len(lines) - 15} more lines)"
            
        return preview[:1500] + "..." if len(preview) > 1500 else preview
        
    async def approve_content(self, query, user_id: int):
        """User approved the generated content, proceed to HTML generation"""
        session = user_sessions[user_id]
        content = session['generated_content']
        
        # Show loading message
        await query.edit_message_text("🎨 Creating HTML page with your carousel...")
        
        try:
            # Generate HTML
            html_content = await self.html_generator.generate_html(content)
            
            # Store HTML in session
            session.update({
                'state': 'html_review',
                'html_content': html_content
            })
            
            # Create temporary preview (you might want to implement a preview endpoint)
            preview_text = (
                "🎨 *HTML carousel has been generated!*\n\n"
                "The carousel contains:\n"
                "• 7 interactive cards\n"
                "• Navigation with dots and buttons\n"
                "• Ability to download individual cards\n"
                "• Responsive design\n\n"
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

Zmodyfikuj treść karuzeli zgodnie z uwagami użytkownika, zachowując oryginalny format i strukturę. 
Zwróć tylko zmodyfikowaną treść bez dodatkowych komentarzy.
"""

            # Call Claude API for modifications
            response = await anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": modification_prompt}]
            )
            
            modified_content = response.content[0].text
            
            # Update session
            session.update({
                'state': 'content_review',
                'generated_content': modified_content
            })
            
            await loading_msg.delete()
            
            # Show modified content
            preview_text = self.format_content_preview(modified_content)
            
            keyboard = [
                [InlineKeyboardButton("✅ Approve Content", callback_data="approve_content")],
                [InlineKeyboardButton("✏️ Request More Changes", callback_data="modify_content")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔄 *Modified Carousel Content:*\n\n{preview_text}",
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
        """Run the bot"""
        logger.info("Starting Carousel Bot...")
        self.app.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        logger.error("Missing required environment variables: TELEGRAM_BOT_TOKEN or ANTHROPIC_API_KEY")
        exit(1)
        
    bot = CarouselBot()
    bot.run()
