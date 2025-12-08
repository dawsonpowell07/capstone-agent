from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
import logging
from typing import Optional, Dict, Any

from config import get_settings

settings = get_settings()

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Cosmos Client
cosmos_client = CosmosClient(
    url=settings.cosmos_db_endpoint,
    credential=settings.cosmos_db_key
)
database = cosmos_client.get_database_client(settings.cosmos_db_database_name)
user_profile_container = database.get_container_client("UserProfiles")


async def fetch_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user profile from CosmosDB.

    Args:
        user_id: The user ID to fetch the profile for

    Returns:
        User profile dict if successful, None if user not found or on error.
    """
    if not user_id:
        logger.warning("No user_id provided to fetch_user_profile")
        return None

    try:
        # Read the user profile from Cosmos DB
        # Assuming user_id is both the id and partition key
        user_profile = user_profile_container.read_item(
            item=user_id,
            partition_key=user_id
        )
        logger.info(
            f"Successfully fetched user profile for user_id: {user_id}")
        return user_profile

    except CosmosResourceNotFoundError:
        logger.warning(f"User profile not found for user_id: {user_id}")
        return None

    except Exception as e:
        logger.error(
            f"Error fetching user profile for user_id {user_id}: {str(e)}")
        return None


# async def test_fetch_user_profile():
#     """Test the fetch_user_profile function with CosmosDB."""
#     # Configure logging for the test
#     logging.basicConfig(level=logging.INFO)

#     print("=" * 60)
#     print("TESTING FETCH USER PROFILE")
#     print("=" * 60)

#     # Test 1: Fetch with a real user ID
#     test_user_id = "auth0|68feab42bd9b8a1be3e566c3"
#     print(f"\n1. Testing fetch_user_profile with user_id: {test_user_id}")
#     try:
#         result = await fetch_user_profile(test_user_id)
#         if result:
#             print("✓ Successfully fetched user profile:")
#             print(f"  User ID: {result.get('id')}")
#             print(f"  Name: {result.get('name', 'N/A')}")
#             print(f"  Email: {result.get('email', 'N/A')}")
#             print(f"  Full profile: {result}")
#         else:
#             print(f"⚠ No user profile found for user_id: {test_user_id}")
#     except Exception as e:
#         print(f"✗ Error fetching user profile: {e}")

#     # Test 2: Fetch with empty user ID
#     print("\n2. Testing fetch_user_profile with empty user_id")
#     try:
#         result = await fetch_user_profile("")
#         if result is None:
#             print("✓ Correctly returned None for empty user_id")
#         else:
#             print(f"✗ Unexpected result: {result}")
#     except Exception as e:
#         print(f"✗ Error: {e}")

#     # Test 3: Fetch with non-existent user ID
#     print("\n3. Testing fetch_user_profile with non-existent user_id")
#     try:
#         result = await fetch_user_profile("non-existent-user-999")
#         if result is None:
#             print("✓ Correctly returned None for non-existent user")
#         else:
#             print(f"✗ Unexpected result: {result}")
#     except Exception as e:
#         print(f"✗ Error: {e}")

#     print("\n" + "=" * 60)
#     print("TESTS COMPLETED")
#     print("=" * 60)


# if __name__ == "__main__":
#     """
#     Run tests when executed directly.

#     Usage:
#         python -m utils.utils

#     Make sure to update test_user_id in test_fetch_user_profile()
#     with a real user ID from your CosmosDB database.
#     """
#     import asyncio
#     asyncio.run(test_fetch_user_profile())
