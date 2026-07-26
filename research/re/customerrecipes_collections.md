# Cookidoo Android API — Custom Recipes & Collections/Lists

Reverse-engineered from jadx output of Cookidoo Android v26.6.19.
Source root: `decompiled/base/sources`

## Key facts & method

- **Networking stack is Retrofit + RxJava + Moshi** (NOT Ktor, despite the brief).
  Return types: `eyg<T>` = RxJava `Single<T>`, `sv1` = RxJava `Completable`.
- **All endpoints use `@Url` (dynamic full URL)** — obfuscated `@cyi`. The app never
  hardcodes paths; it performs **HAL link discovery** from a root `home` document and
  follows link-rels. Paths below are the link-rel names plus any suffixes the repos append.
- Obfuscated Retrofit annotation → HTTP verb map, decoded from
  `a_plugin/nff.java:123-156`:
  | Obf | Meaning |
  |-----|---------|
  | `@fu7` | `@GET` |
  | `@knc` | `@POST` |
  | `@lnc` | `@PUT` |
  | `@jnc` | `@PATCH` |
  | `@xx3` | `@DELETE` |
  | `@s38` | `@HEAD` |
  | `@t38` | `@HTTP` (custom method, `method=`, `hasBody=`) |
  | `@r68` | `@Headers` |
  | `@cyi` | `@Url` |
  | `@vv0` | `@Body` |
  | `@g4e` | `@Query` |
- JSON keys survive as Moshi `@nz8(name="…")` (equivalent to `@SerialName`). LinkDto uses
  `@nz8`. `Date` fields deserialize via `EmptyStringRfc3339DateJsonAdapter` (RFC-3339).
- **The full custom-recipe editing schema (ingredients, steps, servingSize, per-step times)
  is NOT present in native DTOs.** Creating/editing the recipe body happens in a WebView
  (`customer-recipes:edit-page` link, `CustomerRecipeEditWebViewFragment`). The native REST
  surface only creates a recipe shell (`{recipeName}`) and reads back a thin summary. Grep for
  `servingSize|ingredients|steps` in `com/cookidoo/android/customerrecipes` returns nothing.

---

## HAL link discovery

Root home links: `com/cookidoo/android/foundation/data/home/RootHomeLinksDto.java`
- `tmde2:customer-recipes` → customer-recipes sub-home
- `tmde2:organize` → organize sub-home (custom-list / managed-list / bookmark / cooking-history)

### Customer-recipes sub-home links
`com/cookidoo/android/foundation/data/home/customerrecipes/CustomerRecipesHomeLinksDto.java`
| rel (`@nz8`) | getter | purpose |
|---|---|---|
| `customer-recipes:recipes-list` | `recipesList` | list created recipes |
| `customer-recipes:recipe-create` | `recipeCreate` | create-from-scratch & import-from-url |
| `customer-recipes:recipe-details` | `details` | **templated** with recipe id (GET/DELETE/PATCH) |
| `customer-recipes:edit-page` | `editPage` | **templated**; WebView edit URL |
| `customer-recipes:image-signature` | `imageSignature` | image upload signature |
| `customer-recipes:add-to-cookidoo` | `addToCookidoo` | add external recipe to Cookidoo |
| `customer-recipes:config` | `config` | recipe limits/privileges config |
| `customer-recipes:import-options` | `importOptions` | scalability of a cookidoo recipe |
| `customer-recipes:scale-recipe-page` | `scaleRecipePage` | **templated**; WebView |
| `customer-recipes:mobile-report-recipe` | `reportRecipe` | **templated**; WebView |
| `customer-recipes:mobile-share-recipe` | `shareRecipe` | **templated**; WebView |

