# sr10.py
# ChronoRun - Advanced Pygame prototype by ChatGPT
# Save as C:\Users\gmspr\sr10.py and run with `python sr10.py`

import pygame
import random
import math
import sys
import time

# -------- CONFIG ----------
WIDTH, HEIGHT = 1100, 640
FPS = 60

GRAVITY = 0.9
PLAYER_ACC = 0.9
PLAYER_FRICTION = -0.12
PLAYER_JUMP_FORCE = 17
PLAYER_MAX_JUMPS = 2
DASH_SPEED = 16
DASH_COOLDOWN = 60  # frames

CHUNK_WIDTH = 1200
CHUNKS_AHEAD = 2

PLATFORM_MIN_WIDTH = 80
PLATFORM_MAX_WIDTH = 300
PLATFORM_HEIGHT = 20

# Colors
SKY = (145, 190, 255)
BG = (18, 24, 38)
PLATFORM_COLOR = (80, 55, 40)
PLAYER_COLOR_PRIMARY = (10, 210, 240)
PLAYER_COLOR_ACCENT = (240, 240, 220)
ENEMY_COLOR = (230, 80, 80)
COIN_COLOR = (255, 210, 60)
GOAL_COLOR = (50, 230, 80)
POWERUP_COLOR = (255, 120, 0)

# --------------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("ChronoRun — sr10")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 24)
BIG_FONT = pygame.font.SysFont(None, 40)

# ------------------ UTIL -------------------
def clamp(v, a, b):
    return max(a, min(b, v))

def seeded_random(seed):
    rnd = random.Random(seed)
    while True:
        yield rnd.random()

# ------------------ STORY GENERATOR ------------------
HEROES = ["Lyra", "Kai", "Asha", "Rin", "Nova", "Taro"]
VILLAINS = ["Zarnok", "Umbra", "Morgath", "Vexis", "Nyx"]
LANDS = ["EmberVale", "Azurewood", "Thornmoor", "Skyfen", "Ironholm"]
ITEMS = ["Crystal", "Stormcore", "Echo Shard", "Heartwood Seed"]

def generate_story(seed):
    r = random.Random(seed)
    hero = r.choice(HEROES)
    villain = r.choice(VILLAINS)
    land = r.choice(LANDS)
    item = r.choice(ITEMS)
    template = r.choice([
        "{hero} must recover the {item} stolen by {villain} in {land}.",
        "A strange fog covers {land}. {hero} seeks the {item} to lift it from {villain}.",
        "{hero} races to stop {villain} from awakening the buried {item} beneath {land}."
    ])
    return template.format(hero=hero, villain=villain, land=land, item=item), hero

# ------------------ PARTICLE SYSTEM ------------------
class Particle:
    def __init__(self, x, y, vx, vy, life, size, color, fade=True):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.maxlife = life
        self.size = size
        self.color = color
        self.fade = fade

    def update(self):
        self.vy += 0.5
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surf, cam):
        alpha = 255
        if self.fade:
            alpha = int(255 * (self.life / self.maxlife)) if self.life>0 else 0
        s = pygame.Surface((self.size*2, self.size*2), pygame.SRCALPHA)
        c = (*self.color, alpha)
        pygame.draw.circle(s, c, (self.size, self.size), self.size)
        surf.blit(s, (self.x - self.size - cam, self.y - self.size))

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, p):
        self.particles.append(p)

    def burst(self, x, y, color, count=10, spread=3, speed=3):
        for _ in range(count):
            ang = random.random() * math.pi * 2
            v = random.uniform(0.7, speed)
            vx = math.cos(ang) * v * spread
            vy = math.sin(ang) * v * spread * -0.6
            life = random.randint(20, 40)
            size = random.randint(2,4)
            self.emit(Particle(x, y, vx, vy, life, size, color))

    def update(self):
        for p in self.particles[:]:
            p.update()
            if p.life <= 0 or p.y > HEIGHT + 200:
                self.particles.remove(p)

    def draw(self, surf, cam):
        for p in self.particles:
            p.draw(surf, cam)

particle_system = ParticleSystem()

# ------------------ ENTITY BASE ------------------
class Entity(pygame.sprite.Sprite):
    def __init__(self, x, y, w, h):
        super().__init__()
        self.rect = pygame.Rect(x, y, w, h)
        self.pos = pygame.Vector2(x, y)
        self.vel = pygame.Vector2(0,0)
        self.acc = pygame.Vector2(0,0)

    def apply_gravity(self):
        self.acc.y += GRAVITY

    def update_physics(self):
        self.vel += self.acc
        self.pos += self.vel + 0.5 * self.acc
        self.rect.topleft = (round(self.pos.x), round(self.pos.y))
        self.acc = pygame.Vector2(0,0)

