package com.finsightai.data.repository

import android.util.Log
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.AuthApiService
import com.finsightai.data.network.LoginRequest
import com.finsightai.data.network.SignUpRequest
import com.finsightai.domain.repository.AuthRepository
import retrofit2.HttpException

class AuthRepositoryImpl(
    private val apiService: AuthApiService,
    private val sessionManager: SessionManager
) : AuthRepository {

    override suspend fun login(email: String, password: String): Result<Unit> = runCatching {
        Log.d("AuthRepo", "login: calling API — email=$email")
        val response = apiService.login(LoginRequest(email, password))
        Log.d("AuthRepo", "login: success — user=${response.user.email}")
        sessionManager.saveSession(
            token = response.accessToken,
            firstName = response.user.firstName,
            lastName = response.user.lastName,
            email = response.user.email
        )
        Log.d("AuthRepo", "login: session saved")
        Unit
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("AuthRepo", "login: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("AuthRepo", "login: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }

    override suspend fun signup(
        firstName: String,
        lastName: String,
        email: String,
        password: String
    ): Result<Unit> = runCatching {
        Log.d("AuthRepo", "signup: calling API — email=$email")
        val response = apiService.signup(SignUpRequest(firstName, lastName, email, password))
        Log.d("AuthRepo", "signup: success — user=${response.user.email}")
        sessionManager.saveSession(
            token = response.accessToken,
            firstName = response.user.firstName,
            lastName = response.user.lastName,
            email = response.user.email
        )
        Log.d("AuthRepo", "signup: session saved")
        Unit
    }.onFailure { ex ->
        when (ex) {
            is HttpException -> Log.e("AuthRepo", "signup: HTTP ${ex.code()} ${ex.message()}")
            else -> Log.e("AuthRepo", "signup: ${ex.javaClass.simpleName} — ${ex.message}")
        }
    }
}
