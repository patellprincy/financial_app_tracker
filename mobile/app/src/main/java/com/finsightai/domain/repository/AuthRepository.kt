package com.finsightai.domain.repository

interface AuthRepository {
    suspend fun login(email: String, password: String): Result<Unit>
    suspend fun signup(firstName: String, lastName: String, email: String, password: String): Result<Unit>
}
