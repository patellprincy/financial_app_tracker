package com.finsightai.data.network

import android.util.Log
import com.finsightai.core.AppAuthState
import com.finsightai.data.local.SessionManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(private val sessionManager: SessionManager) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val url = chain.request().url
        val token = runBlocking { sessionManager.accessToken.first() }
        val hasToken = !token.isNullOrBlank()
        Log.d("AuthInterceptor", "$url — hasToken=$hasToken")

        val request = if (hasToken) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }

        val response = chain.proceed(request)

        // Only treat 401/403 as session expiry when the request was authenticated.
        // Unauthenticated 401s (wrong password on /auth/login) must NOT clear the session.
        val isAuthenticatedRequest = request.header("Authorization") != null
        if ((response.code == 401 || response.code == 403) && isAuthenticatedRequest) {
            Log.w("AuthInterceptor", "$url → HTTP ${response.code} — token expired or invalid, clearing session")
            runBlocking { sessionManager.clearSession() }
            AppAuthState.notifyUnauthorized()
        } else if (!response.isSuccessful) {
            Log.w("AuthInterceptor", "$url → HTTP ${response.code}")
        }

        return response
    }
}
