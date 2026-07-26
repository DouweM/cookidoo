# Cookidoo Android API — Profile, Account, Subscriptions & Thermomix Remote Monitoring

Reverse-engineered from decompiled app **v26.6.19** (jadx output at
`decompiled/base/sources`).
Stack: Kotlin + **Retrofit/RxJava** (not raw Ktor at this layer) + **Moshi** JSON + **HAL** hypermedia.

> Confidence: paths/rels/media-types/JSON keys are taken from surviving string literals and are
> high-confidence. HTTP verbs are inferred from obfuscated Retrofit annotation shapes (see decode
> table) and are high-confidence. Anything marked "uncertain" is flagged inline.

---

## 0. Transport & conventions

### Obfuscated Retrofit annotation decode table
Derived from usage + `@interface` definitions in `a_plugin/`.

| Obfuscated | Retrofit meaning | Evidence |
|---|---|---|
| `@fu7` | `@GET` | used on read methods with `@Url`, no body (`a_plugin/fu7.java`) |
| `@knc` | `@POST` | used with `@Body` (`a_plugin/knc.java`) |
| `@lnc` | `@PUT` | used with `@Body` on profile update (`a_plugin/lnc.java`, `tu1.b`) |
| `@t38(method=,hasBody=)` | `@HTTP` | `t38(hasBody=true, method="DELETE")` |
| `@cyi String` | `@Url` (dynamic full URL) | every method takes a full URL string |
| `@vv0` | `@Body` | |
| `@r68({...})` | `@Headers({...})` | |
| return `eyg<T>` | RxJava `Single<T>` (`a_plugin/eyg.java`) |
| return `sv1` | RxJava `Completable` (`a_plugin/sv1.java`) |

**All endpoints are `@Url`-driven** — there are no hard-coded path templates on the Retrofit
interfaces. The app is fully **HAL-hypermedia**: it fetches a root/home document, reads
`_links.<rel>.href`, and follows link rels. `LinkDto` supports RFC-6570 templating
(`templated: boolean`); the app expands templates via helper `sn9.b(link, paramsMap, ...)`
(`a_plugin/edf.java` uses this for `nonce`, `deviceId`).

### Base URL
Host is `https://cookidoo.{tld}` (e.g. `https://cookidoo.de`, hard-coded example seen in
`RootHomeLinksDto`/deep-link code). The concrete `homeUrl` is configured/injected and passed to
every interface as the `@Url` argument; from the root home doc everything else is link-following.

### Standard HAL request header
Home-document GETs send:
```
Accept: application/vnd.vorwerk.tmde2.rhd.mobile.hal+json, application/hal+json
```
(literal in `a_plugin/a1f.java`, `xpd.java`, `enc.java`, `lp3.java`, `xu1.java`, `i3e.java`,
`vsb.java`, and many other `*HomeDto` fetchers).

### Home document wrapper DTOs
`com/vorwerk/datacomponents/android/network/home/ScsHomeDto.java`
```
ScsHomeDto<L> {
  @nz8("_links") Links links   // wrapper; links object typed per-service as L (a *HomeLinksDto)
}
```
`ScsDto` (base for every `*HomeLinksDto`) also captures a raw
`HashMap<String, LinkDto> linkMap` of all `_links`.

`LinkDto` (`com/vorwerk/datacomponents/android/network/home/LinkDto.java`):
```
LinkDto {
  @nz8("href")      String  href
  @nz8("templated") boolean templated
}
```

### Root home link rels (`RootHomeLinksDto`)
Top-level HAL entry document. Relevant rels for this scope
(`com/cookidoo/android/foundation/data/home/RootHomeLinksDto.java`):

