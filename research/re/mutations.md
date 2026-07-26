# Cookidoo Android — Mutating Endpoint Contracts (reverse-engineered)

Source: decompiled Retrofit+Moshi app at `decompiled/base/sources`.
All URLs are passed as full HAL-link URLs via `@cyi` (= Retrofit `@Url`). `@vv0` = `@Body`, `@g4e` = `@Query`, `@r68` = `@Headers`.

## Alias → HTTP verb table (DEFINITIVE, not inferred)

Determined from the obfuscated Retrofit `RequestFactory` parser at `a_plugin/nff.java` (lines 123-151), which does `instanceof` on each alias and calls `d("<VERB>", value, hasBody)`:

| Alias | Retrofit annotation | HTTP verb | Has body |
|-------|--------------------|-----------|----------|
| `@fu7` | `@GET`     | GET     | no  |
| `@knc` | `@POST`    | POST    | yes |
| `@lnc` | `@PUT`     | PUT     | yes |
| `@jnc` | `@PATCH`   | PATCH   | yes |
| `@xx3` | `@DELETE`  | DELETE  | no  |
| `@s38` | `@HEAD`    | HEAD    | no  |
| `@dyb` | `@OPTIONS` | OPTIONS | no  |
| `@t38` | `@HTTP`    | (method= attr; used for DELETE-with-body) | per `hasBody` |
| `@vv0` | `@Body`    | — | — |
| `@cyi` | `@Url`     | — | — |
| `@g4e` | `@Query`   | — | — |
| `@r68` | `@Headers` | — | — |

