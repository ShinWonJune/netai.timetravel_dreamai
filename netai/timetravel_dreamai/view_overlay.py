# view_overlay.py - Viewport overlay for displaying object ID labels above prims

import omni.ui.scene as sc
import omni.usd
import omni.kit.app
import carb
from pxr import UsdGeom, Gf


# -----------------------------------------------------------------
#  1. View (Manipulator) Class - Simplified
# -----------------------------------------------------------------
class ObjectIDManipulator(sc.Manipulator):
    """
    Displays an object ID label at the prim's 3D position.
    Directly reads prim position without using a model.
    """
    def __init__(self, prim_path: str, label_text: str, **kwargs):
        super().__init__(**kwargs)
        self._prim_path = prim_path
        self._label_text = label_text
        self._stage = omni.usd.get_context().get_stage()
        self._prim = self._stage.GetPrimAtPath(self._prim_path)
        self._xformable = UsdGeom.Xformable(self._prim)

    def on_build(self):
        """Build the label UI at prim's current position."""
        if not self._prim or not self._prim.IsValid():
            return

        # Get world position
        xform_cache = UsdGeom.XformCache()
        world_transform = xform_cache.GetLocalToWorldTransform(self._prim)
        translation = world_transform.ExtractTranslation()
        
        # Create label at world position (offset 100 units above)
        with sc.Transform(transform=sc.Matrix44.get_translation_matrix(
            translation[0], translation[1] + 100, translation[2]
        )):
            # Draw label text
            sc.Label(
                self._label_text,
                color=0xFF000000,  # Black text
                size=24
            )

    def on_model_updated(self, item):
        """Rebuild when prim moves."""
        self.invalidate()

# -----------------------------------------------------------------
#  2. Manager Class (Model removed - not needed)
# -----------------------------------------------------------------
class ViewOverlay:
    """
    Manages viewport overlay, creating and updating
    Models and Manipulators for multiple prims.
    """
    def __init__(self, viewport_window, ext_id):
        self._viewport_window = viewport_window
        self._ext_id = ext_id
        self._usd_context = omni.usd.get_context()
        self._scene_view = None
        self._manipulators = []  # Changed from _models to _manipulators
        self._stage_event_sub = None
        self._update_sub = None

        # Subscribe to stage events
        self._stage_event_sub = self._usd_context.get_stage_event_stream().create_subscription_to_pop(
            self._on_stage_event, name="ViewOverlayStageEvent"
        )
        
        carb.log_info("[ViewOverlay] Initialized")
        
        # If stage is already open, build UI immediately
        stage = self._usd_context.get_stage()
        if stage:
            carb.log_info("[ViewOverlay] Stage already open, building UI now...")
            self._build_scene_for_stage()
        else:
            carb.log_info("[ViewOverlay] No stage yet, waiting for OPENED event...")

    def shutdown(self):
        """Clean up all resources."""
        carb.log_info("[ViewOverlay] Shutting down...")
        
        self._stage_event_sub = None
        self._update_sub = None
        
        if self._scene_view:
            self._viewport_window.viewport_api.remove_scene_view(self._scene_view)
        
        self._scene_view = None
        self._manipulators = []
        
        carb.log_info("[ViewOverlay] Cleanup complete")

    def _on_stage_event(self, event):
        """Handle stage open/close events."""
        if event.type == int(omni.usd.StageEventType.OPENED):
            carb.log_info("[ViewOverlay] Stage opened. Building UI...")
            self._build_scene_for_stage()
        elif event.type == int(omni.usd.StageEventType.CLOSED):
            carb.log_info("[ViewOverlay] Stage closed. Cleaning up UI...")
            self._cleanup_scene()

    def _get_id_from_name(self, prim_name: str) -> str:
        """
        Extract ID from prim name's last 3 digits.
        Example: 'Astronaut001' -> '1'
        """
        if len(prim_name) < 3:
            return None
        
        last_three = prim_name[-3:]
        if not last_three.isdigit():
            return None
        
        # Convert to int to remove leading zeros, then back to string
        return str(int(last_three))

    def _cleanup_scene(self):
        """Clean up UI when stage is closed."""
        # Stop update subscription
        self._update_sub = None
        
        # Clear manipulators
        self._manipulators = []
        
        # Remove and clear scene view
        if self._scene_view:
            self._viewport_window.viewport_api.remove_scene_view(self._scene_view)
            self._scene_view = None
        
        carb.log_info("[ViewOverlay] Scene view cleaned up")

    def _build_scene_for_stage(self):
        """
        Build all Models and Manipulators when stage is ready.
        Creates labels for all prims under /World/TimeTravel_Objects.
        """
        if self._scene_view:
            carb.log_info("[ViewOverlay] Scene view already exists. Cleaning up...")
            self._cleanup_scene()

        stage = self._usd_context.get_stage()
        if not stage:
            carb.log_error("[ViewOverlay] Cannot get stage")
            return

        parent_prim_path = "/World/TimeTravel_Objects"
        parent_prim = stage.GetPrimAtPath(parent_prim_path)
        
        if not parent_prim.IsValid():
            carb.log_warn(f"[ViewOverlay] '{parent_prim_path}' prim not found")
            return

        # Create scene view
        with self._viewport_window.get_frame(self._ext_id):
            self._scene_view = sc.SceneView()
            
            with self._scene_view.scene:
                # Create manipulator for each child prim
                for prim in parent_prim.GetChildren():
                    prim_name = prim.GetName()
                    label_id = self._get_id_from_name(prim_name)

                    if not label_id:
                        carb.log_info(f"[ViewOverlay] Cannot extract ID from '{prim_name}', skipping")
                        continue

                    prim_path = str(prim.GetPath())
                    
                    carb.log_info(f"[ViewOverlay] Tracking '{prim_path}' (ID: {label_id})")
                    
                    # Create manipulator (reads prim position directly)
                    manipulator = ObjectIDManipulator(prim_path=prim_path, label_text=label_id)
                    self._manipulators.append(manipulator)

            # Add scene view to viewport
            self._viewport_window.viewport_api.add_scene_view(self._scene_view)

        # Subscribe to frame updates
        if not self._update_sub:
            self._update_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
                self._on_update, name="ViewOverlayFrameUpdate"
            )

    def _on_update(self, e):
        """Called every frame to update all manipulators."""
        if not self._manipulators:
            return
        
        # Invalidate all manipulators to force rebuild with new positions
        for manipulator in self._manipulators:
            manipulator.invalidate()