| rel (`tmde2:*`) | leads to |
|---|---|
| `tmde2:profile` | `ProfileHomeLinksDto` (account: password reset, delete account, legal) |
| `tmde2:community-profile` | `CommunityProfileHomeLinksDto` (public/community profile, avatar) |
| `tmde2:ownership` | `OwnershipHomeLinksDto` (subscriptions, owned recipes) |
| `tmde2:mobile-purchases` | `PurchasesHomeLinksDto` (Google Play product ids + purchase validation) |
| `tmde2:rmi-config` | `RemoteMonitoringHomeLinksDto` (**Thermomix remote monitoring**) |
| `tmde2:customer-devices` | `CustomerDevicesHomeLinksDto` (registered TM versions + accessories) |
| `tmde2:mobile-notification` | `NotificationCenterHomeLinksDto` (notification center) |
| `tmde2:community-integration` | comments |
| `tmde2:auth`, `tmde2:mobile-config`, `tmde2:search`, … | (out of scope) |

---

# PART A — Thermomix Device Remote Monitoring  ⭐ (SDK-gap feature)

## A.1 KEY FINDING — realtime transport is **Firebase Cloud Messaging (FCM) push**, not WS/MQTT/SSE

There is **no WebSocket, MQTT, SSE, or polling** for live cooking state. The connected
Thermomix's cooking status is delivered to the phone as **FCM *data* messages**. The app only
talks HTTP to (a) register/unregister its FCM token with the backend and (b) list registered
devices / hand a recipe over. Live state itself is push-only.

Service: `com/cookidoo/android/remotemonitoring/PushNotificationService.java`
(`extends com.google.firebase.messaging.FirebaseMessagingService`).
- `onMessageReceived` (deobf `p(t message)`) reads `message.getData()` (a `Map<String,String>`)
  and maps it to a `CookingActivity` (`i73` mapper → `qpa` field extractors) and a
  `RemoteMonitoringInfo` (`tcf` mapper), persists to Realm, then schedules WorkManager workers to
  raise/update/dismiss the ongoing "cooking" notification.
- `onNewToken` (`r(String token)`) re-registers the new FCM token with the backend.

### A.1.1 FCM data-message payload schema (the live "cooking activity" push)
All values arrive as **strings** in the FCM `data` map. Keys extracted verbatim from
`a_plugin/qpa.java` (each `message.get("<key>")`):

| FCM data key | Type (parsed) | Notes |
|---|---|---|
| `id` | String | **mandatory** — cooking-activity id (hashed to int id locally) |
| `state` | String enum | **mandatory** — `running` \| `paused` \| `done` \| `acknowledged` \| `stale` |
| `deviceId` | String | source Thermomix device id |
| `recipeType` | String enum | `VorwerkRecipe` \| `CreatedRecipe` |
| `recipeId` | String | |
| `iconId` | String | icon identifier |
| `primaryInfo` | String | e.g. step/primary status line |
| `secondaryInfo` | String | |
| `leadingText` | String | |
| `trailingText` | String | |
| `separator` | String | UI separator between info fields |
| `messageTitle` | String | notification title |
| `messageBody` | String | notification body |
| `messageCriticality` | String enum | `info` \| `warning` \| `error` |
| `messageTint` | String enum | `default` \| `prominent` \| `none` |
| `remainingDuration` | long (as String) | remaining cook time (seconds; used for countdown) |
| `isTimeEstimated` | boolean (as String) | whether `remainingDuration` is an estimate |
| `completedDate` | Date (as String) | when the activity completed |
| `dismissalDate` | Date (as String) | when to auto-dismiss the notification |
| `staleDate` | Date (as String) | when state becomes "stale" if no update |

`state` wire→enum mapping (`a_plugin/c73.java` inner enum `a`, third ctor arg is wire string):
`running`, `paused`, `done`(terminal), `acknowledged`(terminal), `stale`(terminal).
`messageCriticality` (`c73.b`): `info`/`warning`/`error`.
`messageTint` (`c73.c`): `default`/`prominent`/`none`.
`recipeType` (`c73.d`): `VorwerkRecipe`→VORWERK, `CreatedRecipe`→CUSTOMER.