### Organize sub-home links
`com/cookidoo/android/foundation/data/home/organize/OrganizeHomeLinksDto.java`
| rel (`@nz8`) | getter | purpose |
|---|---|---|
| `organize:api-custom-list` | `organizeApiCustomList` | user collections (CRUD) |
| `organize:api-managed-list` | `organizeApiManagedList` | managed/system collections |
| `organize:api-bookmark` | `organizeApiBookmark` | saved recipes (bookmarks) |
| `organize:api-cooking-history` | `organizeApiCookingHistory` | cooking history |

The known web paths `created-recipes/{language}/{id}` and
`organize/{language}/api/custom-list` correspond to these link hrefs (the `{language}` /
base host is inside the discovered `href`). Deeplink templates confirm the web path
`/created-recipes/.*/.*` and `/created-recipes/add-to-cookidoo` (`a_plugin/u11.java:16-17`).

`LinkDto` = `{ "href": String, "templated": boolean }`
(`com/vorwerk/datacomponents/android/network/home/LinkDto.java`). Non-templated links
resolved by `sn9.b(link,…)`; templated links expanded with the recipe id by
`rn9.b(link, null, id, …)`.

---

# Custom (created) recipes

Retrofit service: `a_plugin/mt3.java`. Repository (link binding + call sites):
`com/cookidoo/android/customerrecipes/data/a.java`.

### GET — list created recipes
- Method `mt3.k` (`@GET`), rel `customer-recipes:recipes-list` (`a.java:134`)
- Header: `Accept: application/vnd.vorwerk.customer-recipe.full+json`
- Response: `CustomerRecipesCollectionDto` → `{ "items": [ CustomerRecipeResponseDto ] }`
- No pagination params observed for this list.

### POST — create recipe from scratch
- Method `mt3.p` (`@POST`), rel `customer-recipes:recipe-create` (`a.java:105`)
- Header: `Accept: application/vnd.vorwerk.customer-recipe.full+json`
- Body: `CustomerRecipeCreateRequestDto` → `{ "recipeName": String }`
- Response: `CustomerRecipeResponseDto`
- (Full recipe content added afterwards via WebView edit-page.)

### POST — import recipe from URL
- Method `mt3.n` (`@POST`), rel `customer-recipes:recipe-create` (`a.java:309`)
- Header: `Accept: application/vnd.vorwerk.customer-recipe.full+json`
- Body: `CustomerRecipeImportRequestDto` → `{ "recipeUrl": String }`
- Response: `CustomerRecipeResponseDto`

### POST — add external recipe to Cookidoo
- Method `mt3.o` (`@POST`), rel `customer-recipes:add-to-cookidoo` (`a.java:89`)
- Body: `CustomerRecipeAddToCookidooRequestDto` → `{ "recipeUrl": String, "partnerId": String }`
- Response: `CustomerRecipeResponseDto` (no special Accept header)

### DELETE — delete a created recipe
- Method `mt3.j` (`@DELETE`), rel `customer-recipes:recipe-details` **templated with {id}** (`a.java:121`)
- Response: `Completable` (empty)

### PATCH — update image of a created recipe
- Method `mt3.m` (`@PATCH`), rel `customer-recipes:recipe-details` **templated with {id}** (`a.java:98`, `a.java:565`)
- Body: `CustomerRecipeImageUploadRequestDto` → `{ "image": String, "isImageOwnedByUser": Boolean }`
- Response: `Completable`

### PATCH — update work status (publish/draft)
- Method `mt3.l` (`@PATCH`), rel `customer-recipes:recipe-details` **templated with {id}** (`a.java:583`)
- Body: `UpdateCreatedRecipeWorkStatusRequestDto` → `{ "workStatus": String }`
- Response: `Completable`

### POST — image upload signature
- Method `mt3.a` (`@POST`), rel `customer-recipes:image-signature` (`a.java` image flow)
- Body: `PictureSignatureDto` (`{ …, "local", … }` — foundation imageupload pkg)
- Response: `SignatureDto` (foundation imageupload pkg; Cloudinary-style signing)

