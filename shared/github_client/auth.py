import jwt
import time
import httpx
from shared.config.settings import settings

# Cache installation tokens
# Key: installation_id, Value: (token_string, expires_at_timestamp)
token_cache: dict[int, tuple[str, float]] = {}

def generate_jwt() -> str:
    """Generates a GitHub App JWT."""
    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + (10 * 60),
        "iss": settings.GITHUB_APP_ID
    }
    
    # Needs to be a valid RSA private key PEM string
    private_key = settings.GITHUB_APP_PRIVATE_KEY
    if not private_key:
        raise ValueError("GITHUB_APP_PRIVATE_KEY is not set")
        
    return jwt.encode(payload, private_key, algorithm="RS256")

async def get_installation_token(installation_id: int) -> str:
    """Gets an installation token for a specific GitHub App installation."""
    now = time.time()
    if installation_id in token_cache:
        token, expires_at = token_cache[installation_id]
        if now < expires_at - 60: # 1 minute buffer
            return token
            
    jwt_token = generate_jwt()
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        response = await client.post(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        token = data["token"]
        # token expires in 1 hour usually, parse expires_at from response if needed, 
        # but let's just cache it for 9 minutes since jwt expires in 10 minutes anyway
        # Actually github installation tokens expire in 1 hour.
        token_cache[installation_id] = (token, now + 3540) # 59 minutes
        return token
