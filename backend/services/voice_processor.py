# ============================================
# VOICE INPUT PROCESSOR - NLP Command Parsing
# Converts natural language to device control actions
# ============================================

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class VoiceCommandProcessor:
    """
    Intelligent voice command processor that converts natural language
    to structured device control actions.
    
    Supported Devices: AC, Fan, Light, Refrigerator, TV
    Supported Actions: ON, OFF, STATUS, UNKNOWN
    """
    
    # Device mappings with aliases
    DEVICE_ALIASES = {
        "ac": ["air conditioner", "ac", "cooling", "cooler", "ac unit"],
        "fan": ["fan", "ceiling fan", "oscillating fan", "blower"],
        "light": ["light", "lights", "lamp", "bulb", "lighting", "brightness"],
        "tv": ["tv", "television", "screen", "display", "netflix", "youtube"],
        "refrigerator": ["fridge", "refrigerator", "fridge", "cooler", "cold storage"],
    }
    
    # Action keywords
    ACTION_ON_KEYWORDS = [
        "turn on", "switch on", "start", "power on", "activate", 
        "enable", "open", "brighter", "brightness", "cool", "air",
        "on", "please on", "i want", "make", "set"
    ]
    
    ACTION_OFF_KEYWORDS = [
        "turn off", "switch off", "stop", "power off", "deactivate",
        "disable", "close", "darken", "darker", "off", "please off",
        "shut", "shut down"
    ]
    
    ACTION_STATUS_KEYWORDS = [
        "status", "is on", "is off", "is running", "currently", 
        "what", "how", "check", "tell me", "showing"
    ]
    
    def __init__(self):
        """Initialize the voice command processor."""
        self.confidence_threshold = 0.6
        
    def process_command(self, voice_input: str) -> Dict:
        """
        Process voice input and return structured device control action.
        
        Args:
            voice_input (str): Raw voice/text command
            
        Returns:
            Dict: {"device": str, "action": str, "confidence": float, "parsed_command": str}
        """
        if not voice_input or not isinstance(voice_input, str):
            return self._unknown_response("Invalid input format")
        
        # Clean and normalize input
        normalized_input = self._normalize_input(voice_input)
        
        # Extract device
        device, device_confidence = self._extract_device(normalized_input)
        
        # Extract action
        action, action_confidence = self._extract_action(normalized_input)
        
        # Calculate overall confidence
        overall_confidence = (device_confidence + action_confidence) / 2
        
        # Handle special cases
        if device == "ALL":
            return self._handle_all_devices(action, overall_confidence, normalized_input)
        
        if device == "UNKNOWN" or overall_confidence < self.confidence_threshold:
            return self._handle_unclear_command(normalized_input, device, action)
        
        return {
            "device": device,
            "action": action,
            "confidence": round(overall_confidence, 2),
            "parsed_command": normalized_input,
            "status": "success"
        }
    
    def _normalize_input(self, text: str) -> str:
        """
        Normalize voice input by removing extra spaces and lowercasing.
        
        Args:
            text (str): Raw input text
            
        Returns:
            str: Normalized text
        """
        # Remove extra spaces
        text = " ".join(text.split())
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r'[.,!?;:]', '', text)
        return text
    
    def _extract_device(self, normalized_input: str) -> Tuple[str, float]:
        """
        Extract device name from command.
        
        Args:
            normalized_input (str): Normalized command
            
        Returns:
            Tuple: (device_name, confidence_score)
        """
        # Check for "everything" or "all"
        if re.search(r'\b(everything|all|every device)\b', normalized_input):
            return "ALL", 0.95
        
        # Check each device - use word boundaries for proper matching
        for device, aliases in self.DEVICE_ALIASES.items():
            for alias in aliases:
                # Use word boundary regex to avoid partial matches (e.g., "ac" in "activate")
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, normalized_input):
                    confidence = 0.9 if normalized_input.count(alias) > 0 else 0.8
                    return device.upper(), confidence
        
        return "UNKNOWN", 0.0
    
    def _extract_action(self, normalized_input: str) -> Tuple[str, float]:
        """
        Extract action from command.
        
        Args:
            normalized_input (str): Normalized command
            
        Returns:
            Tuple: (action, confidence_score)
        """
        # Helper function to check for keyword with word boundary
        def has_keyword(text: str, keywords: list) -> bool:
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text):
                    return True
            return False
        
        # Check for OFF action
        for keyword in self.ACTION_OFF_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, normalized_input):
                return "OFF", 0.9
        
        # Check for STATUS action
        for keyword in self.ACTION_STATUS_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, normalized_input):
                # Verify it's asking for status, not commanding
                if not (has_keyword(normalized_input, self.ACTION_ON_KEYWORDS) or 
                        has_keyword(normalized_input, self.ACTION_OFF_KEYWORDS)):
                    return "STATUS", 0.85
        
        # Check for ON action (default if unclear)
        for keyword in self.ACTION_ON_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, normalized_input):
                return "ON", 0.9
        
        # Contextual inference
        if "too hot" in normalized_input or "cool air" in normalized_input or "too warm" in normalized_input:
            return "ON", 0.85
        
        if "hurting my eyes" in normalized_input or "too bright" in normalized_input:
            return "OFF", 0.85
        
        return "UNKNOWN", 0.5
    
    def _handle_all_devices(self, action: str, confidence: float, command: str) -> Dict:
        """Handle 'ALL' device commands."""
        return {
            "device": "ALL",
            "action": action if action != "UNKNOWN" else "STATUS",
            "confidence": round(confidence, 2),
            "parsed_command": command,
            "status": "success"
        }
    
    def _handle_unclear_command(self, command: str, device: str, action: str) -> Dict:
        """Handle unclear or low-confidence commands."""
        clarification_msg = ""
        
        if device == "UNKNOWN":
            clarification_msg = "I couldn't identify the device. Did you mean: AC, Fan, Light, TV, or Refrigerator?"
        elif action == "UNKNOWN":
            clarification_msg = f"I found the {device}, but I'm not sure what you want. Do you want to turn it ON, OFF, or check STATUS?"
        
        return {
            "device": device if device != "UNKNOWN" else None,
            "action": "UNKNOWN",
            "confidence": 0.0,
            "parsed_command": command,
            "status": "clarification_needed",
            "message": clarification_msg
        }
    
    def _unknown_response(self, reason: str = "Unable to process command") -> Dict:
        """Generate unknown response."""
        return {
            "device": None,
            "action": "UNKNOWN",
            "confidence": 0.0,
            "status": "error",
            "message": reason
        }
    
    def process_batch_commands(self, commands: List[str]) -> List[Dict]:
        """
        Process multiple commands in batch.
        
        Args:
            commands (List[str]): List of voice commands
            
        Returns:
            List[Dict]: List of processed commands
        """
        return [self.process_command(cmd) for cmd in commands]