Mandatory-field guard: if `id`, `state`, or a valid `completedDate`-derived time is missing, the
push is dropped ("Missing mandatory values in Notification payload", `qpa.i`).

WorkManager workers driven by these pushes:
- `RemoteMonitoringCookingActivityWorker` — create/update the ongoing notification.
- `RemoteMonitoringStaleStateWorker` — fire at `staleDate`.
- `RemoteMonitoringDismissalWorker` — fire at `dismissalDate` (auto-dismiss).

### A.1.2 `CookingActivityDto` (local Moshi model, mirrors the push payload)
`com/cookidoo/android/remotemonitoring/model/CookingActivityDto.java`.
**No `@nz8` annotations → Moshi JSON keys == Kotlin field names.** Used to (de)serialize the
activity into WorkManager input data (`moshi.adapter(CookingActivityDto).toJson(...)`), not a
network response. Fields:

| field / JSON key | Type |
|---|---|
| `id` | int |
| `cookingActivityId` | String (non-null) |
| `deviceId` | String? |
| `recipeId` | String? |
| `recipeImageUrl` | String? |
| `recipeType` | enum `RecipeTypeDto` {VORWERK, CUSTOMER} |
| `state` | enum `CookingActivityStateDto` {RUNNING, PAUSED, DONE, ACKNOWLEDGED, STALE} (non-null) |
| `icon` | String? |
| `primaryInfo` | String? |
| `secondaryInfo` | String? |
| `leadingInfoText` | String? |
| `trailingInfoText` | String? |
| `separator` | String? |
| `messageTitle` | String? |
| `messageBody` | String? |
| `messageCriticality` | enum `MessageCriticalityDto` {INFO, WARNING, ERROR} |
| `messageTint` | enum `MessageTintDto` {DEFAULT, PROMINENT, NONE} |
| `remainingDuration` | Long? (seconds) |
| `isTimeEstimated` | boolean |
| `completedTimestamp` | Date? |
| `stateReceivedTimestamp` | Date (non-null) |

`RemoteMonitoringInfoDto` (`.../model/RemoteMonitoringInfoDto.java`) is the derived UI/domain model
(adds `infoText`, `endTimestamp`, `staleTimestamp`, `dismissalTimestamp`, non-null
`remainingDuration`/`stateReceivedTimestamp`, `CookingActivityIconUi icon`). Not a wire DTO.

## A.2 Remote-monitoring HTTP endpoints (token registration, device list, recipe handover)

Home links doc: `RemoteMonitoringHomeLinksDto`
(`com/cookidoo/android/foundation/data/home/remotemonitoring/RemoteMonitoringHomeLinksDto.java`),
reached via root rel `tmde2:rmi-config`. Rels:

| rel | field | used for |
|---|---|---|
| `rmi:register-token` | registerToken | POST — register this phone's FCM push token |
| `rmi:unregister` | unregisterToken | DELETE — unregister push token(s) |
| `rmi:devices` | devices | GET — list device ids monitored for this user |
| `rmi:actions` | actions | POST — send an action to a device (recipe handover) |

Retrofit interface `a_plugin/fbf.java`; repository `a_plugin/edf.java`.

### A.2.1 GET — list registered devices  (`rmi:devices`)
- Method: `GET {rmi:devices.href}`  (`fbf.a`, `@fu7`)
- Query params: `nonce=<random>` (template expanded; `edf` passes `MapsKt.mapOf("nonce" -> ...)`)
- Response: `List<DeviceIdDto>` where
  `DeviceIdDto { @nz8("deviceId") String deviceId }`
  (`com/cookidoo/android/foundation/data/remotemonitoring/DeviceIdDto.java`)