### GET — import options (scalability)
- Method `mt3.q` (`@GET`), rel `customer-recipes:import-options` (`a.java:325`)
- Query: `?cookidooRecipeId={id}` (`@Query("cookidooRecipeId")`)
- Response: `CookidooRecipeImportOptionsDto` → `{ "scalable": Boolean }`

### GET — created-recipes config
- Method `mt3.r` (`@GET`), rel `customer-recipes:config` (`a.java:225`)
- Response: raw `String` (JSON parsed elsewhere → `CustomerRecipesConfigDto`)

## Custom-recipe DTOs

```
CustomerRecipesCollectionDto            // list wrapper (mt3.k)
  items:        List<CustomerRecipeResponseDto>   @nz8("items")

CustomerRecipeResponseDto
  recipeId:      String                 @nz8("recipeId")
  createdAt:     Date                    @nz8("createdAt")
  recipeContent: CustomerRecipeContentDto @nz8("recipeContent")
  workStatus:    String? (nullable)      @nz8("workStatus")

CustomerRecipeContentDto
  recipeName:       String              @nz8("name")
  descriptiveAssets: List<DescriptiveAssetsDto>? @nz8("descriptiveAssets")
  totalTime:        String?             @nz8("totalTime")

DescriptiveAssetsDto
  square: String?                       @nz8("square")   // image URL

CustomerRecipeCreateRequestDto
  recipeName: String                    @nz8("recipeName")

CustomerRecipeImportRequestDto
  recipeUrl: String                     @nz8("recipeUrl")

CustomerRecipeAddToCookidooRequestDto
  recipeUrl: String                     @nz8("recipeUrl")
  partnerId: String                     @nz8("partnerId")

CustomerRecipeImageUploadRequestDto
  image:             String             @nz8("image")
  isImageOwnedByUser: Boolean?          @nz8("isImageOwnedByUser")

UpdateCreatedRecipeWorkStatusRequestDto
  workStatus: String                    @nz8("workStatus")

CookidooRecipeImportOptionsDto
  scalable: Boolean?                    @nz8("scalable")

// Config (from mt3.r raw String)
CustomerRecipesConfigDto
  recipeLimit:          int             @nz8("recipeLimit")
  recipeLimitThreshold: int             @nz8("recipeLimitThreshold")
  privilegesConfig:     List<CustomerRecipesPrivilegesConfigDto> @nz8("privilegesConfig")

CustomerRecipesPrivilegesConfigDto
  conditions: ConditionsDto             @nz8("conditions")
  privileges: PrivilegesDto             @nz8("privileges")

ConditionsDto
  minRecipes: int                       @nz8("minRecipes")
  maxRecipes: int                       @nz8("maxRecipes")

PrivilegesDto
  recipe: RecipePrivilegesDto           @nz8("recipe")

RecipePrivilegesDto   (all Boolean?, all nullable)
  addToShoppingList  @nz8("addToShoppingList")
  addToMyWeek        @nz8("addToMyWeek")
  addToCookToday     @nz8("addToCookToday")
  create             @nz8("create")
  import             @nz8("import")
  update             @nz8("update")
  delete             @nz8("delete")
```

> `descriptiveAssets`/`totalTime` are the only recipe-content fields modeled natively; the
> mapper `a_plugin/cs3.java` reads `recipeContent.name`, first `descriptiveAssets[].square`,
> `workStatus`, `totalTime`. Ingredients/steps/servingSize live only in the web editor payload.

---

# Collections / Lists

Retrofit service: `a_plugin/p6b.java`.
Repositories: custom lists `a_plugin/ok3.java`, managed lists `a_plugin/ktf.java`,
bookmarks `a_plugin/cw0.java`.
Base URLs from `organize:api-custom-list` / `organize:api-managed-list` /
`organize:api-bookmark` hrefs.

## Custom lists (`organize:api-custom-list`, base = `{customListBase}`)

