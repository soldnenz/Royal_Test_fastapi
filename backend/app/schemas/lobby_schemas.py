from pydantic import BaseModel, validator
import re
from app.logging import get_logger

logger = get_logger(__name__)

class KickParticipantRequest(BaseModel):
    target_user_id: str
    
    @validator('target_user_id')
    def validate_user_id(cls, v):
        if not v or len(v) < 3:
            logger.warning(
                section="Security",
                subsection="Validation",
                message=f"Attempt to use too short user_id for kick: length {len(v) if v else 0}"
            )
            raise ValueError('Invalid user ID')
        # Prevent injection attacks
        if re.search(r'[<>"\';]', v):
            logger.error(
                section="Security",
                subsection="Injection",
                message=f"Potential SQL/XSS injection attempt in target_user_id: {v[:50]}"
            )
            raise ValueError('Invalid characters in user ID')
        return v 