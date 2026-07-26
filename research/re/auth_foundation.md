# Cookidoo Android (v26.6.19) — Auth & Foundation API Contract

Reverse-engineered from jadx output at
`decompiled/base/sources`.

> **Stack correction:** The task brief assumed **Ktor**. The decompiled evidence
> shows the networking stack is actually **OkHttp** (`n3c` = `OkHttpClient`) +
> **Retrofit** (`gjf` = `Retrofit`, built in `a_plugin/enb.java`) + **Moshi**
> (`com.squareup.moshi.j`, adapters annotated `@nz8` = Moshi `@Json`) +
> **RxJava 3** (`eyg` = `Single`, `sv1` = `Completable`, `l0h` = `SingleSource`,
> `bx1` = `CompletableSource`). Some newer token-storage code uses
> **kotlinx.serialization** + coroutines (`a_plugin/hii.java`). There is no Ktor
> client. Retrofit annotation aliases seen: `@fu7`=`@GET`, `@knc`=`@POST`,
> `@ld7`=`@FormUrlEncoded`, `@zn6`=`@Field`, `@h68`=`@Header`, `@r68`=`@Headers`,
> `@cyi`=`@Url`, `@vv0`=`@Body`.

---

## 1. OAuth2 / OIDC configuration (PKCE authorization-code)

| Constant | Value | Source |
|---|---|---|
| `response_type` | `code` | `com/cookidoo/android/accountweb/data/login/a.java:88` |
| `client_id` (authorize, **prod**) | `mobile-android` | `a.java:88` → `ic0.d(false,false,3,null)` → `a_plugin/ic0.java:20` (base64 `bW9iaWxlLWFuZHJvaWQ=`) |
| `client_id` (non-prod) | `kupferwerk-client-nwot` | `a_plugin/ic0.java:20` (base64 `a3VwZmVyd2Vyay1jbGllbnQtbndvdA==`) |
| `redirect_uri` | `com.vorwerk.cookidoo://code-grant` | injected DI string; used at `a_plugin/ul1.java:52` and intercepted at `ul1.java:399` |
| `scope` | `openid profile email offline offline_access` | `a.java:88` (note: `ul1.java:34` variant orders it `openid profile email offline_access offline`) |
| `code_challenge_method` | `S256` | `a.java:88`, `ul1.java` |
| `code_challenge` | PKCE, `BASE64URL(SHA-256(verifier))` | `a.java:88` via `vwg.k()`; `ul1.e(verifier)` |
| `state` | random, stored in `ywg` (`signInCodeGrantStateDataSource`) | `a.java:88` (`y.j()`), validated in `m0()` via `y.k(state)` |
| `market` | UI market code (query param `market`) | `a.java:88` (`R(market)`) |
| `ui_locales` | `Locale.getDefault().toLanguageTag()` | `a.java:88` |
| `grant_type` (login) | `authorization_code` | `a_plugin/o6.java` (`@Field("grant_type")`, default `"authorization_code"`) |
| `grant_type` (refresh) | `refresh_token` | `a_plugin/o6.java` `b(...)`; called `a_plugin/cii.java:91` |
| Token-endpoint Basic auth (**prod**, code-grant) | `Basic bW9iaWxlLWFuZHJvaWQ6a2F1dEdHaW1HTEpncFhRYUFaVUhxUnN1ejRiS1V3` = `mobile-android:kautGGimGLJgpXQaAZUHqRsuz4bKUw` | `a_plugin/ic0.java:6` |
| Token-endpoint Basic auth (non-int/non-code-grant) | `Basic a3VwZmVyd2Vyay1jbGllbnQtbndvdDpMczUwT04xd295U3FzMWRDZEpnZQ==` = `kupferwerk-client-nwot:Ls50ON1woySqs1dCdJge` | `a_plugin/ic0.java:6` |
| Extra token-request header | `Cookie: vrkPreAccessGranted=true` | `a_plugin/o6.java` `@Headers` on both token calls |

