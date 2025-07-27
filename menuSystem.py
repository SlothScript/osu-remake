import pygame
import math
from levelSystem import get_levels, Level
from osu_to_btmp_converter import OsuLazerDatabase
import os

# Initialize pygame
pygame.init()
pygame.font.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (200, 200, 200)
DARK_GRAY = (64, 64, 64)
BLUE = (70, 130, 180)
LIGHT_BLUE = (135, 206, 250)
GREEN = (50, 205, 50)
ORANGE = (255, 165, 0)
PURPLE = (138, 43, 226)

# Color palette for modern UI
PRIMARY_COLOR = (41, 128, 185)
SECONDARY_COLOR = (52, 73, 94)
ACCENT_COLOR = (231, 76, 60)
SUCCESS_COLOR = (39, 174, 96)
WARNING_COLOR = (241, 196, 15)
BACKGROUND_COLOR = (44, 62, 80)
CARD_COLOR = (52, 73, 94)
TEXT_COLOR = (236, 240, 241)
MUTED_TEXT = (149, 165, 166)

class MenuState:
    TITLE = "title"
    LEVEL_SELECT = "level_select"
    PLAYING = "playing"
    PAUSED = "paused"
    OSU_IMPORT = "osu_import"

class Button:
    def __init__(self, x, y, width, height, text, color=PRIMARY_COLOR, text_color=WHITE, font_size=24):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = tuple(min(255, c + 30) for c in color)
        self.text_color = text_color
        self.font = pygame.font.Font(None, font_size)
        self.hovered = False
        self.clicked = False
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                self.clicked = True
                return True
        return False
    
    def draw(self, screen):
        # Draw button with rounded corners effect
        color = self.hover_color if self.hovered else self.color
        
        # Shadow effect
        shadow_rect = self.rect.copy()
        shadow_rect.x += 3
        shadow_rect.y += 3
        pygame.draw.rect(screen, (20, 20, 20), shadow_rect, border_radius=8)
        
        # Main button
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, LIGHT_GRAY if self.hovered else WHITE, self.rect, 2, border_radius=8)
        
        # Text
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

class LevelCard:
    def __init__(self, x, y, width, height, level_name):
        self.rect = pygame.Rect(x, y, width, height)
        self.level_name = level_name
        self.display_name = level_name.replace("Tally Hall - ", "").replace(" [", "\n[")
        self.hovered = False
        self.selected = False
        self.font_title = pygame.font.Font(None, 28)
        self.font_subtitle = pygame.font.Font(None, 20)
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.rect.collidepoint(event.pos):
                return True
        return False
    
    def draw(self, screen):
        # Card background with gradient effect
        base_color = CARD_COLOR
        if self.selected:
            base_color = SUCCESS_COLOR
        elif self.hovered:
            base_color = tuple(min(255, c + 20) for c in CARD_COLOR)
        
        # Shadow
        shadow_rect = self.rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        pygame.draw.rect(screen, (20, 20, 20), shadow_rect, border_radius=12)
        
        # Main card
        pygame.draw.rect(screen, base_color, self.rect, border_radius=12)
        
        # Border
        border_color = SUCCESS_COLOR if self.selected else (LIGHT_BLUE if self.hovered else MUTED_TEXT)
        pygame.draw.rect(screen, border_color, self.rect, 2, border_radius=12)
        
        # Text
        lines = self.display_name.split('\n')
        y_offset = self.rect.centery - (len(lines) * 12)
        
        for i, line in enumerate(lines):
            if i == 0:  # Title
                text_surface = self.font_title.render(line, True, TEXT_COLOR)
            else:  # Subtitle/difficulty
                text_surface = self.font_subtitle.render(line, True, MUTED_TEXT)
            
            text_rect = text_surface.get_rect(centerx=self.rect.centerx, y=y_offset + i * 24)
            screen.blit(text_surface, text_rect)

