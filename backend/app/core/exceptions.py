class PipelineStageError(Exception):
    """Base exception for pipeline stage errors."""
    pass

class PipelineStageValidationError(PipelineStageError):
    """Raised when validation of a pipeline stage fails."""
    pass

class PipelineStageDeletionError(PipelineStageError):
    """Raised when deletion of a pipeline stage fails due to active dependency validation."""
    pass