**`client_id` selector** `ic0.c(z,z2)` (`ic0.java:18-25`): returns
`mobile-android` when `!z2 && z` else `kupferwerk-client-nwot`. In the login
authorize builder `ic0.d(false,false,3,null)` → defaults `z=true,z2=false` →
`mobile-android`. In refresh `ic0.d(isProd,false,2,null)` → prod=`mobile-android`,
non-prod=`kupferwerk-client-nwot`.

**Basic-auth selector** `ic0.a(z,z2,z3)` (`ic0.java:4-8`): if `(z2||z3)` →
(`!z ? "" : "Basic mobile-android:kautGG…"`) else `"Basic kupferwerk-client-nwot:Ls50…"`.
Call args are `(isProd, isIntegration, isLoginTypeCodeGrant)` for refresh
(`cii.java:91`) and `(isProd, true, false)` for login token exchange (`a.java:184`).

### Endpoints (all discovered dynamically — no hardcoded CIAM host)

The app does **not** hardcode the CIAM host. Instead it walks the HAL home
document:

1. Root home doc → `auth` link (`tmde2:auth`).
2. Auth home doc (`AccountWebHomeLinksDto`) → `auth:open-id-connect-discovery`
   link → GET returns `OpenIdDiscoveryDocumentDto`.
3. `OpenIdDiscoveryDocumentDto` provides:
   - `authorization_endpoint` → `authorizationUrl` (`OpenIdDiscoveryDocumentDto.java`)
   - `token_endpoint` → `tokenUrl`

The authorize URL is that `authorizationUrl` with the query params from the table
appended (`a.java:86-89`). The token/refresh POSTs go to `tokenUrl`
(`a.java:184`, `cii.java` `d.apply` returns `it.getTokenUrl()`).
**No `end_session`/logout/userinfo URL exists in the discovery DTO** — only
`authorization_endpoint` and `token_endpoint` are parsed.

---

## 2. Full login flow (PKCE code grant via WebView)

1. **Build authorize URL** — `axg.R(market)` (`a.java:258`):
   fetch auth home doc → follow `auth:open-id-connect-discovery` → GET discovery →
   take `authorization_endpoint`, append
   `response_type=code, client_id=mobile-android, redirect_uri=com.vorwerk.cookidoo://code-grant,
   market=<market>, scope=openid profile email offline offline_access,
   state=<random>, code_challenge=<S256(verifier)>, code_challenge_method=S256,
   ui_locales=<lang-tag>`.
2. **User authenticates in a WebView** (`accountweb/presentation/login/webview/**`).
   Username/password are entered on the CIAM-hosted HTML page; the app does not
   post credentials itself.
3. **Redirect interception** — the WebView watches for a redirect to
   `com.vorwerk.cookidoo://code-grant?...` (`a_plugin/ul1.java:399`,
   `startsWith("com.vorwerk.cookidoo://code-grant")`) and extracts `code` + `state`.
4. **Exchange code for tokens** — `axg.m0(code, state)` (`a.java:266`):
   - Validate `state` against stored value (`ywg.k(state)`); throw `xwg.a` if invalid.
   - Re-fetch discovery, combine with `isProdEnvironment`.
   - `o6.a(Authorization, tokenUrl, code, "authorization_code", redirect_uri, code_verifier)`
     — `Content-Type: application/x-www-form-urlencoded`, header
     `Cookie: vrkPreAccessGranted=true`, and Basic-auth `Authorization`
     (`Basic mobile-android:kautGG…` in prod).
     Body fields: `code`, `grant_type=authorization_code`,
     `redirect_uri=com.vorwerk.cookidoo://code-grant`, `code_verifier`.
     (**Note:** `client_id` is *not* in the body for the login exchange — it rides
     in the Basic-auth header. The `ul1.java:2066` map that *does* include
     `client_id` is a separate/legacy builder.)
   - On `invalid_grant` error JSON (`SignInError{ "error" }`), map to `xwg.b`
     (`a.java:204-224`).
5. **Persist tokens** — mapper `pc0.a(auth)` (`a_plugin/pc0.java`) builds an
   internal token model and `i6.s(...)` stores it via `accountManagerRepository`.

---

## 3. Token model, storage, user info, refresh

