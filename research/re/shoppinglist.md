# Cookidoo Android — Shopping List subsystem HTTP API contract

Reverse-engineered from jadx output of Cookidoo Android v26.6.19.
Source root: `decompiled/base/sources`
Package under study: `com/cookidoo/android/shoppinglist/**` plus the obfuscated
data/network helpers in `a_plugin/`.

Stack note: despite the Kotlin/Ktor framing, the shopping-list network layer is
**Retrofit** (RxJava return types). The Retrofit annotation classes are
obfuscated but were decoded from the request-factory parser
`a_plugin/nff.java` (lines 123–158):

| Obfuscated | Retrofit meaning |
|---|---|
| `@fu7` | `@GET` |
| `@knc` | `@POST` |
| `@xx3` | `@DELETE` |
| `@jnc` | `@PATCH` |
| `@lnc` | `@PUT` |
| `@r68` | `@Headers` |
| `@cyi` | `@Url` (full URL passed at call time) |
| `@vv0` | `@Body` |
| `@g4e` | `@Query` |

RxJava return types: `eyg<T>` = `Single<T>`, `sv1` = `Completable`.

## HAL-driven dispatch (no hard-coded paths)

There are **no literal path templates** in the shopping-list module. Every call
takes a full `@Url` string obtained by expanding a HAL link from the global
**home document**. The link container is
`com/cookidoo/android/foundation/data/home/shoppinglist/ShoppingListHomeLinksDto.java`
(extends `ScsDto`, i.e. read from the home doc `_links`). Link relations
(constructor, verified against field assignments):

| HAL link relation (`_links` key) | DTO getter | Used for |
|---|---|---|
| `pantry:home` | `getShoppingListHome()` | GET list / grouped list / clear (DELETE) |
| `pantry:recipe-ingredients` | `getShoppingListAddRecipes()` | add recipe(s) |
| `pantry:add-additional-items-v2` | `getAddAdditionalItems()` | add additional items |
| `pantry:edit-additional-items` | `getEditAdditionalItems()` | rename additional items |
| `pantry:remove-additional-items` | `getRemoveAdditionalItems()` | remove additional items |
| `pantry:edit-ingredients-ownership` | `getSetIngredientsIsOwnedState()` | ingredient owned state |
| `pantry:edit-additional-items-ownership` | `getSetAdditionalItemsIsOwnedState()` | additional-item owned state |
| `pantry:remove-recipe` | `getRemoveRecipe()` | remove recipe instances |

Links are `LinkDto { href: String, templated: Boolean }`
(`com/vorwerk/datacomponents/android/network/home/LinkDto.java`), expanded as a
URI template via `a_plugin/sn9.b(...)` → `oxi.e(href, vars)` (RFC 6570 expand).
Web reference paths (e.g. `shopping/{language}`, `.../recipes/add`,
`.../additional-items/{add,edit,remove}`,
`.../additional-items/ownership/edit`, `.../owned-ingredients/ownership/edit`)
correspond to the hrefs the server ships under these relations — the app never
hard-codes them.

Retrofit interface: `a_plugin/bqg.java`. Call-site wiring (which link feeds
which method): `a_plugin/ivg.java` (implements `gvg`; the Retrofit service is
field `c`).

Headers: the interface declares almost no headers. Only the grouped-list GET
sets `Accept: text/plain`. The `application/vnd.vorwerk.*+json` Accept/Content-Type
media types seen on web were **not found** in the shopping module — they are
presumably injected by a global OkHttp interceptor / converter (not located in
this subsystem). Marked UNCERTAIN.

---

## Endpoints

All URLs are the expanded HAL href. Method letter = `bqg.java` member.

### 1. Get shopping list — `bqg.d`
- **GET** `{pantry:home}`
- Request body: none
- Response: `ShoppingListDto` (recipes + customerRecipes + additionalItems)
- Call site: `ivg.java:314`

### 2. Get shopping list grouped by category — `bqg.e`
- **GET** `{pantry:home}?groupBy=category`
- Header: `Accept: text/plain`
- Query: `groupBy` (called with literal value `"category"`)
- Response: `String` (raw text/plain, category-grouped/aggregated rendering)
- Call site: `ivg.java:468` — `c.e(home, "category")`
- This is the shopping category / sorting / aggregation endpoint.

### 3. Clear shopping list — `bqg.h`
- **DELETE** `{pantry:home}`
- Request body: none
- Response: `Completable` (no content)
- Call site: `ivg.java:235`

### 4. Add recipe(s) by id — `bqg.i`
- **POST** `{pantry:recipe-ingredients}`
- Body: `AddRecipeRequestDto` `{ "recipeIDs": [String] }`
- Response: `AddRecipeResponseDto` `{ "data": [RecipeDto] }`
- Call sites: `ivg.java:129`, `ivg.java:195` (single-recipe add when no source)