### GET — list all collections (paged)
- Method `p6b.a` (`@GET`), header `Accept: application/vnd.vorwerk.organize.custom-list.mobile+json`
- URL: `{customListBase}` for page 0; subsequent pages `{customListBase}?page={n}`
  (`ok3.java:475`, `ok3.java:488`). **Only `page` param — no `pageSize`.**
- Response: `MyRecipeResponseDto` (contains `customlists[]`, `page`).

### GET — single collection detail
- Method `p6b.j` (`@GET`), same Accept header
- URL: `{customListBase}/{collectionId}` (`ok3.java:292`)
- Response: `CollectionDto`

### PUT — create a collection
- Method `p6b.l` (`@PUT`), same Accept header
- URL: `{customListBase}`  (`ok3.java:118`)
- Body: `CustomListRequestDto` with only `title` set → `{ "title": String }`
- Response: `CustomListResponseDto` (`.content` = created `CollectionDto`)

### POST — add recipe(s) to a collection
- Method `p6b.g` (`@POST`), same Accept header
- URL: `{customListBase}/{collectionId}` (`ok3.java:79`)
- Body: `CustomListRequestDto` with only `recipeIds` set → `{ "recipeIds": [String] }`
- Response: `CustomListResponseDto`

### POST — rename a collection
- Method `p6b.g` (`@POST`), same Accept header
- URL: `{customListBase}/{collectionId}` (`ok3.java:364`)
- Body: `CustomListRequestDto` with only `title` set → `{ "title": String }`
- Response: `CustomListResponseDto`
- (Same verb+path as add-recipe; server distinguishes by which field is present.)

### DELETE — remove a recipe from a collection
- Method `p6b.e` (`@DELETE`), same Accept header
- URL: `{customListBase}/{collectionId}/recipes/{recipeId}` (`ok3.java:226`)
- Response: `CustomListResponseDto`

### DELETE — delete a collection
- Method `p6b.h` (`@DELETE`), same Accept header
- URL: `{customListBase}/{collectionId}` (`ok3.java:170`)
- Response: `CustomListDeleteResponseDto`

## Managed lists (`organize:api-managed-list`, base = `{managedListBase}`)

### GET — list managed collections (paged)
- Method `p6b.b` (`@GET`), header `Accept: application/vnd.vorwerk.organize.managed-list.mobile+json`
- URL: `{managedListBase}` then `?page={n}` (`ktf.java:222`)
- Response: `MyRecipeResponseDto` (contains `managedlists[]`, `page`).

### GET — managed collection detail
- Method `p6b.d` (`@GET`), same managed Accept header
- URL: `{managedListBase}/{collectionId}` (`ktf.java:73`)
- Response: `CollectionDto`

### DELETE — remove a managed list
- Method `p6b.c` (`@DELETE`), same managed Accept header
- URL: `{managedListBase}/{collectionId}` (`ktf.java:141`)
- Response: `CustomListDeleteResponseDto`

## Bookmarks / saved recipes (`organize:api-bookmark`) — adjacent, in scope of "lists"

- `p6b.f` `@GET` Accept `…organize.bookmark.mobile+json` → `MyRecipeResponseDto` (`bookmarks[]`)
- `p6b.i` `@POST` body `BookmarkRequestDto {recipeId}` → `BookmarkResponseDto` (add bookmark, `cw0.java:81`)
- `p6b.m` `@HTTP(method="DELETE", hasBody=true)` body `BookmarkRequestDto {recipeId}` →
  `BookmarkResponseDto` (remove bookmark, `cw0.java:134`)

## Collection / list DTOs

