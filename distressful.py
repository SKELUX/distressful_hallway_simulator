from math import sqrt, sin, atan2, degrees, radians, cos
from pathlib import Path
import sys, os, random as _random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data', 'lib'))
from ursina import *
from panda3d.core import AudioSound, TransparencyAttrib
from better_first_person import BetterFirstPersonController
#from entity_trimmed import Entity as SimpleEntity

 # ------- DEBUG (True/False)-------
TEST_SHOW_STATS = True
TEST_FORCE_SPAWN_FOLLOW = False
TEST_FORCE_SPAWN_FAST = False
TEST_FORCE_SPAWN_LOOK = False
TEST_FORCE_SPAWN_HURRY = False
TEST_FORCE_SPAWN_WALL = False
TEST_DISABLE_SPAWN_HURRY = False
TEST_DISABLE_SPAWN_RANDOM = False
TEST_KILL_WALL = False
TEST_FORCE_OUTDOORS = False
TEST_DISABLE_FOG = False
START_ROOM_INDEX = 1
START_ROOM_EFFECTIVE = 1

# ------- GLOBAL RNG -------
GAME_RNG_SEED = 1
USE_RANDOM_SEED = True
FORCE_REPEAT_SEED = False
if USE_RANDOM_SEED:
    GAME_RNG_SEED = _random.randint(0, 2**31 - 1)
random = _random.Random(GAME_RNG_SEED)

# ------- TUNABLE CONSTANTS -------
ROOM_Z_MIN = 8
ROOM_Z_MAX = 32
ROOM_Y_MIN = 4
ROOM_Y_MAX = 8
ROOM_X_MIN = 7
ROOM_X_MAX = 24
ROOMS_PREBUILT = 2
ROOMS_KEEP_LOAD = 3
FLOOR_Y = 0
PLAYER_HEIGHT = 2
MIN_WALL_EDGE_GAP = 2.25     # minimum gap between internal walls and side walls
SIDE_FEATURE_CHANCE = 0.35   # per-side chance to cut a window/door in a side wall

ROOM_DOOR_WIDTH = 2.25
ROOM_DOOR_HEIGHT = 3.0

# --- Outdoors ---
OUTDOOR_WORLD_X     = 96   # how far grass extends beyond walls. Must be less than ROOM_X_MAX
OUTDOOR_WALL_HEIGHT = 1.5
TREELINE_HEIGHT  = 6.0      # fixed height for the distant treeline
TREELINE_INSET   = 48      # how much closer the second row is from the far edge

# --- Pits ---
PIT_ROOM_CHANCE = 0.25   # 25% of indoor rooms get a pit

# --- Follow entity ---
FOLLOW_ENTITY_LIFETIME = 30.0
FOLLOW_ENTITY_LEAVE_DURATION = 10.0
FOLLOW_ENTITY_DESPAWN_DISTANCE = 60
FOLLOW_ENTITY_CATCH_DISTANCE = 2.5
FOLLOW_ENTITY_SPEED = 3

# --- Fast entity ---
FAST_ENTITY_SPEED = 22.0                     # forward speed along +Z
FAST_ENTITY_SPAWN_DIST = 100.0
FAST_ENTITY_LOS_RANGE = 12.0 # how far away it can "see" you for an instant kill

# --- Fall entity ---
FALL_ENTITY_HEIGHT = 4   # how far above the player it appears

# --- Look entity ---
LOOK_DESPAWN_TIME   = 0.2      # seconds of continuous looking
LOOK_VIEW_ANGLE     = 12.0     # cone from camera forward, in degrees
LOOK_MAX_DISTANCE   = 16.0     # max distance where looking still counts
LOOK_CATCH_DISTANCE = 2.0      # how close before it kills you
LOOK_GROW_TIME      = 0.25     # seconds to grow in
LOOK_SHRINK_TIME    = 0.25     # seconds to shrink out
LOOK_MIN_SPAWN_DISTANCE = 4.0   # min distance from player when spawning

# --- Hurry entity ---
HURRY_SPEED          = 8.0
HURRY_CATCH_DISTANCE = 2.5
HURRY_VIEW_ANGLE     = 10.0    # how closely you must look at it
HURRY_SOUND_RANGE    = 60.0    # distance where sound fades to 0
HURRY_SPAWN_INTERVAL = 2.0     # how often (seconds) to roll for a spawn chance

SPAWN_SCALE_HURRY           = 0.1    # base hurry spawn scale
SPAWN_SCALE_HURRY_OUT_BOUNDS = 1000.0   # multiplier when player is outside side walls
HURRY_OOB_MULT = 3.0 # how much faster hurry will be when player is out of bounds

# --- Wall entity ---
DOOM_WALL_SPEED = 0.5
DOOM_WALL_SPEED_SCALER = 0.005 # speed gained per room, never exceeds half player speed
WALL_SOUND_RANGE  = 32.0
DOOM_WALL = None

# --- Spawn Chance ---
BASE_SPAWN_CHANCE = 1.0 / 64.0   # baseline chance
BASE_SPAWN_CAP = 0.8 # chance of entity spawn can't be higher than this
SPAWN_SCALE_ENTITY = 1.0         # 1.0 = same as base
SPAWN_SCALE_FAST = 1.0
SPAWN_SCALE_LOOK = 1.0
SPAWN_SCALER = 0.05

# --- Textures ---
_TEXTURE_CACHE = {}

DEATH_MESSAGES = {
    "FOLLOW": "Ethereal arms embrace you.",
    "FAST":   "Your heart beats faster and faster.",
    "FALL":   "It lands right on top of you.",
    "LOOK":   "You feel so guilty.",
    "HURRY":  "Your soul is sucked from your body.",
    "WALL":   "You have lots of friends now.",
    "GUTTER": "You shit yourself and die.",
    "YOU":    "You need some you time.",
}

# ------- APP & FOG SETUP -------

app = Ursina(
    title='Distressful Hallway Simulator',
    icon='data/graphics/distressful_hallway.ico'
)

window.borderless = False
window.fullscreen = False
window.color = color.black
window.exit_button.enabled = False
if not TEST_SHOW_STATS:
    window.fps_counter.enabled = False
    window.entity_counter.enabled = False
    window.collider_counter.enabled = False

# Fog-compatible shader
Entity.default_shader = None

# Very dark linear fog
FOG_MIN_DISTANCE = 6
FOG_BASE_DISTANCE = 32
FOG_INCREMENT = 0.1
FOG_FLICKER_MULT = 1.0
scene.fog_color = color.black
scene.fog_density = (0, FOG_BASE_DISTANCE)

# ------- GLOBAL STATE -------

doors = []                  # all RoomDoor instances
door_labels = []
cyl_billboards = []
active_billboards = []
last_billboard_room = None
ACTIVE_ENTITY_FOLLOW = None
ACTIVE_ENTITY_FAST = None
ACTIVE_ENTITY_FALL = None
ACTIVE_ENTITY_LOOK = None
ACTIVE_ENTITY_HURRY = None
DOOM_WALL = None

rooms = []
next_room_index = 0
current_room_index = 0      # player’s current room index
raw_index = 0
max_room_index = 0          # furthest room reached
doors_opened = 0
hurry_spawn_timer = 0.0

game_over = False
game_over_timer = 0.0
game_over_look_target = None

is_paused = False
current_floor_material = 'default'
footstep_cooldown = 0.0
last_player_pos = None

# ------- WORLD LIGHTING -------

ambient_light = AmbientLight(color=color.rgb(80, 80, 80))

main_light = DirectionalLight()
main_light.rotation = (60, -45, 0)
main_light.color = color.rgb(180, 180, 180)

# ------- PLAYER -------

player = BetterFirstPersonController(
    y=PLAYER_HEIGHT,
    z=0,
    speed=6,
)
player.gravity = 1
player.y = FLOOR_Y
player._base_speed = player.speed

# --- SOUND MANAGER -------------------------------------------------

class SoundManager:
    def __init__(self):self._sounds={}
    def load(self, key, path, loop=False, base_volume=1):
        d=self._sounds.get(key)
        if d:s=d['sound']
        else:
            s=loader.loadSfx(path)
            self._sounds[key]={'sound':s,'base_volume':base_volume,'loop':loop}
        s.setLoop(loop);s.setVolume(base_volume);return s
    def play(self, key, pitch_variation=None, volume_mult=1, max_distance=FOG_BASE_DISTANCE, position=None):
        d=self._sounds.get(key)
        if not d:return
        s=d['sound']
        if position:
            dist=horizontal_distance(position,player.position)
            volume_mult=(1-dist/max_distance)**1
        s.stop();s.setTime(0)
        if pitch_variation:
            lo,hi=pitch_variation
            s.setPlayRate(random.uniform(lo,hi))
        s.setVolume(max(0,d['base_volume']*volume_mult));s.play();return s
    def set_volume(self, key, volume):
        d=self._sounds.get(key)
        if d:d['sound'].setVolume(max(0,volume))
    def get(self, key):
        d=self._sounds.get(key);return d and d['sound']

# --- GLOBAL SOUNDS (via SoundManager) ---

def load_sounds_directory(path:str, loop=False, base_volume=1):
    r={}
    for p in Path(path).glob('*.ogg'):
        s=sound_mgr.load(k:=p.stem,str(p),loop=loop,base_volume=0 if loop else base_volume)
        if s:
            r[k]=[k]
            if loop:s.play()
    return r

def update_volume_for_distance(sound_key, dist, dist_max, lerp_speed=10, power=2):
    t=dist/dist_max if dist_max>0 else 1
    tv=0 if dist>=dist_max else max(0,(1-t)**power)
    if not (s:=sound_mgr.get(sound_key)):return
    v=s.getVolume()
    sound_mgr.set_volume(sound_key,v+(tv-v)*min(1,lerp_speed*time.dt))

# ------- TEXTURE HELPERS -------

def find_textures(root, stem=None, recursive=False):
    key = (root, stem, recursive)
    if key in _TEXTURE_CACHE:
        return _TEXTURE_CACHE[key]
    p = Path(root)
    if p.is_file():
        files = [str(p)]
    elif p.is_dir():
        it = p.rglob('*.png') if recursive else p.glob('*.png')
        files = [str(f) for f in it]
    else:
        files = []
    if stem:
        files = [f for f in files if Path(f).stem == stem]
    if not files:
        print(f"[find_textures] no PNGs under {root} (stem={stem}, recursive={recursive}); using 'white_cube'.")
        files = ['white_cube']
    _TEXTURE_CACHE[key] = files
    return files

def get_texture(root, stem=None):
    files = find_textures(root, stem, True)
    return files[0] if len(files) < 2 else random.choice(files)

