package com.finsightai.presentation.insights

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.network.RetrofitClient
import com.finsightai.data.repository.InsightsRepositoryImpl
import com.finsightai.domain.model.InsightItem
import com.finsightai.domain.model.InsightSummary
import com.finsightai.domain.repository.InsightsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException

data class InsightsUiState(
    val isLoading: Boolean = false,
    val insights: List<InsightItem> = emptyList(),
    val summary: InsightSummary? = null,
    val error: String? = null
) {
    val isEmpty: Boolean get() = !isLoading && error == null && insights.isEmpty()
}

class InsightsViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)
    private val repository: InsightsRepository = InsightsRepositoryImpl(
        RetrofitClient.buildInsightsApiService(sessionManager)
    )

    private val _uiState = MutableStateFlow(InsightsUiState())
    val uiState: StateFlow<InsightsUiState> = _uiState.asStateFlow()

    init {
        loadInsights()
    }

    fun loadInsights() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            Log.d("InsightsViewModel", "loadInsights: starting API call")

            repository.getInsights()
                .onSuccess { response ->
                    Log.d("InsightsViewModel", "loadInsights: success — items=${response.items.size}")
                    _uiState.update {
                        it.copy(
                            isLoading = false,
                            insights = response.items,
                            summary = response.summary
                        )
                    }
                }
                .onFailure { ex ->
                    val errorMsg = when (ex) {
                        is HttpException -> "HTTP ${ex.code()}: ${ex.message()}"
                        else -> "Could not load insights. Check your connection."
                    }
                    Log.e("InsightsViewModel", "loadInsights: $errorMsg")
                    _uiState.update { it.copy(isLoading = false, error = errorMsg) }
                }
        }
    }
}