### Token response — `AuthResponseDto`
`com/cookidoo/android/foundation/data/home/auth/AuthResponseDto.java`

| JSON key | field | type |
|---|---|---|
| `access_token` | accessToken | String |
| `refresh_token` | refreshToken | String |
| `token_type` | tokenType | String |
| `id_token` | idToken | String? |
| `expires_in` | expiresIn | int (seconds) |

Expiry is computed as HTTP `Date` response header + `expires_in` seconds
(`pc0.java` `a()`), stored as `expiresAt` millis.

### User info — decoded from the `id_token` JWT (no userinfo HTTP call)
`pc0.c(idToken)` (`pc0.java:27-38`) splits the JWT on `.`, takes segment **1**
(payload), base64url-decodes it (`-`→`+`, `_`→`/`, then `tgh.a` = base64 decode)
and Moshi-parses into `UserInfoDto`:

`UserInfoDto` (`…/home/auth/UserInfoDto.java`):
| JSON key | field |
|---|---|
| `email` | email |
| `given_name` | givenName |
| `family_name` | familyName |
| `sub` | dcid |
| `roles` | roles: List<String> |
| `customFields` | customFields: UserCustomFieldsDto |

`UserCustomFieldsDto`: `country_of_residence` → countryOfResidence.

### Persisted token snapshot — `hii$StoredTokensSnapshot`
kotlinx.serialization (`a_plugin/hii.java:67-107`), fields:
`version` (Long), `accessToken`, `refreshToken`, `expiresAt`, `sessionToken`,
`loginType`. Legacy variant `uk9$b LegacyTokenData`: accessToken, refreshToken,
expirationTimestampMillis, sessionToken, loginType. In-memory `AuthState`
(`a_plugin/h6.java:138`) adds `accessTokenCaptured`, `webSessionToken`, `email`,
`familyName`, `givenName`, `dcid`, `roles`.

### Refresh — `a_plugin/cii.java` + `a_plugin/o6.java`
`o6.b(url, "refresh_token", refreshToken, client_id, Authorization)` — POST
form-encoded to `tokenUrl`, header `Cookie: vrkPreAccessGranted=true`.
- `client_id` = `ic0.d(isProd,false,2,null)` → prod `mobile-android`, else `kupferwerk-client-nwot`.
- `Authorization` = `ic0.a(isProd, isIntegration, isLoginTypeCodeGrant)` (Basic).
On refresh failure the app triggers logout / re-login
(`TokenUtilsKt$logoutOnTokenRefreshFailed`, action
`com.vorwerk.cookidoo.ACTION_START_LOGIN_CODE_GRANT`).

### Logout
No OIDC `end_session` endpoint. Logout is a local operation via `g5a`
logoutExecutor (`a_plugin/l9.java`) that clears stored tokens + registered
`h5a` logout handlers (`a.E()` → `accountManagerRepository.w()`).

---

## 4. How the bearer token is attached (OkHttp interceptors)

Two app-level `Interceptor`s (`zu8`) are installed on the **auth client**
(`NetworkModuleKt.z`, DI qualifier `"auth client"`; the non-auth client omits the
bearer one, `NetworkModuleKt.A`).

- **`a_plugin/kc0.java` (auth interceptor):** if the request has no
  `Authorization` header, it blocking-reads the current access token
  (`accountManagerRepository.x()`) and adds
  `Authorization: Bearer <accessToken>` (`kc0.java` inner `a.a()` →
  `"Bearer " + accessToken`).
- **`a_plugin/m68.java` (Cookidoo headers interceptor):** ensures, only if absent:
  - `Accept: application/json`
  - `Accept-Language: en;q = 1, de-AT;q = 0.9` (literal string, spaces around `=` as decompiled — `m68.java`)
  - `Content-Type: application/json`
  - `Cookie: <safeguard cookie>` — only in **demo** env, value `nwotcookie2024=<token>` (`a_plugin/vx7.java`)
  - `User-Agent: <see below>` (always forces/overwrites)

