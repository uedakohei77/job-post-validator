from pydantic import BaseModel, Field

class VolunteerPostValidation(BaseModel):
    """Pydantic model representing the validation result of a volunteer job posting."""
    
    is_valid: bool = Field(
        description="True if the posting is logical, complete, and the reward points are reasonable based on defined rules."
    )
    extracted_duration_hours: float = Field(
        description="The calculated duration of the volunteer work in hours, extracted from start_time and end_time."
    )
    extracted_points: int = Field(
        description="The total reward points offered in the posting."
    )
    assigned_points_per_hour: float = Field(
        description="The calculated reward points per hour (extracted_points / extracted_duration_hours)."
    )
    category: str = Field(
        description="The category of work. Must be one of: 'Standard', 'High-Effort', 'Passive Storage'."
    )
    reasoning: str = Field(
        description="Detailed explanation of why the posting's points are acceptable or why they violate standard baselines/exceptions."
    )
    corrections_needed: list[str] = Field(
        default=[],
        description="A list of corrections needed if the posting is invalid. Empty list if valid."
    )