def _update_cylindrical_billboards():
    global active_billboards, last_billboard_room, raw_index, cyl_billboards
    # Rebuild active band when we enter a new room index
    if last_billboard_room != raw_index:
        last_billboard_room = raw_index
        # Disable everything first
        for e in cyl_billboards:
            e.enabled = False
        # Collect billboards from rooms [raw_index-1 .. raw_index+1]
        lo, hi = raw_index - 1, raw_index + 1
        active_billboards = [
            b
            for r in rooms
            if lo <= r.index <= hi
            for b in getattr(r, 'billboards', ())
        ]
        # Enable only the nearby band
        for e in active_billboards:
            e.enabled = True
    ry = camera.world_rotation_y
    for e in active_billboards:
        e.rotation_y = ry

# ------- DOORS -------

class RoomDoor(Entity):
    def __init__(self, width, height, pos, slide_dir=1, room_number: int | None = None):
        super().__init__(position=pos, model=None, collider=None)

        self.slide_dir   = 1 if slide_dir >= 0 else -1
        self.room_number = room_number

        # Hinge pivot (at one side of the frame)
        hinge_x = self.slide_dir * (width * 0.5)
        self.hinge = make_entity(parent=self, position=(hinge_x, 0, 0), model=None, collider=None)

        # Door mesh (offset so closed door spans the doorway)
        self.door_mesh = make_entity(
            parent=self.hinge,
            scale=(width, height, 0),
            position=(-hinge_x, 0, 0),
            texture='data/graphics/door.png'
        )

        # Optional room-number plaque
        if self.room_number is not None:
            plaque = make_entity(
                parent=self.door_mesh,
                texture='data/graphics/plaque.png',
                scale=(0.4, 0.1),
                position=(0, 0.25, -1),
            )
            digit_color = color.rgba32(20, 13, 7, 255)
            self.label = Text(
                text=str(self.room_number),
                world_parent=plaque,
                origin=(0, 0),
                position=(0, -0.04, -2),  # tiny offset to avoid z-fighting
                scale=32,
                font='data/fonts/EBGaramond-ExtraBold.ttf',
                color=digit_color,
                use_tags=False
            )
            self.label.scale_x *= 0.4
            door_labels.append((self.label, digit_color))

        # Rotation targets
        self.closed_rot_y = 0.0
        self.open_rot_y   = 120.0 * self.slide_dir  # swings outward
        self.is_open      = False

    def _swing_to(self, angle: float):
        self.hinge.animate_rotation_y(angle, duration=0.45, curve=curve.in_out_quad)

    def open(self):
        if self.is_open:
            return
        self.is_open = True
        sound_mgr.play('door', pitch_variation=(0.8, 1.2), position=self.position)
        self._swing_to(self.open_rot_y)
        notify_door_opened(self)

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        self._swing_to(self.closed_rot_y)

# ------- ROOMS -------

