# core.py - Core logic for Time Travel functionality

import json
import csv
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import omni.usd
from pxr import Usd, UsdGeom, Gf
import carb


class TimeTravelCore:
    """Core logic for Time Travel Extension."""
    
    def __init__(self):
        self._config = {}
        self._data = {}  # {timestamp_str: {objid: (x, y, z)}}
        self._timestamps = []  # Sorted list of timestamps
        self._prim_map = {}  # {objid: prim_path}
        self._event_summary = []  # List of important event timestamps
        
        self._start_time = None
        self._end_time = None
        self._current_time = None
        self._current_event_index = 0
        
        self._is_playing = False
        self._playback_speed = 1.0
        self._accumulated_time = 0.0
        self._use_event_summary = False
        
        self._usd_context = omni.usd.get_context()
        self._stage = None
        
    def load_config(self, config_path: str) -> bool:
        """Load configuration from JSON file."""
        try:
            path = Path(config_path)
            if not path.exists():
                carb.log_warn(f"[TimeTravel] Config file not found: {config_path}")
                return False
            
            with open(path, 'r') as f:
                self._config = json.load(f)
            
            # Store config directory for relative paths
            self._config_dir = path.parent
            
            # Extract prim mapping (will be overridden if auto_generate is enabled)
            self._prim_map = self._config.get('prim_map', {})
            
            # Extract event summary
            self._event_summary = self._config.get('event_summary', [])
            
            carb.log_info(f"[TimeTravel] Config loaded")
            return True
            
        except Exception as e:
            carb.log_error(f"[TimeTravel] Failed to load config: {e}")
            return False
    
    def load_data(self) -> bool:
        """Load trajectory data from CSV file."""
        try:
            data_path = self._config.get('data_path', './data/merged_trajectory.csv')
            
            # Convert to absolute path based on current file location
            if not Path(data_path).is_absolute():
                current_file_dir = Path(__file__).parent
                path = current_file_dir / data_path.lstrip('./')
            else:
                path = Path(data_path)
            
            carb.log_info(f"[TimeTravel] Looking for data file at: {path}")
            
            if not path.exists():
                carb.log_error(f"[TimeTravel] Data file not found: {path}")
                return False
            
            # Load CSV data into memory
            with open(path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    timestamp = row['timestamp']
                    objid = row['objid']
                    x = float(row['x'])
                    y = float(row['y'])
                    z = float(row['z'])
                    
                    if timestamp not in self._data:
                        self._data[timestamp] = {}
                    
                    self._data[timestamp][objid] = (x, y, z)
            
            # Sort timestamps for efficient searching
            # timestamps는 정렬되어있다고 가정
            # self._timestamps = sorted(self._data.keys()) #sorted 는 list를 반환
            self._timestamps = list(self._data.keys()) # dict_keys 객체 - 인덱싱 불가능. key를 list로 변환만
            
            if self._timestamps:
                self._start_time = self._parse_timestamp(self._timestamps[0])
                print(self._start_time)
                self._end_time = self._parse_timestamp(self._timestamps[-1])
                print(self._end_time)
                self._current_time = self._start_time
            
            carb.log_info(f"[TimeTravel] Data loaded: {len(self._timestamps)} timestamps, {self._start_time} to {self._end_time}")
            return True
            
        except Exception as e:
            carb.log_error(f"[TimeTravel] Failed to load data: {e}")
            return False
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime.datetime:
        """Parse timestamp string to datetime object. Manages timestamp formats."""
        try:
            # "2025-01-01T00:00:00Z" -> "2025-01-01T00:00:00+00:00" -> Datetime 객체
            return datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            # CSV format: "2025-01-01 00:00:00.000"
            return datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
    
    def _format_timestamp(self, dt: datetime.datetime) -> str:
        """Format datetime to timestamp string matching data format."""
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    def set_time_range(self, start_time: datetime.datetime, end_time: datetime.datetime) -> bool:
        """Set user-defined time range with validation."""
        # Validate that end time is after start time
        if end_time <= start_time:
            carb.log_error("[TimeTravel] End time must be after start time")
            return False
        
        # Clamp to data range
        if self._start_time and self._end_time:
            # Auto-adjust to data boundaries
            adjusted_start = max(start_time, self._start_time)
            adjusted_end = min(end_time, self._end_time)

            # Log if adjustment was made
            if adjusted_start != start_time:
                carb.log_info(f"[TimeTravel] Start time adjusted to data minimum: {adjusted_start}")
            if adjusted_end != end_time:
                carb.log_info(f"[TimeTravel] End time adjusted to data maximum: {adjusted_end}")
            
            self._start_time = adjusted_start
            self._end_time = adjusted_end
            
            # Ensure current time is within new range
            if self._current_time:
                if self._current_time < self._start_time:
                    self._current_time = self._start_time
                    self.update_stage_objects()
                elif self._current_time > self._end_time:
                    self._current_time = self._end_time
                    self.update_stage_objects()
            
            carb.log_info(f"[TimeTravel] Time range set: {self._start_time} to {self._end_time}")
            return True
        
        return False
    
    def get_data_start_time(self) -> datetime.datetime:
        """Get original data start time."""
        return self._start_time or datetime.datetime.now()
    
    def get_data_end_time(self) -> datetime.datetime:
        """Get original data end time."""
        return self._end_time or datetime.datetime.now()
    
    def get_data_at_time(self, timestamp: datetime.datetime) -> Dict:
        """
        Get object positions at specific timestamp (API for future AI integration).
        Removed microseconds for matching.
        Adjust matching second unit as needed.
        """
        # Normalize to milliseconds (remove microseconds beyond milliseconds)
        # .123456 → .123000 (마이크로초 부분 제거)
        normalized_time = timestamp.replace(microsecond=(timestamp.microsecond // 1000) * 1000)
        timestamp_str = self._format_timestamp(normalized_time)
        
        # Check if exact timestamp exists
        if timestamp_str in self._data:
            return self._data[timestamp_str]
        
        # Apply LKV (Last Known Value) logic
        return self._get_lkv_data(timestamp_str)
    
    def _get_lkv_data(self, timestamp_str: str) -> Dict:
        """Get last known value for given timestamp."""
        if not self._timestamps:
            return {}
        
        # Find the closest previous timestamp
        prev_timestamp = None
        for ts in self._timestamps:
            if ts <= timestamp_str:
                prev_timestamp = ts
            else:
                break
        
        if prev_timestamp:
            return self._data[prev_timestamp]
        
        # If no previous data, return first available data
        return self._data[self._timestamps[0]] if self._timestamps else {}
    
    def update_stage_objects(self):
        """Update USD stage objects based on current time."""
        self._stage = self._usd_context.get_stage()
        if not self._stage:
            return
        
        # Get data for current time
        data = self.get_data_at_time(self._current_time)
        
        if not data:
            return
        
        # Update each mapped object
        for objid, prim_path in self._prim_map.items():
            if objid not in data:
                continue
            
            try:
                prim = self._stage.GetPrimAtPath(prim_path)
                if not prim or not prim.IsValid():
                    continue
                
                # Get position from data
                x, y, z = data[objid]
                
                # Update translate
                xformable = UsdGeom.Xformable(prim)
                if xformable:
                    translate_op = None
                    for op in xformable.GetOrderedXformOps():
                        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                            translate_op = op
                            break
                    
                    if not translate_op:
                        translate_op = xformable.AddTranslateOp()
                    
                    translate_op.Set(Gf.Vec3d(x, y, z))
                    
            except Exception as e:
                carb.log_error(f"[TimeTravel] Failed to update {objid}: {e}")
    
    def set_to_earliest_time(self):
        """Set stage to earliest timestamp."""
        if self._start_time:
            self._current_time = self._start_time
            self.update_stage_objects()
    
    def set_current_time(self, dt: datetime.datetime):
        """Set current time and update stage."""
        if self._start_time and self._end_time:
            # Clamp to valid range
            self._current_time = max(self._start_time, min(dt, self._end_time))
            self.update_stage_objects()
    
    def get_progress(self) -> float:
        """Get current progress as 0-1 value."""
        if not self._start_time or not self._end_time:
            return 0.0
        
        total_duration = (self._end_time - self._start_time).total_seconds()
        if total_duration <= 0:
            return 0.0
        
        current_duration = (self._current_time - self._start_time).total_seconds()
        return min(1.0, max(0.0, current_duration / total_duration))
    
    def set_progress(self, progress: float):
        """Set progress (0-1) and update current time."""
        if not self._start_time or not self._end_time:
            return
        
        progress = min(1.0, max(0.0, progress))
        total_duration = (self._end_time - self._start_time).total_seconds()
        seconds_offset = total_duration * progress
        
        self._current_time = self._start_time + datetime.timedelta(seconds=seconds_offset)
        self.update_stage_objects()
    
    def toggle_playback(self):
        """Toggle play/pause state."""
        self._is_playing = not self._is_playing
        self._accumulated_time = 0.0
    
    def update(self, dt: float):
        """ 
        재생시 0.1초 단위로 화면을 업데이트. 추후에 변화가 감지 기반 업데이트 로직으로 변경 가능
        - 0.1초 단위로 업데이트하는 이유는 너무 자주 업데이트하면 성능에 부담이 될 수 있기 때문.
        - 변화 감지 기반 업데이트의 장점은 더 자연스러운 움직임.
        """
        if not self._is_playing or not self._current_time:
            return
        
        self._accumulated_time += dt * self._playback_speed
        
        # Update every 0.1 second (or when accumulated time >= 0.1 second)
        if self._accumulated_time >= 0.1:
            seconds_to_add = self._accumulated_time
            self._accumulated_time = 0.0  # Reset accumulated time
            
            if self._use_event_summary and self._event_summary:
                # Jump to next event
                self._go_to_next_event()
            else:
                # Normal playback
                new_time = self._current_time + datetime.timedelta(seconds=seconds_to_add)
                
                if new_time >= self._end_time:
                    new_time = self._end_time
                    self._is_playing = False
                
                self._current_time = new_time
                self.update_stage_objects()
    
    def _go_to_next_event(self):
        """Jump to next event in summary."""
        if not self._event_summary:
            return
        
        self._current_event_index = (self._current_event_index + 1) % len(self._event_summary)
        event_timestamp = self._event_summary[self._current_event_index]
        
        try:
            event_time = self._parse_timestamp(event_timestamp)
            self.set_current_time(event_time)
        except Exception as e:
            carb.log_error(f"[TimeTravel] Failed to parse event timestamp: {event_timestamp}")
    
    def go_to_next_event(self):
        """Manually jump to next event (for Go button)."""
        if self._event_summary:
            self._go_to_next_event()
    
    # Getter methods for UI
    def get_start_time(self) -> datetime.datetime:
        return self._start_time or datetime.datetime.now()
    
    def get_end_time(self) -> datetime.datetime:
        return self._end_time or datetime.datetime.now()
    
    def get_current_time(self) -> datetime.datetime:
        return self._current_time or datetime.datetime.now()
    
    def get_stage_time_string(self) -> str:
        """Get formatted stage time string with milliseconds."""
        if self._current_time:
            return self._current_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return "No time set"
    
    def is_playing(self) -> bool:
        return self._is_playing
    
    def get_playback_speed(self) -> float:
        return self._playback_speed
    
    def set_playback_speed(self, speed: float):
        self._playback_speed = max(0.1, speed)
    
    def has_data(self) -> bool:
        return len(self._timestamps) > 0
    
    def has_events(self) -> bool:
        return len(self._event_summary) > 0
    
    def set_use_event_summary(self, use: bool):
        self._use_event_summary = use
        self._current_event_index = 0
    
    def get_summary_events(self) -> List[str]:
        """Get list of event timestamps (API for future AI integration)."""
        return self._event_summary.copy()
    
    def parse_unique_objids(self, csv_path: str) -> List[str]:
        """Extract unique objids from CSV."""
        objids = set()
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'objid' in row:
                        objids.add(row['objid'])
            return sorted(list(objids))
        except Exception as e:
            carb.log_error(f"[TimeTravel] Failed to parse objids: {e}")
            return []
    
    def clear_timetravel_objects(self):
        """Clear existing TimeTravel_Objects."""
        if not self._stage:
            self._stage = self._usd_context.get_stage()
        
        parent_path = "/World/TimeTravel_Objects"
        parent_prim = self._stage.GetPrimAtPath(parent_path)
        
        if parent_prim and parent_prim.IsValid():
            for child in parent_prim.GetChildren():
                self._stage.RemovePrim(child.GetPath())
    
    def create_astronaut_prim(self, index: int) -> str:
        """Create Astronaut prim with Reference."""
        if not self._stage:
            self._stage = self._usd_context.get_stage()
        
        # Get astronaut USD path from config
        astronaut_usd = self._config.get('astronaut_usd', '')
        if not astronaut_usd:
            carb.log_error("[TimeTravel] astronaut_usd not specified in config")
            return ""
        
        # Ensure parent exists
        parent_path = "/World/TimeTravel_Objects"
        if not self._stage.GetPrimAtPath(parent_path):
            self._stage.DefinePrim(parent_path, "Xform")
        
        # Create astronaut prim
        prim_path = f"{parent_path}/Astronaut{index:03d}"
        prim = self._stage.DefinePrim(prim_path, "Xform")
        
        # Add reference
        from pxr import Sdf, UsdGeom
        references = prim.GetReferences()
        references.AddReference(
            assetPath=astronaut_usd,
            primPath=Sdf.Path("/Root")
        )
        
        # Setup transform ops: translate -> rotate -> scale
        xformable = UsdGeom.Xformable(prim)
        
        # 1. Translate first
        translate_op = xformable.AddTranslateOp()
        translate_op.Set(Gf.Vec3d(0, 0, 0))
        
        # 2. Rotate second
        rotate_xyz_op = xformable.AddRotateXYZOp()
        rotate_xyz_op.Set(Gf.Vec3f(-90.0, 0.0, 0.0))
        
        # 3. Scale third
        scale_op = xformable.AddScaleOp()
        scale_op.Set(Gf.Vec3f(1.0, 1.0, 1.0))
        
        return prim_path
    
    def auto_generate_astronauts(self) -> Dict[str, str]:
        """Auto-generate Astronaut prims and create mapping."""
        # Get CSV path
        data_path = self._config.get('data_path', '')
        if not Path(data_path).is_absolute():
            csv_path = self._config_dir / data_path.lstrip('./')
        else:
            csv_path = Path(data_path)
        
        if not csv_path.exists():
            carb.log_error(f"[TimeTravel] Data file not found: {csv_path}")
            return {}
        
        # Parse objids
        objids = self.parse_unique_objids(str(csv_path))
        if not objids:
            carb.log_error("[TimeTravel] No objids found in CSV")
            return {}
        
        carb.log_info(f"[TimeTravel] Auto-generating {len(objids)} Astronauts")
        
        # Clear existing
        self.clear_timetravel_objects()
        
        # Create astronauts and mapping
        prim_map = {}
        for i, objid in enumerate(objids, start=1):
            prim_path = self.create_astronaut_prim(i)
            if prim_path:
                prim_map[objid] = prim_path
                carb.log_info(f"  {objid} -> {prim_path}")
        
        carb.log_info(f"[TimeTravel] Created {len(prim_map)} Astronauts")
        
        # Hide all cameras in the stage
        self.hide_all_cameras()
        
        return prim_map
    
    def hide_all_cameras(self):
        """Hide all camera prims in the stage."""
        if not self._stage:
            self._stage = self._usd_context.get_stage()
        
        if not self._stage:
            return
        
        camera_count = 0
        for prim in self._stage.Traverse():
            if prim.IsA(UsdGeom.Camera):
                imageable = UsdGeom.Imageable(prim)
                imageable.MakeInvisible()
                camera_count += 1
        
        if camera_count > 0:
            carb.log_info(f"[TimeTravel] Hidden {camera_count} cameras")