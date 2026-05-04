package com.finsightai.presentation.auth

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.RetrofitClient
import com.finsightai.data.repository.AuthRepositoryImpl
import com.finsightai.domain.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

data class LoginUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val isAuthenticated: Boolean = false
)

class LoginViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)
    private val repository: AuthRepository = AuthRepositoryImpl(
        RetrofitClient.buildAuthApiService(sessionManager),
        sessionManager
    )

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun login(email: String, password: String) {
        if (email.isBlank() || password.isBlank()) {
            _uiState.update { it.copy(error = "Please enter your email and password.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.login(email.trim(), password)
                .onSuccess {
                    _uiState.update { it.copy(isLoading = false, isAuthenticated = true) }
                }
                .onFailure { ex ->
                    _uiState.update { it.copy(isLoading = false, error = ex.toUserMessage()) }
                }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}

data class SignUpUiState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val isAuthenticated: Boolean = false
)

class SignUpViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)
    private val repository: AuthRepository = AuthRepositoryImpl(
        RetrofitClient.buildAuthApiService(sessionManager),
        sessionManager
    )

    private val _uiState = MutableStateFlow(SignUpUiState())
    val uiState: StateFlow<SignUpUiState> = _uiState.asStateFlow()

    fun signup(firstName: String, lastName: String, email: String, password: String) {
        if (firstName.isBlank() || lastName.isBlank() || email.isBlank() || password.isBlank()) {
            _uiState.update { it.copy(error = "Please fill in all fields.") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            repository.signup(firstName.trim(), lastName.trim(), email.trim(), password)
                .onSuccess {
                    _uiState.update { it.copy(isLoading = false, isAuthenticated = true) }
                }
                .onFailure { ex ->
                    _uiState.update { it.copy(isLoading = false, error = ex.toUserMessage()) }
                }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}

private fun Throwable.toUserMessage(): String = when (this) {
    is UnknownHostException -> "Cannot reach server. Check your connection."
    is ConnectException -> "Server is unavailable. Please try again later."
    is SocketTimeoutException -> "Request timed out. Please try again."
    is HttpException -> when (code()) {
        401 -> "Invalid email or password."
        409 -> "An account with this email already exists."
        422 -> "Please check your input and try again."
        429 -> "Too many attempts. Please wait and try again."
        else -> "Server error (${code()}). Please try again."
    }
    else -> message?.takeIf { it.isNotBlank() } ?: "Something went wrong. Please try again."
}