```
MyRecipeResponseDto           // implements PagingResponse — top-level list response
  customLists:  List<CollectionDto>  @nz8("customlists")
  managedLists: List<CollectionDto>  @nz8("managedlists")
  bookmarks:    List<BookmarkDto>    @nz8("bookmarks")
  page:         PageDto              @nz8("page")

PageDto
  page:          Integer?            @nz8("page")
  totalPages:    Integer?            @nz8("totalPages")
  totalElements: Integer?            @nz8("totalElements")

CollectionDto
  id:       String?                  @nz8("id")
  title:    String?                  @nz8("title")
  version:  Integer?                 @nz8("version")
  created:  Date?                    @nz8("created")
  chapters: List<ChapterDto>?        @nz8("chapters")
  assets:   AssetDto?                @nz8("assets")
  listType: String?                  @nz8("listType")   // "CUSTOMLIST" | "MANAGEDLIST"
  author:   String?                  @nz8("author")
  // NOTE: recipeCount is NOT in this mobile DTO; it's derived by counting
  //       chapters[].recipes. (recipeCount appears only in bundled mock JSON.)

ChapterDto
  title:   String?                   @nz8("title")
  recipes: List<RecipeDto>?          @nz8("recipes")

RecipeDto
  id:        String?                 @nz8("id")
  title:     String?                 @nz8("title")
  assets:    AssetDto?               @nz8("assets")
  type:      String?                 @nz8("type")
  totalTime: String?                 @nz8("totalTime")

AssetDto
  images: ImageDto?                  @nz8("images")

ImageDto
  landscape: String?                 @nz8("landscape")
  square:    String?                 @nz8("square")

BookmarkDto
  created: String?                   @nz8("created")
  recipe:  RecipeDto?                @nz8("recipe")

// --- request / mutation wrappers ---
CustomListRequestDto
  title:     String?                 @nz8("title")
  customListId: String?             @nz8("customlistId")   // NOTE JSON key lowercase-L "customlistId"
  recipeIds: List<String>?           @nz8("recipeIds")

CustomListResponseDto
  code:    String?                   @nz8("code")
  content: CollectionDto?            @nz8("content")
  message: String?                   @nz8("message")

CustomListDeleteResponseDto
  content: Object?                   @nz8("content")

BookmarkRequestDto
  recipeId: String                   @nz8("recipeId")

BookmarkResponseDto
  code:    String?                   @nz8("code")
  content: BookmarkDto?              @nz8("content")
  message: String?                   @nz8("message")
```

### `listType` values
Deserialized/compared as string literals `"CUSTOMLIST"` and `"MANAGEDLIST"`
(`a_plugin/an1.java:37,47`; enum `km1.a.valueOf(listType)` in `a_plugin/ym1.java:25`).
The domain-side list-type enum (`a_plugin/jp9.java`) additionally has CUSTOM, MANAGED,
BOOKMARK, RECENTLY_VIEWED, MY_TIMELINE, SEARCH, CUSTOMER_RECIPES, COOKING_HISTORY — those are
UI groupings, not `listType` wire values.

---

## Uncertainties / notes
- Exact host + `{language}` segment live inside the discovered HAL `href`s; not hardcoded in
  the APK. Web paths given in the brief (`created-recipes/{language}`,
  `organize/{language}/api/custom-list`, `.../custom-list/{id}/recipes/{recipe}`,
  `organize/{language}/api/managed-list`) are **consistent** with the observed URL suffixes.
- **Add-recipe vs. rename** on custom lists are the *same* `POST {base}/{id}`; the server
  branches on whether `recipeIds` or `title` is present in `CustomListRequestDto`.
- `recipeCount` requested in the brief is **not** a field on the mobile `CollectionDto`
  (only in the bundled mock JSON `collections-mock-*.json`); the app computes count from
  `chapters[].recipes`. `imageUrl` per collection likewise is not on `CollectionDto` — images
  come via `assets.images.{square,landscape}` (mock JSON's flat `imageUrl`/`recipeCount`
  reflect an older/full server schema, not the `*.mobile+json` projection the app consumes).
- The complete custom-recipe schema (ingredients, cooking steps, per-step times,
  servingSize/portions) is handled entirely in the WebView editor and is not modeled in the
  native Retrofit/Moshi layer.
- Verb decoding is authoritative (from `a_plugin/nff.java`), not guessed.
```