### A.2.2 POST — register push token  (`rmi:register-token`)
- Method: `POST {rmi:register-token.href}`  (`fbf.c`, `@knc`)
- **Header (required):** `rmi-api-version: 2026-06-01`  (`@r68` on `fbf.c`)
- Request body `RemoteMonitoringTokenDto`
  (`com/cookidoo/android/foundation/data/remotemonitoring/RemoteMonitoringTokenDto.java`):

  | JSON key | field | value |
  |---|---|---|
  | `token` | pushToken | FCM registration token |
  | `bundleId` | applicationId | app package name |
  | `platform` | platform | **default `"AN"`** (Android; `(i&4)!=0 ? "AN"`) |
  | `mobileAppId` | mobileAppId | stored app-instance identifier |

- Response: `Completable` (204/2xx, no body).

### A.2.3 DELETE — unregister push token(s)  (`rmi:unregister`)
- Method: `DELETE {rmi:unregister.href}` **with body** (`fbf.b`, `@t38(method="DELETE", hasBody=true)`)
- Request body `Tokens`:
  ```
  Tokens   { @nz8("entries") List<TokenDto> entries }   // Tokens.java
  TokenDto { @nz8("token")   String token }             // TokenDto.java
  ```
- Response: `Completable`.

### A.2.4 POST — device action / recipe handover  (`rmi:actions`)
- Method: `POST {rmi:actions.href}` with generic `Object` body (`fbf.d`, `@knc`)
- Query params: `deviceId=<id>` (required), `nonce=<random>` (optional) — built in `edf.z1`:
  `createMapBuilder.put("deviceId", ...); createMapBuilder.put("nonce", ...)`.
- Request body `RecipeHandoverDto`
  (`com/cookidoo/android/foundation/data/remotemonitoring/RecipeHandoverDto.java`):
  ```
  RecipeHandoverDto {
    @nz8("recipeId")   String recipeId
    @nz8("recipeType") String recipeType   // "VorwerkRecipe" | "CreatedRecipe"
  }
  ```
  (This is "send this recipe to the Thermomix". `edf` iterates devices from `rmi:devices` and
  POSTs a handover per device.)
- Response: `Completable`.

## A.3 Registered Thermomix devices & accessories (`customer-devices`)

Home links `CustomerDevicesHomeLinksDto` (root rel `tmde2:customer-devices`):

| rel | field | endpoint |
|---|---|---|
| `customer-devices:thermomix-versions` | customerDevicesThermomixVersions | GET → `List<String>` TM version ids |
| `customer-devices:api-accessories` | apiAccessory | GET → `List<AccessoryDto>` |
| `customer-devices:api-accessory-ids` | myAccessoryIds | GET → `List<String>` accessory ids |

Retrofit interface `a_plugin/kp3.java` (all `@fu7` GET, `@Url`):
- `a(url) : Single<List<AccessoryDto>>`
- `b(url) : Single<List<String>>`
- `c(url) : Single<List<String>>`

`AccessoryDto` (`com/cookidoo/android/foundation/data/home/customerdevices/AccessoryDto.java`):
```
AccessoryDto {
  @nz8("id")               String       id
  @nz8("utensilCatalogUids") List<String> utensilCatalogUids
  @nz8("compatibleDevices") List<String> compatibleDevices   // e.g. TM versions
  @nz8("hasSerialNumber")  Boolean      hasSerialNumber
  @nz8("images")           ImageDto     images
}
ImageDto            { @nz8("icon") IconAndThumbnailDto icon; @nz8("thumbnail") IconAndThumbnailDto thumbnail }
IconAndThumbnailDto { @nz8("1x") String; @nz8("2x") String; @nz8("3x") String }   // density variants
```
Synced by `CustomerDevicesSyncWorker`. Thermomix **versions** endpoint returns a plain
`List<String>` (version identifiers); there is no richer per-device DTO than `DeviceIdDto`
(remote-monitoring) and this version-id list.

## A.4 Notification permission / push plumbing (supporting)
- `com/cookidoo/android/remotemonitoring/b.java` + `a.java` compute a `DeprioritizationLogInfo`
  (areNotificationsEnabled, isNotificationPermissionGranted, isNotificationChannelEnabled) and log
  an event `fcm_message_handling` when FCM deprioritizes a message.
