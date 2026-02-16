# Multilead Add Lead Script

Add leads to Multilead campaigns with personalised messages. Built for integration with your personalization workflow.

## Quick Start

### 1. Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your MULTILEAD_API_KEY
```

### 2. Add a Single Lead
```bash
python add_lead.py \
  --campaign-id 108 \
  --email john@example.com \
  --first-name John \
  --personalised-message "Hi John, custom message here"
```

### 3. Add Multiple Leads (Batch)
```bash
python add_lead.py --campaign-id 108 --batch-file example_leads.json
```

## Command Reference

```bash
# Single lead
python add_lead.py --campaign-id 108 --email user@example.com --first-name John

# With personalised message
python add_lead.py --campaign-id 108 --email user@example.com --personalised-message "Your custom message"

# Using LinkedIn profile URL
python add_lead.py --campaign-id 108 --profile-url https://linkedin.com/in/john-smith

# Batch from JSON
python add_lead.py --campaign-id 108 --batch-file leads.json

# Check for duplicates
python add_lead.py --campaign-id 108 --email user@example.com --remove-duplicates

# Custom output file
python add_lead.py --campaign-id 108 --email user@example.com --output my_results.json

# Using API key directly
python add_lead.py --campaign-id 108 --email user@example.com --api-key your_key_here
```

## Arguments

| Argument | Required | Notes |
|----------|----------|-------|
| `--campaign-id` | Yes | Campaign ID to add lead to |
| `--email` | If no profile-url | Email address |
| `--profile-url` | If no email | LinkedIn profile URL |
| `--first-name` | No | First name |
| `--last-name` | No | Last name |
| `--occupation` | No | Job title or company |
| `--phone` | No | Phone number |
| `--personalised-message` | No | Custom message (integrates with your personalization skill) |
| `--remove-duplicates` | No | Check for duplicates across team seats |
| `--batch-file` | No | JSON file with array of leads |
| `--output` | No | Output file (default: result.json) |
| `--api-key` | No | API key (use MULTILEAD_API_KEY env var if not provided) |

## Batch JSON Format

```json
[
  {
    "profileUrl": "https://www.linkedin.com/in/john-smith",
    "firstName": "John",
    "lastName": "Smith",
    "occupation": "CEO",
    "personalisedMessage": "Custom message here..."
  },
  {
    "email": "sarah@example.com",
    "firstName": "Sarah",
    "personalisedMessage": "Another custom message..."
  }
]
```

See `example_leads.json` for full example.

## Output

Results saved to JSON file (default: `result.json`):

```json
[
  {
    "success": true,
    "data": { "message": "Lead added successfully" },
    "error": null,
    "status_code": 200,
    "timestamp": "2025-01-15T10:30:45.123Z"
  }
]
```

## Integration with Personalization Skill

Use the `--personalised-message` argument to pass custom messages from your personalization skill.

**Note:** This script uses `personalisedMessage` as a custom field (not Multilead's built-in `personalizedField`). Ensure your campaign template uses `{{personalisedMessage}}` to reference the personalized message.

```python
# Your personalization skill generates a message
custom_message = generate_personalized_message(lead)

# Pass it to this script
os.system(f"python add_lead.py --campaign-id 108 --email {lead['email']} --personalised-message '{custom_message}'")
```

## Validation

Built-in validation for:
- Campaign ID (must be positive integer)
- Email (standard format validation)
- LinkedIn URL (must match profile URL pattern)
- Phone (7-15 digits)
- Names (letters, spaces, hyphens, apostrophes only)
- Message (max 5000 characters)

## Error Handling

All errors are saved to results JSON file with specific error messages. Common errors:

- "MULTILEAD_API_KEY not set" → Configure .env file
- "Invalid campaign ID" → Check campaign ID exists
- "Email or profileUrl required" → Provide at least one
- "Invalid email format" → Check email spelling
- "Invalid LinkedIn URL" → Use linkedin.com/in/username format
- "Rate limit exceeded" → Wait and retry

## API Reference

- Endpoint: `https://api.multilead.io/api/open-api/v1/campaign/{id}/leads`
- Method: POST
- Auth: API Key in Authorization header
- Docs: https://documenter.getpostman.com/view/7428744/UV5ZAGMg

## Files

- `add_lead.py` - Main script
- `utils.py` - Validation and utilities
- `requirements.txt` - Python dependencies
- `example_leads.json` - Example batch file
- `.env.example` - Environment template
- `SKILL.md` - Full documentation

## Python Module Usage

Import and use directly in code:

```python
from add_lead import MultileadClient

client = MultileadClient(api_key='your_key')
result = client.add_lead(
    campaign_id=108,
    email='john@example.com',
    first_name='John',
    personalised_message='Custom message'
)
```

## Troubleshooting

See `SKILL.md` for detailed troubleshooting guide.

## Requirements

- Python 3.8+
- requests >= 2.28.0
- python-dotenv >= 0.20.0

## License

Created for FAIE Group
