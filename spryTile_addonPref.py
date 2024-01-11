import bpy
from . import addon_updater_ops
import rna_keymap_ui

class SprytileAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    print(bl_idname)
    preview_transparency: bpy.props.FloatProperty(
        name="Preview Alpha",
        description="Transparency level of build preview cursor",
        default=0.8,
        min=0,
        max=1
    )

    auto_adjust_viewport_shading: bpy.props.BoolProperty(
        name="Automatically switch viewport to Material Preview mode",
        description="If enabled, viewport shading mode will change to Material Preview while using Sprytile tools",
        default=True,
    )

    auto_pixel_viewport: bpy.props.BoolProperty(
        name="Automatically setup pixel viewport",
        description="If enabled, loading a tileset will automatically setup the pixel viewport.\nDisable if you're not going for a flatshaded look",
        default=False,
    )

    default_pixel_density: bpy.props.IntProperty(
        name="Pixel Density",
        description="How many pixels are displayed in one world unit",
        default=32,
        min=8
    )

    default_grid: bpy.props.IntVectorProperty(
        name="Grid Size",
        description="Tileset grid size, in pixels",
        min=1,
        size=2,
        subtype='XYZ',
        default=(32, 32)
    )

    default_pad_offset: bpy.props.FloatProperty(
        name="Subpixel Padding",
        description="Default subpixel edge padding for tilesets",
        default=0.05,
        min=0.05,
        max=0.20
    )

    auto_grid_setup: bpy.props.BoolProperty(
        name="Automatically setup grid",
        description="If enabled, loading a tileset will set the grid size to the chosen pixel density.",
        default=True,
    )

    def set_picker(self, value):
        if "tile_picker_key" not in self.keys():
            self["tile_picker_key"] = 1
        if "tile_sel_move_key" not in self.keys():
            self["tile_sel_move_key"] = 2
        if value != self["tile_sel_move_key"]:
            self["tile_picker_key"] = value

    def get_picker(self):
        if "tile_picker_key" not in self.keys():
            self["tile_picker_key"] = 1
        return self["tile_picker_key"]

    tile_picker_key: bpy.props.EnumProperty(
        items=[
            ("Alt", "Alt", "Press Alt to pick tiles", 1),
            ("Ctrl", "Ctrl", "Press Ctrl to pick tiles", 2),
            ("Shift", "Shift", "Press Shift to pick tiles", 3)
        ],
        name="Tile Picker Key",
        description="Key for using the tile picker eyedropper",
        default='Alt',
        set=set_picker,
        get=get_picker
    )

    def set_sel_move(self, value):
        if "tile_picker_key" not in self.keys():
            self["tile_picker_key"] = 1
        if "tile_sel_move_key" not in self.keys():
            self["tile_sel_move_key"] = 2
        if value != self["tile_picker_key"]:
            self["tile_sel_move_key"] = value

    def get_sel_move(self):
        if "tile_sel_move_key" not in self.keys():
            self["tile_sel_move_key"] = 1
        return self["tile_sel_move_key"]

    tile_sel_move_key: bpy.props.EnumProperty(
        items=[
            ("Alt", "Alt", "Press Alt to move tile selection", 1),
            ("Ctrl", "Ctrl", "Press Ctrl to move tile selection", 2),
            ("Shift", "Shift", "Press Shift to move tile selection", 3)
        ],
        name="Tile Selection Move Key",
        description="Key for moving the tile selection",
        default='Ctrl',
        set=set_sel_move,
        get=get_sel_move
    )

    # addon updater preferences
    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )
    updater_intrval_months: bpy.props.IntProperty(
        name='Months',
        description="Number of months between checking for updates",
        default=0,
        min=0
    )
    updater_intrval_days: bpy.props.IntProperty(
        name='Days',
        description="Number of days between checking for updates",
        default=7,
        min=0,
    )
    updater_intrval_hours: bpy.props.IntProperty(
        name='Hours',
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23
    )
    updater_intrval_minutes: bpy.props.IntProperty(
        name='Minutes',
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59
    )

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "preview_transparency")

        box = layout.box()

        box.label(text="Global Options")

        row = box.row()

        size_left_col = 0.3
        
        split = row.split(factor=size_left_col)
        col = split.column()
        col.label(text="Default Settings:")

        col = split.column(align=True)
        col.prop(self, "default_pixel_density")
        col.row().prop(self, "default_grid")
        col.prop(self, "default_pad_offset")

        row = box.row()
        split = row.split(factor=size_left_col)

        col = split.column()
        col.label(text="On Load Tileset:")
        
        col = split.column()
        col.prop(self, "auto_grid_setup")
        col.prop(self, "auto_pixel_viewport")
        
        row = box.row()
        split = row.split(factor=size_left_col)

        col = split.column()
        col.label(text="On Sprytile Edit:")

        col = split.column()
        col.prop(self, "auto_adjust_viewport_shading")

        box = layout.box()
        box.label(text = "Keyboard Shortcuts")
        box.prop(self, "tile_picker_key")
        box.prop(self, "tile_sel_move_key")

        kc = bpy.context.window_manager.keyconfigs.user
        km = kc.keymaps['Mesh']
        kmi_idx = km.keymap_items.find('sprytile.modal_tool')
        if kmi_idx >= 0:
            box.label(text="Tile Mode Shortcut")
            col = box.column()

            kmi = km.keymap_items[kmi_idx]
            km = km.active()
            col.context_pointer_set("keymap", km)
            rna_keymap_ui.draw_kmi([], kc, km, kmi, col, 0)

        addon_updater_ops.update_settings_ui(self, context)
