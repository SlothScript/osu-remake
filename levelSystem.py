# Format:
# levelName.btmp
# text:
# line 1: time in seconds
# line 2: bpm
# Lines with # are comments and ignored
# each subsequent line is a beat
# Beat format: k t b [ht]
# k = key - 1 = d 4 = k
# t = type
# b = beat hit on
# ht = hold time. Only required for t = 1
import pygame
import os
import math
import numpy as np

pygame.init()
# Initialize mixer with specific settings for better compatibility
pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
pygame.mixer.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (231, 76, 60)
GREEN = (46, 204, 113)
BLUE = (52, 152, 219)
YELLOW = (241, 196, 15)
GRAY = (149, 165, 166)
LIGHT_GRAY = (236, 240, 241)
DARK_GRAY = (52, 73, 94)
PURPLE = (155, 89, 182)

# OSU-inspired color palette
OSU_PINK = (255, 102, 170)
OSU_BLUE = (102, 170, 255)
OSU_ORANGE = (255, 170, 102)
OSU_GREEN = (102, 255, 170)
OSU_PURPLE = (170, 102, 255)

# Enhanced neon colors
NEON_RED = (255, 50, 100)
NEON_GREEN = (50, 255, 150)
NEON_BLUE = (100, 150, 255)
NEON_YELLOW = (255, 220, 50)
NEON_PURPLE = (200, 100, 255)
NEON_CYAN = (50, 255, 255)
NEON_ORANGE = (255, 150, 50)

# Modern gradient colors with more vibrant osu! style
GRADIENT_RED = [(255, 120, 170), (255, 60, 120)]
GRADIENT_GREEN = [(120, 255, 200), (60, 255, 160)]
GRADIENT_BLUE = [(170, 200, 255), (120, 160, 255)]
GRADIENT_YELLOW = [(255, 240, 120), (255, 200, 60)]
GRADIENT_PURPLE = [(220, 120, 255), (180, 80, 255)]

# Background colors with better contrast
BACKGROUND_DARK = (25, 25, 40)
BACKGROUND_MID = (35, 35, 55)
LANE_INACTIVE = (45, 45, 65)
LANE_ACTIVE = (65, 65, 95)
LANE_PRESSED = (85, 85, 125)

# Game settings
LANE_WIDTH = 80
LANE_HEIGHT = 500
HIT_LINE_Y = 450
NOTE_WIDTH = 60
NOTE_HEIGHT = 20
APPROACH_TIME = 1000  # milliseconds before hit
AUDIO_OFFSET = 0  # milliseconds to sync audio with visuals (negative = delay visuals)
INTRO_BEATS = 4  # Number of beats to wait before first notes (OSU-style)

# Hit timing windows (in milliseconds)
PERFECT_WINDOW = 50
GOOD_WINDOW = 100
BAD_WINDOW = 150

# Score values
PERFECT_SCORE = 300
GOOD_SCORE = 100
BAD_SCORE = 50
COMBO_MULTIPLIER = 1.2

def read_level(levelName):
    with open("levels/" + levelName + ".btmp", "r") as file:
        lines = file.readlines()
    lines = [line.strip() for line in lines if not line.startswith("#") and line.strip()]
    time = float(lines[0].strip())
    bpm = float(lines[1].strip())
    beats = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        key = int(parts[0])
        beat_type = int(parts[1])
        beat_hit = float(parts[2]) # beat can be like 1.25 for example
        hold_time = float(parts[3]) if len(parts) > 3 else 0 # You can also hold it to for like 1.5 beats
        beats.append((key, beat_type, beat_hit, hold_time))
    return time, bpm, beats

def get_levels():
    levels = []
    if not os.path.exists("levels"):
        os.makedirs("levels")
        return levels
    for filename in os.listdir("levels"):
        if filename.endswith(".btmp"):
            level_name = filename[:-5]  # Remove the .btmp extension
            levels.append(level_name)
    return levels

