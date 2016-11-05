import bgl
import bpy
import bmesh
import math
from . import sprytile_gui
from bpy_extras import view3d_utils
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_plane, distance_point_to_plane
from mathutils.bvhtree import BVHTree

def get_grid_pos(position, grid_center, right_vector, up_vector, world_pixels, grid_x, grid_y):

    position_vector = position - grid_center
    pos_vector_normalized = position.normalized()

    if right_vector.dot(pos_vector_normalized) < 0:
        right_vector *= -1
    if up_vector.dot(pos_vector_normalized) < 0:
        up_vector *= -1

    x_magnitude = position_vector.dot(right_vector)
    y_magnitude = position_vector.dot(up_vector)

    x_unit = grid_x / world_pixels
    y_unit = grid_y / world_pixels

    x_snap = math.floor(x_magnitude / x_unit)
    y_snap = math.floor(y_magnitude / y_unit)

    right_vector *= x_unit
    up_vector *= y_unit

    grid_pos = grid_center + (right_vector * x_snap) + (up_vector * y_snap)

    return grid_pos, right_vector, up_vector

class SprytileModalTool(bpy.types.Operator):
    """Tile based mesh creation/UV layout tool"""
    bl_idname = "sprytile.modal_tool"
    bl_label = "Tile Paint"

    def find_view_axis(self, context):
        # Find the nearest world axis to the view axis
        scene = context.scene
        if scene.sprytile_data.lock_normal is True:
            return

        region = context.region
        rv3d = context.region_data

        # Get the view ray from center of screen
        coord = Vector( (int(region.width/2), int(region.height/2)) )
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

        # Get the up vector. The default scene view camera is pointed
        # downward, with up on Y axis. Apply view rotation to get current up
        view_up_vector = rv3d.view_rotation * Vector((0.0, 1.0, 0.0))
        # print("view up", view_up_vector)
        # print("Original forward", rv3d.view_rotation.inverted() * view_vector)

        plane_normal = self.snap_vector_to_axis(view_vector, mirrored=True)
        up_vector = self.snap_vector_to_axis(view_up_vector)

        scene.sprytile_data.paint_normal_vector = plane_normal
        scene.sprytile_data.paint_up_vector = up_vector

        if abs(plane_normal.x) > 0:
            scene.sprytile_data.normal_mode = 'X'
        elif abs(plane_normal.y) > 0:
            scene.sprytile_data.normal_mode = 'Y'
        else:
            scene.sprytile_data.normal_mode = 'Z'

    def snap_vector_to_axis(self, vector, mirrored = False):
        """Snaps a vector to the closest world axis"""
        norm_vector = vector.normalized()

        x = Vector((1.0, 0.0, 0.0))
        y = Vector((0.0, 1.0, 0.0))
        z = Vector((0.0, 0.0, 1.0))

        x_dot = 1 - abs(norm_vector.dot(x))
        y_dot = 1 - abs(norm_vector.dot(y))
        z_dot = 1 - abs(norm_vector.dot(z))
        dot_array = [x_dot, y_dot, z_dot]
        closest = min(dot_array)

        snapped_vector = x
        if closest is dot_array[0]:
            snapped_vector = x
        elif closest is dot_array[1]:
            snapped_vector = y
        else:
            snapped_vector = z

        vector_dot = norm_vector.dot(snapped_vector)
        if mirrored is False and vector_dot < 0:
            snapped_vector *= -1
        elif mirrored is True and vector_dot > 0:
            snapped_vector *= -1

        return snapped_vector

    def execute_tool(self, context, event):
        """Run the paint tool"""
        # Don't do anything if nothing to raycast on
        # or the GL GUI is using the mouse
        if self.tree is None or self.gui_use_mouse is True:
            return

        print("Execute tool")
        # get the context arguments
        scene = context.scene
        region = context.region
        rv3d = context.region_data
        coord = event.mouse_region_x, event.mouse_region_y

        # get the ray from the viewport and mouse
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)

        ray_target = ray_origin + view_vector

        # if paint mode, ray cast against object
        paint_mode = scene.sprytile_data.paint_mode
        if paint_mode == 'PAINT':
            self.execute_paint(context, ray_origin, ray_target)
        # if build mode, ray cast on plane and build face
        elif paint_mode == 'MAKE_FACE':
            self.execute_build(context, event, scene, region, rv3d, ray_origin, ray_target)
        # set normal mode...

    def object_raycast(self, obj, ray_origin, ray_target):
        matrix = obj.matrix_world.copy()
        # get the ray relative to the object
        matrix_inv = matrix.inverted()
        ray_origin_obj = matrix_inv * ray_origin
        ray_target_obj = matrix_inv * ray_target
        ray_direction_obj = ray_target_obj - ray_origin_obj

        location, normal, face_index, distance = self.tree.ray_cast(ray_origin_obj, ray_direction_obj)
        if face_index is None:
            return None, None, None, None
        location = matrix * location
        return location, normal, face_index, distance

    def execute_paint(self, context, ray_origin, ray_target):
        location, normal, face_index, distance = self.object_raycast(context.object, ray_origin, ray_target)
        if face_index is not None:
            # Change the uv of the given face
            print("Hitting face index ", face_index)

    def execute_build(self, context, event, scene, region, rv3d, ray_origin, ray_target):
        # Get view vector from center of the screen
        coord = int(region.width/2), int(region.height/2)
        view_vector = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)

        data_normal = scene.sprytile_data.paint_normal_vector
        data_up_vector = scene.sprytile_data.paint_up_vector

        plane_normal = Vector((data_normal[0], data_normal[1], data_normal[2]))
        up_vector = Vector((data_up_vector[0], data_up_vector[1], data_up_vector[2]))

        plane_normal.normalize()
        up_vector.normalize()
        right_vector = up_vector.cross(plane_normal)

        location, normal, face_index, distance = self.object_raycast(context.object, ray_origin, ray_target)
        # If raycast on the mesh, check that the hit face isn't facing
        # the same way as the plane_normal and it not coplanar to target plane
        if face_index is not None:
            check_dot = plane_normal.dot(normal)
            check_dot -= 1
            check_dot = abs(check_dot) < 0.05

            check_coplanar = distance_point_to_plane(location, scene.cursor_location, plane_normal)
            check_coplanar = abs(check_coplanar) < 0.05

            if check_dot and check_coplanar:
                return
        print("Execute build")

        plane_pos = intersect_line_plane(ray_origin, ray_target, scene.cursor_location, plane_normal)
        # Didn't hit the plane exit
        if plane_pos is None:
            return

        # print("Up vector", up_vector)
        # print("Right vector", right_vector)

        world_pixels = scene.sprytile_data.world_pixels
        target_grid = scene.sprytile_grids[context.object.sprytile_gridid]
        target_mat = bpy.data.materials[target_grid.mat_id]
        grid_x = target_grid.grid[0]
        grid_y = target_grid.grid[1]

        face_position, x_vector, y_vector = get_grid_pos(plane_pos, scene.cursor_location,
                                                        right_vector.copy(), up_vector.copy(),
                                                        world_pixels, grid_x, grid_y)
        # Convert world space position to object space
        face_position = context.object.matrix_world.copy().inverted() * face_position;

        x_dot = right_vector.dot(x_vector.normalized())
        y_dot = up_vector.dot(y_vector.normalized())
        x_positive = x_dot > 0
        y_positive = y_dot > 0
        # print("X dot:", x_dot, "\nY dot", y_dot)

        bm = bmesh.from_edit_mesh(context.object.data)

        vtx1 = bm.verts.new(face_position)
        vtx2 = bm.verts.new(face_position + y_vector)
        vtx3 = bm.verts.new(face_position + x_vector + y_vector)
        vtx4 = bm.verts.new(face_position + x_vector)

        # Quadrant II, IV
        face_order = (vtx1, vtx2, vtx3, vtx4)
        # Quadrant I, III
        if x_positive == y_positive:
            face_order = (vtx1, vtx4, vtx3, vtx2)

        face = bm.faces.new(face_order)
        bm.normal_update()
        bmesh.update_edit_mesh(context.object.data)

        # Update the collision BVHTree with new data
        self.tree = BVHTree.FromBMesh(bm)
        # Save the last normal and up vector
        scene.sprytile_data.paint_normal_vector = plane_normal
        scene.sprytile_data.paint_up_vector = up_vector
        print("Build face")

    def modal(self, context, event):
        context.area.tag_redraw()
        if event.type == 'TIMER':
            self.find_view_axis(context)
            return {'PASS_THROUGH'}

        region = context.region
        coord = Vector((event.mouse_region_x, event.mouse_region_y))
        # Pass through if outside the region
        if coord.x < 0 or coord.y < 0 or coord.x > region.width or coord.y > region.height:
            context.window.cursor_set('DEFAULT')
            return {'PASS_THROUGH'}

        context.window.cursor_set('PAINT_BRUSH')

        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            # allow navigation
            return {'PASS_THROUGH'}
        elif event.type == 'LEFTMOUSE':
            self.gui_event = event
            self.left_down = event.value == 'PRESS'
            if self.left_down:
                self.execute_tool(context, event)
            return {'RUNNING_MODAL'}
        elif event.type == 'MOUSEMOVE':
            # Update the event for the gui system
            self.gui_event = event
            if self.left_down:
                self.execute_tool(context, event)
                return {'RUNNING_MODAL'}
        # elif event.type == 'S':
        #     # Cursor snap
        #     print("Cursor snap")
        elif event.type in {'RIGHTMOUSE', 'ESC'} and self.gui_use_mouse is False:
            self.exit_modal(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.space_data.type == 'VIEW_3D':
            obj = context.object
            if obj.hide or obj.type != 'MESH':
                self.report({'WARNING'}, "Active object must be a visible mesh")
                return {'CANCELLED'}

            # Set up for raycasting with a BVHTree
            self.left_down = False
            self.tree = BVHTree.FromObject(context.object, context.scene)

            # Set up GL draw callbacks, communication between modal and GUI
            self.gui_event = None
            self.gui_use_mouse = False
            gui_args = (self, context)
            self.glHandle = bpy.types.SpaceView3D.draw_handler_add(sprytile_gui.draw_gui, gui_args, 'WINDOW', 'POST_PIXEL')
            # Set up timer callback
            self.view_axis_timer = context.window_manager.event_timer_add(0.1, context.window)

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "Active space must be a View3d")
            return {'CANCELLED'}

    def exit_modal(self, context):
        self.tree = None
        self.gui_event = None
        self.gui_use_mouse = False
        context.window.cursor_set('DEFAULT')
        context.window_manager.event_timer_remove(self.view_axis_timer)
        bpy.types.SpaceView3D.draw_handler_remove(self.glHandle, 'WINDOW')

def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)

if __name__ == '__main__':
    register()
