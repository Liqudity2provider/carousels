import re
from pathlib import Path
from typing import List, Dict
import aiofiles

class HTMLCarouselGenerator:
    """Generate HTML carousels from content"""
    
    def __init__(self, template_path: str = "project/assets/html_example.html", 
                 cards_template_path: str = "project/assets/cards_html.html"):
        self.template_path = Path(template_path)
        self.cards_template_path = Path(cards_template_path)
    
    async def generate_html(self, content: str) -> str:
        """Generate HTML carousel from content"""
        # Read the HTML template and cards template
        async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
            html_template = await f.read()
        
        async with aiofiles.open(self.cards_template_path, 'r', encoding='utf-8') as f:
            cards_template = await f.read()
        
        # Parse content into cards
        cards = self.parse_content_to_cards(content)
        
        # Generate HTML with the parsed cards
        html_content = await self.replace_template_content(html_template, cards, cards_template)
        
        return html_content
    
    def parse_content_to_cards(self, content: str) -> List[Dict]:
        """Parse generated content into structured cards"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        cards = []
        current_card = None
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Skip separator lines
            if line == '⸻':
                i += 1
                continue
            
            # Detect card types
            if line.startswith('👉') and ('sygnał' in line.lower() or 'sposób' in line.lower() or 'znak' in line.lower()):
                # Hook card (Card 1)
                if current_card:
                    cards.append(current_card)
                
                current_card = {
                    'type': 'hook',
                    'title': line,
                    'content': []
                }
                
            elif line.startswith('🔹'):
                # Main content card (Cards 2-6)
                if current_card:
                    cards.append(current_card)
                
                current_card = {
                    'type': 'main',
                    'title': line,
                    'content': [],
                    'past': '',
                    'present': '',
                    'explanation': ''
                }
                
            elif line.startswith('💡'):
                # Closing card (Card 7)
                if current_card:
                    cards.append(current_card)
                
                current_card = {
                    'type': 'closing',
                    'title': line,
                    'content': []
                }
                
            elif current_card:
                # Add content to current card
                if current_card['type'] == 'main':
                    # For main cards, try to identify past/present/explanation
                    if line.startswith('Kiedyś') or line.startswith('Dawniej'):
                        current_card['past'] = line
                    elif line.startswith('Dziś') or line.startswith('Teraz'):
                        current_card['present'] = line
                    else:
                        # This is explanation text - limit to reasonable length
                        if 'explanation' not in current_card:
                            current_card['explanation'] = ''
                        # Only add if we haven't exceeded reasonable length
                        if len(current_card['explanation']) < 300:  # Limit explanation length
                            current_card['explanation'] += line + ' '
                else:
                    # For hook and closing cards, just add to content
                    current_card['content'].append(line)
            
            i += 1
        
        # Add the last card
        if current_card:
            cards.append(current_card)
        
        return cards
    
    async def replace_template_content(self, html_template: str, cards: List[Dict], cards_template: str) -> str:
        """Replace template content with generated cards"""
        html = html_template
        
        # Update page title
        if cards and cards[0]['type'] == 'hook':
            title = cards[0]['title'].replace('👉', '').strip()
            html = html.replace(
                '<title>Mental Strength Carousel</title>',
                f'<title>{title}</title>'
            )
        
        # Update navigation dots count
        # nav_dots_html = self.generate_navigation_dots(len(cards))
        nav_pattern = r'<div class="navigation">.*?</div>'
        # html = re.sub(nav_pattern, nav_dots_html, html, flags=re.DOTALL)
        
        # Generate cards HTML using templates
        cards_html = self.generate_cards_from_template(cards, cards_template)
        
        # Find and replace the cards placeholder
        cards_placeholder = '<!--        THERE IS A PLACE WHERE DYNAMIC CARDS SHOULD BE INSERTED  -->'
        html = html.replace(cards_placeholder, cards_html)
        
        # Update JavaScript for correct card count
        js_pattern = r'const totalCards = \d+;'
        html = re.sub(js_pattern, f'const totalCards = {len(cards)};', html)
        
        return html
    
    def generate_navigation_dots(self, card_count: int) -> str:
        """Generate navigation dots HTML"""
        dots = []
        for i in range(card_count):
            active_class = " active" if i == 0 else ""
            dots.append(f'<div class="nav-dot{active_class}" onclick="showCard({i})"></div>')
        
        return f'''        <div class="navigation">
            {' '.join(dots)}
        </div>'''
    
    def generate_cards_from_template(self, cards: List[Dict], cards_template: str) -> str:
        """Generate HTML for all cards using templates"""
        # Extract individual card templates more precisely
        first_card_start = cards_template.find('<!-- First Card Template')
        middle_card_start = cards_template.find('<!-- Middle Card Template')
        last_card_start = cards_template.find('<!-- Last Card Template')
        
        # Extract first card template (skip the comment line)
        first_card_comment_end = cards_template.find('-->', first_card_start) + 3
        first_card_end = middle_card_start if middle_card_start > 0 else len(cards_template)
        first_card_template = cards_template[first_card_comment_end:first_card_end].strip()
        
        # Extract middle card template (skip the comment line)
        middle_card_comment_end = cards_template.find('-->', middle_card_start) + 3
        middle_card_end = last_card_start if last_card_start > 0 else len(cards_template)
        middle_card_template = cards_template[middle_card_comment_end:middle_card_end].strip()
        
        # Extract last card template (skip the comment line)
        last_card_comment_end = cards_template.find('-->', last_card_start) + 3
        last_card_template = cards_template[last_card_comment_end:].strip()
        
        cards_html = []
        
        for i, card in enumerate(cards):
            active_class = " active" if i == 0 else ""
            
            if card['type'] == 'hook':
                card_html = self.fill_first_card_template(first_card_template, card, active_class)
            elif card['type'] == 'closing':
                card_html = self.fill_last_card_template(last_card_template, card, active_class)
            else:  # main cards
                card_html = self.fill_middle_card_template(middle_card_template, card, active_class)
                
            cards_html.append(card_html)
        
        return '\n\n'.join(cards_html)
    
    def fill_first_card_template(self, template: str, card: Dict, active_class: str) -> str:
        """Fill the first card template with data"""
        if not template:
            return ""
        
        title = card['title'].replace('👉', '').strip()
        content_lines = card.get('content', [])
        
        main_text = content_lines[0] if content_lines else "Nie zauważasz ich od razu."
        secondary_text = content_lines[1] if len(content_lines) > 1 else "Ale pewnego dnia łapiesz się na tym, że reagujesz zupełnie inaczej niż kiedyś."
        
        # Replace placeholders
        filled_template = template.replace('{{TITLE}}', title)
        filled_template = filled_template.replace('{{MAIN_TEXT}}', main_text)
        filled_template = filled_template.replace('{{SECONDARY_TEXT}}', secondary_text)
        
        # Handle active class
        if active_class:
            filled_template = filled_template.replace('class="card"', f'class="card{active_class}"')
        
        return filled_template
    
    def fill_middle_card_template(self, template: str, card: Dict, active_class: str) -> str:
        """Fill the middle card template with data"""
        if not template:
            return ""
        
        title = card['title'].replace('🔹', '').strip()
        past = card.get('past', '')
        present = card.get('present', '')
        explanation = card.get('explanation', '').strip()
        
        # Combine past and present into body text (limit to 2 sections max)
        body_parts = []
        if past:
            body_parts.append(past)
        if present:
            body_parts.append(present)
        
        # Limit to maximum 2 sections
        body_parts = body_parts[:2]
        body_text = '<br><br>'.join(body_parts)
        
        # Limit explanation text length and split into max 2 sentences
        if explanation:
            sentences = explanation.split('. ')
            if len(sentences) > 2:
                explanation = '. '.join(sentences[:2]) + '.'
            # Limit total character count
            if len(explanation) > 200:
                explanation = explanation[:200] + '...'
        
        # Replace placeholders
        filled_template = template.replace('{{TITLE}}', title)
        filled_template = filled_template.replace('{{BODY_TEXT}}', body_text)
        filled_template = filled_template.replace('{{SECONDARY_TEXT}}', explanation)
        
        # Handle active class
        if active_class:
            filled_template = filled_template.replace('class="card"', f'class="card{active_class}"')
        
        return filled_template
    
    def fill_last_card_template(self, template: str, card: Dict, active_class: str) -> str:
        """Fill the last card template with data"""
        if not template:
            return ""
        
        title = card['title'].replace('💡', '').strip()
        content_lines = card.get('content', [])
        
        # Split content into closing text and CTA
        closing_text = ""
        cta_text = ""
        
        cta_started = False
        for line in content_lines:
            if line.startswith('👉'):
                cta_started = True
                cta_text += line + '<br><br>'
            elif cta_started:
                cta_text += line + '<br><br>'
            else:
                closing_text += line + ' '
        
        # Default CTA if none found
        if not cta_text:
            cta_text = "👉 Zapisz tę karuzelę, żeby wrócić do niej w trudniejszych momentach.<br><br>👉 Podziel się z kimś, kto potrzebuje dziś takiego przypomnienia."
        
        # Replace placeholders
        filled_template = template.replace('{{TITLE}}', title)
        filled_template = filled_template.replace('{{CLOSING_TEXT}}', closing_text.strip())
        filled_template = filled_template.replace('{{CTA_TEXT}}', cta_text.strip())
        
        # Handle active class
        if active_class:
            filled_template = filled_template.replace('class="card"', f'class="card{active_class}"')
        
        return filled_template
    
