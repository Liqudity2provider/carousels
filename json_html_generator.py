import json
from pathlib import Path
from typing import List, Dict
import aiofiles

class JSONCarouselGenerator:
    """Generate HTML carousels from JSON card data"""
    
    def __init__(self, template_path: str = "project/assets/html_example.html", 
                 cards_template_path: str = "project/assets/cards_html.html"):
        self.template_path = Path(template_path)
        self.cards_template_path = Path(cards_template_path)
    
    async def generate_html_from_json(self, cards_json: str) -> str:
        """Generate HTML carousel from JSON cards"""
        # Parse JSON
        try:
            cards_data = json.loads(cards_json)
            cards = cards_data.get('cards', [])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        
        # Read templates
        async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
            html_template = await f.read()
        
        async with aiofiles.open(self.cards_template_path, 'r', encoding='utf-8') as f:
            cards_template = await f.read()
        
        # Generate HTML
        html_content = await self.replace_template_content(html_template, cards, cards_template)
        
        return html_content
    
    async def replace_template_content(self, html_template: str, cards: List[Dict], cards_template: str) -> str:
        """Replace template content with JSON cards"""
        html = html_template
        
        # Update page title from first card
        if cards and cards[0].get('type') == 'hook':
            title = cards[0].get('header', 'Instagram Carousel')
            html = html.replace(
                '<title>Mental Strength Carousel</title>',
                f'<title>{title}</title>'
            )
        
        # Navigation dots are removed - no longer needed
        
        # Generate cards HTML from JSON
        cards_html = self.generate_cards_from_json(cards, cards_template)
        
        # Replace cards placeholder
        cards_placeholder = '<!--        THERE IS A PLACE WHERE DYNAMIC CARDS SHOULD BE INSERTED  -->'
        html = html.replace(cards_placeholder, cards_html)
        
        # Update JavaScript for correct card count
        import re
        js_pattern = r'const totalCards = \d+;'
        html = re.sub(js_pattern, f'const totalCards = {len(cards)};', html)
        
        return html
    
    
    def generate_cards_from_json(self, cards: List[Dict], cards_template: str) -> str:
        """Generate HTML for all cards from JSON data"""
        # Extract card templates
        first_card_start = cards_template.find('<!-- First Card Template')
        middle_card_start = cards_template.find('<!-- Middle Card Template')
        last_card_start = cards_template.find('<!-- Last Card Template')
        
        # Extract templates (skip comment lines)
        first_card_comment_end = cards_template.find('-->', first_card_start) + 3
        first_card_end = middle_card_start if middle_card_start > 0 else len(cards_template)
        first_card_template = cards_template[first_card_comment_end:first_card_end].strip()
        
        middle_card_comment_end = cards_template.find('-->', middle_card_start) + 3
        middle_card_end = last_card_start if last_card_start > 0 else len(cards_template)
        middle_card_template = cards_template[middle_card_comment_end:middle_card_end].strip()
        
        last_card_comment_end = cards_template.find('-->', last_card_start) + 3
        last_card_template = cards_template[last_card_comment_end:].strip()
        
        cards_html = []
        
        for i, card in enumerate(cards):
            active_class = " active" if i == 0 else ""
            card_type = card.get('type', 'main')
            
            if card_type == 'hook':
                card_html = self.fill_hook_card_template(first_card_template, card, active_class)
            elif card_type == 'closing':
                card_html = self.fill_closing_card_template(last_card_template, card, active_class)
            else:  # main cards
                card_html = self.fill_main_card_template(middle_card_template, card, active_class)
                
            cards_html.append(card_html)
        
        return '\n\n'.join(cards_html)
    
    def fill_hook_card_template(self, template: str, card: Dict, active_class: str) -> str:
        """Fill the hook card template with JSON data"""
        if not template:
            return ""
        
        header = card.get('header', '')
        text = card.get('text', '')
        
        # Split text into main and secondary parts
        text_parts = text.split('\n\n')
        main_text = text_parts[0] if text_parts else "Nie zauważasz ich od razu."
        secondary_text = text_parts[1] if len(text_parts) > 1 else "Ale pewnego dnia łapiesz się na tym, że reagujesz zupełnie inaczej niż kiedyś."
        
        # Replace placeholders
        filled_template = template.replace('{{TITLE}}', header)
        filled_template = filled_template.replace('{{MAIN_TEXT}}', main_text)
        filled_template = filled_template.replace('{{SECONDARY_TEXT}}', secondary_text)
        
        # Handle active class
        if active_class:
            filled_template = filled_template.replace('class="card"', f'class="card{active_class}"')
        
        return filled_template
    
    def fill_main_card_template(self, template: str, card: Dict, active_class: str) -> str:
        """Fill the main card template with JSON data"""
        if not template:
            return ""
        
        header = card.get('header', '')
        text = card.get('text', '')
        
        # Split text into paragraphs and limit to 2 main sections + 1 explanation
        text_parts = text.split('\n\n')
        
        # Take first 2 parts as body text (past/present)
        body_parts = text_parts[:2]
        body_text = '<br><br>'.join(body_parts)
        
        # Take remaining as explanation (limit to 1 paragraph)
        explanation = text_parts[2] if len(text_parts) > 2 else ""
        
        # Replace placeholders
        filled_template = template.replace('{{TITLE}}', header)
        filled_template = filled_template.replace('{{BODY_TEXT}}', body_text)
        filled_template = filled_template.replace('{{SECONDARY_TEXT}}', explanation)
        
        # Handle active class
        if active_class:
            filled_template = filled_template.replace('class="card"', f'class="card{active_class}"')
        
        return filled_template
    
    def fill_closing_card_template(self, template: str, card: Dict, active_class: str) -> str:
        """Fill the closing card template with JSON data"""
        if not template:
            return ""
        
        header = card.get('header', '')
        text = card.get('text', '')
        
        # Split text into closing text and CTA
        text_parts = text.split('\n\n')
        
        # Find where CTA starts (lines with 👉)
        closing_parts = []
        cta_parts = []
        cta_started = False
        
        for part in text_parts:
            if '👉' in part:
                cta_started = True
                cta_parts.append(part)
            elif cta_started:
                cta_parts.append(part)
            else:
                closing_parts.append(part)
        
        closing_text = ' '.join(closing_parts)
        cta_text = '<br><br>'.join(cta_parts)
        
        # Default CTA if none found
        if not cta_text:
            cta_text = "👉 Zapisz tę karuzelę, żeby wrócić do niej w trudniejszych momentach.<br><br>👉 Podziel się z kimś, kto potrzebuje dziś takiego przypomnienia."
        
        # Replace placeholders
        filled_template = template.replace('{{TITLE}}', header)
        filled_template = filled_template.replace('{{CLOSING_TEXT}}', closing_text)
        filled_template = filled_template.replace('{{CTA_TEXT}}', cta_text)
        
        # Handle active class
        if active_class:
            filled_template = filled_template.replace('class="card"', f'class="card{active_class}"')
        
        return filled_template
    
    def format_cards_for_display(self, cards_json: str) -> str:
        """Format JSON cards for user display/editing"""
        try:
            cards_data = json.loads(cards_json)
            cards = cards_data.get('cards', [])
            
            formatted_text = "📋 **Generated Carousel Cards:**\n\n"
            
            for i, card in enumerate(cards, 1):
                card_type = card.get('type', 'main').upper()
                header = card.get('header', '')
                text = card.get('text', '').replace('\n\n', '\n')
                
                formatted_text += f"**Card {i} ({card_type}):**\n"
                formatted_text += f"*Header:* {header}\n"
                formatted_text += f"*Text:* {text}\n\n"
                formatted_text += "---\n\n"
            
            return formatted_text
            
        except json.JSONDecodeError:
            return "❌ Invalid JSON format"
