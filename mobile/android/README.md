# Enterprise CRM — Android (Sprint 9)

Native Android client for the Enterprise CRM. **Reuses the existing REST API**
(`backend/`) end-to-end — no business logic is re-implemented on device.

> ⚠️ **Status: unverified scaffolding.** This code was authored without an
> Android/Gradle toolchain in the environment, so it has **not been compiled,
> run, or tested**. It is a correct-by-construction *walking skeleton* that
> establishes the architecture and must be built + verified in your Android CI
> (Android Studio / Gradle). Dependency versions below are indicative and should
> be pinned via a version catalog during first build.

## Architecture

Offline-first Clean Architecture + MVVM (see the Mobile Architecture document):

```
UI (Compose)  →  ViewModel  →  UseCase/Repository  →  { Retrofit API | Room cache | DataStore }
```

- The UI never touches the network directly — only the repository.
- The repository serves the **local cache first**, then reconciles with the API.
- Writes go to a local **outbox** flushed by WorkManager (pattern shown; outbox
  worker is a follow-up module).

## What's in this slice

| Area | Files | Notes |
|---|---|---|
| Core · network | `core/network/Network.kt` | Retrofit, OkHttp, auth header + 401 refresh, cert-pin hook |
| Core · session | `core/session/SessionManager.kt` | Encrypted DataStore token store |
| Core · security | `core/security/BiometricAuthenticator.kt` | BiometricPrompt gate |
| Core · database | `core/database/Database.kt` | Room + DAOs + Hilt module |
| Design | `core/design/Theme.kt` | Material 3, light/dark, brand tokens |
| Feature · auth | `feature/auth/Auth.kt`, `LoginScreen.kt` | `/auth/login` + `/auth/me`, biometric unlock |
| Feature · leads | `feature/leads/LeadsData.kt`, `LeadsScreen.kt` | **Offline-first** list off `/leads` |
| App | `app/App.kt` | Application, MainActivity, NavGraph |

## To extend (same patterns)

Dashboard, cockpit (call→disposition→follow-up), tasks, calendar, comms,
reports, AI — each is a `feature/<name>/` module with `data / domain / ui`,
wired through Hilt, cached in Room, and driven by a ViewModel.

## Build

```
# from mobile/android
./gradlew assembleDebug
```

Set the API base URL in `app/build.gradle.kts` (`API_BASE_URL` BuildConfig field).