### 5. Add recipe(s) with source — `bqg.f`
- **POST** `{pantry:recipe-ingredients}`
- Body: `AddRecipeWithSourceRequestDto`
  `{ "recipeIDs": [ RecipeWithSourceItemDto ] }` where item = `{ "id": String, "source": String }`
- Response: `Completable`
- Call site: `ivg.java:195` (used when a recipe source string is present)

### 6. Remove recipe instances — `bqg.g`
- **POST** `{pantry:remove-recipe}`
- Body: `RemoveRecipeInstancesRequestDto` `{ "recipeIDs": [String] }`
  (the ids here are recipe **instance** ids / ulids)
- Response: `Completable`
- Call site: `ivg.java:301`

### 7. Set ingredient ownership (isOwned) — `bqg.b`
- **POST** `{pantry:edit-ingredients-ownership}`
- Body: `SetIngredientsIsOwnedStateRequestDto`
  `{ "ingredients": [ ItemOwnershipDto ] }`
- Response: `Completable`
- Call site: `ivg.java:674`

### 8. Add additional (custom) items — `bqg.k`
- **POST** `{pantry:add-additional-items-v2}`
- Body: `AddAdditionalItemDto` `{ "itemsValue": [String] }` (free-text item names)
- Response: `AddAdditionalItemResponseDto` `{ "data": [AdditionalItemDto] }`
- Call site: `ivg.java:145`

### 9. Edit / rename additional items — `bqg.a`
- **POST** `{pantry:edit-additional-items}`
- Body: `EditAdditionalItemsDto`
  `{ "additionalItems": [ EditAdditionalItemDto ] }` where item = `{ "id": String, "name": String }`
- Response: `Completable`
- Call site: `ivg.java:285`

### 10. Remove additional items — `bqg.c`
- **POST** `{pantry:remove-additional-items}`
- Body: `RemoveAdditionalItemsRequestDto` `{ "additionalItemIDs": [String] }`
- Response: `Completable`
- Call site: `ivg.java:780`

### 11. Set additional-item ownership (isOwned) — `bqg.j`
- **POST** `{pantry:edit-additional-items-ownership}`
- Body: `SetAdditionalItemsIsOwnedStateRequestDto`
  `{ "additionalItems": [ ItemOwnershipDto ] }`
- Response: `Completable`
- Call site: `ivg.java:651`

### Grocery-ordering (adjacent; out of core scope but in this module)

Separate Retrofit interfaces; links from a different home-links DTO
`NorthforkHomeLinksDto` (rel `north-fork:order-ingredients-northfork`).

- **Northfork** — `a_plugin/yqb.java`: **POST** `{north-fork:order-ingredients-northfork}`,
  body `OrderIngredientsWithServiceNorthforkRequestDto`
  `{ "ingredients": [NorthforkIngredientDto] }`, response
  `OrderIngredientsWithServiceNorthforkResponseDto` `{ "url": String }`.
  Call site: `ivg.java:521`.
- **Whisk** — `a_plugin/jhj.java`: **POST** `{@Url}` with a hard-coded header
  `Authorization: Token g7XmLPOi7rF5XI6k7KbZLxcT1YM1iXiLYmWpslLuezdD1wN4PJOb62qTxTp22s2I`,
  body `OrderIngredientsWithServiceWhiskRequestDto`, response
  `OrderIngredientsWithServiceWhiskResponseDto` `{ "landingUrl": String }`.
- Error DTO: `OrderIngredientsErrorResponseDto` `{ "code": String }`.

---

## DTO schemas (all fields; JSON key = `@nz8(name=...)`)

Files under `com/cookidoo/android/shoppinglist/data/` unless noted.

### ShoppingListDto (top-level GET response)
| JSON key | Type |
|---|---|
| `recipes` | `List<RecipeDto>?` |
| `additionalItems` | `List<AdditionalItemDto>?` |
| `customerRecipes` | `List<RecipeDto>?` |

`customerRecipes` = user-created ("customer") recipes; `recipes` = Cookidoo recipes.

### RecipeDto
Field ← JSON key (note the id/ulid split, verified via constructor assignment):
| Field | JSON key | Type |
|---|---|---|
| `recipeId` | `id` | `String?` (the recipe/product id) |
| `title` | `title` | `String?` |
| `id` | `ulid` | `String?` (the shopping-list instance id) |
| `descriptiveAssetsDto` | `descriptiveAssets` | `List<DescriptiveAssetsDto>?` |
| `recipeIngredientGroups` | `recipeIngredientGroups` | `List<RecipeIngredientGroupDto>?` |
| `isCustomerRecipe` | `isCustomerRecipe` | `Boolean?` |

