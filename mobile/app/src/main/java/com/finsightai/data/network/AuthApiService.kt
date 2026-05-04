package com.finsightai.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

@Serializable
data class LoginRequest(
    val email: String,
    val password: String
)

@Serializable
data class SignUpRequest(
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    val email: String,
    val password: String
)

@Serializable
data class UserResponse(
    val id: String,
    @SerialName("first_name") val firstName: String,
    @SerialName("last_name") val lastName: String,
    val email: String,
    val country: String,
    @SerialName("default_currency") val defaultCurrency: String,
    @SerialName("created_at") val createdAt: String
)

@Serializable
data class AuthResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String,
    val user: UserResponse
)

interface AuthApiService {
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse

    @POST("auth/signup")
    suspend fun signup(@Body request: SignUpRequest): AuthResponse

    @GET("auth/me")
    suspend fun getCurrentUser(): UserResponse
}
