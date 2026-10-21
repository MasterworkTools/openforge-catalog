import logging
from typing import Dict, Optional, Tuple

import patreon
import requests
from flask import current_app
from psycopg import sql
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class OAuthService:
    """Service for handling OAuth authentication with Patreon and Google."""

    def __init__(self, db):
        self.db = db

    def _get_patreon_client(self, access_token: str = None) -> patreon.API:
        """Create a Patreon API client."""
        return patreon.API(access_token)

    def get_patreon_auth_url(self, redirect_uri: str, state: str) -> str:
        """Generate Patreon OAuth authorization URL."""
        client_id = current_app.config.get("PATREON_CLIENT_ID")
        if not client_id:
            raise ValueError("PATREON_CLIENT_ID not configured")

        # Patreon OAuth2 authorization endpoint
        auth_url = (
            f"https://www.patreon.com/oauth2/authorize"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=identity identity.memberships"
            f"&state={state}"
        )
        return auth_url

    def get_google_auth_url(self, redirect_uri: str, state: str) -> str:
        """Generate Google OAuth authorization URL."""
        client_id = current_app.config.get("GOOGLE_CLIENT_ID")
        if not client_id:
            raise ValueError("GOOGLE_CLIENT_ID not configured")

        # Google OAuth2 authorization endpoint
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=openid email profile"
            f"&state={state}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        return auth_url

    def exchange_patreon_code(self, code: str, redirect_uri: str) -> Dict:
        """Exchange Patreon authorization code for access token."""
        client_id = current_app.config.get("PATREON_CLIENT_ID")
        client_secret = current_app.config.get("PATREON_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError("Patreon OAuth credentials not configured")

        # Exchange code for token
        token_url = "https://www.patreon.com/api/oauth2/token"
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }

        response = requests.post(token_url, data=data)
        response.raise_for_status()

        return response.json()

    def exchange_google_code(self, code: str, redirect_uri: str) -> Dict:
        """Exchange Google authorization code for access token."""
        client_id = current_app.config.get("GOOGLE_CLIENT_ID")
        client_secret = current_app.config.get("GOOGLE_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError("Google OAuth credentials not configured")

        # Exchange code for token
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        }

        response = requests.post(token_url, data=data)
        response.raise_for_status()

        return response.json()

    def get_patreon_user_info(self, access_token: str) -> Tuple[Dict, Optional[str]]:
        """Get Patreon user information and tier."""
        api_client = self._get_patreon_client(access_token)

        # Get user identity with memberships
        # The patreon library handles the API v2 calls
        user_response = api_client.fetch_user(
            properties=["email", "full_name"],
            includes=["memberships", "memberships.currently_entitled_tiers"],
        )

        user = user_response["data"]

        # Extract user info
        user_info = {
            "provider_id": user["id"],
            "email": user["attributes"]["email"],
            "full_name": user["attributes"]["full_name"],
        }

        # Check for OpenForge membership and tier
        tier = None

        # Process included memberships
        if "included" in user_response:
            memberships = [
                item for item in user_response["included"] if item["type"] == "member"
            ]
            tiers = {
                item["id"]: item
                for item in user_response["included"]
                if item["type"] == "tier"
            }

            for membership in memberships:
                attrs = membership["attributes"]
                # Check if this is an active patron
                if attrs.get("patron_status") == "active_patron":
                    # Get currently entitled amount
                    amount_cents = attrs.get("currently_entitled_amount_cents", 0)

                    # Check entitled tiers if available
                    entitled_tiers = (
                        membership.get("relationships", {})
                        .get("currently_entitled_tiers", {})
                        .get("data", [])
                    )

                    # Try to get tier from entitled tiers first
                    if entitled_tiers and tiers:
                        # Get the highest tier by amount
                        highest_amount = 0
                        for tier_ref in entitled_tiers:
                            if tier_ref["id"] in tiers:
                                tier_data = tiers[tier_ref["id"]]
                                tier_amount = tier_data["attributes"].get(
                                    "amount_cents", 0
                                )
                                if tier_amount > highest_amount:
                                    highest_amount = tier_amount
                                    tier_title = tier_data["attributes"]["title"]
                                    # Use the actual tier title from Patreon
                                    # This will need to be mapped to our ENUM values
                                    tier = self._map_patreon_tier_to_enum(tier_title)

                    # Fallback to amount-based tier detection
                    if not tier and amount_cents:
                        # These will need to be updated based on actual campaign tiers
                        tier = self._get_tier_by_amount(amount_cents)
                    break

        return user_info, tier

    def _map_patreon_tier_to_enum(self, tier_title: str) -> Optional[str]:
        """Map Patreon tier title to our database enum value."""
        # This mapping should be configured based on actual Patreon tiers
        # For now, we'll use a simple mapping that can be updated
        tier_map = current_app.config.get("PATREON_TIER_MAP", {})

        # If no mapping configured, try to guess based on common patterns
        if not tier_map:
            title_lower = tier_title.lower()
            if any(word in title_lower for word in ["platinum", "highest", "top"]):
                return "Platinum"
            elif any(word in title_lower for word in ["gold", "premium"]):
                return "Gold"
            elif any(word in title_lower for word in ["silver", "standard"]):
                return "Silver"
            elif any(word in title_lower for word in ["bronze", "basic", "supporter"]):
                return "Bronze"

        return tier_map.get(tier_title)

    def _get_tier_by_amount(self, amount_cents: int) -> Optional[str]:
        """Get tier based on pledge amount."""
        # These thresholds should be configured based on actual campaign
        tier_amounts = current_app.config.get(
            "PATREON_TIER_AMOUNTS",
            {
                "Platinum": 2000,  # $20
                "Gold": 1000,  # $10
                "Silver": 500,  # $5
                "Bronze": 100,  # $1
            },
        )

        # Find the highest tier that matches the amount
        for tier_name in ["Platinum", "Gold", "Silver", "Bronze"]:
            if amount_cents >= tier_amounts.get(tier_name, float("inf")):
                return tier_name

        return None

    def get_patreon_campaign_tiers(self, campaign_id: str = None) -> Dict:
        """Fetch campaign tiers from Patreon to get actual tier structure."""
        # This would require campaign access token, not user token
        # For now, this is a placeholder for future implementation
        # You would call this during setup to configure tier mappings
        pass

    def get_google_user_info(self, access_token: str) -> Dict:
        """Get Google user information."""
        # Get user info from Google
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo", headers=headers
        )
        response.raise_for_status()

        data = response.json()
        return {
            "provider_id": data["id"],
            "email": data["email"],
            "full_name": data.get("name"),
        }

    def find_or_create_user(
        self,
        provider: str,
        provider_id: str,
        email: str,
        patreon_tier: Optional[str] = None,
    ) -> Dict:
        """Find existing user or create new one."""
        with self.db.connection() as conn:
            with conn.cursor(row_factory=dict_row) as curs:
                # First check if identity exists
                query = sql.SQL(
                    """
                    SELECT u.*
                    FROM users u
                    JOIN user_identities ui ON u.id = ui.user_id
                    WHERE ui.provider = {provider} AND ui.provider_id = {provider_id}
                    """
                ).format(
                    provider=sql.Placeholder("provider"),
                    provider_id=sql.Placeholder("provider_id"),
                )
                curs.execute(query, {"provider": provider, "provider_id": provider_id})
                user = curs.fetchone()

                if user:
                    # Update Patreon tier if applicable
                    if provider == "patreon" and patreon_tier != user["patreon_tier"]:
                        update_query = sql.SQL(
                            """
                            UPDATE users
                            SET patreon_tier = {tier}, updated_at = now()
                            WHERE id = {user_id}
                            """
                        ).format(
                            tier=sql.Placeholder("tier"),
                            user_id=sql.Placeholder("user_id"),
                        )
                        curs.execute(
                            update_query, {"tier": patreon_tier, "user_id": user["id"]}
                        )
                        user["patreon_tier"] = patreon_tier
                    return user

                # Check if user exists with same email
                query = sql.SQL(
                    """
                    SELECT * FROM users WHERE email = {email}
                    """
                ).format(email=sql.Placeholder("email"))
                curs.execute(query, {"email": email})
                user = curs.fetchone()

                if user:
                    # Link existing user to new identity
                    insert_identity = sql.SQL(
                        """
                        INSERT INTO user_identities (provider, provider_id, user_id)
                        VALUES ({provider}, {provider_id}, {user_id})
                        """
                    ).format(
                        provider=sql.Placeholder("provider"),
                        provider_id=sql.Placeholder("provider_id"),
                        user_id=sql.Placeholder("user_id"),
                    )
                    curs.execute(
                        insert_identity,
                        {
                            "provider": provider,
                            "provider_id": provider_id,
                            "user_id": user["id"],
                        },
                    )

                    # Update tier if Patreon
                    if provider == "patreon" and patreon_tier:
                        update_query = sql.SQL(
                            """
                            UPDATE users
                            SET patreon_tier = {tier}, updated_at = now()
                            WHERE id = {user_id}
                            """
                        ).format(
                            tier=sql.Placeholder("tier"),
                            user_id=sql.Placeholder("user_id"),
                        )
                        curs.execute(
                            update_query, {"tier": patreon_tier, "user_id": user["id"]}
                        )
                        user["patreon_tier"] = patreon_tier
                else:
                    # Create new user
                    insert_user = sql.SQL(
                        """
                        INSERT INTO users (email, role, patreon_tier)
                        VALUES ({email}, {role}, {tier})
                        RETURNING *
                        """
                    ).format(
                        email=sql.Placeholder("email"),
                        role=sql.Placeholder("role"),
                        tier=sql.Placeholder("tier"),
                    )
                    curs.execute(
                        insert_user,
                        {
                            "email": email,
                            "role": "user",  # Default role
                            "tier": patreon_tier,
                        },
                    )
                    user = curs.fetchone()

                    # Create identity link
                    insert_identity = sql.SQL(
                        """
                        INSERT INTO user_identities (provider, provider_id, user_id)
                        VALUES ({provider}, {provider_id}, {user_id})
                        """
                    ).format(
                        provider=sql.Placeholder("provider"),
                        provider_id=sql.Placeholder("provider_id"),
                        user_id=sql.Placeholder("user_id"),
                    )
                    curs.execute(
                        insert_identity,
                        {
                            "provider": provider,
                            "provider_id": provider_id,
                            "user_id": user["id"],
                        },
                    )

                return user
