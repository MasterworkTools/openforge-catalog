# Thingiverse API v2 — Reference

Documentation of the Thingiverse API v2, extracted from the official OpenAPI 3.0 spec
served at <https://api.thingiverse.com/v2/doc> (Swagger UI).

- **Spec version:** OpenAPI 3.0.0 (`Thingiverse API v2`)
- **Production base URL:** `https://api.thingiverse.com`
- **Staging base URL:** `https://api-staging.thingiverse.com`
- **Auth:** JWT Bearer token — `Authorization: Bearer <access_token>` (applied globally by default)
- **Surface:** 71 operations across 11 tags, 43 schemas

> ⚠️ This is the **v2** API (JWT-based, the one powering the modern thingiverse.com site).
> It is distinct from the older public v1 REST API that used `?access_token=` app tokens.
> The spec exposes no documented rate-limit headers or quotas.

---

## Authentication

The default security scheme is HTTP Bearer with a JWT. Nearly every endpoint expects:

```
Authorization: Bearer <access_token>
```

### Token flow

| Concept | Where it comes from |
|---|---|
| `access` (JWT) | Short-lived; sent on every request as the Bearer token |
| `refresh` (JWT) | Long-lived; exchanged at `/v2/auth/refresh` for a new access token |
| `token` | Session/login token returned alongside JWTs by login endpoints |

Typical shapes:

- **`JwtTokenResponse`** — `{ access, refresh }`
- **`AuthTokensResponse`** — `{ message, token, jwt: JwtTokenResponse }`
- **`OAuthTokensResponse`** — `{ token, jwt: JwtTokenResponse }`

A `401` response (shape `{ error }`) means the token is missing/invalid on any authenticated route.

### Auth endpoints (`Auth`, 19 operations)

| Method | Path | Summary | Body / Params |
|---|---|---|---|
| POST | `/v2/auth/oauth/access_token` | Exchange OAuth code for tokens | `OAuthLoginRequest` `{client_id, client_secret, code}` |
| POST | `/v2/auth/login` | Username/email + password login | `LoginRequest` `{usernameOrEmail, password}` → `200 AuthTokensResponse`, `202` = 2FA required |
| GET | `/v2/auth/view` | Get a view (read-only) token | → `JwtTokenResponse` |
| POST | `/v2/auth/refresh` | Refresh access token | `RefreshRequest` `{refresh_token}` → `JwtTokenResponse` |
| GET | `/v2/auth/logout` | Logout, clear login cookies | → `302` |
| GET | `/v2/auth/google` | Begin Google OAuth (redirects to Google) | query `redirect_uri` |
| GET | `/v2/auth/google/callback` | Handle Google OAuth callback | query `code` (req) |
| GET | `/v2/auth/token` | Get the current user's login token | — |
| POST | `/v2/auth/signup` | Create a new account | `SignUpRequest` |
| GET | `/v2/auth/{username}/verifyemail` | Send verification email | path `username` |
| POST | `/v2/auth/forgotpassword` | Send password-reset email | `ForgotPasswordRequest` `{email}` |
| POST | `/v2/auth/resetpassword` | Reset password via token | `ResetPasswordRequest` `{token, password}` |
| POST | `/v2/auth/sendcoppaform` | Send COPPA form to caretaker | `SendCoppaFormRequest` `{username, caretakerName, email}` |
| GET | `/v2/auth/recovery/generate` | Generate new 2FA recovery codes | — |
| POST | `/v2/auth/recovery/login` | Login using a recovery code | `LoginRecoveryCodesRequest` `{recoveryCode}` |
| POST | `/v2/auth/2fa/setup` | Start 2FA setup | — |
| POST | `/v2/auth/2fa/setup/complete` | Complete 2FA setup | `Authenticate2FARequest` `{code}` |
| POST | `/v2/auth/2fa/disable` | Disable 2FA | — |
| POST | `/v2/auth/2fa/login` | Complete login with a 2FA code | `Authenticate2FARequest` `{code}` → `AuthTokensResponse` |

---

## Things (`Things`, 6 operations)

A **Thing** is a published design/model. Most read endpoints come in graduated detail
levels — `minimal` < `summary` < `complete` — plus a `custom` variant that returns only
the fields you name via `?fields=`.

| Method | Path | Returns | Notes |
|---|---|---|---|
| GET | `/v2/things/{id}` | `SingleThingResponseSummary` | Alias of `/summary` |
| GET | `/v2/things/{id}/summary` | `SingleThingResponseSummary` | |
| GET | `/v2/things/{id}/complete` | `SingleThingResponseComplete` | Full record incl. tags, license, ancestors, zip data |
| GET | `/v2/things/{id}/custom` | (filtered object) | `fields` query **required** |
| GET | `/v2/things/{id}/more-like-this` | recommendations | |
| GET | `/v2/things/{id}/secure` | — | "Secure a thing's files for download" (prep for downloading) |

Common query params on the read routes: `image_type`, `image_size`.

### `SingleThingResponseComplete` (key fields)

