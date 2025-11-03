# view_overlay.py - Viewport overlay for VLM-friendly visualization

import omni.ui as ui
import omni.ui.scene as sc
import carb
from omni.kit.viewport.utility import get_active_viewport_window, get_viewport_from_window_name
from pxr import Gf, UsdGeom
import omni.usd


class TimeTravelViewportOverlay:
    """Viewport overlay for displaying time information."""
    
    def __init__(self, core):
        """Initialize the viewport overlay.
        
        Args:
            core: TimeTravelCore instance for accessing time data
        """
        self._core = core
        self._is_visible = True
        self._time_frame = None
        self._date_label = None
        self._time_label = None
        
        # Object ID labels
        self._show_object_ids = True
        self._usd_context = None
        self._objid_frame = None
        self._objid_stack = None
        self._last_data_hash = None  # Track when data changes
        self._label_manipulators = {}  # Compatibility
        
        # Create time overlay
        self._create_time_overlay()
        
        # Create object ID overlay
        self._create_object_id_overlay()
        
        carb.log_info("[ViewOverlay] Time overlay initialized")
    
    def _create_time_overlay(self):
        """Create time display overlay in bottom-right corner."""
        # Get active viewport
        viewport_window = get_active_viewport_window()
        
        if not viewport_window:
            carb.log_warn("[ViewOverlay] No active viewport found")
            return
        
        carb.log_info(f"[ViewOverlay] Active viewport found: {viewport_window}")
        
        # Create overlay frame in viewport
        try:
            with viewport_window.get_frame("timetravel_time_overlay"):
                # Create frame that fills the viewport
                self._time_frame = ui.Frame(separate_window=False)
                
                with self._time_frame:
                    # Use absolute positioning for bottom-right corner
                    with ui.HStack():
                        ui.Spacer()
                        with ui.VStack(width=220):  # Fixed width container
                            ui.Spacer()
                            # Time display box at bottom
                            with ui.ZStack(width=200, height=80):
                                # Background rectangle
                                ui.Rectangle(
                                    style={
                                        "background_color": 0xFF1A1A1A,
                                        "border_color": 0xFF00FF00,
                                        "border_width": 2,
                                        "border_radius": 5
                                    }
                                )
                                
                                # Date and Time text - centered
                                with ui.VStack(spacing=3):
                                    ui.Spacer(height=10)  # Top padding
                                    # Date label
                                    with ui.HStack():
                                        ui.Spacer(width=50)  # Small left space
                                        self._date_label = ui.Label(
                                            "2025-01-01",
                                            style={
                                                "font_size": 24,
                                                "color": 0xFFCCCCCC,
                                                "font_weight": "normal"
                                            }
                                        )
                                        ui.Spacer()  # Larger right space (pushes text left)
                                    # Time label
                                    with ui.HStack():
                                        ui.Spacer(width=50)  # Small left space
                                        self._time_label = ui.Label(
                                            "00:00:00",
                                            style={
                                                "font_size": 28,
                                                "color": 0xFFFFFFFF,
                                                "font_weight": "bold"
                                            }
                                        )
                                        ui.Spacer()  # Larger right space (pushes text left)
                                    ui.Spacer(height=10)  # Bottom padding
                            ui.Spacer(height=10)  # Bottom margin
                
                self._time_frame.visible = self._is_visible
                carb.log_info("[ViewOverlay] Time display created successfully")
        except Exception as e:
            carb.log_error(f"[ViewOverlay] Failed to create time display: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
    
    def _create_object_id_overlay(self):
        """Create viewport frame overlay for object ID labels."""
        viewport_window = get_active_viewport_window()
        
        if not viewport_window:
            carb.log_warn("[ViewOverlay] No active viewport for object ID overlay")
            return
        
        try:
            # Get USD context
            self._usd_context = omni.usd.get_context()
            
            # Create a simple text overlay frame
            with viewport_window.get_frame("timetravel_objid_overlay"):
                self._objid_frame = ui.Frame(separate_window=False)
                with self._objid_frame:
                    # Will be populated in update
                    self._objid_stack = ui.ZStack()
            
            carb.log_info("[ViewOverlay] Object ID overlay initialized (frame-based)")
        except Exception as e:
            carb.log_error(f"[ViewOverlay] Failed to create object ID overlay: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
    
    def _world_xz_to_screen(self, world_pos):
        """Convert 3D world position to 2D screen coordinates (BEV style).
        Uses only X and Z coordinates, ignoring Y (height).
        
        Args:
            world_pos: tuple of (x, y, z) in world coordinates
            
        Returns:
            tuple of (screen_x, screen_y) or None if out of bounds
        """
        try:
            viewport_api = get_active_viewport_window().viewport_api
            viewport_size = viewport_api.resolution
            
            # Define world bounds (adjust these based on your scene)
            # Get approximate bounds from current camera position
            world_x = world_pos[0]
            world_z = world_pos[2]
            
            # Simple mapping: world XZ -> screen XY
            # Assume world space ranges (you can adjust these)
            world_x_min = -3000
            world_x_max = 4000
            world_z_min = -3000
            world_z_max = 0
            
            # Normalize to 0-1
            norm_x = (world_x - world_x_min) / (world_x_max - world_x_min)
            norm_z = (world_z - world_z_min) / (world_z_max - world_z_min)
            
            # Check bounds
            if norm_x < 0 or norm_x > 1 or norm_z < 0 or norm_z > 1:
                return None
            
            # Map to screen (with margins)
            margin = 50
            screen_x = margin + norm_x * (viewport_size[0] - 2 * margin)
            screen_y = margin + norm_z * (viewport_size[1] - 2 * margin)
            
            return (screen_x, screen_y)
            
        except Exception as e:
            carb.log_error(f"[ViewOverlay] Error in world_xz_to_screen: {e}")
            return None
    
    def _update_object_id_labels(self):
        """Update object ID labels at their 2D positions (X,Z projection)."""
        if not self._show_object_ids or not hasattr(self, '_objid_frame'):
            return
        
        try:
            # Get current object data (positions)
            current_time = self._core.get_current_time()
            data = self._core.get_data_at_time(current_time)
            
            if not data:
                return
            
            # Rebuild the frame content every frame (positions change)
            self._objid_stack.clear()
            
            with self._objid_stack:
                # For each object, project X,Z to screen
                for objid, position in sorted(data.items()):
                    x, y, z = position
                    
                    # Convert world X,Z to screen coordinates
                    screen_pos = self._world_xz_to_screen((x, y, z))
                    
                    if screen_pos is None:
                        continue  # Out of bounds
                    
                    screen_x, screen_y = screen_pos
                    
                    # Use placer to position at exact coordinates
                    with ui.Placer(offset_x=screen_x - 35, offset_y=screen_y - 15):
                        with ui.ZStack(width=70, height=30):
                            ui.Rectangle(style={
                                "background_color": 0xFFFFFFFF,
                                "border_radius": 3,
                                "border_width": 1,
                                "border_color": 0xFF000000
                            })
                            ui.Label(objid, 
                                alignment=ui.Alignment.CENTER,
                                style={
                                    "font_size": 14,
                                    "color": 0xFF000000,
                                    "font_weight": "bold"
                                }
                            )
            
        except Exception as e:
            carb.log_error(f"[ViewOverlay] Error updating object ID labels: {e}")
            import traceback
            carb.log_error(traceback.format_exc())
    
    def update(self):
        """Update overlay display (called every frame)."""
        if not self._is_visible:
            return
        
        # Update time display
        if self._time_label and self._date_label:
            try:
                current_time = self._core.get_current_time()
                date_str = current_time.strftime("%Y-%m-%d")
                time_str = current_time.strftime("%H:%M:%S")
                self._date_label.text = date_str
                self._time_label.text = time_str
            except Exception as e:
                carb.log_error(f"[ViewOverlay] Error updating time: {e}")
        
        # Update object ID labels
        self._update_object_id_labels()
    
    def set_visible(self, visible: bool):
        """Show or hide the overlay."""
        self._is_visible = visible
        
        # Control time frame visibility
        if self._time_frame:
            self._time_frame.visible = visible
        
        carb.log_info(f"[ViewOverlay] Visibility set to: {visible}")
    
    def set_object_ids_visible(self, visible: bool):
        """Show or hide object ID labels."""
        self._show_object_ids = visible
        
        if visible:
            # Force update when enabling
            self._last_data_hash = None
            self._update_object_id_labels()
        else:
            # Clear frame when disabling
            if hasattr(self, '_objid_stack'):
                self._objid_stack.clear()
        
        carb.log_info(f"[ViewOverlay] Object IDs visibility set to: {visible}")
    
    def is_visible(self) -> bool:
        """Get current visibility state."""
        return self._is_visible
    
    def destroy(self):
        """Clean up overlay resources."""
        if self._time_frame:
            self._time_frame.clear()
            self._time_frame = None
        
        self._date_label = None
        self._time_label = None
        
        # Clean up object ID frame
        if hasattr(self, '_objid_frame') and self._objid_frame:
            self._objid_frame.clear()
            self._objid_frame = None
        
        if hasattr(self, '_objid_stack'):
            self._objid_stack = None
        
        # Clear any remaining references
        if hasattr(self, '_label_manipulators'):
            self._label_manipulators.clear()
        
        carb.log_info("[ViewOverlay] Overlay destroyed")