- `foundation/presentation/remotemonitoring/PushTokenSyncWorker` re-syncs the token.
- Notification-center list: `NotificationCenterHomeLinksDto` rel `mobile:notifications` →
  `NotificationCenterItemDto { @nz8("id"), @nz8("image-uri") image, lifespanInSeconds,
  @nz8("link") link, message, title, @nz8("topic") topic }`.

---

# PART B — User Profile & Account

## B.1 Community / public profile  (root rel `tmde2:community-profile`)
Home links `CommunityProfileHomeLinksDto`
(`com/cookidoo/android/foundation/data/home/profile/CommunityProfileHomeLinksDto.java`):

| rel | field | purpose |
|---|---|---|
| `community-profile:user-private-profile` | userPrivateProfile | GET/PUT the profile |
| `community-profile:user-basic-info` | userBasicInfo | basic info |
| `community-profile:picture-signature` | pictureSignature | POST → Cloudinary upload signature |
| `community-profile:avatars-list` | avatarList | GET preset avatars |

Retrofit interface `a_plugin/tu1.java`:
- `c(url) : Single<PrivateProfileResponseDto>`  — **GET** private profile (`@fu7`)
- `b(url, PrivateProfileUserInfoDto) : Completable` — **PUT** update profile (`@lnc`)
- `a(url, PictureSignatureDto) : Single<SignatureDto>` — **POST** get image-upload signature (`@knc`)
- `d(url) : Single<List<String>>` — **GET** avatar list (uncertain: list of avatar URLs/ids)

### DTOs (`com/cookidoo/android/profile/data/community/model/`)
```
PrivateProfileResponseDto {
  @nz8("id")       String                    id
  @nz8("isPublic") Boolean                   isPublic
  @nz8("userInfo") PrivateProfileUserInfoDto userInfo
  @nz8("meta")     PrivateProfileMeta        meta
}
PrivateProfileUserInfoDto {   // also the PUT request body
  @nz8("username")    String username
  @nz8("description") String description
  @nz8("picture")     String picture
}
PrivateProfileMeta {
  @nz8("cloudinaryPublicId") String cloudinaryPublicId   // profile image on Cloudinary
}
```
(Profile picture is served via Cloudinary using `cloudinaryPublicId` / `picture`.)

## B.2 Account settings  (root rel `tmde2:profile`)
Home links `ProfileHomeLinksDto`:

| rel | field | purpose |
|---|---|---|
| `profile:password-reset` | resetPassword | trigger password reset |
| `profile:legal-agreement-updates` | legalUpdate | legal/consent updates |
| `profile:api-user` | deleteAccount | DELETE account (delete-account flow) |

(Interface not fully traced; field names come straight from the link-rel DTO. The delete-account
UI lives at `profile/presentation/deleteaccount`, change-password at `.../changepassword`.)

---

# PART C — Subscriptions, Ownership & Purchases

## C.1 Subscriptions & owned recipes  (root rel `tmde2:ownership`)
Home links `OwnershipHomeLinksDto`
(`com/cookidoo/android/foundation/data/home/ownership/OwnershipHomeLinksDto.java`):

| rel | field | endpoint |
|---|---|---|
| `self` | self | |
| `ownership:recipes` | ownershipRecipes | GET → `List<OwnedRecipeIdDto>` |
| `ownership:subscriptionsV2` | ownershipSubscriptions | GET → `List<SubscriptionDto>` |

Retrofit interface `a_plugin/zmc.java` (both `@fu7` GET, `@Url`):
- `a(url) : Single<List<OwnedRecipeIdDto>>`   (owned recipes)
- `b(url) : Single<List<SubscriptionDto>>`    (subscriptions)

