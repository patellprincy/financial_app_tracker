package com.finsightai.presentation.splash

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.RetrofitClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import retrofit2.HttpException

class SplashViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)
    private val apiService = RetrofitClient.buildAuthApiService(sessionManager)

    sealed class Destination {
        object Onboarding : Destination()
        object Home : Destination()
        object Login : Destination()
    }

    private val _destination = MutableStateFlow<Destination?>(null)
    val destination: StateFlow<Destination?> = _destination.asStateFlow()

    init {
        viewModelScope.launch { checkSession() }
    }

    private suspend fun checkSession() {
        val token = sessionManager.accessToken.first()
        Log.d("SplashViewModel", "checkSession: token=${if (token != null) "exists" else "null"}")

        if (token.isNullOrBlank()) {
            val hasLoggedInBefore = sessionManager.hasLoggedInBefore.first()
            Log.d("SplashViewModel", "checkSession: no token — hasLoggedInBefore=$hasLoggedInBefore")
            _destination.value = if (hasLoggedInBefore) Destination.Login else Destination.Onboarding
            return
        }

        try {
            Log.d("SplashViewModel", "checkSession: calling /auth/me to validate token")
            apiService.getCurrentUser()
            Log.d("SplashViewModel", "checkSession: token valid → Home")
            _destination.value = Destination.Home
        } catch (e: HttpException) {
            when (e.code()) {
                401, 403 -> {
                    // AuthInterceptor already cleared session and emitted AppAuthState.unauthorizedEvent.
                    // The global handler in AppNavGraph will navigate to Login.
                    // Do NOT set destination here — setting it would cause a second concurrent navigation.
                    Log.w("SplashViewModel", "checkSession: HTTP ${e.code()} — session expired, global handler navigating to Login")
                }
                else -> {
                    Log.w("SplashViewModel", "checkSession: HTTP ${e.code()} — proceeding to Home")
                    _destination.value = Destination.Home
                }
            }
        } catch (e: Exception) {
            // Network error (no connection, timeout, etc.) — don't invalidate the session.
            // Proceed to Home optimistically; individual screens will handle further failures.
            Log.w("SplashViewModel", "checkSession: ${e.javaClass.simpleName} — no network, proceeding to Home")
            _destination.value = Destination.Home
        }
    }
}