### RecipeIngredientGroupDto (the ingredient item schema)
| JSON key | Type |
|---|---|
| `id` | `String?` |
| `icon` | `String?` |
| `isOwned` | `Boolean?` |
| `quantity` | `QuantityDto?` |
| `unitNotation` | `String?` |
| `ingredientNotation` | `String?` |
| `shoppingCategory_ref` | `String?` (field `shoppingCategoryRef`) |
| `ingredient_ref` | `String?` (field `ingredientRef`) |
| `unit_ref` | `String?` (field `unitRef`) |
| `ownedTimestamp` | `Long?` |
| `optional` | `Boolean?` |

### QuantityDto
| JSON key | Type |
|---|---|
| `to` | `Double?` |
| `from` | `Double?` |
| `value` | `Double?` |

(range quantity `from..to`, or single `value`.)

### DescriptiveAssetsDto
| JSON key | Type |
|---|---|
| `square` | `String?` (image URL) |

### AdditionalItemDto (the additional/custom item schema)
| JSON key | Type |
|---|---|
| `id` | `String?` |
| `name` | `String?` |
| `icon` | `String?` |
| `isOwned` | `Boolean?` |
| `ownedTimestamp` | `Long?` |

### ItemOwnershipDto (ownership-edit element, shared)
| JSON key | Type |
|---|---|
| `id` | `String` |
| `isOwned` | `boolean` (non-null) |
| `ownedTimestamp` | `Long?` |

### Request DTOs
- **AddRecipeRequestDto**: `recipeIDs: List<String>`
- **AddRecipeWithSourceRequestDto**: `recipeIDs: List<RecipeWithSourceItemDto>`
- **RecipeWithSourceItemDto**: `id: String` (→ field `recipeId`), `source: String` (→ `recipeSource`)
- **RemoveRecipeInstancesRequestDto**: `recipeIDs: List<String>` (→ field `ids`)
- **SetIngredientsIsOwnedStateRequestDto**: `ingredients: List<ItemOwnershipDto>`
- **AddAdditionalItemDto**: `itemsValue: List<String>` (→ field `itemValues`)
- **EditAdditionalItemsDto**: `additionalItems: List<EditAdditionalItemDto>` (→ field `items`)
- **EditAdditionalItemDto**: `id: String`, `name: String`
- **RemoveAdditionalItemsRequestDto**: `additionalItemIDs: List<String>` (→ field `additionalItemIds`)
- **SetAdditionalItemsIsOwnedStateRequestDto**: `additionalItems: List<ItemOwnershipDto>`

### Response DTOs
- **AddRecipeResponseDto**: `data: List<RecipeDto>` (→ field `recipeItems`)
- **AddAdditionalItemResponseDto**: `data: List<AdditionalItemDto>` (→ field `additionalItems`)

### Grocery-order DTOs
- **OrderIngredientsWithServiceNorthforkRequestDto**: `ingredients: List<NorthforkIngredientDto>`
- **NorthforkIngredientDto**: `quantity: NorthforkIngredientQuantityDto`, `unitNotation: String`, `ingredientNotation: String`, `preparation: String`
- **NorthforkIngredientQuantityDto**: `value: Double` (→ field `quantity`)
- **OrderIngredientsWithServiceNorthforkResponseDto**: `url: String` (→ `landingUrl`)
- **OrderIngredientsWithServiceWhiskRequestDto**: `country: String`, `items: List<WhiskItemDto>` (→ `whiskItems`), `rawItems: List<String>`, `whiteLabel: String`, `language: String`
- **WhiskItemDto**: `name: String`, `quantity: Double`, `unit: String`
- **OrderIngredientsWithServiceWhiskResponseDto**: `landingUrl: String`
- **OrderIngredientsErrorResponseDto**: `code: String`

---

## Notes / uncertainties
- `@SerialName` here is actually Moshi's `@nz8(name=...)` (== `@Json(name=...)`),
  not kotlinx.serialization — the shopping DTOs are `@Keep` Java-style data
  classes with Moshi codegen, consumed by Retrofit.
- Vendor `application/vnd.vorwerk.*+json` media types are NOT declared in this
  module; assumed applied globally (interceptor). UNCERTAIN — not verified.
- The home document that carries the `pantry:*` links is fetched by the
  foundation/home layer (outside `shoppinglist/**`); its own endpoint/media type
  was not traced here.
- Local persistence mirrors the wire model in
  `com/cookidoo/android/shoppinglist/data/datasource/` (Realm): `ShoppingListDb`,
  `ShoppingListRecipeDb`, `ShoppingListIngredientDb`, `ShoppingListAdditionalItemDb`,
  `ShoppingListQuantityDb` — for offline sync (`presentation/sync/ShoppingListSyncWorker`).
