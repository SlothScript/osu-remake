import pygame
from menuSystem import MenuSystem

# Initialize pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
FPS = 60

# Create screen and clock
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# Set window title
pygame.display.set_caption("Rhythm Game")

# Create and run menu system
menu = MenuSystem(screen, clock)
menu.run()