class Room:
    def __init__(self, index: int):
        self.index = index
        self.length = random.uniform(ROOM_Z_MIN, ROOM_Z_MAX)

        self.entities = []
        self.billboards = []
        self.blockers_xz = []
        self.door = None
        self.is_save_room = ((self.index + 1) % 50 == 0)

        # Random geometry / textures
        self.width  = random.uniform(ROOM_X_MIN, ROOM_X_MAX)
        self.height = random.uniform(ROOM_Y_MIN, ROOM_Y_MAX)
        self.wall_texture    = random.choice(find_textures('data/graphics/wall'))
        self.floor_texture   = random.choice(find_textures('data/graphics/floor'))
        self.ceiling_texture = random.choice(find_textures('data/graphics/ceiling'))

        if TEST_FORCE_OUTDOORS:
            self.wall_texture = 'data/graphics/wall/chain_link.png'
            
        if self.is_save_room:
            self.width = ROOM_X_MIN
            self.length = ROOM_Z_MIN
            self.height = ROOM_Y_MIN
            self.wall_texture    = get_texture('data/graphics/wall/extra', 'save')
            self.floor_texture   = get_texture('data/graphics/floor/extra', 'save')
            self.ceiling_texture = get_texture('data/graphics/ceiling/extra', 'save')

        # Treat chain-link AND any "tree"/"forest" wall as an outdoor area
        wall_name = str(self.wall_texture).lower()
        self.is_outdoors = any(s in wall_name for s in ("chain_link", "fence"))
        if self.is_outdoors:
            self.floor_texture = get_texture('data/graphics', 'grass')
            self.height = OUTDOOR_WALL_HEIGHT

        self.has_pit = False   # will be set true if we build a pitted floor
        self.pit_bounds = None
        
        prev = rooms[-1] if rooms else None
        self.center_z = 0.0 if not prev else prev.center_z + prev.length / 2 + self.length / 2
        
        self._build_room()
        if prev:
            connect_rooms(prev, self)
        
    def _build_room(self):
        # Floor uses the full room width (outdoor width already scaled in __init__)
        width = self.width

        # Indoor rooms only: sometimes have a central pit you must walk around
        if (
            not self.is_outdoors
            and not self.is_save_room
            and self.index > 0
            and self.index != (START_ROOM_INDEX-1)
            and random.random() < PIT_ROOM_CHANCE
            and width > 10.0
            and self.length > 10.0
        ):
            self._build_pitted_floor(width)
            self.has_pit = True
        else:
            floor = make_entity(
                scale=(width, 0, self.length),
                position=(0, FLOOR_Y, self.center_z),
                texture=self.floor_texture,
                texture_scale=(math.ceil(width / 8), math.ceil(self.length / 8))
            )
            self.entities.append(floor)

            # central footpath for outdoors
            if self.is_outdoors:
                path = make_entity(
                    scale=(ROOM_DOOR_WIDTH, 0, self.length),
                    position=(0, FLOOR_Y + 0.01, self.center_z),
                    texture=get_texture('data/graphics', 'path'),
                    texture_scale=(1, math.ceil(self.length / ROOM_DOOR_WIDTH))
                )
                self.entities.append(path)

        # ---------- Ceiling ----------
        # Indoors gets a ceiling, outdoors is open to the sky
        if self.height > 0 and not self.is_outdoors:
            ceiling = make_entity(
                scale=(self.width, 0, self.length),
                position=(0, FLOOR_Y + self.height, self.center_z),
                texture=self.ceiling_texture,
                rotation=(180, 0, 0),
                texture_scale=(math.ceil(self.width / 8), math.ceil(self.length / 8))
            )
            self.entities.append(ceiling)

        # ---------- Side walls (with optional windows/doors) ----------
        half_width = self.width / 2

        # Outdoor walls are short so you can jump over them
        wall_height = OUTDOOR_WALL_HEIGHT if self.is_outdoors else self.height

        start_z = self.center_z - self.length / 2
        end_z   = self.center_z + self.length / 2

        def _make_wall_segment(x_pos, z0, z1, y0, y1, tex=None):
            if z1 <= z0 or y1 <= y0:
                return
            seg_len = z1 - z0
            seg_h   = y1 - y0
            seg = make_entity(
                scale=(0, seg_h, seg_len),
                position=(x_pos, y0 + seg_h / 2, z0 + seg_len / 2),
                texture=tex or self.wall_texture,
                texture_scale=(math.ceil(seg_len / wall_height), 1)
            )
            self.entities.append(seg)

        def _build_side_wall(side_sign: int):
            global doors

            x_pos = side_sign * half_width
            wall_bottom = FLOOR_Y
            wall_top    = FLOOR_Y + wall_height

            # No features for outdoors or very small rooms
            use_feature = (
                not self.is_outdoors
                and not self.is_save_room
                and self.length > 6.0
                and wall_height > 3.0
                and random.random() < SIDE_FEATURE_CHANCE
            )

            if not use_feature:
                _make_wall_segment(x_pos, start_z, end_z, wall_bottom, wall_top)
                return

            # Three possibilities:
            #  - 'window'       = floating window band
            #  - 'doorway'      = open doorway (no physical door)
            #  - 'door_with_door' = doorway with an actual RoomDoor
            feature = random.choice(('window', 'door_with_door'))

            # Opening spans a chunk in the middle along Z
            open_len = ROOM_DOOR_WIDTH
            open_min_z = self.center_z - open_len / 2
            open_max_z = self.center_z + open_len / 2

            # Vertical bounds of the opening
            if feature == 'window':
                sill        = FLOOR_Y + 1.2
                win_h       = 1.6
                open_bottom = max(wall_bottom + 0.4, sill)
                open_top    = min(wall_top - 0.3, open_bottom + win_h)
            else:
                # doorway / door_with_door share the same vertical opening
                open_bottom = wall_bottom
                open_top    = min(wall_top - 0.4, wall_bottom + 3.0)

            has_physical_door = (feature == 'door_with_door')

            # 1) Solid strips before/after the opening along Z
            _make_wall_segment(x_pos, start_z,    open_min_z, wall_bottom, wall_top)
            _make_wall_segment(x_pos, open_max_z, end_z,      wall_bottom, wall_top)

            # 2) Top / bottom strips around the opening so all gaps are filled
            # Bottom strip (none for a full-height window, but we still keep a sill)
            _make_wall_segment(x_pos, open_min_z, open_max_z, wall_bottom, open_bottom)
            # Top strip
            _make_wall_segment(x_pos, open_min_z, open_max_z, open_top,    wall_top)

            # 3) Window infill panel (blocks player, uses window texture)
            if feature == 'window':
                _make_wall_segment(
                    x_pos,
                    open_min_z,
                    open_max_z,
                    open_bottom,
                    open_top,
                    get_texture('data/graphics', 'window')
                )

            # 4) If this is a real door, drop a RoomDoor into the opening
            if has_physical_door:
                door_center_z = (open_min_z + open_max_z) / 2
                door_center_y = open_bottom + ROOM_DOOR_HEIGHT / 2

                side_door = RoomDoor(
                    width=ROOM_DOOR_WIDTH,
                    height=ROOM_DOOR_HEIGHT,
                    pos=Vec3(x_pos, door_center_y, door_center_z),
                    slide_dir=-1,
                    room_number=None   # side rooms will handle their own labels later
                )
                # Rotate so its plane faces ±X instead of ±Z
                side_door.rotation_y = 90 * side_sign

                self.entities.append(side_door)
                doors.append(side_door)

        # Build left and right walls
        _build_side_wall(-1)
        _build_side_wall(1)

        # ---------- Extra grass outside side walls ----------
        grass_depth = (OUTDOOR_WORLD_X - self.width) / 2 + TREELINE_INSET

        # Left side grass beyond the wall
        left_grass = make_entity(
            scale=(grass_depth, 0, self.length),
            position=(
                -half_width - grass_depth / 2.0,
                FLOOR_Y,
                self.center_z
            ),
            texture=get_texture('data/graphics', 'grass'),
            texture_scale=(math.ceil(grass_depth / 6), math.ceil(self.length / 6))
        )

        # Right side grass beyond the wall
        right_grass = make_entity(
            scale=(grass_depth, 0, self.length),
            position=(
                half_width + grass_depth / 2.0,
                FLOOR_Y,
                self.center_z
            ),
            texture=get_texture('data/graphics', 'grass'),
            texture_scale=(math.ceil(grass_depth / 6), math.ceil(self.length / 6))
        )
        self.entities.extend([left_grass, right_grass])

        # ---------- Treeline at far ends of the grass ----------
        # We place a treeline wall TREELINE_INSET units closer to the building on both left and right.
        if grass_depth > 0.1:
            treeline_height = TREELINE_HEIGHT
            treeline_y = FLOOR_Y + treeline_height / 2.0

            # Distance from centre to the far edge of grass
            edge_offset = half_width + grass_depth

            for side in (-1, 1):  # -1 = left, +1 = right
                # Inner row: inset from far edge, but never inside the room walls
                offset = max(edge_offset - TREELINE_INSET, half_width + 0.5)

                x_pos = side * offset
                tree_wall = make_entity(
                    scale=(0, treeline_height, self.length),
                    position=(x_pos, treeline_y, self.center_z),
                    texture=get_texture('data/graphics', 'trees'),
                    texture_scale=(math.ceil(self.length / treeline_height), 1)
                )
                self.entities.append(tree_wall)

        # Random interior walls / props
        self._spawn_random_props()
        
        # --- SAVE POINT (save rooms only) ---
        if self.is_save_room:
            sp = SavePoint(
                room_index=self.index,
                pos=Vec3(0, FLOOR_Y + PLAYER_HEIGHT, self.center_z)
            )
            self.entities.append(sp)

        # Back wall for the first room so you can't walk backwards forever
        if self.index == 0:
            back_z = self.center_z - self.length / 2
            wall_y_center_full = FLOOR_Y + self.height / 2  # keep full height here
            back_wall = make_entity(
                scale=(self.width, self.height, 0),
                position=(0, wall_y_center_full, back_z),
                texture=self.wall_texture,
                texture_scale=(math.ceil(self.width / self.height), 1)
            )
            self.entities.append(back_wall)
            
            # Grass + treeline directly behind room 0
            seg_len = 16
            grass = make_entity(
                scale=(OUTDOOR_WORLD_X + (TREELINE_INSET * 2), 0, seg_len + TREELINE_INSET),
                position=(0, FLOOR_Y, back_z - (seg_len + TREELINE_INSET) / 2),
                texture=get_texture('data/graphics', 'grass'),
                texture_scale=(math.ceil((OUTDOOR_WORLD_X + (TREELINE_INSET * 2)) / 6), math.ceil((seg_len + TREELINE_INSET) / 6))
            )
            tree_back = make_entity(
                scale=(OUTDOOR_WORLD_X, TREELINE_HEIGHT, 0),
                position=(0, FLOOR_Y + TREELINE_HEIGHT / 2, back_z - seg_len),
                texture=get_texture('data/graphics', 'trees'),
                texture_scale=(math.ceil(OUTDOOR_WORLD_X / TREELINE_HEIGHT), 1)
            )
            for sx in (-OUTDOOR_WORLD_X, OUTDOOR_WORLD_X):
                self.entities.append(make_entity(
                    scale=(0, TREELINE_HEIGHT, seg_len),
                    position=(sx / 2, FLOOR_Y + TREELINE_HEIGHT / 2, back_z - seg_len / 2),
                    texture=get_texture('data/graphics', 'trees'),
                    texture_scale=(math.ceil(seg_len / TREELINE_HEIGHT), 1)
                ))
            self.entities += [grass, tree_back]

    def _build_pitted_floor(self, floor_width: float):
        half_width = floor_width / 2.0
        half_length = self.length / 2.0

        # Pick pit size as a fraction of room size, clamped to sane limits
        pit_width = min(floor_width * 0.6,
                        max(4.0, floor_width * random.uniform(0.25, 0.4)))
        pit_length = min(self.length * 0.6,
                         max(4.0, self.length * random.uniform(0.25, 0.45)))

        pit_half_w = pit_width / 2.0
        pit_half_l = pit_length / 2.0

        # Pit is centred in the room for now
        pit_center_x = 0.0
        pit_center_z = self.center_z

        pit_min_x = pit_center_x - pit_half_w
        pit_max_x = pit_center_x + pit_half_w
        pit_min_z = pit_center_z - pit_half_l
        pit_max_z = pit_center_z + pit_half_l
        
        # Store pit meta so other code (props) can avoid it
        self.has_pit = True
        self.pit_bounds = (pit_min_x, pit_max_x, pit_min_z, pit_max_z)

        # -------- Floor tiles around the hole --------

        # Front strip (before pit, along -Z)
        front_start_z = self.center_z - half_length
        front_len = pit_min_z - front_start_z
        if front_len > 0.5:
            front = make_entity(
                scale=(floor_width, 0, front_len),
                position=(0, FLOOR_Y, front_start_z + front_len / 2.0),
                texture=self.floor_texture,
                texture_scale=(math.ceil(floor_width / 8), math.ceil(front_len / 8))
            )
            self.entities.append(front)

        # Back strip (after pit, along +Z)
        back_end_z = self.center_z + half_length
        back_len = back_end_z - pit_max_z
        if back_len > 0.5:
            back = make_entity(
                scale=(floor_width, 0, back_len),
                position=(0, FLOOR_Y, pit_max_z + back_len / 2.0),
                texture=self.floor_texture,
                texture_scale=(math.ceil(floor_width / 8), math.ceil(back_len / 8))
            )
            self.entities.append(back)

        # Left walkway along the pit
        left_width = pit_min_x - (-half_width)
        if left_width > 0.5:
            left = make_entity(
                scale=(left_width, 0, pit_length),
                position=(-half_width + left_width / 2.0,
                          FLOOR_Y,
                          pit_center_z),
                texture=self.floor_texture,
                texture_scale=(math.ceil(left_width / 8), math.ceil(pit_length / 8))
            )
            self.entities.append(left)

        # Right walkway along the pit
        right_width = half_width - pit_max_x
        if right_width > 0.5:
            right = make_entity(
                scale=(right_width, 0, pit_length),
                position=(half_width - right_width / 2.0,
                          FLOOR_Y,
                          pit_center_z),
                texture=self.floor_texture,
                texture_scale=(math.ceil(right_width / 8), math.ceil(pit_length / 8))
            )
            self.entities.append(right)

        # -------- Pit walls + bottom --------
        depth = 6.0
        wall_y_center = FLOOR_Y - depth / 2.0
        bottom_y = FLOOR_Y - depth

        # Front wall (towards -Z)
        front_wall = make_entity(
            scale=(pit_width, depth, 0),
            position=(pit_center_x,
                      wall_y_center,
                      pit_min_z),
            texture=self.wall_texture,
            texture_scale=(math.ceil(pit_width / depth), 1)
        )
        self.entities.append(front_wall)

        # Back wall (towards +Z)
        back_wall = make_entity(
            scale=(pit_width, depth, 0),
            position=(pit_center_x,
                      wall_y_center,
                      pit_max_z),
            texture=self.wall_texture,
            texture_scale=(math.ceil(pit_width / depth), 1)
        )
        self.entities.append(back_wall)

        # Left wall
        left_wall = make_entity(
            scale=(0, depth, pit_length),
            position=(pit_min_x,
                      wall_y_center,
                      pit_center_z),
            texture=self.wall_texture,
            texture_scale=(math.ceil(pit_length / depth), 1)
        )
        self.entities.append(left_wall)

        # Right wall
        right_wall = make_entity(
            scale=(0, depth, pit_length),
            position=(pit_max_x,
                      wall_y_center,
                      pit_center_z),
            texture=self.wall_texture,
            texture_scale=(math.ceil(pit_length / depth), 1)
        )
        self.entities.append(right_wall)

        # Bottom of the pit (dark floor) – has a collider so you don't fall forever
        bottom = make_entity(
            scale=(pit_width, 0, pit_length),
            position=(pit_center_x,
                      bottom_y,
                      pit_center_z),
            texture='data/graphics/black.png',
            color=color.black
        )
        self.entities.append(bottom)
        
    def _spawn_random_props(self):
        if self.is_save_room:
            self.blockers_xz = []
            return
            
        # room 0: no blocking interior props, but we still allow side trees
        num_internal_walls = 0 if (self.index == 0 or self.is_outdoors) else random.randint(0, 3)

        half_width  = self.width / 2
        half_length = self.length / 2

        placed_walls = []   # (x_min, x_max, z_min, z_max)

        # ---------- OUTDOOR CRATE ----------
        if self.is_outdoors and random.random() < 0.4:
            s = 2
            z = self.center_z + random.choice([-1, 1]) * (half_length - s)
            x = random.choice([-1, 1]) * random.uniform(ROOM_DOOR_WIDTH/2 + s/2, half_width - s/2)

            crate = make_entity(
                scale=(s, s, s),
                position=(x, FLOOR_Y + s / 2, z),
                texture='data/graphics/crate.png'
            )
            self.entities.append(crate)
            placed_walls.append((x - s / 2, x + s / 2, z - s / 2, z + s / 2))

        # Treat pit as an occupied region so props don't spawn over it
        if self.pit_bounds is not None:
            pit_min_x, pit_max_x, pit_min_z, pit_max_z = self.pit_bounds
            placed_walls.append((pit_min_x, pit_max_x, pit_min_z, pit_max_z))

        def overlaps_existing(xc, zc, sx, sz, margin=0.05):
            half_x = max(abs(sx) * 0.5, 1) # give a slight margin of 1
            half_z = max(abs(sz) * 0.5, 1)
            x_min = xc - half_x
            x_max = xc + half_x
            z_min = zc - half_z
            z_max = zc + half_z
            for (ox_min, ox_max, oz_min, oz_max) in placed_walls:
                if not (
                    x_max < ox_min + margin or
                    x_min > ox_max - margin or
                    z_max < oz_min + margin or
                    z_min > oz_max - margin
                ):
                    return True
            return False

        # ---------- INTERNAL WALLS (indoors, non-start rooms) ----------
        for _ in range(num_internal_walls):
            for _attempt in range(10):
                orientation = random.choice(['across', 'along'])

                if orientation == 'across':
                    # Across the width
                    wall_length = random.uniform(self.width * 0.4, self.width * 0.9)
                    size_x = wall_length
                    size_z = 0

                    max_span = self.width - 2 * MIN_WALL_EDGE_GAP
                    if size_x >= max_span:
                        continue

                    x_center = random.uniform(
                        -half_width + MIN_WALL_EDGE_GAP + size_x / 2,
                        half_width - MIN_WALL_EDGE_GAP - size_x / 2
                    )
                    z_center = self.center_z + random.uniform(-half_length * 0.4,
                                                              half_length * 0.4)
                else:
                    # Along the corridor
                    wall_length = random.uniform(self.length * 0.3, self.length * 0.7)
                    size_x = 0
                    size_z = wall_length

                    side = random.choice([-1, 1])
                    x_center = side * (half_width - MIN_WALL_EDGE_GAP - size_x / 2)
                    x_center = max(
                        -half_width + MIN_WALL_EDGE_GAP + size_x / 2,
                        min(
                            x_center,
                            half_width - MIN_WALL_EDGE_GAP - size_x / 2
                        )
                    )
                    z_center = self.center_z + random.uniform(-half_length * 0.3,
                                                              half_length * 0.3)

                if overlaps_existing(x_center, z_center, size_x, size_z):
                    continue

                wall_entity = make_entity(
                    scale=(size_x, self.height, size_z),
                    position=(x_center, FLOOR_Y + self.height / 2, z_center),
                    texture=self.wall_texture
                )
                a = math.ceil(size_x / self.height)
                b = math.ceil(size_z / self.height)
                wall_entity.texture_scale = (max(a, b), 1)
                self.entities.append(wall_entity)

                x_min = x_center - size_x / 2
                x_max = x_center + size_x / 2
                z_min = z_center - size_z / 2
                z_max = z_center + size_z / 2
                placed_walls.append((x_min, x_max, z_min, z_max))
                break  # placed this wall, move to next

        # ---------- TABLES & CHAIRS (indoors only, non-start rooms) ----------
        if not self.is_outdoors and self.index != 0:
            def spawn_table_with_chairs(x_center: float, z_center: float):
                PROP_TEXTURE = 'data/graphics/wood.png'
                
                # Random orientation for the whole set
                rot_y = random.choice([0, 90, 180, 270])

                # ---- Table (scaled up) ----
                table_height = 1.0
                top_thickness = 0.2
                top_size_x = 2.0
                top_size_z = 1.2

                table_top = make_entity(
                    scale=(top_size_x, top_thickness, top_size_z),
                    position=(x_center, FLOOR_Y + table_height, z_center),
                    texture=PROP_TEXTURE,
                    color=color.rgb(140, 100, 70),
                    rotation=(0, rot_y, 0)
                )
                self.entities.append(table_top)

                leg_height = table_height
                leg_thickness = 0.12

                leg_offsets_local = [
                    ( top_size_x / 2 - leg_thickness / 2,  top_size_z / 2 - leg_thickness / 2),
                    (-top_size_x / 2 + leg_thickness / 2,  top_size_z / 2 - leg_thickness / 2),
                    ( top_size_x / 2 - leg_thickness / 2, -top_size_z / 2 + leg_thickness / 2),
                    (-top_size_x / 2 + leg_thickness / 2, -top_size_z / 2 + leg_thickness / 2),
                ]

                def rotate_offset(dx, dz, deg):
                    if deg == 0:
                        return dx, dz
                    elif deg == 90:
                        return -dz, dx
                    elif deg == 180:
                        return -dx, -dz
                    elif deg == 270:
                        return dz, -dx
                    return dx, dz

                for dx_local, dz_local in leg_offsets_local:
                    dx, dz = rotate_offset(dx_local, dz_local, rot_y)
                    leg = make_entity(
                        scale=(leg_thickness, leg_height, leg_thickness),
                        position=(x_center + dx,
                                  FLOOR_Y + leg_height / 2,
                                  z_center + dz),
                        texture=PROP_TEXTURE,
                        color=color.rgb(100, 70, 50)
                    )
                    self.entities.append(leg)

                # ---- Big invisible collider so the player definitely collides with the table ----
                collision_box = make_entity(
                    scale=(top_size_x * 1.05, table_height + top_thickness + 0.5, top_size_z * 1.05),
                    position=(x_center,
                              FLOOR_Y + (table_height + top_thickness + 0.5) / 2,
                              z_center),
                    visible=False
                )
                self.entities.append(collision_box)

                # ---- Chairs (scaled up) ----
                # (local_x, local_z, local_yaw_offset relative to table)
                chair_positions_local = [
                    (0.0, -(top_size_z / 2 + 0.8), 0.0),
                    (0.0,  (top_size_z / 2 + 0.8), 180.0),
                    ( top_size_x / 2 + 0.8, 0.0,   90.0),
                    (-(top_size_x / 2 + 0.8), 0.0, 270.0),
                ]

                num_chairs = random.randint(0, 4)
                random.shuffle(chair_positions_local)
                chair_positions_local = chair_positions_local[:num_chairs]

                seat_height = 0.7
                seat_size_x = 0.7
                seat_size_z = 0.7
                seat_thickness = 0.12
                back_height = 0.8
                leg_height_chair = seat_height
                leg_thickness_chair = 0.08

                for dx_local, dz_local, yaw_offset in chair_positions_local:
                    # Position: table's rotation applied to the local chair offset
                    dx, dz = rotate_offset(dx_local, dz_local, rot_y)
                    cx = x_center + dx
                    cz = z_center + dz

                    # Final yaw so chair faces the table
                    chair_yaw = (rot_y + yaw_offset) % 360

                    # Seat
                    seat = make_entity(
                        scale=(seat_size_x, seat_thickness, seat_size_z),
                        position=(cx, FLOOR_Y + seat_height, cz),
                        texture=PROP_TEXTURE,
                        color=color.rgb(180, 180, 180),
                        rotation=(0, chair_yaw, 0)
                    )
                    self.entities.append(seat)

                    # Backrest: behind the seat (opposite the table)
                    back_dx_local, back_dz_local = 0, -seat_size_z / 2
                    bdx, bdz = rotate_offset(back_dx_local, back_dz_local, chair_yaw)
                    back = make_entity(
                        collider=None,
                        scale=(seat_size_x * 0.9, back_height, seat_thickness),
                        position=(cx + bdx,
                                  FLOOR_Y + seat_height + back_height / 2,
                                  cz + bdz),
                        texture=PROP_TEXTURE,
                        color=color.rgb(150, 150, 150),
                        rotation=(0, chair_yaw, 0)
                    )
                    self.entities.append(back)

                    # Chair legs – oriented with the chair
                    leg_offsets_seat_local = [
                        ( seat_size_x / 2 - leg_thickness_chair / 2,  seat_size_z / 2 - leg_thickness_chair / 2),
                        (-seat_size_x / 2 + leg_thickness_chair / 2,  seat_size_z / 2 - leg_thickness_chair / 2),
                        ( seat_size_x / 2 - leg_thickness_chair / 2, -seat_size_z / 2 + leg_thickness_chair / 2),
                        (-seat_size_x / 2 + leg_thickness_chair / 2, -seat_size_z / 2 + leg_thickness_chair / 2),
                    ]
                    for ldx_local, ldz_local in leg_offsets_seat_local:
                        ldx, ldz = rotate_offset(ldx_local, ldz_local, chair_yaw)
                        leg = make_entity(
                            collider=None,
                            scale=(leg_thickness_chair, leg_height_chair, leg_thickness_chair),
                            position=(cx + ldx,
                                      FLOOR_Y + leg_height_chair / 2,
                                      cz + ldz),
                            texture=PROP_TEXTURE,
                            color=color.rgb(120, 120, 120)
                        )
                        self.entities.append(leg)

            # Spawn 0–3 table groups per room, avoiding walls and other tables
            table_footprint_x = 5.0
            table_footprint_z = 5.0

            num_groups = random.randint(0, 3)
            for _ in range(num_groups):
                placed = False
                for _attempt in range(12):  # try a few times to find a free spot
                    x = random.uniform(-half_width + 2.5, half_width - 2.5)
                    z = self.center_z + random.uniform(-half_length + 3.0, half_length - 3.0)

                    if overlaps_existing(x, z, table_footprint_x, table_footprint_z, margin=0.1):
                        continue

                    spawn_table_with_chairs(x, z)

                    x_min = x - table_footprint_x / 2
                    x_max = x + table_footprint_x / 2
                    z_min = z - table_footprint_z / 2
                    z_max = z + table_footprint_z / 2
                    placed_walls.append((x_min, x_max, z_min, z_max))

                    placed = True
                    break

                if not placed:
                    continue

        # ---------- BILLBOARDED TREES ----------
        size = 4
        base_dimensions = 128
        num = random.randint(16,48)
        for _ in range(num):
            for _a in range(12):
                x = random.uniform(-OUTDOOR_WORLD_X/2 + ROOM_DOOR_WIDTH, OUTDOOR_WORLD_X/2 - ROOM_DOOR_WIDTH)
                z = self.center_z + random.uniform(-half_length, half_length)

                if (
                    abs(x) < ROOM_DOOR_WIDTH or                          # avoid central footpath
                    abs(abs(x) - half_width) < ROOM_DOOR_WIDTH or        # avoid hugging side walls
                    (abs(z - (self.center_z - half_length)) < ROOM_DOOR_WIDTH and x < ROOM_X_MAX/2 and x > -ROOM_X_MAX/2) or     # avoid front edge of room
                    (abs(z - (self.center_z + half_length)) < ROOM_DOOR_WIDTH and x < ROOM_X_MAX/2 and x > -ROOM_X_MAX/2) or     # avoid back edge of room
                    overlaps_existing(x, z, size, 0.5, margin=0.1) or       # avoid overlapping other blockers/trees
                    (not self.is_outdoors and (-half_width <= x <= half_width)) # don't place trees indoors
                ):
                    continue

                tex = get_texture('data/graphics/flora')
                tree = make_entity(
                    model='quad', collider=None,
                    position=(x, FLOOR_Y, z),
                    scale=(size, size, 1),
                    texture=tex,
                    billboard=True,
                    origin_y = -0.5,
                    ignore_in_los = True
                )
                t = getattr(tree, 'texture', None)
                width_mult = getattr(t, 'width', base_dimensions) / base_dimensions
                height_mult = getattr(t, 'height', base_dimensions) / base_dimensions
                tree.scale_x = size * width_mult
                tree.scale_y = size * height_mult
                
                # add a collision pole if the tree is large enough
                if height_mult >= 0.5:
                    pole = make_entity(
                        position=(x, FLOOR_Y + size / 2, z),
                        scale=(1, size, 1),
                        visible=False
                    )
                    pole.ignore_in_los = True
                    self.entities.append(pole)

                self.entities.append(tree)
                self.billboards.append(tree)
                sx = tree.scale_x
                placed_walls.append((x - sx / 2, x + sx / 2, z - 0.25, z + 0.25))
                break

        self.blockers_xz = placed_walls

    def destroy(self):
        global doors

        # Remove every RoomDoor in this room from the global doors list
        for e in self.entities:
            if isinstance(e, RoomDoor) and e in doors:
                doors.remove(e)
            destroy(e)
            
        for e in self.entities:
            if isinstance(e, RoomDoor) and e in doors:
                doors.remove(e)
            if e in cyl_billboards:
                cyl_billboards.remove(e)
            if e in active_billboards:
                active_billboards.remove(e)
            destroy(e)

        self.entities.clear()
        self.door = None

