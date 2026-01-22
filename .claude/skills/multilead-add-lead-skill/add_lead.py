#!/usr/bin/env python3
"""
Multilead Add Lead to Campaign Script

Add single or multiple leads to a Multilead campaign with personalised messages.
Supports custom fields and duplicate detection.

Usage:
    python add_lead.py --campaign-id 108 --email john@example.com --first-name John
    python add_lead.py --campaign-id 108 --profile-url https://linkedin.com/in/john-smith --personalised-message "Custom message here"
"""

import requests
import json
import sys
import argparse
from typing import Dict, Optional, List, Any
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv('MULTILEAD_API_KEY')
API_BASE_URL = os.getenv('MULTILEAD_API_BASE_URL', 'https://api.multilead.io/api/open-api/v1')


class MultileadClient:
    """Client for interacting with Multilead Open API."""
    
    def __init__(self, api_key: str, base_url: str = API_BASE_URL):
        """
        Initialize the Multilead client.
        
        Args:
            api_key: Multilead API key
            base_url: Base URL for API (defaults to v1)
        """
        if not api_key:
            raise ValueError("MULTILEAD_API_KEY environment variable not set")
        
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    
    def add_lead(
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
    ) -> Dict[str, Any]:
        """
        Add a single lead to a campaign.
        
        Args:
            campaign_id: ID of the campaign to add lead to (required)
            profile_url: LinkedIn profile URL (required if email not provided)
            email: Email address (required if profileUrl not provided)
            first_name: First name (optional)
            last_name: Last name (optional)
            occupation: Job title or company (optional)
            phone: Phone number (optional)
            personalised_message: Custom personalised message (optional)
            remove_db_duplicates: Check for duplicates across team (optional)
            custom_fields: Additional custom fields as dict (optional)
        
        Returns:
            API response as dictionary
        
        Raises:
            ValueError: If required fields are missing or invalid
            requests.RequestException: If API call fails
        """
        
        # Validation
        if not campaign_id:
            raise ValueError("campaign_id is required")
        
        if not profile_url and not email:
            raise ValueError("Either profile_url or email is required")
        
        # Build request payload
        payload = {
            'profileUrl': profile_url,
            'email': email,
            'firstName': first_name,
            'lastName': last_name,
            'occupation': occupation,
            'phone': phone,
        }
        
        # Add optional fields only if provided
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Add personalised message if provided (using custom field for template compatibility)
        if personalised_message:
            payload['personalisedMessage'] = personalised_message
        
        # Add duplicate detection if specified
        if remove_db_duplicates is not None:
            payload['removeDbDuplicates'] = 'true' if remove_db_duplicates else 'false'
        
        # Merge custom fields
        if custom_fields:
            payload.update(custom_fields)
        
        # Make API request
        endpoint = f"{self.base_url}/campaign/{campaign_id}/leads"
        
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=payload,
                timeout=10
            )
            
            # Handle response
            if response.status_code == 429:
                raise Exception(f"Rate limit exceeded. Retry after: {response.headers.get('Retry-After', 'unknown')} seconds")
            
            if response.status_code >= 400:
                raise Exception(f"API error {response.status_code}: {response.text}")
            
            return {
                'success': True,
                'data': response.json() if response.text else {'message': 'Lead added successfully'},
                'status_code': response.status_code
            }
        
        except requests.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'status_code': 500
            }
    
    def add_leads_batch(
        self,
        campaign_id: int,
        leads: List[Dict[str, Any]],
        remove_db_duplicates: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Add multiple leads to a campaign.
        
        Args:
            campaign_id: ID of the campaign
            leads: List of lead dictionaries with lead data
            remove_db_duplicates: Apply to all leads (optional)
        
        Returns:
            List of API responses for each lead
        """
        
        if not leads:
            raise ValueError("At least one lead must be provided")
        
        results = []
        
        for i, lead in enumerate(leads):
            # Extract personalised message if present
            personalised_msg = lead.pop('personalisedMessage', None)
            
            # Extract standard fields
            profile_url = lead.pop('profileUrl', None)
            email = lead.pop('email', None)
            first_name = lead.pop('firstName', None)
            last_name = lead.pop('lastName', None)
            occupation = lead.pop('occupation', None)
            phone = lead.pop('phone', None)
            
            # Remaining fields are custom
            custom_fields = lead if lead else None
            
            # Add lead
            result = self.add_lead(
                campaign_id=campaign_id,
                profile_url=profile_url,
                email=email,
                first_name=first_name,
                last_name=last_name,
                occupation=occupation,
                phone=phone,
                personalised_message=personalised_msg,
                remove_db_duplicates=remove_db_duplicates,
                custom_fields=custom_fields
            )
            
            result['lead_index'] = i
            results.append(result)
        
        return results


def main():
    """Command-line interface for adding leads."""
    
    parser = argparse.ArgumentParser(
        description='Add leads to a Multilead campaign with personalised messages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add single lead with email
  python add_lead.py --campaign-id 108 --email john@example.com --first-name John --last-name Smith
  
  # Add lead with LinkedIn profile URL
  python add_lead.py --campaign-id 108 --profile-url https://linkedin.com/in/john-smith
  
  # Add lead with personalised message
  python add_lead.py --campaign-id 108 --email john@example.com --personalised-message "Hi John, custom message here"
  
  # Add from JSON file
  python add_lead.py --campaign-id 108 --batch-file leads.json
  
  # Check for duplicates across team
  python add_lead.py --campaign-id 108 --email john@example.com --remove-duplicates
        """
    )
    
    parser.add_argument(
        '--campaign-id',
        type=int,
        required=True,
        help='Campaign ID (required)'
    )
    
    parser.add_argument(
        '--email',
        help='Email address (required if no profile-url)'
    )
    
    parser.add_argument(
        '--profile-url',
        help='LinkedIn profile URL (required if no email)'
    )
    
    parser.add_argument(
        '--first-name',
        help='First name (optional)'
    )
    
    parser.add_argument(
        '--last-name',
        help='Last name (optional)'
    )
    
    parser.add_argument(
        '--occupation',
        help='Job title or company (optional)'
    )
    
    parser.add_argument(
        '--phone',
        help='Phone number (optional)'
    )
    
    parser.add_argument(
        '--personalised-message',
        help='Custom personalised message (optional)'
    )
    
    parser.add_argument(
        '--remove-duplicates',
        action='store_true',
        help='Check for duplicates across team seats'
    )
    
    parser.add_argument(
        '--batch-file',
        help='JSON file with array of leads to add in batch'
    )
    
    parser.add_argument(
        '--output',
        default='result.json',
        help='Output file for results (default: result.json)'
    )
    
    parser.add_argument(
        '--api-key',
        help='Multilead API key (or use MULTILEAD_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or API_KEY
    if not api_key:
        print("Error: MULTILEAD_API_KEY not set. Provide via --api-key or environment variable.")
        sys.exit(1)
    
    # Initialize client
    client = MultileadClient(api_key)
    
    try:
        # Handle batch file
        if args.batch_file:
            with open(args.batch_file, 'r') as f:
                leads = json.load(f)
            
            if not isinstance(leads, list):
                raise ValueError("Batch file must contain a JSON array of leads")
            
            print(f"Adding {len(leads)} leads to campaign {args.campaign_id}...")
            results = client.add_leads_batch(
                campaign_id=args.campaign_id,
                leads=leads,
                remove_db_duplicates=args.remove_duplicates
            )
        
        # Handle single lead
        else:
            print(f"Adding lead to campaign {args.campaign_id}...")
            result = client.add_lead(
                campaign_id=args.campaign_id,
                profile_url=args.profile_url,
                email=args.email,
                first_name=args.first_name,
                last_name=args.last_name,
                occupation=args.occupation,
                phone=args.phone,
                personalised_message=args.personalised_message,
                remove_db_duplicates=args.remove_duplicates if args.remove_duplicates else None
            )
            results = [result]
        
        # Save results
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Summary
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        
        print(f"\n✓ Results saved to {args.output}")
        print(f"✓ Successful: {successful}")
        print(f"✗ Failed: {failed}")
        
        if failed > 0:
            sys.exit(1)
    
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
