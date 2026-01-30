"""Base class for evaluation results."""

from typing import Optional


class EvalResult:
    """Base class for evaluation results."""
    
    def __init__(self, reason: str, suggestion: Optional[str] = None):
        """Initialize the evaluation result.
        
        Args:
            reason: The reason for the evaluation decision
            suggestion: Optional suggestion for alternative tactics
        """
        self.reason = reason
        self.suggestion = suggestion
    
    def is_good(self) -> bool:
        """Check if the evaluation result is good/successful.
        
        This method should be overridden by subclasses.
        
        Returns:
            True if the evaluation is positive, False otherwise
        """
        raise NotImplementedError("Subclasses must implement is_good()")
    
    def get_suggestion(self) -> Optional[str]:
        """Get the suggestion or empty string if none.
        
        Returns:
            The suggestion text or empty string
        """
        return self.suggestion
    
    def __repr__(self):
        """Default representation - should be overridden by subclasses."""
        return f"{self.__class__.__name__}(reason={self.reason}, suggestion={self.suggestion})"