class SavePoint(Entity):
    def __init__(self, room_index:int, pos:Vec3):
        self.room_index = room_index
        self._base_y = pos.y
        self._last_save_t = -1e9
        super().__init__(model='quad', texture='data/graphics/save.png',
                position=pos, scale=1.5, collider=None, double_sided=True)
        self.ignore_in_los = True
        self.is_save_point = True

    def update(self):
        if is_paused:
            return
        # gentle float + spin
        self.y = self._base_y + 0.35 * sin(time.time() * 1.8)
        self.rotation_y += 90 * time.dt

def connect_rooms(room_a: Room, room_b: Room):
    end_z = room_a.center_z + room_a.length / 2

    eps = 0.001
    z_a = end_z - eps   # room_a's wall plane
    z_b = end_z + eps   # room_b's wall plane

    def add_seg(r: Room, zpos: float, cx: float, w: float, h: float, tex: str, y_center: float, max_y: float):
        seg = make_entity(
            scale=(w, h, 0),
            position=(cx, y_center, zpos),
            texture=tex,
            texture_scale=(math.ceil(w / max_y), 1)
        )
        r.entities.append(seg)
        return seg

    def build_wall_for_room(r: Room, zpos: float, tex: str, with_opening: bool, add_top_filler: bool):
        w = r.width
        h = OUTDOOR_WALL_HEIGHT if r.is_outdoors else r.height
        y_mid = FLOOR_Y + h / 2

        half = w / 2
        side_w = half - ROOM_DOOR_WIDTH / 2

        # left/right segments with gap for door
        add_seg(r, zpos, -half + side_w / 2, side_w, h, tex, y_mid, h)
        add_seg(r, zpos,  half - side_w / 2, side_w, h, tex, y_mid, h)

        # top filler above doorway (indoor only)
        if add_top_filler and not r.is_outdoors:
            gap = h - ROOM_DOOR_HEIGHT
            if gap > 0:
                add_seg(
                    r, zpos,
                    0,
                    ROOM_DOOR_WIDTH,
                    gap,
                    tex,
                    FLOOR_Y + ROOM_DOOR_HEIGHT + gap / 2,
                    h
                )

    def add_main_door():
        door_pos = Vec3(0, FLOOR_Y + ROOM_DOOR_HEIGHT / 2, end_z)
        door = RoomDoor(
            width=ROOM_DOOR_WIDTH,
            height=ROOM_DOOR_HEIGHT,
            pos=door_pos,
            slide_dir=-1,
            room_number=room_b.index + 1
        )
        room_b.door = door
        room_b.entities.append(door)
        doors.append(door)

    # --- detect indoor/outdoor pairing -------------------------------------

    a_out = room_a.is_outdoors
    b_out = room_b.is_outdoors

    # Case 1: both indoor
    if (not a_out) and (not b_out):
        build_wall_for_room(room_a, z_a, room_a.wall_texture, with_opening=True,  add_top_filler=True)
        build_wall_for_room(room_b, z_b, room_b.wall_texture, with_opening=True,  add_top_filler=True)
        add_main_door()
        return

    # Case 2: both outdoor (open passage, no door)
    if a_out and b_out:
        build_wall_for_room(room_a, z_a, room_a.wall_texture, with_opening=True,  add_top_filler=False)
        build_wall_for_room(room_b, z_b, room_b.wall_texture, with_opening=True,  add_top_filler=False)
        return

    # Case 3: one indoor, one outdoor
    indoor = room_a if not a_out else room_b
    outdoor = room_a if a_out else room_b

    # 3a) indoor gets a proper doorway wall on its own plane (with top filler)
    if indoor is room_a:
        build_wall_for_room(room_a, z_a, room_a.wall_texture, with_opening=True, add_top_filler=True)
    else:
        build_wall_for_room(room_b, z_b, room_b.wall_texture, with_opening=True, add_top_filler=True)

    # 3b) outdoor gets ONLY the outer "tree/fence" segments beyond indoor width (so doorway isn't blocked)
    indoor_half  = indoor.width / 2.0
    outdoor_half = outdoor.width / 2.0
    extra = outdoor_half - indoor_half
    if extra > 0.05:
        y_out = FLOOR_Y + OUTDOOR_WALL_HEIGHT / 2.0
        z_out = z_a if outdoor is room_a else z_b

        add_seg(outdoor, z_out, -outdoor_half + extra / 2.0, extra, OUTDOOR_WALL_HEIGHT, outdoor.wall_texture, y_out, OUTDOOR_WALL_HEIGHT)
        add_seg(outdoor, z_out,  outdoor_half - extra / 2.0, extra, OUTDOOR_WALL_HEIGHT, outdoor.wall_texture, y_out, OUTDOOR_WALL_HEIGHT)

    # door exists only for the indoor side (your existing behavior)
    add_main_door()

