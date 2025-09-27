import json
import re
from pathlib import Path
from typing import List, Dict
import aiofiles

class JSONCarouselGeneratorStyle2:
    """Generate HTML carousels from JSON card data using Style 2 (grid layout)"""
    
    def __init__(self, template_path: str = "project/assets/style_2/html_example.html", 
                 cards_template_path: str = "project/assets/style_2/cards_html.html"):
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
        """Replace template content with generated cards"""
        html = html_template
        
        # Update page title
        if cards and cards[0]['type'] == 'hook':
            title = cards[0]['header'].strip()
            html = html.replace(
                '<title>Life Goals Cards</title>',
                f'<title>{title}</title>'
            )
        
        # Generate cards HTML from JSON
        cards_html = self.generate_cards_from_json(cards, cards_template)
        
        # Replace cards placeholder
        cards_placeholder = '<!--        THERE IS A PLACE WHERE DYNAMIC CARDS SHOULD BE INSERTED  -->'
        html = html.replace(cards_placeholder, cards_html)
        
        # Update JavaScript for correct card count
        js_pattern = r'const totalCards = \d+;'
        html = re.sub(js_pattern, f'const totalCards = {len(cards)};', html)
        
        return html
    
    def generate_cards_from_json(self, cards: List[Dict], cards_template: str) -> str:
        """Generate HTML for all cards from JSON data"""
        # Extract card templates
        first_card_start = cards_template.find('<!-- First Card Template')
        content_card_start = cards_template.find('<!-- Content Card Template')
        section_template_start = cards_template.find('<!-- Section Template')
        
        # Extract first card template
        first_card_comment_end = cards_template.find('-->', first_card_start) + 3
        first_card_end = content_card_start if content_card_start > 0 else len(cards_template)
        first_card_template = cards_template[first_card_comment_end:first_card_end].strip()
        
        # Extract content card template
        content_card_comment_end = cards_template.find('-->', content_card_start) + 3
        content_card_end = section_template_start if section_template_start > 0 else len(cards_template)
        content_card_template = cards_template[content_card_comment_end:content_card_end].strip()
        
        # Extract section template
        section_comment_end = cards_template.find('-->', section_template_start) + 3
        section_template = cards_template[section_comment_end:].strip()
        
        cards_html = []
        
        for i, card in enumerate(cards):
            card_id = f'card{i+1}'
            
            if i == 0 and card['type'] == 'hook':
                # First card (title card with illustration)
                card_html = self.fill_first_card_template(first_card_template, card, card_id)
            else:
                # Content cards (cards 2-10)
                card_html = self.fill_content_card_template(content_card_template, card, card_id, section_template)
                
            cards_html.append(card_html)
        
        return '\n\n'.join(cards_html)
    
    def fill_first_card_template(self, template: str, card: Dict, card_id: str) -> str:
        """Fill the first card template with data"""
        if not template:
            return ""
        
        # Handle the title with proper HTML formatting
        title = card.get('header', '')
        # The title might already have <br> tags from the AI, so we keep them as is
        filled_template = template.replace('{{TITLE}}', title)
        filled_template = filled_template.replace('id="card1"', f'id="{card_id}"')
        
        return filled_template
    
    def fill_content_card_template(self, template: str, card: Dict, card_id: str, section_template: str) -> str:
        """Fill the content card template with data"""
        if not template:
            return ""
        
        # Parse the card text into sections
        sections_html = self.generate_sections_from_text(card.get('text', ''), section_template)
        
        filled_template = template.replace('{{SECTIONS}}', sections_html)
        filled_template = filled_template.replace('id="card2"', f'id="{card_id}"')
        
        return filled_template
    
    def generate_sections_from_text(self, text: str, section_template: str) -> str:
        """Generate sections HTML from card text"""
        if not text or not section_template:
            return ""
        
        # Split text into paragraphs first (by double line breaks)
        paragraphs = text.split('\n\n')
        sections = []
        current_section = {'number': '', 'text': []}
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # Check if paragraph starts with a number (section header)
            if re.match(r'^\d+\.', paragraph):
                # Save previous section if it exists
                if current_section['number'] or current_section['text']:
                    sections.append(current_section)
                
                # Start new section
                current_section = {'number': paragraph, 'text': []}
            else:
                # Add to current section text
                current_section['text'].append(paragraph)
        
        # Add the last section
        if current_section['number'] or current_section['text']:
            sections.append(current_section)
        
        # Generate HTML for each section
        sections_html = []
        for section in sections:
            if section['number'] or section['text']:
                section_html = section_template.replace('{{SECTION_NUMBER}}', section['number'])
                # Convert text to HTML with proper line breaks
                # First join paragraphs with double breaks, then handle single line breaks within paragraphs
                processed_text = []
                for text_part in section['text']:
                    # Replace single line breaks within paragraphs with <br>
                    processed_part = text_part.replace('\n', '<br>')
                    processed_text.append(processed_part)
                
                section_text = '<br><br>'.join(processed_text)
                section_html = section_html.replace('{{SECTION_TEXT}}', section_text)
                sections_html.append(section_html)
        
        return '\n\n'.join(sections_html)
    
    def format_cards_for_display(self, json_content: str) -> str:
        """Format JSON cards into a readable string for Telegram display"""
        try:
            cards_data = json.loads(json_content)
            cards = cards_data.get('cards', [])
            
            display_text = []
            for i, card in enumerate(cards):
                card_type = card.get('type', 'unknown').upper()
                header = card.get('header', 'No Header')
                text = card.get('text', 'No Text')
                
                display_text.append(f"--- Card {i+1} ({card_type}) ---")
                display_text.append(f"Header: {header}")
                display_text.append(f"Text:\n{text}\n")
                
            return "\n".join(display_text)
        except json.JSONDecodeError:
            return f"Invalid JSON content:\n{json_content}"
        except Exception as e:
            return f"Error formatting content: {e}\n{json_content}"
