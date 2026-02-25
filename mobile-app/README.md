# Music School Mobile (KMM)

This folder contains a Kotlin Multiplatform Mobile blueprint + scaffold for Android and iOS, aligned with your Flask `/api/v1` backend.

## Milestones (implemented scaffold)

### Milestone 1 — Student core
- Auth/session role flow in shared interfaces
- Availability + booking APIs wired in shared client
- Android + iOS student tab scaffold

### Milestone 2 — Teacher core
- Teacher bookings + attendance APIs in shared client
- Teacher tab scaffold in Android + iOS

### Milestone 3 — Admin core
- Admin booking APIs in shared client
- Admin tab scaffold in Android + iOS

### Milestone 4 — Production hardening (next)
- JWT refresh flow for mobile
- Offline cache (SQLDelight)
- Push notifications
- CI/CD for Play Store + TestFlight

## Project layout
- `shared/` Kotlin Multiplatform shared networking/domain module
- `androidApp/` Android app (Jetpack Compose)
- `iosApp/` iOS SwiftUI scaffold consuming shared module

## Run Android
```bash
cd mobile-app
gradle :androidApp:assembleDebug
```

## Run tests
```bash
cd mobile-app
gradle :shared:allTests
```


## Theme alignment with website
- Mobile palette now maps your web CSS colors:
  - Primary violet `#6b4eff` (web accent)
  - Gold accent `#ffcc66`
  - Student orange `#ff8f3d`
  - Teacher/Admin green `#18a957`
- Android applies this in Compose Material theme (`ui/theme/AppTheme.kt`).
- iOS applies this in SwiftUI theme constants (`iosApp/MusicSchoolApp/AppTheme.swift`).

## iOS note
iOS app compilation requires Xcode on macOS. Linux environment cannot build iOS GUI binaries.
