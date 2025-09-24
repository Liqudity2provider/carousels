import re
from pathlib import Path
from typing import List, Dict
import aiofiles

class HTMLCarouselGenerator:
    """Generate HTML carousels from content"""
    
    def __init__(self, template_path: str = "project/assets/html_example.html"):
        self.template_path = Path(template_path)
    
    async def generate_html(self, content: str) -> str:
        """Generate HTML carousel from content"""
        # Read the HTML template
        async with aiofiles.open(self.template_path, 'r', encoding='utf-8') as f:
            html_template = await f.read()
        
        # Parse content into cards
        cards = self.parse_content_to_cards(content)
        
        # Generate HTML with the parsed cards
        html_content = await self.replace_template_content(html_template, cards)
        
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
                        # This is explanation text
                        current_card['explanation'] += line + ' '
                else:
                    # For hook and closing cards, just add to content
                    current_card['content'].append(line)
            
            i += 1
        
        # Add the last card
        if current_card:
            cards.append(current_card)
        
        return cards
    
    async def replace_template_content(self, html_template: str, cards: List[Dict]) -> str:
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
        nav_dots_html = self.generate_navigation_dots(len(cards))
        nav_pattern = r'<div class="navigation">.*?</div>'
        html = re.sub(nav_pattern, nav_dots_html, html, flags=re.DOTALL)
        
        # Replace cards content
        cards_html = self.generate_cards_html(cards)
        
        # Find and replace the cards section
        cards_pattern = r'<!-- Card 1 \(Hook\) -->.*?</div>\s*<div class="controls">'
        replacement = cards_html + '\n        <div class="controls">'
        html = re.sub(cards_pattern, replacement, html, flags=re.DOTALL)
        
        # Update JavaScript for correct card count
        js_pattern = r'const totalCards = \d+;'
        html = re.sub(js_pattern, f'const totalCards = {len(cards)};', html)
        
        return html
    
    def generate_navigation_dots(self, card_count: int) -> str:
        """Generate navigation dots HTML"""
        dots = []
        for i in range(card_count):
            active_class = " active" if i == 0 else ""
            dots.append(f'            <div class="nav-dot{active_class}" onclick="showCard({i})"></div>')
        
        return f'''        <div class="navigation">
{chr(10).join(dots)}
        </div>'''
    
    def generate_cards_html(self, cards: List[Dict]) -> str:
        """Generate HTML for all cards"""
        cards_html = []
        
        for i, card in enumerate(cards):
            active_class = " active" if i == 0 else ""
            
            if card['type'] == 'hook':
                card_html = self.generate_hook_card(card, active_class)
            elif card['type'] == 'main':
                card_html = self.generate_main_card(card, active_class)
            elif card['type'] == 'closing':
                card_html = self.generate_closing_card(card, active_class)
            else:
                continue
                
            cards_html.append(card_html)
        
        return '\n\n'.join(cards_html)
    
    def generate_hook_card(self, card: Dict, active_class: str) -> str:
        """Generate hook card HTML"""
        title = card['title'].replace('👉', '').strip()
        content_lines = card['content']
        
        main_text = content_lines[0] if content_lines else "Nie zauważasz ich od razu."
        secondary_text = content_lines[1] if len(content_lines) > 1 else "Ale pewnego dnia łapiesz się na tym, że reagujesz zupełnie inaczej niż kiedyś."
        
        return f'''        <!-- Card 1 (Hook) -->
        <div class="card{active_class}">
            <div class="content">
                <div class="header large">
                    <span class="emoji">👉</span>
                    <span>{title}</span>
                </div>

                <div class="main-text">
                    {main_text}
                </div>

                <div class="secondary-text">
                    {secondary_text}
                </div>
            </div>

            <div class="author-section">
                <div class="author-avatar"></div>
                <div class="author-info">
                    <div class="author-name">
                        Daniel Tur
                        <span class="verified-icon">✓</span>
                    </div>
                    <div class="author-handle">@cryptur_daniel</div>
                </div>
            </div>
        </div>'''
    
    def generate_main_card(self, card: Dict, active_class: str) -> str:
        """Generate main content card HTML"""
        title = card['title'].replace('🔹', '').strip()
        past = card.get('past', '')
        present = card.get('present', '')
        explanation = card.get('explanation', '').strip()
        
        # Combine past and present into body text
        body_parts = []
        if past:
            body_parts.append(past)
        if present:
            body_parts.append(present)
        
        body_text = '<br><br>'.join(body_parts)
        
        return f'''        <!-- Main Card -->
        <div class="card{active_class}">
            <div class="content">
                <div class="header">
                    <span class="emoji">🔹</span>
                    <span>{title}</span>
                </div>

                <div class="body-text">
                    {body_text}
                </div>

                <div class="secondary-text">
                    {explanation}
                </div>
            </div>
        </div>'''
    
    def generate_closing_card(self, card: Dict, active_class: str) -> str:
        """Generate closing card HTML"""
        title = card['title'].replace('💡', '').strip()
        content_lines = card['content']
        
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
        
        return f'''        <!-- Card 7 (Closing) -->
        <div class="card{active_class}">
            <div class="content">
                <div class="header">
                    <span class="emoji">💡</span>
                    <span>{title}</span>
                </div>

                <div class="closing-text">
                    {closing_text.strip()}
                </div>

                <div class="cta-text">
                    {cta_text.strip()}
                </div>
            </div>

            <div class="author-section">
                <div class="author-avatar"></div>
                <div class="author-info">
                    <div class="author-name">
                        Daniel Tur
                        <span class="verified-icon">✓</span>
                    </div>
                    <div class="author-handle">@cryptur_daniel</div>
                </div>
            </div>
        </div>'''
