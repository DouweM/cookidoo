# Cookidoo Android API — Recipe / Search / Explore

Reverse-engineered from decompiled app v26.6.19 (jadx Java output at
`decompiled/base/sources`).

- HTTP stack: **Retrofit** (RxJava return types) + **Moshi** for JSON. Moshi field annotation
  is obfuscated to `@nz8(name = "...")` (= `@Json(name=...)`). Retrofit verb/param annotations are
  obfuscated: `@fu7`=`@GET`, `@knc`≈`@POST`, `@lnc`≈`@PUT`, `@xx3`≈`@DELETE`, `@cyi`=`@Url`,
  `@vv0`=`@Body`, `@r68`=`@Headers`. (GET is certain — the others are inferred from
  create/update/delete semantics; the annotation runtime metadata is stripped, so exact verbs for
  POST/PUT/DELETE are marked *inferred*.)
- **HAL / hypermedia**: almost every call takes a **full URL via `@Url`** (`@cyi String`). Those URLs
  are produced by expanding **RFC 6570 URI templates** taken from a discovery/home document.
  - Discovery doc type: `ScsHomeDto<Links>` with the single field `_links` (`@nz8(name="_links")`),
    whose value is a typed `ScsDto` subclass holding named `LinkDto`s.
    File: `com/vorwerk/datacomponents/android/network/home/ScsHomeDto.java`.
  - `LinkDto` = `{ "href": String, "templated": boolean }`
    (`com/vorwerk/datacomponents/android/network/home/LinkDto.java`).
  - Home docs are fetched with header
    **`Accept: application/vnd.vorwerk.tmde2.rhd.mobile.hal+json, application/hal+json`**
    (e.g. search home iface `a_plugin/z5g.java`).
  - Template expansion helper: `a_plugin/sn9.b(LinkDto, Map values, ...)` →
    `oxi.e(href, values)` (RFC6570 UriTemplate.expand). Nested maps (e.g. `filters`) are passed as
    a value and exploded by the template.
- Base host: `https://cookidoo.{tld}` (per the project brief; the concrete origin comes from the
  home/discovery document, not hard-coded in these modules).
- **Explore** (`com/cookidoo/android/explore/**`) and the **interactive keyword Search UI**
  (`com/cookidoo/android/search/presentation/SearchFragment`) are **WebViews**
  (`extends AbstractWebViewFragment`, load `CookidooWebView`). The rich free-text search with the
  full filter set (difficulty/times/portions/etc.) is rendered by the web frontend, **not** by
  native HTTP calls. Native search endpoints below are used for browse/similar/category card lists.

---

## Recipe endpoints

### 1. Recipe detail
- **Interface**: `a_plugin/qke.java` method `a`
- **Method**: GET (`@fu7`)
- **URL**: `@Url` — expanded from HAL link **`recipe:details`** with template var **`{id}` = recipeId**.
  - Link relation source: `RecipeHomeLinksDto` (`_links`: `self`, `recipe:health-check`,
    `recipe:details`, `recipe-variants`) —
    `com/cookidoo/android/foundation/data/home/recipe/RecipeHomeLinksDto.java`
  - Expansion in repo `a_plugin/fze.java`: `sn9.b(getRecipeDetails(), mapOf("id" -> recipeId))`
- **Required header**: `Accept: application/vnd.vorwerk.recipe.mobile.v1+json`
- **Request body**: none
- **Response DTO**: `RecipeDto` (full schema below)

### 2. Recipe variants (alternative TM versions / scalings)
- **Interface**: `a_plugin/qke.java` method `b`
- **Method**: GET (`@fu7`), no special Accept header
- **URL**: `@Url` — HAL link **`recipe-variants`**, template var **`{clusterId}`**
  (`fze.java`: `sn9.b(getRecipeVariants(), mapOf("clusterId" -> clusterId))`)
- **Response**: `List<RecipeVariantDto>`

