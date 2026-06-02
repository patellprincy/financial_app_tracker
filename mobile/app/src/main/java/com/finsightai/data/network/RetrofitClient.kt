package com.finsightai.data.network

import com.finsightai.data.local.SessionManager
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        encodeDefaults = true
    }

    // Fast endpoints (auth, transactions, insights) use OkHttp's default 10s read
    // timeout. Statement upload/import are long-running on the backend (PDF parse +
    // AI cleanup; concurrent AI classification + ML anomaly detection per row), so
    // they get a much larger ceiling to avoid the client giving up mid-request.
    private const val DEFAULT_TIMEOUT_SECONDS = 30L
    private const val STATEMENT_TIMEOUT_SECONDS = 180L

    fun buildAuthApiService(sessionManager: SessionManager): AuthApiService =
        buildRetrofit(sessionManager).create(AuthApiService::class.java)

    fun buildTransactionApiService(sessionManager: SessionManager): TransactionApiService =
        buildRetrofit(sessionManager).create(TransactionApiService::class.java)

    fun buildInsightsApiService(sessionManager: SessionManager): InsightsApiService =
        buildRetrofit(sessionManager).create(InsightsApiService::class.java)

    fun buildStatementApiService(sessionManager: SessionManager): StatementApiService =
        buildRetrofit(sessionManager, timeoutSeconds = STATEMENT_TIMEOUT_SECONDS)
            .create(StatementApiService::class.java)

    private fun buildRetrofit(
        sessionManager: SessionManager,
        timeoutSeconds: Long = DEFAULT_TIMEOUT_SECONDS,
    ): Retrofit {
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(sessionManager))
            .connectTimeout(30, TimeUnit.SECONDS)
            // read/write/call govern how long we wait for the backend to finish
            // a slow request (e.g. a large statement import).
            .readTimeout(timeoutSeconds, TimeUnit.SECONDS)
            .writeTimeout(timeoutSeconds, TimeUnit.SECONDS)
            .callTimeout(timeoutSeconds, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(NetworkConfig.BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }
}