# ------- GENERIC GROW/SHRINK HELPERS -------

def play_grow_in(e, duration=0.25, overshoot=1.1):
    base = getattr(e, '_base_scale', e.scale)
    e._base_scale = base
    e.scale = base * 0.01

    first = duration * 0.7
    e.animate_scale(base * overshoot, duration=first, curve=curve.out_back)

    invoke(
        lambda: e.animate_scale(base, duration=duration - first, curve=curve.in_quad),
        delay=first
    )

def play_shrink_out(e, duration=0.25, on_done=None):
    base = getattr(e, '_base_scale', e.scale)
    e._base_scale = base
    e.animate_scale(base * 0.01, duration=duration, curve=curve.in_quad)
    if on_done:
        invoke(on_done, delay=duration)

# ------- GHOSTS -------

class FollowGhost(Entity):
    def __init__(self, target, start_position):
        self.target       = target
        self.follow_speed = FOLLOW_ENTITY_SPEED
        self.min_distance, self.max_distance = 1.0, 40.0
        self.float_phase  = random.uniform(0, 6.28)
        self.entity_name  = "FOLLOW"

        self.age = self.leave_timer = 0.0
        self.state = 'chasing'   # 'chasing' -> 'leaving' -> 'caught'

        fog_range   = getattr(scene, 'fog_density', (0, 20))
        self.fog_end = fog_range[1] if isinstance(fog_range, (tuple, list)) and len(fog_range) >= 2 else 20

        super().__init__(
            model='quad',
            texture=get_texture('data/graphics/entity', 'follow'),
            scale=3,
            position=start_position,
            billboard=True,
            double_sided=True,
            collider=None,
        )

    def die(self):
        global ACTIVE_ENTITY_FOLLOW
        if ACTIVE_ENTITY_FOLLOW is self:
            ACTIVE_ENTITY_FOLLOW = None
        sound_mgr.set_volume('follow', 0.0)
        destroy(self)

    def update(self):
        global game_over
        if is_paused or game_over or self.state == 'caught':
            return

        dt = time.dt
        self.age += dt

        # Floating animation
        self.float_phase += dt * 1.2
        self.y = FLOOR_Y + PLAYER_HEIGHT + 0.4 + 0.4 * sin(self.float_phase)

        # Whisper volume
        dist = horizontal_distance(self.position, player.position)
        update_volume_for_distance('follow', dist, FOLLOW_ENTITY_DESPAWN_DISTANCE / 2, lerp_speed=8.0)

        dx = self.target.x - self.x
        dz = self.target.z - self.z
        dist = sqrt(dx * dx + dz * dz) if dx or dz else 0.0

        # Lifetime -> start leaving
        if self.state == 'chasing' and self.age >= FOLLOW_ENTITY_LIFETIME:
            self.state = 'leaving'
            self.leave_timer = 0.0

        if self.state == 'chasing':
            if dist > max(0.001, self.min_distance):
                dir_x = dx / dist
                dir_z = dz / dist
                speed_boost = 1.0
                if dist > self.max_distance:
                    speed_boost = 2.5
                if dist > self.fog_end:
                    speed_boost = 5.0
                step = self.follow_speed * speed_boost * dt
                self.x += dir_x * step
                self.z += dir_z * step

            if dist <= FOLLOW_ENTITY_CATCH_DISTANCE and has_line_of_sight(self, player, max_distance=FOLLOW_ENTITY_CATCH_DISTANCE):
                trigger_game_over(self)
                return

        elif self.state == 'leaving':
            self.leave_timer += dt

            if dist > 0.001:
                dir_x = -dx / dist
                dir_z = -dz / dist
                step = self.follow_speed * 2.0 * dt
                self.x += dir_x * step
                self.z += dir_z * step

            if self.leave_timer >= FOLLOW_ENTITY_LEAVE_DURATION or dist > FOLLOW_ENTITY_DESPAWN_DISTANCE:
                self.die()

class FastGhost(Entity):
    def __init__(self, start_position):
        self.speed       = FAST_ENTITY_SPEED
        self.state       = 'rushing'  # trigger_game_over sets 'caught'
        self.entity_name = "FAST"

        # Base (non-jittered) path position
        self.base_x, self.base_y, self.base_z = start_position

        super().__init__(
            model='quad',
            texture=get_texture('data/graphics/entity', 'fast'),
            scale=3,
            position=start_position,
            billboard=True,
            double_sided=True,
            collider=None,
        )

    def die(self):
        global ACTIVE_ENTITY_FAST
        if ACTIVE_ENTITY_FAST is self:
            ACTIVE_ENTITY_FAST = None
        sound_mgr.set_volume('fast', 0.0)
        destroy(self)

    def update(self):
        global game_over
        if is_paused:
            return

        # Volume tracking (always)
        dist = horizontal_distance(self.position, player.position)
        update_volume_for_distance('fast', dist, FAST_ENTITY_SPAWN_DIST, lerp_speed=10.0)

        # If it's frozen from game over, don't move or jitter
        if self.state == 'caught':
            return

        dt = time.dt

        if not game_over:
            # Advance along a straight base Z path
            self.base_z += self.speed * dt

            # Per-frame RANDOM jitter (non-accumulating)
            jx = random.uniform(-0.25, 0.25)
            jy = random.uniform(-0.25, 0.25)
            jz = random.uniform(-0.25, 0.25)

            # Apply jitter around the base path
            self.x = self.base_x + jx
            self.y = self.base_y + jy
            self.z = self.base_z + jz

            # Instant-kill if it has line-of-sight to you
            if has_line_of_sight(self, player, max_distance=FAST_ENTITY_LOS_RANGE):
                trigger_game_over(self)
                return

        # Despawn using the base straight-line path so jitter doesn't affect lifetime
        if self.base_z > (player.z + FAST_ENTITY_SPAWN_DIST):
            self.die()

class FallGhost(Entity):
    def __init__(self, pos: Vec3):
        self.entity_name  = "FALL"
        self.float_phase  = random.uniform(0, 6.28)
        super().__init__(
            model='quad',
            texture=get_texture('data/graphics/entity', 'fall'),
            scale=1,
            position=pos,
            billboard=True,
            double_sided=True,
            collider=None,
        )

    def update(self):
        # Gentle hovering while game over
        self.float_phase += time.dt * 1.5
        self.y += 0.002 * sin(self.float_phase)

    def die(self):
        global ACTIVE_ENTITY_FALL
        if ACTIVE_ENTITY_FALL is self:
            ACTIVE_ENTITY_FALL = None
        destroy(self)

