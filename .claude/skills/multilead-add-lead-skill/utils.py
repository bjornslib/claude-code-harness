#!/usr/bin/env python3
"""
Multilead API Utilities

Utility functions for validating inputs, formatting requests, and handling responses
from the Multilead Open API.
"""

import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class LinkedInURLValidator:
    """Validates LinkedIn profile URLs."""
    
    LINKEDIN_PATTERNS = [
        r'^https?://(?:www\.)?linkedin\.com/in/[a-z0-9\-]+/?$',  # Standard profile
        r'^https?://(?:www\.)?linkedin\.com/sales/people/[A-Za-z0-9]+/?$',  # Sales Nav
    ]
    
    @classmethod
    def is_valid(cls, url: str) -> bool:
        """Check if URL matches LinkedIn profile format."""
        if not url:
            return False
        
        url_lower = url.lower().strip()
        return any(re.match(pattern, url_lower) for pattern in cls.LINKEDIN_PATTERNS)
    
    @classmethod
    def validate(cls, url: str) -> str:
        """
        Validate LinkedIn URL and return normalized version.
        
        Raises:
            ValidationError: If URL is invalid
        """
        if not cls.is_valid(url):
            raise ValidationError(
                f"Invalid LinkedIn profile URL: {url}\n"
                "Expected format: https://linkedin.com/in/[username] or "
                "https://linkedin.com/sales/people/[id]"
            )
        return url.strip()


class EmailValidator:
    """Validates email addresses."""
    
    PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    @classmethod
    def is_valid(cls, email: str) -> bool:
        """Check if email matches basic format."""
        if not email:
            return False
        return bool(re.match(cls.PATTERN, email.strip()))
    
    @classmethod
    def validate(cls, email: str) -> str:
        """
        Validate email and return normalized version.
        
        Raises:
            ValidationError: If email is invalid
        """
        if not cls.is_valid(email):
            raise ValidationError(f"Invalid email address: {email}")
        return email.strip().lower()