`id`, `name`, `public_url`, `created_at`, `thumbnail`, `preview_image`,
`creator` (`SingleUserResponseMinimal`), `description_html`, `details`, `details_parts`,
`license`, `file_count`, `remix_count`, `make_count`, `like_count`, `comment_count`,
`collect_count`, `is_published`, `is_featured`, `is_edu_approved`, `is_winner`, `is_nsfw`,
`is_ai`, `is_wip`, `is_derivative`, `is_premium`, `is_liked`, `is_collected`, `is_watched`,
`allows_derivatives`, `ancestors` (`[SingleThingResponseSummary]`), `tags` (`[TagDto]`),
`zip_data` (`ZipDataDto`), `default_image` (`ImageDto`), `categories_url`, `type_name`, `rank`.

---

## Files (`Files`, 2 operations)

| Method | Path | Summary | Params / Body |
|---|---|---|---|
| GET | `/v2/files/{id}/download` | Download a thing file | path `id`; query `incrementDownload` (bool), `token` (string) → `200` file (string/binary) |
| POST | `/v2/files/image/upload/{imageType}/{id}` | Upload an image | path `imageType`, `id`; body `multipart/form-data` |

> The `download` route pairs with `GET /v2/things/{id}/secure`, which authorizes the file set
> before downloading. `incrementDownload=true` counts the download toward stats.

---

## Search (`Search`, 6 operations)

