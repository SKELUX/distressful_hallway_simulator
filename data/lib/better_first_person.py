# better_first_person.py

from ursina import *


class BetterFirstPersonController(Entity):
    def __init__(self, **kwargs):
        # crosshair
        #self.cursor = Entity(parent=camera.ui, model='quad', color=color.white, scale=.008, rotation_z=45)
        self.cursor = Entity(parent=camera.ui, model=None, color=color.pink, scale=0, rotation_z=45)
        super().__init__()

        # --- basic movement settings ---
        self.speed = 5                      # base standing speed
        self.height = 2                     # standing "character height"
        self.camera_pivot = Entity(parent=self, y=self.height)

        # how "fat" the player is in X/Z (collision radius)
        self.radius = 0.4

        # set up camera
        camera.parent = self.camera_pivot
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = 90
        mouse.locked = True
        self.mouse_sensitivity = Vec2(40, 40)

        # movement / jump
        self.gravity = 1
        self.grounded = False
        self.jump_height = 2
        self.jump_up_duration = .5
        self.fall_after = .35
        self.jumping = False
        self.air_time = 0

        # Apply kwargs like y=..., z=..., speed=... etc
        for key, value in kwargs.items():
            setattr(self, key, value)

        # --------- CROUCH STATE ---------
        self.stand_height = self.height               # whatever height ended up as
        self.crouch_height = self.stand_height * 0.75  # how low crouch goes
        self.is_crouching = False
        self.crouch_speed_multiplier = 0.4            # move slower while crouched

        # make sure camera pivot matches current height
        self.camera_pivot.y = self.height
        # --------------------------------

        # don't start inside the floor if gravity is on
        if self.gravity:
            ray = raycast(self.world_position + (0, self.height, 0),
                          self.down, ignore=(self,))
            if ray.hit:
                self.y = ray.world_point.y

    # --------- CROUCH TOGGLE ----------
    def toggle_crouch(self):
        """Toggle crouch on/off, change view height and collision height."""
        self.is_crouching = not self.is_crouching

        target_height = self.crouch_height if self.is_crouching else self.stand_height

        # animate camera pivot so the view smoothly lowers/raises
        self.camera_pivot.animate_y(target_height, duration=.15, curve=curve.linear)

        # update the logical height used for ground raycasts
        self.height = target_height
    # ----------------------------------

    def update(self):
        # --- mouse look ---
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity[1]

        self.camera_pivot.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity[0]
        self.camera_pivot.rotation_x = clamp(self.camera_pivot.rotation_x, -90, 90)

        # --- movement input ---
        self.direction = Vec3(
            self.forward * (held_keys['w'] - held_keys['s'])
            + self.right   * (held_keys['d'] - held_keys['a'])
        ).normalized()

        # choose speed based on crouch state
        move_speed = self.speed * (self.crouch_speed_multiplier if self.is_crouching else 1.0)

        # amount we WANT to move this frame
        move = self.direction * move_speed * time.dt

        # --- SLIDING COLLISION: handle X and Z separately ---
        feet_origin = self.position + Vec3(0, 0.5, 0)
        head_origin = self.position + Vec3(0, self.height - .1, 0)

        # effective collision radius in X/Z
        radius = getattr(self, 'radius', 0.6)

        def sign(v):
            return 1 if v > 0 else -1

        # Move in X
        if abs(move.x) > 0:
            dir_x = Vec3(sign(move.x), 0, 0)
            # cast far enough to include our radius
            dist_x = abs(move.x) + radius
            feet_ray = raycast(feet_origin, dir_x, ignore=(self,), distance=dist_x, debug=False)
            head_ray = raycast(head_origin, dir_x, ignore=(self,), distance=dist_x, debug=False)
            if not feet_ray.hit and not head_ray.hit:
                self.x += move.x

        # Move in Z
        if abs(move.z) > 0:
            dir_z = Vec3(0, 0, sign(move.z))
            dist_z = abs(move.z) + radius
            feet_ray = raycast(feet_origin, dir_z, ignore=(self,), distance=dist_z, debug=False)
            head_ray = raycast(head_origin, dir_z, ignore=(self,), distance=dist_z, debug=False)
            if not feet_ray.hit and not head_ray.hit:
                self.z += move.z

        # --- gravity / ground check ---
        if self.gravity:
            ray = raycast(self.world_position + (0, self.height, 0),
                          self.down, ignore=(self,))
            if ray.distance <= self.height + .1:
                if not self.grounded:
                    self.land()
                self.grounded = True

                if ray.world_normal.y > .7 and ray.world_point.y - self.world_y < .5:
                    # walk up slope
                    self.y = ray.world_point[1]
            else:
                self.grounded = False

                # fall
                self.y -= min(self.air_time, ray.distance - .05) * time.dt * 100
                self.air_time += time.dt * .25 * self.gravity

    def input(self, key):
        # jump
        if key == 'space':
            self.jump()

        # TOGGLE CROUCH WITH LEFT SHIFT
        if key == 'left shift':
            self.toggle_crouch()

    def jump(self):
        if not self.grounded:
            return
        head_start = self.world_position + Vec3(0, self.height, 0)
        hit = raycast(
            head_start,
            Vec3(0, 1, 0),
            ignore=(self,),
            distance=self.jump_height + .1,
            debug=False
        )
        max_up = self.jump_height
        if hit.hit:
            max_up = max(0, min(self.jump_height, hit.distance - 0.05))
        if max_up <= 0.01:
            return
        self.grounded = False
        # scale jump timing for low ceilings so it never "teleports"
        frac = max_up / self.jump_height
        dur = max(0.05, self.jump_up_duration * frac)
        delay = min(dur, self.fall_after * frac)

        self.y_animator = self.animate_y(
            self.y + max_up,
            dur,
            resolution=int(1 // time.dt),
            curve=curve.out_expo
        )
        invoke(self.start_fall, delay=delay)

    def start_fall(self):
        if hasattr(self, 'y_animator') and self.y_animator:
            self.y_animator.pause()
        self.jumping = False

    def land(self):
        self.air_time = 0
        self.grounded = True

    def on_enable(self):
        mouse.locked = True
        self.cursor.enabled = True

    def on_disable(self):
        mouse.locked = False
        self.cursor.enabled = False