Retrofit itself is built with a **placeholder base URL** `https://127.0.0.1`
(`NetworkModuleKt.B/C`); every real call uses Retrofit `@Url` (`@cyi`) with an
absolute URL resolved from HAL links, so the base URL is irrelevant.

### User-Agent
`a_plugin/uyi.java`: `nwot-mobile-android/26.6.19 (Android/<Build.VERSION.RELEASE>)`
(prefix `nwot-mobile`, `-android/`, appVersion `26.6.19`, `(Android/<os release>)`).
DI qualifier `"user agent cookidoo app"` (`NetworkModuleKt:227-239`).

---

## 5. Base URL / locale construction

Environment host templates (`a_plugin/u16.java`, `a_plugin/x16.java`), `%1s` =
market code lowercased:

| Env (`u16` subclass) | Name | Template |
|---|---|---|
| `u16.e` | `PROD` | `https://%1s.tmmobile.vorwerk-digital.com` |
| `u16.d` | `INT` | `https://%1s.mobile.integration.cookidoo.vorwerk-digital.com` |
| `u16.c` | `DEMO` | `https://%1s.mobile.demo.cookidoo.vorwerk-digital.com` |
| `u16.b` | `CONTENT_STAGING` | `https://%1s.mobile.contentstaging.cookidoo.vorwerk-digital.com` |

`u16.b(localization)` (`u16.java` `public String b(xy9)`):
`template.replace("%1s", localization.countryCode.toLowerCase(ROOT))`.
`xy9` (`a_plugin/xy9.java`) holds `countryCode`, `languageCode`, and derives a
`language-COUNTRY` tag. Environment name + resolved base URL are persisted in
core storage keys `environment_name_key` / `environment_base_url_key`
(`x16.java`); default env = **PROD**.

> The website host `https://cookidoo.<tld>` also appears
> (`NavigateToRecipeDeepLinkKt` → `https://cookidoo.de/recipes/recipe/<id>`) but
> the **mobile API** uses the `*.tmmobile.vorwerk-digital.com` (prod) hosts above.

### Home-document entry endpoint
`a_plugin/imf.java` (`hmf` impl) fetches the root home doc from:

```
GET {baseUrl}/.well-known/mobile-home
```

(`imf.java:41` — `baseUrl + "/.well-known/mobile-home"`), i.e. in prod
`https://<market>.tmmobile.vorwerk-digital.com/.well-known/mobile-home`.
If an "alternative home document URL" is set, it's used verbatim instead.
Fetched by `a_plugin/gmf.java`:

```java
@GET @Headers({"Accept: application/vnd.vorwerk.tmde2.rhd.mobile.hal+json, application/hal+json"})
Single<RootHomeDto> a(@Url String url);
```

The home doc is deserialized via a custom Moshi adapter (`enb$a`) that reads the
JSON object, parses known link fields, and stuffs every `{ "href": … }` child
into a generic `linkMap` on `ScsDto` (`a_plugin/enb.java`). Other features resolve
their URLs by URI-template-expanding a `LinkDto.href`
(`a_plugin/sn9.java` → `oxi.e(href, values)`; auto-adds `lang` = language tag).

---

## 6. HAL link relations

### Root home doc — `RootHomeDto` / `RootHomeLinksDto`
`RootHomeDto`: `_links` → `RootHomeLinksDto`.
Relations (`@Json name` → field):

| rel | field |
|---|---|
| `self` | self |
| `tmde2:search` | search |
| `tmde2:recipe-details` | recipeDetails |
| `tmde2:organize` | organize |
| `tmde2:planning` | planning |
| `tmde2:foundation` | foundation |
| `tmde2:foundation-tutorials` | foundationTutorials |
| `tmde2:profile` | profile |
| `tmde2:ownership` | ownership |
| `tmde2:commerce` | commerce |
| `tmde2:community-integration` | communityIntegration |
| `tmde2:auth` | auth |
| `tmde2:pantry` | pantry |
| `tmde2:north-fork` | northfork |
| `tmde2:collections` | collections |
| `tmde2:rating` | recipeRating |
| `tmde2:recommender` | recommender |
| `tmde2:community-profile` | communityProfile |
| `tmde2:mobile-config` | mobileConfig |
| `tmde2:customer-recipes` | customerRecipes |
| `tmde2:cookidoo-served` | cookidooServed |
| `tmde2:mobile-notification` | notificationCenter |
| `tmde2:rmi-config` | rmiConfig |
| `tmde2:recipe-notes` | recipeNotes |
| `tmde2:mobile-purchases` | mobilePurchases |
| `tmde2:copilot` | copilot |
| `tmde2:campaign-distribution-service` | campaignDistributionService |
| `tmde2:customer-devices` | customerDevices |

