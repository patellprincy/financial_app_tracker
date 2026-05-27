package com.finsightai.data.network

import com.finsightai.data.local.SessionManager
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit

object RetrofitClient {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    fun buildAuthApiService(sessionManager: SessionManager): AuthApiService =
        buildRetrofit(sessionManager).create(AuthApiService::class.java)

    fun buildTransactionApiService(sessionManager: SessionManager): TransactionApiService =
        buildRetrofit(sessionManager).create(TransactionApiService::class.java)

    fun buildInsightsApiService(sessionManager: SessionManager): InsightsApiService =
        buildRetrofit(sessionManager).create(InsightsApiService::class.java)

    private fun buildRetrofit(sessionManager: SessionManager): Retrofit {
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(sessionManager))
            .build()

        return Retrofit.Builder()
            .baseUrl(NetworkConfig.BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }
}