class ParticleSystem:
    def __init__(self):
        self.particles = []
    
    def add_particle(self, x, y, color=PRIMARY_COLOR):
        self.particles.append({
            'x': x,
            'y': y,
            'vx': (pygame.time.get_ticks() % 100 - 50) / 25.0,
            'vy': (pygame.time.get_ticks() % 80 - 40) / 20.0,
            'life': 60,
            'max_life': 60,
            'color': color,
            'size': 3
        })
    
    def update(self):
        for particle in self.particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['life'] -= 1
            particle['size'] = max(1, particle['size'] * 0.98)
            
            if particle['life'] <= 0:
                self.particles.remove(particle)
    
    def draw(self, screen):
        for particle in self.particles:
            alpha = int(255 * (particle['life'] / particle['max_life']))
            color = (*particle['color'], alpha)
            
            # Create surface for alpha blending
            size = int(particle['size'])
            if size > 0:
                surf = pygame.Surface((size * 2, size * 2))
                surf.set_alpha(alpha)
                pygame.draw.circle(surf, particle['color'], (size, size), size)
                screen.blit(surf, (particle['x'] - size, particle['y'] - size))

class MenuSystem:
    def __init__(self, screen, clock):
        self.screen = screen
        self.clock = clock
        self.state = MenuState.TITLE
        self.current_level = None
        self.selected_level_name = None
        self.preview_playing = False
        self.current_preview = None
        self.preview_sound = None
        self.preview_channel = None
        
        # Audio
        self.audio_candidates = None
        self.audio_candidate_choice = None
        self.audio_candidate_callback = None
        
        # Fonts
        self.title_font = pygame.font.Font(None, 72)
        self.subtitle_font = pygame.font.Font(None, 36)
        self.text_font = pygame.font.Font(None, 28)
        
        # Effects
        self.particles = ParticleSystem()
        self.animation_time = 0
        
        # Load levels
        self.levels = get_levels()
        
        # OSU import state
        self.osu_beatmaps = []
        self.osu_loading = False
        self.osu_loading_text = "Loading osu! beatmaps..."
        self.osu_scroll_offset = 0
        self.osu_converting = False
        self.osu_converting_text = ""
        
        # Create UI elements
        self.setup_ui()
    
    def setup_ui(self):
        # Title screen buttons
        button_width = 250
        button_height = 60
        center_x = SCREEN_WIDTH // 2 - button_width // 2

        self.play_button = Button(center_x, 280, button_width, button_height, "PLAY", PRIMARY_COLOR)
        self.import_button = Button(center_x, 360, button_width, button_height, "IMPORT OSU! SONGS", WARNING_COLOR)
        self.quit_button = Button(center_x, 440, button_width, button_height, "QUIT", ACCENT_COLOR)

        # Level select back button
        self.back_button = Button(50, 50, 120, 40, "← BACK", SECONDARY_COLOR, font_size=20)

        # Level cards
        self.level_cards = []
        cards_per_row = 2
        card_width = 320
        card_height = 120
        start_x = (SCREEN_WIDTH - (cards_per_row * card_width + (cards_per_row - 1) * 20)) // 2
        start_y = 150

        for i, level_name in enumerate(self.levels):
            row = i // cards_per_row
            col = i % cards_per_row
            x = start_x + col * (card_width + 20)
            y = start_y + row * (card_height + 20)
            self.level_cards.append(LevelCard(x, y, card_width, card_height, level_name))

        # OSU import UI
        self.setup_osu_import_ui()
    
    def draw_beatmap_list(self, start_y):
        """Draw the list of osu! beatmaps for import."""
        item_height = 70
        for i, beatmap in enumerate(self.osu_beatmaps):
            y = start_y + i * item_height - self.osu_scroll_offset
            if y < 100 or y > SCREEN_HEIGHT - 80:
                continue  # Skip items outside visible area
            rect = pygame.Rect(50, y, SCREEN_WIDTH - 100, item_height - 10)
            color = LIGHT_GRAY if self.osu_converting and i == self.audio_candidate_choice else CARD_COLOR
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            pygame.draw.rect(self.screen, LIGHT_BLUE, rect, 2, border_radius=8)
            # Beatmap info
            info = f"{beatmap['artist']} - {beatmap['title']} [{beatmap['version']}]"
            text_surface = self.text_font.render(info, True, TEXT_COLOR)
            self.screen.blit(text_surface, (rect.x + 16, rect.y + 16))

    def setup_osu_import_ui(self):
        """Setup UI elements for OSU import screen."""
        self.osu_back_button = Button(50, 50, 120, 40, "← BACK", SECONDARY_COLOR, font_size=20)
        self.osu_refresh_button = Button(200, 50, 150, 40, "REFRESH", PRIMARY_COLOR, font_size=20)

    def handle_events(self, event):
        if self.state == MenuState.TITLE:
            if self.play_button.handle_event(event):
                self.state = MenuState.LEVEL_SELECT
                return True
            if self.import_button.handle_event(event):
                self.state = MenuState.OSU_IMPORT
                self.load_osu_beatmaps()
                return True
            if self.quit_button.handle_event(event):
                pygame.quit()
                exit()
        elif self.state == MenuState.LEVEL_SELECT:
            if self.back_button.handle_event(event):
                self.state = MenuState.TITLE
                self.stop_preview()
                return True
            for card in self.level_cards:
                if card.handle_event(event):
                    self.selected_level_name = card.level_name
                    self.start_preview(card.level_name)
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        self.start_level(card.level_name)
                    return True
        elif self.state == MenuState.PLAYING:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.state = MenuState.LEVEL_SELECT
                self.stop_preview()
                return True
            if self.current_level:
                self.current_level.handle_events(event)
        elif self.state == MenuState.OSU_IMPORT:
            if self.osu_back_button.handle_event(event):
                self.state = MenuState.TITLE
                return True
            if self.osu_refresh_button.handle_event(event):
                self.load_osu_beatmaps()
                return True
            # Scroll with mouse wheel
            if event.type == pygame.MOUSEWHEEL:
                self.osu_scroll_offset -= event.y * 40
                self.osu_scroll_offset = max(0, self.osu_scroll_offset)
                return True
            # Handle audio candidate selection
            if self.audio_candidates:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    x, y = event.pos
                    box_width = SCREEN_WIDTH - 100
                    box_height = 60
                    start_y = 140
                    for i, candidate in enumerate(self.audio_candidates):
                        rect = pygame.Rect(50, start_y + i * (box_height + 10), box_width, box_height)
                        if rect.collidepoint(x, y):
                            self.audio_candidate_choice = i
                            if self.audio_candidate_callback:
                                self.audio_candidate_callback(i)
                            return True
            # Click on beatmap (only left mouse button, and not converting)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.osu_converting:
                x, y = event.pos
                idx = self.get_beatmap_at_position(x, y)
                if idx is not None:
                    self.convert_osu_beatmap(idx)
                    return True
            if self.audio_candidates:
                # Handle selection
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    box_width = SCREEN_WIDTH - 100
                    box_height = 60
                    start_y = 140
                    for i, candidate in enumerate(self.audio_candidates):
                        rect = pygame.Rect(50, start_y + i * (box_height + 10), box_width, box_height)
                        if rect.collidepoint(x, y):
                            self.audio_candidate_choice = i
                            if self.audio_candidate_callback:
                                self.audio_candidate_callback(i)
                            return True
        return False

    def start_preview(self, level_name):
        """Start playing a preview of the selected level"""
        try:
            if self.current_preview != level_name:
                # Stop any current preview
                self.stop_preview()
                
                audio_path = f"levels/{level_name}.wav"
                print(f"Starting preview for: {level_name}")
                
                # Try Sound first (more reliable)
                try:
                    self.preview_sound = pygame.mixer.Sound(audio_path)
                    self.preview_channel = self.preview_sound.play(loops=-1)  # Loop forever
                    self.preview_channel.set_volume(0.3)  # Lower volume
                    print(f"Preview playing via Sound: {self.preview_channel.get_busy()}")
                except:
                    # Fallback to music
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.set_volume(0.3)
                    pygame.mixer.music.play(-1)  # Loop forever
                    print(f"Preview playing via Music: {pygame.mixer.music.get_busy()}")
                
                self.preview_playing = True
                self.current_preview = level_name
                print(f"Successfully started preview for: {level_name}")
                
        except Exception as e:
            print(f"Could not preview audio file: {level_name} - Error: {e}")
    
    def stop_preview(self):
        """Stop the current preview"""
        if self.preview_playing:
            # Stop Sound preview
            if self.preview_channel:
                self.preview_channel.stop()
                self.preview_channel = None
            # Stop Music preview
            pygame.mixer.music.stop()
            
            self.preview_playing = False
            self.current_preview = None
            self.preview_sound = None
    
    def start_level(self, level_name):
        self.stop_preview()  # Stop preview before starting level
        self.current_level = Level(level_name)
        self.current_level.play()
        self.state = MenuState.PLAYING
    
    def load_osu_beatmaps(self):
        """Load osu! beatmaps in a separate thread."""
        import threading
        if self.osu_loading:
            return
        self.osu_loading = True
        self.osu_beatmaps = []

        def load_thread():
            try:
                db = OsuLazerDatabase()
                beatmaps = db.list_beatmaps()
                self.osu_beatmaps = beatmaps
                self.osu_loading_text = f"Found {len(beatmaps)} beatmaps. Click to convert."
            except Exception as e:
                self.osu_loading_text = f"Error loading osu!lazer: {e}"
            self.osu_loading = False

        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()

    def get_beatmap_at_position(self, x, y):
        """Get the beatmap index at the given mouse position."""
        start_y = 120
        item_height = 70
        if x < 50 or x > SCREEN_WIDTH - 50:
            return None
        adjusted_y = y + self.osu_scroll_offset - start_y
        if adjusted_y < 0:
            return None
        beatmap_index = int(adjusted_y // item_height)
        if 0 <= beatmap_index < len(self.osu_beatmaps):
            return beatmap_index
        return None

    def convert_osu_beatmap(self, beatmap_index):
        """Convert selected osu! beatmap to BTMP format."""
        import threading
        if self.osu_converting or beatmap_index >= len(self.osu_beatmaps):
            return
        selected = self.osu_beatmaps[beatmap_index]
        self.osu_converting = True
        self.osu_converting_text = f"Converting {selected['artist']} - {selected['title']}..."
        self.audio_candidates = None
        self.audio_candidate_choice = None
        self.audio_candidate_callback = None

        def convert_thread():
            try:
                # Patch: convert_from_lazer expects 1-based index, but our list is 0-based
                # Instead of using convert_from_lazer directly, we reimplement the audio selection logic here
                db = OsuLazerDatabase()
                beatmaps = db.list_beatmaps()
                selected = beatmaps[beatmap_index]
                # Find audio candidates
                candidates = db.find_audio_file_for_beatmap(selected['audio_filename'], selected['file_path'], return_candidates=True)
                if candidates and len(candidates) > 1:
                    # Show graphical selection
                    self.audio_candidates = candidates
                    self.audio_candidate_choice = None
                    self.audio_candidate_callback = lambda idx: self.finish_audio_selection(idx, selected, db)
                    self.osu_converting_text = "Multiple audio files found. Please select one below."
                    return
                elif candidates and len(candidates) == 1:
                    self.finish_audio_selection(0, selected, db)
                else:
                    self.finish_audio_selection(None, selected, db)
            except Exception as e:
                self.osu_converting_text = f"Error: {e}"
            self.osu_converting = False

        thread = threading.Thread(target=convert_thread)
        thread.daemon = True
        thread.start()

    def finish_audio_selection(self, idx, selected, db):
        # Actually convert the beatmap and copy the selected audio file
        try:
            # Generate output filename
            import re, os, shutil
            # Remove any null bytes from strings before using them
            safe_title = re.sub(r'[\x00-\x1F\x7F]', '', selected['title'])
            safe_title = re.sub(r'[^\w\s-]', '', safe_title).strip()
            safe_artist = re.sub(r'[\x00-\x1F\x7F]', '', selected['artist'])
            safe_artist = re.sub(r'[^\w\s-]', '', safe_artist).strip()
            safe_version = re.sub(r'[\x00-\x1F\x7F]', '', selected['version'])
            safe_version = re.sub(r'[^\w\s-]', '', safe_version).strip()
            output_name = f"{safe_artist} - {safe_title} [{safe_version}]"
            output_path = os.path.join("levels", output_name + '.btmp')
            os.makedirs("levels", exist_ok=True)
            converter = OsuConverter()
            converter.parse_osu_content(selected['content'])
            converter.convert_to_btmp(output_path)
            # Copy audio file
            if self.audio_candidates and idx is not None and idx < len(self.audio_candidates):
                audio_source = self.audio_candidates[idx]['path']
                audio_dest = os.path.join("levels", output_name + '.wav')
                shutil.copy2(audio_source, audio_dest)
                self.osu_converting_text = f"Conversion complete! Audio file copied."
            else:
                self.osu_converting_text = f"Conversion complete! No audio file copied."
            self.levels = get_levels()
            self.setup_ui()
        except Exception as e:
            self.osu_converting_text = f"Error: {e}"
        self.osu_converting = False
        self.audio_candidates = None
        self.audio_candidate_choice = None
        self.audio_candidate_callback = None

    def update(self):
        self.animation_time += self.clock.get_time()
        self.particles.update()
        
        # Add occasional particles on title screen
        if self.state == MenuState.TITLE and pygame.time.get_ticks() % 30 == 0:
            x = pygame.time.get_ticks() % SCREEN_WIDTH
            y = 100 + (pygame.time.get_ticks() % 50)
            self.particles.add_particle(x, y, LIGHT_BLUE)
    
    def draw_gradient_background(self, color1, color2):
        for y in range(SCREEN_HEIGHT):
            ratio = y / SCREEN_HEIGHT
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            pygame.draw.line(self.screen, (r, g, b), (0, y), (SCREEN_WIDTH, y))
    
    def draw(self):
        if self.state == MenuState.TITLE:
            self.draw_title_screen()
        elif self.state == MenuState.LEVEL_SELECT:
            self.draw_level_select()
        elif self.state == MenuState.OSU_IMPORT:
            self.draw_osu_import()
        elif self.state == MenuState.PLAYING:
            self.draw_game()
    
    def draw_title_screen(self):
        # Gradient background
        self.draw_gradient_background(BACKGROUND_COLOR, SECONDARY_COLOR)
        
        # Enhanced animated title with osu! style
        title_y = 150 + math.sin(self.animation_time / 1000) * 10
        
        # Multi-layered title effect
        title_text = "RHYTHM MANIA"
        
        # Outer glow
        for offset in range(8, 0, -1):
            alpha = max(20, 100 - offset * 10)
            glow_font = pygame.font.Font(None, 72 + offset)
            glow_text = glow_font.render(title_text, True, PRIMARY_COLOR)
            glow_text.set_alpha(alpha)
            glow_rect = glow_text.get_rect(center=(SCREEN_WIDTH // 2, title_y))
            self.screen.blit(glow_text, glow_rect)
        
        # Main title with gradient effect
        main_title = self.title_font.render(title_text, True, TEXT_COLOR)
        title_rect = main_title.get_rect(center=(SCREEN_WIDTH // 2, title_y))
        
        # Title shadow
        shadow_text = self.title_font.render(title_text, True, (10, 10, 15))
        shadow_rect = shadow_text.get_rect(center=(SCREEN_WIDTH // 2 + 4, title_y + 4))
        self.screen.blit(shadow_text, shadow_rect)
        self.screen.blit(main_title, title_rect)
        
        # Sparkle effects around title
        for i in range(3):
            sparkle_x = SCREEN_WIDTH // 2 + math.sin(self.animation_time / 800 + i * 2) * 200
            sparkle_y = title_y + math.cos(self.animation_time / 600 + i * 1.5) * 30
            sparkle_size = 3 + math.sin(self.animation_time / 200 + i) * 2
            sparkle_color = [PRIMARY_COLOR, SUCCESS_COLOR, WARNING_COLOR][i]
            pygame.draw.circle(self.screen, sparkle_color, (int(sparkle_x), int(sparkle_y)), int(sparkle_size))
        
        # Subtitle
        subtitle_text = self.subtitle_font.render("Made by Natch", True, MUTED_TEXT)
        subtitle_rect = subtitle_text.get_rect(center=(SCREEN_WIDTH // 2, title_y + 60))
        self.screen.blit(subtitle_text, subtitle_rect)
        
        # Buttons
        self.play_button.draw(self.screen)
        self.import_button.draw(self.screen)
        self.quit_button.draw(self.screen)
        
        # Particles
        self.particles.draw(self.screen)
        
        # Instructions
        instruction_text = self.text_font.render("Use D, F, J, K keys to play", True, MUTED_TEXT)
        instruction_rect = instruction_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        self.screen.blit(instruction_text, instruction_rect)
    
    def draw_level_select(self):
        # Gradient background
        self.draw_gradient_background(BACKGROUND_COLOR, SECONDARY_COLOR)
        
        # Title
        title_text = self.subtitle_font.render("SELECT LEVEL", True, TEXT_COLOR)
        title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, 100))
        self.screen.blit(title_text, title_rect)
        
        # Back button
        self.back_button.draw(self.screen)
        
        # Level cards
        for card in self.level_cards:
            card.draw(self.screen)
        
        # Instructions
        if self.selected_level_name:
            instruction_text = self.text_font.render("Press ENTER to start selected level", True, SUCCESS_COLOR)
        else:
            instruction_text = self.text_font.render("Click on a level to select it", True, MUTED_TEXT)
        instruction_rect = instruction_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        self.screen.blit(instruction_text, instruction_rect)
        
        # Particles
        self.particles.draw(self.screen)
    
    def draw_game(self):
        if self.current_level:
            self.current_level.draw(self.screen)
            
            # Add pause instruction
            font = pygame.font.Font(None, 24)
            pause_text = font.render("Press ESC to return to menu", True, WHITE)
            self.screen.blit(pause_text, (SCREEN_WIDTH - 250, 10))
    
    def draw_osu_import(self):
        self.draw_gradient_background(BACKGROUND_COLOR, SECONDARY_COLOR)
        # Title
        title_surface = self.title_font.render("Import osu!lazer Beatmaps", True, TEXT_COLOR)
        self.screen.blit(title_surface, (SCREEN_WIDTH // 2 - title_surface.get_width() // 2, 30))
        # Back and refresh buttons
        self.osu_back_button.draw(self.screen)
        self.osu_refresh_button.draw(self.screen)
        # Loading text or beatmap list
        if self.osu_loading:
            loading_surface = self.subtitle_font.render(self.osu_loading_text, True, WARNING_COLOR)
            self.screen.blit(loading_surface, (SCREEN_WIDTH // 2 - loading_surface.get_width() // 2, 100))
        elif self.audio_candidates:
            self.draw_audio_candidate_selection()
        else:
            self.draw_beatmap_list(120)
            if self.osu_converting:
                converting_surface = self.subtitle_font.render(self.osu_converting_text, True, ACCENT_COLOR)
                self.screen.blit(converting_surface, (SCREEN_WIDTH // 2 - converting_surface.get_width() // 2, SCREEN_HEIGHT - 60))

    def draw_audio_candidate_selection(self):
        # Draw graphical selection for audio candidates
        box_width = SCREEN_WIDTH - 100
        box_height = 60
        start_y = 140
        for i, candidate in enumerate(self.audio_candidates):
            y = start_y + i * (box_height + 10)
            rect = pygame.Rect(50, y, box_width, box_height)
            color = LIGHT_BLUE if self.audio_candidate_choice == i else CARD_COLOR
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            pygame.draw.rect(self.screen, LIGHT_GRAY, rect, 2, border_radius=10)
            # Candidate info
            info = f"{os.path.basename(candidate['path'])} | Score: {candidate['score']:.1f} | Size: {candidate['size'] // 1024} KB"
            text_surface = self.text_font.render(info, True, TEXT_COLOR)
            self.screen.blit(text_surface, (rect.x + 16, rect.y + 12))
        # Instructions
        inst_surface = self.subtitle_font.render("Select the correct audio file for this beatmap:", True, WARNING_COLOR)
        self.screen.blit(inst_surface, (SCREEN_WIDTH // 2 - inst_surface.get_width() // 2, 100))

    def handle_events(self, event):
        if self.state == MenuState.TITLE:
            if self.play_button.handle_event(event):
                self.state = MenuState.LEVEL_SELECT
                return True
            if self.import_button.handle_event(event):
                self.state = MenuState.OSU_IMPORT
                self.load_osu_beatmaps()
                return True
            if self.quit_button.handle_event(event):
                pygame.quit()
                exit()
        elif self.state == MenuState.LEVEL_SELECT:
            if self.back_button.handle_event(event):
                self.state = MenuState.TITLE
                self.stop_preview()
                return True
            for card in self.level_cards:
                if card.handle_event(event):
                    self.selected_level_name = card.level_name
                    self.start_preview(card.level_name)
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        self.start_level(card.level_name)
                    return True
        elif self.state == MenuState.PLAYING:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.state = MenuState.LEVEL_SELECT
                self.stop_preview()
                return True
            if self.current_level:
                self.current_level.handle_events(event)
        elif self.state == MenuState.OSU_IMPORT:
            if self.osu_back_button.handle_event(event):
                self.state = MenuState.TITLE
                return True
            if self.osu_refresh_button.handle_event(event):
                self.load_osu_beatmaps()
                return True
            # Scroll with mouse wheel
            if event.type == pygame.MOUSEWHEEL:
                self.osu_scroll_offset -= event.y * 40
                self.osu_scroll_offset = max(0, self.osu_scroll_offset)
                return True
            # Click on beatmap
            if event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                idx = self.get_beatmap_at_position(x, y)
                if idx is not None:
                    self.convert_osu_beatmap(idx)
                    return True
            if self.audio_candidates:
                # Handle selection
                if event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = event.pos
                    box_width = SCREEN_WIDTH - 100
                    box_height = 60
                    start_y = 140
                    for i, candidate in enumerate(self.audio_candidates):
                        rect = pygame.Rect(50, start_y + i * (box_height + 10), box_width, box_height)
                        if rect.collidepoint(x, y):
                            self.audio_candidate_choice = i
                            if self.audio_candidate_callback:
                                self.audio_candidate_callback(i)
                            return True
        return False

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    result = self.handle_events(event)
                    if result == "quit":
                        running = False
                    elif result == "start_level":
                        self.start_level(self.selected_level_name)
            
            self.update()
            self.draw()
            pygame.display.flip()
            self.clock.tick(60)
        
        pygame.quit()
        return False
