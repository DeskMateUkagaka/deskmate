extends Node2D

# Real skin assets from app/skins/default/
var expressions: Array[String] = ["neutral", "happy", "sad", "surprise", "thinking"]
var textures: Dictionary = {}
var expr_index: int = 0
var click_through_enabled: bool = true

@onready var character: Sprite2D = $Character
@onready var bubble: PanelContainer = $BubbleContainer

const SKIN_DIR = "../../app/skins/default/"
const DISPLAY_HEIGHT = 400.0


func _ready() -> void:
	# Load real skin PNGs
	var skin_path = ProjectSettings.globalize_path("res://").path_join(SKIN_DIR)
	for expr in expressions:
		var path = skin_path.path_join(expr + ".png")
		var img = Image.load_from_file(path)
		if img == null:
			print("[DeskMate] WARNING: Failed to load %s" % path)
			continue
		# Scale to DISPLAY_HEIGHT keeping aspect ratio
		var scale_factor = DISPLAY_HEIGHT / img.get_height()
		var new_w = int(img.get_width() * scale_factor)
		var new_h = int(DISPLAY_HEIGHT)
		img.resize(new_w, new_h, Image.INTERPOLATE_LANCZOS)
		textures[expr] = ImageTexture.create_from_image(img)
		print("[DeskMate] Loaded %s: %dx%d -> %dx%d" % [expr, img.get_width(), img.get_height(), new_w, new_h])

	if textures.is_empty():
		print("[DeskMate] FATAL: No skin assets found!")
		get_tree().quit()
		return

	character.texture = textures[expressions[expr_index]]

	# Resize window to fit the scaled image
	var tex = character.texture
	var win_w = tex.get_width() + 40
	var win_h = tex.get_height() + 40
	DisplayServer.window_set_size(Vector2i(win_w, win_h))
	character.position = Vector2(win_w / 2.0, win_h / 2.0)

	# Reposition bubble relative to character
	bubble.offset_left = win_w / 2.0 + 20
	bubble.offset_top = 20
	bubble.offset_right = win_w - 10
	bubble.offset_bottom = 100

	_apply_bubble_style()
	bubble.visible = false

	# Full click-through by default
	DisplayServer.window_set_mouse_passthrough(PackedVector2Array())

	print("[DeskMate] Startup complete. Window: %dx%d. Press H for help." % [win_w, win_h])
	_print_help()


func _input(event: InputEvent) -> void:
	if not event is InputEventKey:
		return
	if not event.pressed:
		return

	match event.keycode:
		KEY_SPACE:
			_switch_expression()
		KEY_B:
			_toggle_bubble()
		KEY_F:
			_fade_bubble()
		KEY_T:
			_toggle_click_through()
		KEY_H:
			_print_help()
		KEY_Q, KEY_ESCAPE:
			print("[DeskMate] Quitting.")
			get_tree().quit()


func _switch_expression() -> void:
	var prev = expressions[expr_index]
	expr_index = (expr_index + 1) % expressions.size()
	var next_expr = expressions[expr_index]
	character.texture = textures[next_expr]
	# Re-apply passthrough after expression switch
	if click_through_enabled:
		DisplayServer.window_set_mouse_passthrough(PackedVector2Array())
	else:
		_set_sprite_passthrough()
	print("[DeskMate] %s Expression switched: %s -> %s. Check for bleed artifacts!" % [_timestamp(), prev, next_expr])


func _toggle_bubble() -> void:
	bubble.visible = not bubble.visible
	var state = "shown" if bubble.visible else "hidden"
	print("[DeskMate] %s Bubble %s" % [_timestamp(), state])


func _fade_bubble() -> void:
	print("[DeskMate] %s Fade animation started" % _timestamp())
	var tween = create_tween()
	if bubble.modulate.a < 0.5:
		bubble.visible = true
		tween.tween_property(bubble, "modulate:a", 1.0, 0.5)
	else:
		tween.tween_property(bubble, "modulate:a", 0.0, 0.5)
		tween.tween_callback(func(): bubble.visible = false)


func _toggle_click_through() -> void:
	click_through_enabled = not click_through_enabled
	if click_through_enabled:
		DisplayServer.window_set_mouse_passthrough(PackedVector2Array())
		print("[DeskMate] %s Click-through ENABLED (passthrough everywhere)" % _timestamp())
	else:
		_set_sprite_passthrough()
		print("[DeskMate] %s Click-through DISABLED (sprite area blocks clicks)" % _timestamp())


func _set_sprite_passthrough() -> void:
	# Use the sprite's bounding rect as the click-receiving area
	var tex = character.texture
	if tex == null:
		return
	var w = tex.get_width()
	var h = tex.get_height()
	var cx = character.position.x
	var cy = character.position.y
	var left = cx - w / 2.0
	var top = cy - h / 2.0
	var points = PackedVector2Array([
		Vector2(left, top),
		Vector2(left + w, top),
		Vector2(left + w, top + h),
		Vector2(left, top + h),
	])
	DisplayServer.window_set_mouse_passthrough(points)


func _apply_bubble_style() -> void:
	var stylebox = StyleBoxFlat.new()
	stylebox.bg_color = Color(1.0, 1.0, 1.0, 0.85)
	stylebox.corner_radius_top_left = 10
	stylebox.corner_radius_top_right = 10
	stylebox.corner_radius_bottom_left = 10
	stylebox.corner_radius_bottom_right = 10
	stylebox.content_margin_left = 12.0
	stylebox.content_margin_right = 12.0
	stylebox.content_margin_top = 8.0
	stylebox.content_margin_bottom = 8.0
	bubble.add_theme_stylebox_override("panel", stylebox)


func _timestamp() -> String:
	return "[%s]" % Time.get_time_string_from_system()


func _print_help() -> void:
	print("[DeskMate] Keyboard shortcuts:")
	print("  Space  - Cycle expression (%s)" % ", ".join(expressions))
	print("  B      - Toggle chat bubble")
	print("  F      - Fade bubble in/out")
	print("  T      - Toggle click-through mode")
	print("  H      - Show this help")
	print("  Q/Esc  - Quit")