class LeadValidator:
    """Validates lead data before sending to API."""
    
    @staticmethod
    def validate_campaign_id(campaign_id: Any) -> int:
        """
        Validate campaign ID.
        
        Args:
            campaign_id: Campaign ID to validate
        
        Returns:
            campaign_id as integer
        
        Raises:
            ValidationError: If invalid
        """
        try:
            cid = int(campaign_id)
            if cid <= 0:
                raise ValidationError("Campaign ID must be a positive integer")
            return cid
        except (TypeError, ValueError):
            raise ValidationError(f"Invalid campaign ID: {campaign_id}")
    
    @staticmethod
    def validate_lead_identification(
        profile_url: Optional[str] = None,
        email: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate that at least one identification method is provided and valid.
        
        Args:
            profile_url: LinkedIn profile URL
            email: Email address
        
        Returns:
            Tuple of (validated_profile_url, validated_email)
        
        Raises:
            ValidationError: If neither or both are invalid
        """
        validated_url = None
        validated_email = None
        
        if profile_url:
            try:
                validated_url = LinkedInURLValidator.validate(profile_url)
            except ValidationError:
                raise
        
        if email:
            try:
                validated_email = EmailValidator.validate(email)
            except ValidationError:
                raise
        
        if not validated_url and not validated_email:
            raise ValidationError(
                "At least one of profileUrl or email is required"
            )
        
        return validated_url, validated_email
    
    @staticmethod
    def validate_phone(phone: Optional[str]) -> Optional[str]:
        """
        Validate phone number (basic validation).
        
        Returns:
            Phone number or None
        """
        if not phone:
            return None
        
        # Remove common formatting
        cleaned = re.sub(r'[\s\-\(\)\.]+', '', phone)
        
        # Check if it contains mostly digits
        if not re.match(r'^\+?[0-9]{7,15}$', cleaned):
            raise ValidationError(f"Invalid phone number format: {phone}")
        
        return phone.strip()
    
    @staticmethod
    def validate_name(name: Optional[str], field_name: str = "Name") -> Optional[str]:
        """
        Validate name field (allow letters, spaces, hyphens, apostrophes).
        
        Returns:
            Name or None
        """
        if not name:
            return None
        
        name = name.strip()
        
        if not re.match(r"^[a-zA-Z\s\-']+$", name):
            raise ValidationError(f"{field_name} contains invalid characters: {name}")
        
        if len(name) > 100:
            raise ValidationError(f"{field_name} exceeds maximum length (100 chars)")
        
        return name
    
    @staticmethod
    def validate_occupation(occupation: Optional[str]) -> Optional[str]:
        """
        Validate occupation/job title.
        
        Returns:
            Occupation or None
        """
        if not occupation:
            return None
        
        occupation = occupation.strip()
        
        if len(occupation) > 200:
            raise ValidationError("Occupation exceeds maximum length (200 chars)")
        
        return occupation


class PersonalisationMessageValidator:
    """Validates personalised message fields."""
    
    @staticmethod
    def validate_message(
        message: Any
    ) -> Optional[str]:
        """
        Validate personalised message.
        
        Accepts:
        - String: single message
        - List: will be joined with commas
        - None/Empty: returns None
        
        Args:
            message: Message to validate
        
        Returns:
            Validated message string or None
        
        Raises:
            ValidationError: If message is too long or invalid
        """
        if not message:
            return None
        
        # Handle list/array
        if isinstance(message, (list, tuple)):
            message = ', '.join(str(m) for m in message if m)
        else:
            message = str(message).strip()
        
        if not message:
            return None
        
        # Max length check
        max_length = 5000  # Reasonable limit for message
        if len(message) > max_length:
            raise ValidationError(
                f"Personalised message exceeds maximum length ({max_length} chars)"
            )
        
        return message


class LeadData:
    """Represents validated lead data ready for API submission."""
    
    def __init__(
        self,
        campaign_id: int,
        profile_url: Optional[str] = None,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        occupation: Optional[str] = None,
        phone: Optional[str] = None,
        personalised_message: Optional[str] = None,
        remove_db_duplicates: Optional[bool] = None,
        custom_fields: Optional[Dict[str, str]] = None
    ):
        """
        Initialize and validate lead data.
        
        Raises:
            ValidationError: If any field is invalid
        """
        # Validate core fields
        self.campaign_id = LeadValidator.validate_campaign_id(campaign_id)
        
        self.profile_url, self.email = LeadValidator.validate_lead_identification(
            profile_url, email
        )
        
        self.first_name = LeadValidator.validate_name(first_name, "First name")
        self.last_name = LeadValidator.validate_name(last_name, "Last name")
        self.occupation = LeadValidator.validate_occupation(occupation)
        self.phone = LeadValidator.validate_phone(phone)
        self.personalised_message = PersonalisationMessageValidator.validate_message(
            personalised_message
        )
        self.remove_db_duplicates = remove_db_duplicates
        self.custom_fields = custom_fields or {}
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API request payload."""
        payload = {}
        
        # Add fields only if they have values
        if self.profile_url:
            payload['profileUrl'] = self.profile_url
        if self.email:
            payload['email'] = self.email
        if self.first_name:
            payload['firstName'] = self.first_name
        if self.last_name:
            payload['lastName'] = self.last_name
        if self.occupation:
            payload['occupation'] = self.occupation
        if self.phone:
            payload['phone'] = self.phone
        if self.personalised_message:
            payload['personalizedField'] = self.personalised_message
        
        # Add remove duplicates flag
        if self.remove_db_duplicates is not None:
            payload['removeDbDuplicates'] = 'true' if self.remove_db_duplicates else 'false'
        
        # Add custom fields
        payload.update(self.custom_fields)
        
        return payload
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'campaign_id': self.campaign_id,
            'profile_url': self.profile_url,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'occupation': self.occupation,
            'phone': self.phone,
            'personalised_message': self.personalised_message,
            'remove_db_duplicates': self.remove_db_duplicates,
            'custom_fields': self.custom_fields
        }
    
    def __repr__(self) -> str:
        identity = self.email or self.profile_url or 'Unknown'
        return f"<LeadData: {identity} (campaign {self.campaign_id})>"


def validate_batch_leads(leads_data: List[Dict[str, Any]]) -> List[LeadData]:
    """
    Validate a batch of leads.
    
    Args:
        leads_data: List of lead dictionaries
    
    Returns:
        List of validated LeadData objects
    
    Raises:
        ValidationError: If any lead is invalid (with index information)
    """
    validated = []
    
    for i, lead in enumerate(leads_data):
        try:
            validated_lead = LeadData(
                campaign_id=lead.get('campaign_id'),
                profile_url=lead.get('profile_url'),
                email=lead.get('email'),
                first_name=lead.get('first_name'),
                last_name=lead.get('last_name'),
                occupation=lead.get('occupation'),
                phone=lead.get('phone'),
                personalised_message=lead.get('personalised_message'),
                remove_db_duplicates=lead.get('remove_db_duplicates'),
                custom_fields=lead.get('custom_fields')
            )
            validated.append(validated_lead)
        except ValidationError as e:
            raise ValidationError(f"Lead #{i + 1}: {str(e)}")
    
    return validated


def format_api_response(
    success: bool,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    status_code: int = 200
) -> Dict[str, Any]:
    """
    Format API response in standard format.
    
    Args:
        success: Whether operation was successful
        data: Response data
        error: Error message if failed
        status_code: HTTP status code
    
    Returns:
        Formatted response dictionary
    """
    return {
        'success': success,
        'data': data or {},
        'error': error,
        'status_code': status_code,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