All search endpoints are paginated (`page`, `per_page`, default `per_page=20`, `page=1`)
and accept a `term` string. Each domain adds its own filters.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v2/search/` | Global/thing search (same filters as `/search/things`) |
| GET | `/v2/search/things` | Search things (rich filter set) |
| GET | `/v2/search/users` | Search users |
| GET | `/v2/search/makes` | Search makes |
| GET | `/v2/search/collections` | Search collections |
| GET | `/v2/search/autocompletetags` | Tag autocomplete — query `term` (req), `max_suggestions` |

### `/v2/search/things` filters (`ThingsQuery`)

`sort`, `return`, `image_size`, `image_type`, `exclude_thing_id`, `category_id`, `user_id`,
`is_edu_approved`, `grades`, `subjects`, `standards`, `license`, `customizable`,
`show_customized`, `has_makes`, `is_featured`, `is_challenge_winner`, `liked_by`, `made_by`,
`is_derivative`, `is_wip`, `min_likes`, `posted_after`, `fields`, `show_ai`,
plus `term`, `per_page`, `page`.

### `/v2/search/users` filters (`UsersQuery`)

`sort`, `return`, `is_verified`, `is_featured`, `is_exclusive`, `users_user_types`,
`skill_level`, `programs`, `fields`, `term`, `per_page`, `page`.

### Other search filters

- **`MakesQuery`**: `sort`, `user_id`, `term`, `per_page`, `page`
- **`CollectionsQuery`**: `sort`, `user_id`, `is_featured`, `liked_by`, `term`, `per_page`, `page`

---

## Users (`Users`, 16 operations)

Users are addressable by numeric `id` or by `username`, each with the same detail ladder
(`minimal` / `summary` / `complete`) and a `custom` (`?fields=`) variant.

| Method | Path | Returns |
|---|---|---|
| GET | `/v2/users/id/{id}` | `SingleUserResponseSummary` |
| GET | `/v2/users/id/{id}/minimal` | `SingleUserResponseMinimal` |
| GET | `/v2/users/id/{id}/summary` | `SingleUserResponseSummary` |
| GET | `/v2/users/id/{id}/complete` | `SingleUserResponseComplete` |
| GET | `/v2/users/id/{id}/custom` | filtered (`fields` req) |
| GET | `/v2/users/username/{username}` | `SingleUserResponseSummary` |
| GET | `/v2/users/username/{username}/minimal` | `SingleUserResponseMinimal` |
| GET | `/v2/users/username/{username}/summary` | `SingleUserResponseSummary` |
| GET | `/v2/users/username/{username}/complete` | `SingleUserResponseComplete` |
| GET | `/v2/users/username/{username}/custom` | filtered (`fields` req) |
| GET | `/v2/users/me` | `SingleUserResponseComplete` (the authenticated user) |
| GET | `/v2/users/{username}/validate` | Check username availability/validity |
| GET | `/v2/users/industries` | List of industries |
| PATCH | `/v2/users/{id}` | Update user data — body `EditUserRequest` |
| DELETE | `/v2/users/{id}` | Soft-delete a user |
| POST | `/v2/users/{id}/{type}` | Relationship action (e.g. follow) — path `type` |

### `SingleUserResponseComplete` (key fields)

Public: `id`, `name`, `first_name`, `last_name`, `public_url`, `thumbnail`, `cover`, `bio`,
`bio_html`, `location`, `country`, `website`, `twitter`, `membership_level`, `level`,
`skill_level`, `is_featured`, `is_verified`, `is_exclusive`, `is_admin`, `is_moderator`,
`accepts_tips`, `approved_vendor`, `is_following`, counts (`count_of_followers`,
`count_of_following`, `count_of_designs`, `collection_count`, `make_count`, `like_count`,
`favorite_count`), `printers`, `programs`, `types`, `groups`, `default_license`.

Private (only on `me` / self): `email`, `2fa_enabled`, `recovery_codes_created_at`, `stripe_id`.

`EditUserRequest` also carries email-notification toggles and password-change fields
(`current_password`, `new_password`, `confirm_new_password`).

---

## Makes (`Makes`, 6 operations)

A **Make** is a user's build of a Thing (photos + print settings).

| Method | Path | Returns / Body |
|---|---|---|
| GET | `/v2/makes/{id}` | `SingleMakeResponseSummary` |
| GET | `/v2/makes/{id}/summary` | `SingleMakeResponseSummary` |
| GET | `/v2/makes/{id}/complete` | `SingleMakeResponseComplete` |
| POST | `/v2/makes` | Create — `PostMakeRequest` `{thing_id, description?, print_settings?}` |
| PATCH | `/v2/makes/{id}` | Update — `PatchMakeRequest` `{description?, print_settings*}` |
| DELETE | `/v2/makes/{id}` | Delete |

Read routes accept `image_type` and `image_size`. A make embeds its `creator`
(`SingleUserResponseMinimal`) and `thing` (`SingleThingResponseSummary`).

---

## Collections (`Collections`, 3 operations)

| Method | Path | Returns |
|---|---|---|
| GET | `/v2/collections/{id}/summary` | `ThingCollectionResponseSummary` |
| GET | `/v2/collections/{id}/complete` | `ThingCollectionResponseSummary` |
| GET | `/v2/collections/{id}/things` | Paginated things (`page`, `per_page`) |

`ThingCollectionResponseSummary`: `id`, `name`, `created_at`, `creator`, `count`,
`public_url`, `thumbnails[]`, `is_liked`, `is_featured`.

---

## Challenges (`Challenges`, 9 operations)

Design contests. Read routes have the `minimal`/`summary`/`complete` ladder; write routes
appear to be admin-only.

| Method | Path | Returns / Body |
|---|---|---|
| GET | `/v2/challenges/{type}` | `GetChallengesRequest` `{current[], previous[]}` |
| GET | `/v2/challenges/{id}` | `SingleChallengeRequestSummary` |
| GET | `/v2/challenges/{id}/minimal` | `SingleChallengeRequestMinimal` |
| GET | `/v2/challenges/{id}/summary` | `SingleChallengeRequestSummary` |
| GET | `/v2/challenges/{id}/complete` | `SingleChallengeRequestComplete` |
| GET | `/v2/challenges/{id}/custom` | filtered (`fields` req) |
| POST | `/v2/challenges/` | Create — `PostChallengeRequest` |
| PATCH | `/v2/challenges/{id}` | Update — `PostChallengeRequest` → `GenericResponse` |
| POST | `/v2/challenges/{id}/winners` | Set winners — `[PostChallengeWinnersObject]` `{thing_id, place}` |

---

## Membership, Newsletter, Webhook (misc.)

| Tag | Method | Path | Notes |
|---|---|---|---|
| Membership | GET | `/v2/membership/signup` | query `period` (req) → `303` redirect (Stripe checkout) |
| Membership | GET | `/v2/membership/edit` | → `303` redirect (Stripe billing portal) |
| Newsletter | POST | `/v2/newsletter/subscribe` | `SubscribeRequest` `{email}` → `GenericResponse` |
| Webhook | POST | `/v2/webhook/stripe` | Stripe webhook receiver (server-to-server) |

---

## Response detail levels (pattern)

Several resources share a consistent shape convention worth relying on:

- **`minimal`** — id, name, url, thumbnail, a few flags. Cheapest.
- **`summary`** — minimal + core counts/metadata. The default when you hit the bare `/{id}`.
- **`complete`** — everything, including HTML bodies, relationships, and heavier nested data.
- **`custom`** — you pass `?fields=a,b,c` (required) and get back only those. Use this to
  minimize payload when you know exactly what you need.

## Common response shapes

- **Error / 401 / 404 / 400** → `{ error }` or `GenericResponse` `{ message?, error?, code? }`
- **Pagination** → `PaginationQuery` `{ page (default 1), per_page (default 20) }`

---

## OpenForge tooling environment variables

- `THINGIVERSE_TOKEN_FILE` — where `openforge/thingiverse/auth.py` persists the
  access/refresh JWTs (owner-only file permissions). Defaults to
  `~/.config/openforge/thingiverse_tokens.json`. Name documented here only —
  never commit token values.

## Notes for OpenForge integration

- The API is JWT/session-oriented and clearly built for the first-party web app rather than
  third-party app tokens — expect to manage `access`/`refresh` tokens rather than a static
  API key.
- For pulling OpenForge design metadata, the useful read paths are
  `GET /v2/search/things?user_id=<devon>` (or `made_by`/`liked_by`),
  `GET /v2/things/{id}/complete`, and `GET /v2/files/{id}/download`
  (preceded by `GET /v2/things/{id}/secure`).
- No documented rate limits in the spec; be conservative and cache, per the project's
  cost-conscious/serverless posture.
- The spec lists local/staging/production servers; always target
  `https://api.thingiverse.com` and make relative `/v2/...` calls in code.
