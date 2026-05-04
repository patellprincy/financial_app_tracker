package com.finsightai.data.repository

import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.AuthApiService
import com.finsightai.data.network.LoginRequest
import com.finsightai.data.network.SignUpRequest
import com.finsightai.domain.repository.AuthRepository

class AuthRepositoryImpl(
    private val apiService: AuthApiService,
    private val sessionManager: SessionManager
) : AuthRepository {

    override suspend fun login(email: String, password: String): Result<Unit> = runCatching {
        val response = apiService.login(LoginRequest(email, password))
        sessionManager.saveSession(
            token = response.accessToken,
            firstName = response.user.firstName,
            lastName = response.user.lastName,
            email = response.user.email
        )
    }

    override suspend fun signup(
        firstName: String,
        lastName: String,
        email: String,
        password: String
    ): Result<Unit> = runCatching {
        val response = apiService.signup(SignUpRequest(firstName, lastName, email, password))
        sessionManager.saveSession(
            token = response.accessToken,
            firstName = response.user.firstName,
            lastName = response.user.lastName,
            email = response.user.email
        )
    }
}