# ------------------ PLATFORM, COIN, POWERUP ------------------
class Platform:
    def __init__(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, PLATFORM_HEIGHT)

    def draw(self, surf, cam):
        r = self.rect.move(-cam,0)
        pygame.draw.rect(surf, PLATFORM_COLOR, r, border_radius=6)
        # small highlight
        pygame.draw.rect(surf, (120,85,55), (r.x, r.y, r.w, 6))

class Coin:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x-9, y-9, 18, 18)
        self.collected = False

    def draw(self, surf, cam):
        if self.collected: return
        r = self.rect.move(-cam,0)
        pygame.draw.circle(surf, COIN_COLOR, r.center, 9)
        pygame.draw.circle(surf, (255,255,255,60), r.center, 4)

class Powerup:
    def __init__(self, x, y, kind="speed"):
        self.rect = pygame.Rect(x-12, y-12, 24, 24)
        self.collected = False
        self.kind = kind

    def draw(self, surf, cam):
        if self.collected: return
        r = self.rect.move(-cam,0)
        pygame.draw.rect(surf, POWERUP_COLOR, r, border_radius=6)
        pygame.draw.circle(surf, (255,255,255), (r.centerx, r.centery-4), 4)

# ------------------ PLAYER ------------------
class Player(Entity):
    def __init__(self, x, y, name="Hero"):
        super().__init__(x, y, 40, 56)
        self.name = name
        self.on_ground = False
        self.jumps = 0
        self.max_jumps = PLAYER_MAX_JUMPS
        self.dash_cool = 0
        self.dash_time = 0
        self.facing = 1
        self.score = 0
        self.color_primary = PLAYER_COLOR_PRIMARY
        self.color_accent = PLAYER_COLOR_ACCENT
        self.trail = deque(maxlen=8)

    def handle_input(self, keys):
        self.acc.x = 0
        if keys.get(pygame.K_LEFT) or keys.get(pygame.K_a):
            self.acc.x = -PLAYER_ACC
            self.facing = -1
        if keys.get(pygame.K_RIGHT) or keys.get(pygame.K_d):
            self.acc.x = PLAYER_ACC
            self.facing = 1

        # dash
        if keys.get(pygame.K_LSHIFT) or keys.get(pygame.K_RSHIFT):
            if self.dash_cool <= 0:
                self.dash_time = 6
                self.dash_cool = DASH_COOLDOWN
                # dash particles
                for i in range(8):
                    vx = -self.facing * random.uniform(1.5, 4)
                    vy = random.uniform(-1.5, 1.5)
                    particle_system.emit(Particle(self.pos.x + self.rect.w/2, self.pos.y + self.rect.h/2, vx, vy, 18, 3, (0,200,255)))
        if self.dash_cool > 0:
            self.dash_cool -= 1
        if self.dash_time > 0:
            self.dash_time -= 1

    def jump(self):
        if self.on_ground or self.jumps < self.max_jumps:
            self.vel.y = -PLAYER_JUMP_FORCE
            self.jumps += 1
            self.on_ground = False
            # jump particles
            particle_system.burst(self.pos.x + self.rect.w/2, self.pos.y + self.rect.h, (200,180,120), count=10, spread=2, speed=2)

    def update(self, platforms):
        # physics
        if self.dash_time > 0:
            self.vel.x = DASH_SPEED * self.facing
        else:
            # friction + acceleration
            self.acc.x += self.vel.x * PLAYER_FRICTION
            self.vel.x += self.acc.x
        self.apply_gravity()
        self.update_physics()

        # collisions with platforms
        self.on_ground = False
        for p in platforms:
            if self.rect.colliderect(p.rect):
                # vertical collision (landing)
                if self.vel.y > 0 and self.rect.bottom - p.rect.top < 20:
                    self.rect.bottom = p.rect.top
                    self.pos.y = self.rect.y
                    self.vel.y = 0
                    self.on_ground = True
                    self.jumps = 0
        # trail
        self.trail.append((self.pos.x + self.rect.w/2, self.pos.y + self.rect.h/2))

    def draw(self, surf, cam):
        # draw trail
        tlen = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(30 * (i / (tlen+1)) + 10)
            s = pygame.Surface((16,16), pygame.SRCALPHA)
            c = (*self.color_primary, alpha)
            pygame.draw.circle(s, c, (8,8), 6)
            surf.blit(s, (tx-8-cam, ty-8))

        r = self.rect.move(-cam,0)
        # body
        body = pygame.Rect(r.x, r.y+10, r.w, r.h-10)
        pygame.draw.rect(surf, self.color_primary, body, border_radius=8)
        # head (Claude-like stylized)
        head_center = (r.x + r.w//2, r.y + 8)
        pygame.draw.circle(surf, self.color_accent, head_center, 12)
        # eyes
        eye_x = 6 if self.facing>=0 else -6
        pygame.draw.circle(surf, (20,20,30), (head_center[0]+eye_x, head_center[1]-2), 2)
        pygame.draw.circle(surf, (20,20,30), (head_center[0]+eye_x//2, head_center[1]-2), 2)
        # accent stripe
        pygame.draw.rect(surf, (0,120,180), (r.x+6, r.y+20, r.w-12, 6), border_radius=4)

# ------------------ ENEMIES ------------------
class Enemy(Entity):
    def __init__(self, x, y, w=36, h=48, speed=1.4):
        super().__init__(x, y, w, h)
        self.patrol_left = x - 80
        self.patrol_right = x + 80
        self.speed = speed
        self.state = 'patrol'  # patrol, chase, stun
        self.vision = 210
        self.chase_timer = 0
        self.health = 2

    def update(self, player, platforms):
        # states
        if self.state == 'patrol':
            # move back and forth
            if self.pos.x < self.patrol_left:
                self.vel.x = self.speed
            elif self.pos.x > self.patrol_right:
                self.vel.x = -self.speed
            # detect
            if abs(player.rect.centerx - self.rect.centerx) < self.vision and abs(player.rect.centery - self.rect.centery) < 70:
                self.state = 'chase'
                self.chase_timer = 0
        elif self.state == 'chase':
            # simple line chase with limited speed
            dx = player.rect.centerx - self.rect.centerx
            self.vel.x = clamp(dx * 0.02, -4.2, 4.2)
            self.chase_timer += 1
            if self.chase_timer > 180:
                self.state = 'patrol'
        elif self.state == 'stun':
            self.vel.x *= 0.9
            if abs(self.vel.x) < 0.2:
                self.state = 'patrol'

        self.apply_gravity()
        self.update_physics()

        # platform collision
        for p in platforms:
            if self.rect.colliderect(p.rect):
                if self.vel.y > 0 and self.rect.bottom - p.rect.top < 18:
                    self.rect.bottom = p.rect.top
                    self.pos.y = self.rect.y
                    self.vel.y = 0

    def draw(self, surf, cam):
        r = self.rect.move(-cam,0)
        # body
        pygame.draw.rect(surf, ENEMY_COLOR, r, border_radius=6)
        # darker top
        pygame.draw.rect(surf, (180,40,40), (r.x, r.y, r.w, 8), border_radius=4)
        # eyes
        pygame.draw.circle(surf, (0,0,0), (r.x + r.w//2, r.y + 10), 3)

class JumperEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 32, 40, speed=1.0)
        self.jump_cool = random.randint(40, 120)

    def update(self, player, platforms):
        # jump toward player occasionally
        self.jump_cool -= 1
        if self.jump_cool <= 0:
            # if on ground, jump
            self.vel.y = -12
            if player.rect.centerx > self.rect.centerx:
                self.vel.x += 2
            else:
                self.vel.x -= 2
            self.jump_cool = random.randint(60, 140)
        super().update(player, platforms)

class RangedEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, 36, 36, speed=0.6)
        self.shoot_cool = random.randint(80,160)
        self.bullets = []

    def update(self, player, platforms):
        # shoot if in range
        self.shoot_cool -= 1
        if self.shoot_cool <= 0:
            self.shoot_cool = random.randint(90, 200)
            # shoot bullet toward player
            bx = self.rect.centerx
            by = self.rect.centery
            dx = player.rect.centerx - bx
            dy = player.rect.centery - by
            dist = math.hypot(dx, dy) + 0.001
            vx = dx / dist * 6
            vy = dy / dist * 6
            self.bullets.append([bx, by, vx, vy, 90])
        # update bullets
        for b in self.bullets[:]:
            b[0] += b[2]; b[1] += b[3]; b[4] -= 1
            if b[4] <= 0:
                self.bullets.remove(b)
        super().update(player, platforms)

    def draw(self, surf, cam):
        super().draw(surf, cam)
        # draw bullets
        for b in self.bullets:
            pygame.draw.circle(surf, (255,220,80), (int(b[0]-cam), int(b[1])), 5)

# ------------------ WORLD GENERATOR ------------------
class World:
    def __init__(self, seed=None):
        self.seed = seed if seed is not None else random.randrange(1<<30)
        self.rnd = random.Random(self.seed)
        self.platforms = []
        self.coins = []
        self.powerups = []
        self.enemies = []
        self.generated_chunks = set()
        self.end_x = 0
        self.generate_initial()

    def generate_initial(self):
        # large floor
        self.platforms.append(Platform(-2000, HEIGHT-60, 5000))
        self.end_x = 1600
        for i in range(CHUNKS_AHEAD+1):
            self.generate_chunk(i)

    def generate_chunk(self, idx):
        if idx in self.generated_chunks: return
        base_x = idx * CHUNK_WIDTH
        rnd = random.Random(self.seed + idx * 137)
        y_base = HEIGHT - 150
        platform_count = rnd.randint(6, 12)
        x = base_x + 200
        last_w = 200
        for i in range(platform_count):
            w = rnd.randint(PLATFORM_MIN_WIDTH, PLATFORM_MAX_WIDTH)
            gap = rnd.randint(80, 260)
            x += last_w + gap
            y_variation = rnd.randint(-140, 100)
            y = clamp(y_base + y_variation - (i*6), 120, HEIGHT-120)
            plat = Platform(x, y, w)
            self.platforms.append(plat)
            # coin
            if rnd.random() < 0.4:
                self.coins.append(Coin(x + w//2, y - 26))
            # enemy
            r = rnd.random()
            if r < 0.35:
                e = Enemy(x + w//2, y - 48, w=36, h=44, speed=1.2 + rnd.random()*1.6)
                e.patrol_left = x - 20
                e.patrol_right = x + w - 20
                self.enemies.append(e)
            elif r < 0.55:
                je = JumperEnemy(x + w//2, y - 40)
                je.patrol_left = x + 10
                je.patrol_right = x + w - 10
                self.enemies.append(je)
            elif r < 0.66:
                re = RangedEnemy(x + w//2, y - 44)
                re.patrol_left = x + 10
                re.patrol_right = x + w - 10
                self.enemies.append(re)
            # powerup
            if rnd.random() < 0.12:
                self.powerups.append(Powerup(x + int(rnd.random()*w), y - 36))
            last_w = w
        self.generated_chunks.add(idx)
        self.end_x = max(self.end_x, base_x + CHUNK_WIDTH - 200)

    def ensure_for_x(self, x):
        current_idx = max(0, x // CHUNK_WIDTH)
        for i in range(current_idx, current_idx + CHUNKS_AHEAD + 1):
            self.generate_chunk(i)

# ------------------ MAIN GAME ------------------
def main(seed_arg=None):
    if seed_arg is None:
        seed = random.randrange(1<<30)
    else:
        seed = seed_arg

    story, hero_name = generate_story(seed)
    world = World(seed)
    player = Player(120, HEIGHT-220, name=hero_name)
    camera_x = 0
    keys = {}
    running = True
    level_complete = False
    start_time = time.time()
    last_score_tick = 0

    while running:
        dt = clock.tick(FPS)
        # events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False; break
            elif event.type == pygame.KEYDOWN:
                keys[event.key] = True
                if event.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                    player.jump()
                if event.key == pygame.K_r:
                    # restart same seed
                    main(seed)
                    return
                if event.key == pygame.K_n:
                    main(None)
                    return
                if event.key == pygame.K_ESCAPE:
                    running = False; break
            elif event.type == pygame.KEYUP:
                keys[event.key] = False

        if not running:
            break

        # world generation based on player pos
        world.ensure_for_x(int(player.pos.x + camera_x))

        # input & updates
        player.handle_input(keys)
        player.update(world.platforms)

        # coins & powerups
        for coin in world.coins:
            if not coin.collected and player.rect.colliderect(coin.rect):
                coin.collected = True
                player.score += 15
                particle_system.burst(coin.rect.centerx, coin.rect.centery, (255,220,90), count=12, spread=2, speed=3)
        for pu in world.powerups:
            if not pu.collected and player.rect.colliderect(pu.rect):
                pu.collected = True
                player.score += 50
                # sample effect: reduce jump cooldown or temporary speed (simple)
                player.vel.x *= 1.2
                particle_system.burst(pu.rect.centerx, pu.rect.centery, (255,120,10), count=16, spread=3, speed=3)

        # enemies update
        for e in world.enemies[:]:
            e.update(player, world.platforms)
            # collision with player
            if player.rect.colliderect(e.rect):
                # if player is falling (stomping)
                if player.vel.y > 3 and (player.rect.bottom - e.rect.top) < 20:
                    # stomp
                    e.health -= 1
                    player.vel.y = -10
                    particle_system.burst(e.rect.centerx, e.rect.centery, (255,80,80), count=12)
                    if e.health <= 0:
                        try:
                            world.enemies.remove(e)
                            player.score += 40
                        except ValueError:
                            pass
                else:
                    # player hit: knockback + tiny invulnerable window (not fully implemented - simple respawn)
                    player.pos.x = 120
                    player.pos.y = HEIGHT - 300
                    player.vel = pygame.Vector2(0,0)
                    player.score = max(0, player.score - 12)
                    particle_system.burst(player.pos.x+20, player.pos.y+30, (255,255,255), count=14, spread=2)

            # ranged bullets collision
            if isinstance(e, RangedEnemy):
                for b in e.bullets[:]:
                    bx, by = b[0], b[1]
                    if player.rect.collidepoint(bx, by):
                        # respawn
                        player.pos.x = 120; player.pos.y = HEIGHT-300
                        player.vel = pygame.Vector2(0,0)
                        player.score = max(0, player.score - 8)
                        e.bullets.remove(b)
                        particle_system.burst(bx, by, (255,200,80), count=8)

        # camera follows player (smooth)
        target = player.pos.x - WIDTH // 4
        camera_x += (target - camera_x) * 0.08
        camera_x = clamp(camera_x, -2000, world.end_x)

        # check goal (end of level)
        if player.pos.x + camera_x > world.end_x - 220:
            level_complete = True

        # periodic score for time survival
        if time.time() - last_score_tick > 4:
            last_score_tick = time.time()
            player.score += 1

        # update particles
        particle_system.update()

        # --- DRAW ---
        screen.fill(SKY)

        # parallax background: simple hills
        for i in range(3):
            hue = 160 - i*20
            offset = (camera_x * (0.2 + i*0.15)) % (WIDTH*2)
            points = [
                (-offset, HEIGHT - 30 - i*40),
                (WIDTH*2 - offset, HEIGHT - 30 - i*40),
                (WIDTH*2 - offset, HEIGHT),
                (-offset, HEIGHT)
            ]
            pygame.draw.polygon(screen, (20 + i*18, 60 + i*26, 100 + i*20), points)

        # platforms
        for p in world.platforms:
            p.draw(screen, int(camera_x))

        # coins
        for c in world.coins:
            c.draw(screen, int(camera_x))

        # powerups
        for pu in world.powerups:
            pu.draw(screen, int(camera_x))

        # enemies
        for e in world.enemies:
            e.draw(screen, int(camera_x))

        # goal marker at end
        gx = world.end_x - 100 - camera_x
        pygame.draw.rect(screen, GOAL_COLOR, (world.end_x - camera_x - 100, HEIGHT - 220, 60, 160), border_radius=8)
        # flag
        pygame.draw.polygon(screen, (255,255,255), [(world.end_x - camera_x - 60, HEIGHT-220+20), (world.end_x - camera_x - 20, HEIGHT-220+36), (world.end_x - camera_x - 60, HEIGHT-220+52)])

        # player
        player.draw(screen, int(camera_x))

        # particles
        particle_system.draw(screen, int(camera_x))

        # HUD
        tsec = int(time.time() - start_time)
        hud_text = f"Seed: {world.seed}  | Hero: {player.name}  | Score: {player.score}  | Time: {tsec}s  | DashCD: {player.dash_cool}"
        hud = FONT.render(hud_text, True, (20,20,20))
        # background box
        pygame.draw.rect(screen, (255,255,255,180), (8,8, min(WIDTH-16, 20 + len(hud_text)*7), 28))
        screen.blit(hud, (12,12))

        # story top-left small panel
        story_surf = FONT.render("Story: " + story, True, (10,10,10))
        screen.blit(story_surf, (12, 44))

        # level complete overlay
        if level_complete:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((10,10,20,200))
            screen.blit(overlay, (0,0))
            msg = BIG_FONT.render("Chapter Complete!", True, (240,240,240))
            screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 80))
            sub = FONT.render(f"{player.name} completed: {story}", True, (220,220,220))
            screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 - 30))
            sub2 = FONT.render("Press N for new world, R to replay same seed", True, (180,180,180))
            screen.blit(sub2, (WIDTH//2 - sub2.get_width()//2, HEIGHT//2 + 8))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    # Accept optional seed argument from command line
    if len(sys.argv) > 1:
        try:
            arg = int(sys.argv[1])
            main(arg)
        except:
            main(None)
    else:
        main(None)