class LookGhost(Entity):
    def __init__(self, room_index: int, start_position: Vec3):
        self.room_index         = room_index
        self.entity_name        = "LOOK"
        self.state              = 'room'
        self.look_timer         = 0.0
        self.float_phase        = random.uniform(0, 6.28)
        self.is_despawning      = False
        self.target_door        = None
        self.queued_room_index  = None

        super().__init__(
            model='quad',
            texture=get_texture('data/graphics/entity', 'look'),
            scale=1,
            position=start_position,
            billboard=True,
            double_sided=True,
            collider='box',
        )
        play_grow_in(self, duration=LOOK_GROW_TIME)

    def die(self):
        global ACTIVE_ENTITY_LOOK
        if ACTIVE_ENTITY_LOOK is self:
            ACTIVE_ENTITY_LOOK = None
        destroy(self)

    def update(self):
        if is_paused:
            return

        dt = time.dt

        # Gentle hovering
        self.float_phase += dt * 1.2
        self.y = FLOOR_Y + PLAYER_HEIGHT + 0.2 + 0.25 * sin(self.float_phase)

        # No further logic while game over / despawning
        if game_over or self.is_despawning:
            return

        dist = horizontal_distance(self.position, player.position)
        clear_sight = has_line_of_sight(camera, self, max_distance=LOOK_MAX_DISTANCE)

        # Kill on contact
        if dist <= LOOK_CATCH_DISTANCE and clear_sight:
            trigger_game_over(self)
            return

        # Look tracking with LOS check
        looking = camera_is_looking_at(
            self.world_position,
            max_distance=LOOK_MAX_DISTANCE,
            fov_deg=LOOK_VIEW_ANGLE,
        )

        if looking and clear_sight:
            self.look_timer += dt
            if self.look_timer >= LOOK_DESPAWN_TIME:
                self.is_despawning = True
                sound_mgr.play('look', pitch_variation=(0.8, 1.2), position=self.position)
                play_shrink_out(self, duration=LOOK_SHRINK_TIME, on_done=self.die)
        else:
            self.look_timer = 0.0

class HurryGhost(Entity):
    def __init__(self, start_position: Vec3):
        self.entity_name = "HURRY"
        self.state       = 'charging'   # 'charging' -> 'shrinking' -> dead
        self.age         = 0.0

        super().__init__(
            model='quad',
            texture=get_texture('data/graphics/entity', 'hurry'),
            scale=2.5,
            position=start_position,
            billboard=True,
            double_sided=True,
            collider=None,   # should collide with walls and player
        )

    def die(self):
        global ACTIVE_ENTITY_HURRY
        if ACTIVE_ENTITY_HURRY is self:
            ACTIVE_ENTITY_HURRY = None
        sound_mgr.set_volume('hurry', 0.0)
        destroy(self)

    def update(self):
        if is_paused:
            return

        dt = time.dt
        self.age += dt

        dist = horizontal_distance(self.position, player.position)
        update_volume_for_distance('hurry', dist, HURRY_SOUND_RANGE, lerp_speed=10.0)

        if self.state == 'shrinking' or game_over:
            return

        # If player looks directly at it, stop and shrink away
        if camera_is_looking_at(
            self.world_position,
            max_distance=FOG_BASE_DISTANCE,
            fov_deg=HURRY_VIEW_ANGLE,
        ):
            self.state = 'shrinking'
            play_shrink_out(self, duration=LOOK_SHRINK_TIME, on_done=self.die)
            return

        if self.state == 'charging':
            # Move rapidly toward the player
            dx = player.x - self.x
            dz = player.z - self.z
            dist = sqrt(dx * dx + dz * dz) if dx or dz else 0.0

            if dist > 0.001:
                dir_x = dx / dist
                dir_z = dz / dist

                move_speed = HURRY_SPEED
                room = get_room_containing_z(player.z)
                if not is_inside_room_x(room, player.x):
                    move_speed *= HURRY_OOB_MULT

                step = move_speed * dt
                self.x += dir_x * step
                self.z += dir_z * step

            # Catch check
            if horizontal_distance(self.position, player.position) <= HURRY_CATCH_DISTANCE:
                trigger_game_over(self)

class DoomWall(Entity):
    def __init__(self):
        self.entity_name = "WALL"
        w = OUTDOOR_WORLD_X * 2
        h = TREELINE_HEIGHT * 8
        super().__init__(
            model='cube',
            texture=get_texture('data/graphics/entity', 'wall'),
            collider='box',
            scale=(w, h, 1.0),
            position=(0, FLOOR_Y, 0),
        )
        tile = 4  # world units per (square) tile
        self.texture_scale = (w / tile, h / tile)
        self.rotation_x = 5

        # UV scroll state
        self._uv_y = 0.0
        self.scroll_speed = -0.1
        self.update_speed(max(START_ROOM_INDEX - 1, 0))

    def update_speed(self, room):
        self.speed = min(
            DOOM_WALL_SPEED + DOOM_WALL_SPEED_SCALER * room,
            player.speed / 2
        )

    def update(self):
        if is_paused:
            return

        dt = time.dt
        dist = abs(player.z - self.z)
        update_volume_for_distance('wall', dist, WALL_SOUND_RANGE,
                                   lerp_speed=8.0, power=2.0)
        if game_over:
            return

        self.z += self.speed * dt

        # Scroll texture upward
        self._uv_y = (self._uv_y + self.scroll_speed * dt) % 1.0
        self.texture_offset = (0, self._uv_y)

        # Kill if it reaches you
        if dist < 1.0:
            trigger_game_over(self)

def trigger_game_over(ghost):
    global game_over, game_over_look_target, game_over_timer
    if game_over:
        return

    game_over = True
    game_over_timer = 0.0

    name = getattr(ghost, 'entity_name', '???')
    game_over_look_target = None if name == "WALL" else ghost

    if hasattr(ghost, 'state'):
        ghost.state = 'caught'

    # Disable player movement + look
    player.enabled = False
    player.gravity = 0

    # Show game-over text
    text = f"<{name}> GOT YOU"
    for t in (game_over_text_main, game_over_text_red, game_over_text_blue):
        t.text = text
        t.enabled = True
        
    # Entity-specific flavour text underneath
    detail = DEATH_MESSAGES.get(name, "You died. See you next time.")
    game_over_text_detail.text = detail
    game_over_text_detail.enabled = True

    stop_audio()
    sound_mgr.play('game_over', pitch_variation=(1, 1))

# ------- FOG FLICKER -------

def trigger_fog_flicker():
    if TEST_DISABLE_FOG:
        return
    pattern = [
        (0.00, 0.4),
        (0.06, 0.9),
        (0.12, 0.5),
        (0.18, 0.8),
        (0.26, 0.6),
        (0.36, 1.0),
    ]
    def set_mult(m):
        global FOG_FLICKER_MULT
        FOG_FLICKER_MULT = m
    for delay, mult in pattern:
        invoke(set_mult, mult, delay=delay)
    # safety: ensure we’re fully back to baseline after the sequence
    last_delay = pattern[-1][0] + 0.05
    invoke(set_mult, 1.0, delay=last_delay)
    sound_mgr.play('flicker', pitch_variation=(0.8, 1.2))

# ------- ROOM MANAGEMENT -------

def create_room():
    global next_room_index

    room = Room(next_room_index)
    rooms.append(room)
    next_room_index += 1

# ------- UTILS -------

def make_entity(*, model='cube', collider='box', **kwargs):
    bb = kwargs.pop('billboard', False)
    e = Entity(model=model, collider=collider, **kwargs)
    if bb:
        e.billboard = False
        e.enabled = False
        cyl_billboards.append(e)
    return e

def horizontal_distance(a:Vec3,b:Vec3)->float:
    return sqrt((a.x-b.x)**2+(a.z-b.z)**2)

def get_room_by_index(idx:int):
    return next((r for r in rooms if r.index==idx),None)

def get_room_containing_z(z:float):
    return next((r for r in rooms if r.center_z-r.length/2<=z<r.center_z+r.length/2),None)
    
def is_inside_room_x(room, x:float, margin:float=0.0)->bool:
    return bool(room and -room.width/2-margin<=x<=room.width/2+margin)
    
def is_inside_room_z(room,z:float,margin:float=0.0)->bool:
    return bool(room and room.center_z-room.length/2-margin<=z<=room.center_z+room.length/2+margin)

def _segment_hits_aabb(p0:Vec3,p1:Vec3,bmin:Vec3,bmax:Vec3)->bool:
    d=p1-p0;tmin,tmax=0.0,1.0
    for axis in('x','y','z'):
        o=getattr(p0,axis);v=getattr(d,axis)
        mn=getattr(bmin,axis);mx=getattr(bmax,axis)
        if abs(v)<1e-8:
            if o<mn or o>mx:return False
            continue
        t1,t2=(mn-o)/v,(mx-o)/v
        if t1>t2:t1,t2=t2,t1
        tmin=max(tmin,t1);tmax=min(tmax,t2)
        if tmin>tmax:return False
    return True

def has_line_of_sight(source:Entity,target:Entity,max_distance:float|None=None)->bool:
    def eye_pos(ent:Entity)->Vec3:
        if ent in(player,camera):return camera.world_position
        c=ent.world_position;s=getattr(ent,'world_scale',ent.scale);h=abs(s.y)
        if h<1e-3:return c+Vec3(0,0.5,0)
        eye_y=c.y-h*0.5+h*0.8
        return Vec3(c.x,eye_y,c.z)

    p0,p1=eye_pos(source),eye_pos(target)
    d=p1-p0;dist=d.length()
    if dist<=0.01:return True
    if max_distance is not None and dist>max_distance:return False

    eps=0.05
    for ent in scene.entities:
        if ent in(source,target):continue
        if not getattr(ent,'enabled',True):continue
        if not getattr(ent,'collider',None):continue
        if getattr(ent,'ignore_in_los',False):continue

        center=ent.world_position
        s=getattr(ent,'world_scale',ent.scale)
        hx,hy,hz=abs(s.x)*0.5,abs(s.y)*0.5,abs(s.z)*0.5

        rot=getattr(ent,'world_rotation',ent.rotation)
        yaw=radians(rot.y);c=abs(cos(yaw));sn=abs(sin(yaw))
        hx2=hx*c+hz*sn;hz2=hx*sn+hz*c

        half=Vec3(max(hx2,eps),max(hy,eps),max(hz2,eps))
        if _segment_hits_aabb(p0,p1,center-half,center+half):return False
    return True
    
def _update_game_over_camera():
    if not game_over or not getattr(game_over_look_target, 'enabled', False):
        return

    cam_pos = camera.world_position
    tgt_pos = game_over_look_target.world_position

    dx = tgt_pos.x - cam_pos.x
    dy = tgt_pos.y - cam_pos.y
    dz = tgt_pos.z - cam_pos.z
    horiz = sqrt(dx * dx + dz * dz)

    if horiz < 0.001:
        desired_yaw   = player.rotation_y
        desired_pitch = -90.0 if dy > 0 else 90.0
    else:
        desired_yaw   = degrees(atan2(dx, dz))
        desired_pitch = -degrees(atan2(dy, horiz))

    t = min(1.0, 2.5 * time.dt)

    # Yaw on player
    diff = (desired_yaw - player.rotation_y + 180.0) % 360.0 - 180.0
    player.rotation_y += diff * t

    # Pitch on camera pivot (BetterFirstPerson style)
    pivot = camera.parent or camera
    cur_pitch = pivot.rotation_x
    new_pitch = cur_pitch + (desired_pitch - cur_pitch) * t
    pivot.rotation_x = max(-89.0, min(89.0, new_pitch))

