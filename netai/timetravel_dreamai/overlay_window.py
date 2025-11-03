# overlay_window.py - UI for VLM Overlay Control

import omni.ui as ui
import carb


class OverlayControlWindow:
    """Overlay Control UI Window for VLM visualization."""
    
    def __init__(self, overlay):
        """Initialize the Overlay Control window.
        
        Args:
            overlay: TimeTravelViewportOverlay instance to control
        """
        self._overlay = overlay
        
        # Create window with visible position
        self._window = ui.Window(
            "Overlay Control", 
            width=250, 
            height=120,
            visible=True
        )
        
        carb.log_info(f"[OverlayControl] Window created: {self._window}")
        
        with self._window.frame:
            with ui.VStack(spacing=5, style={"margin": 8}):
                # Title
                with ui.HStack(height=25):
                    ui.Label("VLM Overlay", style={"font_size": 16, "font_weight": "bold"})
                
                # Time display toggle
                with ui.HStack(height=22):
                    self._time_checkbox = ui.CheckBox(width=18)
                    self._time_checkbox.model.set_value(self._overlay.is_visible())
                    self._time_checkbox.model.add_value_changed_fn(self._on_time_display_changed)
                    ui.Label("Show Time Display", style={"font_size": 16})
                
                # Object ID display toggle
                with ui.HStack(height=22):
                    self._objid_checkbox = ui.CheckBox(width=18)
                    self._objid_checkbox.model.set_value(True)
                    self._objid_checkbox.model.add_value_changed_fn(self._on_objid_display_changed)
                    ui.Label("Show Object IDs", style={"font_size": 16})
    
    def _on_time_display_changed(self, model):
        """Handle time display checkbox change."""
        visible = model.get_value_as_bool()
        self._overlay.set_visible(visible)
        
        if visible:
            carb.log_info("[OverlayControl] Time display enabled")
        else:
            carb.log_info("[OverlayControl] Time display disabled")
    
    def _on_objid_display_changed(self, model):
        """Handle object ID display checkbox change."""
        visible = model.get_value_as_bool()
        self._overlay.set_object_ids_visible(visible)
        
        if visible:
            carb.log_info("[OverlayControl] Object ID display enabled")
        else:
            carb.log_info("[OverlayControl] Object ID display disabled")
    
    def update_ui(self):
        """Update UI elements (called every frame if needed)."""
        # Sync checkbox with actual overlay state (in case it changed externally)
        if self._time_checkbox.model.get_value_as_bool() != self._overlay.is_visible():
            self._time_checkbox.model.set_value(self._overlay.is_visible())
    
    def destroy(self):
        """Clean up the window."""
        if self._window:
            self._window.destroy()
            self._window = None