This is exact evidence (the parser's own string literals), so verbs below are FACTS, not inferences. They also match the miaucl/cookidoo-api web reference (PUT add-to-collection/calendar, POST shopping mutations + custom-list create, DELETE removals).

## Endpoint table

| Endpoint | Verb | Body JSON (exact keys / types) | Query | Interface method | Source |
|----------|------|-------------------------------|-------|------------------|--------|
| Planner: add recipe(s) to a day | PUT | `{"dayKey": String?, "recipeIds": [String]?, "recipeSource": String?}` | — | `p0d.c` | a_plugin/p0d.java; com/cookidoo/android/planner/data/AddRecipeRequestDto.java |
| Planner: remove recipe from day | DELETE | (none — URL only) | none on method | `p0d.b` | a_plugin/p0d.java |
| Planner: get my-days | GET | — | — | `p0d.a` | a_plugin/p0d.java |
| Shopping: add recipe ingredients | POST | `{"recipeIDs": [String]}` | — | `bqg.i` | a_plugin/bqg.java; shoppinglist/data/AddRecipeRequestDto.java |
| Shopping: add recipe w/ source | POST | `{"recipeIDs": [{"id": String, "source": String}]}` | — | `bqg.f` | shoppinglist/data/AddRecipeWithSourceRequestDto.java + RecipeWithSourceItemDto.java |
| Shopping: remove recipe(s) | POST | `{"recipeIDs": [String]}` | — | `bqg.g` | shoppinglist/data/RemoveRecipeInstancesRequestDto.java |
| Shopping: add additional items (v2) | POST | `{"itemsValue": [String]}` | — | `bqg.k` | shoppinglist/data/AddAdditionalItemDto.java |
| Shopping: edit additional items | POST | `{"additionalItems": [{"id": String, "name": String}]}` | — | `bqg.a` | shoppinglist/data/EditAdditionalItemsDto.java + EditAdditionalItemDto.java |
| Shopping: remove additional items | POST | `{"additionalItemIDs": [String]}` | — | `bqg.c` | shoppinglist/data/RemoveAdditionalItemsRequestDto.java |
| Shopping: edit ingredients ownership | POST | `{"ingredients": [{"id": String, "isOwned": bool, "ownedTimestamp": Long?}]}` | — | `bqg.b` | shoppinglist/data/SetIngredientsIsOwnedStateRequestDto.java + ItemOwnershipDto.java |
| Shopping: edit additional-items ownership | POST | `{"additionalItems": [{"id": String, "isOwned": bool, "ownedTimestamp": Long?}]}` | — | `bqg.j` | shoppinglist/data/SetAdditionalItemsIsOwnedStateRequestDto.java + ItemOwnershipDto.java |
| Shopping: clear/delete list | DELETE | (none — URL only) | — | `bqg.h` | a_plugin/bqg.java |
| Shopping: get list | GET | — | — | `bqg.d` | a_plugin/bqg.java |
| Shopping: get list (text) | GET | — | `groupBy` (String) | `bqg.e` | a_plugin/bqg.java |
| Collections: create custom-list | POST | `{"title": String?, "customlistId": String?, "recipeIds": [String]?}` | — | `p6b.l` | a_plugin/p6b.java; myrecipes/data/models/CustomListRequestDto.java |
| Collections: add recipes to custom-list | PUT | `{"title": String?, "customlistId": String?, "recipeIds": [String]?}` (same DTO) | — | `p6b.g` | a_plugin/p6b.java; CustomListRequestDto.java |
| Collections: delete custom-list | DELETE | (none — URL only) | — | `p6b.e` / `p6b.h` | a_plugin/p6b.java |
| Collections: delete managed-list | DELETE | (none — URL only) | — | `p6b.c` | a_plugin/p6b.java |
| Collections: add bookmark | PUT | `{"recipeId": String}` | — | `p6b.i` | myrecipes/data/models/BookmarkRequestDto.java |
| Collections: remove bookmark | DELETE (with body) | `{"recipeId": String}` | — | `p6b.m` (`@t38 method="DELETE" hasBody=true`) | a_plugin/p6b.java; BookmarkRequestDto.java |
| Custom recipes: create | POST | `{"recipeName": String}` | — | `mt3.p` | customerrecipes/data/CustomerRecipeCreateRequestDto.java |
| Custom recipes: import from URL | POST | `{"recipeUrl": String}` | — | `mt3.n` | customerrecipes/data/CustomerRecipeImportRequestDto.java |
| Custom recipes: add to Cookidoo | POST | `{"recipeUrl": String, "partnerId": String}` | — | `mt3.o` | customerrecipes/data/CustomerRecipeAddToCookidooRequestDto.java |
| Custom recipes: update work-status | PATCH | UpdateCreatedRecipeWorkStatusRequestDto | — | `mt3.l` | a_plugin/mt3.java |
| Custom recipes: image upload meta | PATCH | CustomerRecipeImageUploadRequestDto | — | `mt3.m` | a_plugin/mt3.java |
| Custom recipes: image signature | POST | PictureSignatureDto | — | `mt3.a` | a_plugin/mt3.java |
| Custom recipes: delete | DELETE | (none — URL only) | — | `mt3.j` | a_plugin/mt3.java |
| Custom recipes: get import options | GET | — | `cookidooRecipeId` (String) | `mt3.q` | a_plugin/mt3.java |
| Rating: set user rating | PUT | `{"rating": int}` | — | `xzi.b` | a_plugin/xzi.java; recipe/data/UserRecipeRatingDto.java |
| Rating: get user rating | GET | — | — | `xzi.a` | a_plugin/xzi.java |
| Recipe notes: create note | POST | `{"recipeId": String, "text": String}` | — | `kye.d` | a_plugin/kye.java; recipe/data/NoteDto.java |
| Recipe notes: update note | PUT | `{"text": String}` | — | `kye.c` | a_plugin/kye.java; recipe/data/UpdateNoteDto.java |
| Recipe notes: delete note | DELETE | (none — URL only) | — | `kye.b` | a_plugin/kye.java |
| Recipe notes: get note(s) | GET | — | — | `kye.a` | a_plugin/kye.java |
| Assistant/Copilot: chat | N/A — WebView, no native REST | — | — | — | see note below |

### Notes / caveats
- Planner add uses PUT (`@lnc`) — matches web reference "add to calendar/my-day". `recipeSource` is nullable; JSON key exactly `recipeSource`.
- Planner remove is a plain DELETE on a HAL-templated URL (no `@Query`/`@Body` on the method). Any `recipeSource` filter is baked into the URL upstream; the app stores `recipeSource` locally (PlannerRecipeDb) but does not send it as a method-level query param.
- Note the shopping `recipeIDs` / `additionalItemIDs` casing (capital `ID`), vs planner `recipeIds` and collections `recipeIds` (lowercase `d`). Custom-list DTO key is `customlistId` (lowercase L, no camel hump) — verified exact.
- Bookmark add = PUT; bookmark remove = DELETE-with-body via Retrofit `@HTTP(method="DELETE", hasBody=true)`.
- Custom-recipe create body key is `recipeName` (not `name`); import body key is `recipeUrl`.
- Assistant/Copilot "chat" is NOT a native Retrofit endpoint. It is a hosted WebView launched via intent `ACTION_START_COOKIDOO_ASSISTANT_WEB_VIEW` with HAL rel `copilot.assistant:chat` (a_plugin/p97.java:205; AssistantHomeLinksDto exposes `self` + `assistant:chat` link only; CookidooAssistantWebViewFragment). No request DTO exists — an SDK cannot call it as REST.
