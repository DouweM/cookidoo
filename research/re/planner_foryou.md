# Cookidoo Android (v26.6.19) — HTTP API contract: Meal Planner + For You

Reverse-engineered from jadx output at `decompiled/base/sources`.

## Key mechanics

- **Transport:** Retrofit 2 + RxJava 3, **not** Ktor for these features. (Ktor exists elsewhere in the app.)
  - Return-type wrappers (deobfuscated): `a_plugin.eyg` = `io.reactivex.rxjava3.core.Single`; `a_plugin.sv1` = `Completable`; `a_plugin.uif` = `retrofit2.Response<T>`.
- **JSON:** Moshi. Field keys come from `@a_plugin.nz8(name = "...")` (Moshi's `@Json`), *not* kotlinx `@SerialName`. All DTOs are `@Keep` data classes.
- **Retrofit annotations (deobfuscated by signature):**
  - `@fu7` = `@GET` · `@lnc` = `@POST` · `@xx3` = `@DELETE` (all three: `String value() default ""`)
  - `@r68` = `@Headers` (`String[] value()`, `boolean allowUnsafeNonAsciiValues`)
  - `@cyi` = `@Url` · `@vv0` = `@Body`
- **HAL / URL resolution:** Endpoints are **not hard-coded paths**. Every call passes a full URL via `@Url`, obtained by resolving a HAL link-relation from the SCS "home" document (`ScsHomeDto` → `_links`). Links are `{ "href": String, "templated": Boolean }` (`com/vorwerk/datacomponents/android/network/home/LinkDto.java`). Templates are expanded by `a_plugin.sn9.b(link, paramsMap, encode, ...)`.
- Host is `https://cookidoo.{tld}` and hrefs are expected to embed `{language}` (e.g. `planning/{language}/api/my-week`), consistent with the known web paths — the concrete template text is server-supplied in the home doc and not a literal in the APK.

---

# Part 1 — Meal Planner (my-week / my-day)

Retrofit API interface: `a_plugin/p0d.java`. Repository (URL building + RxJava orchestration): `a_plugin/t5d.java`. DTO↔domain mapper: `a_plugin/z1d.java`, `a_plugin/a2d.java`. UI: `com/cookidoo/android/planner/**` and `com/cookidoo/android/myweek/**` (Compose; drives the same domain repo).

HAL link relations (from `com/cookidoo/android/foundation/data/home/planning/PlanningHomeLinksDto.java`):

| Field | `@Json` rel name | Used for |
|---|---|---|
| `self` | `self` | — |
| `planningApiMyWeek` | `planning:api-my-week` | GET week |
| `planningMyDay` | `planning:api-my-day` | POST add / DELETE remove |

All three planner calls send header: `Accept: application/vnd.vorwerk.planning.my-day.mobile+json`.

## 1.1 GET week (recipes planned for a day)

- **Interface:** `p0d.a(@Url String url)` → `Single<MyDaysDto>` (`@GET`)
- **URL:** `resolve(planning:api-my-week) + "/" + {dayKey}` — built in `t5d` (~line 203-205). `{dayKey}` is a formatted date string (`yyyy-...`, produced by the `dateKeyMapper`). The repo iterates each date of the visible week and issues one GET per day, aggregating results.
- **Web path (known/consistent):** `planning/{language}/api/my-week/{day}`
- **Headers:** `Accept: application/vnd.vorwerk.planning.my-day.mobile+json`
- **Response:** `MyDaysDto`

## 1.2 POST add recipe(s) to a day

- **Interface:** `p0d.c(@Url String url, @Body AddRecipeRequestDto body)` → `Single<MyDayContent>` (`@POST`)
- **URL:** `resolve(planning:api-my-day)` (no suffix) — `t5d` ~line 140.
- **Web path (known):** `planning/{language}/api/my-day`
- **Headers:** `Accept: application/vnd.vorwerk.planning.my-day.mobile+json`
- **Request body:** `AddRecipeRequestDto { dayKey, recipeIds:[recipeId], recipeSource }` (single recipe wrapped in a list at the call site).
- **Response:** `MyDayContent` (wrapper around `MyDayDto`).

## 1.3 DELETE recipe from a day

- **Interface:** `p0d.b(@Url String url)` → `Completable` (`@DELETE`)
- **URL:** `resolve(planning:api-my-day) + "/" + {dayKey} + "/recipes/" + {recipeId}` and, **iff** a recipeSource is present, append query `?recipeSource={recipeSource}` (`t5d` ~line 355-360, `String.format("recipeSource=%s", …)`).
- **Web path (known):** `planning/{language}/api/my-day/{day}/recipes/{recipe}[?recipeSource=CUSTOMER]`
- **Headers:** `Accept: application/vnd.vorwerk.planning.my-day.mobile+json`
- **Response:** empty (Completable).

## 1.4 `recipeSource` enum

- Only the literal **`"CUSTOMER"`** exists in the planner path (custom/user recipes). It is DI-injected via Koin qualifier `"customer recipe recipe source value"` → returns `"CUSTOMER"` (`a_plugin/k50.java` ~line 1545; wired in `PlannerModuleKt.java:753` into mapper `z1d`).
- Standard Thermomix recipes carry **no `recipeSource`** (field/query omitted → `null`). The `?recipeSource=...` query is only appended when non-null.
- There is **no `TM_RECIPE` literal** in this module. (A separate, unrelated MyGoals plugin enum `UseCaseRecipeSource` = `{CUSTOMER, VORWERK}` exists at `com/vorwerk/mobile/plugin/mg/mygoals/domain/recipeplanning/models/UseCaseRecipeSource.java` — different feature, likely different endpoint.)

## 1.5 Planner DTOs (all Moshi `@Json` keys)

```
MyDaysDto                       // com/cookidoo/android/planner/data/MyDaysDto.java
  myDays: List<MyDayDto>?       // "myDays"

MyDayContent                    // MyDayContent.java  (POST response wrapper)
  content: MyDayDto?            // "content"

MyDayDto                        // MyDayDto.java
  author: String?              // "author"
  created: Date?               // "created"  (Moshi Date adapter)
  dayKey: String?              // "dayKey"
  id: String?                  // "id"
  recipes: List<RecipeTailDto>?// "recipes"
  customerRecipeIds: List<String>? // "customerRecipeIds"
  title: String?              // "title"

RecipeTailDto                   // RecipeTailDto.java
  assets: AssetDto?            // "assets"
  id: String?                 // "id"
  title: String?              // "title"
  totalTime: Long?            // "totalTime" (seconds)

AssetDto                        // AssetDto.java
  images: ImageDto?            // "images"

ImageDto                        // planner/data/ImageDto.java
  square: String?             // "square"
  portrait: String?           // "portrait"
  landscape: String?          // "landscape"

AddRecipeRequestDto             // AddRecipeRequestDto.java  (POST request body)
  dayKey: String?             // "dayKey"
  recipeIds: List<String>?    // "recipeIds"
  recipeSource: String?       // "recipeSource"  (only "CUSTOMER" or absent)
```

Note the calendar day DTO carries **both** structured `recipes[]` (TM recipes, with assets/title/time) **and** a separate `customerRecipeIds[]` (IDs only; custom recipes are resolved/hydrated separately by the repo — `t5d` "loadCustomerRecipesAsPlannedRecipesWrapper").

---

# Part 2 — "For You" personalized home feed

Retrofit API interface: `a_plugin/p4f.java`. Repositories: `a_plugin/g1f.java` (stripe position), `a_plugin/x97.java` (For You stripes + Persy), `a_plugin/nxg.java` (SimRec). UI: `com/cookidoo/android/foryou/**` and `com/cookidoo/android/foundation/presentation/foryou/ForYouPersySyncWorker.java`.

HAL link relations (from `com/cookidoo/android/foundation/data/home/foryou/RecommendationHomeLinksDto.java`):

| Field | `@Json` rel name | Endpoint |
|---|---|---|
| `self` | `self` | — |
| `recommenderStripePosition` | `recommender:stripe_position` | 2.1 |
| `forYouRecommendation` | `recommender:mobile_foryou` | 2.2 |
| `persy` | `recommender:persy` | 2.3 |
| `mobileSimRec` | `recommender:mobile_simrec` | 2.4 |

All four are `@GET @Url`. Methods 2.1–2.3 additionally send `Content-Type: application/x-www-form-urlencoded; charset=utf-8` (an odd header on a body-less GET, but that's what the interface declares). No explicit `Accept` header on these (relies on client default).

## 2.1 Stripe-position recommendations

- **Interface:** `p4f.c(@Url String) ` → `Single<Response<RecommendationsForStripePositionDto>>`
- **URL:** resolve `recommender:stripe_position`, expanding template var **`stripePosition`** (default `0`) — `g1f.java` ~line 85: `sn9.b(link, mapOf("stripePosition" to 0), …)`.
- **Response:** `RecommendationsForStripePositionDto`.

## 2.2 For You recommendation stripes (main feed)

- **Interface:** `p4f.b(@Url String)` → `Single<Response<ForYouRecommendationStripesDto>>`
- **URL:** resolve `recommender:mobile_foryou` (no template params) — `x97.java` ~line 94.
- **Gating:** skipped when a "For You Portal enabled" feature flag (`forYouPortalEnabledUseCase`) is true.
- **Response:** `ForYouRecommendationStripesDto` — the carousel/stripe feed.

## 2.3 Persy (personalization segments)

- **Interface:** `p4f.d(@Url String)` → `Single<PersyDto>`
- **URL:** resolve `recommender:persy` — `x97.java` ~line 145.
- **Behaviour:** response mapped and persisted to a local Realm DB (`SegmentDb`, `PersyDbDataSource`); refreshed by `ForYouPersySyncWorker`. Segments/cohorts feed downstream personalization.
- **Response:** `PersyDto`.

## 2.4 SimRec (similar-recipe recommendations)

- **Interface:** `p4f.a(@Url String)` → `Single<Response<List<SimRecDto>>>`
- **URL:** resolve `recommender:mobile_simrec` — `nxg.java` ~line 77.
- **Response:** `List<SimRecDto>` (`SimRecDto` lives in `com/cookidoo/android/foundation/data/home/recipe/` — not fully expanded here; out of the tile-feed core but wired through the same API).

## 2.5 For You DTOs (Moshi `@Json` keys)

```
ForYouRecommendationStripesDto  // foundation/data/home/foryou/ForYouRecommendationStripesDto.java
  consent: Boolean             // "consent"   (personalization consent flag)
  stripes: List<ForYouStripeDto>? // "stripes"

ForYouStripeDto                 // ForYouStripeDto.java  (one carousel/row)
  stripeTopic: String?         // "stripeTopic"
  stripeTitle: String?         // "stripeTitle"
  stripePosition: Int          // "stripePosition"
  recipes: List<ForYouRecommendationDto>? // "recipes"

ForYouRecommendationDto         // ForYouRecommendationDto.java  (one tile)
  id: String?                  // "id"
  title: String?               // "title"
  images: List<ImageDto>?      // "descriptiveAssets"   ← key differs from field name
  averageRating: Float         // "averageRating"
  numRating: Int               // "numRating"
  totalTime: Int               // "totalTime"

ImageDto                        // foundation/data/home/foryou/ImageDto.java
  square: String?              // "square"   (only a square asset URL)

RecommendationsForStripePositionDto // foundation/data/recommender/RecommendationsForStripePositionDto.java
  recommendations: List<RecommendationDto>? // "data"   ← wrapped under "data"

RecommendationDto               // foundation/data/recommender/RecommendationDto.java
  id: String?                  // "id"
  title: String?               // "title"
  images: List<ImageDto>?      // "descriptiveAssets"
  // (recommender/ImageDto: square: String? — "square")

PersyDto                        // foundation/data/home/foryou/PersyDto.java
  segments: List<SegmentDto>?  // "segments"

SegmentDto                      // foundation/data/home/foryou/SegmentDto.java
  cluster: String?             // "cluster"
  cohorts: List<String>?       // "cohorts"

RecommendationNotificationStatusDto // foundation/data/recommender/RecommendationNotificationStatusDto.java
  seenRecipeIds: List<String>? // "seenRecipeIds"  (field key not @Json-annotated in output; likely same)
```

### Contentful / ctfassets.net
No `ctfassets.net` or Contentful asset references were found in the planner or For You data models. The feed is purely recommender-driven (recipe tiles by id/title/image/rating/time); image URLs are plain CDN strings under `descriptiveAssets`/`square`. Editorial-module/Contentful content, if present in the app, is not wired through these For You DTOs.

---

## Uncertainties / notes

- HTTP verb mapping (`@fu7`/`@lnc`/`@xx3` → GET/POST/DELETE) is inferred from Retrofit annotation *shape* + call semantics (returns/body/naming). The obfuscated annotation classes retain no Retrofit strings, but the mapping is unambiguous given usage (list-fetch=GET, has-@Body=POST, remove/Completable=DELETE).
- Concrete href templates (with `{language}`, exact `my-week`/`my-day` spelling) are **server-supplied** via the home document, not literals in the APK. The web paths cited match the app's URL construction (`+ "/" + dayKey + "/recipes/" + recipeId`, `?recipeSource=`) and are marked "known/consistent".
- The `Content-Type: x-www-form-urlencoded` header on the body-less For You GETs is copied verbatim from `p4f.java` — appears to be a server quirk/legacy header.
- `SimRecDto` internals not expanded (peripheral to the tile feed; `com/cookidoo/android/foundation/data/home/recipe/SimRecDto.java` if needed).