class VoiceIntegrationService:
    """Service to integrate voice commands with device control."""
    
    def __init__(self, device_controller=None):
        """
        Initialize voice integration service.
        
        Args:
            device_controller: Reference to device control service
        """
        self.processor = VoiceCommandProcessor()
        self.device_controller = device_controller
        self.command_history: List[Dict] = []
    
    def execute_voice_command(self, voice_input: str, user_id: Optional[str] = None) -> Dict:
        """
        Process voice command and execute device action.
        
        Args:
            voice_input (str): Raw voice command
            user_id (str, optional): User identifier for logging
            
        Returns:
            Dict: Execution result with device action
        """
        # Parse command
        parsed = self.processor.process_command(voice_input)
        
        # Log command
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "input": voice_input,
            "parsed": parsed,
            "user_id": user_id
        }
        self.command_history.append(log_entry)
        
        # If clarification needed, return message
        if parsed["status"] in ["error", "clarification_needed"]:
            return {
                "success": False,
                "device": parsed.get("device"),
                "action": parsed.get("action"),
                "message": parsed.get("message", "Unable to process command"),
                "confidence": parsed.get("confidence", 0.0)
            }
        
        # Execute device action if controller available
        if self.device_controller and parsed["device"]:
            execution_result = self.device_controller.control_device(
                device_name=parsed["device"],
                action=parsed["action"]
            )
            return {
                "success": execution_result.get("success", False),
                "device": parsed["device"],
                "action": parsed["action"],
                "message": f"{parsed['device']} {parsed['action']} command executed",
                "confidence": parsed["confidence"],
                "result": execution_result
            }
        
        return {
            "success": True,
            "device": parsed["device"],
            "action": parsed["action"],
            "message": f"Parsed: {parsed['device']} - {parsed['action']}",
            "confidence": parsed["confidence"]
        }
    
    def get_command_history(self, limit: int = 50) -> List[Dict]:
        """Get recent command history."""
        return self.command_history[-limit:]
    
    def clear_history(self):
        """Clear command history."""
        self.command_history = []


# Initialize processor
voice_processor = VoiceCommandProcessor()