class Level:
    def __init__(self, name):
        self.name = name
        self.time, self.bpm, self.beats = read_level(name)
        self.start_time = 0
        self.key_states = {pygame.K_d: False, pygame.K_f: False, pygame.K_j: False, pygame.K_k: False}
        self.key_colors = {1: OSU_PINK, 2: OSU_GREEN, 3: OSU_BLUE, 4: OSU_ORANGE}
        self.key_colors_dim = {1: NEON_RED, 2: NEON_GREEN, 3: NEON_BLUE, 4: NEON_YELLOW}
        self.key_positions = {1: 200, 2: 300, 3: 400, 4: 500}  # X positions for lanes
        self.hit_effects = []  # Store hit effects
        
        # Score system
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.perfect_hits = 0
        self.good_hits = 0
        self.bad_hits = 0
        self.misses = 0
        self.total_notes = len(self.beats)
        
        # Track which beats have been hit/missed
        self.hit_beats = set()
        self.judgment_effects = []  # Store judgment text effects
        self.active_holds = {}  # Track currently active hold notes
        self.hold_ends = set()  # Track which hold ends have been scored
        
        # Audio
        self.sound = None
        self.channel = None
        
        # Enhanced visuals
        self.key_gradients = {1: GRADIENT_RED, 2: GRADIENT_GREEN, 3: GRADIENT_BLUE, 4: GRADIENT_YELLOW}
        
        # OSU-style circular elements
        self.note_radius = 30
        self.approach_circle_max = 60
        self.particle_systems = {1: [], 2: [], 3: [], 4: []}
        self.burst_effects = []
        
        # Sound effects
        self.load_sound_effects()
    
    def load_sound_effects(self):
        """Load sound effects for hits and misses"""
        try:
            # Create simple tones using pygame (no external files needed)
            self.hit_sounds = {}
            self.miss_sound = None
            
            # Generate simple hit sounds for each lane
            for key in range(1, 5):
                frequency = 440 + (key * 110)  # A4, B4, C5, D5
                duration = 0.1
                sample_rate = 22050
                frames = int(duration * sample_rate)
                
                # Generate sine wave using numpy
                t = np.linspace(0, duration, frames, False)
                wave = np.sin(frequency * 2 * np.pi * t) * 0.3
                
                # Convert to stereo array
                stereo_wave = np.array([wave, wave]).T
                sound_array = pygame.sndarray.make_sound((stereo_wave * 32767).astype(np.int16))
                self.hit_sounds[key] = sound_array
            
            print("Sound effects loaded successfully")
        except Exception as e:
            print(f"Could not load sound effects: {e}")
            self.hit_sounds = {}
            self.miss_sound = None
    
    def play_hit_sound(self, key_num, judgment):
        """Play appropriate sound for hit"""
        try:
            if key_num in self.hit_sounds:
                if judgment == "PERFECT":
                    # Play at normal volume for perfect hits
                    self.hit_sounds[key_num].set_volume(0.6)
                elif judgment == "GOOD":
                    self.hit_sounds[key_num].set_volume(0.4)
                elif judgment == "BAD":
                    self.hit_sounds[key_num].set_volume(0.2)
                else:  # MISS
                    self.hit_sounds[key_num].set_volume(0.1)
                
                self.hit_sounds[key_num].play()
        except Exception as e:
            print(f"Could not play hit sound: {e}")
        
    def play(self):
        try:
            audio_path = "levels/" + self.name + ".wav"
            print(f"Attempting to load: {audio_path}")
            
            # First try with pygame.mixer.Sound for better compatibility
            try:
                self.sound = pygame.mixer.Sound(audio_path)
                self.channel = self.sound.play()
                print(f"Successfully loaded as Sound: {audio_path}")
                print(f"Sound length: {self.sound.get_length()} seconds")
                print(f"Channel playing: {self.channel.get_busy()}")
            except:
                # Fallback to music module
                print("Sound failed, trying music module...")
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.set_volume(1.0)
                pygame.mixer.music.play(loops=0, start=0.0)
                print(f"Music module playing: {pygame.mixer.music.get_busy()}")
            
            self.start_time = pygame.time.get_ticks()
            print(f"Audio playback started successfully")
            
        except Exception as e:
            print(f"Could not load audio file: {audio_path} - Error: {e}")
            print(f"Available mixer info: {pygame.mixer.get_init()}")
            self.start_time = pygame.time.get_ticks()
    
    def handle_events(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in self.key_states:
                self.key_states[event.key] = True
                key_num = {pygame.K_d: 1, pygame.K_f: 2, pygame.K_j: 3, pygame.K_k: 4}[event.key]
                self.check_hit(key_num)
        elif event.type == pygame.KEYUP:
            if event.key in self.key_states:
                self.key_states[event.key] = False
                key_num = {pygame.K_d: 1, pygame.K_f: 2, pygame.K_j: 3, pygame.K_k: 4}[event.key]
                self.check_hold_release(key_num)
    
    def check_hit(self, key_num):
        current_time = pygame.time.get_ticks() - self.start_time + AUDIO_OFFSET
        beat_duration = 60000 / self.bpm
        
        closest_beat = None
        closest_distance = float('inf')
        closest_index = -1
        
        # Find the closest unhit beat for this key
        for i, beat in enumerate(self.beats):
            beat_key, beat_type, beat_hit, hold_time = beat
            if beat_key == key_num and i not in self.hit_beats:
                intro_delay = INTRO_BEATS * beat_duration
                beat_time = beat_hit * beat_duration + intro_delay
                distance = abs(current_time - beat_time)
                if distance < closest_distance and distance <= BAD_WINDOW:
                    closest_distance = distance
                    closest_beat = beat
                    closest_index = i
        
        if closest_beat:
            beat_key, beat_type, beat_hit, hold_time = closest_beat
            self.hit_beats.add(closest_index)
            judgment = self.get_judgment(closest_distance)
            self.add_score(judgment)
            self.add_hit_effect(key_num, judgment)
            
            # If it's a hold note, track it
            if beat_type == 1 and hold_time > 0:
                beat_duration = 60000 / self.bpm
                intro_delay = INTRO_BEATS * beat_duration
                hold_end_time = (beat_hit + hold_time) * beat_duration + intro_delay
                self.active_holds[key_num] = {
                    'index': closest_index,
                    'end_time': hold_end_time,
                    'hit_start': True
                }
    
    def check_hold_release(self, key_num):
        """Check if a hold note was released at the right time"""
        if key_num in self.active_holds:
            current_time = pygame.time.get_ticks() - self.start_time + AUDIO_OFFSET
            hold_info = self.active_holds[key_num]
            end_time = hold_info['end_time']
            hold_index = hold_info['index']
            
            # Check if release was close to the end time
            distance = abs(current_time - end_time)
            
            # Only score the end if we haven't already
            if hold_index not in self.hold_ends:
                self.hold_ends.add(hold_index)
                judgment = self.get_judgment(distance)
                self.add_score(judgment)
                self.add_hit_effect(key_num, judgment)
            
            # Remove from active holds
            del self.active_holds[key_num]
    
    def get_judgment(self, distance):
        if distance <= PERFECT_WINDOW:
            return "PERFECT"
        elif distance <= GOOD_WINDOW:
            return "GOOD"
        elif distance <= BAD_WINDOW:
            return "BAD"
        return "MISS"
    
    def add_score(self, judgment):
        if judgment == "PERFECT":
            self.perfect_hits += 1
            base_score = PERFECT_SCORE
            self.combo += 1
        elif judgment == "GOOD":
            self.good_hits += 1
            base_score = GOOD_SCORE
            self.combo += 1
        elif judgment == "BAD":
            self.bad_hits += 1
            base_score = BAD_SCORE
            self.combo += 1
        else:  # MISS
            self.misses += 1
            base_score = 0
            self.combo = 0
        
        if self.combo > self.max_combo:
            self.max_combo = self.combo
        
        # Apply combo multiplier
        if self.combo > 0:
            multiplier = 1 + (self.combo * 0.01)  # 1% per combo
            self.score += int(base_score * multiplier)
        else:
            self.score += base_score
    
    def add_burst_effect(self, x, y, color, intensity=1.0):
        """Add a simplified burst effect with fewer particles"""
        particle_count = int(8 * intensity)  # Reduced from 20 to 8
        for i in range(particle_count):
            angle = (i / particle_count) * 2 * math.pi
            speed = 1.5 + (i % 2)  # Reduced speed
            self.burst_effects.append({
                'x': x,
                'y': y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': 20,  # Reduced from 30
                'max_life': 20,
                'color': color,
                'size': 3 if intensity > 0.8 else 2  # Smaller particles
            })

    def add_hit_effect(self, key_num, judgment):
        x, y = self.key_positions[key_num], HIT_LINE_Y
        
        # Original hit effect
        self.hit_effects.append({
            'x': x,
            'y': y,
            'time': pygame.time.get_ticks(),
            'color': self.key_colors[key_num]
        })
        
        # Add burst effect based on judgment quality
        intensity_map = {"PERFECT": 1.5, "GOOD": 1.0, "BAD": 0.6, "MISS": 0.3}
        intensity = intensity_map.get(judgment, 0.5)
        self.add_burst_effect(x, y, self.key_colors[key_num], intensity)
        
        # Play hit sound
        self.play_hit_sound(key_num, judgment)
        
        # Add judgment text effect with enhanced colors
        judgment_colors = {
            "PERFECT": NEON_CYAN,     # Bright cyan
            "GOOD": NEON_GREEN,       # Bright green
            "BAD": NEON_YELLOW,       # Bright yellow
            "MISS": NEON_RED          # Bright red
        }
        
        self.judgment_effects.append({
            'text': judgment,
            'x': x,
            'y': y - 50,
            'time': pygame.time.get_ticks(),
            'color': judgment_colors.get(judgment, WHITE),
            'judgment': judgment
        })
    
    def check_misses(self):
        current_time = pygame.time.get_ticks() - self.start_time + AUDIO_OFFSET
        beat_duration = 60000 / self.bpm
        
        for i, beat in enumerate(self.beats):
            if i not in self.hit_beats:
                beat_key, beat_type, beat_hit, hold_time = beat
                intro_delay = INTRO_BEATS * beat_duration
                beat_time = beat_hit * beat_duration + intro_delay
                if current_time > beat_time + BAD_WINDOW:
                    self.hit_beats.add(i)
                    self.add_score("MISS")
                    self.add_hit_effect(beat_key, "MISS")
        
        # Check for missed hold note ends
        for i, beat in enumerate(self.beats):
            beat_key, beat_type, beat_hit, hold_time = beat
            if beat_type == 1 and hold_time > 0 and i not in self.hold_ends:
                intro_delay = INTRO_BEATS * beat_duration
                hold_end_time = (beat_hit + hold_time) * beat_duration + intro_delay
                if current_time > hold_end_time + BAD_WINDOW:
                    self.hold_ends.add(i)
                    self.add_score("MISS")
                    self.add_hit_effect(beat_key, "MISS")
                    # Remove from active holds if still there
                    if beat_key in self.active_holds:
                        del self.active_holds[beat_key]
    
    def get_accuracy(self):
        total_hits = self.perfect_hits + self.good_hits + self.bad_hits + self.misses
        if total_hits == 0:
            return 100.0
        return ((self.perfect_hits * 1.0 + self.good_hits * 0.5 + self.bad_hits * 0.1) / total_hits) * 100
    
    def draw_gradient_background(self, screen):
        """Draw a beautiful gradient background"""
        for y in range(SCREEN_HEIGHT):
            ratio = y / SCREEN_HEIGHT
            # Create more complex gradient with multiple colors
            if ratio < 0.3:
                # Top section - dark blue to purple
                local_ratio = ratio / 0.3
                r = int(BACKGROUND_DARK[0] * (1 - local_ratio) + BACKGROUND_MID[0] * local_ratio)
                g = int(BACKGROUND_DARK[1] * (1 - local_ratio) + BACKGROUND_MID[1] * local_ratio)
                b = int(BACKGROUND_DARK[2] * (1 - local_ratio) + BACKGROUND_MID[2] * local_ratio)
            else:
                # Bottom section - darker fade
                local_ratio = (ratio - 0.3) / 0.7
                r = int(BACKGROUND_MID[0] * (1 - local_ratio) + BLACK[0] * local_ratio)
                g = int(BACKGROUND_MID[1] * (1 - local_ratio) + BLACK[1] * local_ratio)
                b = int(BACKGROUND_MID[2] * (1 - local_ratio) + BLACK[2] * local_ratio)
            pygame.draw.line(screen, (r, g, b), (0, y), (SCREEN_WIDTH, y))
    
    def draw_background_effects(self, screen, current_time):
        """Draw simplified background effects for better performance"""
        beat_duration = 60000 / self.bpm
        beat_progress = (current_time % beat_duration) / beat_duration
        
        # Simple pulse effect on beat (reduced intensity)
        if beat_progress < 0.1:  # First 10% of beat
            intensity = (0.1 - beat_progress) / 0.1
            alpha = int(20 * intensity)  # Reduced from 40
            pulse_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            if self.combo > 50:
                pulse_color = (*OSU_PINK, alpha)
            elif self.combo > 20:
                pulse_color = (*OSU_BLUE, alpha)
            else:
                pulse_color = (*OSU_PURPLE, alpha//2)
            pulse_surface.fill(pulse_color)
            screen.blit(pulse_surface, (0, 0))
        
        # Simplified floating elements (reduced from 5 to 2)
        for i in range(2):
            t = current_time / 2000 + i * 2  # Slower movement
            x = (math.sin(t) * 150 + SCREEN_WIDTH/2 + i * 200) % SCREEN_WIDTH
            y = 150 + i * 250
            alpha = 20  # Fixed alpha for performance
            
            radius = 12  # Fixed size
            color = [OSU_BLUE, OSU_PURPLE][i]
            
            # Simple circles only
            circle_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            circle_surface.fill((*color, alpha))
            pygame.draw.circle(circle_surface, color, (radius, radius), radius)
            circle_surface.set_alpha(alpha)
            screen.blit(circle_surface, (x - radius, y - radius))
    
    def draw_gradient_rect(self, screen, rect, color1, color2):
        """Draw a rectangle with vertical gradient"""
        for y in range(rect.height):
            ratio = y / rect.height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            pygame.draw.line(screen, (r, g, b), 
                           (rect.x, rect.y + y), 
                           (rect.x + rect.width, rect.y + y))
    
    def draw(self, screen):
        current_time = pygame.time.get_ticks() - self.start_time + AUDIO_OFFSET
        beat_duration = 60000 / self.bpm  # milliseconds per beat
        
        # Check for missed notes
        self.check_misses()
        
        # Draw gradient background
        self.draw_gradient_background(screen)
        
        # Draw background effects
        self.draw_background_effects(screen, current_time)
        
        # Draw enhanced lanes with better visual hierarchy
        for i in range(1, 5):
            x = self.key_positions[i]
            key_pressed = self.key_states[{1: pygame.K_d, 2: pygame.K_f, 3: pygame.K_j, 4: pygame.K_k}[i]]
            
            # Lane background with subtle gradient
            lane_color = LANE_PRESSED if key_pressed else (LANE_ACTIVE if any(self.key_states.values()) else LANE_INACTIVE)
            lane_rect = pygame.Rect(x - LANE_WIDTH//2, 50, LANE_WIDTH, LANE_HEIGHT)
            
            # Draw lane with vertical gradient
            for y in range(lane_rect.height):
                ratio = y / lane_rect.height
                if key_pressed:
                    # Bright when pressed
                    color = [int(lane_color[j] + (255 - lane_color[j]) * 0.3 * (1 - ratio)) for j in range(3)]
                else:
                    # Normal gradient
                    color = [int(lane_color[j] * (1 + ratio * 0.2)) for j in range(3)]
                pygame.draw.line(screen, color, (lane_rect.x, lane_rect.y + y), (lane_rect.x + lane_rect.width, lane_rect.y + y))
            
            # Lane borders
            border_color = self.key_colors[i] if key_pressed else GRAY
            pygame.draw.rect(screen, border_color, lane_rect, 2)
            
            # Simple lane glow effect when pressed
            if key_pressed:
                glow_width = LANE_WIDTH + 16
                glow_surface = pygame.Surface((glow_width, LANE_HEIGHT), pygame.SRCALPHA)
                glow_color = (*self.key_colors[i], 25)
                glow_surface.fill(glow_color)
                screen.blit(glow_surface, (x - glow_width//2, 50))
            
            # OSU-style circular key indicator
            key_center_y = HIT_LINE_Y
            key_radius = 25
            key_color = self.key_colors[i]
            
            # Shadow
            shadow_surface = pygame.Surface((key_radius * 2 + 6, key_radius * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(shadow_surface, (0, 0, 0, 80), (key_radius + 3, key_radius + 3), key_radius)
            screen.blit(shadow_surface, (x - key_radius - 3, key_center_y - key_radius - 3))
            
            # Main circle with gradient
            gradient = self.key_gradients[i]
            for r in range(key_radius, 0, -1):
                ratio = r / key_radius
                if key_pressed:
                    # Brighter when pressed
                    grad_color = [min(255, int(gradient[0][j] * ratio + gradient[1][j] * (1 - ratio) + 50)) for j in range(3)]
                else:
                    grad_color = [int(gradient[0][j] * ratio + gradient[1][j] * (1 - ratio)) for j in range(3)]
                pygame.draw.circle(screen, grad_color, (x, key_center_y), r)
            
            # Outer border
            border_width = 4 if key_pressed else 2
            pygame.draw.circle(screen, WHITE if key_pressed else LIGHT_GRAY, (x, key_center_y), key_radius, border_width)
            
            # Key letter in center
            key_letter = ['D', 'F', 'J', 'K'][i-1]
            key_font = pygame.font.Font(None, 24)
            key_text = key_font.render(key_letter, True, WHITE)
            key_text_rect = key_text.get_rect(center=(x, key_center_y))
            screen.blit(key_text, key_text_rect)
            
            # Pulse effect when pressed
            if key_pressed:
                pulse_radius = key_radius + 8
                pulse_surface = pygame.Surface((pulse_radius * 2, pulse_radius * 2), pygame.SRCALPHA)
                pulse_alpha = abs(int(60 * math.sin(current_time / 100)))
                # Create a color with alpha by drawing on SRCALPHA surface
                pulse_color = key_color
                pygame.draw.circle(pulse_surface, pulse_color, (pulse_radius, pulse_radius), pulse_radius, 3)
                pulse_surface.set_alpha(pulse_alpha)
                screen.blit(pulse_surface, (x - pulse_radius, key_center_y - pulse_radius))
        
        # Enhanced hit line with osu!-style design
        hit_line_start = 150
        hit_line_width = 400
        hit_line_height = 6
        hit_rect = pygame.Rect(hit_line_start, HIT_LINE_Y - hit_line_height//2, hit_line_width, hit_line_height)
        
        # Animated glow based on combo
        glow_intensity = min(1.0, self.combo / 100)  # Max at 100 combo
        glow_color = OSU_PINK if self.combo > 50 else OSU_BLUE if self.combo > 20 else OSU_PURPLE
        
        # Simple glow effect (reduced complexity)
        for width in range(1, 6):  # Reduced from 15 to 6
            alpha = max(5, int((30 * glow_intensity) // width))  # Reduced intensity
            glow_rect = pygame.Rect(hit_line_start - width, HIT_LINE_Y - width//2, hit_line_width + width*2, width)
            glow_surface = pygame.Surface((hit_line_width + width*2, width), pygame.SRCALPHA)
            glow_surface.fill((*glow_color, alpha))
            screen.blit(glow_surface, (hit_line_start - width, HIT_LINE_Y - width//2))
        
        # Main hit line with dynamic color
        main_color = (255, 255, 255) if self.combo < 10 else glow_color
        self.draw_gradient_rect(screen, hit_rect, main_color, tuple(c//2 for c in main_color))
        
        # Sharp borders
        pygame.draw.rect(screen, WHITE, hit_rect, 2)
        
        # Beat pulse effect
        beat_duration = 60000 / self.bpm
        beat_progress = (current_time % beat_duration) / beat_duration
        if beat_progress < 0.1:
            pulse_intensity = (0.1 - beat_progress) / 0.1
            pulse_height = int(hit_line_height + pulse_intensity * 4)
            pulse_rect = pygame.Rect(hit_line_start, HIT_LINE_Y - pulse_height//2, hit_line_width, pulse_height)
            pulse_surface = pygame.Surface((hit_line_width, pulse_height), pygame.SRCALPHA)
            pulse_alpha = int(80 * pulse_intensity)
            pulse_surface.fill((*WHITE, pulse_alpha))
            screen.blit(pulse_surface, (hit_line_start, HIT_LINE_Y - pulse_height//2))
        
        # Draw beats
        for beat in self.beats:
            key, beat_type, beat_hit, hold_time = beat
            if key < 1 or key > 4:  # Skip invalid keys
                continue
            
            # Add intro delay - OSU style 4 beat countdown
            intro_delay = INTRO_BEATS * beat_duration
            beat_time = beat_hit * beat_duration + intro_delay
            time_until_hit = beat_time - current_time
            
            # Only draw beats that are approaching or recently passed
            if beat_type == 1 and hold_time:
                # For hold notes, draw from when start appears until end disappears
                hold_duration = hold_time * beat_duration
                time_until_end = (beat_time + hold_duration) - current_time
                should_draw = time_until_hit < APPROACH_TIME and time_until_end > -200
                
            else:
                should_draw = -200 < time_until_hit < APPROACH_TIME

            if should_draw:
                x = self.key_positions[key]
                color = self.key_colors[key]
                
                if beat_type == 1 and hold_time:  # Hold note
                    # Calculate positions for hold note
                    progress_start = 1 - (time_until_hit / APPROACH_TIME)
                    y_start = 50 + progress_start * (HIT_LINE_Y - 50)
                    
                    hold_duration = hold_time * beat_duration
                    time_until_end = (beat_time + hold_duration) - current_time
                    progress_end = 1 - (time_until_end / APPROACH_TIME)
                    y_end = 50 + progress_end * (HIT_LINE_Y - 50)
                    
                    # Enhanced hold line with gradient effect
                    # Clamp y_end to at least 50 so slider always shows when start is visible
                    y_end_clamped = max(y_end, 50)
                    if y_start > 50:
                        hold_width = 25
                        hold_rect = pygame.Rect(x - hold_width//2, int(y_end_clamped), hold_width, int(y_start - y_end_clamped))
                        
                        # Shadow
                        shadow_rect = hold_rect.copy()
                        shadow_rect.x += 2
                        shadow_rect.y += 2
                        pygame.draw.rect(screen, BLACK, shadow_rect)
                        
                        # Main hold body with gradient effect
                        pygame.draw.rect(screen, color, hold_rect)
                        
                        # Glow effect
                        glow_surface = pygame.Surface((hold_width + 10, int(y_start - y_end_clamped) + 10), pygame.SRCALPHA)
                        glow_color = (*color, 40)
                        glow_surface.fill(glow_color)
                        screen.blit(glow_surface, (x - hold_width//2 - 5, int(y_end_clamped) - 5))
                        
                        # Border
                        pygame.draw.rect(screen, WHITE, hold_rect, 3)
                        
                        # Active hold indicator
                        if key in self.active_holds:
                            active_surface = pygame.Surface((hold_width, int(y_start - y_end_clamped)), pygame.SRCALPHA)
                            active_color = (*NEON_YELLOW, 60)
                            active_surface.fill(active_color)
                            screen.blit(active_surface, (x - hold_width//2, int(y_end_clamped)))
                    
                    # Enhanced start rectangle
                    start_rect = pygame.Rect(int(x) - NOTE_WIDTH//2, int(y_start) - NOTE_HEIGHT//2, NOTE_WIDTH, NOTE_HEIGHT)
                    shadow_rect = start_rect.copy()
                    shadow_rect.x += 2
                    shadow_rect.y += 2
                    pygame.draw.rect(screen, BLACK, shadow_rect)  # Shadow
                    pygame.draw.rect(screen, color, start_rect)
                    pygame.draw.rect(screen, WHITE, start_rect, 4)
                    
                    # Inner highlight for start
                    inner_start = pygame.Rect(int(x) - NOTE_WIDTH//4, int(y_start) - NOTE_HEIGHT//4, NOTE_WIDTH//2, NOTE_HEIGHT//2)
                    pygame.draw.rect(screen, WHITE, inner_start)
                    
                    # Enhanced end rectangle if visible
                    if y_end > 50:
                        end_width = NOTE_WIDTH//2 + 10
                        end_height = NOTE_HEIGHT//2 + 10
                        end_rect = pygame.Rect(int(x) - end_width//2, int(y_end) - end_height//2, end_width, end_height)
                        end_shadow = end_rect.copy()
                        end_shadow.x += 1
                        end_shadow.y += 1
                        pygame.draw.rect(screen, BLACK, end_shadow)  # Shadow
                        pygame.draw.rect(screen, color, end_rect)
                        pygame.draw.rect(screen, WHITE, end_rect, 3)
                        
                        # End marker
                        marker_rect = pygame.Rect(int(x) - 3, int(y_end) - 3, 6, 6)
                        pygame.draw.rect(screen, WHITE, marker_rect)
                else:  # Regular note - osu!lazer style rectangle
                    # Calculate Y position based on time until hit
                    progress = 1 - (time_until_hit / APPROACH_TIME)
                    y = 50 + progress * (HIT_LINE_Y - 50)
                    
                    # osu!lazer style rectangular note
                    note_width = NOTE_WIDTH
                    note_height = NOTE_HEIGHT
                    note_rect = pygame.Rect(int(x) - note_width//2, int(y) - note_height//2, note_width, note_height)
                    
                    # Subtle shadow
                    shadow_rect = note_rect.copy()
                    shadow_rect.x += 2
                    shadow_rect.y += 2
                    pygame.draw.rect(screen, (0, 0, 0, 80), shadow_rect, border_radius=6)
                    
                    # Single glow effect (reduced for performance)
                    glow_rect = pygame.Rect(note_rect.x - 4, note_rect.y - 4, note_rect.width + 8, note_rect.height + 8)
                    glow_surface = pygame.Surface((glow_rect.width, glow_rect.height), pygame.SRCALPHA)
                    glow_surface.fill((*color, 30))
                    screen.blit(glow_surface, (glow_rect.x, glow_rect.y))
                    
                    # Main note with gradient (simplified)
                    gradient = self.key_gradients[key]
                    self.draw_gradient_rect(screen, note_rect, gradient[0], gradient[1])
                    
                    # Rounded corners effect with border
                    pygame.draw.rect(screen, WHITE, note_rect, 2, border_radius=6)
                    
                    # Inner highlight for osu!lazer look
                    inner_rect = pygame.Rect(note_rect.x + 4, note_rect.y + 2, note_rect.width - 8, note_rect.height // 3)
                    inner_surface = pygame.Surface((inner_rect.width, inner_rect.height), pygame.SRCALPHA)
                    inner_surface.fill((255, 255, 255, 60))
                    screen.blit(inner_surface, (inner_rect.x, inner_rect.y))
                    
                    # Lane number in center
                    number_font = pygame.font.Font(None, 20)
                    number_text = number_font.render(str(key), True, WHITE)
                    number_rect = number_text.get_rect(center=note_rect.center)
                    screen.blit(number_text, number_rect)
                
                # Draw approach circle for both types (OSU style)
                if time_until_hit > 0:
                    progress = 1 - (time_until_hit / APPROACH_TIME)
                    y = 50 + progress * (HIT_LINE_Y - 50)
                    
                    # Approach circle that shrinks as note approaches
                    approach_scale = 1 + (time_until_hit / APPROACH_TIME) * 2
                    approach_radius = int(self.approach_circle_max * approach_scale)
                    
                    # Approach circle with fade effect
                    alpha = int(180 * (time_until_hit / APPROACH_TIME))
                    if alpha > 10:  # Only draw if visible enough
                        approach_surface = pygame.Surface((approach_radius * 2 + 6, approach_radius * 2 + 6), pygame.SRCALPHA)
                        approach_color = (*color, alpha)
                        
                        # Thick approach circle
                        center_pos = (approach_radius + 3, approach_radius + 3)
                        pygame.draw.circle(approach_surface, approach_color, center_pos, approach_radius, 4)
                        
                        # Inner glow for the approach circle
                        inner_alpha = alpha // 3
                        inner_color = (*color, inner_alpha)
                        pygame.draw.circle(approach_surface, inner_color, center_pos, approach_radius - 2, 2)
                        
                        screen.blit(approach_surface, (int(x) - approach_radius - 3, int(y) - approach_radius - 3))
        
        # Update and draw burst effects
        current_time_burst = pygame.time.get_ticks()
        self.burst_effects = [effect for effect in self.burst_effects if effect['life'] > 0]
        
        for effect in self.burst_effects:
            effect['x'] += effect['vx']
            effect['y'] += effect['vy']
            effect['life'] -= 1
            effect['vx'] *= 0.98  # Friction
            effect['vy'] *= 0.98
            
            alpha = int(255 * (effect['life'] / effect['max_life']))
            if alpha > 5:
                particle_surface = pygame.Surface((effect['size'] * 2, effect['size'] * 2), pygame.SRCALPHA)
                pygame.draw.circle(particle_surface, (*effect['color'], alpha), 
                                 (effect['size'], effect['size']), effect['size'])
                screen.blit(particle_surface, (effect['x'] - effect['size'], effect['y'] - effect['size']))
        
        # Draw hit effects (enhanced)
        current_time_effects = pygame.time.get_ticks()
        self.hit_effects = [effect for effect in self.hit_effects if current_time_effects - effect['time'] < 300]
        
        for effect in self.hit_effects:
            elapsed = current_time_effects - effect['time']
            alpha = max(0, 255 - (elapsed * 255 // 300))
            scale = 1 + (elapsed / 150)  # Slower scaling
            effect_radius = int(self.note_radius * scale)
            
            # Create circular hit effect
            if alpha > 10:
                effect_surface = pygame.Surface((effect_radius * 2, effect_radius * 2), pygame.SRCALPHA)
                effect_color = (*effect['color'], alpha)
                pygame.draw.circle(effect_surface, effect_color, (effect_radius, effect_radius), effect_radius)
                # Add ring effect
                ring_radius = effect_radius - 5
                if ring_radius > 0:
                    pygame.draw.circle(effect_surface, (255, 255, 255, alpha//2), 
                                     (effect_radius, effect_radius), ring_radius, 3)
                screen.blit(effect_surface, (effect['x'] - effect_radius, effect['y'] - effect_radius))
        
        # Draw enhanced judgment effects
        current_time_judgment = pygame.time.get_ticks()
        self.judgment_effects = [effect for effect in self.judgment_effects if current_time_judgment - effect['time'] < 1200]
        
        for effect in self.judgment_effects:
            elapsed = current_time_judgment - effect['time']
            alpha = max(0, 255 - (elapsed * 255 // 1200))
            y_offset = elapsed // 8  # Move up over time
            
            # Scale effect based on judgment quality and time
            judgment = effect.get('judgment', 'MISS')
            base_scale = {'PERFECT': 1.5, 'GOOD': 1.2, 'BAD': 1.0, 'MISS': 0.8}.get(judgment, 1.0)
            time_scale = 1.0 + (min(elapsed, 200) / 400)  # Grow then stay
            final_scale = base_scale * time_scale
            
            font_size = int(40 * final_scale)
            font = pygame.font.Font(None, font_size)
            
            # Create text with outline
            text_color = effect['color']
            outline_color = (0, 0, 0)
            
            # Draw outline
            for dx in [-2, 0, 2]:
                for dy in [-2, 0, 2]:
                    if dx != 0 or dy != 0:
                        outline_surface = font.render(effect['text'], True, outline_color)
                        outline_surface.set_alpha(alpha)
                        outline_rect = outline_surface.get_rect(center=(effect['x'] + dx, effect['y'] - y_offset + dy))
                        screen.blit(outline_surface, outline_rect)
            
            # Draw main text
            text_surface = font.render(effect['text'], True, text_color)
            text_surface.set_alpha(alpha)
            text_rect = text_surface.get_rect(center=(effect['x'], effect['y'] - y_offset))
            screen.blit(text_surface, text_rect)
            
            # Add glow effect for perfect hits
            if judgment == 'PERFECT' and elapsed < 400:
                glow_alpha = int((400 - elapsed) / 400 * 60)
                glow_surface = font.render(effect['text'], True, (255, 255, 255))
                glow_surface.set_alpha(glow_alpha)
                screen.blit(glow_surface, text_rect)
        
        # Draw UI with enhanced styling
        font = pygame.font.Font(None, 36)
        medium_font = pygame.font.Font(None, 28)
        
        # UI Background panel with proper alpha
        ui_panel = pygame.Surface((300, 200), pygame.SRCALPHA)
        panel_color = (*DARK_GRAY, 180)
        ui_panel.fill(panel_color)
        screen.blit(ui_panel, (5, 5))
        pygame.draw.rect(screen, LIGHT_GRAY, (5, 5, 300, 200), 2)
        
        # Score with enhanced styling
        score_text = font.render(f"Score: {self.score:,}", True, NEON_YELLOW)
        score_shadow = font.render(f"Score: {self.score:,}", True, BLACK)
        screen.blit(score_shadow, (16, 16))
        screen.blit(score_text, (15, 15))
        
        # Combo with glow effect for high combos
        combo_color = WHITE if self.combo < 10 else NEON_YELLOW if self.combo < 50 else NEON_RED
        combo_text = font.render(f"Combo: {self.combo}x", True, combo_color)
        combo_shadow = font.render(f"Combo: {self.combo}x", True, BLACK)
        screen.blit(combo_shadow, (16, 56))
        screen.blit(combo_text, (15, 55))
        
        # High combo glow effect
        if self.combo >= 50:
            glow_surface = pygame.Surface((200, 40), pygame.SRCALPHA)
            glow_color = (*NEON_RED, 30)
            glow_surface.fill(glow_color)
            screen.blit(glow_surface, (10, 50))
        
        # Max combo
        max_combo_text = medium_font.render(f"Max: {self.max_combo}x", True, LIGHT_GRAY)
        screen.blit(max_combo_text, (10, 85))
        
        # Accuracy
        accuracy = self.get_accuracy()
        accuracy_color = WHITE
        if accuracy >= 95:
            accuracy_color = (0, 255, 255)  # Cyan for excellent
        elif accuracy >= 85:
            accuracy_color = GREEN
        elif accuracy >= 70:
            accuracy_color = YELLOW
        else:
            accuracy_color = RED
            
        accuracy_text = font.render(f"Accuracy: {accuracy:.1f}%", True, accuracy_color)
        screen.blit(accuracy_text, (10, 115))
        
        # Hit statistics (smaller text)
        small_font = pygame.font.Font(None, 20)
        stats_y = 150
        perfect_text = small_font.render(f"Perfect: {self.perfect_hits}", True, (0, 255, 255))
        screen.blit(perfect_text, (10, stats_y))
        good_text = small_font.render(f"Good: {self.good_hits}", True, GREEN)
        screen.blit(good_text, (10, stats_y + 20))
        bad_text = small_font.render(f"Bad: {self.bad_hits}", True, YELLOW)
        screen.blit(bad_text, (10, stats_y + 40))
        miss_text = small_font.render(f"Miss: {self.misses}", True, RED)
        screen.blit(miss_text, (10, stats_y + 60))
        
        # Time
        time_text = medium_font.render(f"Time: {current_time/1000:.1f}s", True, WHITE)
        screen.blit(time_text, (10, stats_y + 90))
        
        # Draw key labels
        key_font = pygame.font.Font(None, 24)
        labels = ['D', 'F', 'J', 'K']
        for i, label in enumerate(labels, 1):
            x = self.key_positions[i]
            text = key_font.render(label, True, WHITE)
            text_rect = text.get_rect(center=(x, HIT_LINE_Y + 50))
            screen.blit(text, text_rect)