### 3. Similar / related / category / "stripe" recipe card lists
- **Interface**: `a_plugin/b5g.java` method `b` — `@fu7 GET`, returns `SearchResultDto`.
- **Repository**: `a_plugin/w6g.java` (impl of `v6g`). All variants expand the search HAL link
  (`search:searchapi` or `search:stripeapi` from `SearchHomeLinksDto`) with top-level params
  `context`, `limit`, `includeRating`, and a nested `filters` map. Observed uses:
  - Category browse (`w6g.a`): `context=recipes`, `limit=<n>`, `filters={languages, categories, exclude, [countries]}`
  - "For you"/publishedAt (`w6g.c`): `context=recipes`, `limit`, `filters={sortby=publishedAt, languages=<device lang>}`
  - Similar-to-recipe (`w6g.b`, uses `search:stripeapi`): `context=recipes`, `limit`, `includeRating=true`, `filters={like=<recipeId>}`
  - By-ids (`w6g.d`): `limit`, `filters={ids=<csv of recipe ids>}`
- **Full known `filters.*` keys**: `languages`, `categories`, `exclude`, `countries`, `sortby`
  (e.g. `publishedAt`), `like`, `ids`. Top-level: `context` (=`recipes`), `limit`, `includeRating`.
- **Response**: `SearchResultDto`

### 4. Search — conversion tracking (Algolia insights)
- **Interface**: `a_plugin/b5g.java` method `a`
- **Method**: POST (`@knc`, *inferred*), header `Content-Type: application/x-www-form-urlencoded; charset=utf-8`
- **URL**: HAL link **`search:insight:converted-object-ids-after-search`**
  (`SearchHomeLinksDto.getConversionTracking`), expanded in `a_plugin/e03.java`
- **Body**: `c03` (conversion tracking DTO — objectIDs/queryID; not in scope module, `a_plugin/c03.java`)

### 5. User recipe rating — read
- **Interface**: `a_plugin/xzi.java` method `a` — `@fu7 GET`
- **URL**: HAL link **`rating:user-rating-recipe`**, template var **`{recipeId}`**
  (repo `a_plugin/aze.java`, helper `h()`: `sn9.b(link, mapOf("recipeId" -> recipeId))`)
- **Response**: `UserRecipeRatingDto` `{ rating: int }`

### 6. User recipe rating — set
- **Interface**: `a_plugin/xzi.java` method `b`
- **Method**: PUT (`@lnc`, *inferred*)
- **URL**: same `rating:user-rating-recipe` link (`{recipeId}`)
- **Body**: `UserRecipeRatingDto` `{ rating: int }`
- **Response**: completable (no body)

### 7. Aggregated recipe rating
- **Interface**: `a_plugin/aj.java` method `a` — `@fu7 GET`
- **URL**: HAL link **`rating:aggregated-rating-recipe`**, template var **`{recipeId}`**
  (`RecipeRatingHomeLinksDto` — `_links`: `self`, `rating:user-rating-recipe`,
  `rating:aggregated-rating-recipe`;
  `com/cookidoo/android/foundation/data/home/reciperating/RecipeRatingHomeLinksDto.java`)
- **Response**: `AggregatedRecipeRatingDto` `{ aggregatedRating: float, numberOfRatings: int }`

### 8. Recipe notes (personal notes on a recipe)
- **Interface**: `a_plugin/kye.java`; repo `a_plugin/nye.java`. Link relation
  **`recipe-notes:recipe-note`** (`RecipeNotesHomeLinksDto` —
  `com/cookidoo/android/foundation/data/home/recipenotes/RecipeNotesHomeLinksDto.java`),
  template var **`{recipeId}`** (except create).
  - `a` GET → `uif<RecipeNoteDto>` (optional/wrapper) — read note for recipe
  - `b` DELETE (`@xx3`, *inferred*) → delete note
  - `c` PUT (`@lnc`, *inferred*) body `UpdateNoteDto{text}` → update note
  - `d` POST (`@knc`, *inferred*) body `NoteDto{recipeId, text}` → create note (link expanded with **no** vars)
- **Response** (c/d): `RecipeNoteDto`