def camera_is_looking_at(world_pos:Vec3,max_distance:float,fov_deg:float)->bool:
    if game_over or is_paused:return False
    to_target=world_pos-camera.world_position
    dist=to_target.length()
    if not(0.01<dist<=max_distance):return False
    dir_to_target=to_target.normalized()
    dot=camera.forward.dot(dir_to_target)
    return dot>0.0 and dot>=cos(radians(fov_deg))

def move_doom_wall_to_back():
    if DOOM_WALL is None or not rooms:return
    back = min(r.center_z - r.length/2 for r in rooms)
    if rooms[0].index==0 and not TEST_FORCE_SPAWN_WALL:back -= WALL_SOUND_RANGE*2
    if rooms[0].index==0 or DOOM_WALL.z<back: DOOM_WALL.z = back

def _update_fog_for_index(idx: int):
    if TEST_DISABLE_FOG:
        return
    dist = max(FOG_MIN_DISTANCE, FOG_BASE_DISTANCE - FOG_INCREMENT * max(0, idx))
    dist *= FOG_FLICKER_MULT
    scene.fog_density = (0, dist)
    camera.clip_plane = (0.1, dist)
    application.base.camLens.setNearFar(0.1, dist)

def _write_save_file(room_number_1based:int):
    try:
        Path('save.txt').write_text(str(room_number_1based), encoding='utf-8')
        save_notify_text.enabled = True
        invoke(lambda: setattr(save_notify_text, 'enabled', False), delay=1.2)
        print(f"[save] wrote save.txt = {room_number_1based}")
    except Exception as e:
        print(f"[save] FAILED to write save.txt: {e}")

# ------- GHOST SPAWN HELPERS -------

def get_scaled_spawn_chance(room_index: int, scale: float = 1.0) -> float:
    room_num = max(1, room_index + 1)  # index 0 -> room 1
    chance = BASE_SPAWN_CHANCE * scale * (1.0 + (room_num - 1) * SPAWN_SCALER)
    return min(chance, BASE_SPAWN_CAP)

def spawn_entity_fall_and_kill():
    global ACTIVE_ENTITY_FALL
    if game_over or ACTIVE_ENTITY_FALL is not None:return
    pos=Vec3(player.x,player.y+FALL_ENTITY_HEIGHT,player.z)
    ACTIVE_ENTITY_FALL=FallGhost(pos)
    trigger_game_over(ACTIVE_ENTITY_FALL)

def on_enter_room(room_index: int):
    global doors_opened

    if doors_opened <= 0 or TEST_DISABLE_SPAWN_RANDOM:
        return

    room_obj = get_room_by_index(room_index + 1)
    if not room_obj or room_obj.is_outdoors or room_obj.is_save_room:
        return

    do_flicker = (
        _attempt_spawn_entity_follow(room_index)
        or _attempt_spawn_entity_fast(room_index)
        or _attempt_spawn_entity_look(room_index + 1)
    )

    if DOOM_WALL is not None:
        DOOM_WALL.update_speed(max_room_index)

    if do_flicker:
        trigger_fog_flicker()

def _attempt_spawn_entity_follow(room_index: int):
    global ACTIVE_ENTITY_FOLLOW

    if ACTIVE_ENTITY_FOLLOW is not None:
        return False

    if not TEST_FORCE_SPAWN_FOLLOW:
        chance = get_scaled_spawn_chance(room_index, SPAWN_SCALE_ENTITY)
        if random.random() > chance:
            return False

    # Try a few rooms away, else fallback to current
    candidates = [
        i for i in (room_index - 3, room_index + 3)
        if 0 <= i < next_room_index and get_room_by_index(i)
    ] or [room_index]

    room = get_room_by_index(random.choice(candidates))
    if room is None:
        return False

    half_len = room.length / 2.0
    spawn_z = room.center_z + random.uniform(-half_len * 0.3, half_len * 0.3)
    spawn_x = random.uniform(-room.width * 0.25, room.width * 0.25)
    start_pos = Vec3(spawn_x, FLOOR_Y + PLAYER_HEIGHT, spawn_z)

    ACTIVE_ENTITY_FOLLOW = FollowGhost(player, start_position=start_pos)
    return True

def _attempt_spawn_entity_fast(room_index: int):
    global ACTIVE_ENTITY_FAST

    if ACTIVE_ENTITY_FAST is not None:
        return False

    if not TEST_FORCE_SPAWN_FAST:
        chance = get_scaled_spawn_chance(room_index, SPAWN_SCALE_FAST)
        if random.random() > chance:
            return False

    # Was spawn_entity_fast()
    start_z = player.z - FAST_ENTITY_SPAWN_DIST
    start_pos = Vec3(0.0, FLOOR_Y + PLAYER_HEIGHT, start_z)
    ACTIVE_ENTITY_FAST = FastGhost(start_pos)

    return True

def _attempt_spawn_entity_look(room_index: int) -> bool:
    global ACTIVE_ENTITY_LOOK

    # Chance roll (unless test-forced)
    if not TEST_FORCE_SPAWN_LOOK:
        if random.random() > get_scaled_spawn_chance(room_index, SPAWN_SCALE_LOOK):
            return False

    room = get_room_by_index(room_index)
    if not room:
        return False

    half_len = room.length * 0.5
    obstacles = getattr(room, 'blockers_xz', ()) or ()

    def overlaps_obstacle(x: float, z: float, margin: float = 0.4) -> bool:
        return any(
            (x_min - margin) < x < (x_max + margin)
            and (z_min - margin) < z < (z_max + margin)
            for x_min, x_max, z_min, z_max in obstacles
        )

    fallback_pos = None

    for _ in range(32):
        x = random.uniform(-room.width * 0.35, room.width * 0.35)
        z = room.center_z + random.uniform(-half_len * 0.3, half_len * 0.3)
        pos = Vec3(x, FLOOR_Y + PLAYER_HEIGHT, z)

        # Not on top of the player
        if horizontal_distance(pos, player.position) < LOOK_MIN_SPAWN_DISTANCE:
            continue

        # Avoid blocking geometry
        if overlaps_obstacle(x, z):
            continue

        # Prefer spots *not* currently in view
        in_view = camera_is_looking_at(
            pos,
            max_distance=LOOK_MAX_DISTANCE,
            fov_deg=LOOK_VIEW_ANGLE,
        )

        if not in_view:
            ACTIVE_ENTITY_LOOK = LookGhost(room_index, pos)
            return True

        # Keep a fallback that's valid but visible
        if fallback_pos is None:
            fallback_pos = pos

    # If no hidden spot found, but we have a valid fallback, spawn anyway (even in view)
    if fallback_pos is not None:
        ACTIVE_ENTITY_LOOK = LookGhost(room_index, fallback_pos)
        return True

    return False

def notify_door_opened(door):
    global ACTIVE_ENTITY_LOOK
    lg = ACTIVE_ENTITY_LOOK
    if not lg or getattr(lg, 'state', None) != 'room' or getattr(lg, 'is_despawning', False):
        return

    door_room = next((r for r in rooms if r.door is door), None)
    if not door_room:
        return

    spawn_idx = door_room.index - 1
    if lg.room_index != spawn_idx or current_room_index != spawn_idx:
        return

    lg.state = 'doorway'

    def _reappear():
        lg.position = Vec3(
            door.position.x,
            FLOOR_Y + PLAYER_HEIGHT,
            door.position.z - 0.15
        )
        play_grow_in(lg, duration=LOOK_GROW_TIME)

    play_shrink_out(lg, duration=LOOK_SHRINK_TIME, on_done=_reappear)

def _attempt_spawn_entity_hurry(room: Room) -> bool:
    global ACTIVE_ENTITY_HURRY

    if ACTIVE_ENTITY_HURRY is not None or TEST_DISABLE_SPAWN_HURRY:
        return False

    player_out = not is_inside_room_x(room, player.x)
    scale = SPAWN_SCALE_HURRY_OUT_BOUNDS if player_out else SPAWN_SCALE_HURRY

    if not TEST_FORCE_SPAWN_HURRY:
        if random.random() > get_scaled_spawn_chance(room.index, scale):
            return False

    # Choose side: if player is out of bounds, use nearest side; else random.
    side = -1 if player_out and player.x < 0 else (1 if player_out and player.x >= 0 else random.choice([-1, 1]))
    x_pos = side * OUTDOOR_WORLD_X

    spawn_z = random.uniform(room.center_z - room.length, room.center_z + room.length)
    start_pos = Vec3(x_pos, FLOOR_Y + PLAYER_HEIGHT, spawn_z)

    ACTIVE_ENTITY_HURRY = HurryGhost(start_pos)
    return True

# ------- MAIN UPDATE LOOP -------