### `SubscriptionDto`  (`com/cookidoo/android/foundation/data/ownership/SubscriptionDto.java`)
```
SubscriptionDto {
  @nz8("subscriptionActive")  boolean subscriptionActive     // active flag
  @nz8("autoRenewingActive")  boolean autoRenewingActive     // auto-renew on
  @nz8("endDate")             Date    endDate                // expiry
  @nz8("type")                String  type
  @nz8("status")              String  status
  @nz8("subscriptionSource")  String  source                 // field name "source", key "subscriptionSource"
  @nz8("subscriptionLevel")   String  level                  // field name "level", key "subscriptionLevel"
}
```
> Note: this differs from the older web contract in the task brief. Actual v26.6.19 keys are
> `subscriptionActive`, `autoRenewingActive`, `endDate`, `type`, `status`, `subscriptionSource`,
> `subscriptionLevel` (endpoint rel is `ownership:subscriptionsV2`). No `startDate` / `expires` /
> `extendedType` fields are present in this build — if you need those, they are not in the mobile
> DTO. String enums for `type`/`status`/`subscriptionSource`/`subscriptionLevel` are not
> constrained in the DTO (free strings).

`OwnedRecipeIdDto { @nz8("id") String id }`.

## C.2 In-app purchases (Google Play)  (root rel `tmde2:mobile-purchases`)
Home links `PurchasesHomeLinksDto`:

| rel | field | endpoint |
|---|---|---|
| `google:productIds` | productIds | GET → `List<ProductDto>` |
| `google:purchase-validation` | purchaseValidation | POST purchase for validation |

Retrofit interface `a_plugin/f3e.java`:
- `b(url) : Single<List<ProductDto>>` (`@fu7` GET)
- `a(url, PurchaseDataDto) : Completable` (`@knc` POST — validate a Play purchase)

### DTOs (`com/cookidoo/android/profile/data/purchases/model/`)
```
ProductDto {
  @nz8("productId")     String id
  @nz8("runtimeMonths") int    runtimeMonths
  @nz8("title")         String title
  @nz8("description")   String description
}
PurchaseDataDto {   // POST body for purchase validation
  @nz8("purchaseToken")      String purchaseToken
  @nz8("applicationVersion") String applicationVersion
  @nz8("campaign")           String campaign
  @nz8("productId")          String productId
  @nz8("purchaseTime")       String purchaseTime
}
```

---

## Appendix — key source files
| Concern | File |
|---|---|
| RM Retrofit interface | `a_plugin/fbf.java` |
| RM repository (link-following, token reg, handover) | `a_plugin/edf.java`, DI in `a_plugin/k50.java` |
| RM home links | `.../foundation/data/home/remotemonitoring/RemoteMonitoringHomeLinksDto.java` |
| FCM service | `.../remotemonitoring/PushNotificationService.java` |
| FCM payload field extractors | `a_plugin/qpa.java`; mappers `a_plugin/i73.java`, `a_plugin/tcf.java` |
| Cooking activity model + enums | `.../remotemonitoring/model/CookingActivityDto.java`, `a_plugin/c73.java` |
| RM token / device / handover DTOs | `.../foundation/data/remotemonitoring/{RemoteMonitoringTokenDto,Tokens,TokenDto,DeviceIdDto,RecipeHandoverDto}.java` |
| Customer devices | `a_plugin/kp3.java`, `.../foundation/data/home/customerdevices/*` |
| Community profile | `a_plugin/tu1.java`, `.../profile/data/community/model/*` |
| Subscriptions/ownership | `a_plugin/zmc.java`, `.../foundation/data/ownership/SubscriptionDto.java`, `OwnedRecipeIdDto.java` |
| Purchases | `a_plugin/f3e.java`, `.../profile/data/purchases/model/*` |
| Root home rels | `.../foundation/data/home/RootHomeLinksDto.java` |
| HAL wrappers | `com/vorwerk/datacomponents/android/network/home/{ScsHomeDto,ScsDto,LinkDto}.java` |