### Auth home doc — `AccountWebHomeLinksDto`
`…/home/auth/AccountWebHomeLinksDto.java` (extends `ScsDto`):

| rel | field |
|---|---|
| `self` | self |
| `auth:client-credential` | authClientCredential |
| `auth:registration` | authRegistration |
| `auth:reset` | authReset |
| `auth:code-grant` | authCodeGrant |
| `auth:implicit` | authImplicit |
| `auth:token` | authToken |
| `auth:open-id-connect-discovery` | authOpenIdDiscovery |

---

## 7. Vendor media types (`application/vnd.vorwerk.*`)

Seen across Retrofit `@Headers` (`a_plugin/*.java`):

- `application/vnd.vorwerk.tmde2.rhd.mobile.hal+json` (+ `application/hal+json`) — home documents
- `application/vnd.vorwerk.planning.my-day.mobile+json`
- `application/vnd.vorwerk.recipe.mobile.v1+json`
- `application/vnd.vorwerk.organize.custom-list.mobile+json`
- `application/vnd.vorwerk.organize.managed-list.mobile+json`
- `application/vnd.vorwerk.organize.bookmark.mobile+json`
- `application/vnd.vorwerk.customer-recipe.full+json`

---

## 8. Key serializable DTOs (Moshi `@nz8` = `@Json`)

- **`OpenIdDiscoveryDocumentDto`** — `authorization_endpoint`→authorizationUrl,
  `token_endpoint`→tokenUrl.
- **`AuthResponseDto`** — see §3.
- **`UserInfoDto` / `UserCustomFieldsDto`** — see §3.
- **`SignInError`** — `error`→error (`accountweb/data/login/SignInError.java`).
- **`RootHomeDto`** — `_links`→links (`RootHomeLinksDto`).
- **`RootHomeLinksDto`**, **`AccountWebHomeLinksDto`** — §6.
- **`LocalizationConfigDto`** — `markets`→List<MarketDto>
  (`accountweb/data/selectlocale/LocalizationConfigDto.java`).
- **`MarketDto`** — `marketCode`→code, `allowedUILanguages`→languages: List<String>,
  `countries`→List<CountryDto>, `mainDomain`→market, `awsRegion`→awsRegion.
- **`LinkDto`** (`com.vorwerk.datacomponents.android.network.home.LinkDto`) — HAL
  link with `href` (URI-template capable via `oxi.e`).

---

## 9. Miscellaneous constants

- Snowplow tracking collector: prod `https://com-vorwerk-prod1.mini.snplow.net`,
  else `https://cmobile.cookidoo.de` (`a_plugin` grep line 95).
- Internal-URL deeplink scheme: `com.vorwerk.cookidoo://internalurl?url=<url>`.
- Login re-trigger action: `com.vorwerk.cookidoo.ACTION_START_LOGIN_CODE_GRANT`.
- Demo-env safeguard cookie name: `nwotcookie2024`.

### UNCERTAIN / notes
- The exact bytes of `Accept-Language` (`en;q = 1, de-AT;q = 0.9`) include spaces
  around `=`; this is verbatim from the decompiled literal and may be a jadx
  artifact, but is stored/sent as-is.
- `client_id`/Basic-auth selection depends on env + login-type flags; prod values
  are given above. The `kupferwerk-client-nwot` credentials apply to non-prod /
  non-code-grant paths.
- `market` query param source is the selected UI market (`R(market)` caller);
  its exact value set comes from `LocalizationConfigDto.markets[].marketCode`.