### Guided cooking / cook-now
No dedicated HAL endpoint in the recipe module. Guided cooking is driven **client-side** from the
`RecipeDto.recipeStepGroups[].recipeSteps[]` (`title` + `formattedText`) already returned by the
recipe-detail call. (`RecipeHomeLinksDto` exposes only `self`, `recipe:health-check`,
`recipe:details`, `recipe-variants`.) Cooking-history is a separate `myrecipes` concern
(`a_plugin/p6b.java`, out of scope).

---

## Search endpoints (native) — summary
`search:searchapi`, `search:stripeapi`, `search:home`, and
`search:insight:converted-object-ids-after-search` are the four `SearchHomeLinksDto` relations
(`com/cookidoo/android/foundation/data/home/search/SearchHomeLinksDto.java`). Search-result GETs
return `SearchResultDto`. The results carry Algolia metadata (`objectID`, `queryID`, `indexName`,
`position`) — the Vorwerk search API is an Algolia proxy.

---

## Response DTOs — full field list (`@nz8(name)` = JSON key)

### RecipeDto  (`com/cookidoo/android/recipe/data/RecipeDto.java`) — recipe detail, richest
| JSON key | Type |
|---|---|
| `id` | String |
| `title` | String |
| `times` | List<TimeDto> |
| `servingSize` | ServingSizeDto |
| `variantCluster` | List<VariantClusterDto> (nullable) |
| `recipeUtensils` | List<RecipeUtensilsDto> |
| `difficulty` | String |
| `nutritionGroups` | List<NutritionGroupDto> |
| `recipeIngredientGroups` | List<RecipeIngredientGroupDto> |
| `recipeStepGroups` | List<RecipeStepGroupDto> |
| `descriptiveAssets` | List<DescriptiveAssetsDto> |
| `additionalInformation` | List<AdditionalInformationDto> (nullable) |
| `thermomixVersions` | List<String> |
| `tags` | List<TagDto> |
| `language` | String (nullable) |
| `locale` | String (nullable) |
| `categories` | List<CategoryDto> |
| `inCollections` | List<InCollectionsDto> (nullable) |
| `additionalDevices` | List<String> (nullable) |
| `optionalDevices` | List<String> (nullable) |
| `markets` | List<String> (nullable) |
| `targetCountries` | List<String> (nullable) |
| `ingredients` | List<IngredientDto> (nullable) |
| `carouselAssets` | List<DescriptiveAssetsDto> (nullable) |
| `devicesAndAccessories` | List<DevicesAndAccessoriesDto> (nullable) |
| `deviceAgnosticPreparationTexts` | List<DeviceAgnosticPreparationTextDto> (nullable) |

### TimeDto — `type` String, `quantity` QuantityDto, `comment` String
Time `type` values distinguish preparation vs total/cooking (rendered via Stats domain model `deh`:
preparationTime, cookingTime, servingSize, difficulty).

### QuantityDto — `from` Double?, `to` Double?, `value` Double?
### ServingSizeDto — `quantity` QuantityDto, `unitNotation` String?, `comment` String?

### RecipeIngredientGroupDto — `title` String?, `recipeIngredients` List<RecipeIngredientDto>
### RecipeIngredientDto
| JSON key | Type |
|---|---|
| `icon` | String? |
| `ingredientNotation` | String |
| `ingredient_ref` | String |
| `preparation` | String? |
| `quantity` | QuantityDto |
| `unitNotation` | String? |
| `optional` | boolean |
| `localId` | String |
| `recipeAlternativeIngredient` | RecipeIngredientDto (self-nested, nullable) |
| `shoppingCategory_ref` | String? |

### IngredientDto — `id` String?, `shoppingCategory_ref` String?
### RecipeStepGroupDto — `title` String?, `recipeSteps` List<RecipeStepDto>
### RecipeStepDto — `title` String, `formattedText` String  (guided-cooking step)
### RecipeUtensilsDto — `utensilRef` String?, `utensilNotation` String?
### DeviceAgnosticPreparationTextDto — `text` String, `type` String

### NutritionGroupDto — `name` String, `recipeNutritions` List<RecipeNutritionDto>
### RecipeNutritionDto — `quantity` Float?, `unitNotation` String?, `nutritions` List<NutritionDto>
### NutritionDto — `number` float, `type` String, `unittype` String  (note JSON key `unittype`)

