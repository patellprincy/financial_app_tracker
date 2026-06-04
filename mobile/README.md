<div align="center">

# Finance Tracker — Android

**Native Android application built in Kotlin and Jetpack Compose, following Clean Architecture and MVVM. Communicates exclusively with the Main Backend — never directly with AI or ML services.**

<br/>

[![Kotlin](https://img.shields.io/badge/Kotlin-1.9-7F52FF?style=flat-square&logo=kotlin&logoColor=white)](https://kotlinlang.org)
[![Jetpack Compose](https://img.shields.io/badge/Jetpack%20Compose-BOM%202024-4285F4?style=flat-square&logo=android&logoColor=white)](https://developer.android.com/jetpack/compose)
[![Min SDK](https://img.shields.io/badge/Min%20SDK-API%2026%20(Android%208.0)-3DDC84?style=flat-square&logo=android&logoColor=white)](https://developer.android.com)
[![Architecture](https://img.shields.io/badge/Architecture-MVVM%20%2B%20Clean-009688?style=flat-square)](https://developer.android.com/topic/architecture)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Package Structure](#package-structure)
- [Screens and Features](#screens-and-features)
- [Network Layer](#network-layer)
- [Authentication](#authentication)
- [State Management](#state-management)
- [Error Handling](#error-handling)
- [Technology Stack](#technology-stack)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Build Instructions](#build-instructions)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Finance Tracker Android application is the user-facing layer of a three-service microservice platform. It provides a native mobile experience for personal finance tracking, transaction management, AI-powered category classification, and ML-driven anomaly detection.

All data operations are handled through the Main Backend. The app does not have direct access to the AI classification service or the ML anomaly detection service — the backend orchestrates those calls transparently. From the app's perspective, every API response includes already-classified and already-scored transaction data.

---

## Architecture

The application follows Clean Architecture with MVVM in the presentation layer.

```
┌──────────────────────────────────────────────────────────┐
│  Presentation Layer                                       │
│  Compose Screens  ←→  ViewModel  ←→  UiState (StateFlow) │
└──────────────────────────┬───────────────────────────────┘
                           │ calls
┌──────────────────────────▼───────────────────────────────┐
│  Domain Layer                                             │
│  Repository Interfaces  +  Domain Models                  │
│  (zero Android dependencies — pure Kotlin)               │
└──────────────────────────┬───────────────────────────────┘
                           │ implemented by
┌──────────────────────────▼───────────────────────────────┐
│  Data Layer                                               │
│  Repository Implementations  +  Network DTOs             │
│  SessionManager (JWT persistence)                         │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTP via Retrofit
┌──────────────────────────▼───────────────────────────────┐
│  Network Layer                                            │
│  Retrofit Service Interfaces  +  OkHttp Client           │
│  AuthInterceptor (JWT injection)                          │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS
                    Main Backend API
```

### Layer Responsibilities

**Presentation Layer** — Compose screens render state emitted by ViewModels as `StateFlow<UiState>`. Screens observe state and forward user events to ViewModels. No business logic lives in screens.

**Domain Layer** — Defines repository interfaces and domain models as plain Kotlin data classes with no Android framework dependency. This layer is independently testable.

**Data Layer** — Repository implementations satisfy domain interfaces by calling Retrofit services. They handle error mapping and DTO-to-domain model conversion. `SessionManager` manages JWT persistence.

**Network Layer** — Typed Retrofit interfaces, one per API domain. `AuthInterceptor` reads the stored JWT and injects it as a Bearer token on every outgoing request. A single shared `OkHttpClient` instance is reused across all service instances.

---

## Package Structure

```
com.finsightai/
│
├── core/
│   ├── AppAuthState.kt              Sealed class: Authenticated | Unauthenticated
│   └── SessionManager.kt            JWT read/write via SharedPreferences
│
├── data/
│   ├── local/                        Local persistence utilities
│   ├── network/
│   │   ├── ApiConfig.kt              Base URL constant
│   │   ├── AuthApiService.kt         /auth/* endpoints
│   │   ├── TransactionApiService.kt  /transactions/* endpoints
│   │   ├── InsightsApiService.kt     /insights endpoint
│   │   ├── StatementApiService.kt    /statements/* endpoints
│   │   ├── AuthInterceptor.kt        Bearer token injection
│   │   ├── NetworkConfig.kt          OkHttp builder configuration
│   │   └── RetrofitClient.kt         Singleton Retrofit instances
│   └── repository/
│       ├── AuthRepositoryImpl.kt
│       ├── TransactionRepositoryImpl.kt
│       ├── InsightsRepositoryImpl.kt
│       └── StatementRepositoryImpl.kt
│
├── domain/
│   ├── model/
│   │   ├── Transaction.kt
│   │   ├── DashboardData.kt
│   │   ├── InsightItem.kt
│   │   ├── InsightsResponse.kt
│   │   ├── InsightSummary.kt
│   │   ├── StatementUpload.kt
│   │   ├── ChatMessage.kt
│   │   └── SelectedFile.kt
│   └── repository/
│       ├── AuthRepository.kt
│       ├── TransactionRepository.kt
│       ├── InsightsRepository.kt
│       └── StatementRepository.kt
│
├── navigation/
│   ├── AppNavGraph.kt                NavHost with all route definitions
│   ├── BottomNavItem.kt              Bottom navigation item sealed class
│   └── NavRoutes.kt                  Route string constants
│
├── presentation/
│   ├── auth/
│   │   ├── LoginScreen.kt
│   │   ├── LoginViewModel.kt
│   │   └── SignUpScreen.kt
│   ├── home/
│   │   ├── HomeScreen.kt             Dashboard
│   │   └── HomeViewModel.kt
│   ├── transactions/
│   │   ├── TransactionsScreen.kt
│   │   ├── TransactionDetailScreen.kt
│   │   └── TransactionDetailViewModel.kt
│   ├── addexpense/
│   │   ├── AddExpenseScreen.kt
│   │   └── AddExpenseViewModel.kt
│   ├── insights/
│   │   ├── InsightsScreen.kt
│   │   └── InsightsViewModel.kt
│   ├── upload/                        PDF statement upload and import flow
│   ├── chat/
│   │   ├── ChatScreen.kt
│   │   └── ChatViewModel.kt
│   ├── settings/
│   │   ├── SettingsScreen.kt
│   │   └── SettingsViewModel.kt
│   ├── splash/
│   │   ├── SplashScreen.kt
│   │   └── SplashViewModel.kt
│   └── onboarding/
│       └── OnboardingScreen.kt
│
├── ui/
│   ├── components/                    Shared Compose composables
│   └── theme/                         MaterialTheme: colors, typography, shapes
│
└── MainActivity.kt                    Single activity; hosts NavHost
```

---

## Screens and Features

### Splash

Displayed on every app launch. `SplashViewModel` reads the stored JWT from `SessionManager`. If a valid token is found, the user is navigated directly to the Dashboard. If no token exists, the user is directed to Onboarding.

### Onboarding

Shown only on the first launch. Introduces the application's key capabilities before routing the user to Login.

### Authentication (Login / Sign Up)

- Login form collects email and password, calls `POST /auth/login`
- Sign Up form collects first name, last name, email, password, country, and currency, calls `POST /auth/signup`
- On success, the returned `access_token` is persisted via `SessionManager`
- Failed authentication shows an inline error message without clearing the form

### Home (Dashboard)

Displays:
- Current balance (income minus expenses)
- Total income and total expense for the period
- Recent transaction list

Data is fetched from `GET /transactions/dashboard` on composition. The ViewModel exposes a `StateFlow<HomeUiState>` with `Loading`, `Success`, and `Error` states.

### Transactions

Full transaction history fetched from `GET /transactions`. Ordered by creation date, descending. Each row shows merchant, amount, category, and anomaly indicator.

### Transaction Detail

Navigated to from the transaction list. Shows all fields including anomaly status, anomaly confidence score, and the human-readable reason string generated by the ML service.

### Add Expense

Manual transaction entry form. Accepts merchant name, amount, transaction type (income/expense), date, and optional notes. On submission, calls `POST /transactions/manual`. The backend handles AI classification and ML anomaly detection before returning the persisted result.

### Insights

Displays the feed returned by `GET /insights`. Only transactions with `anomaly_status: confirmed_anomaly` appear. Each item shows the category, description, flagged amount, and severity level (`low`, `medium`, or `high`).

### PDF Upload

A two-step flow:
1. The user selects a PDF file from their device storage
2. `POST /statements/upload` sends the file; the response is a parsed preview list
3. The user reviews the parsed transactions, edits if needed, and confirms
4. `POST /statements/{upload_id}/import` persists the approved rows with full AI classification and ML anomaly detection

### Chat

A conversational interface for finance-related questions. Messages are stored as a local list of `ChatMessage` domain objects. The ViewModel manages turn-based interaction.

### Settings

Displays user profile information and allows editing of currency and country preferences.

---

## Network Layer

### Client Configuration

All API services share a single `OkHttpClient` instance configured with:

- `AuthInterceptor` — reads the JWT from `SessionManager` on every request and appends `Authorization: Bearer <token>` to the headers automatically
- HTTP logging interceptor in debug builds only
- Connect timeout: 30 seconds
- Read timeout: 60 seconds (extended to accommodate large PDF uploads and slow Render cold-starts)

### Service Interfaces

| Interface | Base Path | Endpoints |
|---|---|---|
| `AuthApiService` | `/auth` | `POST /signup`, `POST /login`, `GET /me` |
| `TransactionApiService` | `/transactions` | `POST /manual`, `GET /`, `GET /dashboard`, `GET /{id}` |
| `InsightsApiService` | `/insights` | `GET /` |
| `StatementApiService` | `/statements` | `POST /upload`, `POST /{id}/import` |

### Base URL

```kotlin
// data/network/ApiConfig.kt
object ApiConfig {
    const val BASE_URL = "https://financial-app-tracker-backend.onrender.com/"
}
```

For local development, see the [Configuration](#configuration) section.

---

## Authentication

### Flow

```
App launch
  ↓
SplashViewModel.checkSession()
  reads SessionManager.getToken()
  ↓
Token exists  →  navigate to Home
Token absent  →  navigate to Onboarding → Login / Sign Up

Login / Sign Up:
  ↓
ViewModel calls AuthRepository
  ↓
AuthRepository calls AuthApiService (Retrofit)
  ↓
Backend validates credentials, returns { access_token }
  ↓
SessionManager.saveToken(token)
  ↓
Navigate to Home

Per-request token injection:
  ↓
AuthInterceptor.intercept()
  reads SessionManager.getToken()
  adds header: Authorization: Bearer <token>

Logout:
  ↓
SessionManager.clearToken()
  ↓
Navigate to Login
```

### SessionManager

`SessionManager` wraps `SharedPreferences` and exposes three synchronous operations:

```kotlin
fun saveToken(token: String)   // persists the JWT
fun getToken(): String?        // retrieves the JWT or null
fun clearToken()               // removes the JWT on logout
```

The 401 response from the backend (expired or invalid token) is caught in the repository layer, which clears the stored token and signals the presentation layer to redirect to Login.

---

## State Management

Each ViewModel exposes a `StateFlow<UiState>` where `UiState` is a sealed class with `Loading`, `Success(data)`, and `Error(message)` variants. Compose screens collect this flow using `collectAsStateWithLifecycle()`.

Pattern:

```kotlin
// ViewModel
private val _state = MutableStateFlow<TransactionsUiState>(TransactionsUiState.Loading)
val state: StateFlow<TransactionsUiState> = _state.asStateFlow()

fun loadTransactions() {
    viewModelScope.launch {
        _state.value = TransactionsUiState.Loading
        transactionRepository.getTransactions()
            .onSuccess { _state.value = TransactionsUiState.Success(it) }
            .onFailure { _state.value = TransactionsUiState.Error(it.message ?: "Unknown error") }
    }
}

// Screen
val state by viewModel.state.collectAsStateWithLifecycle()
when (val s = state) {
    is Loading  -> LoadingIndicator()
    is Success  -> TransactionList(s.transactions)
    is Error    -> ErrorMessage(s.message)
}
```

All async operations run via `viewModelScope.launch`. Repository suspend functions dispatch to `Dispatchers.IO` via `withContext`.

---

## Error Handling

| Error Type | Handling Strategy |
|---|---|
| Network unavailable | Repository catches `IOException`, returns `Result.failure` with user-facing message |
| HTTP 401 Unauthorized | Repository clears stored token, signals re-authentication |
| HTTP 4xx client error | Repository maps error body to a typed error message |
| HTTP 5xx server error | Repository surfaces a generic service error message |
| File too large (PDF) | Validated client-side before upload; server enforces 10 MB cap |
| Empty response | Repository returns `Result.failure` with descriptive message |

All error states surface in the ViewModel's `StateFlow` as `UiState.Error(message)`. Screens render the error message inline — no crash dialogs or unhandled exceptions reach the user.

---

## Technology Stack

| Technology | Role | Version |
|---|---|---|
| Kotlin | Primary language | 1.9.x |
| Jetpack Compose | Declarative UI framework | BOM 2024.x |
| Navigation Compose | Type-safe screen navigation | 2.7.x |
| ViewModel | Lifecycle-aware state holder | Jetpack |
| StateFlow / Flow | Reactive state emission | Coroutines 1.7.x |
| Coroutines | Async operations | 1.7.x |
| Retrofit | Type-safe HTTP client | 2.9.x |
| OkHttp | HTTP engine and interceptors | 4.x |
| Kotlin Serialisation | JSON serialisation | 1.6.x |
| Material 3 | Design system | Latest |
| Gradle (Kotlin DSL) | Build system | 9.4.x |

---

## Screenshots

| Screen | Description |
|---|---|
| Splash | App logo and JWT validation |
| Onboarding | Feature introduction |
| Login | Email/password form |
| Dashboard | Balance, income, expenses, recent list |
| Transactions | Full history list |
| Transaction Detail | Single row with anomaly detail |
| Add Expense | Manual entry form |
| Insights | Anomaly feed |
| PDF Upload | File picker and transaction preview |
| Settings | Profile and preferences |

*Screenshots will be added after UI stabilises.*

---

## Installation

### Option 1 — Download APK from GitHub Releases

Recommended for testers and recruiters. No development tools required.

1. Go to the [Releases](../../releases/latest) page of this repository
2. Download the latest `finance-tracker.apk`
3. On your Android device: **Settings > Security > Install unknown apps**
4. Enable installation from your file manager or browser
5. Open the APK and tap Install
6. Launch the app and create an account — the backend is live on Render

**Minimum Android version:** Android 8.0 (API level 26)

### Option 2 — Build from Source

See [Build Instructions](#build-instructions) below.

---

## Build Instructions

### Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Android Studio | Hedgehog 2023.1.1 | Electric Eel or newer also works |
| JDK | 17 | Bundled with Android Studio |
| Android SDK | API 26 (min), API 34 (target) | Install via SDK Manager |
| Gradle | 9.4.1 | Managed by the Gradle wrapper |

### Steps

1. Open Android Studio and select **File > Open**
2. Navigate to and open the `mobile/` directory (not the repository root)
3. Wait for the initial Gradle sync to complete — first sync downloads approximately 1 GB of dependencies
4. Update the base URL in `ApiConfig.kt` if connecting to a local backend (see [Configuration](#configuration))

#### Debug Build

```bash
cd mobile
./gradlew assembleDebug
```

Output: `app/build/outputs/apk/debug/app-debug.apk`

Install on a connected device via ADB:

```bash
adb install app/build/outputs/apk/debug/app-debug.apk
```

#### Release Build

```bash
./gradlew assembleRelease
```

A signing keystore must be configured in `app/build.gradle.kts` under `signingConfigs` before building a release APK for distribution.

#### Run Tests

```bash
./gradlew test                  # unit tests
./gradlew connectedAndroidTest  # instrumentation tests (device required)
```

#### Clean Build

```bash
./gradlew clean assembleDebug
```

---

## Configuration

### Pointing at a local backend

Update `app/src/main/java/com/finsightai/data/network/ApiConfig.kt`:

```kotlin
object ApiConfig {
    // Android Emulator → host machine (10.0.2.2 maps to localhost on host)
    const val BASE_URL = "http://10.0.2.2:8000/"

    // Physical device on same Wi-Fi network
    // const val BASE_URL = "http://192.168.1.x:8000/"

    // Production (default)
    // const val BASE_URL = "https://financial-app-tracker-backend.onrender.com/"
}
```

`localhost` from within an Android emulator resolves to the emulator itself, not the development machine. Use `10.0.2.2` to reach services running on the host.

---

## Troubleshooting

### Cannot connect to the backend

- Confirm the backend is running: `curl http://localhost:8000/health`
- Verify `ApiConfig.kt` has the correct URL for your environment
- On an emulator, use `10.0.2.2`, not `localhost`
- On a physical device, confirm both are on the same Wi-Fi network and no firewall blocks port 8000
- On Render, the free tier cold-starts — wait 20–30 seconds and retry

### Gradle sync fails

- Select **File > Invalidate Caches / Restart**
- Confirm you are using JDK 17 (**File > Project Structure > SDK Location**)
- Ensure an active internet connection is available for dependency resolution

### APK installation blocked

- Go to **Settings > Security > Install unknown apps**
- Enable installation from your browser or file manager
- This is the expected Android behaviour for APKs not distributed through the Play Store

### Login returns 401

- The JWT may have expired — tap logout and log in again for a fresh token
- If self-hosting, confirm `JWT_SECRET_KEY` is consistent across backend restarts

### Insights tab shows no items

- Anomaly detection requires at least 10 expense transactions in the user's history before the ML model engages (cold-start protection)
- Add more transactions — the ML service will automatically evaluate each new one
- Confirm the ML service is live on Render and `model_ready: true` appears in its startup logs

### PDF upload fails

- The server accepts only `application/pdf` files — confirm the selected file is a PDF
- Maximum upload size is 10 MB
- The PDF must be text-based (searchable), not a scanned image; pdfplumber cannot extract text from images