def update():
    global rooms, next_room_index, current_room_index, raw_index, max_room_index, game_over_timer
    global footstep_cooldown, last_player_pos, current_floor_material, doors_opened
    global hurry_spawn_timer, door_labels

    if is_paused:
        return

    focused = application.base.win.get_properties().get_foreground()
    if not focused:
        player.enabled = False
        return
    elif not game_over:
        player.enabled = True

    dt = time.dt

    # ---------- Find room under / near player ----------
    room_obj = get_room_containing_z(player.z)
    if room_obj is None and rooms:
        room_obj = min(rooms, key=lambda r: abs(r.center_z - player.z))
    raw_index = room_obj.index if room_obj else 0
    _update_fog_for_index(raw_index)
    
    # ---------- Doom wall speed modifier for save rooms ----------
    if DOOM_WALL is not None and not game_over:
        DOOM_WALL.update_speed(max_room_index)
        if room_obj.is_save_room:
            DOOM_WALL.speed = DOOM_WALL_SPEED
    
    # ---------- Maintain rooms ----------
    if not game_over and room_obj and rooms:
        if rooms[-1].index - room_obj.index < ROOMS_PREBUILT:
            create_room()
        while rooms and room_obj.index - rooms[0].index > ROOMS_KEEP_LOAD:
            r = rooms.pop(0)
            r.destroy()
            move_doom_wall_to_back()
            
    # ---------- Auto-open doors (one-way based on rotation) ----------
    if not getattr(player, 'is_crouching', False):
        for d in doors:
            if not isinstance(d, RoomDoor) or d.is_open:
                continue

            ry = d.rotation_y % 360

            # Side doors (on left/right walls): rotation ~ ±90°
            if abs(ry - 90.0) < 45.0 or abs(ry - 270.0) < 45.0:
                # Only open from the interior side (toward the corridor).
                # Right wall: door.x > 0, interior is x <= door.x
                # Left wall : door.x < 0, interior is x >= door.x
                if d.position.x > 0:
                    # right wall: if you're further right than the door, you're outside
                    if player.x > d.position.x:
                        continue
                else:
                    # left wall: if you're further left than the door, you're outside
                    if player.x < d.position.x:
                        continue

            else:
                # Corridor doors (between rooms): rotation ~ 0°/180°
                # Only open if you're on the "start side" (lower Z).
                if player.z > d.position.z:
                    continue

            # Passed one-way check, now distance check
            if horizontal_distance(player.position, d.position) < 4.0:
                d.open()
                if d.room_number is not None and d.room_number > max_room_index:
                    doors_opened += 1
                    invoke(on_enter_room, raw_index, delay=2.0)

    # ---------- Sticky room index ----------
    if not game_over and room_obj and raw_index != current_room_index:
        if is_inside_room_x(room_obj, player.x):
            current_room_index = raw_index
            if raw_index > max_room_index:
                max_room_index = raw_index
                
            # ----- SAVE ROOM: force Follow to leave on entry -----
            if room_obj.is_save_room and ACTIVE_ENTITY_FOLLOW is not None:
                if getattr(ACTIVE_ENTITY_FOLLOW, 'state', None) == 'chasing':
                    ACTIVE_ENTITY_FOLLOW.state = 'leaving'
                    ACTIVE_ENTITY_FOLLOW.leave_timer = 0.0
                    ACTIVE_ENTITY_FOLLOW.age = FOLLOW_ENTITY_LIFETIME

    # ---------- HURRY spawn logic ----------
    if not game_over and room_obj:
        inside_x = is_inside_room_x(room_obj, player.x)
        outdoors_or_oob = room_obj.is_outdoors or not inside_x

        if outdoors_or_oob:
            hurry_spawn_timer += dt
            if hurry_spawn_timer >= HURRY_SPAWN_INTERVAL:
                hurry_spawn_timer -= HURRY_SPAWN_INTERVAL
                _attempt_spawn_entity_hurry(room_obj)
        else:
            hurry_spawn_timer = 0.0
    else:
        hurry_spawn_timer = 0.0

    # ---------- Floor material ----------
    if room_obj and is_inside_room_x(room_obj, player.x) and is_inside_room_z(room_obj, player.z):
        tex = getattr(room_obj, 'floor_texture', None)
        current_floor_material = Path(tex).stem.lower() if tex else 'default'
        if room_obj.is_outdoors and abs(player.x) <= ROOM_DOOR_WIDTH * 0.5:
            current_floor_material = "path"
    else:
        current_floor_material = 'grass'
        
    # ---------- Movement / footsteps / pit logic ----------
    if last_player_pos is None:
        last_player_pos = Vec3(player.x, player.y, player.z)
        return

    dx = player.x - last_player_pos.x
    dz = player.z - last_player_pos.z
    dist = sqrt(dx * dx + dz * dz)
    speed = dist / max(dt, 1e-6)

    if hasattr(player, 'grounded'):
        grounded = bool(player.grounded)
    else:
        dy = player.y - last_player_pos.y
        grounded = abs(dy) < 0.02

    # If grounded on something that's neither the floor nor the roof, treat as default
    on_floor = abs(player.y - FLOOR_Y) < 1
    roof_y = FLOOR_Y + room_obj.height if room_obj and not room_obj.is_outdoors else None
    on_roof = roof_y is not None and abs(player.y - roof_y) < 1
    if grounded and not on_floor and not on_roof:
        current_floor_material = 'default'

    # Apply surface-based movement speed (grass = 75% speed)
    player.speed = player._base_speed * (0.75 if current_floor_material == 'grass' and grounded else 1.0)

    # Pit death check
    if (
        not game_over
        and room_obj
        and getattr(room_obj, 'pit_bounds', None) is not None
        and player.y < FLOOR_Y - 0.5
        and grounded
    ):
        pit_min_x, pit_max_x, pit_min_z, pit_max_z = room_obj.pit_bounds
        if pit_min_x < player.x < pit_max_x and pit_min_z < player.z < pit_max_z:
            spawn_entity_fall_and_kill()

    # Footsteps
    if not grounded or game_over:
        footstep_cooldown = 0.0
    else:
        if speed > 0.5:
            footstep_cooldown -= dt
            if footstep_cooldown <= 0.0:
                keys = FOOTSTEP_SFX_MAP.get(current_floor_material) or FOOTSTEP_SFX_MAP.get('default', [])
                if keys:
                    key = random.choice(keys)
                    sound_mgr.play(key, pitch_variation=(0.8, 1.2))

                base_interval, min_interval = 1.0, 0.5
                t = max(0.0, min(1.0, (speed - 1.0) / 4.0))
                footstep_cooldown = base_interval - t * (base_interval - min_interval)
        else:
            footstep_cooldown = 0.0

    last_player_pos = Vec3(player.x, player.y, player.z)

    # ---------- HUD ----------
    room_counter_text.text = f"Room: {current_room_index + 1}"

    # ---------- Fade door labels like fog ----------
    alive = []
    fog_end = getattr(scene, 'fog_density', (0, FOG_BASE_DISTANCE))[1]
    for label, base_col in door_labels:
        if getattr(label, '_destroyed', False):
            continue
        try:
            if not label.enabled:
                alive.append((label, base_col))
                continue

            d = (label.world_position - camera.world_position).length()
            alpha = 0.0 if d >= fog_end else max(0.0, 1.0 - d / fog_end)
            label.color = color.rgba(base_col.r, base_col.g, base_col.b, alpha)
            alive.append((label, base_col))
        except Exception:
            continue
    door_labels = alive
    
    # ---------- Custom billboard rotation ----------
    _update_cylindrical_billboards()

    # ---------- Game-over camera & glitch text ----------
    if game_over:
        game_over_timer += dt
        _update_game_over_camera()

        base = Vec2(0, 0)
        jitter = 0.005
        game_over_text_main.position = base
        game_over_text_red.position = base + Vec2(
            (random.random() - 0.5) * jitter,
            (random.random() - 0.5) * jitter,
        )
        game_over_text_blue.position = base + Vec2(
            (random.random() - 0.5) * jitter,
            (random.random() - 0.5) * jitter,
        )

# ------- RESET / INPUT / HUD -------

def stop_audio():
    global last_player_pos,footstep_cooldown
    last_player_pos=None;footstep_cooldown=0.0
    for k in sound_mgr._sounds:sound_mgr.set_volume(k,0.0)

def die_all_entities():
    for ent in list(scene.entities):
        die=getattr(ent,'die',None)
        if callable(die):
            try:die()
            except Exception as e:print(f"Error calling die() on {ent}: {e}")

def reset_game():
    global rooms,doors,next_room_index,current_room_index,raw_index,max_room_index,doors_opened
    global game_over,game_over_timer,game_over_look_target, last_billboard_room

    if FORCE_REPEAT_SEED:
        random.seed(GAME_RNG_SEED)

    stop_audio()
    for r in rooms:r.destroy()
    rooms.clear();doors.clear()
    die_all_entities()
    
    rooms.clear()
    cyl_billboards.clear()
    active_billboards.clear()
    last_billboard_room = None
    door_labels.clear()

    start = max(START_ROOM_INDEX, 1) - 1
    if START_ROOM_INDEX <= 1:
        try:
            start = max(int(Path('save.txt').read_text(encoding='utf-8').strip() or '1'), 1) - 1
        except Exception:
            pass
    
    first = max(0,start-ROOMS_KEEP_LOAD)
    last  = start+ROOMS_KEEP_LOAD

    next_room_index    = first
    current_room_index = start
    raw_index          = start
    max_room_index     = current_room_index + 1
    doors_opened       = 0

    for _ in range(last-first+1):create_room()
    start_room = get_room_by_index(start) or rooms[0]

    player.enabled = True
    player.gravity = 1
    player.position = Vec3(0,FLOOR_Y,start_room.center_z)
    player.rotation = camera.rotation = camera.parent.rotation = Vec3(0,0,0)

    move_doom_wall_to_back()

    game_over = False
    game_over_timer = 0.0
    game_over_look_target = None
    for t in (game_over_text_main,game_over_text_red,game_over_text_blue,game_over_text_detail): t.enabled = False
    room_counter_text.text = "Room: 1"
    set_paused(False)

def set_paused(value:bool):
    global is_paused
    is_paused=value
    pause_text.enabled=value
    mouse.locked=not value
    if value:
        player.enabled=False
        stop_audio()
    elif not game_over:
        player.enabled=True

def input(key):
    global game_over,is_paused
    if key=='escape':
        application.quit() if game_over else set_paused(not is_paused)
        return
    if key=='r':reset_game()
    if is_paused and key=='q':application.quit()
    
    # --- CLICK SAVE POINT ---
    if key=='left mouse down' and not is_paused and not game_over:
        room = get_room_containing_z(player.z)
        if not room.is_save_room: return
        sp = next(e for e in room.entities if getattr(e,'is_save_point',False))

        now=time.time()
        if now-sp._last_save_t<1.2: return
        sp._last_save_t=now

        if camera_is_looking_at(sp.world_position, max_distance=4.0, fov_deg=10.0) and has_line_of_sight(camera, sp, max_distance=4.0) and horizontal_distance(player.position, sp.world_position)<=4.0:
            sound_mgr.play('save')
            _write_save_file(current_room_index+1)

# HUD text
seed_text = Text(
    text=f"Seed: {GAME_RNG_SEED}",
    position=(-0.85, 0.45),
    origin=(-0.5, 0),
    scale=1,
    background=True
)

room_counter_text = Text(
    text="Room: _____",
    position=(0.75, 0.45),
    origin=(0.5, 0),
    scale=1,
    background=True
)

save_notify_text = Text(
    text="SAVED",
    position=(0, 0),
    origin=(0, 0),
    scale=4,
    background=True,
    enabled=False
)

# Pause overlay (transparent film over the game)
pause_text = Text(
    text="PAUSED\n\nESC = Resume\nQ = Quit",
    parent=camera.ui,
    origin=(0, 0),
    position=(0, 0.1),
    scale=1.2,
    color=color.white,
    z=-1,                                   # in front of the overlay
    enabled=False
)

# Game over text
def make_go_text(col):
    return Text(
        origin=(0, 0),
        position=(0, 0),
        scale=2,
        color=col,
        use_tags=False,
        enabled=False
    )

game_over_text_main = make_go_text(color.white)
game_over_text_red  = make_go_text(color.rgba32(255, 0, 0, 180))
game_over_text_blue = make_go_text(color.rgba32(0, 200, 255, 180))

game_over_text_detail = Text(
    origin=(0, 0),
    position=(0, -0.1),
    scale=1.0, 
    color=color.white,
    use_tags=False,
    enabled=False
)

# World setup

sound_mgr = SoundManager()

if not TEST_KILL_WALL and not DOOM_WALL:
    DOOM_WALL = DoomWall()
    
load_sounds_directory('data/audio', base_volume=0.8)
load_sounds_directory('data/audio/entity')
load_sounds_directory('data/audio/entity/loop', loop=True)
FOOTSTEP_SFX_MAP = load_sounds_directory('data/audio/steps', base_volume=.6)

reset_game()
app.run()
