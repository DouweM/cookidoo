"""Constants extracted from the Cookidoo Android app (com.vorwerk.cookidoo 26.6.19).

Everything here was recovered by reverse-engineering the APK. See ``research/re/``
for provenance (source file:line references).
"""

from __future__ import annotations

from typing import Final

APP_VERSION: Final = '26.6.19'

# a_plugin/uyi.java — always sent (overwrites any existing UA).
USER_AGENT: Final = f'nwot-mobile-android/{APP_VERSION} (Android/14)'

# a_plugin/u16.java — %1s is replaced by the market code, lowercased.
ENV_HOST_TEMPLATES: Final = {
    'prod': 'https://{market}.tmmobile.vorwerk-digital.com',
    'int': 'https://{market}.mobile.integration.cookidoo.vorwerk-digital.com',
    'demo': 'https://{market}.mobile.demo.cookidoo.vorwerk-digital.com',
    'content_staging': 'https://{market}.mobile.contentstaging.cookidoo.vorwerk-digital.com',
}

# a_plugin/imf.java
HOME_DOCUMENT_PATH: Final = '/.well-known/mobile-home'

# HAL media types (Accept headers). a_plugin/*.java @Headers.
HOME_ACCEPT: Final = 'application/vnd.vorwerk.tmde2.rhd.mobile.hal+json, application/hal+json'
MEDIA_RECIPE: Final = 'application/vnd.vorwerk.recipe.mobile.v1+json'
MEDIA_PLANNING_MY_DAY: Final = 'application/vnd.vorwerk.planning.my-day.mobile+json'
MEDIA_CUSTOM_LIST: Final = 'application/vnd.vorwerk.organize.custom-list.mobile+json'
MEDIA_MANAGED_LIST: Final = 'application/vnd.vorwerk.organize.managed-list.mobile+json'
MEDIA_BOOKMARK: Final = 'application/vnd.vorwerk.organize.bookmark.mobile+json'
MEDIA_CUSTOMER_RECIPE_FULL: Final = 'application/vnd.vorwerk.customer-recipe.full+json'

# --- OAuth2 / OIDC (PKCE authorization-code). a_plugin/ic0.java, accountweb/data/login/a.java ---
OAUTH_CLIENT_ID: Final = 'mobile-android'
OAUTH_REDIRECT_URI: Final = 'com.vorwerk.cookidoo://code-grant'
OAUTH_SCOPE: Final = 'openid profile email offline offline_access'
OAUTH_RESPONSE_TYPE: Final = 'code'
OAUTH_CODE_CHALLENGE_METHOD: Final = 'S256'
# Basic auth on the token endpoint (mobile-android:<secret>), a_plugin/ic0.java:6.
OAUTH_TOKEN_BASIC_USER: Final = 'mobile-android'
OAUTH_TOKEN_BASIC_PASS: Final = 'kautGGimGLJgpXQaAZUHqRsuz4bKUw'
# Required cookie on token requests, a_plugin/o6.java @Headers.
OAUTH_TOKEN_COOKIE: Final = 'vrkPreAccessGranted=true'

# --- Remote monitoring (RMI) + Firebase Cloud Messaging (live cooking status) ---
# Header required on the IoT gateway (a_plugin/fbf.java @Headers).
RMI_API_VERSION: Final = '2026-06-01'
# Android package (used as bundleId when registering a push token).
ANDROID_PACKAGE: Final = 'com.vorwerk.cookidoo'
# Firebase project of the app (res/values/strings.xml). App-public, in every APK.
FIREBASE_PROJECT_ID: Final = 'cookidoo-app'
FIREBASE_APP_ID: Final = '1:447648593759:android:ebfbf2b01378844b'
FIREBASE_API_KEY: Final = 'AIzaSyCPyZm8EAdpVhWhNLFv3cOw_Kx4iNxR_E4'
FIREBASE_SENDER_ID: Final = '447648593759'


# Root home document HAL relations (RootHomeLinksDto). All prefixed ``tmde2:``.
class Rel:
    """Top-level (root home document) HAL link relations."""

    SEARCH = 'tmde2:search'
    RECIPE_DETAILS = 'tmde2:recipe-details'
    ORGANIZE = 'tmde2:organize'
    PLANNING = 'tmde2:planning'
    FOUNDATION = 'tmde2:foundation'
    FOUNDATION_TUTORIALS = 'tmde2:foundation-tutorials'
    PROFILE = 'tmde2:profile'
    OWNERSHIP = 'tmde2:ownership'
    COMMERCE = 'tmde2:commerce'
    COMMUNITY_INTEGRATION = 'tmde2:community-integration'
    AUTH = 'tmde2:auth'
    PANTRY = 'tmde2:pantry'
    NORTH_FORK = 'tmde2:north-fork'
    COLLECTIONS = 'tmde2:collections'
    RATING = 'tmde2:rating'
    RECOMMENDER = 'tmde2:recommender'
    COMMUNITY_PROFILE = 'tmde2:community-profile'
    MOBILE_CONFIG = 'tmde2:mobile-config'
    CUSTOMER_RECIPES = 'tmde2:customer-recipes'
    COOKIDOO_SERVED = 'tmde2:cookidoo-served'
    NOTIFICATION_CENTER = 'tmde2:mobile-notification'
    RMI_CONFIG = 'tmde2:rmi-config'
    RECIPE_NOTES = 'tmde2:recipe-notes'
    MOBILE_PURCHASES = 'tmde2:mobile-purchases'
    COPILOT = 'tmde2:copilot'
    CAMPAIGN = 'tmde2:campaign-distribution-service'
    CUSTOMER_DEVICES = 'tmde2:customer-devices'


# Auth sub-document relations (AccountWebHomeLinksDto).
AUTH_REL_DISCOVERY: Final = 'auth:open-id-connect-discovery'
AUTH_REL_TOKEN: Final = 'auth:token'
AUTH_REL_CODE_GRANT: Final = 'auth:code-grant'
AUTH_REL_REGISTRATION: Final = 'auth:registration'
AUTH_REL_RESET: Final = 'auth:reset'