### TagDto — `id` String?, `name` String?
### CategoryDto — `id` String?, `title` String?, `subtitle` String?, `colorCode` String?, `defaultTitle` String?, `defaultSubTitle` String?
### DevicesAndAccessoriesDto — `id` String?, `name` String?, `iconUrl` String?, `notation` String?, `optional` boolean, `type` String?
### AdditionalInformationDto — `content` String?
### DescriptiveAssetsDto (recipe) — `landscape` String
### DescriptiveAssetsInColDto — `square` String
### VariantClusterDto — `uid` String, `clusterType` String, `clusterDefaultId` String
### RecipeVariantDto — `recipe_id` String, `quantity` float, `notation` String, `types` List<String>?

### InCollectionsDto — `id` String?, `title` String?, `recipesCount` RecipesCountDto, `market` String?, `descriptiveAssets` List<DescriptiveAssetsInColDto>?
### RecipesCountDto — `value` int, `text` String

### Ratings / notes
- **UserRecipeRatingDto** — `rating` int
- **AggregatedRecipeRatingDto** — `aggregatedRating` float, `numberOfRatings` int
- **NoteDto** — `recipeId` String, `text` String
- **UpdateNoteDto** — `text` String
- **RecipeNoteDto** — `noteId` String, `userId` String, `recipeId` String, `text` String, `modifiedAt` Date, `createdAt` Date

### Search DTOs (`com/cookidoo/android/search/data/`)
- **SearchResultDto** — `data` List<SearchResultItemDto>
- **SearchResultItemDto**
  | JSON key | Type |
  |---|---|
  | `publishedAt` | Date? |
  | `id` | String? |
  | `title` | String? |
  | `objectID` | String? (Algolia) |
  | `queryID` | String? (Algolia) |
  | `position` | Long? (Algolia) |
  | `indexName` | String? (Algolia) |
  | `totalTime` | Integer? |
  | `rating` | float |
  | `numberOfRatings` | int |
  | `descriptiveAssets` | List<DescriptiveAssetsDto> |
- **DescriptiveAssetsDto (search)** — `square` String

### Home/link DTOs (foundation, referenced above)
- `LinkDto` — `href` String, `templated` boolean
- `ScsHomeDto<Links>` — `_links` Links
- `RecipeHomeLinksDto` — `self`, `recipe:health-check`, `recipe:details`, `recipe-variants` (all LinkDto)
- `RecipeRatingHomeLinksDto` — `self`, `rating:user-rating-recipe`, `rating:aggregated-rating-recipe`
- `RecipeNotesHomeLinksDto` — `recipe-notes:recipe-note`
- `SearchHomeLinksDto` — `search:home`, `search:searchapi`, `search:stripeapi`, `search:insight:converted-object-ids-after-search`

---

## Uncertainties / notes
- HTTP verbs for non-GET methods (POST/PUT/DELETE) are inferred from CRUD semantics; Retrofit verb
  annotations were reduced to empty `@interface` shells by R8, so the runtime `@HTTP(method=...)`
  is not recoverable from source.
- Concrete URI-template strings (query-param spellings) live in the server's home document, not in
  the APK; the app only supplies template **values** (`id`, `clusterId`, `recipeId`, `context`,
  `limit`, `includeRating`, `filters.*`). Param names above are the map keys the client sends.
- Full free-text search with the complete filter set (categories, tags, ingredients,
  excludeIngredients, accessories, difficulty, times, portions, ratings, countries, languages,
  tmv/device, page/pageSize, sort) is handled by the **WebView** frontend, so those exact
  query-parameter names are **not present in native code**. The native `filters.*` keys actually
  observed are: `languages`, `categories`, `exclude`, `countries`, `sortby`, `like`, `ids`
  (plus `context`, `limit`, `includeRating`).
- `uif<RecipeNoteDto>` (notes read) is an Optional/response wrapper type (obfuscated `a_plugin/uif`).
</content>
</invoke>
